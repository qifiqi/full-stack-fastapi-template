"""Worker engine: task-type registry, claim loops, heartbeat and watchdog.

Implements docs/migration/03-architecture.md §3:
- task-poller (3-5s): DB claim with affected-rows check, cancel bridging
- heartbeat (15s)
- watchdog (60s): heartbeat-timeout eviction with attempt=N/3 protocol
- ThreadPoolExecutor with per-type concurrency quotas
"""

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import update
from sqlmodel import Session, col, func, select

from app.core.config import settings
from app.crud import create_task_log
from app.models import GoogleSheet, GoogleSheetToken, ScheduledTask, Task, TaskLogCreate
from app.services.config_manager import ConfigManager
from app.services.google_sheet.registry_service import GoogleSheetRegistryService
from app.services.google_sheet.token_service import GoogleSheetTokenService
from app.services.tasks.errors import (
    NETWORK_ERROR_PREFIX,
    WATCHDOG_RESTART_PREFIX,
)

logger = logging.getLogger("app.worker")


@dataclass(frozen=True)
class TaskTypeSpec:
    type_key: str
    display_name: str
    service_name: str  # import path of the engine class within app.services
    max_concurrency_key: str
    max_concurrency_default: int = 4


GLOBAL_MAX_KEY = "task_max_workers"
GLOBAL_MAX_DEFAULT = 8

TASK_TYPE_REGISTRY: dict[str, TaskTypeSpec] = {
    spec.type_key: spec
    for spec in (
        TaskTypeSpec(
            "google_sheet",
            "C3",
            "google_sheet_tasks.c3.C3Service",
            "task_concurrency_google_sheet",
        ),
        TaskTypeSpec(
            "google_sheet_c4",
            "C4",
            "google_sheet_tasks.c4.C4Service",
            "task_concurrency_google_sheet_c4",
        ),
        TaskTypeSpec(
            "google_sheet_c5",
            "C5",
            "google_sheet_tasks.c5.C5Service",
            "task_concurrency_google_sheet_c5",
        ),
        TaskTypeSpec(
            "google_sheet_c7",
            "C7",
            "google_sheet_tasks.c7.C7Service",
            "task_concurrency_google_sheet_c7",
        ),
        TaskTypeSpec(
            "backtest_training",
            "单品回测",
            "backtest.training_service.BacktestTrainingService",
            "task_concurrency_backtest_training",
        ),
        TaskTypeSpec(
            "backtest_multi_product",
            "多品回测",
            "backtest.multi_product_service.BacktestMultiProductService",
            "task_concurrency_backtest_multi_product",
        ),
    )
}

ATTEMPT_PATTERN = r"attempt=(\d+)/(\d+)"
MAX_RESTART_ATTEMPTS = 3
HEARTBEAT_TIMEOUT_MINUTES = 10


def get_task_type_spec(task_type: str | None) -> TaskTypeSpec | None:
    return TASK_TYPE_REGISTRY.get((task_type or "").strip().lower())


def _import_service_class(service_path: str) -> type:
    module_name, class_name = service_path.rsplit(".", 1)
    import importlib

    module = importlib.import_module(f"app.services.{module_name}")
    return cast("type[Any]", getattr(module, class_name))


