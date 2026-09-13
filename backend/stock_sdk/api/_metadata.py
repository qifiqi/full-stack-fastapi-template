"""Route metadata used to discover generated API operations at import time."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar


Operation = tuple[str, str, str, str]
FunctionT = TypeVar("FunctionT", bound=Callable[..., Any])


def endpoint(method: str, path: str) -> Callable[[FunctionT], FunctionT]:
    """Attach the documented HTTP method and path to an endpoint wrapper."""

    def decorate(function: FunctionT) -> FunctionT:
        setattr(function, "__dy_stock_endpoint__", (method, path))
        return function

    return decorate


def collect_operations(
    *groups: tuple[str, type[Any]],
) -> tuple[Operation, ...]:
    """Collect endpoint metadata from generated controller methods in definition order."""
    operations: list[Operation] = []
    for group_name, group_class in groups:
        for method_name, method in group_class.__dict__.items():
            metadata = getattr(method, "__dy_stock_endpoint__", None)
            if metadata:
                http_method, path = metadata
                operations.append((group_name, method_name, http_method, path))
    return tuple(operations)
