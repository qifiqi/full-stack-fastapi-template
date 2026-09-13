"""K-line adjustment normalization (ported from kline_adjustment.py)."""

from __future__ import annotations

from typing import Any

KLINE_ADJUSTMENT_FORWARD = "forward"
KLINE_ADJUSTMENT_BACK = "back"
KLINE_ADJUSTMENT_NONE = "none"
DEFAULT_KLINE_ADJUSTMENT = KLINE_ADJUSTMENT_FORWARD

_ALIASES = {
    "forward": "forward",
    "qfq": "forward",
    "前复权": "forward",
    "1": "forward",
    "back": "back",
    "hfq": "back",
    "后复权": "back",
    "2": "back",
    "none": "none",
    "": "none",
    "不复权": "none",
    "0": "none",
}


def normalize_kline_adjustment(
    value: Any, default: str = DEFAULT_KLINE_ADJUSTMENT
) -> str:
    text = str(value or "").strip().lower()
    return _ALIASES.get(text, default)


def eastmoney_fqt(value: Any) -> str:
    normalized = normalize_kline_adjustment(value)
    return {"forward": "1", "back": "2", "none": "0"}[normalized]


def sina_adjust(value: Any, default: str = "") -> str:
    normalized = normalize_kline_adjustment(value, "none")
    return {"forward": "qfq", "back": "hfq", "none": default}[normalized]


def yahoo_adjust_flags(value: Any) -> dict[str, bool]:
    normalized = normalize_kline_adjustment(value)
    return {
        "auto_adjust": normalized == "forward",
        "back_adjusted": normalized == "back",
    }
