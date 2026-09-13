"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import IdRequestDto, RequsetPageDto, t_param_backtest_sheet_run_locks
from ..response import ResponseDto
from ._metadata import endpoint

class ParambacktestsheetrunlocksApi(ApiGroup):
    @endpoint('POST', '/api/ParamBacktestSheetRunLocks/Delete')
    def delete(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamBacktestSheetRunLocks/Delete', json_body=request)

    @endpoint('POST', '/api/ParamBacktestSheetRunLocks/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: RequsetPageDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamBacktestSheetRunLocks/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/ParamBacktestSheetRunLocks/GetInfoById')
    def get_info_by_id(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamBacktestSheetRunLocks/GetInfoById', json_body=request)

    @endpoint('POST', '/api/ParamBacktestSheetRunLocks/ModifyOrAdd')
    def modify_or_add(
        self,
        request: t_param_backtest_sheet_run_locks | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamBacktestSheetRunLocks/ModifyOrAdd', json_body=request)
