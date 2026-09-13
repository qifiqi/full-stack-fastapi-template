"""Performance-analysis streaming engine (functional V1 port).

Computes core return-series metrics (annualized return/volatility, max
drawdown, Sharpe/Sortino, monthly stats) from a strategy vs index return
series and emits NDJSON streams, mirroring the source project's wire protocol
(one ``json.dumps`` line + ``\\n`` per record). The full 13-file source
package (text analysis, portfolio combiner, sheets reader) lands later; the
endpoint contracts below are final.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReturnSeries:
    dates: list[str]
    start_returns: list[float]
    index_returns: list[float]


def parse_series(payload: dict[str, Any]) -> ReturnSeries:
    dates = [str(d) for d in payload.get("dates") or []]
    start_returns = [
        float(v) for v in (payload.get("start_returns") or []) if v is not None
    ]
    index_returns = [
        float(v) for v in (payload.get("index_returns") or []) if v is not None
    ]
    n = min(len(dates), len(start_returns), len(index_returns))
    return ReturnSeries(dates[:n], start_returns[:n], index_returns[:n])


def _max_drawdown(returns: list[float]) -> float:
    nav = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in returns:
        nav *= 1.0 + r
        peak = max(peak, nav)
        if peak > 0:
            max_dd = min(max_dd, nav / peak - 1.0)
    return max_dd


def _annualized_return(returns: list[float]) -> float | None:
    if not returns:
        return None
    nav = 1.0
    for r in returns:
        nav *= 1.0 + r
    years = len(returns) / 252.0
    if nav <= 0 or years <= 0:
        return None
    return float(nav ** (1.0 / years) - 1.0)


def _std(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance)


def analyze_series(series: ReturnSeries) -> dict[str, Any]:
    start, index = series.start_returns, series.index_returns

    def _safe(value: float | None) -> float | None:
        return None if value is None or not math.isfinite(value) else value

    start_ann = _annualized_return(start)
    index_ann = _annualized_return(index)
    start_std, index_std = _std(start), _std(index)
    start_mean = sum(start) / len(start) if start else None
    index_mean = sum(index) / len(index) if index else None
    rf = 0.0
    excess = [r - rf for r in start]
    downside = [r for r in excess if r < 0]
    downside_std = _std(downside) if len(downside) >= 2 else None

    monthly_groups: dict[str, list[float]] = {}
    for date_label, r in zip(series.dates, start, strict=False):
        monthly_groups.setdefault(date_label[:7], []).append(r)
    monthly_returns = []
    for _month, rs in monthly_groups.items():
        nav = 1.0
        for r in rs:
            nav *= 1.0 + r
        monthly_returns.append(nav - 1.0)

    flat: dict[str, Any] = {
        "start_annualized_return": _safe(start_ann),
        "index_annualized_return": _safe(index_ann),
        "annualized_return_diff": _safe(
            start_ann - index_ann
            if start_ann is not None and index_ann is not None
            else None
        ),
        "start_monthly_std_dev": _safe(start_std),
        "index_monthly_std_dev": _safe(index_std),
        "start_max_drawdown": _safe(_max_drawdown(start)),
        "index_max_drawdown": _safe(_max_drawdown(index)),
        "start_sharpe_ratio": _safe(
            (start_mean - rf) / start_std * math.sqrt(252)
            if start_mean is not None and start_std
            else None
        ),
        "index_sharpe_ratio": _safe(
            (index_mean - rf) / index_std * math.sqrt(252)
            if index_mean is not None and index_std
            else None
        ),
        "start_sortino_ratio": _safe(
            (start_mean - rf) / downside_std * math.sqrt(252)
            if start_mean is not None and downside_std
            else None
        ),
        "excess_sharpe": None,
        "excess_sortino": None,
        "monthly_returns": monthly_returns,
    }
    flat["excess_sharpe"] = (
        flat["start_sharpe_ratio"] - flat["index_sharpe_ratio"]
        if flat["start_sharpe_ratio"] is not None
        and flat["index_sharpe_ratio"] is not None
        else None
    )
    return flat


def ndjson_lines(payload: dict[str, Any]) -> Iterator[str]:
    """Yield NDJSON chunks: metrics first, then per-day rows."""
    series = parse_series(payload)
    flat = analyze_series(series)
    yield (
        json.dumps({"type": "metrics", **flat}, ensure_ascii=False, default=str) + "\n"
    )
    for date_label, s_ret, i_ret in zip(
        series.dates, series.start_returns, series.index_returns, strict=True
    ):
        row = {
            "type": "row",
            "date": date_label,
            "start_return": s_ret,
            "index_return": i_ret,
        }
        yield json.dumps(row, ensure_ascii=False, default=str) + "\n"


def weight_combination_lines(payload: dict[str, Any]) -> Iterator[str]:
    """Yield weighted-series rows in chunks (up to ~100k combos)."""
    series = parse_series(payload)
    weights = payload.get("weight_grid") or [0.0, 0.25, 0.5, 0.75, 1.0]
    yield (
        json.dumps(
            {"type": "meta", "rows": len(weights), "dates": len(series.dates)},
            ensure_ascii=False,
        )
        + "\n"
    )
    for weight in weights:
        blended = [
            (weight * s + (1.0 - weight) * i)
            for s, i in zip(series.start_returns, series.index_returns, strict=True)
        ]
        ann = _annualized_return(blended)
        dd = _max_drawdown(blended)
        row = {
            "type": "combination",
            "weight": weight,
            "annualized_return": ann,
            "max_drawdown": dd,
        }
        yield json.dumps(row, ensure_ascii=False, default=str) + "\n"
