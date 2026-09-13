"""Generated request and entity models. Do not edit by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..model_base import SerializableModel

@dataclass
class GetListHisPageRequestDto(SerializableModel):
    stock_date: str | None = None

@dataclass
class GetStockDataAllListRequestDto(SerializableModel):
    begin_date: str | None = None
    stock_code: str | None = None

@dataclass
class GetStockDataListPageRequestDto(SerializableModel):
    page_index: int | None = None
    page_size: int | None = None
    order_field: str | None = None
    order_type: str | None = None
    stock_code: str | None = None
    min_coefficient: float | None = None
    max_coefficient: float | None = None
    stock_concept: str | None = None
    stock_lelvel: int | None = None

@dataclass
class GetStockDataListRequestDto(SerializableModel):
    page_index: int | None = None
    page_size: int | None = None
    order_field: str | None = None
    order_type: str | None = None
    stock_concept: str | None = None
    stock_industry: str | None = None
    stock_area: str | None = None
    begin_date: str | None = None
    end_time: str | None = None
    stock_hs300: int | None = None
    stock_code: str | None = None

@dataclass
class GetStockDataRequestDto(SerializableModel):
    page_index: int | None = None
    page_size: int | None = None
    order_field: str | None = None
    order_type: str | None = None
    stock_industry: str | None = None
    stock_concept: str | None = None
    stock_area: str | None = None
    stock_pe_ratio_where: str | None = None
    stock_pe_ratio: float | None = None
    stock_hs300: int | None = None
    day_max_volume: int | None = None
    max_volume_coefficient: float | None = None
    where_max_count: str | None = None
    day_current_volume: int | None = None
    coefficient: float | None = None
    his_day_max_volume: int | None = None
    stock_lelvel: int | None = None
    stock_code: str | None = None
    appentWhereType: int | None = None

@dataclass
class GetStockListByCodeRequestDto(SerializableModel):
    stock_code: str | None = None
    begin_date: str | None = None
    end_time: str | None = None

@dataclass
class t_stock_data(SerializableModel):
    id: int | None = None
    stock_code: str | None = None
    stock_name: str | None = None
    stock_open: float | None = None
    stock_max: float | None = None
    stock_min: float | None = None
    stock_close: float | None = None
    stock_close_y: float | None = None
    stock_limit: float | None = None
    stock_limit_price: float | None = None
    stock_volume: float | None = None
    stock_volume_price: float | None = None
    stock_amp: float | None = None
    stock_ratio: float | None = None
    stock_turnrate: float | None = None
    stock_pe_ratio: float | None = None
    stock_pb_ratio: float | None = None
    stock_market_cap: float | None = None
    stock_inflow: float | None = None
    stock_date: str | None = None
    createtime: str | None = None
    stock_concept: str | None = None
    stock_industry: str | None = None
    stock_area: str | None = None
    stock_max_volume: float | None = None
    stock_avg_price: float | None = None
    stock_avg_price_90: float | None = None
    stock_avg_price_70: float | None = None
    stock_lelvel: int | None = None
    double_time: str | None = None
    stock_macd_day_date: str | None = None
    stock_macd_month_date: str | None = None
    stock_limit_count: int | None = None
    stock_hs300: int | None = None
    stock_macd_state: int | None = None
    stock_dea: float | None = None
    stock_wr6: float | None = None
    stock_wr10: float | None = None
    stock_boll_mid: float | None = None
    stock_mavol5: float | None = None
    stock_ma60: float | None = None
    stock_sixmonth_vol: float | None = None
    stock_oneyear_vol: float | None = None

__all__ = ['GetListHisPageRequestDto', 'GetStockDataAllListRequestDto', 'GetStockDataListPageRequestDto', 'GetStockDataListRequestDto', 'GetStockDataRequestDto', 'GetStockListByCodeRequestDto', 't_stock_data']
