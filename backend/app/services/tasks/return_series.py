"""Return-series persistence helpers (relation-table version).

The old 3-parallel-JSON-array columns become ``return_series_point`` rows.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from app.services.market.codes import normalize_market_type, normalize_stock_code


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def extract_return_rows(value: Any) -> list[dict[str, Any]]:
    """Depth-first search for the return-series row list inside a result payload."""
    if isinstance(value, dict):
        for key in ("_return_date", "return_date"):
            rows = value.get(key)
            if isinstance(rows, list):
                return rows
        for child in value.values():
            rows = extract_return_rows(child)
            if rows:
                return rows
    elif isinstance(value, list):
        for child in value:
            rows = extract_return_rows(child)
            if rows:
                return rows
    return []


def build_return_series_points(
    return_rows: Iterable[dict[str, Any]] | None,
    *,
    task_result_id: int,
) -> list[dict[str, Any]]:
    """Build return_series_point row dicts (date/index_return/start_return)."""
    points: list[dict[str, Any]] = []
    for row in return_rows or []:
        if not isinstance(row, dict):
            continue
        parsed = _as_date(row.get("stock_date") or row.get("date"))
        if parsed is None:
            continue
        points.append(
            {
                "task_result_id": task_result_id,
                "date": parsed,
                "index_return": _as_float(row.get("index_return")),
                "start_return": _as_float(row.get("start_return")),
            }
        )
    return points


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace("%", "").replace(",", ""))
    except TypeError, ValueError:
        return None


def build_return_series_fields(
    return_rows: Iterable[dict[str, Any]] | None,
    *,
    stock_code: Any,
    stock_name: Any,
    market_type: Any = None,
    exchange_market: Any = None,
) -> dict[str, Any] | None:
    """Hot-column metadata for a return series (result_timestamp range etc.)."""
    rows = [row for row in (return_rows or []) if isinstance(row, dict)]
    if not rows:
        return None
    parsed_dates = [_as_date(row.get("stock_date") or row.get("date")) for row in rows]
    valid_dates = [value for value in parsed_dates if value is not None]
    if not valid_dates:
        return None
    raw_stock_code = str(stock_code or "").strip()
    normalized_market = normalize_market_type(
        market_type, "cn" if raw_stock_code.isdigit() else "en"
    )
    formatted_code = normalize_stock_code(
        raw_stock_code or "UNKNOWN", normalized_market, exchange_market
    )
    return {
        "stock_code": formatted_code,
        "stock_name": str(stock_name or stock_code or "未知股票").strip() or "未知股票",
        "start_return_date": min(valid_dates),
        "end_return_date": max(valid_dates),
        "return_length": len(rows),
    }
