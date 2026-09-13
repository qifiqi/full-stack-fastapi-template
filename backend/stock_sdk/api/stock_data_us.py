"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import GetListHisPageRequestDto, GetStockDataAllListRequestDto, GetStockDataListPageRequestDto, GetStockDataListRequestDto, IdRequestDto, t_stock_data_us
from ..response import ResponseDto
from ._metadata import endpoint

class StockdatausApi(ApiGroup):
    @endpoint('POST', '/api/StockDataUs/Delete')
    def delete(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/StockDataUs/Delete', json_body=request)

    @endpoint('POST', '/api/StockDataUs/GetById')
    def get_by_id(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/StockDataUs/GetById', json_body=request)

    @endpoint('POST', '/api/StockDataUs/GetDataAllList')
    def get_data_all_list(
        self,
        request: GetStockDataAllListRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/StockDataUs/GetDataAllList', json_body=request)

    @endpoint('POST', '/api/StockDataUs/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: GetStockDataListRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/StockDataUs/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/StockDataUs/GetListHisPage')
    def get_list_his_page(
        self,
        request: GetListHisPageRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/StockDataUs/GetListHisPage', json_body=request)

    @endpoint('POST', '/api/StockDataUs/GetListPage')
    def get_list_page(
        self,
        request: GetStockDataListPageRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/StockDataUs/GetListPage', json_body=request)

    @endpoint('POST', '/api/StockDataUs/ModifyOrAdd')
    def modify_or_add(
        self,
        request: t_stock_data_us | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/StockDataUs/ModifyOrAdd', json_body=request)
