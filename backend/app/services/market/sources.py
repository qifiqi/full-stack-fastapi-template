"""Market data source registry with lazy imports (Python 3.14 wheel risk).

akshare / yfinance are imported lazily; if unavailable the affected source is
skipped and the core Sheet-check chain keeps working (stock_sdk / dfcf / qq).
All HTTP calls use constant endpoint literals with ``params=`` dictionaries.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from app.services.market.codes import (
    infer_market_type,
    normalize_market_type,
    strip_stock_code_suffix,
)
from app.services.market.kline_adjustment import (
    eastmoney_fqt,
    sina_adjust,
    yahoo_adjust_flags,
)

logger = logging.getLogger(__name__)

DATA_SOURCE_DFCF = "dfcf"
DATA_SOURCE_QQ = "qq"
DATA_SOURCE_YAHOO = "yahoo"
DATA_SOURCE_TDX = "tdx"
DATA_SOURCE_DATABASE = "database"
DATA_SOURCE_AKSHARE = "akshare"
VALID_DATA_SOURCES = {
    DATA_SOURCE_DFCF,
    DATA_SOURCE_QQ,
    DATA_SOURCE_YAHOO,
    DATA_SOURCE_TDX,
    DATA_SOURCE_DATABASE,
    DATA_SOURCE_AKSHARE,
}

_KLINE_PRICE_FIELD_BY_MODE = {
    "kp_price": "open",
    "sp_price": "close",
    "vwap_price": "vwap",
    "ohlc_price": "close",
}
DEFAULT_KLINE_PRICE_FIELD = "vwap"

_EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
_EASTMONEY_SEARCH_URL = "https://searchadapter.eastmoney.com/api/suggest/get"
_QQ_FQKLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"


def get_kline_price_field(price_mode: str) -> str:
    return _KLINE_PRICE_FIELD_BY_MODE.get(price_mode or "", DEFAULT_KLINE_PRICE_FIELD)


class DFCJStockApi:
    """Eastmoney kline client (condensed port: session + retries + fqt)."""

    def __init__(self) -> None:
        self._session: requests.Session | None = None

    def _get_session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(
                {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
            )
        return self._session

    def get_stock_kline_data(
        self,
        stock_code: str,
        stock_type: str = "",
        limit: int = 100,
        kline_type: str = "101",
        adjust_type: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        from tenacity import (
            retry,
            retry_if_result,
            stop_after_attempt,
            wait_exponential,
        )

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(min=1, max=8),
            retry=retry_if_result(lambda rows: not rows),
            reraise=True,
        )
        def _fetch() -> list[dict[str, Any]]:
            session = self._get_session()
            response = session.get(
                _EASTMONEY_KLINE_URL,
                params={
                    "secid": f"{stock_type or '1'}.{stock_code}",
                    "klt": kline_type,
                    "fqt": eastmoney_fqt(adjust_type),
                    "lmt": str(max(limit, 1)),
                    "end": "20500101",
                    "fields1": "f1,f2,f3,f4,f5,f6",
                    "fields2": "f51,f52,f53,f54,f55,f56,f57",
                },
                timeout=15,
                allow_redirects=False,
            )
            response.raise_for_status()
            data = response.json().get("data") or {}
            klines = data.get("klines") or []
            rows: list[dict[str, Any]] = []
            for line in klines:
                parts = line.split(",")
                if len(parts) < 7:
                    continue
                try:
                    rows.append(
                        {
                            "stock_date": parts[0],
                            "open": float(parts[1]),
                            "close": float(parts[2]),
                            "high": float(parts[3]),
                            "low": float(parts[4]),
                            "volume": float(parts[5]),
                            "amount": float(parts[6]),
                            "stock_code": stock_code,
                            "data_source": DATA_SOURCE_DFCF,
                        }
                    )
                except ValueError:
                    continue
            return rows

        return _fetch()

    def get_search_list_by_stock_code(
        self, keyword: str, page_size: int = 20
    ) -> list[dict[str, Any]]:
        session = self._get_session()
        try:
            response = session.get(
                _EASTMONEY_SEARCH_URL,
                params={
                    "input": keyword,
                    "type": "14",
                    "token": "D43BF722C8E33BDC906FB84D85E326E8",
                    "count": str(page_size),
                },
                timeout=10,
                allow_redirects=False,
            )
            response.raise_for_status()
            items = (
                (response.json().get("QuotationCodeTable") or {}).get("Data")
            ) or []
            return [item for item in items if isinstance(item, dict)]
        except Exception:
            return []


class QQStockApi:
    """Tencent kline client (condensed port with fixed throttling)."""

    MIN_REQUEST_INTERVAL = 0.5

    def __init__(self) -> None:
        self._last_request_time = 0.0

    def _throttle(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.monotonic()

    @staticmethod
    def resolve_market_prefix(
        exchange: str, stock_code: str, market_type: str | None = None
    ) -> str:
        normalized = normalize_market_type(market_type) or infer_market_type(
            stock_code, "cn"
        )
        if normalized == "hk":
            return "hk"
        if normalized == "us":
            return "us"
        if str(exchange) == "1":
            return "sh"
        return "sz"

    def get_stock_kline_data(
        self,
        stock_code: str,
        exchange: str,
        limit: int = 640,
        kline_type: str = "101",
        adjust_type: str = "1",
        market_type: str | None = None,
    ) -> list[dict[str, Any]]:
        prefix = self.resolve_market_prefix(exchange, stock_code, market_type)
        symbol = f"{prefix}{strip_stock_code_suffix(stock_code)}"
        rows: list[dict[str, Any]] = []
        for _page in range(5):
            self._throttle()
            response = requests.get(
                _QQ_FQKLINE_URL,
                params={
                    "param": f"{symbol},day,,,320,{adjust_type}",
                    "_var": "kline_dayqfq",
                },
                timeout=15,
                allow_redirects=False,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
            payload = response.json().get("data") or {}
            stock_data = payload.get(symbol) or {}
            klines = stock_data.get("qfqday") or stock_data.get("day") or []
            if not klines:
                break
            for item in klines:
                if not isinstance(item, list) or len(item) < 6:
                    continue
                try:
                    rows.append(
                        {
                            "stock_date": item[0],
                            "open": float(item[1]),
                            "close": float(item[2]),
                            "high": float(item[3]),
                            "low": float(item[4]),
                            "volume": float(item[5]),
                            "stock_code": stock_code,
                            "data_source": DATA_SOURCE_QQ,
                        }
                    )
                except TypeError, ValueError:
                    continue
            if len(rows) >= limit:
                break
        return rows[:limit]


class AkshareApi:
    """Sina-backed A/HK/fund klines with a 0.5s throttle; akshare imports lazily."""

    MIN_REQUEST_INTERVAL = 0.5

    def __init__(self) -> None:
        self._ak: Any = None
        self._last_request_time = 0.0

    def _get_ak(self) -> Any:
        if self._ak is None:
            import akshare as ak  # type: ignore[import-untyped]

            self._ak = ak
        return self._ak

    def _throttle(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.monotonic()

    def get_stock_kline_data(
        self,
        stock_code: str,
        exchange: str = "",
        limit: int = 100,
        adjust_type: str | None = None,
        market_type: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        ak = self._get_ak()
        normalized_market = normalize_market_type(market_type) or infer_market_type(
            stock_code, "cn"
        )
        symbol = strip_stock_code_suffix(stock_code)
        adjust = sina_adjust(adjust_type)
        self._throttle()
        try:
            if normalized_market == "hk":
                raw = ak.stock_hk_daily(symbol=symbol, adjust=adjust or "")
            elif normalized_market == "fund":
                raw = ak.fund_etf_hist_sina(symbol=symbol)
            else:
                raw = ak.stock_zh_a_daily(
                    symbol=symbol,
                    adjust=adjust or "",
                    start_date=(start_date or "").replace("-", ""),
                    end_date=(end_date or "").replace("-", ""),
                )
        except Exception as exc:
            logger.warning("akshare 拉取失败 (%s): %s", stock_code, exc)
            return []

        rows: list[dict[str, Any]] = []
        for _, row in raw.iterrows():
            rows.append(
                {
                    "stock_date": str(row.get("date"))[:10],
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "close": row.get("close"),
                    "volume": row.get("volume"),
                    "stock_code": stock_code,
                    "data_source": DATA_SOURCE_AKSHARE,
                }
            )
        return rows[-limit:] if limit else rows


class YFApi:
    """Yahoo Finance klines (US/BTC); yfinance imports lazily."""

    def get_kline_data(
        self,
        stock_code: str = "BTC",
        period: str = "max",
        interval: str = "1d",
        adjust_type: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            import yfinance as yf  # type: ignore[import-untyped]
        except Exception as exc:
            logger.warning("yfinance 不可用，跳过 yahoo 源: %s", exc)
            return []

        flags = yahoo_adjust_flags(adjust_type)
        ticker = yf.Ticker(stock_code)
        raw = ticker.history(period=period, interval=interval, **flags)
        rows: list[dict[str, Any]] = []
        for index, row in raw.iterrows():
            rows.append(
                {
                    "stock_date": str(index)[:10],
                    "open": row.get("Open"),
                    "high": row.get("High"),
                    "low": row.get("Low"),
                    "close": row.get("Close"),
                    "volume": row.get("Volume"),
                    "stock_code": stock_code,
                    "data_source": DATA_SOURCE_YAHOO,
                }
            )
        return rows
