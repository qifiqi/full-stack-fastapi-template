"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import IdRequestDto, RequsetPageDto, t_param_task_results
from ..response import ResponseDto
from ._metadata import endpoint

class ParamtaskresultsApi(ApiGroup):
    @endpoint('POST', '/api/ParamTaskResults/Delete')
    def delete(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskResults/Delete', json_body=request)

    @endpoint('POST', '/api/ParamTaskResults/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: RequsetPageDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskResults/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/ParamTaskResults/GetInfoById')
    def get_info_by_id(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskResults/GetInfoById', json_body=request)

    @endpoint('POST', '/api/ParamTaskResults/ModifyOrAdd')
    def modify_or_add(
        self,
        request: t_param_task_results | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskResults/ModifyOrAdd', json_body=request)
