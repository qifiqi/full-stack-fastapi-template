from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.common import BIGINT_PK, JSON_TYPE, get_datetime_utc


class StockMetadataBase(SQLModel):
    stock_code: str = Field(max_length=32)
    market_type: str = Field(max_length=8)
    name: str | None = Field(default=None, max_length=255)
    exchange: str | None = Field(default=None, max_length=50)


class StockMetadataCreate(StockMetadataBase):
    pass


class StockMetadataUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    exchange: str | None = Field(default=None, max_length=50)
    raw: dict[str, Any] | None = None


class StockMetadata(StockMetadataBase, table=True):
    __tablename__ = "stock_metadata"
    __table_args__ = (
        UniqueConstraint("stock_code", "market_type", name="uq_stock_market"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BIGINT_PK, primary_key=True, autoincrement=True),
    )
    raw: dict[str, Any] | None = Field(default=None, sa_type=JSON_TYPE)  # type: ignore
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(
            DateTime(timezone=True),
            default=get_datetime_utc,
            onupdate=get_datetime_utc,
            nullable=False,
        ),
    )


class StockMetadataPublic(StockMetadataBase):
    id: int
    raw: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class StocksMetadataPublic(SQLModel):
    data: list[StockMetadataPublic]
    count: int
