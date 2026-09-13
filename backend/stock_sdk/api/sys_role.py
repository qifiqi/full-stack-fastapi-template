"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import GetSysRoleListRequestDto, IdRequestDto, IsRoleRequestDto, sys_role
from ..response import ResponseDto
from ._metadata import endpoint

class SysroleApi(ApiGroup):
    @endpoint('POST', '/api/SysRole/Delete')
    def delete(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysRole/Delete', json_body=request)

    @endpoint('POST', '/api/SysRole/GetById')
    def get_by_id(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysRole/GetById', json_body=request)

    @endpoint('POST', '/api/SysRole/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: GetSysRoleListRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysRole/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/SysRole/GetRoleListForSelect')
    def get_role_list_for_select(self) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysRole/GetRoleListForSelect')

    @endpoint('POST', '/api/SysRole/IsRole')
    def is_role(
        self,
        request: IsRoleRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysRole/IsRole', json_body=request)

    @endpoint('POST', '/api/SysRole/ModifyOrAdd')
    def modify_or_add(
        self,
        request: sys_role | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysRole/ModifyOrAdd', json_body=request)
