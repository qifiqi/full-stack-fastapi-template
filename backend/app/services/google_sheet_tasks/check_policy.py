"""Result readiness policy (ported from google_sheet_task check_policy.py)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from app.services.tasks.errors import SheetCheckError

logger = logging.getLogger(__name__)


def is_valid_result_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def _c5_invalid(value: Any) -> bool:
    return (not value) or (not is_valid_result_value(value))


def _c7_invalid(value: Any) -> bool:
    return (
        value is None
        or (isinstance(value, str) and not value.strip())
        or (not is_valid_result_value(value))
    )


C5_INVALID = _c5_invalid
C7_INVALID = _c7_invalid


def normalize_check_values(
    check_values: dict[str, Any],
    *,
    log_info: Callable[[str], None] = logger.info,
    invalid_predicate: Callable[[Any], bool] = _c5_invalid,
) -> dict[str, Any]:
    """Validate and normalize Sheet check-cell outputs.

    - invalid values raise (caller counts the failure);
    - '#'-prefixed values raise SheetCheckError (template error signal);
    - '5.00%' -> 0.05, '1,234' -> 1234.0;
    - '-' placeholders are dropped.
    """
    normalized: dict[str, Any] = {}
    for position, value in check_values.items():
        if invalid_predicate(value):
            log_info(f"结果位置 {position} 值为空或无效，跳过重新检查：{value}")
            raise Exception(f"结果位置 {position} 值为空或无效，跳过重新检查：{value}")
        if str(value).strip().startswith(("#", "#N/A")):
            error_msg = f"获取结果位置 {position} 时出错: {value}"
            raise SheetCheckError(
                f"检查报错，出现#|#N/A 这种异常错误，联系用户检查 {error_msg}"
            )
        normalized_value = value
        if isinstance(normalized_value, str) and "%" in normalized_value:
            normalized_value = (
                float(normalized_value.replace("%", "").replace(",", "")) / 100
            )
        if isinstance(normalized_value, str) and "," in normalized_value:
            normalized_value = float(normalized_value.replace(",", ""))
        if normalized_value == "-":
            continue
        normalized[position] = normalized_value
    return normalized
