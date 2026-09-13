from typing import Any

from sqlmodel import Session, col, func, select

from app.models import (
    TaskTemplate,
    TaskTemplateCreate,
    TaskTemplateUpdate,
)


def create_task_template(
    *, session: Session, template_in: TaskTemplateCreate
) -> TaskTemplate:
    db_obj = TaskTemplate.model_validate(template_in)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_task_template(*, session: Session, template_id: int) -> TaskTemplate | None:
    return session.get(TaskTemplate, template_id)


def get_task_templates(
    *, session: Session, skip: int = 0, limit: int = 100
) -> tuple[list[TaskTemplate], int]:
    count = session.exec(select(func.count()).select_from(TaskTemplate)).one()
    statement = (
        select(TaskTemplate)
        .order_by(col(TaskTemplate.updated_at).desc(), col(TaskTemplate.id).desc())
        .offset(skip)
        .limit(limit)
    )
    templates = list(session.exec(statement).all())
    return templates, count


def update_task_template(
    *, session: Session, db_template: TaskTemplate, template_in: TaskTemplateUpdate
) -> Any:
    template_data = template_in.model_dump(exclude_unset=True)
    db_template.sqlmodel_update(template_data)
    session.add(db_template)
    session.commit()
    session.refresh(db_template)
    return db_template


def delete_task_template(*, session: Session, db_template: TaskTemplate) -> None:
    session.delete(db_template)
    session.commit()
