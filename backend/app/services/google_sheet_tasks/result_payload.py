"""Outbound stock-param payload builders (ported from result_payload.py)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# (payload 键, 模板单元格, 变换)；transform="ratio" 表示百分数 → 小数。
STOCK_PARAM_METRIC_SPECS: list[tuple[str, str, str | None]] = [
    ("return_rate", "D2", "ratio"),
    ("annualized_rate", "D3", "ratio"),
    ("maxdd", "D4", "ratio"),
    ("index_rate", "D5", "ratio"),
    ("index_annualized_rate", "D6", "ratio"),
    ("max_index_dd", "D7", "ratio"),
    ("fee_total", "D8", "ratio"),
    ("fee_annualized", "D9", "ratio"),
    ("turnover_rate", "D10", None),
    ("return_beats", "D11", "ratio"),
    ("dd_beats", "D12", "ratio"),
    ("max_1y_beats", "D13", "ratio"),
    ("min_1y_beats", "D14", "ratio"),
    ("max_theoretical_leverage", "D15", None),
    ("avg_theoretical_leverage", "D16", None),
    ("unit_theoretical_leverage_return", "D17", "ratio"),
    ("max_actual_leverage", "D18", None),
    ("avg_actual_leverage", "D19", None),
    ("unit_actual_leverage_return", "D20", "ratio"),
]

ANALYZE_RESULT_KEYS = (
    "start_monthly_std_dev",
    "index_monthly_std_dev",
    "index_annualized_return",
    "start_annualized_return",
    "index_profit_annual",
    "start_profit_annual",
    "index_profit_monthly_percentage",
    "start_profit_monthly_percentage",
    "index_avg_monthly_return_common",
    "start_avg_monthly_return_common",
    "index_monthly_return_volatility",
    "start_monthly_return_volatility",
    "annualized_return_diff",
    "outperform_year",
    "monthly_excess_return_percentage_last_return",
    "avg_monthly_excess_returns",
    "monthly_excess_volatility",
    "max_drawdown",
    "excess_drawdown_winning_rate",
    "start_drawdown",
    "start_maximum_number_of_backtest_repair_days",
    "excess_maximum_number_of_backtest_repair_days",
    "index_sharpe_ratio",
    "start_sharpe_ratio",
    "index_kama_ratio",
    "start_kama_ratio",
    "index_sortino_ratio",
    "start_sortino_ratio",
    "excess_sharpe",
    "excess_sortino",
)


def to_decimal_ratio(value: Any) -> float:
    """Convert percentage-like values into decimal ratios for outbound payloads."""
    if value in (None, ""):
        return 0
    raw_value = value
    if isinstance(value, str):
        raw_value = value.strip().replace("%", "").replace(",", "")
        if raw_value == "":
            return 0
    try:
        return float(raw_value) / 100
    except TypeError, ValueError:
        return 0


def build_stock_param_metric_fields(
    value_getter: Callable[[str], Any],
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key, cell, transform in STOCK_PARAM_METRIC_SPECS:
        value = value_getter(cell)
        fields[key] = to_decimal_ratio(value) if transform == "ratio" else value
    return fields


def build_analyze_fields(analyze_result: dict[str, Any]) -> dict[str, Any]:
    return {key: analyze_result.get(key, 0) for key in ANALYZE_RESULT_KEYS}
