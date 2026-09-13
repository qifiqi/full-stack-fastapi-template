"""Google Sheet token pool service (rewritten for the new google_sheet_token model).

Per-token task-type quotas live in the ``type_quotas`` JSON column instead of
the old per-row ``task_type`` column; runtime token files live under
``settings.google_token_dir`` instead of a ``token_file`` column.
"""

import json
import random
import re
from pathlib import Path
from typing import Any

from sqlmodel import Session, col, select

from app.core.config import settings
from app.models import GoogleSheetToken, GoogleSheetTokenCreate, Task
from app.services.config_manager import get_config_manager
from app.services.tasks.errors import NotFoundError, ValidationError

RANDOM_TOKEN_VALUE = "__random__"

DEFAULT_TOKEN_TYPE = "google_sheet"


def normalize_token_task_type(
    value: str | None, default: str | None = DEFAULT_TOKEN_TYPE
) -> str | None:
    raw = (value or "").strip().lower()
    return raw if raw in {"google_sheet", "backtest_training"} else default


class GoogleSheetTokenService:
    """Token pool with usage accounting, driven by an injected session factory."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    # -- helpers ------------------------------------------------------------
    def _token_type_quota(self, token: GoogleSheetToken, task_type: str | None) -> int:
        quotas = token.type_quotas if isinstance(token.type_quotas, dict) else {}
        raw = quotas.get(normalize_token_task_type(task_type) or "")
        try:
            return int(raw or 0)
        except TypeError, ValueError:
            return 0

    def is_available(
        self, token: GoogleSheetToken, task_type: str | None = None
    ) -> bool:
        if not token.is_active:
            return False
        if token.max_usage_count and token.max_usage_count > 0:
            if token.current_in_use_count >= token.max_usage_count:
                return False
        quota = self._token_type_quota(token, task_type)
        if quota > 0 and token.current_in_use_count >= quota:
            return False
        return True

    def token_file_path(self, token: GoogleSheetToken) -> str:
        token_dir = Path(settings.google_token_dir) / "google_sheet_tokens"
        return str(token_dir / f"token_{token.id}.json")

    def _build_live_usage_snapshot(self) -> dict[str, Any]:
        """Current per-token occupancy derived from running task configs."""
        token_usage: dict[int, int] = {}
        current_total = 0
        with self._session_factory() as session:
            rows = session.exec(
                select(Task.id, Task.config).where(
                    Task.status == "running", col(Task.config).is_not(None)
                )
            ).all()
        for _task_id, config in rows:
            if not isinstance(config, dict):
                continue
            if config.get("token_type", "file") != "file":
                continue
            token_id = config.get("token_id")
            if not token_id:
                continue
            try:
                token_id_int = int(token_id)
            except TypeError, ValueError:
                continue
            token_usage[token_id_int] = token_usage.get(token_id_int, 0) + 1
            current_total += 1
        return {"token_usage": token_usage, "current_total": current_total}

    def _assert_token_usage_available(
        self, token: GoogleSheetToken, current_in_use: int, task_type: str | None = None
    ) -> None:
        if not token:
            raise NotFoundError("所选 Token 不存在")
        if not token.is_active:
            raise ValidationError(f"Token [{token.name}] 已被禁用，请更换 Token")

        max_usage = int(token.max_usage_count or 0)
        if max_usage > 0 and int(current_in_use) >= max_usage:
            raise ValidationError(
                f"Token [{token.name}] 已达到最大占用次数 ({current_in_use}/{max_usage})，请更换 Token"
            )
        quota = self._token_type_quota(token, task_type)
        if quota > 0 and int(current_in_use) >= quota:
            raise ValidationError(
                f"Token [{token.name}] 已达到 {task_type} 类型配额 ({current_in_use}/{quota})，请更换 Token"
            )

    # -- maintenance --------------------------------------------------------
    def reconcile_in_use_counts(self) -> int:
        snapshot = self._build_live_usage_snapshot()
        token_usage = snapshot["token_usage"]
        updated = 0
        with self._session_factory() as session:
            tokens = session.exec(select(GoogleSheetToken)).all()
            for token in tokens:
                count = int(token_usage.get(int(token.id or 0), 0))
                if token.current_in_use_count != count:
                    token.current_in_use_count = count
                    session.add(token)
                    updated += 1
            session.commit()
        return updated

    # -- CRUD-facing --------------------------------------------------------
    def list_tokens(self, session: Session) -> list[GoogleSheetToken]:
        statement = select(GoogleSheetToken).order_by(
            col(GoogleSheetToken.is_active).desc(),
            col(GoogleSheetToken.current_in_use_count).asc(),
            col(GoogleSheetToken.total_usage_count).asc(),
            col(GoogleSheetToken.id).asc(),
        )
        return list(session.exec(statement).all())

    def import_token(
        self,
        session: Session,
        *,
        token_context: str | None = None,
        name: str | None = None,
        max_usage_count: int | None = None,
        type_quotas: dict[str, int] | None = None,
    ) -> tuple[GoogleSheetToken, bool]:
        normalized_context = self._load_token_context(token_context=token_context)
        target_context: dict[str, Any] = json.loads(normalized_context)

        # JSON(B) columns cannot be compared to text portably (PG jsonb vs
        # varchar); dedupe by deserialized equality instead.
        existing = None
        for candidate in session.exec(select(GoogleSheetToken)).all():
            if candidate.token_context == target_context:
                existing = candidate
                break
        if existing is not None:
            if name:
                existing.name = name.strip()
            if max_usage_count is not None:
                existing.max_usage_count = max(0, int(max_usage_count))
            if type_quotas is not None:
                existing.type_quotas = type_quotas
            existing.is_active = True
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing, False

        token = GoogleSheetTokenCreate(
            name=(name or "").strip() or None,
            token_context=target_context,
            max_usage_count=max_usage_count,
            type_quotas=type_quotas,
            is_active=True,
        )
        db_token = GoogleSheetToken.model_validate(token)
        session.add(db_token)
        session.commit()
        session.refresh(db_token)
        return db_token, True

    def update_token(
        self, session: Session, token_id: int, **payload: Any
    ) -> GoogleSheetToken | None:
        token = session.get(GoogleSheetToken, token_id)
        if not token:
            return None

        name = payload.get("name")
        max_usage_count = payload.get("max_usage_count")
        is_active = payload.get("is_active")
        type_quotas = payload.get("type_quotas")
        token_context = payload.get("token_context")

        if name is not None:
            token.name = str(name).strip() or token.name
        if max_usage_count is not None:
            token.max_usage_count = max(0, int(max_usage_count))
        if is_active is not None:
            token.is_active = bool(is_active)
        if type_quotas is not None:
            token.type_quotas = type_quotas
        if token_context is not None:
            token.token_context = json.loads(
                self._load_token_context(token_context=token_context)
            )
        session.add(token)
        session.commit()
        session.refresh(token)
        return token

    def delete_token(self, session: Session, token_id: int) -> bool:
        token = session.get(GoogleSheetToken, token_id)
        if not token:
            return False
        session.delete(token)
        session.commit()
        return True

    # -- runtime ------------------------------------------------------------
    def ensure_token_file(self, session: Session, token: GoogleSheetToken) -> str:
        runtime_path = Path(self.token_file_path(token))
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        content = token.token_context
        text = (
            content
            if isinstance(content, str)
            else json.dumps(content, ensure_ascii=False, indent=2)
        )
        if (
            not runtime_path.exists()
            or runtime_path.read_text(encoding="utf-8") != text
        ):
            runtime_path.write_text(text, encoding="utf-8")
        return str(runtime_path)

    def pick_token(
        self,
        session: Session,
        token_selection: Any,
        task_type: str | None = None,
        snapshot: dict[str, Any] | None = None,
    ) -> GoogleSheetToken:
        snapshot = snapshot or self._build_live_usage_snapshot()
        normalized_task_type = normalize_token_task_type(task_type)
        if str(token_selection) == RANDOM_TOKEN_VALUE:
            return self._pick_random_available_token(
                session, snapshot=snapshot, task_type=normalized_task_type
            )

        token = session.get(GoogleSheetToken, int(token_selection))
        if not token:
            raise NotFoundError("所选 Token 不存在")
        current_in_use = int(snapshot["token_usage"].get(int(token.id or 0), 0))
        self._assert_token_usage_available(token, current_in_use, normalized_task_type)
        return token

    def _pick_random_available_token(
        self,
        session: Session,
        snapshot: dict[str, Any],
        task_type: str | None = None,
    ) -> GoogleSheetToken:
        token_usage = snapshot["token_usage"]
        statement = select(GoogleSheetToken).where(col(GoogleSheetToken.is_active))  # noqa: E712
        statement = statement.order_by(
            col(GoogleSheetToken.current_in_use_count).asc(),
            col(GoogleSheetToken.total_usage_count).asc(),
            col(GoogleSheetToken.id).asc(),
        )
        tokens = session.exec(statement).all()
        available = []
        for token in tokens:
            current_in_use = int(token_usage.get(int(token.id or 0), 0))
            if self.is_available(token, task_type) or (
                token.max_usage_count
                and token.max_usage_count > 0
                and current_in_use < token.max_usage_count
                and not self._token_type_quota(token, task_type)
            ):
                available.append((token, current_in_use))
        if not available:
            raise ValidationError(
                "所有 Token 都已达到上限，请先调整 Token 或系统上限配置"
            )

        min_usage = min(current_in_use for _, current_in_use in available)
        candidates = [
            token for token, current_in_use in available if current_in_use == min_usage
        ]
        return random.choice(candidates)

    def validate_task_start(self, config: dict[str, Any]) -> None:
        if not isinstance(config, dict):
            return
        if config.get("token_type", "file") != "file":
            return

        snapshot = self._build_live_usage_snapshot()
        self._assert_global_usage_available(current_total=snapshot["current_total"])

        token_id = config.get("token_id")
        if not token_id:
            return
        with self._session_factory() as session:
            token = session.get(GoogleSheetToken, int(token_id))
            if not token:
                raise NotFoundError("所选 Token 不存在")
            current_in_use = int(snapshot["token_usage"].get(int(token.id or 0), 0))
            expected_task_type = normalize_token_task_type(
                config.get("token_task_type")
            )
            self._assert_token_usage_available(
                token, current_in_use, expected_task_type
            )

    def increment_usage(
        self, session: Session, token_id: int | None
    ) -> GoogleSheetToken | None:
        if not token_id:
            return None

        snapshot = self._build_live_usage_snapshot()
        self._assert_global_usage_available(current_total=snapshot["current_total"])

        token = session.get(GoogleSheetToken, int(token_id))
        if not token:
            raise NotFoundError("所选 Token 不存在")
        current_in_use = int(snapshot["token_usage"].get(int(token.id or 0), 0))
        self._assert_token_usage_available(token, current_in_use)

        token.total_usage_count = int(token.total_usage_count or 0) + 1
        token.current_in_use_count = current_in_use + 1
        session.add(token)
        session.commit()
        session.refresh(token)
        return token

    def release_usage(
        self, session: Session, token_id: int | None
    ) -> GoogleSheetToken | None:
        if not token_id:
            return None

        token = session.get(GoogleSheetToken, int(token_id))
        if not token:
            return None

        token.current_in_use_count = max(0, int(token.current_in_use_count or 0) - 1)
        session.add(token)
        session.commit()
        session.refresh(token)
        return token

    def _assert_global_usage_available(self, current_total: int | None = None) -> None:
        max_usage = self._get_global_max_usage()
        if max_usage <= 0:
            return
        if current_total is None:
            snapshot = self._build_live_usage_snapshot()
            current_total = int(snapshot["current_total"])
        if int(current_total) >= max_usage:
            raise ValidationError(
                f"所有 Token 当前占用次数已达到系统上限({max_usage})，停止生成任务"
            )

    def _get_global_max_usage(self) -> int:
        try:
            manager = get_config_manager()
            value = manager.get_config("google_sheet_token_global_max_usage", 0)
        except Exception:
            value = 0
        try:
            return int(value or 0)
        except TypeError, ValueError:
            return 0

    def _load_token_context(self, token_context: str | None = None) -> str:
        raw_context = (token_context or "").strip()
        if not raw_context:
            raise ValidationError("token内容不能为空")
        try:
            parsed = json.loads(raw_context)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"token内容不是有效JSON: {exc}") from exc
        return json.dumps(parsed, ensure_ascii=False, indent=2)


_TOKEN_ID_PATTERN = re.compile(r"token_(\d+)\.json$")


def parse_token_id_from_path(path: str | None) -> int | None:
    match = _TOKEN_ID_PATTERN.search(str(path or ""))
    return int(match.group(1)) if match else None
