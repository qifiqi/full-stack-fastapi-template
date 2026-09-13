"""Generated request and entity models. Do not edit by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..model_base import SerializableModel

@dataclass
class t_param_task_results(SerializableModel):
    id: int | None = None
    task_id: str | None = None
    step_index: int | None = None
    parameters: str | None = None
    result: str | None = None
    return_series_id: int | None = None
    success: int | None = None
    error_message: str | None = None
    timestamp: str | None = None

__all__ = ['t_param_task_results']
