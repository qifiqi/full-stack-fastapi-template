"""Worker entrypoint: ``python -m app.worker [--job ID --instance ID]``.

Main mode runs startup recovery + the four loops (poller 5s / heartbeat 15s /
watchdog 60s / cron scheduler 30s). Job mode runs one scheduled cleanup task
in a subprocess and exits (03 §3.4/§4).
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
from typing import Any

from sqlmodel import Session

from app.core import scheduler as scheduler_module
from app.core.db import engine
from app.core.workers import TaskManager
from app.models import ScheduledTask
from app.services.config_manager import init_config_manager
from app.services.tasks.data_cleanup import (
    cleanup_old_data,
    cleanup_old_logs,
    cleanup_old_results,
)

logger = logging.getLogger("app.worker")

JOB_HANDLERS = {
    "cleanup_old_logs": cleanup_old_logs,
    "cleanup_old_results": cleanup_old_results,
    "cleanup_old_data": cleanup_old_data,
}


def _session_factory() -> Session:
    return Session(engine)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        import os

        from concurrent_log_handler import ConcurrentRotatingFileHandler

        os.makedirs("logs", exist_ok=True)
        handler = ConcurrentRotatingFileHandler(
            "logs/worker.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=10,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        logging.getLogger().addHandler(handler)
    except Exception:
        pass  # plain stdout logging is an acceptable fallback


def run_job(task_id: int, instance_id: str) -> bool:
    """Job subprocess entrypoint: execute one whitelisted cleanup task."""
    with _session_factory() as session:
        task = session.get(ScheduledTask, task_id)
        if task is None:
            logger.error("调度任务不存在: %s", task_id)
            return False
        handler = JOB_HANDLERS.get(task.task_type)
        if handler is None:
            logger.error("未知的清理任务类型: %s", task.task_type)
            return False
        params = task.params if isinstance(task.params, dict) else {}
        success = False
        error: str | None = None
        try:
            success = handler(session, params)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            logger.exception("清理任务执行失败: %s", task_id)
        finally:
            task.last_status = "success" if success else "error"
            task.last_error = error
            task.last_run_at = task.last_run_at  # set at claim time
            session.add(task)
            session.commit()
            scheduler_module.release_run_lock(session, task_id, instance_id)
        return success


def main() -> int:
    parser = argparse.ArgumentParser(prog="app.worker")
    parser.add_argument(
        "--job", type=int, default=None, help="scheduled task id (job mode)"
    )
    parser.add_argument(
        "--instance", type=str, default=None, help="instance id (job mode)"
    )
    args = parser.parse_args()

    _configure_logging()

    if args.job is not None:
        return 0 if run_job(args.job, args.instance or "job") else 1

    manager = TaskManager(_session_factory)
    init_config_manager(_session_factory)
    manager.bind(init_config_manager(_session_factory))
    scheduler = scheduler_module.CronScheduler(_session_factory, manager.instance_id)

    logger.info("worker 启动: instance=%s", manager.instance_id)
    manager.recover_on_startup()
    with _session_factory() as session:
        scheduler_module.seed_default_tasks(session)

    stop = threading.Event()

    def _handle_signal(signum: int, _frame: Any) -> None:
        logger.info("收到信号 %s，优雅退出", signum)
        stop.set()
        manager.stop_event.set()
        scheduler.stop()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    def _loop(name: str, interval: float, fn: Any) -> None:
        while not stop.is_set():
            try:
                fn()
            except Exception:
                logger.exception("%s 循环异常", name)
            stop.wait(interval)

    loops = [
        threading.Thread(
            target=_loop, args=("poller", 5, manager.poller_tick), daemon=True
        ),
        threading.Thread(
            target=_loop, args=("heartbeat", 15, manager.heartbeat), daemon=True
        ),
        threading.Thread(
            target=_loop, args=("watchdog", 60, manager.watchdog_tick), daemon=True
        ),
        threading.Thread(
            target=_loop, args=("scheduler", 30, scheduler.tick), daemon=True
        ),
    ]
    for loop in loops:
        loop.start()

    while not stop.is_set():
        stop.wait(1.0)
    logger.info("worker 已退出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
