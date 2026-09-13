"""The common response envelope returned by DY.Stock.Api."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from .exceptions import ApiBusinessError


ResultT = TypeVar("ResultT")


@dataclass(frozen=True)
class ResponseDto(Generic[ResultT]):
    """Uniform DY.Stock.Api response envelope."""

    ret_code: int | None = None
    ret_msg: str | None = None
    ret_count: int | None = None
    ret_obj: ResultT | None = None

    @property
    def is_success(self) -> bool:
        """Whether the documented success code (200) was returned."""
        return self.ret_code == 200

    def raise_for_error(self) -> None:
        """Raise ``ApiBusinessError`` unless this is a successful API response."""
        if not self.is_success:
            raise ApiBusinessError(self.ret_code, self.ret_msg)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ResponseDto[Any]":
        """Read both snake_case and camelCase variants of the response envelope."""
        return cls(
            ret_code=value.get("ret_code", value.get("retCode")),
            ret_msg=value.get("ret_msg", value.get("retMsg")),
            ret_count=value.get("ret_count", value.get("retCount")),
            ret_obj=value.get("ret_obj", value.get("retObj")),
        )
