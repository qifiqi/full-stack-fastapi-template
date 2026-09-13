"""Task creation: config normalization, validation and batch expansion.

Ported from google_sheet_task task/creation.py; UUID ids become BIGINT and
config stays a plain dict (JSON column, no dumps/loads round trip).
"""

import json
from itertools import product
from typing import Any

from sqlmodel import Session

from app.crud import get_task
from app.models import Task, TaskCreate
from app.services.tasks.errors import BadRequestError, ValidationError

KLINE_SOURCE_AUTO = "auto"
KLINE_SOURCE_CUSTOM = "custom"
VALID_KLINE_SOURCES = {KLINE_SOURCE_AUTO, KLINE_SOURCE_CUSTOM}

SHEET_TASK_TYPES = {
    "google_sheet",
    "google_sheet_c4",
    "google_sheet_c5",
    "google_sheet_c7",
}
BACKTEST_TASK_TYPES = {"backtest_training", "backtest_multi_product"}
VALID_TASK_TYPES = SHEET_TASK_TYPES | BACKTEST_TASK_TYPES

RANDOM_TOKEN_VALUE = "__random__"

VALID_BACKTEST_PRICE_MODES = {"kp_price", "sp_price", "vwap_price"}

_VALID_KLINE_DATA_SOURCES = {"dfcf", "qq", "yahoo", "akshare", "tdx", "database"}


def normalize_task_type(value: str | None, default: str = "google_sheet") -> str:
    normalized = (value or "").strip().lower()
    if normalized == "c31":
        normalized = "google_sheet"
    return normalized if normalized in VALID_TASK_TYPES else default


def normalize_kline_data_source(value: Any) -> str:
    text = str(value or "").strip().lower()
    aliases = {"eastmoney": "dfcf", "internal": "database", "db": "database"}
    text = aliases.get(text, text)
    if text not in _VALID_KLINE_DATA_SOURCES:
        raise ValidationError(
            "kline_data_source 仅支持 dfcf/qq/yahoo/akshare/tdx/database"
        )
    return text


def normalize_market_type(value: Any, default: str = "cn") -> str:
    text = str(value or "").strip().lower()
    aliases = {"us": "en", "a": "cn", "a股": "cn"}
    text = aliases.get(text, text)
    return text or default


def normalize_stock_code(code: Any, market_type: Any = None) -> str:
    from app.services.market.codes import normalize_stock_code as _normalize

    return _normalize(code, market_type)


def _is_empty_custom_kline_option(value: Any) -> bool:
    return value in (None, "") or value == [] or value == ()


def _normalize_c_series_kline_source_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(config)
    kline_source = (
        str(normalized.get("kline_source") or KLINE_SOURCE_AUTO).strip().lower()
    )
    if kline_source not in VALID_KLINE_SOURCES:
        raise ValidationError("kline_source 仅支持 auto 或 custom")

    normalized["kline_source"] = kline_source
    if kline_source != KLINE_SOURCE_CUSTOM:
        return normalized

    if normalized.get("count_mode") not in (None, "", "total"):
        raise ValidationError("自定义K线模式不支持 N+1 或其它统计方式")
    if (
        not _is_empty_custom_kline_option(normalized.get("market_type"))
        and normalized.get("market_type") != "custom"
    ):
        raise ValidationError("自定义K线模式不支持选择 A股/美股市场")
    if not _is_empty_custom_kline_option(normalized.get("price_mode")):
        raise ValidationError("自定义K线模式不支持选择价格类型")
    if not _is_empty_custom_kline_option(normalized.get("kline_adjustment")):
        raise ValidationError("自定义K线模式不支持选择K线复权")
    if not _is_empty_custom_kline_option(normalized.get("date_range_mode")):
        raise ValidationError("自定义K线模式不支持整年/近年选项")
    if not _is_empty_custom_kline_option(normalized.get("exclude_recent_years")):
        raise ValidationError("自定义K线模式不支持近年排除选项")
    if not _is_empty_custom_kline_option(
        normalized.get("start_date")
    ) or not _is_empty_custom_kline_option(normalized.get("end_date")):
        raise ValidationError("自定义K线模式不支持开始日期/结束日期")

    normalized["count_mode"] = "total"
    normalized["market_type"] = "custom"
    normalized["price_mode"] = None
    normalized["kline_adjustment"] = None
    normalized["date_range_mode"] = []
    normalized["exclude_recent_years"] = []
    normalized["start_date"] = None
    normalized["end_date"] = None
    return normalized


