"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import GetSysUserListRequestDto, GetUserListForSelectRequestDto, IdRequestDto, RegisterRequestDto, UpdatePwdRequestDto, UserEnableOrUnEnableRequestDto, sys_user
from ..response import ResponseDto
from ._metadata import endpoint

class SysuserApi(ApiGroup):
    @endpoint('POST', '/api/SysUser/Get')
    def get(self) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysUser/Get')

    @endpoint('POST', '/api/SysUser/GetById')
    def get_by_id(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysUser/GetById', json_body=request)

    @endpoint('POST', '/api/SysUser/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: GetSysUserListRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysUser/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/SysUser/GetListForSelect')
    def get_list_for_select(
        self,
        request: GetUserListForSelectRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysUser/GetListForSelect', json_body=request)

    @endpoint('POST', '/api/SysUser/GetUserInfo')
    def get_user_info(self) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysUser/GetUserInfo')

    @endpoint('POST', '/api/SysUser/GetUserRoleList')
    def get_user_role_list(self) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysUser/GetUserRoleList')

    @endpoint('POST', '/api/SysUser/Login')
    def login(
        self,
        request: RegisterRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysUser/Login', json_body=request)

    @endpoint('POST', '/api/SysUser/PwdReset')
    def pwd_reset(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysUser/PwdReset', json_body=request)

    @endpoint('POST', '/api/SysUser/Register')
    def register(
        self,
        request: RegisterRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysUser/Register', json_body=request)

    @endpoint('POST', '/api/SysUser/UpdatePwd')
    def update_pwd(
        self,
        request: UpdatePwdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysUser/UpdatePwd', json_body=request)

    @endpoint('POST', '/api/SysUser/UpdateUserRole')
    def update_user_role(
        self,
        request: sys_user | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysUser/UpdateUserRole', json_body=request)

    @endpoint('POST', '/api/SysUser/UserEnableOrUnEnable')
    def user_enable_or_un_enable(
        self,
        request: UserEnableOrUnEnableRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysUser/UserEnableOrUnEnable', json_body=request)
