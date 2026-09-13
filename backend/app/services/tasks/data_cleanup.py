"""Task execution-data cleanup (FK CASCADE now handles row graphs)."""

from typing import Any

from sqlmodel import Session, col, delete, select

from app.models import BacktestSheetRunLock, ReturnSeriesPoint, TaskLog, TaskResult


def clear_task_execution_data(
    session: Session, task_id: int, *, include_logs: bool = False
) -> None:
    """Delete a task's execution artifacts (results cascade to return series)."""
    session.exec(delete(TaskResult).where(col(TaskResult.task_id) == task_id))
    session.exec(
        delete(BacktestSheetRunLock).where(col(BacktestSheetRunLock.task_id) == task_id)
    )
    if include_logs:
        session.exec(delete(TaskLog).where(col(TaskLog.task_id) == task_id))
    session.commit()


def list_result_ids(session: Session, task_id: int) -> list[int]:
    statement = select(TaskResult.id).where(col(TaskResult.task_id) == task_id)
    return [int(row) for row in session.exec(statement).all() if row is not None]


def cleanup_old_logs(session: Session, params: dict[str, Any] | None) -> bool:
    """Batch-delete task logs older than ``days`` (scheduled job whitelist)."""
    import time as _time
    from datetime import UTC, datetime, timedelta

    params = params or {}
    days = int(params.get("days") or 10)
    batch_size = int(params.get("batch_size") or 200)
    delay = int(params.get("delay") or 2)
    cutoff = datetime.now(UTC) - timedelta(days=days)

    total_deleted = 0
    while True:
        ids = session.exec(
            select(TaskLog.id).where(col(TaskLog.created_at) < cutoff).limit(batch_size)
        ).all()
        if not ids:
            break
        session.exec(delete(TaskLog).where(col(TaskLog.id).in_(ids)))
        session.commit()
        total_deleted += len(ids)
        if len(ids) < batch_size:
            break
        _time.sleep(delay)
    return True


def cleanup_old_results(session: Session, params: dict[str, Any] | None) -> bool:
    """Batch-delete task results older than ``days`` (return series cascade)."""
    import time as _time
    from datetime import UTC, datetime, timedelta

    params = params or {}
    days = int(params.get("days") or 10)
    batch_size = int(params.get("batch_size") or 200)
    delay = int(params.get("delay") or 2)
    cutoff = datetime.now(UTC) - timedelta(days=days)

    total_deleted = 0
    while True:
        ids = session.exec(
            select(TaskResult.id)
            .where(col(TaskResult.created_at) < cutoff)
            .limit(batch_size)
        ).all()
        if not ids:
            break
        session.exec(
            delete(ReturnSeriesPoint).where(
                col(ReturnSeriesPoint.task_result_id).in_(ids)
            )
        )
        session.exec(delete(TaskResult).where(col(TaskResult.id).in_(ids)))
        session.commit()
        total_deleted += len(ids)
        if len(ids) < batch_size:
            break
        _time.sleep(delay)
    return True


def cleanup_old_data(session: Session, params: dict[str, Any] | None) -> bool:
    """Default daily cleanup: logs then results."""
    cleanup_old_logs(session, params)
    cleanup_old_results(session, params)
    return True