def _normalize_c7_random_price_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(config)
    price_mode = normalized.get("price_mode") or "vwap_price"
    if price_mode != "random_price":
        normalized.pop("random_price_range", None)
        normalized.pop("random_group_count", None)
        return normalized

    versions = {
        str(sheet.get("c7_model_version") or "c7_0_2").strip().lower()
        for sheet in normalized.get("sheets") or []
    }
    if "c7_0_3" in versions:
        raise ValidationError("随机价格仅支持 C7.0.2")
    random_range = (
        str(normalized.get("random_price_range") or "high_low").strip().lower()
    )
    if random_range not in {"high_low", "open_close"}:
        raise ValidationError("随机价格范围仅支持最高最低或开盘收盘")
    try:
        raw_group_count = normalized.get("random_group_count")
        group_count = 1 if raw_group_count in (None, "") else int(raw_group_count)
    except (TypeError, ValueError) as exc:
        raise ValidationError("随机组数必须是正整数") from exc
    if (
        isinstance(raw_group_count, bool)
        or (isinstance(raw_group_count, float) and not raw_group_count.is_integer())
        or group_count < 1
    ):
        raise ValidationError("随机组数必须是正整数")
    normalized["random_price_range"] = random_range
    normalized["random_group_count"] = group_count
    return normalized


def normalize_task_config(task_type: str, config: dict[str, Any]) -> dict[str, Any]:
    """Normalize a task config dict for its task type (source rules preserved)."""
    normalized = dict(config or {})
    task_type = normalize_task_type(task_type)

    market_type = (
        normalize_market_type(normalized.get("market_type"))
        if normalized.get("market_type")
        else ""
    )
    if normalized.get("market_type"):
        normalized["market_type"] = market_type

    if normalized.get("stock_code"):
        normalized["stock_code"] = normalize_stock_code(
            normalized["stock_code"], market_type
        )

    if task_type in SHEET_TASK_TYPES or task_type in BACKTEST_TASK_TYPES:
        source = normalized.get("kline_data_source") or normalized.get("data_source")
        if source:
            normalized["kline_data_source"] = normalize_kline_data_source(source)
            normalized.pop("data_source", None)

    if task_type in {"google_sheet_c5", "google_sheet_c7"}:
        normalized = _normalize_c_series_kline_source_config(normalized)
    if task_type == "google_sheet_c7":
        normalized = _normalize_c7_random_price_config(normalized)

    if task_type in BACKTEST_TASK_TYPES:
        price_mode = normalized.get("price_mode") or "vwap_price"
        if price_mode not in VALID_BACKTEST_PRICE_MODES:
            price_mode = "vwap_price"
        normalized["price_mode"] = price_mode

    if task_type in {"google_sheet_c4", "google_sheet_c5", "google_sheet_c7"}:
        normalized.pop("spreadsheet_id", None)
        normalized.pop("sheet_name", None)

    return normalized


def extract_hot_columns(task_type: str, config: dict[str, Any]) -> dict[str, Any]:
    """Hot columns written at creation time so lists never parse config JSON."""
    hot: dict[str, Any] = {
        "spreadsheet_id": None,
        "stock_code": None,
        "market_type": None,
    }
    if not isinstance(config, dict):
        return hot
    hot["stock_code"] = config.get("stock_code") or None
    hot["market_type"] = config.get("market_type") or None
    spreadsheet_id = config.get("spreadsheet_id")
    if not spreadsheet_id and task_type in BACKTEST_TASK_TYPES:
        sheet = config.get("sheet") or {}
        if isinstance(sheet, dict):
            spreadsheet_id = sheet.get("spreadsheet_id")
    if (
        not spreadsheet_id
        and isinstance(config.get("sheets"), list)
        and config["sheets"]
    ):
        first = config["sheets"][0]
        if isinstance(first, dict):
            spreadsheet_id = first.get("spreadsheet_id")
    hot["spreadsheet_id"] = spreadsheet_id
    return hot


