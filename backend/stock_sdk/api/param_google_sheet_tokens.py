"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import IdRequestDto, RequsetPageDto, t_param_google_sheet_tokens
from ..response import ResponseDto
from ._metadata import endpoint

class ParamgooglesheettokensApi(ApiGroup):
    @endpoint('POST', '/api/ParamGoogleSheetTokens/Delete')
    def delete(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamGoogleSheetTokens/Delete', json_body=request)

    @endpoint('POST', '/api/ParamGoogleSheetTokens/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: RequsetPageDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamGoogleSheetTokens/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/ParamGoogleSheetTokens/GetInfoById')
    def get_info_by_id(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamGoogleSheetTokens/GetInfoById', json_body=request)

    @endpoint('POST', '/api/ParamGoogleSheetTokens/ModifyOrAdd')
    def modify_or_add(
        self,
        request: t_param_google_sheet_tokens | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamGoogleSheetTokens/ModifyOrAdd', json_body=request)
