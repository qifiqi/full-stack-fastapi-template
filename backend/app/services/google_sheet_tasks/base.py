"""Base Google Sheet task engine (ported from google_sheet_tasks/base.py).

The Flask ``app=`` injection is replaced by an injected ``session_factory`` +
``settings``; the runner signature is
``(config, task_id, *, session_factory, settings, stop_event)``.
``_save_task_result`` now writes hot columns, flips ``is_best`` and inserts
``return_series_point`` rows in the same transaction (02 §2.3/§2.4).
"""

from __future__ import annotations

import logging
import math
import threading
import time
from datetime import date as _date
from datetime import datetime
from typing import Any

from sqlmodel import Session, col, select

from app.models import (
    ReturnSeriesPoint,
    Task,
    TaskResult,
    TaskResultCreate,
)
from app.services.google_sheet.client import GoogleSheet
from app.services.tasks.errors import (
    NETWORK_ERROR_PREFIX,
    SheetCheckError,
    record_task_exception,
)
from app.services.tasks.logs import add_task_log
from app.services.tasks.return_series import (
    build_return_series_points,
    extract_return_rows,
)

DEFAULT_EXECUTION_DELAY_MIN = 20
DEFAULT_EXECUTION_DELAY_MAX = 30

_POLL_MAX_ATTEMPTS = 60


def should_alert_execute_task_result(result: str) -> bool:
    return result == "error"


def _shift_date_months(date_str: str, months: int) -> str:
    year, month, day = (int(p) for p in date_str.split("-"))
    total = year * 12 + (month - 1) + months
    new_year, new_month = divmod(total, 12)
    return f"{new_year:04d}-{new_month + 1:02d}-{day:02d}"


