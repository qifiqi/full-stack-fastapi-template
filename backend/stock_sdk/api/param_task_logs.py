"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import IdRequestDto, RequsetPageDto, t_param_task_logs
from ..response import ResponseDto
from ._metadata import endpoint

class ParamtasklogsApi(ApiGroup):
    @endpoint('POST', '/api/ParamTaskLogs/Delete')
    def delete(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskLogs/Delete', json_body=request)

    @endpoint('POST', '/api/ParamTaskLogs/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: RequsetPageDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskLogs/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/ParamTaskLogs/GetInfoById')
    def get_info_by_id(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskLogs/GetInfoById', json_body=request)

    @endpoint('POST', '/api/ParamTaskLogs/ModifyOrAdd')
    def modify_or_add(
        self,
        request: t_param_task_logs | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskLogs/ModifyOrAdd', json_body=request)
