from sqlmodel import Session, col, func, select

from app.models import TaskLog, TaskLogCreate


def create_task_log(*, session: Session, log_in: TaskLogCreate) -> TaskLog:
    db_obj = TaskLog.model_validate(log_in)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def list_task_logs(
    *,
    session: Session,
    task_id: int,
    skip: int = 0,
    limit: int = 100,
    level: str | None = None,
) -> tuple[list[TaskLog], int]:
    statement = select(TaskLog).where(TaskLog.task_id == task_id)
    count_statement = (
        select(func.count()).select_from(TaskLog).where(TaskLog.task_id == task_id)
    )
    if level:
        statement = statement.where(TaskLog.level == level)
        count_statement = count_statement.where(TaskLog.level == level)
    count = session.exec(count_statement).one()
    statement = (
        statement.order_by(col(TaskLog.created_at).desc(), col(TaskLog.id).desc())
        .offset(skip)
        .limit(limit)
    )
    logs = list(session.exec(statement).all())
    return logs, count


def get_latest_task_log(*, session: Session, task_id: int) -> TaskLog | None:
    statement = (
        select(TaskLog)
        .where(TaskLog.task_id == task_id)
        .order_by(col(TaskLog.created_at).desc(), col(TaskLog.id).desc())
        .limit(1)
    )
    return session.exec(statement).first()
