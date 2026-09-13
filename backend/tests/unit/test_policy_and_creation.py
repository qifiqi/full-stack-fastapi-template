"""Golden tests for check_policy / creation normalization (source rules)."""

import pytest

from app.services.google_sheet_tasks.check_policy import normalize_check_values
from app.services.google_sheet_tasks.result_payload import build_stock_param_metric_fields, to_decimal_ratio
from app.services.tasks.creation import normalize_task_config
from app.services.tasks.errors import SheetCheckError, ValidationError


def test_normalize_check_values_percent_and_placeholder() -> None:
    normalized = normalize_check_values(
        {"X2": "5.00%", "X3": "1,234", "X4": "-"},
        invalid_predicate=lambda v: v in (None, ""),
    )
    assert normalized["X2"] == pytest.approx(0.05)
    assert normalized["X3"] == 1234.0
    assert "X4" not in normalized


def test_normalize_check_values_hash_raises_sheet_check_error() -> None:
    with pytest.raises(SheetCheckError):
        normalize_check_values({"X2": "#N/A"})


def test_to_decimal_ratio() -> None:
    assert to_decimal_ratio("71.88%") == pytest.approx(0.7188)
    assert to_decimal_ratio("") == 0
    assert to_decimal_ratio(None) == 0
    assert to_decimal_ratio("1,234") == pytest.approx(12.34)


def test_build_stock_param_metric_fields() -> None:
    result = {"D2": "10%", "D15": "1.5", "D10": "230"}
    fields = build_stock_param_metric_fields(lambda cell: result.get(cell, 0))
    assert fields["return_rate"] == pytest.approx(0.10)
    assert fields["max_theoretical_leverage"] == "1.5"
    assert fields["turnover_rate"] == "230"


def test_normalize_task_config_kline_source_rules() -> None:
    config = normalize_task_config("google_sheet_c5", {"kline_source": "auto", "market_type": "cn"})
    assert config["kline_source"] == "auto"
    with pytest.raises(ValidationError):
        normalize_task_config("google_sheet_c5", {"kline_source": "magic"})
    # custom mode + explicit market is rejected (source rule)
    with pytest.raises(ValidationError):
        normalize_task_config(
            "google_sheet_c5", {"kline_source": "custom", "market_type": "cn"}
        )
    custom = normalize_task_config(
        "google_sheet_c5",
        {"kline_source": "custom"},
    )
    assert custom["market_type"] == "custom"
    assert custom["count_mode"] == "total"


def test_normalize_task_config_c7_random_price_rules() -> None:
    config = normalize_task_config(
        "google_sheet_c7",
        {"price_mode": "random_price", "random_price_range": "open_close", "random_group_count": "3"},
    )
    assert config["random_group_count"] == 3
    with pytest.raises(ValidationError):
        normalize_task_config(
            "google_sheet_c7",
            {
                "price_mode": "random_price",
                "sheets": [{"c7_model_version": "c7_0_3"}],
            },
        )
    with pytest.raises(ValidationError):
        normalize_task_config(
            "google_sheet_c7",
            {"price_mode": "random_price", "random_price_range": "diagonal"},
        )
    stripped = normalize_task_config("google_sheet_c7", {"price_mode": "vwap_price", "random_price_range": "high_low"})
    assert "random_price_range" not in stripped


def test_normalize_task_config_backtest_price_mode_fallback() -> None:
    config = normalize_task_config("backtest_training", {"price_mode": "magic"})
    assert config["price_mode"] == "vwap_price"


def test_normalize_task_config_c4_drops_sheet_keys() -> None:
    config = normalize_task_config(
        "google_sheet_c4",
        {"spreadsheet_id": "SS", "sheet_name": "S1", "market_type": "cn"},
    )
    assert "spreadsheet_id" not in config
    assert "sheet_name" not in config
