from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Column, DateTime, Index, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.common import BIGINT_PK, JSON_TYPE, get_datetime_utc


class GoogleSheetBase(SQLModel):
    spreadsheet_id: str = Field(max_length=255)
    name: str | None = Field(default=None, max_length=255)
    registry_scope: str = Field(default="default", max_length=50)


class GoogleSheetCreate(GoogleSheetBase):
    pass


class GoogleSheetUpdate(SQLModel):
    spreadsheet_id: str | None = Field(default=None, max_length=255)
    name: str | None = Field(default=None, max_length=255)
    registry_scope: str | None = Field(default=None, max_length=50)


class GoogleSheet(GoogleSheetBase, table=True):
    __tablename__ = "google_sheet"
    __table_args__ = (
        UniqueConstraint("spreadsheet_id", "registry_scope", name="uq_sheet_scope"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BIGINT_PK, primary_key=True, autoincrement=True),
    )
    is_in_use: bool = False
    current_task_id: int | None = Field(
        default=None,
        sa_type=BigInteger,
        foreign_key="task.id",
        ondelete="SET NULL",
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class GoogleSheetPublic(GoogleSheetBase):
    id: int
    is_in_use: bool
    current_task_id: int | None = None
    created_at: datetime | None = None


class GoogleSheetsPublic(SQLModel):
    data: list[GoogleSheetPublic]
    count: int


class GoogleSheetTokenBase(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    is_active: bool = True
    current_in_use_count: int = 0
    total_usage_count: int = 0
    max_usage_count: int | None = None
    type_quotas: dict[str, Any] | None = Field(default=None, sa_type=JSON_TYPE)  # type: ignore


class GoogleSheetTokenCreate(GoogleSheetTokenBase):
    token_context: dict[str, Any]


class GoogleSheetTokenUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    max_usage_count: int | None = None
    type_quotas: dict[str, Any] | None = None


class GoogleSheetToken(GoogleSheetTokenBase, table=True):
    __tablename__ = "google_sheet_token"
    __table_args__ = (
        Index("idx_token_active_usage", "is_active", "current_in_use_count"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BIGINT_PK, primary_key=True, autoincrement=True),
    )
    token_context: dict[str, Any] = Field(sa_type=JSON_TYPE)  # type: ignore
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class GoogleSheetTokenPublic(GoogleSheetTokenBase):
    id: int
    token_context: dict[str, Any]
    created_at: datetime | None = None


class GoogleSheetTokensPublic(SQLModel):
    data: list[GoogleSheetTokenPublic]
    count: int
