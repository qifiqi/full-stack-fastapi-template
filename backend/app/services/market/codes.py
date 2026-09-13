"""Stock market / code normalization helpers (ported from google_sheet_task)."""

from __future__ import annotations

import re
from typing import Any

MARKET_TYPE_ALIASES = {
    "cn": "cn",
    "a": "cn",
    "a股": "cn",
    "ashare": "cn",
    "china": "cn",
    "en": "en",
    "us": "en",
    "usa": "en",
    "美股": "en",
    "ca": "ca",
    "canada": "ca",
    "加拿大": "ca",
    "kr": "kr",
    "korea": "kr",
    "韩国": "kr",
    "jp": "jp",
    "japan": "jp",
    "日本": "jp",
    "hk": "hk",
    "hongkong": "hk",
    "hong kong": "hk",
    "香港": "hk",
    "港股": "hk",
    "uk": "uk",
    "gb": "uk",
    "london": "uk",
    "伦敦": "uk",
    "英股": "uk",
    "fr": "fr",
    "france": "fr",
    "法国": "fr",
    "de": "de",
    "germany": "de",
    "德国": "de",
    "sg": "sg",
    "singapore": "sg",
    "新加坡": "sg",
    "au": "au",
    "australia": "au",
    "澳洲": "au",
    "my": "my",
    "malaysia": "my",
    "马来西亚": "my",
    "futures": "futures",
    "期货": "futures",
    "fund": "fund",
    "基金": "fund",
    "场外基金": "fund",
}

STOCK_CODE_SUFFIXES = {
    "en": ".US",
    "ca": ".TO",
    "kr": ".KS",
    "jp": ".T",
    "hk": ".HK",
    "uk": ".L",
    "fr": ".PA",
    "de": ".DE",
    "sg": ".SI",
    "au": ".AX",
    "my": ".KL",
}

STANDARD_SUFFIX_MARKETS = {
    ".SS": "cn",
    ".SH": "cn",
    ".SZ": "cn",
    ".BJ": "cn",
    **{suffix.upper(): market for market, suffix in STOCK_CODE_SUFFIXES.items()},
}


def normalize_market_type(value: Any, default: str | None = None) -> str | None:
    text = str(value or "").strip().lower()
    return MARKET_TYPE_ALIASES.get(text, default)


def split_stock_code(stock_code: Any) -> tuple[str, str | None]:
    code = str(stock_code or "").strip().upper()
    if "." not in code:
        return code, None
    base, suffix = code.rsplit(".", 1)
    suffix = f".{suffix}"
    return (base, suffix) if suffix in STANDARD_SUFFIX_MARKETS else (code, None)


def infer_market_type(stock_code: Any, default: Any = None) -> str | None:
    _base, suffix = split_stock_code(stock_code)
    if suffix:
        return STANDARD_SUFFIX_MARKETS[suffix]
    return normalize_market_type(default) or (
        "cn" if str(stock_code or "").strip().isdigit() else "en"
    )


def strip_stock_code_suffix(stock_code: Any) -> str:
    return split_stock_code(stock_code)[0]


def exchange_market_from_stock_code(stock_code: Any, default: Any = None) -> str:
    _base, suffix = split_stock_code(stock_code)
    if suffix in {".SS", ".SH"}:
        return "1"
    if suffix in {".SZ", ".BJ"}:
        return "0"
    return str(default or "").strip()


def normalize_stock_code(
    stock_code: Any,
    market_type: Any,
    exchange_market: Any = None,
) -> str:
    """Unified security code format, e.g. 600519.SS / 0700.HK / AAPL.US."""
    original_code = str(stock_code or "").strip().upper()
    code, existing_suffix = split_stock_code(original_code)
    market = infer_market_type(stock_code, market_type)
    if not code or not market:
        return code
    if code == "UNKNOWN" or not re.fullmatch(r"[A-Z0-9-]+", code):
        return original_code
    if "." in original_code and existing_suffix is None:
        return original_code
    if market == "cn":
        exchange = str(exchange_market or "").strip()
        if existing_suffix in {".SS", ".SH"}:
            return f"{code}.SS"
        if existing_suffix in {".SZ", ".BJ"}:
            return f"{code}{existing_suffix}"
        if exchange == "1" or code.startswith(("5", "6")):
            return f"{code}.SS"
        if exchange == "0" or code.startswith(("0", "1", "2", "3")):
            return f"{code}.SZ"
        if code.startswith(("4", "8")):
            return f"{code}.BJ"
        return code
    if market == "hk":
        code = code.lstrip("0").zfill(4)
    suffix = STOCK_CODE_SUFFIXES.get(market)
    return f"{code}{suffix}" if suffix else code


def to_yahoo_ticker(
    stock_code: Any, market_type: Any, exchange_market: Any = None
) -> str:
    code = normalize_stock_code(stock_code, market_type, exchange_market)
    if infer_market_type(code, market_type) == "en" and code.endswith(".US"):
        return code[:-3]
    return code
