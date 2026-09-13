"""Cron scheduler loop (croniter + DB run lock + subprocess jobs).

Replaces APScheduler (03 §3.4 / decision ⑧): a 30s tick loads enabled
scheduled tasks, claims the DB run lock (stale-lock takeover after
``scheduled_task_lock_timeout_hours``) and runs whitelisted cleanup jobs in a
subprocess ``python -m app.worker --job <id> --instance <id>``.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from croniter import CroniterBadCronError, croniter  # type: ignore[import-untyped]
from sqlmodel import Session, col, select

from app.core.config import settings
from app.models import ScheduledTask

logger = logging.getLogger("app.scheduler")

CLEANUP_JOB_TYPES = {"cleanup_old_logs", "cleanup_old_results", "cleanup_old_data"}
DEFAULT_SEED_TASK: dict[str, Any] = {
    "name": "每日数据清理",
    "task_type": "cleanup_old_data",
    "cron_expression": "0 0 * * *",
    "params": {"days": 10},
}


def validate_cron_expression(expression: str) -> bool:
    try:
        croniter(expression)
        return True
    except CroniterBadCronError, ValueError:
        return False


def next_fire_time(expression: str, base: datetime | None = None) -> datetime | None:
    try:
        cron = croniter(expression, base or datetime.now(UTC))
        return cast("datetime", cron.get_next(datetime))
    except CroniterBadCronError, ValueError:
        return None


def seed_default_tasks(session: Session) -> None:
    """Idempotently ensure the default daily cleanup task exists."""
    existing = session.exec(
        select(ScheduledTask).where(ScheduledTask.name == DEFAULT_SEED_TASK["name"])
    ).first()
    if existing is not None:
        return
    session.add(
        ScheduledTask(
            name=DEFAULT_SEED_TASK["name"],
            task_type=DEFAULT_SEED_TASK["task_type"],
            cron_expression=DEFAULT_SEED_TASK["cron_expression"],
            params=DEFAULT_SEED_TASK["params"],
            enabled=True,
        )
    )
    session.commit()


def acquire_run_lock(
    session: Session,
    task_id: int,
    instance_id: str,
    *,
    stale_before: datetime | None = None,
) -> bool:
    """Conditional UPDATE claim; affected rows == 1 means this instance won."""
    from sqlalchemy import update

    now = datetime.now(UTC)
    statement = update(ScheduledTask).where(col(ScheduledTask.id) == task_id)
    if stale_before is None:
        statement = statement.where(col(ScheduledTask.is_running) == False)  # noqa: E712
    else:
        from sqlalchemy import or_

        statement = statement.where(
            or_(
                col(ScheduledTask.is_running) == False,  # noqa: E712
                col(ScheduledTask.last_run_at).is_(None),
                col(ScheduledTask.last_run_at) < stale_before,
            )
        )
    statement = statement.values(
        is_running=True, running_instance_id=instance_id, last_run_at=now
    )
    result = session.exec(statement)
    session.commit()
    return bool(result.rowcount == 1)


def release_run_lock(session: Session, task_id: int, instance_id: str) -> bool:
    from sqlalchemy import update

    statement = (
        update(ScheduledTask)
        .where(
            col(ScheduledTask.id) == task_id,
            col(ScheduledTask.running_instance_id) == instance_id,
        )
        .values(is_running=False, running_instance_id=None)
    )
    result = session.exec(statement)
    session.commit()
    return bool(result.rowcount == 1)


def subprocess_log_path(task_id: int) -> str:
    return os.path.join(os.getcwd(), "logs", f"scheduled_task_{task_id}.log")


def run_job_in_subprocess(
    task_id: int, instance_id: str
) -> subprocess.Popen[str] | None:
    """Spawn ``python -m app.worker --job <id> --instance <id>``."""
    command = [
        sys.executable,
        "-m",
        "app.worker",
        "--job",
        str(task_id),
        "--instance",
        instance_id,
    ]
    log_path = subprocess_log_path(task_id)
    output_target: Any
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        output_target = open(log_path, "a", encoding="utf-8")  # noqa: SIM115
    except OSError:
        output_target = subprocess.DEVNULL
    kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        process: subprocess.Popen[str] = subprocess.Popen(
            command,
            stdout=output_target,
            stderr=subprocess.STDOUT,
            cwd=".",
            **kwargs,
        )
        return process
    except OSError:
        logger.exception("调度子进程启动失败: scheduled_task=%s", task_id)
        return None


class CronScheduler:
    """30s tick loop over enabled scheduled tasks."""

    def __init__(self, session_factory: Any, instance_id: str | None = None) -> None:
        self.session_factory = session_factory
        self.instance_id = instance_id or f"sched-{settings.worker_instance_id}"
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def tick(self) -> None:
        with self.session_factory() as session:
            tasks = list(
                session.exec(
                    select(ScheduledTask).where(col(ScheduledTask.enabled))
                ).all()  # noqa: E712
            )
        for task in tasks:
            if self._stop:
                return
            if task.task_type not in CLEANUP_JOB_TYPES:
                continue
            if not croniter.is_valid(task.cron_expression):
                continue
            now = datetime.now(UTC)
            try:
                previous = croniter(task.cron_expression, now).get_prev(datetime)
            except CroniterBadCronError, ValueError:
                continue
            if task.last_run_at is not None and task.last_run_at >= previous:
                continue  # already ran inside the current cron window

            timeout_hours = float(settings.scheduled_task_lock_timeout_hours)
            stale_before = now - timedelta(hours=timeout_hours)
            with self.session_factory() as session:
                claimed = acquire_run_lock(
                    session,
                    int(task.id or 0),
                    self.instance_id,
                    stale_before=stale_before,
                )
            if not claimed:
                continue
            process = run_job_in_subprocess(int(task.id or 0), self.instance_id)
            if process is None:
                with self.session_factory() as session:
                    release_run_lock(session, int(task.id or 0), self.instance_id)

    def finalize_run(
        self, task_id: int, success: bool, error: str | None = None
    ) -> None:
        with self.session_factory() as session:
            release_run_lock(session, task_id, self.instance_id)
            task = session.get(ScheduledTask, task_id)
            if task is not None:
                task.last_status = "success" if success else "error"
                task.last_error = error
                task.last_run_at = datetime.now(UTC)
                session.add(task)
                session.commit()
