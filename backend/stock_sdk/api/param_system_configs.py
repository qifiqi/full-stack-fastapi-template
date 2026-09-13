"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import IdRequestDto, RequsetPageDto, t_param_system_configs
from ..response import ResponseDto
from ._metadata import endpoint

class ParamsystemconfigsApi(ApiGroup):
    @endpoint('POST', '/api/ParamSystemConfigs/Delete')
    def delete(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamSystemConfigs/Delete', json_body=request)

    @endpoint('POST', '/api/ParamSystemConfigs/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: RequsetPageDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamSystemConfigs/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/ParamSystemConfigs/GetInfoById')
    def get_info_by_id(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamSystemConfigs/GetInfoById', json_body=request)

    @endpoint('POST', '/api/ParamSystemConfigs/ModifyOrAdd')
    def modify_or_add(
        self,
        request: t_param_system_configs | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamSystemConfigs/ModifyOrAdd', json_body=request)
