"""K-line service: multi-source orchestration with fallback (condensed port)."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.services.market.codes import (
    exchange_market_from_stock_code,
    normalize_market_type,
    normalize_stock_code,
    strip_stock_code_suffix,
    to_yahoo_ticker,
)
from app.services.market.kline_adjustment import normalize_kline_adjustment
from app.services.market.sources import (
    DATA_SOURCE_AKSHARE,
    DATA_SOURCE_DFCF,
    DATA_SOURCE_QQ,
    DATA_SOURCE_YAHOO,
    VALID_DATA_SOURCES,
    AkshareApi,
    DFCJStockApi,
    QQStockApi,
    YFApi,
    get_kline_price_field,
)

logger = logging.getLogger(__name__)


def _resolve_stock_base_url() -> str | None:
    return settings.stock_base_url or None


class KlineService:
    """Fetch K-lines with multi-source fallback and price-row projection."""

    def __init__(
        self,
        dfcf_api: DFCJStockApi | None = None,
        qq_api: QQStockApi | None = None,
        yahoo_api: YFApi | None = None,
    ) -> None:
        self.dfcf_api = dfcf_api or DFCJStockApi()
        self.qq_api = qq_api or QQStockApi()
        self.yahoo_api = yahoo_api or YFApi()
        self.akshare_api: AkshareApi | None = None
        self.sources: dict[str, Any] = {
            DATA_SOURCE_DFCF: self.dfcf_api,
            DATA_SOURCE_QQ: self.qq_api,
            DATA_SOURCE_YAHOO: self.yahoo_api,
        }
        self.stock_base_url = _resolve_stock_base_url()

    def register_source(self, name: str, handler: Any) -> None:
        self.sources[name] = handler

    def _get_akshare_api(self) -> AkshareApi | None:
        """akshare is optional; failures degrade to dfcf/qq without breaking runs."""
        if self.akshare_api is None:
            try:
                self.akshare_api = AkshareApi()
                self.akshare_api._get_ak()  # noqa: SLF001 - warm the lazy import
            except Exception as exc:
                logger.warning("akshare 不可用，跳过该源: %s", exc)
                self.akshare_api = None
        return self.akshare_api

    @staticmethod
    def normalize_data_source(
        value: Any, available_sources: set[str] | None = None
    ) -> str:
        text = str(value or "").strip().lower()
        aliases = {
            "eastmoney": DATA_SOURCE_DFCF,
            "internal": "database",
            "db": "database",
        }
        text = aliases.get(text, text)
        valid = available_sources or VALID_DATA_SOURCES
        if text not in valid:
            raise ValueError(f"kline_data_source 仅支持 {'/'.join(sorted(valid))}")
        return text

    @staticmethod
    def get_stock_market(code: str) -> str:
        base = strip_stock_code_suffix(code)
        if base.startswith("6") or base.startswith("5"):
            return f"{base}.SH"
        if base.startswith(("0", "1", "2", "3")):
            return f"{base}.SZ"
        if base.startswith(("4", "8")):
            return f"{base}.BJ"
        return base

    def get_kline_data(
        self,
        stock_code: str,
        market_type: str = "cn",
        limit: int = 100,
        *,
        data_source: str = DATA_SOURCE_AKSHARE,
        start_date: str | None = None,
        end_date: str | None = None,
        adjust_type: str | None = None,
        exchange_market: str | None = None,
        stock_name: str | None = None,
    ) -> list[dict[str, Any]]:
        source = self.normalize_data_source(data_source)
        market = normalize_market_type(market_type, "cn") or "cn"
        normalized_code = normalize_stock_code(stock_code, market, exchange_market)
        base_code = strip_stock_code_suffix(normalized_code)
        exchange = exchange_market or exchange_market_from_stock_code(normalized_code)
        adjust = normalize_kline_adjustment(adjust_type, "none")

        request = {
            "stock_code": base_code,
            "market_type": market,
            "exchange_market": exchange,
            "limit": int(limit),
            "adjust_type": adjust,
            "start_date": start_date,
            "end_date": end_date,
            "stock_name": stock_name,
        }

        rows: list[dict[str, Any]] = []
        for candidate in self._fallback_chain(source, market):
            try:
                rows = self._fetch_from(candidate, request, normalized_code)
            except Exception as exc:
                logger.warning("行情源 %s 拉取失败: %s", candidate, exc)
                rows = []
            if rows:
                break

        rows = self._normalize_rows(rows, normalized_code, stock_name)
        return self._filter_rows_by_date_range(rows, start_date, end_date, limit)

    def _fallback_chain(self, source: str, market: str) -> list[str]:
        if source == DATA_SOURCE_AKSHARE and market not in {"cn", "hk", "fund"}:
            source = DATA_SOURCE_DFCF
        chain = [source]
        if source == "database":
            chain.append(DATA_SOURCE_DFCF)
        if market == "en":
            chain.extend([DATA_SOURCE_DFCF, DATA_SOURCE_YAHOO])
        else:
            chain.extend([DATA_SOURCE_DFCF, DATA_SOURCE_QQ])
        seen: list[str] = []
        for item in chain:
            if item not in seen:
                seen.append(item)
        return seen

    def _fetch_from(
        self, source: str, request: dict[str, Any], normalized_code: str
    ) -> list[dict[str, Any]]:
        if source == DATA_SOURCE_YAHOO:
            ticker = to_yahoo_ticker(normalized_code, request["market_type"])
            rows = self.yahoo_api.get_kline_data(
                stock_code=ticker, period="10y", adjust_type=request["adjust_type"]
            )
            return rows
        if source == DATA_SOURCE_QQ:
            return self.qq_api.get_stock_kline_data(
                request["stock_code"],
                request["exchange_market"],
                limit=request["limit"],
                adjust_type="1" if request["adjust_type"] == "forward" else "0",
                market_type=request["market_type"],
            )
        if source == DATA_SOURCE_AKSHARE:
            api = self._get_akshare_api()
            if api is None:
                return []
            akshare_rows: list[dict[str, Any]] = api.get_stock_kline_data(**request)
            return akshare_rows
        if source in self.sources and source != DATA_SOURCE_YAHOO:
            handler: Any = self.sources[source]
            if source == DATA_SOURCE_DFCF:
                dfcf_rows: list[dict[str, Any]] = handler.get_stock_kline_data(
                    request["stock_code"],
                    stock_type=request["exchange_market"] or "1",
                    limit=request["limit"],
                    adjust_type=request["adjust_type"],
                    start_date=request["start_date"],
                    end_date=request["end_date"],
                )
                return dfcf_rows
            handler_rows: list[dict[str, Any]] = handler.get_stock_kline_data(**request)
            return handler_rows
        return []

    @staticmethod
    def _normalize_rows(
        rows: list[dict[str, Any]], stock_code: str, stock_name: str | None
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for row in rows:
            try:
                open_price = float(row.get("open") or 0)
                close_price = float(row.get("close") or 0)
            except TypeError, ValueError:
                continue
            high = row.get("high")
            low = row.get("low")
            high_price = (
                float(high) if high is not None else max(open_price, close_price)
            )
            low_price = float(low) if low is not None else min(open_price, close_price)
            volume = row.get("volume")
            amount = row.get("amount")
            vwap = row.get("vwap")
            if vwap is None:
                try:
                    vwap = (
                        float(amount) / float(volume)
                        if amount is not None and volume
                        else close_price
                    )
                except TypeError, ZeroDivisionError, ValueError:
                    vwap = close_price
            normalized.append(
                {
                    "stock_date": str(row.get("stock_date"))[:10],
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,
                    "amount": amount,
                    "vwap": vwap,
                    "stock_code": row.get("stock_code") or stock_code,
                    "stock_name": row.get("stock_name") or stock_name,
                    "data_source": row.get("data_source"),
                }
            )
        normalized.sort(key=lambda r: r["stock_date"])
        return normalized

    @staticmethod
    def _filter_rows_by_date_range(
        rows: list[dict[str, Any]],
        start_date: str | None,
        end_date: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        if start_date or end_date:
            return [
                row
                for row in rows
                if (not start_date or row["stock_date"] >= start_date)
                and (not end_date or row["stock_date"] <= end_date)
            ]
        return rows[-limit:] if limit else rows

    @staticmethod
    def build_price_rows(
        klines: list[dict[str, Any]],
        price_mode: str,
        *,
        price_field: str | None = None,
        year: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        include_ohlc: bool = False,
        random_price_range: str | None = None,
        random_generator: Any = None,
    ) -> list[dict[str, Any]]:
        field = price_field or get_kline_price_field(price_mode)
        rows: list[dict[str, Any]] = []
        for kline in klines:
            stock_date = kline.get("stock_date")
            if not stock_date:
                continue
            if year is not None:
                if int(str(stock_date)[:4]) != int(year):
                    continue
            elif start_date and end_date:
                if not (start_date <= stock_date <= end_date):
                    continue
            entry: dict[str, Any] = {"stock_date": stock_date}
            if include_ohlc:
                entry.update(
                    {
                        "open": kline.get("open"),
                        "high": kline.get("high"),
                        "low": kline.get("low"),
                        "close": kline.get("close"),
                    }
                )
            else:
                value = kline.get(field)
                if random_price_range and random_generator is not None:
                    low_key, high_key = _random_price_range_fields(random_price_range)
                    low = kline.get(low_key)
                    high = kline.get(high_key)
                    value = random_generator.uniform(low, high)
                entry["stock_val"] = value
            rows.append(entry)
        return rows


def _random_price_range_fields(random_price_range: str) -> tuple[str, str]:
    mapping = {"high_low": ("low", "high"), "open_close": ("open", "close")}
    return mapping.get(random_price_range, ("low", "high"))
