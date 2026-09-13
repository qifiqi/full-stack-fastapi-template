from datetime import UTC, datetime
from threading import RLock
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import col, func, select

from app.api.deps import SessionDep
from app.models import (
    Task,
    TaskResult,
)

router = APIRouter(prefix="/model-summary", tags=["model-summary"])

# RLock: the request path acquires non-blocking, then re-enters for the run.
_rebuild_lock = RLock()
_rebuild_status: dict[str, Any] = {"state": "idle", "finished_at": None, "result": None}


@router.get("/")
def read_model_summary(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    best_only: bool = True,
    stock_code: str | None = None,
    market_type: str | None = None,
    period_key: str | None = None,
    task_type: str | None = None,
    task_id: int | None = None,
) -> Any:
    """Query best results through the task_result hot columns (is_best)."""
    join_on = col(Task.id) == col(TaskResult.task_id)
    statement = select(TaskResult).join(Task, join_on, isouter=True)
    count_statement = (
        select(func.count()).select_from(TaskResult).join(Task, join_on, isouter=True)
    )
    conditions = []
    if best_only:
        conditions.append(col(TaskResult.is_best) == True)  # noqa: E712
    if stock_code:
        conditions.append(col(TaskResult.stock_code) == stock_code)
    if period_key:
        conditions.append(col(TaskResult.period_key) == period_key)
    if task_type:
        conditions.append(col(Task.task_type) == task_type)
    if task_id is not None:
        conditions.append(col(TaskResult.task_id) == task_id)
    if market_type:
        conditions.append(col(Task.market_type) == market_type)
    # market filter by stock_code shape (cn = pure digits), mirrors source rule
    for condition in conditions:
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    count = session.exec(count_statement).one()
    statement = (
        statement.order_by(
            col(TaskResult.result_timestamp).desc(), col(TaskResult.id).desc()
        )
        .offset(skip)
        .limit(limit)
    )
    rows = session.exec(statement).all()
    return {
        "data": [
            {
                "id": r.id,
                "task_id": r.task_id,
                "stock_code": r.stock_code,
                "stock_name": r.stock_name,
                "model_key": r.model_key,
                "model_name": r.model_name,
                "period_key": r.period_key,
                "year_label": r.year_label,
                "kline_range": r.kline_range,
                "best_metric_name": r.best_metric_name,
                "best_metric_value": r.best_metric_value,
                "is_best": r.is_best,
                "result_timestamp": r.result_timestamp,
                "success": r.success,
            }
            for r in rows
        ],
        "count": count,
    }


class BackfillRequest(BaseModel):
    task_ids: list[int] | None = None
    all: bool = False


@router.post("/rebuild")
def rebuild_model_summary(session: SessionDep, request: BackfillRequest) -> Any:
    """Recompute hot columns for finished tasks (backfill repair tool)."""
    from app.services.model_summary.backfill import run_backfill

    if not request.all and not request.task_ids:
        raise HTTPException(status_code=422, detail="Provide task_ids or all=true")
    acquired = _rebuild_lock.acquire(blocking=False)
    if not acquired:
        raise HTTPException(status_code=409, detail="Rebuild already running")
    try:
        with _rebuild_lock:
            _rebuild_status.update(
                {
                    "state": "running",
                    "started_at": datetime.now(UTC).isoformat(),
                    "result": None,
                }
            )
            result = run_backfill(
                session,
                task_ids=request.task_ids if not request.all else None,
            )
            _rebuild_status.update(
                {
                    "state": "completed",
                    "finished_at": datetime.now(UTC).isoformat(),
                    "result": result,
                }
            )
            return result
    except Exception as exc:
        _rebuild_status.update({"state": "error", "error": str(exc)})
        session.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/rebuild/status")
def rebuild_status() -> Any:
    """Last rebuild job status."""
    return _rebuild_status


@router.get("/columns")
def summary_columns() -> Any:
    """Shared column vocabulary for summary tables (single source of truth)."""
    from app.services.model_summary.extractor import SUMMARY_COLUMNS, TASK_TYPE_LABELS

    return {"columns": SUMMARY_COLUMNS, "task_type_labels": TASK_TYPE_LABELS}
