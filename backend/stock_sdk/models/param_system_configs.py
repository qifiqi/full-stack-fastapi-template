"""Generated request and entity models. Do not edit by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..model_base import SerializableModel

@dataclass
class t_param_system_configs(SerializableModel):
    id: int | None = None
    key: str | None = None
    value: str | None = None
    description: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

__all__ = ['t_param_system_configs']
