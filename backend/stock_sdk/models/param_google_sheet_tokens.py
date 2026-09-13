"""Generated request and entity models. Do not edit by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..model_base import SerializableModel

@dataclass
class t_param_google_sheet_tokens(SerializableModel):
    id: int | None = None
    name: str | None = None
    task_type: str | None = None
    token_file: str | None = None
    token_context: str | None = None
    task_usage_count: int | None = None
    current_in_use_count: int | None = None
    max_usage_count: int | None = None
    is_active: int | None = None
    last_used_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

__all__ = ['t_param_google_sheet_tokens']
