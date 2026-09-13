"""Model-summary backfill tool (recomputes hot columns for finished tasks)."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, col, select

from app.crud import create_task_log
from app.models import Task, TaskLogCreate, TaskResult
from app.services.model_summary.extractor import extract_hot_columns_for_result

logger = logging.getLogger(__name__)


def backfill_task(session: Session, task: Task) -> int:
    """Recompute hot columns + is_best for all results of one task."""
    statement = (
        select(TaskResult)
        .where(TaskResult.task_id == task.id)
        .order_by(col(TaskResult.step_index).asc(), col(TaskResult.id).asc())
    )
    task_config = task.config if isinstance(task.config, dict) else {}
    best_by_group: dict[str, tuple[float | None, int]] = {}
    updated = 0

    for result in session.exec(statement).all():
        hot = extract_hot_columns_for_result(
            task_type=task.task_type,
            task_name=task.name,
            task_config=task_config,
            parameters=result.params,
            result=result.result,
        )
        result.stock_code = hot.get("stock_code")
        result.stock_name = hot.get("stock_name")
        result.model_key = hot.get("model_key") or "default"
        result.model_name = hot.get("model_name")
        result.period_key = hot.get("period_key")
        result.year_label = hot.get("year_label")
        result.kline_range = hot.get("kline_range")
        result.best_metric_name = hot.get("best_metric_name")
        result.best_metric_value = hot.get("best_metric_value")

        group = f"{result.stock_code}|{result.model_key}"
        value = result.best_metric_value
        current = best_by_group.get(group)
        if current is None or (
            value is not None and (current[0] is None or value > current[0])
        ):
            best_by_group[group] = (value, int(result.id or 0))
        session.add(result)
        updated += 1

    session.flush()
    # second pass: flip is_best per group
    statement = select(TaskResult).where(TaskResult.task_id == task.id)
    for result in session.exec(statement).all():
        group = f"{result.stock_code}|{result.model_key}"
        best = best_by_group.get(group)
        result.is_best = best is not None and best[1] == int(result.id or 0)
        session.add(result)

    session.commit()
    return updated


def run_backfill(
    session: Session,
    *,
    task_ids: Iterable[int] | None = None,
    progress_task_id: int | None = None,
) -> dict[str, Any]:
    """Backfill hot columns for given (or all supported) finished tasks."""
    from app.services.model_summary.extractor import SUPPORTED_TASK_TYPES

    if task_ids:
        statement = select(Task).where(col(Task.id).in_(list(task_ids)))
    else:
        statement = select(Task).where(
            col(Task.status).in_(["success", "error", "cancelled"]),
            col(Task.task_type).in_(list(SUPPORTED_TASK_TYPES)),
        )
    tasks = list(session.exec(statement).all())

    total_updated = 0
    for index, task in enumerate(tasks, start=1):
        total_updated += backfill_task(session, task)
        if progress_task_id:
            create_task_log(
                session=session,
                log_in=TaskLogCreate(
                    task_id=progress_task_id,
                    level="INFO",
                    message=f"回填进度: {index}/{len(tasks)} 任务, 累计更新 {total_updated} 行",
                ),
            )
    return {
        "tasks": len(tasks),
        "results_updated": total_updated,
        "finished_at": datetime.now(UTC).isoformat(),
    }
