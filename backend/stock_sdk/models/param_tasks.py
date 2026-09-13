"""Generated request and entity models. Do not edit by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..model_base import SerializableModel

@dataclass
class ParamStringIdRequestDto(SerializableModel):
    id: str | None = None

@dataclass
class t_param_tasks(SerializableModel):
    id: str | None = None
    name: str | None = None
    description: str | None = None
    status: str | None = None
    task_type: str | None = None
    config: str | None = None
    created_by_user_id: int | None = None
    start_time: str | None = None
    end_time: str | None = None
    current_step: int | None = None
    total_steps: int | None = None
    error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

__all__ = ['ParamStringIdRequestDto', 't_param_tasks']
