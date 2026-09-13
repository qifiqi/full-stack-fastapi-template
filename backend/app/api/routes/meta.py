from typing import Any

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.core.workers import TASK_TYPE_REGISTRY

router = APIRouter(prefix="/meta", tags=["meta"])

APP_VERSION = "0.1.0"


@router.get("/versions")
def read_versions() -> Any:
    """App/API version info."""
    return {"app": APP_VERSION, "api": "/api/v1"}


@router.get("/enums")
def read_enums(session: SessionDep) -> Any:
    """Single source of truth for UI enums (task types, statuses, markets)."""
    task_types = [
        {
            "value": spec.type_key,
            "label": spec.display_name,
        }
        for spec in TASK_TYPE_REGISTRY.values()
    ]
    statuses = [
        {"value": "pending", "label": "待执行"},
        {"value": "queued", "label": "排队中"},
        {"value": "running", "label": "运行中"},
        {"value": "success", "label": "成功"},
        {"value": "error", "label": "失败"},
        {"value": "cancelled", "label": "已取消"},
    ]
    markets = [
        {"value": "cn", "label": "A股"},
        {"value": "en", "label": "美股"},
        {"value": "hk", "label": "港股"},
        {"value": "fund", "label": "场外基金"},
    ]
    log_levels = ["INFO", "WARNING", "ERROR"]
    from app.crud import get_task_statistics  # noqa: F401

    _ = session  # reserved for future dynamic enums from SystemConfig
    return {
        "task_types": task_types,
        "task_statuses": statuses,
        "market_types": markets,
        "log_levels": log_levels,
    }
