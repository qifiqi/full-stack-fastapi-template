"""Sheet template layout constants (single source of truth, ported verbatim)."""

# C3 参数输入格：8 槽位（B5 佣金 + 7 业务参数）
# (单元格, 契约字段名, 导出列名, 展示标签)
C3_PARAM_SLOTS = [
    ("B5", "commission", None, "Commission"),
    ("B6", "xm", "xm", "X Multiplier"),
    ("B7", "dbbh1", "tp1", "单边保护1"),
    ("B8", "dbbh2", None, "单边保护2"),
    ("B9", "zlxc", "nl", "中立限仓"),
    ("B10", "zsgz", "if", "指数跟踪"),
    ("B11", "ywf1", "ywfs", "一窝蜂 smoothing"),
    ("B12", "ywf2", "ywb", "一窝蜂 bordering"),
]

C3_PARAMETER_KEYS = tuple(
    key for _cell, key, _alias, _label in C3_PARAM_SLOTS if key != "commission"
)

# 结果单元格：概念键 → 单元格
C3_METRIC_CELLS = {
    "return_rate": "I15",
    "annualized_rate": "I16",
    "max_drawdown": "I17",
    "index_return": "I18",
    "index_annualized_rate": "I19",
    "index_max_drawdown": "I20",
    "fee_total": "I21",
    "fee_annualized": "I22",
    "turnover_rate": "I23",
}

C4_C5_METRIC_CELLS = {
    "return_rate": "D2",
    "annualized_rate": "D3",
    "max_drawdown": "D4",
    "index_return": "D5",
    "index_annualized_rate": "D6",
    "index_max_drawdown": "D7",
    "fee_total": "D8",
    "fee_annualized": "D9",
    "turnover_rate": "D10",
    "return_beats": "D11",
    "dd_beats": "D12",
    "max_one_year_beats": "D13",
    "min_one_year_beats": "D14",
    "max_theoretical_leverage": "D15",
    "avg_theoretical_leverage": "D16",
    "unit_theoretical_leverage_return": "D17",
    "max_actual_leverage": "D18",
    "avg_actual_leverage": "D19",
    "unit_actual_leverage_return": "D20",
}

# C7.0.2 的结果区域 = C4/C5 布局整体下移 6 行（D2→D8 … D20→D26）；
# C7.0.3 与 C5 布局一致，不做平移。
C7_ROW_SHIFT = 6


def c7_shifted_cell(cell: str) -> str:
    return f"D{int(cell[1:]) + C7_ROW_SHIFT}"


_REPORT_SUMMARY_ALIASES = {"return_rate": "return"}
_REPORT_SUMMARY_CONCEPTS = (
    "return_rate",
    "index_return",
    "max_drawdown",
    "index_max_drawdown",
)


def _report_key(concept: str) -> str:
    return _REPORT_SUMMARY_ALIASES.get(concept, concept)


SUMMARY_METRIC_CELL_MAP = {
    "C3": {_report_key(c): C3_METRIC_CELLS[c] for c in _REPORT_SUMMARY_CONCEPTS},
    "C5": {_report_key(c): C4_C5_METRIC_CELLS[c] for c in _REPORT_SUMMARY_CONCEPTS},
    "C7": {
        _report_key(c): c7_shifted_cell(C4_C5_METRIC_CELLS[c])
        for c in _REPORT_SUMMARY_CONCEPTS
    },
}
SUMMARY_METRIC_CELL_MAP["C4"] = SUMMARY_METRIC_CELL_MAP["C5"]

# C7 原始结果中按百分数字符串存储、需 ×100 归一的单元格（C7 平移布局下取值）。
_C7_RAW_PERCENT_CONCEPTS = (
    "max_drawdown",
    "fee_annualized",
    "dd_beats",
    "max_one_year_beats",
)
_C7_PERCENT_LEVERAGE_CONCEPTS = (
    "avg_theoretical_leverage",
    "max_actual_leverage",
    "avg_actual_leverage",
)
C7_RAW_PERCENT_CELLS = frozenset(
    c7_shifted_cell(C4_C5_METRIC_CELLS[k]) for k in _C7_RAW_PERCENT_CONCEPTS
)
C7_PERCENT_LEVERAGE_CELLS = frozenset(
    c7_shifted_cell(C4_C5_METRIC_CELLS[k]) for k in _C7_PERCENT_LEVERAGE_CONCEPTS
)
