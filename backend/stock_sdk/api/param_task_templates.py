"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import IdRequestDto, RequsetPageDto, t_param_task_templates
from ..response import ResponseDto
from ._metadata import endpoint

class ParamtasktemplatesApi(ApiGroup):
    @endpoint('POST', '/api/ParamTaskTemplates/Delete')
    def delete(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskTemplates/Delete', json_body=request)

    @endpoint('POST', '/api/ParamTaskTemplates/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: RequsetPageDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskTemplates/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/ParamTaskTemplates/GetInfoById')
    def get_info_by_id(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskTemplates/GetInfoById', json_body=request)

    @endpoint('POST', '/api/ParamTaskTemplates/ModifyOrAdd')
    def modify_or_add(
        self,
        request: t_param_task_templates | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamTaskTemplates/ModifyOrAdd', json_body=request)
