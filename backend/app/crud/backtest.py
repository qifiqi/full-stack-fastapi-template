from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, delete, select

from app.models import BacktestSheetRunLock, BacktestSheetRunLockCreate


def acquire_sheet_lock(
    *, session: Session, lock_in: BacktestSheetRunLockCreate
) -> bool:
    """Insert a Sheet run lock; returns False when the sheet is already locked."""
    db_obj = BacktestSheetRunLock.model_validate(lock_in)
    session.add(db_obj)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return False
    session.refresh(db_obj)
    return True


def release_sheet_lock(*, session: Session, spreadsheet_id: str) -> None:
    session.exec(
        delete(BacktestSheetRunLock).where(
            col(BacktestSheetRunLock.spreadsheet_id) == spreadsheet_id
        )
    )
    session.commit()


def get_sheet_lock(
    *, session: Session, spreadsheet_id: str
) -> BacktestSheetRunLock | None:
    statement = select(BacktestSheetRunLock).where(
        col(BacktestSheetRunLock.spreadsheet_id) == spreadsheet_id
    )
    return session.exec(statement).first()


def clear_sheet_locks(*, session: Session) -> None:
    """Drop all runtime locks; worker startup recovery only (in-process state)."""
    session.exec(delete(BacktestSheetRunLock))
    session.commit()
