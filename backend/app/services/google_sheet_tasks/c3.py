"""C3 sheet-check engine (ported from google_sheet_tasks/c3.py, condensed)."""

from __future__ import annotations

from typing import Any

from app.services.google_sheet_tasks.base import BaseGoogleSheetService
from app.services.google_sheet_tasks.check_policy import is_valid_result_value
from app.services.tasks.errors import SheetCheckError

_INVALID_RESULT_TOKENS = (
    "#DIV/0!",
    "",
    "#N/A",
    "#ERROR!",
    "#VALUE!",
    "#REF!",
    "#NAME?",
    "#NUM!",
)

_NONE_VALUES = (
    None,
    "",
    " ",
    "#N/A",
    "#DIV/0!",
    "#ERROR!",
    "#VALUE!",
    "#REF!",
    "#NAME?",
    "#NUM!",
)


class C3Service(BaseGoogleSheetService):
    def _task_type(self) -> str:
        return "google_sheet"

    def get_bdl(
        self, task: Any, name: str, parameters: list[Any], cfg: dict[str, Any]
    ) -> tuple[int, int, str]:
        total_combinations = 1
        for param_list in parameters or []:
            total_combinations *= len(param_list)
        self._update_task_steps(total_combinations)

        start_index = (
            max(0, min((task.current_step or 1) - 1, total_combinations - 1))
            if task.current_step
            else 0
        )
        success_count = start_index
        combinations = self._expand_parameters(parameters)

        sheet = self.google_sheets[0]
        param_positions = cfg.get("parameter_positions") or []
        check_positions = cfg.get("check_positions") or []
        result_positions: dict[str, Any] = dict(cfg.get("result_positions") or {})

        for index in range(start_index, total_combinations):
            if self._is_cancel_requested():
                return success_count, 0, "cancelled"
            current_step = index + 1
            self._log_step(current_step, total_combinations, "开始处理参数组合")
            combination = combinations[index]

            try:
                success, result = self._execute_c3_combination(
                    sheet,
                    combination,
                    param_positions,
                    check_positions,
                    result_positions,
                    cfg,
                )
            except SheetCheckError as exc:
                self._log_error(f"模板检查错误: {exc}")
                return success_count, 1, "error"
            except RuntimeError as exc:
                if "cancelled" in str(exc):
                    return success_count, 0, "cancelled"
                raise
            except Exception as exc:
                if self._is_cancel_requested():
                    return success_count, 0, "cancelled"
                self._log_error(f"参数组合执行失败: {exc}")
                return success_count, 1, "error"

            if not success:
                return success_count, 1, "error"

            success_count += 1
            cfg["kline"] = cfg.get("kline")
            self._update_task_progress(current_step)
            self._save_task_result(
                index, self._result_parameters(combination, cfg), result, True
            )
        return success_count, 0, "completed"

    def _execute_c3_combination(
        self,
        sheet: Any,
        combination: tuple[Any, ...],
        param_positions: list[str],
        check_positions: dict[str, Any] | list[str],
        result_positions: dict[str, Any],
        cfg: dict[str, Any],
    ) -> tuple[bool, dict[str, Any]]:
        cell_updates = {
            position: value
            for position, value in zip(param_positions, combination, strict=False)
            if position
        }
        sheet.update_jumped_cells(cell_updates)

        delay_min, delay_max = self._get_execution_poll_delay_bounds()
        batch_error_count = 0
        max_batch_error_count = 3

        for attempt in range(60):
            if attempt != 0 and (attempt % 10 == 0 or attempt in [3, 5, 8]):
                self._log_info(f"第 {attempt + 1} 次检查执行状态前，刷新表格")
                sheet.update_jumped_cells(cell_updates)
            delay = self._get_execution_poll_delay(attempt, delay_min, delay_max)
            self._log_info(f"第 {attempt + 1} 次检查执行状态... delay {delay} 秒")
            if not self._interruptible_sleep(delay):
                raise RuntimeError("task cancelled")

            if check_positions:
                try:
                    check_values = sheet.get_cells_batch(list(check_positions))
                    if not self._validate_check_values(check_values, cfg):
                        continue
                except Exception as exc:
                    self._log_warning(f"检查位读取失败: {exc}")
                    continue

            try:
                results = sheet.get_cells_batch(list(result_positions))
                if self._results_ready(results):
                    return True, self._finalize_result_values(results, cfg)
                continue
            except SheetCheckError:
                raise
            except Exception as exc:
                batch_error_count += 1
                self._log_warning(f"结果位读取失败: {exc}")
                if batch_error_count > max_batch_error_count:
                    fallback = {}
                    for position in result_positions:
                        try:
                            fallback[position] = sheet.get_cell(position)
                        except Exception:
                            fallback[position] = None
                    if self._results_ready(fallback):
                        return True, self._finalize_result_values(fallback, cfg)
                    return False, {}

        self._log_warning("执行超时，未在规定时间内完成")
        return False, {}

    def _validate_check_values(
        self, check_values: dict[str, Any], cfg: dict[str, Any]
    ) -> bool:
        if not check_values:
            return False
        for _position, value in check_values.items():
            if not value or value in _INVALID_RESULT_TOKENS:
                return False
            if "target" in str(value).lower():
                return False
        return True

    def _results_ready(self, results: dict[str, Any]) -> bool:
        if not results:
            return False
        return all(
            value not in _NONE_VALUES and is_valid_result_value(value)
            for value in results.values()
        )

    def _normalize_result_value(self, position: str, value: Any) -> float:
        if not value or not is_valid_result_value(value):
            self._log_info(f"结果位置 {position} 值为空或无效，跳过重新检查")
            raise Exception(f"结果位置 {position} 值为空或无效，跳过重新检查")
        raw_value = str(value).strip()
        if raw_value.startswith(("#", "#N/A")):
            raise SheetCheckError(
                f"检查报错，出现#|#N/A 这种异常错误，联系用户检查 位置 {position}: {value}"
            )
        if "%" in raw_value:
            return round(float(raw_value.replace("%", "").replace(",", "")) / 100, 5)
        if isinstance(value, str):
            return round(float(raw_value.replace(",", "")), 5)
        return round(float(value), 5)

    def _finalize_result_values(
        self, results: dict[str, Any], cfg: dict[str, Any]
    ) -> dict[str, Any]:
        finalized: dict[str, Any] = {}
        for position, value in results.items():
            finalized[position] = self._normalize_result_value(position, value)
        return finalized
