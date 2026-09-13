"""All generated endpoint groups, grouped by Swagger controller."""

from __future__ import annotations

from typing import Any

from .param_backtest_product_result_cache import ParambacktestproductresultcacheApi
from .param_backtest_sheet_run_locks import ParambacktestsheetrunlocksApi
from .param_google_sheet import ParamgooglesheetApi
from .param_google_sheet_tokens import ParamgooglesheettokensApi
from .param_scheduled_tasks import ParamscheduledtasksApi
from .param_stock_metadata import ParamstockmetadataApi
from .param_system_configs import ParamsystemconfigsApi
from .param_task_logs import ParamtasklogsApi
from .param_task_results import ParamtaskresultsApi
from .param_task_results_return import ParamtaskresultsreturnApi
from .param_task_result_summary_index import ParamtaskresultsummaryindexApi
from .param_tasks import ParamtasksApi
from .param_task_templates import ParamtasktemplatesApi
from .param_xpl_analysis_jobs import ParamxplanalysisjobsApi
from .stock_data import StockdataApi
from .stock_data_us import StockdatausApi
from .sys_log import SyslogApi
from .sys_model import SysmodelApi
from .sys_role import SysroleApi
from .sys_user import SysuserApi

def bind_api_groups(client: Any) -> None:
    """Attach every controller group to a client instance."""
    client.param_backtest_product_result_cache = ParambacktestproductresultcacheApi(client)
    client.param_backtest_sheet_run_locks = ParambacktestsheetrunlocksApi(client)
    client.param_google_sheet = ParamgooglesheetApi(client)
    client.param_google_sheet_tokens = ParamgooglesheettokensApi(client)
    client.param_scheduled_tasks = ParamscheduledtasksApi(client)
    client.param_stock_metadata = ParamstockmetadataApi(client)
    client.param_system_configs = ParamsystemconfigsApi(client)
    client.param_task_logs = ParamtasklogsApi(client)
    client.param_task_results = ParamtaskresultsApi(client)
    client.param_task_results_return = ParamtaskresultsreturnApi(client)
    client.param_task_result_summary_index = ParamtaskresultsummaryindexApi(client)
    client.param_tasks = ParamtasksApi(client)
    client.param_task_templates = ParamtasktemplatesApi(client)
    client.param_xpl_analysis_jobs = ParamxplanalysisjobsApi(client)
    client.stock_data = StockdataApi(client)
    client.stock_data_us = StockdatausApi(client)
    client.sys_log = SyslogApi(client)
    client.sys_model = SysmodelApi(client)
    client.sys_role = SysroleApi(client)
    client.sys_user = SysuserApi(client)

