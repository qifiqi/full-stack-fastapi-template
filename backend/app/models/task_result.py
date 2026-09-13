from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Column, DateTime, Double, Index, Text
from sqlmodel import Field, SQLModel

from app.models.common import BIGINT_PK, JSON_TYPE, get_datetime_utc


class TaskResultBase(SQLModel):
    task_id: int = Field(
        sa_type=BigInteger,
        foreign_key="task.id",
        ondelete="CASCADE",
    )
    step_index: int
    success: bool = True
    error_message: str | None = Field(default=None, sa_type=Text)
    params: dict[str, Any] | None = Field(default=None, sa_type=JSON_TYPE)  # type: ignore
    result: dict[str, Any] | None = Field(default=None, sa_type=JSON_TYPE)  # type: ignore
    stock_code: str | None = Field(default=None, max_length=64)
    stock_name: str | None = Field(default=None, max_length=255)
    model_key: str = Field(default="default", max_length=255)
    model_name: str | None = Field(default=None, max_length=255)
    period_key: str | None = Field(default=None, max_length=32)
    year_label: str | None = Field(default=None, max_length=64)
    kline_range: str | None = Field(default=None, max_length=128)
    best_metric_name: str | None = Field(default=None, max_length=100)
    best_metric_value: float | None = Field(default=None, sa_type=Double)
    is_best: bool = False
    result_timestamp: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class TaskResultCreate(TaskResultBase):
    pass


class TaskResultUpdate(SQLModel):
    error_message: str | None = None
    stock_name: str | None = Field(default=None, max_length=255)
    model_name: str | None = Field(default=None, max_length=255)
    best_metric_name: str | None = Field(default=None, max_length=100)
    best_metric_value: float | None = None
    is_best: bool | None = None


class TaskResult(TaskResultBase, table=True):
    __tablename__ = "task_result"
    __table_args__ = (
        Index("idx_result_task_step", "task_id", "step_index"),
        Index("idx_result_stock", "stock_code"),
        Index("idx_result_task_best", "task_id", "is_best"),
        Index("idx_result_created", "created_at"),
        Index("idx_result_period", "period_key"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BIGINT_PK, primary_key=True, autoincrement=True),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class TaskResultPublic(TaskResultBase):
    id: int
    created_at: datetime | None = None


class TaskResultsPublic(SQLModel):
    data: list[TaskResultPublic]
    count: int


class TaskResultListItem(SQLModel):
    """Lightweight projection for list/polling endpoints: hot columns only,
    never the heavy params/result JSON payloads."""

    id: int
    task_id: int
    step_index: int
    success: bool
    error_message: str | None = None
    stock_code: str | None = None
    stock_name: str | None = None
    model_key: str
    model_name: str | None = None
    period_key: str | None = None
    year_label: str | None = None
    kline_range: str | None = None
    best_metric_name: str | None = None
    best_metric_value: float | None = None
    is_best: bool
    result_timestamp: datetime
    created_at: datetime | None = None


class TaskResultListPublic(SQLModel):
    data: list[TaskResultListItem]
    count: int
