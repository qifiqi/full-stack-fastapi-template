"""Generated request and entity models. Do not edit by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..model_base import SerializableModel

@dataclass
class GetModelListRequestDto(SerializableModel):
    page_index: int | None = None
    page_size: int | None = None
    order_field: str | None = None
    order_type: str | None = None
    parent_model_name: str | None = None
    model_name: str | None = None

@dataclass
class sys_model(SerializableModel):
    model_id: int | None = None
    model_name: str | None = None
    model_code: str | None = None
    parent_model_id: int | None = None
    parent_model_name: str | None = None
    order_num: int | None = None
    model_type: ModelTypeEnum | None = None
    model_icon: str | None = None
    model_link: str | None = None
    create_time: str | None = None

__all__ = ['GetModelListRequestDto', 'sys_model']
