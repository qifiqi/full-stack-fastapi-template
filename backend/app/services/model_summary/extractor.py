"""Summary-record extraction (golden-critical, ported from model_summary/extractor.py).

The old batch "summary index rebuild" becomes write-path extraction: the
engine calls :func:`extract_hot_columns_for_result` inside
``_save_task_result``; :func:`extract_summary_records` powers the backfill tool.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.services.google_sheet_tasks.layout import C3_METRIC_CELLS, C4_C5_METRIC_CELLS
from app.services.model_summary.historical_metrics import (
    find_all_entry as _all_entry,
)
from app.services.model_summary.historical_metrics import upgrade_historical_metrics

SUPPORTED_TASK_TYPES = (
    "google_sheet",
    "google_sheet_c4",
    "google_sheet_c5",
    "backtest_training",
)

SUMMARY_COLUMNS = [
    {"key": "return_rate", "label": "Return%", "format": "percent"},
    {"key": "annualized_rate", "label": "Annualized", "format": "percent"},
    {"key": "max_drawdown", "label": "Max DD%", "format": "percent"},
    {"key": "index_return", "label": "Index Return", "format": "percent"},
    {"key": "index_annualized_rate", "label": "Annualized", "format": "percent"},
    {"key": "index_max_drawdown", "label": "Index max dd", "format": "percent"},
]

TASK_TYPE_LABELS = {
    "google_sheet": "C3",
    "google_sheet_c4": "C4",
    "google_sheet_c5": "C5",
    "backtest_training": "回测",
}


# -- parsing helpers ------------------------------------------------------------
def parse_lenient_json(raw: Any, default: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw) if raw else default
    except TypeError, json.JSONDecodeError:
        return default


def _parse_float(value: Any, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except TypeError, ValueError:
        return default
    if number != number or number in (float("inf"), float("-inf")):
        return default
    return number


def parse_percent_like(value: Any, *, default: float | None = None) -> float | None:
    """Parse a number or percent string; '5%' -> 0.05."""
    if value in (None, "") or isinstance(value, bool):
        return default
    text = str(value).strip().replace(",", "").replace("$", "")
    if not text or text == "-":
        return default
    if text.endswith("%"):
        number = _parse_float(text[:-1], default=default)
        return number / 100 if number is not None else default
    return _parse_float(text, default=default)


_safe_number = parse_percent_like
_parse_json = parse_lenient_json


# -- record model ------------------------------------------------------------------
@dataclass(frozen=True)
class SummaryRecord:
    task_id: int
    task_result_id: int
    task_type: str
    task_name: str
    stock_code: str
    stock_name: str
    model_key: str
    model_name: str
    year_label: str
    period_key: str
    kline_range: str
    parameter_summary: dict[str, Any]
    best_metric_name: str
    best_metric_value: float | None
    metrics: dict[str, Any]
    result_timestamp: datetime | None


# -- small pure helpers -------------------------------------------------------------
def _kline_range(parameters: Any) -> str:
    kline = None
    if isinstance(parameters, dict):
        kline = parameters.get("kline")
    elif isinstance(parameters, list) and parameters:
        kline = parameters[-1]
    if isinstance(kline, list) and kline:
        first, last = kline[0], kline[-1]
        first_date = first.get("stock_date") if isinstance(first, dict) else None
        last_date = last.get("stock_date") if isinstance(last, dict) else None
        if first_date and last_date:
            return f"{first_date} ~ {last_date}"
    return ""


def _normalize_year_number(value: Any) -> int | None:
    try:
        number = int(str(value))
    except TypeError, ValueError:
        return None
    if number < 100:
        number += 2000
    return number


def _period_key_from_year_label(value: Any) -> str:
    text = str(value or "").strip()
    years = re.findall(r"\d{2,4}", text)
    if len(years) >= 2:
        first, last = (_normalize_year_number(y) for y in years[:2])
        if first is not None and last is not None:
            return f"recent_{last - first + 1}y"
    year = _normalize_year_number(years[0]) if years else None
    return f"full_{year}" if year else ""


def _period_key_from_year_n(value: Any) -> str:
    match = re.fullmatch(r"([0-9]+)y", str(value or "").strip().lower())
    return f"recent_{match.group(1)}y" if match else ""


def _period_key_for_record(
    task_config: dict[str, Any],
    parameters: Any,
    year_label: str,
    task_name: str = "",
) -> str:
    if year_label:
        key = _period_key_from_year_label(year_label)
        if key:
            return key
    if isinstance(parameters, dict):
        year_n = parameters.get("year_n")
    else:
        year_n = (task_config or {}).get("year_n")
    key = _period_key_from_year_n(year_n)
    if key:
        return key
    match = re.search(r"([0-9]+y)", str(task_name or ""))
    return _period_key_from_year_n(match.group(1)) if match else ""


def _summary_record_group_key(record: SummaryRecord) -> str:
    return record.period_key or record.year_label or record.kline_range


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _parameter_summary(parameters: Any) -> dict[str, Any]:
    if isinstance(parameters, dict):
        keys = ("stock_code", "task_name", "year", "A1", "B1", "parameter")
        return {k: parameters[k] for k in keys if k in parameters}
    if isinstance(parameters, list):
        return {"parameter": parameters[:-1] if len(parameters) > 1 else parameters}
    return {"parameter": parameters}


def _first_text_value(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _display_model_name(raw_name: str, task_type: str) -> str:
    lowered = raw_name.lower()
    if "c5" in lowered or task_type == "google_sheet_c5":
        return "C5"
    if "c4" in lowered or task_type == "google_sheet_c4":
        return "C4"
    return raw_name


def _strip_brackets(value: str) -> str:
    text = str(value or "")
    pattern = re.compile(r"[()\[\]（）【】]")
    while True:
        new_text = pattern.sub("", text)
        if new_text == text:
            break
        text = new_text
    return re.sub(r"\s+", " ", text).strip()


def _stock_code_from_task_name(task_type: str, task_name: str) -> str:
    clean = _strip_brackets(task_name)
    segments = [seg for seg in clean.split("-") if seg]
    if len(segments) >= 2 and task_type.lower().startswith(("c", "google_sheet")):
        candidate = segments[1].strip()
        if candidate.isdigit():
            return candidate
    if segments:
        candidate = segments[0].strip()
        if candidate.isdigit():
            return candidate
        return candidate.upper()
    return ""


def _extract_stock_code(
    task_type: str,
    task_config: dict[str, Any],
    parameters: Any,
    task_name: str,
    task_id: int | None = None,
) -> str:
    from app.services.market.codes import infer_market_type, normalize_stock_code

    market_type = (task_config or {}).get("market_type")

    def standardize(code: str) -> str:
        return normalize_stock_code(code, market_type or infer_market_type(code))

    if isinstance(parameters, dict):
        for key in ("stock_code", "stock_no", "code", "symbol"):
            value = parameters.get(key)
            if value not in (None, ""):
                return standardize(str(value))
        for key in ("task_name", "name", "base_task_name", "taskName"):
            value = parameters.get(key)
            if value not in (None, ""):
                code = _stock_code_from_task_name(task_type, str(value))
                if code:
                    return standardize(code)
    code = _stock_code_from_task_name(task_type, task_name)
    if code:
        return standardize(code)
    direct = (task_config or {}).get("stock_code")
    if direct not in (None, ""):
        return standardize(str(direct))
    return str(task_id or "").strip().upper()


def _extract_stock_name(parameters: Any) -> str:
    if isinstance(parameters, dict):
        return _first_text_value(parameters, ("stock_name", "name_cn", "product_name"))
    return ""


# -- metric extraction ------------------------------------------------------------
def _extract_return_analysis_metrics(payload: dict[str, Any]) -> dict[str, float]:
    flat_result = payload.get("flat_result")
    if isinstance(flat_result, dict):
        payload = {**payload, **flat_result}

    payload = upgrade_historical_metrics(payload)

    field_map = {
        "start_monthly_std_dev": "start_monthly_std_dev",
        "index_monthly_std_dev": "index_monthly_std_dev",
        "start_annualized_return": "start_annualized_return",
        "index_annualized_return": "index_annualized_return",
        "start_profit_annual": "start_profit_annual",
        "index_profit_annual": "index_profit_annual",
        "start_profit_monthly_percentage": "start_profit_monthly_percentage",
        "index_profit_monthly_percentage": "index_profit_monthly_percentage",
        "start_avg_monthly_return_common": "start_avg_monthly_return_common",
        "index_avg_monthly_return_common": "index_avg_monthly_return_common",
        "start_monthly_return_volatility": "start_monthly_return_volatility",
        "index_monthly_return_volatility": "index_monthly_return_volatility",
        "annualized_return_diff": "annualized_return_diff",
        "outperform_year": "outperform_year",
        "monthly_excess_return_percentage": "monthly_excess_return_percentage_last_return",
        "avg_monthly_excess_returns": "avg_monthly_excess_returns",
        "monthly_excess_volatility": "monthly_excess_volatility",
        "max_drawdown_analysis": "max_drawdown",
        "excess_drawdown_winning_rate": "excess_drawdown_winning_rate",
        "start_drawdown": "start_drawdown",
        "start_maximum_number_of_backtest_repair_days": "start_maximum_number_of_backtest_repair_days",
        "excess_maximum_number_of_backtest_repair_days": "excess_maximum_number_of_backtest_repair_days",
        "start_sharpe_ratio": "start_sharpe_ratio",
        "index_sharpe_ratio": "index_sharpe_ratio",
        "start_kama_ratio": "start_kama_ratio",
        "index_kama_ratio": "index_kama_ratio",
        "start_sortino_ratio": "start_sortino_ratio",
        "index_sortino_ratio": "index_sortino_ratio",
        "excess_sharpe": "excess_sharpe",
        "excess_sortino": "excess_sortino",
    }
    metrics: dict[str, float] = {}
    for output_key, source_key in field_map.items():
        value = _safe_number(payload.get(source_key))
        if value is not None:
            metrics[output_key] = value
    return metrics


def _first_safe_number(*values: Any) -> float | None:
    for value in values:
        number = _safe_number(value)
        if number is not None:
            return number
    return None


def _extract_c3_core(
    task_type: str,
    task_name: str,
    task_config: dict[str, Any],
    parameters: Any,
    payload: dict[str, Any],
    task_id: int,
    result_id: int,
    result_timestamp: datetime | None,
) -> SummaryRecord:
    return_rate = _fmt_percent_like(payload.get("I15"))
    metrics = {
        key: _fmt_percent_like(payload.get(cell))
        for key, cell in C3_METRIC_CELLS.items()
    }
    index_return = metrics.get("index_return")
    return_beats = (
        round(return_rate - index_return, 12)
        if return_rate is not None and index_return is not None
        else None
    )
    metrics["return_beats"] = return_beats
    metrics.update(_extract_return_analysis_metrics(payload))
    summary = _parameter_summary(parameters)
    stock_code = _extract_stock_code(
        task_type, task_config, parameters, task_name, task_id
    )
    year_label = str(summary.get("year") or "")
    return SummaryRecord(
        task_id=task_id,
        task_result_id=result_id,
        task_type=task_type,
        task_name=task_name,
        stock_code=stock_code,
        stock_name=_extract_stock_name(parameters)
        or (task_config or {}).get("stock_name", ""),
        model_key="default",
        model_name="C3",
        year_label=year_label,
        period_key=_period_key_for_record(
            task_config, parameters, year_label, task_name
        ),
        kline_range=_kline_range(parameters),
        parameter_summary=summary,
        best_metric_name="ReturnBeats",
        best_metric_value=return_beats,
        metrics={key: value for key, value in metrics.items() if value is not None},
        result_timestamp=result_timestamp,
    )


def _fmt_percent_like(value: Any) -> float | None:
    return _safe_number(value)


def _extract_c3(
    task_type: str,
    task_name: str,
    task_config: dict[str, Any],
    parameters: Any,
    payload: dict[str, Any],
    task_id: int,
    result_id: int,
    result_timestamp: datetime | None,
) -> list[SummaryRecord]:
    if not isinstance(payload, dict):
        return []
    return [
        _extract_c3_core(
            task_type,
            task_name,
            task_config,
            parameters,
            payload,
            task_id,
            result_id,
            result_timestamp,
        )
    ]


def _extract_c4_c5(
    task_type: str,
    task_name: str,
    task_config: dict[str, Any],
    parameters: Any,
    payload: dict[str, Any],
    task_id: int,
    result_id: int,
    result_timestamp: datetime | None,
) -> list[SummaryRecord]:
    if not isinstance(payload, dict):
        return []

    records = []
    for model_key, raw_metrics in payload.items():
        if model_key == "flat_result" or not isinstance(raw_metrics, dict):
            continue

        return_beats = _safe_number(raw_metrics.get("D11"))
        if return_beats is None:
            left = _safe_number(raw_metrics.get("D2"))
            right = _safe_number(raw_metrics.get("D5"))
            return_beats = (
                left - right if left is not None and right is not None else None
            )

        key_parts = str(model_key).split("__")
        model_name = "__".join(key_parts[1:]) if len(key_parts) > 1 else str(model_key)
        model_name = _display_model_name(model_name, task_type)
        metrics = {
            key: _safe_number(raw_metrics.get(cell))
            for key, cell in C4_C5_METRIC_CELLS.items()
        }
        metrics.update({"return_beats": return_beats})
        metrics.update(_extract_return_analysis_metrics(raw_metrics))
        summary = _parameter_summary(parameters)
        stock_code = _extract_stock_code(
            task_type, task_config, parameters, task_name, task_id
        )
        year_label = str(summary.get("year") or "")
        records.append(
            SummaryRecord(
                task_id=task_id,
                task_result_id=result_id,
                task_type=task_type,
                task_name=task_name,
                stock_code=stock_code,
                stock_name=_extract_stock_name(parameters)
                or (task_config or {}).get("stock_name", ""),
                model_key=str(model_key),
                model_name=model_name,
                year_label=year_label,
                period_key=_period_key_for_record(
                    task_config, parameters, year_label, task_name
                ),
                kline_range=_kline_range(parameters),
                parameter_summary=summary,
                best_metric_name="ReturnBeats",
                best_metric_value=return_beats,
                metrics={
                    key: value for key, value in metrics.items() if value is not None
                },
                result_timestamp=result_timestamp,
            )
        )
    return records


def _extract_backtest(
    task_type: str,
    task_name: str,
    task_config: dict[str, Any],
    parameters: Any,
    payload: dict[str, Any],
    task_id: int,
    result_id: int,
    result_timestamp: datetime | None,
) -> list[SummaryRecord]:
    if not isinstance(payload, dict):
        return []
    core = None
    for value in payload.values():
        if isinstance(value, dict):
            core = value
            break
    metrics_payload = (
        (core or {}).get("metrics_payload") if isinstance(core, dict) else None
    )
    calculate_metrics = (
        metrics_payload.get("metrics")
        if isinstance(metrics_payload, dict)
        else (core or {}).get("calculate_metrics")
    )
    calculate_metrics = calculate_metrics if isinstance(calculate_metrics, dict) else {}
    calculate_metrics = upgrade_historical_metrics(calculate_metrics)
    if not calculate_metrics:
        return []

    excess_all = _all_entry(calculate_metrics.get("excess_returns"))
    annualized_diff = _safe_number(excess_all.get("annualized_return_diff"))
    start_annualized = _safe_number(excess_all.get("start_annualized_return"))
    year_label = str(
        (parameters or {}).get("year") if isinstance(parameters, dict) else ""
    )
    stock_code = _extract_stock_code(
        task_type, task_config, parameters, task_name, task_id
    )
    return [
        SummaryRecord(
            task_id=task_id,
            task_result_id=result_id,
            task_type=task_type,
            task_name=task_name,
            stock_code=stock_code,
            stock_name=_extract_stock_name(parameters)
            or (task_config or {}).get("stock_name", ""),
            model_key="default",
            model_name="回测",
            year_label=year_label,
            period_key=_period_key_for_record(
                task_config, parameters, year_label, task_name
            ),
            kline_range=str(excess_all.get("start_end_date") or ""),
            parameter_summary=_parameter_summary(parameters),
            best_metric_name="年化超额收益",
            best_metric_value=annualized_diff,
            metrics={
                "absolute_annualized_return": start_annualized,
                "relative_annualized_excess_return": annualized_diff,
                "outperform_year": _safe_number(
                    calculate_metrics.get("outperform_year")
                ),
                "excess_sharpe": _safe_number(calculate_metrics.get("excess_sharpe")),
                "excess_sortino": _safe_number(calculate_metrics.get("excess_sortino")),
            },
            result_timestamp=result_timestamp,
        )
    ]


def extract_summary_records(
    task_type: str,
    task_name: str,
    task_config: dict[str, Any],
    parameters: Any,
    result_payload: Any,
    *,
    task_id: int = 0,
    result_id: int = 0,
    result_timestamp: datetime | None = None,
    success: bool = True,
) -> list[SummaryRecord]:
    if not success:
        return []
    normalized = (task_type or "").strip().lower()
    if normalized == "google_sheet":
        return _extract_c3(
            normalized,
            task_name,
            task_config,
            parameters,
            result_payload,
            task_id,
            result_id,
            result_timestamp,
        )
    if normalized in {"google_sheet_c4", "google_sheet_c5"}:
        return _extract_c4_c5(
            normalized,
            task_name,
            task_config,
            parameters,
            result_payload,
            task_id,
            result_id,
            result_timestamp,
        )
    if normalized == "backtest_training":
        return _extract_backtest(
            normalized,
            task_name,
            task_config,
            parameters,
            result_payload,
            task_id,
            result_id,
            result_timestamp,
        )
    return []


# -- write-path hot columns ----------------------------------------------------------
def extract_hot_columns_for_result(
    *,
    task_type: str,
    task_name: str,
    task_config: dict[str, Any],
    parameters: Any,
    result: Any,
) -> dict[str, Any]:
    """Hot columns for one task_result row (write-time extraction).

    ``is_best`` is determined by the caller against current DB best state.
    """
    parameters = _parse_json(parameters, {})
    result = _parse_json(result, {})
    records = extract_summary_records(
        task_type,
        task_name,
        task_config or {},
        parameters,
        result,
    )
    hot: dict[str, Any] = {
        "stock_code": None,
        "stock_name": None,
        "model_key": "default",
        "model_name": None,
        "period_key": None,
        "year_label": None,
        "kline_range": None,
        "best_metric_name": None,
        "best_metric_value": None,
        "is_best": False,
    }
    if not records:
        if isinstance(parameters, dict) and parameters.get("stock_code"):
            from app.services.market.codes import normalize_stock_code

            hot["stock_code"] = normalize_stock_code(
                parameters["stock_code"], (task_config or {}).get("market_type")
            )
            hot["stock_name"] = parameters.get("stock_name")
        return hot

    # Prefer the record with the highest best_metric_value inside this row payload.
    best = max(
        records,
        key=lambda r: (r.best_metric_value is not None, r.best_metric_value or 0),
    )
    hot.update(
        {
            "stock_code": best.stock_code or None,
            "stock_name": best.stock_name or None,
            "model_key": best.model_key or "default",
            "model_name": best.model_name or None,
            "period_key": best.period_key or None,
            "year_label": best.year_label or None,
            "kline_range": best.kline_range or None,
            "best_metric_name": best.best_metric_name,
            "best_metric_value": best.best_metric_value,
        }
    )
    return hot