def _sanitize_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _sanitize_json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_json_value(item) for item in value]
    if isinstance(value, (datetime, _date)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        import numpy as _np

        if isinstance(value, _np.integer):
            return int(value)
        if isinstance(value, _np.floating):
            value = float(value)
            return value if math.isfinite(value) else None
        if isinstance(value, _np.ndarray):
            return _sanitize_json_value(value.tolist())
    except ImportError:
        pass
    return value


def _prepare_result_for_persistence(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = {
        k: v
        for k, v in payload.items()
        if k not in {"_return_date", "return_date", "returns_json"}
    }
    return cleaned


class BaseGoogleSheetService:
    """Task engine base: execute loop, polling, persistence."""

    def __init__(
        self,
        config: dict[str, Any],
        task_id: int,
        *,
        session_factory: Any,
        settings: Any,
        stop_event: threading.Event | None = None,
    ) -> None:
        self.config = config
        self.task_id = task_id
        self.session_factory = session_factory
        self.settings = settings
        self.stop_event = stop_event
        self.task_name = ""
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{task_id}")
        self.google_sheets: list[GoogleSheet] = []
        self._return_date_cache: dict[tuple[str, int], dict[str, Any]] = {}

    # -- logging ------------------------------------------------------------
    def _log(self, level: str, message: str) -> None:
        prefix = f"[Task-{self.task_id}] "
        text = f"{prefix}{message}"
        if level == "info":
            self.logger.info(text)
        elif level == "warning":
            self.logger.warning(text)
        else:
            self.logger.error(text)
        try:
            with self.session_factory() as session:
                add_task_log(session, self.task_id, level.upper(), message)
        except Exception:
            pass

    def _log_info(self, message: str) -> None:
        self._log("info", message)

    def _log_warning(self, message: str) -> None:
        self._log("warning", message)

    def _log_error(self, message: str) -> None:
        self._log("error", message)

    def _log_step(self, step: int, total: int, message: str) -> None:
        self._log_info(f"[Step {step}/{total}] {message}")

    # -- cancellation ---------------------------------------------------------
    def _is_cancel_requested(self) -> bool:
        if self.stop_event is not None and self.stop_event.is_set():
            return True
        try:
            with self.session_factory() as session:
                task = session.get(Task, self.task_id)
                return bool(task and task.status == "cancelled")
        except Exception:
            return False

    def _interruptible_sleep(self, seconds: int) -> bool:
        """Sleep that can be interrupted; False means cancellation requested."""
        if self.stop_event is not None:
            if not self.stop_event.wait(seconds):
                return True
            return False
        time.sleep(seconds)
        return not self._is_cancel_requested()

    # -- config ---------------------------------------------------------------
    def _get_execution_poll_delay_bounds(self) -> tuple[int, int]:
        from app.services.config_manager import try_get_config_manager

        manager = try_get_config_manager()
        try:
            delay_min = DEFAULT_EXECUTION_DELAY_MIN
            delay_max = DEFAULT_EXECUTION_DELAY_MAX
            if manager is not None:
                delay_min = int(manager.get_config("execution_delay_min", delay_min))
                delay_max = int(manager.get_config("execution_delay_max", delay_max))
        except (TypeError, ValueError) as exc:
            self._log_warning(f"执行等待配置无效，使用默认值 20-30 秒: {exc}")
            return DEFAULT_EXECUTION_DELAY_MIN, DEFAULT_EXECUTION_DELAY_MAX
        if delay_min < 0 or delay_max < 0 or delay_min > delay_max:
            return DEFAULT_EXECUTION_DELAY_MIN, DEFAULT_EXECUTION_DELAY_MAX
        return delay_min, delay_max

    @staticmethod
    def _get_execution_poll_delay(attempt: int, delay_min: int, delay_max: int) -> int:
        return int(min(delay_min + max(attempt, 0) * 5, delay_max))

    def _merged_config(self) -> dict[str, Any]:
        from app.services.config_manager import try_get_config_manager

        manager = try_get_config_manager()
        base = manager.get_google_sheet_config() if manager is not None else {}
        return {**base, **self.config}

    # -- polling ---------------------------------------------------------------
    def _poll_google_sheet_completion(
        self,
        attempt_fn: Any,
        refresh_fn: Any = None,
        post_attempt_fn: Any = None,
        timeout_payload: tuple[bool, dict[str, Any]] = (False, {}),
    ) -> tuple[bool, dict[str, Any]]:
        delay_min, delay_max = self._get_execution_poll_delay_bounds()
        for attempt in range(_POLL_MAX_ATTEMPTS):
            if (
                refresh_fn is not None
                and attempt != 0
                and (attempt % 10 == 0 or attempt in [5, 15, 25, 35])
            ):
                self._log_info("刷新参数")
                refresh_fn(20)
            delay = self._get_execution_poll_delay(attempt, delay_min, delay_max)
            self._log_info(f"第 {attempt + 1} 次检查执行状态... delay {delay} 秒")
            if not self._interruptible_sleep(delay):
                raise RuntimeError("task cancelled")
            done, payload = attempt_fn(attempt)
            if done:
                return True, payload
            if post_attempt_fn is not None and attempt in [5, 15, 25, 35]:
                post_attempt_fn(attempt)
        self._log_warning("执行超时，未在规定时间内完成")
        return timeout_payload

    # -- sheet connections -------------------------------------------------------
    def _build_client(
        self, cfg: dict[str, Any], sheet_cfg: dict[str, Any]
    ) -> GoogleSheet:
        from app.services.config_manager import try_get_config_manager

        manager = try_get_config_manager()
        token_file = (
            manager.resolve_google_token_path(cfg.get("token_file"))
            if manager
            else cfg.get("token_file", "data/token.json")
        )
        return GoogleSheet(
            sheet_cfg.get("spreadsheet_id") or cfg.get("spreadsheet_id", ""),
            sheet_name=sheet_cfg.get("sheet_name") or cfg.get("sheet_name"),
            token_file=token_file,
            proxy_url=cfg.get("proxy_url"),
            task_id=self.task_id,
        )

    def _init_google_sheets(self, cfg: dict[str, Any]) -> list[GoogleSheet]:
        sheets_value = cfg.get("sheets")
        sheet_cfgs: list[dict[str, Any]] = (
            list(sheets_value)
            if isinstance(sheets_value, list) and sheets_value
            else [{}]
        )
        self.google_sheets = [
            self._build_client(cfg, sheet_cfg) for sheet_cfg in sheet_cfgs
        ]
        if not self.google_sheets:
            raise Exception("请先选择工作表")
        return self.google_sheets

    # -- execution ----------------------------------------------------------------
    def execute_task(self) -> str:
        """Template method: returns 'completed' | 'cancelled' | 'error'."""
        try:
            cfg = self._merged_config()
            task = self._load_task()
            if task is None:
                return "error"
            if task.status == "cancelled":
                return "cancelled"
            self._log_info("开始执行Google Sheet任务")
            self._init_google_sheets(cfg)

            parameters = cfg.get("parameters", [])
            if not parameters:
                self._log_error("任务参数为空")
                return "error"
            self.task_name = task.name

            success_count, failed_count, task_status = self.get_bdl(
                task, task.name, parameters, cfg
            )
            if task_status == "cancelled":
                return "cancelled"
            if task_status == "error":
                return "error"
            if success_count == 0 and failed_count == 0:
                return "error"
            self._notify_completion(success_count, failed_count)
            return "completed"
        except Exception as exc:
            if self._is_cancel_requested() or (
                isinstance(exc, RuntimeError) and "cancelled" in str(exc)
            ):
                return "cancelled"
            self._record_execution_error(exc, "execute_task")
            return "error"

    def get_bdl(
        self, task: Task, name: str, parameters: list[Any], cfg: dict[str, Any]
    ) -> tuple[int, int, str]:
        """Default combination loop (C4/C5/C7 shape)."""
        total_combinations = 1
        for param_list in parameters:
            total_combinations *= len(param_list)
        self._update_task_steps(total_combinations)

        start_index = self._get_resume_start_index(
            task.current_step or 0, total_combinations
        )
        success_count = start_index
        failed_count = 0
        combinations = self._expand_parameters(parameters)

        self._clear_input_columns(cfg)

        cache_parameters: dict[str, Any] = {}
        for index in range(start_index, total_combinations):
            if self._is_cancel_requested():
                return success_count, 0, "cancelled"
            current_step = index + 1
            self._log_step(current_step, total_combinations, "开始处理参数组合")
            combination = combinations[index]
            try:
                success, result = self._execute_parameter_combination(
                    combination, cache_parameters, cfg
                )
            except SheetCheckError as exc:
                self._log_error(f"模板检查错误: {exc}")
                return success_count, failed_count + 1, "error"
            except RuntimeError as exc:
                if "cancelled" in str(exc):
                    return success_count, 0, "cancelled"
                raise
            except Exception as exc:
                if self._is_cancel_requested():
                    return success_count, 0, "cancelled"
                self._log_error(f"参数组合执行失败: {exc}")
                return success_count, failed_count + 1, "error"

            if not success:
                return success_count, failed_count + 1, "error"

            success_count += 1
            cache_parameters["combination"] = combination
            self._update_task_progress(current_step)
            self._save_task_result(
                index,
                self._result_parameters(combination, cfg),
                result,
                True,
            )
        return success_count, 0, "completed"

    def _result_parameters(
        self, combination: Any, cfg: dict[str, Any]
    ) -> dict[str, Any]:
        parameters = {
            "stock_code": cfg.get("stock_code"),
            "stock_name": cfg.get("stock_name"),
            "market_type": cfg.get("market_type"),
        }
        if isinstance(combination, dict):
            parameters.update({k: v for k, v in combination.items() if k != "kline"})
        elif isinstance(combination, (list, tuple)):
            parameters["parameter"] = list(combination)
        kline = (
            cfg.get("kline") or (combination or {}).get("kline")
            if isinstance(combination, dict)
            else cfg.get("kline")
        )
        if kline:
            parameters["kline"] = kline
        return parameters

    def _expand_parameters(self, parameters: list[Any]) -> list[Any]:
        from itertools import product

        return list(product(*parameters))

    def _get_resume_start_index(self, current_step: int, total: int) -> int:
        return max(0, min(current_step, total))

    def _clear_input_columns(self, cfg: dict[str, Any]) -> None:
        """Holding-space before writes; subclasses override per layout."""
        return None

    def _execute_parameter_combination(
        self, combination: Any, cache_parameters: dict[str, Any], cfg: dict[str, Any]
    ) -> tuple[bool, dict[str, Any]]:
        raise NotImplementedError

    # -- progress ------------------------------------------------------------------
    def _load_task(self) -> Task | None:
        with self.session_factory() as session:
            task: Task | None = session.get(Task, self.task_id)
            return task

    def _update_task_steps(self, total_steps: int) -> None:
        with self.session_factory() as session:
            task = session.get(Task, self.task_id)
            if task is not None:
                task.total_steps = total_steps
                session.add(task)
                session.commit()

    def _update_task_progress(self, current_step: int) -> None:
        with self.session_factory() as session:
            task = session.get(Task, self.task_id)
            if task is not None:
                task.current_step = current_step
                session.add(task)
                session.commit()

    # -- persistence ---------------------------------------------------------------
    def _save_task_result(
        self,
        step_index: int,
        parameters: dict[str, Any],
        result: dict[str, Any],
        success: bool,
        return_date: list[dict[str, Any]] | None = None,
    ) -> TaskResult:
        """Persist one result: hot columns + is_best flip + return series rows.

        Parsing failures raise here instead of silently degrading (02 §4 #9).
        """
        safe_parameters = _sanitize_json_value(parameters)
        safe_result = _sanitize_json_value(
            _prepare_result_for_persistence(dict(result or {}))
        )
        return_rows = (
            return_date if return_date is not None else extract_return_rows(result)
        )

        hot = self._extract_hot_columns(safe_parameters, safe_result)

        with self.session_factory() as session:
            task_result = TaskResult.model_validate(
                TaskResultCreate(
                    task_id=self.task_id,
                    step_index=step_index,
                    success=success,
                    params=safe_parameters,
                    result=safe_result,
                    result_timestamp=datetime.now(),
                    **hot,
                )
            )

            # is_best: new value beats the current stored best for this
            # (task_id, stock_code, model_key) group? MySQL 5.7-safe: no window
            # functions, plain indexed lookup (idx_result_task_best).
            best_value = hot.get("best_metric_value")
            is_best = False
            if best_value is not None:
                current_best = session.exec(
                    select(TaskResult)
                    .where(
                        TaskResult.task_id == self.task_id,
                        TaskResult.stock_code == hot.get("stock_code"),
                        TaskResult.model_key == (hot.get("model_key") or "default"),
                        col(TaskResult.is_best) == True,  # noqa: E712
                    )
                    .limit(1)
                ).first()
                if current_best is None or current_best.best_metric_value is None:
                    is_best = True
                elif best_value > current_best.best_metric_value:
                    is_best = True
            task_result.is_best = is_best
            session.add(task_result)
            session.flush()

            if is_best:
                self._demote_other_best_rows(session, int(task_result.id or 0), hot)

            if return_rows:
                points = build_return_series_points(
                    return_rows, task_result_id=int(task_result.id or 0)
                )
                for point in points:
                    session.add(ReturnSeriesPoint.model_validate(point))
                if return_date is not None and not points:
                    raise ValueError("收益序列缺少有效日期")

            session.commit()
            session.refresh(task_result)
            return task_result

    def _extract_hot_columns(
        self, parameters: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any]:
        """Delegate to the model_summary extractor (single source of truth)."""
        from app.services.model_summary.extractor import extract_hot_columns_for_result

        return extract_hot_columns_for_result(
            task_type=self._task_type(),
            task_name=self.task_name,
            task_config=self.config,
            parameters=parameters,
            result=result,
        )

    def _task_type(self) -> str:
        return "google_sheet"

    def _demote_other_best_rows(
        self, session: Session, new_result_id: int, hot: dict[str, Any]
    ) -> None:
        """Flip off previous best rows in the same (task, stock, model) group."""
        statement = select(TaskResult).where(
            TaskResult.task_id == self.task_id,
            TaskResult.id != new_result_id,
            col(TaskResult.is_best) == True,  # noqa: E712
            TaskResult.stock_code == hot.get("stock_code"),
            TaskResult.model_key == (hot.get("model_key") or "default"),
        )
        for old in session.exec(statement).all():
            old.is_best = False
            session.add(old)

    def _record_execution_error(self, exc: BaseException, phase: str) -> None:
        record_task_exception(
            self.task_id,
            exc,
            phase,
            session_factory=self.session_factory,
        )
        self._log_error(
            f"{NETWORK_ERROR_PREFIX if False else ''}{phase} 执行失败: {exc}"
        )

    # -- completion notification -----------------------------------------------------
    def _notify_completion(self, success_count: int, failed_count: int) -> None:
        try:
            from app.services.notify.dingtalk import send_task_notification

            send_task_notification(
                task_id=self.task_id,
                task_name=self.task_name,
                notify_type="success" if not failed_count else "error",
                summary=f"成功: {success_count}, 失败: {failed_count}",
            )
        except Exception:
            self._log_warning("钉钉通知发送失败（忽略）")

    # -- utility ------------------------------------------------------------------------
    @staticmethod
    def get_worksheets(
        spreadsheet_id: str, token_file: str, proxy_url: str | None
    ) -> dict[str, Any]:
        client = GoogleSheet(spreadsheet_id, token_file=token_file, proxy_url=proxy_url)
        try:
            return {
                "title": client.title or "",
                "worksheets": client.get_all_worksheets(),
            }
        finally:
            client.close()
