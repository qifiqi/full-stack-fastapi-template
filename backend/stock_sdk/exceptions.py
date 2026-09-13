"""Exception hierarchy for transport, protocol, and API failures."""

from __future__ import annotations

from typing import Any


class StockSdkError(Exception):
    """Base exception for all SDK failures."""


class ApiConnectionError(StockSdkError):
    """The server could not be reached."""


class ApiTimeoutError(ApiConnectionError):
    """The request exceeded the configured timeout."""


class ApiResponseError(StockSdkError):
    """The server returned a malformed or unexpected response."""


class ApiHttpError(StockSdkError):
    """The server returned an HTTP failure status."""

    def __init__(self, status_code: int, body: Any) -> None:
        super().__init__(f"HTTP {status_code}: {body}")
        self.status_code = status_code
        self.body = body


class ApiBusinessError(StockSdkError):
    """The API returned a non-success ``ret_code`` response."""

    def __init__(self, ret_code: int | None, ret_msg: str | None) -> None:
        super().__init__(f"API ret_code {ret_code}: {ret_msg or ''}".rstrip())
        self.ret_code = ret_code
        self.ret_msg = ret_msg
