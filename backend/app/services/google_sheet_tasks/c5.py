"""C5 sheet-check engine (ported, condensed: param write -> snapshot -> poll)."""

from __future__ import annotations

from typing import Any

from app.services.google_sheet_tasks.base import BaseGoogleSheetService
from app.services.google_sheet_tasks.check_policy import (
    C5_INVALID,
    normalize_check_values,
)
from app.services.tasks.errors import SheetCheckError


class C5Service(BaseGoogleSheetService):
    def _task_type(self) -> str:
        return "google_sheet_c5"

    def _execute_parameter_combination(
        self, combination: Any, cache_parameters: dict[str, Any], cfg: dict[str, Any]
    ) -> tuple[bool, dict[str, Any]]:
        sheet = self.google_sheets[0]
        param_positions = cfg.get("c5_parameter_positions") or ["B1", "B2"]
        check_positions = cfg.get("c5_check_positions") or ["G1", "H1"]
        output_range_1 = cfg.get("c5_output_range_1", "X2:X20")
        output_range_2 = cfg.get("c5_output_range_2", "X22:X25")

        a1_value = combination[0] if len(combination) > 0 else ""
        b1_value = combination[1] if len(combination) > 1 else ""
        cell_updates = {
            param_positions[0]: f"xm:{a1_value}",
            param_positions[1]: f"ml:{b1_value}",
        }

        raw_previous = cache_parameters.get("combination")
        previous: dict[str, Any] = (
            raw_previous if isinstance(raw_previous, dict) else {}
        )
        (
            previous.get("kline_key") != cache_parameters.get("kline_key")
            or not cache_parameters
        )

        initial_results = sheet.get_range(output_range_1)
        sheet.update_jumped_cells(cell_updates)

        def _attempt(_attempt_number: int) -> tuple[bool, dict[str, Any]]:
            if check_positions:
                ranges = [output_range_1, ":".join(check_positions)]
                batch = sheet.get_ranges(ranges)
                check_values = batch.get(":".join(check_positions), {})
                try:
                    normalize_check_values(check_values, invalid_predicate=C5_INVALID)
                except Exception as exc:
                    self._log_info(f"检查位未就绪: {exc}")
                    return False, {}
                current = batch.get(output_range_1, {})
                keys = sorted(initial_results.keys())
                if (
                    keys
                    and current.get(keys[0]) == initial_results.get(keys[0])
                    and current.get(keys[1], "") == initial_results.get(keys[1], "")
                ):
                    return False, {}

            results = sheet.get_range(output_range_1)
            results.update(sheet.get_range(output_range_2))
            normalized_results = self._normalize_results(results)
            return True, normalized_results

        done, payload = self._poll_google_sheet_completion(_attempt)
        if not done:
            return False, {}
        return True, payload

    def _normalize_results(self, results: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for position, value in results.items():
            if str(value).strip().startswith(("#", "#N/A")):
                raise SheetCheckError(f"结果位 {position} 出现 #: {value}")
            if isinstance(value, str) and value == "-":
                continue
            normalized[position] = value
        return normalized

    def _result_parameters(
        self, combination: Any, cfg: dict[str, Any]
    ) -> dict[str, Any]:
        parameters = super()._result_parameters(combination, cfg)
        if isinstance(combination, tuple) and len(combination) >= 2:
            parameters["A1"] = combination[0]
            parameters["B1"] = combination[1]
        return parameters
