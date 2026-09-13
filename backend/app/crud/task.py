from typing import Any, cast

from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, literal_column, select

from app.models import Task, TaskCreate, TaskStatistics, TaskUpdate


def create_task(*, session: Session, task_in: TaskCreate) -> Task:
    db_obj = Task.model_validate(task_in)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_task(*, session: Session, task_id: int) -> Task | None:
    return session.get(Task, task_id)


def get_tasks(
    *,
    session: Session,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    task_type: str | None = None,
    spreadsheet_id: str | None = None,
    stock_code: str | None = None,
    keyword: str | None = None,
) -> tuple[list[Task], int]:
    statement = select(Task)
    count_statement = select(func.count()).select_from(Task)
    if status:
        statement = statement.where(Task.status == status)
        count_statement = count_statement.where(Task.status == status)
    if task_type:
        statement = statement.where(Task.task_type == task_type)
        count_statement = count_statement.where(Task.task_type == task_type)
    if spreadsheet_id:
        statement = statement.where(Task.spreadsheet_id == spreadsheet_id)
        count_statement = count_statement.where(Task.spreadsheet_id == spreadsheet_id)
    if stock_code:
        statement = statement.where(Task.stock_code == stock_code)
        count_statement = count_statement.where(Task.stock_code == stock_code)
    if keyword:
        pattern = f"{keyword}%"
        condition = col(Task.name).like(pattern) | col(Task.description).like(pattern)
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    count = session.exec(count_statement).one()
    statement = (
        statement.order_by(col(Task.created_at).desc(), col(Task.id).desc())
        .offset(skip)
        .limit(limit)
    )
    tasks = list(session.exec(statement).all())
    return tasks, count


def get_task_statistics(*, session: Session) -> TaskStatistics:
    total = session.exec(select(func.count()).select_from(Task)).one()
    status_rows = session.exec(
        select(Task.status, func.count()).group_by(Task.status)
    ).all()
    by_status = dict(status_rows)
    avg_seconds = session.exec(
        select(func.avg(_avg_running_seconds_expr(session))).where(
            col(Task.started_at).is_not(None) & col(Task.finished_at).is_not(None)
        )
    ).one()
    return TaskStatistics(
        total=total,
        by_status=by_status,
        avg_running_seconds=float(avg_seconds) if avg_seconds is not None else None,
    )


def _avg_running_seconds_expr(session: Session) -> ColumnElement[float]:
    # AVG is linear, so averaging a per-row duration expression is exact.
    # Dialect selection only; all fragments are constant SQL (no user input).
    bind = session.get_bind()
    dialect = bind.dialect.name if bind is not None else "postgresql"
    duration = col(Task.finished_at) - col(Task.started_at)
    if dialect == "mysql":
        return cast(
            "ColumnElement[float]",
            func.timestampdiff(
                literal_column("SECOND"), col(Task.started_at), col(Task.finished_at)
            ),
        )
    if dialect == "sqlite":
        return cast(
            "ColumnElement[float]",
            (
                func.julianday(col(Task.finished_at))
                - func.julianday(col(Task.started_at))
            )
            * 86400.0,
        )
    return cast("ColumnElement[float]", func.extract("epoch", duration))


def update_task(*, session: Session, db_task: Task, task_in: TaskUpdate) -> Any:
    task_data = task_in.model_dump(exclude_unset=True)
    db_task.sqlmodel_update(task_data)
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    return db_task


def delete_task(*, session: Session, db_task: Task) -> None:
    session.delete(db_task)
    session.commit()
