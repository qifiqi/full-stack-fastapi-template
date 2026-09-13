"""Synchronous HTTP transport used by generated endpoint wrappers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import requests

from .exceptions import ApiConnectionError, ApiHttpError, ApiResponseError, ApiTimeoutError
from .model_base import SerializableModel
from .response import ResponseDto


DEFAULT_BASE_URL = "http://172.18.20.20:8081"


class SyncHttpClient:
    """Minimal standard-library synchronous HTTP client with Token auth."""

    def __init__(
        self,
        *,
        token: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 10.0,
        session: requests.Session | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token = token
        self._client = session if session is not None else requests.Session()
        self._client.headers.update({"Accept": "application/json"})

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: SerializableModel | Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> ResponseDto[Any]:
        """Send one request and decode the API's common response envelope."""
        headers: dict[str, str] = {}
        if self.token:
            headers["Token"] = self.token
        payload = None
        if json_body is not None:
            payload = (
                json_body.to_dict()
                if isinstance(json_body, SerializableModel)
                else dict(json_body)
            )
        filtered_params = (
            {key: value for key, value in params.items() if value is not None}
            if params
            else None
        )
        try:
            response = self._client.request(
                method,
                f"{self.base_url}{path}",
                params=filtered_params,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.Timeout as error:
            raise ApiTimeoutError("Request timed out") from error
        except requests.RequestException as error:
            raise ApiConnectionError(str(error)) from error
        body = self._decode_body(response)
        if response.status_code >= 400:
            raise ApiHttpError(response.status_code, body)
        if not isinstance(body, dict):
            raise ApiResponseError("Expected a JSON object response envelope")
        return ResponseDto.from_dict(body)

    @staticmethod
    def _decode_body(response: requests.Response) -> Any:
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as error:
            raise ApiResponseError("Response body is not valid JSON") from error

    def close(self) -> None:
        """Close the underlying synchronous requests session."""
        self._client.close()

    def __enter__(self) -> "SyncHttpClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class ApiGroup:
    """Base class shared by generated controller endpoint wrappers."""

    def __init__(self, client: SyncHttpClient) -> None:
        self._client = client

    def _call(self, method: str, path: str, **kwargs: Any) -> ResponseDto[Any]:
        return self._client.request(method, path, **kwargs)
