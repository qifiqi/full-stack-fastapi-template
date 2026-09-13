"""C7 sheet-check engine (ported, condensed: 0.2/0.3 layout + xm/ml checks)."""

from __future__ import annotations

from typing import Any

from app.services.google_sheet_tasks.base import BaseGoogleSheetService
from app.services.google_sheet_tasks.check_policy import (
    C7_INVALID,
    normalize_check_values,
)
from app.services.google_sheet_tasks.layout import C7_ROW_SHIFT


def c7_model_version(sheet_cfg: dict[str, Any]) -> str:
    version = str(sheet_cfg.get("c7_model_version") or "c7_0_2").strip().lower()
    return version if version in {"c7_0_2", "c7_0_3"} else "c7_0_2"


class C7Service(BaseGoogleSheetService):
    def _task_type(self) -> str:
        return "google_sheet_c7"

    def _execute_parameter_combination(
        self, combination: Any, cache_parameters: dict[str, Any], cfg: dict[str, Any]
    ) -> tuple[bool, dict[str, Any]]:
        sheets_value = cfg.get("sheets")
        sheet_cfgs: list[dict[str, Any]] = (
            list(sheets_value)
            if isinstance(sheets_value, list) and sheets_value
            else [{}]
        )
        results: dict[str, Any] = {}

        for sheet, sheet_cfg in zip(self.google_sheets, sheet_cfgs, strict=False):
            version = c7_model_version(sheet_cfg)
            shift = 0 if version == "c7_0_3" else C7_ROW_SHIFT
            output_range_1 = sheet_cfg.get("c7_output_range_1") or (
                "D2:D20" if version == "c7_0_3" else f"D{2 + shift}:D{20 + shift}"
            )
            output_range_2 = sheet_cfg.get("c7_output_range_2") or (
                "D22:F25" if version == "c7_0_3" else f"D{22 + shift}:F{25 + shift}"
            )
            param_positions = sheet_cfg.get("c7_parameter_positions") or ["A1", "B1"]
            check_positions = sheet_cfg.get("c7_check_positions") or ["G1", "H1"]

            a1_value = combination[0] if len(combination) > 0 else ""
            b1_value = combination[1] if len(combination) > 1 else ""
            cell_updates = {
                param_positions[0]: f"xm:{a1_value}",
                param_positions[1]: f"ml:{b1_value}",
            }
            initial = sheet.get_range(output_range_1)
            sheet.update_jumped_cells(cell_updates)

            def _attempt(
                _attempt_number: int,
                sheet: Any = sheet,
                initial: dict[str, Any] = initial,
                check_positions: Any = check_positions,
                output_range_1: str = output_range_1,
                output_range_2: str = output_range_2,
                version: str = version,
            ) -> tuple[bool, dict[str, Any]]:
                if version != "c7_0_3" and check_positions:
                    check_values = sheet.get_cells_batch(list(check_positions))
                    try:
                        normalize_check_values(
                            check_values, invalid_predicate=C7_INVALID
                        )
                    except Exception as exc:
                        self._log_info(f"检查位未就绪: {exc}")
                        return False, {}

                current = sheet.get_range(output_range_1)
                keys = sorted(initial.keys())
                if keys and all(current.get(k) == initial.get(k) for k in keys[:2]):
                    return False, {}

                payload = dict(current)
                payload.update(sheet.get_range(output_range_2))
                return True, payload

            done, payload = self._poll_google_sheet_completion(_attempt)
            if not done:
                return False, {}
            results[f"{sheet.spreadsheet_id}__{sheet.title or ''}"] = payload
        return True, {
            "sheets": results,
            "c7_model_version": sheet_cfgs[0].get("c7_model_version", "c7_0_2"),
        }

    def _result_parameters(
        self, combination: Any, cfg: dict[str, Any]
    ) -> dict[str, Any]:
        parameters = super()._result_parameters(combination, cfg)
        if isinstance(combination, tuple) and len(combination) >= 2:
            parameters["A1"] = combination[0]
            parameters["B1"] = combination[1]
        return parameters
