"""Generated endpoint wrappers for one Swagger controller."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..http_client import ApiGroup
from ..models import GetSysLogListRequestDto
from ..response import ResponseDto
from ._metadata import endpoint

class SyslogApi(ApiGroup):
    @endpoint('POST', '/api/SysLog/GetDataByPageList')
    def get_data_by_page_list(
        self,
        request: GetSysLogListRequestDto | Mapping[str, Any],
    ) -> ResponseDto[Any]:
        return self._call('POST', '/api/SysLog/GetDataByPageList', json_body=request)
