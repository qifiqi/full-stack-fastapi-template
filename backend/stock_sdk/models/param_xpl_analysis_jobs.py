"""Generated request and entity models. Do not edit by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..model_base import SerializableModel

@dataclass
class t_param_xpl_analysis_jobs(SerializableModel):
    id: str | None = None
    task_id: str | None = None
    task_result_id: str | None = None
    return_series_id: str | None = None
    status: str | None = None
    attempts: str | None = None
    max_attempts: str | None = None
    locked_by: str | None = None
    locked_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

__all__ = ['t_param_xpl_analysis_jobs']
