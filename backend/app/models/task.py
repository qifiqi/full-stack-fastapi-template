from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Column, DateTime, Index, Text
from sqlmodel import Field, SQLModel

from app.models.common import BIGINT_PK, JSON_TYPE, get_datetime_utc


class TaskBase(SQLModel):
    name: str = Field(max_length=255)
    description: str | None = Field(default=None, sa_type=Text)
    task_type: str = Field(default="google_sheet", max_length=50)
    config: dict[str, Any] | None = Field(default=None, sa_type=JSON_TYPE)  # type: ignore


class TaskCreate(TaskBase):
    pass


class TaskUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    config: dict[str, Any] | None = None


class Task(TaskBase, table=True):
    __tablename__ = "task"
    __table_args__ = (
        Index("idx_task_status_created", "status", "created_at"),
        Index("idx_task_type_status", "task_type", "status"),
        Index("idx_task_spreadsheet", "spreadsheet_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BIGINT_PK, primary_key=True, autoincrement=True),
    )
    status: str = Field(default="pending", max_length=20)
    spreadsheet_id: str | None = Field(default=None, max_length=64)
    stock_code: str | None = Field(default=None, max_length=32)
    market_type: str | None = Field(default=None, max_length=8)
    current_step: int = 0
    total_steps: int = 0
    error_message: str | None = Field(default=None, sa_type=Text)
    stop_requested: bool = False
    running_instance: str | None = Field(default=None, max_length=64)
    heartbeat_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    started_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class TaskPublic(TaskBase):
    id: int
    status: str
    spreadsheet_id: str | None = None
    stock_code: str | None = None
    market_type: str | None = None
    current_step: int
    total_steps: int
    error_message: str | None = None
    stop_requested: bool
    running_instance: str | None = None
    heartbeat_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None


class TaskStatistics(SQLModel):
    total: int
    by_status: dict[str, int]
    avg_running_seconds: float | None = None


class TasksPublic(SQLModel):
    data: list[TaskPublic]
    count: int
    statistics: TaskStatistics | None = None


class TaskStatusCheck(SQLModel):
    id: int
    status: str
    current_step: int
    total_steps: int
    heartbeat_at: datetime | None = None
    running_instance: str | None = None
    latest_log: str | None = None


class TaskLogBase(SQLModel):
    task_id: int = Field(
        sa_type=BigInteger,
        foreign_key="task.id",
        ondelete="CASCADE",
    )
    level: str = Field(default="INFO", max_length=20)
    message: str = Field(sa_type=Text)


class TaskLogCreate(TaskLogBase):
    pass


class TaskLog(TaskLogBase, table=True):
    __tablename__ = "task_log"
    __table_args__ = (Index("idx_task_log_task_created", "task_id", "created_at"),)

    id: int | None = Field(
        default=None,
        sa_column=Column(BIGINT_PK, primary_key=True, autoincrement=True),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class TaskLogPublic(TaskLogBase):
    id: int
    created_at: datetime | None = None


class TaskLogsPublic(SQLModel):
    data: list[TaskLogPublic]
    count: int


class TaskTemplateBase(SQLModel):
    name: str = Field(max_length=255)
    description: str | None = Field(default=None, sa_type=Text)
    config: dict[str, Any] | None = Field(default=None, sa_type=JSON_TYPE)  # type: ignore


class TaskTemplateCreate(TaskTemplateBase):
    pass


class TaskTemplateUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    config: dict[str, Any] | None = None


class TaskTemplate(TaskTemplateBase, table=True):
    __tablename__ = "task_template"

    id: int | None = Field(
        default=None,
        sa_column=Column(BIGINT_PK, primary_key=True, autoincrement=True),
    )
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


class TaskTemplatePublic(TaskTemplateBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskTemplatesPublic(SQLModel):
    data: list[TaskTemplatePublic]
    count: int