def create_task_with_config(
    session: Session,
    *,
    name: str,
    description: str | None,
    task_type: str,
    config: dict[str, Any],
) -> Task:
    """Normalize, validate and persist one pending task row (API-side)."""
    raw_type = (task_type or "").strip().lower()
    if raw_type != "c31" and raw_type not in VALID_TASK_TYPES:
        raise ValidationError(f"不支持的任务类型: {task_type}")
    task_type = normalize_task_type(task_type)
    normalized = normalize_task_config(task_type, config)
    hot = extract_hot_columns(task_type, normalized)
    task = Task.model_validate(
        TaskCreate(
            name=name,
            description=description,
            task_type=task_type,
            config=normalized,
        ),
        update=hot,
    )
    return _persist(session, task)


def _persist(session: Session, task: Task) -> Task:
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def create_restart_task(session: Session, original_task_id: int) -> Task:
    """Copy an existing task into a fresh pending row (config object reused)."""
    original = get_task(session=session, task_id=original_task_id)
    if not original:
        raise BadRequestError(f"任务不存在: {original_task_id}")

    config = original.config if isinstance(original.config, dict) else {}
    normalized = normalize_task_config(original.task_type, config)
    hot = extract_hot_columns(original.task_type, normalized)
    task = Task.model_validate(
        TaskCreate(
            name=f"{original.name} (重启)",
            description=f"{original.description or ''}基于任务 {original.id} 重启".strip(),
            task_type=original.task_type,
            config=normalized,
        ),
        update=hot,
    )
    return _persist(session, task)


# ---------------------------------------------------------------------------
# C31 batch expansion (stocks × parameter groups × sheets)
# ---------------------------------------------------------------------------


def _normalize_c31_parameter_groups(parameters: Any) -> list[list[list[Any]]]:
    if not isinstance(parameters, list) or not parameters:
        raise ValidationError("parameters 不能为空")
    groups: list[list[list[Any]]] = []
    for group in parameters:
        if not isinstance(group, list) or not group:
            raise ValidationError("每个参数组必须是非空数组")
        if all(isinstance(item, list) for item in group):
            for item in group:
                if not isinstance(item, list) or not item:
                    raise ValidationError("二维参数组内的每个子项必须是非空数组")
            groups.append([list(item) for item in group])
        else:
            groups.append(list(group))
    return groups


def _sheet_title_sort_key(title: str) -> tuple[str, int] | None:
    text = str(title or "").strip()
    if not text.endswith("]"):
        return None
    segments = text[:-1].split("-")
    if len(segments) < 2:
        return None
    year_n = segments[-2]
    try:
        sort_n = int(segments[-1])
    except ValueError:
        return None
    return year_n, sort_n


