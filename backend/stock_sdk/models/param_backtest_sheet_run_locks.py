"""Generated request and entity models. Do not edit by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..model_base import SerializableModel

@dataclass
class t_param_backtest_sheet_run_locks(SerializableModel):
    id: int | None = None
    spreadsheet_id: str | None = None
    task_id: str | None = None
    task_type: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

__all__ = ['t_param_backtest_sheet_run_locks']
