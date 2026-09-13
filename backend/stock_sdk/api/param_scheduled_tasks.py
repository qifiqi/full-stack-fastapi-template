"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import IdRequestDto, RequsetPageDto, t_param_scheduled_tasks
from ..response import ResponseDto
from ._metadata import endpoint

class ParamscheduledtasksApi(ApiGroup):
    @endpoint('POST', '/api/ParamScheduledTasks/Delete')
    def delete(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamScheduledTasks/Delete', json_body=request)

    @endpoint('POST', '/api/ParamScheduledTasks/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: RequsetPageDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamScheduledTasks/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/ParamScheduledTasks/GetInfoById')
    def get_info_by_id(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamScheduledTasks/GetInfoById', json_body=request)

    @endpoint('POST', '/api/ParamScheduledTasks/ModifyOrAdd')
    def modify_or_add(
        self,
        request: t_param_scheduled_tasks | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamScheduledTasks/ModifyOrAdd', json_body=request)
