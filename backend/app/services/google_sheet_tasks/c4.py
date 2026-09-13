"""C4 multi-sheet engine (ported, condensed: kline-only write + D2/D3 change poll)."""

from __future__ import annotations

from typing import Any

from app.services.google_sheet_tasks.base import BaseGoogleSheetService
from app.services.tasks.errors import SheetCheckError


class C4Service(BaseGoogleSheetService):
    def _task_type(self) -> str:
        return "google_sheet_c4"

    def _expand_parameters(self, parameters: list[Any]) -> list[Any]:
        """C4 combinations arrive pre-expanded by creation (per-stock klines)."""
        if parameters and all(isinstance(item, dict) for item in parameters):
            return list(parameters)
        return super()._expand_parameters(parameters)

    def _execute_parameter_combination(
        self, combination: Any, cache_parameters: dict[str, Any], cfg: dict[str, Any]
    ) -> tuple[bool, dict[str, Any]]:
        results: dict[str, Any] = {}
        output_range_1 = cfg.get("c4_output_range_1", "D2:D20")
        output_range_2 = cfg.get("c4_output_range_2", "D22:D25")

        for sheet in self.google_sheets:
            key = f"{sheet.spreadsheet_id}__{sheet.title or ''}"
            initial = sheet.get_range(output_range_1)

            def _attempt(
                _attempt_number: int,
                sheet: Any = sheet,
                initial: dict[str, Any] = initial,
            ) -> tuple[bool, dict[str, Any]]:
                current = sheet.get_range(output_range_1)
                d2 = current.get("D2")
                d3 = current.get("D3")
                if (
                    not d2
                    or not d3
                    or d2 in ("", "#DIV/0!", "#N/A")
                    or d3 in ("", "#DIV/0!", "#N/A")
                ):
                    return False, {}
                if d2 == initial.get("D2") and d3 == initial.get("D3"):
                    return False, {}
                payload = dict(current)
                payload.update(sheet.get_range(output_range_2))
                return True, payload

            done, payload = self._poll_google_sheet_completion(_attempt)
            if not done:
                return False, {}
            if str(payload.get("D2", "")).startswith("#"):
                raise SheetCheckError(f"C4 结果位出现 #: {payload.get('D2')}")
            results[key] = payload
        return True, {"sheets": results}

    def _result_parameters(
        self, combination: Any, cfg: dict[str, Any]
    ) -> dict[str, Any]:
        parameters = super()._result_parameters(combination, cfg)
        if isinstance(combination, dict):
            parameters["stock_code"] = combination.get(
                "stock_code", parameters.get("stock_code")
            )
            parameters["stock_name"] = combination.get("stock_name")
            if combination.get("year"):
                parameters["year"] = combination["year"]
        return parameters