class TaskManager:
    """Single-instance worker state: claim, execute, bridge cancel, watchdog."""

    def __init__(self, session_factory: Any, instance_id: str | None = None) -> None:
        self.session_factory = session_factory
        self.instance_id = instance_id or settings.worker_instance_id
        self.stop_event = threading.Event()
        self._pool: ThreadPoolExecutor | None = None
        self._pool_lock = threading.Lock()
        self.task_stop_events: dict[int, threading.Event] = {}
        self.task_execution_types: dict[int, str] = {}
        self.task_token_occupancy: dict[int, int] = {}
        self._runtime_state_lock = threading.RLock()
        self.backtest_sheet_start_lock = threading.RLock()
        self.config: ConfigManager | None = None
        self.token_service: GoogleSheetTokenService | None = None
        self.registry_service: GoogleSheetRegistryService | None = None

    # -- wiring -------------------------------------------------------------
    def bind(self, config: ConfigManager) -> None:
        self.config = config
        self.token_service = GoogleSheetTokenService(self.session_factory)
        self.registry_service = GoogleSheetRegistryService(self.session_factory)

    def _get_config_value(self, key: str, default: Any) -> Any:
        if self.config is not None:
            return self.config.get_config(key, default)
        return default

    def _get_pool(self) -> ThreadPoolExecutor:
        with self._pool_lock:
            if self._pool is None:
                max_workers = int(
                    self._get_config_value(GLOBAL_MAX_KEY, settings.task_max_workers)
                )
                self._pool = ThreadPoolExecutor(
                    max_workers=max(max_workers, 1), thread_name_prefix="task_worker"
                )
            return self._pool

    # -- DB helpers ---------------------------------------------------------
    def _claim_task(self, session: Session, task_id: int) -> bool:
        """Atomic claim: affected rows == 1 means this instance owns the task."""
        now = datetime.now(UTC)
        statement = (
            update(Task)
            .where(col(Task.id) == task_id, col(Task.status).in_(["pending", "queued"]))
            .values(
                status="running",
                running_instance=self.instance_id,
                heartbeat_at=now,
                started_at=func.coalesce(col(Task.started_at), now),
                stop_requested=False,
            )
        )
        result = session.exec(statement)
        session.commit()
        return bool(result.rowcount == 1)

    def count_running_by_type(self, session: Session) -> dict[str, int]:
        rows = session.exec(
            select(Task.task_type, func.count())
            .where(
                Task.status == "running",
                Task.running_instance == self.instance_id,
            )
            .group_by(Task.task_type)
        ).all()
        return dict(rows)

    def _load_claimable_tasks(self, session: Session, slots: int) -> list[Task]:
        if slots <= 0:
            return []
        statement = (
            select(Task)
            .where(col(Task.status).in_(["pending", "queued"]))
            .order_by(col(Task.created_at).asc(), col(Task.id).asc())
            .limit(slots)
        )
        return list(session.exec(statement).all())

    # -- poller -------------------------------------------------------------
    def poller_tick(self) -> None:
        """One poller pass: claim tasks up to quotas, bridge stop requests."""
        with self.session_factory() as session:
            global_max = int(
                self._get_config_value(GLOBAL_MAX_KEY, settings.task_max_workers)
            )
            running = self.count_running_by_type(session)
            running_total = sum(running.values())
            slots = global_max - running_total
            if slots <= 0:
                self._bridge_stop_requests(session)
                return

            claimed: list[int] = []
            for task in self._load_claimable_tasks(session, slots * 2):
                spec = get_task_type_spec(task.task_type)
                if spec is None:
                    self._reject_unregistered(session, task)
                    continue
                type_limit = int(
                    self._get_config_value(
                        spec.max_concurrency_key, spec.max_concurrency_default
                    )
                )
                if running.get(task.task_type, 0) >= type_limit:
                    continue
                if self._claim_task(session, int(task.id or 0)):
                    running[task.task_type] = running.get(task.task_type, 0) + 1
                    claimed.append(int(task.id or 0))
                if sum(running.values()) >= global_max:
                    break

        for task_id in claimed:
            self._dispatch(task_id)

        with self.session_factory() as session:
            self._bridge_stop_requests(session)

    def _reject_unregistered(self, session: Session, task: Task) -> None:
        task.status = "error"
        task.error_message = f"未注册的任务类型: {task.task_type}"
        task.finished_at = datetime.now(UTC)
        session.add(task)
        session.commit()
        create_task_log(
            session=session,
            log_in=TaskLogCreate(
                task_id=int(task.id or 0), level="ERROR", message=task.error_message
            ),
        )

    def _bridge_stop_requests(self, session: Session) -> None:
        statement = select(Task).where(
            Task.status == "running",
            Task.running_instance == self.instance_id,
            col(Task.stop_requested) == True,  # noqa: E712
        )
        for task in session.exec(statement).all():
            with self._runtime_state_lock:
                event = self.task_stop_events.get(int(task.id or 0))
            if event is not None:
                event.set()

    # -- dispatch / execution ----------------------------------------------
    def _dispatch(self, task_id: int) -> None:
        spec = self._get_spec_for_task(task_id)
        if spec is None:
            return
        stop_event = threading.Event()
        with self._runtime_state_lock:
            self.task_stop_events[task_id] = stop_event
            self.task_execution_types[task_id] = spec.type_key
        try:
            self._get_pool().submit(self._run_task, task_id, spec, stop_event)
        except Exception:
            with self._runtime_state_lock:
                self.task_stop_events.pop(task_id, None)
                self.task_execution_types.pop(task_id, None)
            raise

    def _get_spec_for_task(self, task_id: int) -> TaskTypeSpec | None:
        with self._runtime_state_lock:
            type_key = self.task_execution_types.get(task_id)
        if type_key:
            return TASK_TYPE_REGISTRY.get(type_key)
        with self.session_factory() as session:
            task = session.get(Task, task_id)
            return get_task_type_spec(task.task_type) if task else None

    def _run_task(
        self, task_id: int, spec: TaskTypeSpec, stop_event: threading.Event
    ) -> None:
        status = "error"
        error_message: str | None = None
        try:
            service_class = _import_service_class(spec.service_name)
            with self.session_factory() as session:
                task = session.get(Task, task_id)
                if task is None:
                    return
                if task.status == "cancelled":
                    return
                config = dict(task.config or {})
            engine = service_class(
                config,
                task_id,
                session_factory=self.session_factory,
                settings=settings,
                stop_event=stop_event,
            )
            result = engine.execute_task()
            status = (
                result if result in {"completed", "cancelled", "error"} else "error"
            )
        except Exception as exc:  # noqa: BLE001
            from app.services.tasks.errors import (
                build_task_error_record,
                unwrap_exception,
            )

            root = unwrap_exception(exc)
            error_message = f"{type(root or exc).__name__}: {root or exc}"[:500]
            logger.exception("任务执行异常: task_id=%s", task_id)
            try:
                with self.session_factory() as session:
                    create_task_log(
                        session=session,
                        log_in=TaskLogCreate(
                            task_id=task_id,
                            level="ERROR",
                            message=f"trace_id={build_task_error_record(exc, 'execute', task_id).trace_id} {error_message}",
                        ),
                    )
            except Exception:
                pass
        finally:
            self._finalize_task(task_id, status, error_message, stop_event)

    def _finalize_task(
        self,
        task_id: int,
        status: str,
        error_message: str | None,
        stop_event: threading.Event,
    ) -> None:
        now = datetime.now(UTC)
        try:
            with self.session_factory() as session:
                task = session.get(Task, task_id)
                if task is None:
                    return
                if stop_event.is_set() or status == "cancelled":
                    task.status = "cancelled"
                elif status == "completed":
                    task.status = "success"
                else:
                    task.status = "error"
                    task.error_message = error_message or task.error_message
                task.finished_at = now
                task.running_instance = None
                task.heartbeat_at = None
                session.add(task)
                session.commit()
        except Exception:
            logger.exception("任务收尾失败: task_id=%s", task_id)
        finally:
            self._release_occupancy(task_id, is_backtest=False)
            with self._runtime_state_lock:
                self.task_stop_events.pop(task_id, None)
                self.task_execution_types.pop(task_id, None)

    def _release_occupancy(self, task_id: int, *, is_backtest: bool) -> None:
        try:
            with self.session_factory() as session:
                if self.registry_service is not None:
                    self.registry_service.release_for_task(session, task_id)
                token_id = self.task_token_occupancy.pop(task_id, None)
                if token_id and self.token_service is not None:
                    self.token_service.release_usage(session, token_id)
                if is_backtest:
                    from app.crud import release_sheet_lock

                    release_sheet_lock(
                        session=session, spreadsheet_id=f"task:{task_id}"
                    )
        except Exception:
            logger.exception("释放任务占用失败: task_id=%s", task_id)

    # -- heartbeat ----------------------------------------------------------
    def heartbeat(self) -> None:
        statement = (
            update(Task)
            .where(
                col(Task.status) == "running",
                col(Task.running_instance) == self.instance_id,
            )
            .values(heartbeat_at=datetime.now(UTC))
        )
        with self.session_factory() as session:
            session.exec(statement)
            session.commit()

    # -- watchdog -----------------------------------------------------------
    def watchdog_tick(self) -> None:
        """Evict tasks whose heartbeat expired; attempt=N/3 protocol preserved."""
        cutoff = datetime.now(UTC) - timedelta(days=5)
        stale_before = datetime.now(UTC) - timedelta(minutes=HEARTBEAT_TIMEOUT_MINUTES)
        with self.session_factory() as session:
            statement = select(Task).where(
                Task.status == "running",
                col(Task.created_at) >= cutoff,
                Task.running_instance == self.instance_id,
                col(Task.heartbeat_at) < stale_before,
            )
            stale_tasks = list(session.exec(statement).all())

        for task in stale_tasks:
            task_id = int(task.id or 0)
            attempt = self._parse_attempt(task.error_message) + 1
            self._force_detach_running_task(task_id)
            try:
                self._release_occupancy(task_id, is_backtest=False)
            except Exception:
                logger.exception("watchdog 释放占用失败: task_id=%s", task_id)
            with self.session_factory() as session:
                db_task = session.get(Task, task_id)
                if db_task is None:
                    continue
                if attempt < MAX_RESTART_ATTEMPTS:
                    db_task.status = "pending"
                    db_task.running_instance = None
                    db_task.heartbeat_at = None
                    db_task.error_message = f"{WATCHDOG_RESTART_PREFIX} attempt={attempt}/{MAX_RESTART_ATTEMPTS} reason=heartbeat_timeout"
                    session.add(db_task)
                    session.commit()
                    create_task_log(
                        session=session,
                        log_in=TaskLogCreate(
                            task_id=task_id,
                            level="WARNING",
                            message=f"watchdog 检测到心跳超时, 任务已重置待重启 (attempt={attempt}/{MAX_RESTART_ATTEMPTS})",
                        ),
                    )
                else:
                    db_task.status = "error"
                    db_task.finished_at = datetime.now(UTC)
                    db_task.running_instance = None
                    db_task.heartbeat_at = None
                    db_task.error_message = f"watchdog 已放弃自动重启 (尝试 {attempt} 次, reason=heartbeat_timeout)"
                    session.add(db_task)
                    session.commit()

        # error tasks flagged retryable go back to pending once
        with self.session_factory() as session:
            statement = select(Task).where(
                Task.status == "error",
                col(Task.created_at) >= cutoff,
                col(Task.error_message).like(f"{NETWORK_ERROR_PREFIX}%"),
            )
            retryable = list(session.exec(statement).all())
            for task in retryable:
                task.status = "pending"
                task.running_instance = None
                session.add(task)
            if retryable:
                session.commit()

        # scheduled_task stale locks takeover window is enforced at claim time
        self._recover_stale_scheduled_locks()

    def _parse_attempt(self, error_message: str | None) -> int:
        import re

        if not error_message:
            return 0
        match = re.search(ATTEMPT_PATTERN, error_message)
        return int(match.group(1)) if match else 0

    def _force_detach_running_task(self, task_id: int) -> None:
        with self._runtime_state_lock:
            event = self.task_stop_events.pop(task_id, None)
            self.task_execution_types.pop(task_id, None)
        if event is not None:
            event.set()

    def _recover_stale_scheduled_locks(self) -> None:
        timeout_hours = float(
            self._get_config_value(
                "scheduled_task_lock_timeout_hours",
                settings.scheduled_task_lock_timeout_hours,
            )
        )
        stale_before = datetime.now(UTC) - timedelta(hours=timeout_hours)
        with self.session_factory() as session:
            statement = select(ScheduledTask).where(
                col(ScheduledTask.is_running) == True,  # noqa: E712
                col(ScheduledTask.last_run_at) < stale_before,
            )
            for row in session.exec(statement).all():
                logger.warning("接管过期调度锁: scheduled_task=%s", row.id)
                row.is_running = False
                row.running_instance_id = None
                session.add(row)
            session.commit()

    # -- runtime recovery (worker startup) ----------------------------------
    def recover_on_startup(self) -> None:
        from app.crud import clear_sheet_locks

        with self.session_factory() as session:
            clear_sheet_locks(session=session)
            for sheet in session.exec(select(GoogleSheet)).all():
                sheet.is_in_use = False
                sheet.current_task_id = None
                session.add(sheet)
            session.exec(update(GoogleSheetToken).values(current_in_use_count=0))
            session.commit()

        with self.session_factory() as session:
            statement = select(Task).where(
                Task.status == "running",
                Task.running_instance == self.instance_id,
            )
            for task in session.exec(statement).all():
                task.status = "pending"
                task.running_instance = None
                task.heartbeat_at = None
                session.add(task)
            session.commit()

    # -- API-facing actions -------------------------------------------------
    def request_stop(self, task_id: int) -> bool:
        """API cancel: set stop_requested; worker bridges it to the stop event."""
        with self.session_factory() as session:
            task = session.get(Task, task_id)
            if task is None or task.status != "running":
                return False
            task.stop_requested = True
            session.add(task)
            session.commit()
        with self._runtime_state_lock:
            event = self.task_stop_events.get(task_id)
        if event is not None:
            event.set()
        return True

    def submit_job_task(self, job_name: str, params: dict[str, Any] | None) -> bool:
        """Run a whitelisted cleanup job in-process (job subprocess entrypoint)."""
        from app.services.tasks import data_cleanup

        jobs: dict[str, Callable[[Session, dict[str, Any] | None], bool]] = {
            "cleanup_old_logs": data_cleanup.cleanup_old_logs,
            "cleanup_old_results": data_cleanup.cleanup_old_results,
            "cleanup_old_data": data_cleanup.cleanup_old_data,
        }
        handler = jobs.get(job_name)
        if handler is None:
            logger.error("未知的清理任务类型: %s", job_name)
            return False
        with self.session_factory() as session:
            return handler(session, params)

    def runtime_snapshot(self) -> dict[str, Any]:
        with self._runtime_state_lock:
            return {
                "stop_event_task_ids": sorted(self.task_stop_events.keys()),
                "token_occupancy_task_ids": sorted(self.task_token_occupancy.keys()),
            }
