"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import IdRequestDto, RequsetPageDto, t_param_task_result_summary_index
from ..response import ResponseDto
from ._metadata import endpoint

class ParamtaskresultsummaryindexApi(ApiGroup):
    @endpoint('POST', '/api/ParamTaskResultSummaryIndex/Delete')
    def delete(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskResultSummaryIndex/Delete', json_body=request)

    @endpoint('POST', '/api/ParamTaskResultSummaryIndex/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: RequsetPageDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskResultSummaryIndex/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/ParamTaskResultSummaryIndex/GetInfoById')
    def get_info_by_id(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskResultSummaryIndex/GetInfoById', json_body=request)

    @endpoint('POST', '/api/ParamTaskResultSummaryIndex/ModifyOrAdd')
    def modify_or_add(
        self,
        request: t_param_task_result_summary_index | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskResultSummaryIndex/ModifyOrAdd', json_body=request)
