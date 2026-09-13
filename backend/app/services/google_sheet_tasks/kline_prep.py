"""K-line write preparation pipeline (ported from google_sheet_task kline_prep.py)."""

from __future__ import annotations

from typing import Any


class KlineRowsError(Exception):
    """Raised when the kline rows for a parameter set are missing/insufficient."""


def require_kline_rows(
    parameter: Any,
    market_type: str,
    all_kline: list[dict[str, Any]],
    *,
    context: str,
    start_date: str | None = None,
    end_date: str | None = None,
    latest_date: str | None = None,
    min_rows: int = 1,
    price_field: str = "stock_val",
) -> list[dict[str, Any]]:
    rows = [row for row in all_kline if row.get(price_field) is not None]
    if len(rows) < min_rows:
        raise KlineRowsError(
            f"{context} K线行数不足: parameter={parameter} market={market_type} "
            f"rows={len(rows)} required>={min_rows} range={start_date}~{end_date}"
        )
    if latest_date and end_date and str(latest_date) > str(end_date):
        raise KlineRowsError(
            f"{context} K线数据超出结束日期: latest={latest_date} end={end_date}"
        )
    return rows


def project_and_validate_write_ready(
    kline_service: Any,
    *,
    parameter: Any,
    market_type: str,
    klines: list[dict[str, Any]],
    price_mode: str,
    price_field: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    data_end_date: str | None = None,
    include_ohlc: bool = False,
) -> list[dict[str, Any]]:
    """Range filter -> build_price_rows projection -> write-ready validation."""
    klines = [k for k in klines if start_date <= k["stock_date"] <= end_date]
    all_kline = kline_service.build_price_rows(
        klines,
        price_mode,
        start_date=start_date,
        end_date=end_date,
        price_field=price_field,
        include_ohlc=include_ohlc,
    )
    return require_kline_rows(
        parameter,
        market_type,
        all_kline,
        context="写入Sheet K线",
        start_date=start_date,
        end_date=end_date,
        latest_date=data_end_date,
    )
