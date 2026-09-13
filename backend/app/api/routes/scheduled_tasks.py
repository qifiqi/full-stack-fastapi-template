from typing import Any

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import SessionDep
from app.core import scheduler as scheduler_module
from app.core.config import settings
from app.models import (
    Message,
    ScheduledTaskCreate,
    ScheduledTaskPublic,
    ScheduledTasksPublic,
    ScheduledTaskUpdate,
)

router = APIRouter(prefix="/scheduled-tasks", tags=["scheduled-tasks"])


@router.get("/", response_model=ScheduledTasksPublic)
def read_scheduled_tasks(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """List scheduled tasks with lock state and next fire time."""
    tasks, count = crud.get_scheduled_tasks(session=session, skip=skip, limit=limit)
    data = []
    for task in tasks:
        item = ScheduledTaskPublic.model_validate(task).model_copy(
            update={"id": int(task.id or 0)}
        )
        data.append(item)
    return ScheduledTasksPublic(data=data, count=count)


@router.post("/", response_model=ScheduledTaskPublic)
def create_scheduled_task(session: SessionDep, task_in: ScheduledTaskCreate) -> Any:
    """Create a scheduled task; the cron expression is validated with croniter."""
    if not scheduler_module.validate_cron_expression(task_in.cron_expression):
        raise HTTPException(status_code=422, detail="Invalid cron expression")
    if task_in.task_type not in scheduler_module.CLEANUP_JOB_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported scheduled task type")
    return crud.create_scheduled_task(session=session, task_in=task_in)


@router.get("/scheduler/stats")
def read_scheduler_stats(session: SessionDep) -> Any:
    """Worker instance, running lock count and next fire times."""
    tasks, _count = crud.get_scheduled_tasks(session=session, skip=0, limit=200)
    running = [t for t in tasks if t.is_running]
    next_fires = {}
    for t in tasks:
        if not t.enabled:
            continue
        fire = scheduler_module.next_fire_time(t.cron_expression)
        next_fires[str(t.id)] = fire.isoformat() if fire is not None else None
    return {
        "worker_instance_id": settings.worker_instance_id,
        "running_count": len(running),
        "running": [
            {
                "id": int(t.id or 0),
                "name": t.name,
                "running_instance_id": t.running_instance_id,
                "last_run_at": t.last_run_at.isoformat() if t.last_run_at else None,
            }
            for t in running
        ],
        "next_fire_times": next_fires,
    }


@router.get("/{id}", response_model=ScheduledTaskPublic)
def read_scheduled_task(session: SessionDep, id: int) -> Any:
    """Get one scheduled task."""
    task = crud.get_scheduled_task(session=session, task_id=id)
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    return task


@router.put("/{id}", response_model=ScheduledTaskPublic)
def update_scheduled_task(
    session: SessionDep, id: int, task_in: ScheduledTaskUpdate
) -> Any:
    """Update a scheduled task (name/cron/params/enabled)."""
    data = task_in.model_dump(exclude_unset=True)
    if "cron_expression" in data and not scheduler_module.validate_cron_expression(
        str(data["cron_expression"])
    ):
        raise HTTPException(status_code=422, detail="Invalid cron expression")
    if (
        "task_type" in data
        and data["task_type"] not in scheduler_module.CLEANUP_JOB_TYPES
    ):
        raise HTTPException(status_code=422, detail="Unsupported scheduled task type")
    task = crud.get_scheduled_task(session=session, task_id=id)
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    return crud.update_scheduled_task(session=session, db_task=task, task_in=task_in)


@router.delete("/{id}")
def delete_scheduled_task(session: SessionDep, id: int) -> Message:
    """Delete a scheduled task (blocked while its lock is held)."""
    task = crud.get_scheduled_task(session=session, task_id=id)
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    if task.is_running:
        raise HTTPException(status_code=409, detail="Scheduled task is running")
    crud.delete_scheduled_task(session=session, db_task=task)
    return Message(message="Scheduled task deleted successfully")


@router.post("/{id}/toggle", response_model=ScheduledTaskPublic)
def toggle_scheduled_task(session: SessionDep, id: int) -> Any:
    """Enable/disable a scheduled task."""
    task = crud.get_scheduled_task(session=session, task_id=id)
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    return crud.update_scheduled_task(
        session=session,
        db_task=task,
        task_in=ScheduledTaskUpdate(enabled=not task.enabled),
    )


@router.post("/{id}/run", response_model=Message)
def run_scheduled_task(session: SessionDep, id: int) -> Message:
    """Run now: clear last_run_at so the next scheduler tick claims it."""
    task = crud.get_scheduled_task(session=session, task_id=id)
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    if not task.enabled:
        raise HTTPException(status_code=409, detail="Scheduled task is disabled")
    task.last_run_at = None
    session.add(task)
    session.commit()
    return Message(message="Scheduled task queued for the next scheduler tick")
