from typing import Any

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import SessionDep
from app.models import (
    Message,
    TaskTemplateCreate,
    TaskTemplatePublic,
    TaskTemplatesPublic,
    TaskTemplateUpdate,
)

router = APIRouter(prefix="/task-templates", tags=["task-templates"])


@router.get("/", response_model=TaskTemplatesPublic)
def read_task_templates(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """List task templates."""
    templates, count = crud.get_task_templates(session=session, skip=skip, limit=limit)
    return TaskTemplatesPublic(
        data=[TaskTemplatePublic.model_validate(t) for t in templates], count=count
    )


@router.post("/", response_model=TaskTemplatePublic)
def create_task_template(session: SessionDep, template_in: TaskTemplateCreate) -> Any:
    """Create a task template."""
    return crud.create_task_template(session=session, template_in=template_in)


@router.get("/{id}", response_model=TaskTemplatePublic)
def read_task_template(session: SessionDep, id: int) -> Any:
    """Get a task template."""
    template = crud.get_task_template(session=session, template_id=id)
    if not template:
        raise HTTPException(status_code=404, detail="Task template not found")
    return template


@router.put("/{id}", response_model=TaskTemplatePublic)
def update_task_template(
    session: SessionDep, id: int, template_in: TaskTemplateUpdate
) -> Any:
    """Update a task template."""
    template = crud.get_task_template(session=session, template_id=id)
    if not template:
        raise HTTPException(status_code=404, detail="Task template not found")
    return crud.update_task_template(
        session=session, db_template=template, template_in=template_in
    )


@router.delete("/{id}")
def delete_task_template(session: SessionDep, id: int) -> Message:
    """Delete a task template."""
    template = crud.get_task_template(session=session, template_id=id)
    if not template:
        raise HTTPException(status_code=404, detail="Task template not found")
    crud.delete_task_template(session=session, db_template=template)
    return Message(message="Task template deleted successfully")
