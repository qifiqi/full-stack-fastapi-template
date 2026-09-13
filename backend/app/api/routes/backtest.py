from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app import crud
from app.api.deps import SessionDep
from app.crud import upsert_system_config
from app.models import TaskResult

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.get("/task-results/{id}")
def read_backtest_result(session: SessionDep, id: int) -> Any:
    """Backtest result detail (full params/result payloads)."""
    result = crud.get_task_result(session=session, result_id=id)
    if not result:
        raise HTTPException(status_code=404, detail="Task result not found")
    return result


@router.get("/task-summary/{task_id}")
def read_backtest_summary(session: SessionDep, task_id: int) -> Any:
    """Task-level summary from hot columns (no full-table scans)."""
    task = crud.get_task(session=session, task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    total = session.exec(
        select(func.count())
        .select_from(TaskResult)
        .where(col(TaskResult.task_id) == task_id)
    ).one()
    success_count = session.exec(
        select(func.count())
        .select_from(TaskResult)
        .where(col(TaskResult.task_id) == task_id, col(TaskResult.success) == True)  # noqa: E712
    ).one()
    best_rows = session.exec(
        select(TaskResult)
        .where(
            col(TaskResult.task_id) == task_id,
            col(TaskResult.is_best) == True,  # noqa: E712
        )
        .order_by(col(TaskResult.stock_code).asc())
    ).all()
    return {
        "task_id": task_id,
        "task_type": task.task_type,
        "total": total,
        "success_count": success_count,
        "failed_count": total - success_count,
        "best": [
            {
                "result_id": r.id,
                "stock_code": r.stock_code,
                "stock_name": r.stock_name,
                "model_key": r.model_key,
                "period_key": r.period_key,
                "best_metric_name": r.best_metric_name,
                "best_metric_value": r.best_metric_value,
            }
            for r in best_rows
        ],
    }


@router.post("/calculate-ratios")
def calculate_ratios(_session: SessionDep, payload: dict[str, Any]) -> Any:
    """Ratio calculation over provided metric values (percent-safe)."""
    from app.services.google_sheet_tasks.result_payload import to_decimal_ratio

    values = payload.get("values")
    if not isinstance(values, dict):
        raise HTTPException(status_code=422, detail="values must be a dict")
    return {
        "ratios": {key: to_decimal_ratio(value) for key, value in values.items()},
    }


@router.put("/ratios")
def save_ratios(session: SessionDep, payload: dict[str, Any]) -> Any:
    """Persist per-task ratio edits (system_config keyed storage)."""
    task_id = payload.get("task_id")
    ratios = payload.get("ratios")
    if task_id is None or not isinstance(ratios, dict):
        raise HTTPException(status_code=422, detail="task_id and ratios are required")
    import json

    upsert_system_config(
        session=session,
        key=f"backtest_ratios_{task_id}",
        value=json.dumps(ratios, ensure_ascii=False),
    )
    return {"task_id": task_id, "saved": True}


@router.get("/task-results/{id}/export-preview")
def read_export_preview(session: SessionDep, id: int) -> Any:
    """Export preview payload (Excel workbook rendering lands in P6)."""
    result = crud.get_task_result(session=session, result_id=id)
    if not result:
        raise HTTPException(status_code=404, detail="Task result not found")
    return {
        "result_id": result.id,
        "task_id": result.task_id,
        "stock_code": result.stock_code,
        "model_key": result.model_key,
        "period_key": result.period_key,
        "preview_note": "Full workbook rendering lands in P6",
    }
