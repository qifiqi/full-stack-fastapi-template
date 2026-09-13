"""Google Sheet registry service (adapted to the new google_sheet model)."""

import logging
import time
from typing import Any

from sqlmodel import Session, col, func, or_, select

from app.models import GoogleSheet, GoogleSheetCreate
from app.services.google_sheet.client import GoogleSheet as GoogleSheetClient
from app.services.tasks.errors import ConflictError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)


def google_sheet_registry_scope(table_type: str | None) -> str:
    """Registry grouping key: C-series share one scope (source semantics)."""
    normalized = (table_type or "").strip().lower()
    if normalized == "c31":
        normalized = "c3"
    if normalized in {"c3", "c4", "c5", "c7"}:
        return "c_series"
    return normalized or "default"


class GoogleSheetRegistryService:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory
        self._worksheets_cache: dict[str, dict[str, Any]] = {}
        self._worksheets_cache_ttl = 5 * 24 * 60 * 60

    def list_sheets(
        self,
        session: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        registry_scope: str | None = None,
        only_available: bool = False,
    ) -> tuple[list[GoogleSheet], int]:
        statement = select(GoogleSheet)
        count_statement = select(func.count()).select_from(GoogleSheet)
        if registry_scope:
            statement = statement.where(GoogleSheet.registry_scope == registry_scope)
            count_statement = count_statement.where(
                GoogleSheet.registry_scope == registry_scope
            )
        if only_available:
            condition = or_(
                col(GoogleSheet.is_in_use) == False,  # noqa: E712
                col(GoogleSheet.current_task_id).is_(None),
            )
            statement = statement.where(condition)
            count_statement = count_statement.where(condition)
        count = session.exec(count_statement).one()
        statement = (
            statement.order_by(col(GoogleSheet.name).asc(), col(GoogleSheet.id).asc())
            .offset(skip)
            .limit(limit)
        )
        return list(session.exec(statement).all()), count

    def get_sheet(self, session: Session, sheet_id: int) -> GoogleSheet | None:
        return session.get(GoogleSheet, sheet_id)

    def create_sheet(
        self,
        session: Session,
        *,
        spreadsheet_id: str,
        name: str | None = None,
        registry_scope: str | None = None,
    ) -> GoogleSheet:
        spreadsheet_id = (spreadsheet_id or "").strip()
        if not spreadsheet_id:
            raise ValidationError("spreadsheet_id 不能为空")
        scope = google_sheet_registry_scope(registry_scope)
        duplicate = session.exec(
            select(GoogleSheet).where(
                GoogleSheet.spreadsheet_id == spreadsheet_id,
                GoogleSheet.registry_scope == scope,
            )
        ).first()
        if duplicate:
            raise ValidationError("相同 spreadsheet_id 已存在于该注册分组")
        db_obj = GoogleSheet.model_validate(
            GoogleSheetCreate(
                spreadsheet_id=spreadsheet_id,
                name=(name or "").strip() or spreadsheet_id,
                registry_scope=scope,
            )
        )
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj

    def update_sheet(
        self, session: Session, sheet_id: int, *, sheet_in: Any
    ) -> GoogleSheet:
        db_sheet = session.get(GoogleSheet, sheet_id)
        if not db_sheet:
            raise NotFoundError("所选 Google Sheet 不存在")

        data = sheet_in.model_dump(exclude_unset=True)
        new_scope = data.get("registry_scope")
        if new_scope is not None:
            data["registry_scope"] = google_sheet_registry_scope(new_scope)
        target_spreadsheet = data.get("spreadsheet_id", db_sheet.spreadsheet_id)
        target_scope = data.get("registry_scope", db_sheet.registry_scope)
        duplicate = session.exec(
            select(GoogleSheet).where(
                GoogleSheet.spreadsheet_id == target_spreadsheet,
                GoogleSheet.registry_scope == target_scope,
                GoogleSheet.id != sheet_id,
            )
        ).first()
        if duplicate:
            raise ValidationError("相同 spreadsheet_id 已存在于该注册分组")

        db_sheet.sqlmodel_update(data)
        session.add(db_sheet)
        session.commit()
        session.refresh(db_sheet)
        return db_sheet

    def delete_sheet(self, session: Session, sheet_id: int) -> None:
        db_sheet = session.get(GoogleSheet, sheet_id)
        if not db_sheet:
            raise NotFoundError("所选 Google Sheet 不存在")
        if db_sheet.is_in_use:
            raise ConflictError("Google Sheet 正在被任务使用，无法删除")
        session.delete(db_sheet)
        session.commit()

    # -- occupancy ----------------------------------------------------------
    def acquire_for_task(
        self, session: Session, sheet_id: int, task_id: int
    ) -> GoogleSheet:
        db_sheet = session.get(GoogleSheet, sheet_id)
        if not db_sheet:
            raise NotFoundError("所选 Google Sheet 不存在")
        if db_sheet.current_task_id == task_id and db_sheet.is_in_use:
            return db_sheet
        if db_sheet.is_in_use and db_sheet.current_task_id != task_id:
            raise ConflictError("Google Sheet 正在被其他任务使用")
        db_sheet.is_in_use = True
        db_sheet.current_task_id = task_id
        session.add(db_sheet)
        session.commit()
        session.refresh(db_sheet)
        if not db_sheet.is_in_use or db_sheet.current_task_id != task_id:
            raise ConflictError("Google Sheet 占用失败，请重试")
        return db_sheet

    def release_for_task(self, session: Session, task_id: int) -> bool:
        statement = select(GoogleSheet).where(
            GoogleSheet.current_task_id == task_id,
            col(GoogleSheet.is_in_use) == True,  # noqa: E712
        )
        rows = session.exec(statement).all()
        for sheet in rows:
            sheet.is_in_use = False
            sheet.current_task_id = None
            session.add(sheet)
        if rows:
            session.commit()
        return bool(rows)

    # -- worksheets cache ---------------------------------------------------
    def get_worksheets_with_cache(
        self,
        spreadsheet_id: str,
        token_file: str,
        proxy_url: str | None,
        http_timeout: int | None = None,
    ) -> dict[str, Any]:
        cache_key = f"{spreadsheet_id}|{token_file}|{proxy_url or ''}"
        cached = self._worksheets_cache.get(cache_key)
        now = time.time()
        if cached and now - cached.get("_ts", 0) < self._worksheets_cache_ttl:
            return {
                "title": cached["title"],
                "worksheets": cached["worksheets"],
                "cached": True,
            }

        client = GoogleSheetClient(
            spreadsheet_id,
            token_file=token_file,
            proxy_url=proxy_url,
            http_timeout=http_timeout,
        )
        try:
            result = {
                "title": client.title or "",
                "worksheets": client.get_all_worksheets(),
            }
        finally:
            client.close()

        self._worksheets_cache[cache_key] = {**result, "_ts": now}
        return result
