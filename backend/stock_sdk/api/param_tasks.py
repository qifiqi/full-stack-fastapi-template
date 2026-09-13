"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import ParamStringIdRequestDto, RequsetPageDto, t_param_tasks
from ..response import ResponseDto
from ._metadata import endpoint

class ParamtasksApi(ApiGroup):
    @endpoint('POST', '/api/ParamTasks/Delete')
    def delete(
        self,
        request: ParamStringIdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTasks/Delete', json_body=request)

    @endpoint('POST', '/api/ParamTasks/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: RequsetPageDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTasks/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/ParamTasks/GetInfoById')
    def get_info_by_id(
        self,
        request: ParamStringIdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTasks/GetInfoById', json_body=request)

    @endpoint('POST', '/api/ParamTasks/ModifyOrAdd')
    def modify_or_add(
        self,
        request: t_param_tasks | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTasks/ModifyOrAdd', json_body=request)
