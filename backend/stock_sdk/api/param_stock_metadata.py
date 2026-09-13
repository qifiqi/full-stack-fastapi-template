"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import IdRequestDto, RequsetPageDto, t_param_stock_metadata
from ..response import ResponseDto
from ._metadata import endpoint

class ParamstockmetadataApi(ApiGroup):
    @endpoint('POST', '/api/ParamStockMetadata/Delete')
    def delete(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamStockMetadata/Delete', json_body=request)

    @endpoint('POST', '/api/ParamStockMetadata/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: RequsetPageDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamStockMetadata/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/ParamStockMetadata/GetInfoById')
    def get_info_by_id(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamStockMetadata/GetInfoById', json_body=request)

    @endpoint('POST', '/api/ParamStockMetadata/ModifyOrAdd')
    def modify_or_add(
        self,
        request: t_param_stock_metadata | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamStockMetadata/ModifyOrAdd', json_body=request)
