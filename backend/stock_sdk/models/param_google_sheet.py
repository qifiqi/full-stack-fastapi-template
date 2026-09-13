"""Generated request and entity models. Do not edit by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..model_base import SerializableModel

@dataclass
class t_param_google_sheet(SerializableModel):
    id: int | None = None
    name: str | None = None
    spreadsheet_id: str | None = None
    table_type: str | None = None
    registry_scope: str | None = None
    remark: str | None = None
    is_active: int | None = None
    is_in_use: int | None = None
    current_task_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

__all__ = ['t_param_google_sheet']
