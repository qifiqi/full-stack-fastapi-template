"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import IdRequestDto, RequsetPageDto, t_param_task_results_return
from ..response import ResponseDto
from ._metadata import endpoint

class ParamtaskresultsreturnApi(ApiGroup):
    @endpoint('POST', '/api/ParamTaskResultsReturn/Delete')
    def delete(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskResultsReturn/Delete', json_body=request)

    @endpoint('POST', '/api/ParamTaskResultsReturn/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: RequsetPageDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskResultsReturn/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/ParamTaskResultsReturn/GetInfoById')
    def get_info_by_id(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskResultsReturn/GetInfoById', json_body=request)

    @endpoint('POST', '/api/ParamTaskResultsReturn/ModifyOrAdd')
    def modify_or_add(
        self,
        request: t_param_task_results_return | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskResultsReturn/ModifyOrAdd', json_body=request)
