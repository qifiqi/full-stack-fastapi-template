"""Generated request and entity models. Do not edit by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..model_base import SerializableModel

@dataclass
class t_stock_data_us(SerializableModel):
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
    stock_limit_count: int | None = None

__all__ = ['t_stock_data_us']
