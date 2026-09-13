from datetime import datetime
from typing import Any

from fastapi import APIRouter
from sqlmodel import col, func, select

from app.api.deps import SessionDep
from app.models import TaskLog, TaskLogsPublic

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/", response_model=TaskLogsPublic)
def read_logs(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    level: str | None = None,
    task_id: int | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> Any:
    """Query task logs with level/task/time filters."""
    statement = select(TaskLog)
    count_statement = select(func.count()).select_from(TaskLog)
    if level:
        statement = statement.where(col(TaskLog.level) == level.upper())
        count_statement = count_statement.where(col(TaskLog.level) == level.upper())
    if task_id is not None:
        statement = statement.where(col(TaskLog.task_id) == task_id)
        count_statement = count_statement.where(col(TaskLog.task_id) == task_id)
    if start is not None:
        statement = statement.where(col(TaskLog.created_at) >= start)
        count_statement = count_statement.where(col(TaskLog.created_at) >= start)
    if end is not None:
        statement = statement.where(col(TaskLog.created_at) <= end)
        count_statement = count_statement.where(col(TaskLog.created_at) <= end)
    count = session.exec(count_statement).one()
    statement = (
        statement.order_by(col(TaskLog.created_at).desc(), col(TaskLog.id).desc())
        .offset(skip)
        .limit(limit)
    )
    logs = list(session.exec(statement).all())
    return TaskLogsPublic(
        data=[TaskLog.model_validate(log) for log in logs], count=count
    )


@router.get("/latest")
def read_latest_logs(session: SessionDep, limit: int = 20) -> Any:
    """Most recent log rows across all tasks."""
    statement = (
        select(TaskLog)
        .order_by(col(TaskLog.created_at).desc(), col(TaskLog.id).desc())
        .limit(limit)
    )
    logs = list(session.exec(statement).all())
    return TaskLogsPublic(
        data=[TaskLog.model_validate(log) for log in logs], count=len(logs)
    )
