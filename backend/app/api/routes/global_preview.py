from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import col, select

from app.api.deps import SessionDep
from app.models import Task, TaskResult

router = APIRouter(prefix="/global-preview", tags=["global-preview"])


class PreviewGroupRequest(BaseModel):
    group_keys: list[str] | None = None
    best_only: bool = True


@router.get("/tasks/{task_id}")
def read_global_preview(
    session: SessionDep, task_id: int, best_only: bool = False
) -> Any:
    """Initial global-preview payload built from hot columns (no full scans)."""
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    statement = select(TaskResult).where(col(TaskResult.task_id) == task_id)
    if best_only:
        statement = statement.where(col(TaskResult.is_best) == True)  # noqa: E712
    statement = statement.order_by(
        col(TaskResult.stock_code).asc(), col(TaskResult.step_index).asc()
    )
    rows = session.exec(statement).all()
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        key = f"{r.stock_code or 'unknown'}|{r.model_key or 'default'}"
        groups.setdefault(key, []).append(
            {
                "result_id": r.id,
                "step_index": r.step_index,
                "stock_name": r.stock_name,
                "period_key": r.period_key,
                "year_label": r.year_label,
                "kline_range": r.kline_range,
                "best_metric_name": r.best_metric_name,
                "best_metric_value": r.best_metric_value,
                "result_timestamp": r.result_timestamp,
            }
        )
    return {
        "task_id": task_id,
        "task_type": task.task_type,
        "groups": groups,
        "count": len(rows),
    }


@router.post("/tasks/{task_id}/preview-group")
def read_preview_group(
    session: SessionDep, task_id: int, request: PreviewGroupRequest
) -> Any:
    """Filtered/grouped preview payload."""
    preview = read_global_preview(session, task_id, best_only=request.best_only)
    if request.group_keys is not None:
        preview["groups"] = {
            key: value
            for key, value in preview["groups"].items()
            if key in request.group_keys
        }
    return preview
