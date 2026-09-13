from typing import Any

from sqlmodel import Session, col, func, select

from app.models import (
    ScheduledTask,
    ScheduledTaskCreate,
    ScheduledTaskUpdate,
)


def create_scheduled_task(
    *, session: Session, task_in: ScheduledTaskCreate
) -> ScheduledTask:
    db_obj = ScheduledTask.model_validate(task_in)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_scheduled_task(*, session: Session, task_id: int) -> ScheduledTask | None:
    return session.get(ScheduledTask, task_id)


def get_scheduled_tasks(
    *, session: Session, skip: int = 0, limit: int = 100
) -> tuple[list[ScheduledTask], int]:
    count = session.exec(select(func.count()).select_from(ScheduledTask)).one()
    statement = (
        select(ScheduledTask)
        .order_by(col(ScheduledTask.created_at).desc(), col(ScheduledTask.id).desc())
        .offset(skip)
        .limit(limit)
    )
    tasks = list(session.exec(statement).all())
    return tasks, count


def list_enabled_scheduled_tasks(*, session: Session) -> list[ScheduledTask]:
    statement = select(ScheduledTask).where(col(ScheduledTask.enabled))
    return list(session.exec(statement).all())


def update_scheduled_task(
    *, session: Session, db_task: ScheduledTask, task_in: ScheduledTaskUpdate
) -> Any:
    task_data = task_in.model_dump(exclude_unset=True)
    db_task.sqlmodel_update(task_data)
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    return db_task


def delete_scheduled_task(*, session: Session, db_task: ScheduledTask) -> None:
    session.delete(db_task)
    session.commit()
