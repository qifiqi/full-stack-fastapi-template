from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app import crud
from app.api.deps import SessionDep
from app.models import (
    Message,
    TaskCreate,
    TaskLog,
    TaskLogsPublic,
    TaskPublic,
    TasksPublic,
    TaskStatusCheck,
    TaskUpdate,
)
from app.services.tasks.creation import (
    create_batch_tasks,
    create_restart_task,
    create_task_with_config,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/", response_model=TasksPublic)
def read_tasks(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    task_type: str | None = None,
    spreadsheet_id: str | None = None,
    stock_code: str | None = None,
    keyword: str | None = Query(default=None, max_length=64),
    include_statistics: bool = True,
) -> Any:
    """Retrieve tasks with optional filters and statistics."""
    tasks, count = crud.get_tasks(
        session=session,
        skip=skip,
        limit=limit,
        status=status,
        task_type=task_type,
        spreadsheet_id=spreadsheet_id,
        stock_code=stock_code,
        keyword=keyword,
    )
    statistics = (
        crud.get_task_statistics(session=session) if include_statistics else None
    )
    return TasksPublic(
        data=[TaskPublic.model_validate(t) for t in tasks],
        count=count,
        statistics=statistics,
    )


@router.post("/", response_model=TaskPublic)
def create_task(session: SessionDep, task_in: TaskCreate) -> Any:
    """Create a new pending task; the worker claims it when slots free up."""
    try:
        task = create_task_with_config(
            session,
            name=task_in.name,
            description=task_in.description,
            task_type=task_in.task_type,
            config=task_in.config or {},
        )
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return task


@router.post("/batch-create", response_model=list[TaskPublic])
def batch_create_tasks(session: SessionDep, data: dict[str, Any]) -> Any:
    """Expand a C31 batch request into pending C3 tasks."""
    try:
        created = create_batch_tasks(session, data)
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    tasks = [
        crud.get_task(session=session, task_id=item["task_id"]) for item in created
    ]
    return [TaskPublic.model_validate(t) for t in tasks if t is not None]


@router.get("/{id}", response_model=TaskPublic)
def read_task(session: SessionDep, id: int) -> Any:
    """Get task by ID (includes full config)."""
    task = crud.get_task(session=session, task_id=id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/{id}")
def delete_task(session: SessionDep, id: int) -> Message:
    """Delete a task; results/series/logs cascade."""
    task = crud.get_task(session=session, task_id=id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status == "running":
        raise HTTPException(status_code=409, detail="Task is running; cancel it first")
    crud.delete_task(session=session, db_task=task)
    return Message(message="Task deleted successfully")


@router.put("/{id}/config", response_model=TaskPublic)
def update_task_config(session: SessionDep, id: int, task_in: TaskUpdate) -> Any:
    """Update a pending task's name/description/config."""
    task = crud.get_task(session=session, task_id=id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in ("pending", "queued", "error", "cancelled", "success"):
        raise HTTPException(
            status_code=409, detail="Only non-running tasks can be updated"
        )
    if task_in.config is not None and isinstance(task_in.config, dict):
        from app.services.tasks.creation import (
            extract_hot_columns,
            normalize_task_config,
        )

        normalized = normalize_task_config(task.task_type, task_in.config)
        updated = dict(task_in.model_dump(exclude_unset=True))
        updated["config"] = normalized
        updated.update(extract_hot_columns(task.task_type, normalized))
        task_in = TaskUpdate.model_validate(updated)
    task = crud.update_task(session=session, db_task=task, task_in=task_in)
    return task


@router.post("/{id}/cancel", response_model=TaskPublic)
def cancel_task(session: SessionDep, id: int) -> Any:
    """Request cancellation: sets stop_requested; the worker bridges it."""
    task = crud.get_task(session=session, task_id=id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "running":
        raise HTTPException(status_code=409, detail="Task is not running")
    task.stop_requested = True
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.post("/{id}/create-restart", response_model=TaskPublic)
def create_restart(session: SessionDep, id: int) -> Any:
    """Copy a task into a fresh pending row (config reused, old row untouched)."""
    try:
        return create_restart_task(session, id)
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=404, detail="Task not found") from exc


@router.get("/{id}/logs", response_model=TaskLogsPublic)
def read_task_logs(
    session: SessionDep,
    id: int,
    skip: int = 0,
    limit: int = 100,
    level: str | None = None,
) -> Any:
    """Retrieve task logs (newest first)."""
    if crud.get_task(session=session, task_id=id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    logs, count = crud.list_task_logs(
        session=session, task_id=id, skip=skip, limit=limit, level=level
    )
    return TaskLogsPublic(
        data=[TaskLog.model_validate(log) for log in logs], count=count
    )


@router.get("/{id}/status-check", response_model=TaskStatusCheck)
def read_task_status_check(session: SessionDep, id: int) -> Any:
    """Lightweight polling payload: status, progress, heartbeat, latest log."""
    task = crud.get_task(session=session, task_id=id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    latest = crud.get_latest_task_log(session=session, task_id=id)
    return TaskStatusCheck(
        id=int(task.id or 0),
        status=task.status,
        current_step=task.current_step,
        total_steps=task.total_steps,
        heartbeat_at=task.heartbeat_at,
        running_instance=task.running_instance,
        latest_log=latest.message if latest else None,
    )
