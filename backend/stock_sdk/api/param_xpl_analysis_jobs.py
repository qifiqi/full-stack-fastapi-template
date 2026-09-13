"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import ParamStringIdRequestDto, RequsetPageDto, t_param_xpl_analysis_jobs
from ..response import ResponseDto
from ._metadata import endpoint

class ParamxplanalysisjobsApi(ApiGroup):
    @endpoint('POST', '/api/ParamXplAnalysisJobs/Delete')
    def delete(
        self,
        request: ParamStringIdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamXplAnalysisJobs/Delete', json_body=request)

    @endpoint('POST', '/api/ParamXplAnalysisJobs/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: RequsetPageDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamXplAnalysisJobs/GetDataByPageList', json_body=request)

    @endpoint('POST', '/api/ParamXplAnalysisJobs/GetInfoById')
    def get_info_by_id(
        self,
        request: ParamStringIdRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamXplAnalysisJobs/GetInfoById', json_body=request)

    @endpoint('POST', '/api/ParamXplAnalysisJobs/ModifyOrAdd')
    def modify_or_add(
        self,
        request: t_param_xpl_analysis_jobs | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/ParamXplAnalysisJobs/ModifyOrAdd', json_body=request)
