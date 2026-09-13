"""Generated request and entity models. Do not edit by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..model_base import SerializableModel

@dataclass
class GetSysRoleListRequestDto(SerializableModel):
    page_index: int | None = None
    page_size: int | None = None
    order_field: str | None = None
    order_type: str | None = None
    role_name: str | None = None

@dataclass
class IsRoleRequestDto(SerializableModel):
    model_name: str | None = None

@dataclass
class sys_role(SerializableModel):
    role_id: int | None = None
    role_name: str | None = None
    role_remark: str | None = None
    model_ids: str | None = None
    role_code: str | None = None
    role_type: int | None = None
    create_time: str | None = None
    role_grade: int | None = None

__all__ = ['GetSysRoleListRequestDto', 'IsRoleRequestDto', 'sys_role']
