"""Backtest engines (task-registry entries; shared C-series execution loop).

The full source engines (backtest_training_service.py ~900 lines) depend on
the performance-analysis package; this port reuses the C5 execution skeleton
(kline write -> poll D-range -> save with hot columns) and is the designated
P6 joint-debugging point.
"""

from __future__ import annotations

from app.services.google_sheet_tasks.c5 import C5Service


class BacktestTrainingService(C5Service):
    def _task_type(self) -> str:
        return "backtest_training"


class BacktestMultiProductService(BacktestTrainingService):
    def _task_type(self) -> str:
        return "backtest_multi_product"
