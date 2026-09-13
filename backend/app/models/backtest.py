from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Column, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.common import BIGINT_PK, JSON_TYPE, get_datetime_utc


class BacktestSheetRunLockBase(SQLModel):
    spreadsheet_id: str = Field(max_length=255)
    task_id: int = Field(
        sa_type=BigInteger,
        foreign_key="task.id",
        ondelete="CASCADE",
    )
    task_type: str | None = Field(default=None, max_length=50)


class BacktestSheetRunLockCreate(BacktestSheetRunLockBase):
    pass


class BacktestSheetRunLock(BacktestSheetRunLockBase, table=True):
    __tablename__ = "backtest_sheet_run_lock"
    __table_args__ = (UniqueConstraint("spreadsheet_id", name="uq_lock_spreadsheet"),)

    id: int | None = Field(
        default=None,
        sa_column=Column(BIGINT_PK, primary_key=True, autoincrement=True),
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


class BacktestSheetRunLockPublic(BacktestSheetRunLockBase):
    id: int
    updated_at: datetime | None = None


class BacktestProductResultCacheBase(SQLModel):
    batch_id: str = Field(max_length=64)
    cache_key: str = Field(max_length=64)
    result: dict[str, Any] = Field(sa_type=JSON_TYPE)  # type: ignore
    returns: dict[str, Any] | None = Field(default=None, sa_type=JSON_TYPE)  # type: ignore
    source_task_id: int | None = Field(
        default=None,
        sa_type=BigInteger,
        foreign_key="task.id",
        ondelete="SET NULL",
    )
    source_step_index: int | None = None


class BacktestProductResultCacheCreate(BacktestProductResultCacheBase):
    pass


class BacktestProductResultCache(BacktestProductResultCacheBase, table=True):
    __tablename__ = "backtest_product_result_cache"
    __table_args__ = (UniqueConstraint("batch_id", "cache_key", name="uq_batch_cache"),)

    id: int | None = Field(
        default=None,
        sa_column=Column(BIGINT_PK, primary_key=True, autoincrement=True),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class BacktestProductResultCachePublic(BacktestProductResultCacheBase):
    id: int
    created_at: datetime | None = None
