"""Generated request and entity models. Do not edit by hand."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..model_base import SerializableModel

@dataclass
class t_param_task_result_summary_index(SerializableModel):
    id: int | None = None
    task_id: str | None = None
    task_result_id: int | None = None
    task_type: str | None = None
    task_name: str | None = None
    stock_code: str | None = None
    stock_name: str | None = None
    market_type: str | None = None
    model_key: str | None = None
    model_name: str | None = None
    year_label: str | None = None
    period_key: str | None = None
    kline_range: str | None = None
    parameter_summary: str | None = None
    best_metric_name: str | None = None
    best_metric_value: float | None = None
    metrics_json: str | None = None
    is_best: int | None = None
    result_timestamp: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

__all__ = ['t_param_task_result_summary_index']
