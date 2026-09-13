import json
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import Session

from app.api.deps import SessionDep
from app.models import (
    GoogleSheetCreate,
    GoogleSheetPublic,
    GoogleSheetsPublic,
    GoogleSheetToken,
    GoogleSheetTokenCreate,
    GoogleSheetTokenPublic,
    GoogleSheetTokensPublic,
    GoogleSheetTokenUpdate,
    GoogleSheetUpdate,
    Message,
)
from app.services.google_sheet.registry_service import (
    GoogleSheetRegistryService,
)
from app.services.google_sheet.token_service import GoogleSheetTokenService

sheets_router = APIRouter(prefix="/google-sheets", tags=["google-sheets"])
tokens_router = APIRouter(prefix="/google-sheet-tokens", tags=["google-sheet-tokens"])


def _registry_service(session: Session) -> GoogleSheetRegistryService:
    return GoogleSheetRegistryService(
        session_factory=lambda: Session(session.get_bind())
    )


def _token_service(session: Session) -> GoogleSheetTokenService:
    return GoogleSheetTokenService(session_factory=lambda: Session(session.get_bind()))


# -- google sheets ----------------------------------------------------------


@sheets_router.get("/", response_model=GoogleSheetsPublic)
def read_google_sheets(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    registry_scope: str | None = None,
    only_available: bool = False,
) -> Any:
    """List registered Google Sheets with occupancy state."""
    sheets, count = _registry_service(session).list_sheets(
        session,
        skip=skip,
        limit=limit,
        registry_scope=registry_scope,
        only_available=only_available,
    )
    return GoogleSheetsPublic(
        data=[GoogleSheetPublic.model_validate(s) for s in sheets], count=count
    )


@sheets_router.post("/", response_model=GoogleSheetPublic)
def create_google_sheet(session: SessionDep, sheet_in: GoogleSheetCreate) -> Any:
    """Register a Google Sheet."""
    try:
        return _registry_service(session).create_sheet(
            session,
            spreadsheet_id=sheet_in.spreadsheet_id,
            name=sheet_in.name,
            registry_scope=sheet_in.registry_scope,
        )
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@sheets_router.get("/{id}", response_model=GoogleSheetPublic)
def read_google_sheet(session: SessionDep, id: int) -> Any:
    """Get a registered sheet."""
    sheet = _registry_service(session).get_sheet(session, id)
    if not sheet:
        raise HTTPException(status_code=404, detail="Google Sheet not found")
    return sheet


@sheets_router.put("/{id}", response_model=GoogleSheetPublic)
def update_google_sheet(
    session: SessionDep, id: int, sheet_in: GoogleSheetUpdate
) -> Any:
    """Update a registered sheet."""
    try:
        return _registry_service(session).update_sheet(session, id, sheet_in=sheet_in)
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@sheets_router.delete("/{id}")
def delete_google_sheet(session: SessionDep, id: int) -> Message:
    """Delete a registered sheet (blocked while occupied)."""
    try:
        _registry_service(session).delete_sheet(session, id)
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Message(message="Google Sheet deleted successfully")


# -- token pool ---------------------------------------------------------------


@tokens_router.get("/", response_model=GoogleSheetTokensPublic)
def read_google_sheet_tokens(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> Any:
    """List the token pool with usage counters."""
    tokens = _token_service(session).list_tokens(session)
    page = tokens[skip : skip + limit]
    return GoogleSheetTokensPublic(
        data=[GoogleSheetTokenPublic.model_validate(t) for t in page], count=len(tokens)
    )


@tokens_router.post("/", response_model=GoogleSheetTokenPublic)
def create_google_sheet_token(
    session: SessionDep, token_in: GoogleSheetTokenCreate
) -> Any:
    """Import one OAuth token into the pool."""
    context_text = (
        token_in.token_context
        if isinstance(token_in.token_context, str)
        else json.dumps(token_in.token_context, ensure_ascii=False)
    )
    token, _is_new = _token_service(session).import_token(
        session,
        token_context=context_text,
        name=token_in.name,
        max_usage_count=token_in.max_usage_count,
        type_quotas=token_in.type_quotas,
    )
    return token


class TokenImportRequest(GoogleSheetTokenCreate):
    pass


@tokens_router.post("/import", response_model=list[GoogleSheetTokenPublic])
def import_google_sheet_tokens(
    session: SessionDep, tokens: list[TokenImportRequest]
) -> Any:
    """Batch-import tokens (deduplicated by context)."""
    service = _token_service(session)
    imported: list[GoogleSheetTokenPublic] = []
    for item in tokens:
        context_text = (
            item.token_context
            if isinstance(item.token_context, str)
            else json.dumps(item.token_context, ensure_ascii=False)
        )
        token, _new = service.import_token(
            session,
            token_context=context_text,
            name=item.name,
            max_usage_count=item.max_usage_count,
            type_quotas=item.type_quotas,
        )
        imported.append(GoogleSheetTokenPublic.model_validate(token))
    return imported


@tokens_router.post("/reconcile", response_model=Message)
def reconcile_google_sheet_tokens(session: SessionDep) -> Message:
    """Reconcile current_in_use_count against running task configs."""
    updated = _token_service(session).reconcile_in_use_counts()
    return Message(message=f"Reconciled {updated} token counters")


@tokens_router.get("/{id}", response_model=GoogleSheetTokenPublic)
def read_google_sheet_token(session: SessionDep, id: int) -> Any:
    """Get one token (context included; mask before display in the UI)."""
    token = session.get(GoogleSheetToken, id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    return token


@tokens_router.put("/{id}", response_model=GoogleSheetTokenPublic)
def update_google_sheet_token(
    session: SessionDep, id: int, token_in: GoogleSheetTokenUpdate
) -> Any:
    """Update token name/quotas/active flag."""
    token = _token_service(session).update_token(
        session,
        id,
        **token_in.model_dump(exclude_unset=True),
    )
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    return token


@tokens_router.delete("/{id}")
def delete_google_sheet_token(session: SessionDep, id: int) -> Message:
    """Remove a token from the pool."""
    if not _token_service(session).delete_token(session, id):
        raise HTTPException(status_code=404, detail="Token not found")
    return Message(message="Token deleted successfully")
