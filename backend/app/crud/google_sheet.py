from typing import Any

from sqlmodel import Session, col, func, select

from app.models import GoogleSheet, GoogleSheetCreate, GoogleSheetUpdate


def create_google_sheet(
    *, session: Session, sheet_in: GoogleSheetCreate
) -> GoogleSheet:
    db_obj = GoogleSheet.model_validate(sheet_in)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_google_sheet(*, session: Session, sheet_id: int) -> GoogleSheet | None:
    return session.get(GoogleSheet, sheet_id)


def get_google_sheet_by_spreadsheet_id(
    *, session: Session, spreadsheet_id: str, registry_scope: str = "default"
) -> GoogleSheet | None:
    statement = select(GoogleSheet).where(
        GoogleSheet.spreadsheet_id == spreadsheet_id,
        GoogleSheet.registry_scope == registry_scope,
    )
    return session.exec(statement).first()


def get_google_sheets(
    *, session: Session, skip: int = 0, limit: int = 100
) -> tuple[list[GoogleSheet], int]:
    count = session.exec(select(func.count()).select_from(GoogleSheet)).one()
    statement = (
        select(GoogleSheet)
        .order_by(col(GoogleSheet.created_at).desc(), col(GoogleSheet.id).desc())
        .offset(skip)
        .limit(limit)
    )
    sheets = list(session.exec(statement).all())
    return sheets, count


def update_google_sheet(
    *, session: Session, db_sheet: GoogleSheet, sheet_in: GoogleSheetUpdate
) -> Any:
    sheet_data = sheet_in.model_dump(exclude_unset=True)
    db_sheet.sqlmodel_update(sheet_data)
    session.add(db_sheet)
    session.commit()
    session.refresh(db_sheet)
    return db_sheet


def delete_google_sheet(*, session: Session, db_sheet: GoogleSheet) -> None:
    session.delete(db_sheet)
    session.commit()
