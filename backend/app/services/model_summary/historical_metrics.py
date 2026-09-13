"""Historical metric payload compatibility (ported from historical_metrics.py)."""

from __future__ import annotations

from typing import Any

_LEGACY_KEYS = {
    "index_sotino_ratio": "index_sortino_ratio",
    "start_sotino_ratio": "start_sortino_ratio",
    "index_weekly_sotino_ratio": "index_weekly_sortino_ratio",
    "start_weekly_sotino_ratio": "start_weekly_sortino_ratio",
    "sotino_ratio": "sortino_ratio",
    "excess_sharp": "excess_sharpe",
    "excess_of_promissory_note": "excess_sortino",
    "cumulative_excess": "excess_cumulative_return",
    "excess_net": "excess_nav",
}


def upgrade_historical_metrics(value: Any) -> Any:
    """Read-time conversion of legacy metric JSON keys to current names."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = _LEGACY_KEYS.get(str(key), str(key))
            result[normalized_key] = upgrade_historical_metrics(item)
        return result
    if isinstance(value, list):
        return [upgrade_historical_metrics(item) for item in value]
    return value


def find_all_entry(items: Any, key_name: str = "year") -> dict[str, Any]:
    if not isinstance(items, list):
        return {}
    for item in items:
        if isinstance(item, dict) and str(item.get(key_name)) == "all":
            return item
    return {}


def collect_summary_all_entries(metrics: Any) -> dict[str, Any]:
    if not isinstance(metrics, dict):
        metrics = {}
    return {
        "excess_all": find_all_entry(metrics.get("excess_returns")),
        "index_profit_monthly_all": find_all_entry(metrics.get("index_profit_monthly")),
        "start_profit_monthly_all": find_all_entry(metrics.get("start_profit_monthly")),
        "index_kama_all": find_all_entry(metrics.get("index_kama_ratio")),
        "start_kama_all": find_all_entry(metrics.get("start_kama_ratio")),
        "index_sortino_all": find_all_entry(metrics.get("index_sortino_ratio")),
        "start_sortino_all": find_all_entry(metrics.get("start_sortino_ratio")),
        "monthly_excess_percentage_all": find_all_entry(
            metrics.get("monthly_excess_return_percentage")
        ),
        "index_sharpe_all": (metrics.get("index_sharpe_ratios") or {}).get("all") or {},
        "start_sharpe_all": (metrics.get("start_sharpe_ratios") or {}).get("all") or {},
    }
