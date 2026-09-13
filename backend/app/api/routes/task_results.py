from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import SessionDep
from app.models import (
    Message,
    ReturnSeriesPointPublic,
    TaskResultListItem,
    TaskResultListPublic,
    TaskResultPublic,
)

router = APIRouter(prefix="/task-results", tags=["task-results"])


@router.get("/tasks/{task_id}/results", response_model=TaskResultListPublic)
def read_task_results(
    session: SessionDep,
    task_id: int,
    skip: int = 0,
    limit: int = 100,
    success: bool | None = None,
) -> Any:
    """List a task's results (lightweight projection, no heavy params/result JSON)."""
    results, count = crud.list_task_results(
        session=session, task_id=task_id, skip=skip, limit=limit, success=success
    )
    items = [TaskResultListItem.model_validate(r) for r in results]
    return TaskResultListPublic(data=items, count=count)


@router.get("/{id}", response_model=TaskResultPublic)
def read_task_result(session: SessionDep, id: int) -> Any:
    """Get one result including the full params/result JSON payloads."""
    result = crud.get_task_result(session=session, result_id=id)
    if not result:
        raise HTTPException(status_code=404, detail="Task result not found")
    return result


@router.delete("/{id}")
def delete_task_result(session: SessionDep, id: int) -> Message:
    """Delete a result; its return-series rows cascade."""
    result = crud.get_task_result(session=session, result_id=id)
    if not result:
        raise HTTPException(status_code=404, detail="Task result not found")
    crud.delete_task_result(session=session, db_result=result)
    return Message(message="Task result deleted successfully")


@router.get("/{id}/return-series", response_model=list[ReturnSeriesPointPublic])
def read_return_series(
    session: SessionDep,
    id: int,
    start: date | None = None,
    end: date | None = None,
) -> Any:
    """Return-series rows for a result, ordered by date (PK prefix range scan)."""
    if crud.get_task_result(session=session, result_id=id) is None:
        raise HTTPException(status_code=404, detail="Task result not found")
    points = crud.list_return_series_points(
        session=session, task_result_id=id, start_date=start, end_date=end
    )
    return [ReturnSeriesPointPublic.model_validate(p) for p in points]
