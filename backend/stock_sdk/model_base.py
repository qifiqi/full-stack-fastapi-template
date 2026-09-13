"""Shared serialization behaviour for generated models."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Self


def _serialize(value: Any) -> Any:
    if isinstance(value, SerializableModel):
        return value.to_dict()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


class SerializableModel:
    """Base class for generated OpenAPI request and entity models."""

    def to_dict(self, *, exclude_none: bool = True) -> dict[str, Any]:
        """Convert the model to the JSON field names declared by OpenAPI."""
        values = {
            field.name: _serialize(getattr(self, field.name)) for field in fields(self)
        }
        if exclude_none:
            return {key: value for key, value in values.items() if value is not None}
        return values

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Self:
        """Create a model while ignoring fields absent from this SDK version."""
        known_fields = {field.name for field in fields(cls)}
        return cls(**{key: item for key, item in value.items() if key in known_fields})
