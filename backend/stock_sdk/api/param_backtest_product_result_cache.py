"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import IdRequestDto, RequsetPageDto, t_param_backtest_product_result_cache
from ..response import ResponseDto
from ._metadata import endpoint

class ParambacktestproductresultcacheApi(ApiGroup):
    @endpoint('POST', '/api/ParamBacktestProductResultCache/Delete')
    def delete(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamBacktestProductResultCache/Delete', json_body=request)

    @endpoint('POST', '/api/ParamBacktestProductResultCache/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: RequsetPageDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamBacktestProductResultCache/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/ParamBacktestProductResultCache/GetInfoById')
    def get_info_by_id(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamBacktestProductResultCache/GetInfoById', json_body=request)

    @endpoint('POST', '/api/ParamBacktestProductResultCache/ModifyOrAdd')
    def modify_or_add(
        self,
        request: t_param_backtest_product_result_cache | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamBacktestProductResultCache/ModifyOrAdd', json_body=request)
