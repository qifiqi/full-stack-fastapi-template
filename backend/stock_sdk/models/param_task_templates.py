"""Generated request and entity models. Do not edit by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..model_base import SerializableModel

@dataclass
class t_param_task_templates(SerializableModel):
    id: int | None = None
    name: str | None = None
    description: str | None = None
    config: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

__all__ = ['t_param_task_templates']
