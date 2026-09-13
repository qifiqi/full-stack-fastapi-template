"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import IdRequestDto, RequsetPageDto, t_param_google_sheet
from ..response import ResponseDto
from ._metadata import endpoint

class ParamgooglesheetApi(ApiGroup):
    @endpoint('POST', '/api/ParamGoogleSheet/Delete')
    def delete(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamGoogleSheet/Delete', json_body=request)

    @endpoint('POST', '/api/ParamGoogleSheet/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: RequsetPageDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamGoogleSheet/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/ParamGoogleSheet/GetInfoById')
    def get_info_by_id(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamGoogleSheet/GetInfoById', json_body=request)

    @endpoint('POST', '/api/ParamGoogleSheet/ModifyOrAdd')
    def modify_or_add(
        self,
        request: t_param_google_sheet | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamGoogleSheet/ModifyOrAdd', json_body=request)
