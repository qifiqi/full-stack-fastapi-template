"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import GetListHisPageRequestDto, GetStockDataAllListRequestDto, GetStockDataListPageRequestDto, GetStockDataListRequestDto, GetStockDataRequestDto, GetStockListByCodeRequestDto, IdRequestDto, t_stock_data
from ..response import ResponseDto
from ._metadata import endpoint

class StockdataApi(ApiGroup):
    @endpoint('POST', '/api/StockData/Delete')
    def delete(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/StockData/Delete', json_body=request)

    @endpoint('POST', '/api/StockData/GetById')
    def get_by_id(
        self,
        request: IdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/StockData/GetById', json_body=request)

    @endpoint('POST', '/api/StockData/GetDataAllList')
    def get_data_all_list(
        self,
        request: GetStockDataAllListRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/StockData/GetDataAllList', json_body=request)

    @endpoint('POST', '/api/StockData/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: GetStockDataListRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/StockData/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/StockData/GetListHisPage')
    def get_list_his_page(
        self,
        request: GetListHisPageRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/StockData/GetListHisPage', json_body=request)

    @endpoint('POST', '/api/StockData/GetListPage')
    def get_list_page(
        self,
        request: GetStockDataListPageRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/StockData/GetListPage', json_body=request)

    @endpoint('POST', '/api/StockData/GetListVolume')
    def get_list_volume(
        self,
        request: GetStockDataRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/StockData/GetListVolume', json_body=request)

    @endpoint('POST', '/api/StockData/GetStockListByCode')
    def get_stock_list_by_code(
        self,
        request: GetStockListByCodeRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/StockData/GetStockListByCode', json_body=request)

    @endpoint('POST', '/api/StockData/GetStockListByCodeOrDate')
    def get_stock_list_by_code_or_date(
        self,
        request: GetStockListByCodeRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/StockData/GetStockListByCodeOrDate', json_body=request)

    @endpoint('POST', '/api/StockData/ModifyOrAdd')
    def modify_or_add(
        self,
        request: t_stock_data | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/StockData/ModifyOrAdd', json_body=request)
