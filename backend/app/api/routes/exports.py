import csv
import io
import json
import zipfile
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import col, func, select

from app import crud
from app.api.deps import SessionDep
from app.models import TaskResult

router = APIRouter(prefix="/exports", tags=["exports"])

MAX_BATCH_TASKS = 10
CSV_FILENAME_SUFFIX = ".csv"


def _result_rows(session: Any, task_id: int) -> list[dict[str, Any]]:
    results, _count = crud.list_task_results(
        session=session, task_id=task_id, skip=0, limit=100000
    )
    rows = []
    for r in results:
        rows.append(
            {
                "result_id": r.id,
                "task_id": r.task_id,
                "step_index": r.step_index,
                "success": r.success,
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
                "params_json": json.dumps(
                    r.params or {}, ensure_ascii=False, default=str
                ),
                "result_json": json.dumps(
                    r.result or {}, ensure_ascii=False, default=str
                ),
            }
        )
    return rows


def _csv_response(rows: list[dict[str, Any]], filename: str) -> StreamingResponse:
    if not rows:
        raise HTTPException(status_code=404, detail="No results to export")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.get("/tasks/{task_id}")
def export_task(session: SessionDep, task_id: int, format: str = "csv") -> Any:
    """Stream one task's results as CSV."""
    if format != "csv":
        raise HTTPException(
            status_code=422, detail="Only csv format is supported for single tasks"
        )
    rows = _result_rows(session, task_id)
    return _csv_response(rows, f"task_{task_id}_results.csv")


@router.post("/tasks/batch")
def export_tasks_batch(session: SessionDep, task_ids: list[int]) -> Any:
    """Pack up to 10 tasks' result CSVs into one ZIP download."""
    if not task_ids or len(task_ids) > MAX_BATCH_TASKS:
        raise HTTPException(
            status_code=422, detail=f"task_ids must contain 1..{MAX_BATCH_TASKS} items"
        )
    zip_buffer = io.BytesIO()
    included = 0
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for task_id in task_ids:
            rows = _result_rows(session, task_id)
            if not rows:
                continue
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
            zf.writestr(f"task_{task_id}_results.csv", buffer.getvalue())
            included += 1
    if not included:
        raise HTTPException(status_code=404, detail="No results to export")
    zip_buffer.seek(0)
    return StreamingResponse(
        iter([zip_buffer.getvalue()]),
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''tasks_export.zip"
        },
    )


@router.get("/model-summary")
def export_model_summary(
    session: SessionDep, best_only: bool = True, task_id: int | None = None
) -> Any:
    """Export the summary grid (hot columns) as CSV."""
    statement = select(TaskResult)
    if best_only:
        from sqlmodel import col

        statement = statement.where(col(TaskResult.is_best) == True)  # noqa: E712
    if task_id is not None:
        statement = statement.where(col(TaskResult.task_id) == task_id)
    rows_raw = session.exec(statement).all()
    rows = [
        {
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
            "result_timestamp": r.result_timestamp,
        }
        for r in rows_raw
    ]
    if not rows:
        raise HTTPException(status_code=404, detail="No summary rows to export")
    return _csv_response(rows, "model_summary.csv")


@router.get("/model-summary.xlsx")
def export_model_summary_xlsx(
    session: SessionDep, best_only: bool = True, task_id: int | None = None
) -> Any:
    """Export the summary grid as an Excel workbook."""
    from sqlmodel import col

    from app.services.export.report_builders import build_excel_summary

    statement = select(TaskResult)
    if best_only:
        statement = statement.where(col(TaskResult.is_best) == True)  # noqa: E712
    if task_id is not None:
        statement = statement.where(col(TaskResult.task_id) == task_id)
    rows_raw = session.exec(statement).all()
    rows = [
        {
            "task_id": r.task_id,
            "stock_code": r.stock_code,
            "stock_name": r.stock_name,
            "model_key": r.model_key,
            "model_name": r.model_name,
            "period_key": r.period_key,
            "best_metric_name": r.best_metric_name,
            "best_metric_value": r.best_metric_value,
        }
        for r in rows_raw
    ]
    if not rows:
        raise HTTPException(status_code=404, detail="No summary rows to export")
    content = build_excel_summary(rows)
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''model_summary.xlsx"
        },
    )


@router.get("/global-previews/{task_id}")
def export_global_preview(session: SessionDep, task_id: int) -> Any:
    """Global preview workbook: best rows of a task as xlsx."""
    from app.crud import get_task
    from app.services.export.report_builders import build_excel_summary

    if get_task(session=session, task_id=task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    statement = select(TaskResult).where(col(TaskResult.task_id) == task_id)
    rows = [
        {
            "step_index": r.step_index,
            "stock_code": r.stock_code,
            "model_key": r.model_key,
            "period_key": r.period_key,
            "best_metric_name": r.best_metric_name,
            "best_metric_value": r.best_metric_value,
        }
        for r in session.exec(statement).all()
    ]
    if not rows:
        raise HTTPException(status_code=404, detail="No results to export")
    content = build_excel_summary(rows)
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''preview_task_{task_id}.xlsx"
        },
    )


@router.post("/backtest-reports/word")
def export_word_report(session: SessionDep, payload: dict[str, Any]) -> Any:
    """Word backtest report for a task (python-docx)."""
    from app.crud import get_task
    from app.services.export.report_builders import build_word_report

    task_id = payload.get("task_id")
    if task_id is None:
        raise HTTPException(status_code=422, detail="task_id is required")
    task = get_task(session=session, task_id=int(task_id))
    if task is None:
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
    best_rows = [
        {
            "stock_code": r.stock_code,
            "model_key": r.model_key,
            "period_key": r.period_key,
            "best_metric_name": r.best_metric_name,
            "best_metric_value": r.best_metric_value,
        }
        for r in session.exec(
            select(TaskResult).where(
                col(TaskResult.task_id) == task_id,
                col(TaskResult.is_best) == True,  # noqa: E712
            )
        ).all()
    ]
    content = build_word_report(
        task=task,
        summary={
            "total": total,
            "success_count": success_count,
            "failed_count": total - success_count,
        },
        best_rows=best_rows,
    )
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''report_task_{task_id}.docx"
        },
    )
