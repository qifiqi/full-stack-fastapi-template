"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import GetModelListRequestDto, IdRequestDto, sys_model
from ..response import ResponseDto
from ._metadata import endpoint

class SysmodelApi(ApiGroup):
    @endpoint('POST', '/api/SysModel/Delete')
    def delete(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysModel/Delete', json_body=request)

    @endpoint('POST', '/api/SysModel/GetById')
    def get_by_id(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysModel/GetById', json_body=request)

    @endpoint('POST', '/api/SysModel/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: GetModelListRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysModel/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/SysModel/GetTopModelList')
    def get_top_model_list(
        self,
        request: sys_model | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysModel/GetTopModelList', json_body=request)

    @endpoint('POST', '/api/SysModel/ModifyOrAdd')
    def modify_or_add(
        self,
        request: sys_model | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysModel/ModifyOrAdd', json_body=request)