def expand_batch_c31(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand a C31 batch request into per-sheet C3 task specs."""
    from datetime import datetime, timedelta

    config = data.get("config") or {}
    base_task_name = str(config.get("base_task_name") or "").strip()
    if not base_task_name:
        raise ValidationError("base_task_name 不能为空")

    sheets = config.get("sheets")
    stock_codes = config.get("stock_codes") or config.get("stocks")
    parameters = config.get("parameters")
    if not isinstance(sheets, list) or not sheets:
        raise ValidationError("sheets 不能为空")
    if not isinstance(stock_codes, list) or not stock_codes:
        raise ValidationError("stock_codes 不能为空")
    if not isinstance(parameters, list) or not parameters:
        raise ValidationError("parameters 不能为空")

    groups = _normalize_c31_parameter_groups(parameters)
    combinations = list(product(*groups))

    valid_sheets = [
        s
        for s in sheets
        if isinstance(s, dict) and (s.get("spreadsheet_id") or "").strip()
    ]
    total = len(combinations)
    if total != len(valid_sheets) and (
        total == 0
        or len(valid_sheets) == 0
        or (total % len(valid_sheets) != 0 and len(valid_sheets) % total != 0)
    ):
        raise ValidationError("参数组合数与 Sheet 数量无法对齐")

    by_year: dict[str, list[dict[str, Any]]] = {}
    for sheet in valid_sheets:
        key = _sheet_title_sort_key(sheet.get("title") or sheet.get("sheet_name") or "")
        if key is None:
            raise ValidationError(f"Sheet 标题格式非法: {sheet.get('title')}")
        year_n, sort_n = key
        sheet = dict(sheet)
        sheet["_sort_n"] = sort_n
        by_year.setdefault(year_n, []).append(sheet)
    for year_n, group in by_year.items():
        group.sort(key=lambda s: s["_sort_n"])
        if len(group) != total:
            raise ValidationError(f"年份 {year_n} 的 Sheet 数量与参数组合数不一致")

    shared_config = {
        k: v
        for k, v in config.items()
        if k
        not in {
            "base_task_name",
            "task_description",
            "stock_codes",
            "parameters",
            "parameter_dimensions",
            "sheets",
        }
    }
    if not shared_config.get("token_id"):
        shared_config["token_type"] = "file"
        shared_config["token_id"] = RANDOM_TOKEN_VALUE

    specs: list[dict[str, Any]] = []
    default_end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    for stock in stock_codes:
        stock_code = stock
        stock_meta: dict[str, Any] = {}
        if isinstance(stock, dict):
            stock_meta = stock
            stock_code = stock.get("stock_code") or stock.get("code")
        if not stock_code:
            raise ValidationError("股票代码不能为空")
        market_type = normalize_market_type(
            stock_meta.get("market_type") or shared_config.get("market_type")
        )
        normalized_code = normalize_stock_code(stock_code, market_type)

        for index in range(total):
            year_sheets = {year_n: group[index] for year_n, group in by_year.items()}
            for year_n, sheet in year_sheets.items():
                child_config = dict(shared_config)
                child_config.update(
                    {
                        "spreadsheet_id": sheet.get("spreadsheet_id"),
                        "sheet_name": sheet.get("sheet_name"),
                        "title": sheet.get("title"),
                        "stock_code": normalized_code,
                        "stock_name": stock_meta.get("stock_name")
                        or stock_meta.get("name"),
                        "market_type": market_type,
                        "kline_adjustment": shared_config.get(
                            "kline_adjustment", "forward"
                        ),
                        "end_date": shared_config.get("end_date") or default_end_date,
                        "year_n": year_n,
                        "parameters": [list(combinations[index])],
                    }
                )
                specs.append(
                    {
                        "name": f"{base_task_name}-{year_n}-{sheet['_sort_n']}",
                        "description": config.get("task_description"),
                        "task_type": "google_sheet",
                        "config": child_config,
                    }
                )
    return specs


def create_batch_tasks(session: Session, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Create all tasks of a C31 batch; the worker claims them when slots free up."""
    specs = expand_batch_c31(data)
    created: list[dict[str, Any]] = []
    for spec in specs:
        task = create_task_with_config(
            session,
            name=spec["name"],
            description=spec["description"],
            task_type=spec["task_type"],
            config=spec["config"],
        )
        created.append({"task_id": task.id, "name": task.name})
    return created


def parse_parameters_literal(raw: str | None) -> list[list[Any]]:
    """Parse a pasted parameter matrix (JSON) used by the create form."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"参数矩阵不是有效JSON: {exc}") from exc
    if not isinstance(parsed, list):
        raise ValidationError("参数矩阵必须是二维数组")
    return parsed
