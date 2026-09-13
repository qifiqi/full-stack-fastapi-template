from datetime import date

from sqlmodel import Session, col, func, select

from app.models import (
    ReturnSeriesPoint,
    ReturnSeriesPointCreate,
    TaskResult,
    TaskResultCreate,
)


def create_task_result(*, session: Session, result_in: TaskResultCreate) -> TaskResult:
    db_obj = TaskResult.model_validate(result_in)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_task_result(*, session: Session, result_id: int) -> TaskResult | None:
    return session.get(TaskResult, result_id)


def list_task_results(
    *,
    session: Session,
    task_id: int,
    skip: int = 0,
    limit: int = 100,
    success: bool | None = None,
) -> tuple[list[TaskResult], int]:
    statement = select(TaskResult).where(TaskResult.task_id == task_id)
    count_statement = (
        select(func.count())
        .select_from(TaskResult)
        .where(TaskResult.task_id == task_id)
    )
    if success is not None:
        statement = statement.where(TaskResult.success == success)
        count_statement = count_statement.where(TaskResult.success == success)
    count = session.exec(count_statement).one()
    statement = (
        statement.order_by(col(TaskResult.step_index).asc(), col(TaskResult.id).asc())
        .offset(skip)
        .limit(limit)
    )
    results = list(session.exec(statement).all())
    return results, count


def delete_task_result(*, session: Session, db_result: TaskResult) -> None:
    session.delete(db_result)
    session.commit()


def create_return_series_points(
    *, session: Session, points: list[ReturnSeriesPointCreate]
) -> None:
    for point in points:
        session.add(ReturnSeriesPoint.model_validate(point))
    session.commit()


def list_return_series_points(
    *,
    session: Session,
    task_result_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[ReturnSeriesPoint]:
    statement = select(ReturnSeriesPoint).where(
        ReturnSeriesPoint.task_result_id == task_result_id
    )
    if start_date is not None:
        statement = statement.where(col(ReturnSeriesPoint.date) >= start_date)
    if end_date is not None:
        statement = statement.where(col(ReturnSeriesPoint.date) <= end_date)
    statement = statement.order_by(col(ReturnSeriesPoint.date).asc())
    return list(session.exec(statement).all())
