"""Generated request and entity models. Do not edit by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..model_base import SerializableModel

@dataclass
class t_param_stock_metadata(SerializableModel):
    id: int | None = None
    stock_code: str | None = None
    stock_name: str | None = None
    market_type: str | None = None
    exchange_market: str | None = None
    security_type_name: str | None = None
    source: str | None = None
    raw_json: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

__all__ = ['t_param_stock_metadata']
