from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import SessionDep
from app.crud import get_system_config, get_system_configs, upsert_system_config
from app.models import SystemConfigUpdate
from app.services.config_manager import mask_config_value

router = APIRouter(prefix="/configs", tags=["configs"])


@router.get("/")
def read_configs(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """List system config entries (sensitive values masked)."""
    result = get_system_configs(session=session, skip=skip, limit=limit)
    for item in result.data:
        item.value = mask_config_value(item.key, item.value)
    return result


@router.get("/validate")
def validate_configs(_session: SessionDep) -> Any:
    """Sanity-check known config keys (types parse, bounds hold)."""
    from app.services.config_manager import coerce_bool, get_config_manager

    manager = get_config_manager()
    checks = []
    integer_keys = {
        "task_max_workers": (1, 64),
        "execution_delay_min": (0, 3600),
        "execution_delay_max": (0, 3600),
        "google_sheet_token_global_max_usage": (0, 10000),
    }
    bool_keys = ["watchdog_enabled"]
    for key, (low, high) in integer_keys.items():
        value = manager.get_config(key, None)
        if value is None:
            continue
        try:
            number = int(value)
            checks.append({"key": key, "valid": low <= number <= high})
        except TypeError, ValueError:
            checks.append({"key": key, "valid": False})
    for key in bool_keys:
        value = manager.get_config(key, None)
        if value is None:
            continue
        checks.append({"key": key, "valid": coerce_bool(value, True) in (True, False)})
    return {"data": checks, "count": len(checks)}


@router.get("/{key}")
def read_config(session: SessionDep, key: str) -> Any:
    """Read one config value (sensitive values masked)."""
    config = get_system_config(session=session, key=key)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    return {"key": config.key, "value": mask_config_value(config.key, config.value)}


@router.put("/{key}")
def update_config(session: SessionDep, key: str, config_in: SystemConfigUpdate) -> Any:
    """Upsert one config value."""
    config = upsert_system_config(session=session, key=key, value=config_in.value)
    return {"key": config.key, "value": config.value}
