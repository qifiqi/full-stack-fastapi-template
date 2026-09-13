"""Generated request and entity models. Do not edit by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..model_base import SerializableModel

@dataclass
class t_param_scheduled_tasks(SerializableModel):
    id: int | None = None
    name: str | None = None
    description: str | None = None
    cron_expression: str | None = None
    task_type: str | None = None
    task_function: str | None = None
    task_params: str | None = None
    is_active: int | None = None
    last_run_time: str | None = None
    next_run_time: str | None = None
    run_count: int | None = None
    is_running: int | None = None
    running_instance_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

__all__ = ['t_param_scheduled_tasks']
