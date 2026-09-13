"""Generated request and entity models. Do not edit by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..model_base import SerializableModel

@dataclass
class IdRequestDto(SerializableModel):
    id: int | None = None

@dataclass
class RequsetPageDto(SerializableModel):
    page_index: int | None = None
    page_size: int | None = None
    order_field: str | None = None
    order_type: str | None = None

@dataclass
class t_param_backtest_product_result_cache(SerializableModel):
    id: int | None = None
    batch_id: str | None = None
    cache_key: str | None = None
    result_json: str | None = None
    returns_json: str | None = None
    source_task_id: str | None = None
    source_step_index: int | None = None
    created_at: str | None = None

__all__ = ['IdRequestDto', 'RequsetPageDto', 't_param_backtest_product_result_cache']
