"""SystemConfig-backed runtime configuration center (Session-injected port)."""

import json
import threading
from pathlib import Path
from typing import Any

from sqlmodel import select

from app.core.config import settings
from app.models import SystemConfig

_MISSING = object()

_SENSITIVE_KEY_HINTS = ("token", "secret", "password", "credential", "apikey")


def mask_config_value(key: str, value: Any) -> Any:
    lowered = str(key).lower()
    if any(hint in lowered for hint in _SENSITIVE_KEY_HINTS):
        return "***"
    return value


def _serialize_config_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError, ValueError:
        return str(value)


def _reject_json_constant(name: str) -> Any:
    raise ValueError(f"非法 JSON 常量: {name}")


def _deserialize_config_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    if value == "True":
        return True
    if value == "False":
        return False
    if value == "None":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "null":
        return None

    stripped = value.strip()
    if stripped[:1] in ("{", "[", '"'):
        try:
            return json.loads(stripped, parse_constant=_reject_json_constant)
        except json.JSONDecodeError, TypeError, ValueError:
            return value

    if stripped[:1].isdigit() or stripped[:1] in ("-", "."):
        try:
            parsed = json.loads(stripped, parse_constant=_reject_json_constant)
        except json.JSONDecodeError, TypeError, ValueError:
            return value
        if isinstance(parsed, (int, float)):
            return parsed
    return value


def coerce_bool(value: Any, default: bool = False) -> bool:
    if value is _MISSING:
        return default
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("1", "true", "yes", "on", "t", "y"):
            return True
        if normalized in ("", "0", "false", "no", "off", "n"):
            return False
    return default


class ConfigManager:
    """In-process cached reader over the system_config table.

    A single worker/API process owns one instance; every DB access opens a
    short-lived session from the injected factory (worker-thread safe).
    """

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory
        self._cache: dict[str, Any] = {}
        self._loaded = False
        self._lock = threading.RLock()

    def _load_configs(self) -> None:
        try:
            with self._session_factory() as session:
                rows = session.exec(select(SystemConfig)).all()
            cache: dict[str, Any] = {row.key: row.value for row in rows}
            with self._lock:
                self._cache = {
                    k: _deserialize_config_value(v) for k, v in cache.items()
                }
                self._loaded = True
        except Exception:
            pass

    def get_config(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if not self._loaded:
                self._load_configs()

            if key in self._cache:
                value = self._cache[key]
                return default if value is _MISSING else value

            try:
                with self._session_factory() as session:
                    row = session.get(SystemConfig, key)
                    if row:
                        value = _deserialize_config_value(row.value)
                        self._cache[key] = value
                        return value
                    self._cache[key] = _MISSING
                    return default
            except Exception:
                return default

    def get_all_configs(self, force_refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            if force_refresh or not self._loaded:
                self._load_configs()
            return {k: v for k, v in self._cache.items() if v is not _MISSING}

    def set_config(self, key: str, value: Any) -> bool:
        try:
            value_str = _serialize_config_value(value)
            with self._session_factory() as session:
                db_obj = session.get(SystemConfig, key)
                if db_obj:
                    db_obj.value = value_str
                else:
                    db_obj = SystemConfig(key=key, value=value_str)
                session.add(db_obj)
                session.commit()
            with self._lock:
                self._cache[key] = _deserialize_config_value(value_str)
            return True
        except Exception:
            return False

    def delete_config(self, key: str) -> bool:
        try:
            with self._session_factory() as session:
                db_obj = session.get(SystemConfig, key)
                if not db_obj:
                    return False
                session.delete(db_obj)
                session.commit()
            with self._lock:
                self._cache.pop(key, None)
            return True
        except Exception:
            return False

    def update_configs(self, configs: dict[str, Any]) -> bool:
        try:
            for key, value in configs.items():
                if not self.set_config(key, value):
                    return False
            with self._lock:
                self._load_configs()
            return True
        except Exception:
            return False

    def get_google_sheet_config(self, force_refresh: bool = False) -> dict[str, Any]:
        configs = self.get_all_configs(force_refresh=force_refresh)

        param_positions = configs.get("parameter_positions", [])
        check_positions = configs.get("check_positions", [])
        result_positions = configs.get("result_positions", [])

        if isinstance(param_positions, dict):
            param_positions = list(param_positions.values())
        if isinstance(check_positions, dict):
            check_positions = list(check_positions.values())
        if isinstance(result_positions, dict):
            result_positions = list(result_positions.values())

        configs["parameter_positions"] = param_positions
        configs["check_positions"] = check_positions
        configs["result_positions"] = result_positions
        return configs

    def refresh_cache(self) -> None:
        with self._lock:
            self._load_configs()

    def resolve_google_token_path(self, relative: str | None) -> str:
        """Resolve a token file path under GOOGLE_TOKEN_DIR."""
        candidate = relative or "token.json"
        path = Path(candidate)
        if not path.is_absolute():
            path = Path(settings.google_token_dir) / path
        return str(path)


_config_manager: ConfigManager | None = None
_config_manager_lock = threading.Lock()


def init_config_manager(session_factory: Any) -> ConfigManager:
    global _config_manager
    if _config_manager is None:
        with _config_manager_lock:
            if _config_manager is None:
                _config_manager = ConfigManager(session_factory)
    return _config_manager


def get_config_manager() -> ConfigManager:
    if _config_manager is None:
        raise RuntimeError(
            "config_manager not initialized; call init_config_manager() first"
        )
    return _config_manager


def try_get_config_manager() -> ConfigManager | None:
    return _config_manager
