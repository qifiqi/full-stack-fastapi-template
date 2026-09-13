from typing import Any

from sqlmodel import Session, col, func, select

from app.models import GoogleSheetToken, GoogleSheetTokenCreate, GoogleSheetTokenUpdate


def create_google_sheet_token(
    *, session: Session, token_in: GoogleSheetTokenCreate
) -> GoogleSheetToken:
    db_obj = GoogleSheetToken.model_validate(token_in)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_google_sheet_token(
    *, session: Session, token_id: int
) -> GoogleSheetToken | None:
    return session.get(GoogleSheetToken, token_id)


def get_google_sheet_tokens(
    *, session: Session, skip: int = 0, limit: int = 100
) -> tuple[list[GoogleSheetToken], int]:
    count = session.exec(select(func.count()).select_from(GoogleSheetToken)).one()
    statement = (
        select(GoogleSheetToken)
        .order_by(
            col(GoogleSheetToken.created_at).desc(), col(GoogleSheetToken.id).desc()
        )
        .offset(skip)
        .limit(limit)
    )
    tokens = list(session.exec(statement).all())
    return tokens, count


def update_google_sheet_token(
    *, session: Session, db_token: GoogleSheetToken, token_in: GoogleSheetTokenUpdate
) -> Any:
    token_data = token_in.model_dump(exclude_unset=True)
    db_token.sqlmodel_update(token_data)
    session.add(db_token)
    session.commit()
    session.refresh(db_token)
    return db_token


def delete_google_sheet_token(*, session: Session, db_token: GoogleSheetToken) -> None:
    session.delete(db_token)
    session.commit()
