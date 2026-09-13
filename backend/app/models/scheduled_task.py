from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, SQLModel

from app.models.common import BIGINT_PK, JSON_TYPE, get_datetime_utc


class ScheduledTaskBase(SQLModel):
    name: str = Field(max_length=255)
    task_type: str = Field(max_length=50)
    cron_expression: str = Field(max_length=64)
    params: dict[str, Any] | None = Field(default=None, sa_type=JSON_TYPE)  # type: ignore
    enabled: bool = True


class ScheduledTaskCreate(ScheduledTaskBase):
    pass


class ScheduledTaskUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    task_type: str | None = Field(default=None, max_length=50)
    cron_expression: str | None = Field(default=None, max_length=64)
    params: dict[str, Any] | None = None
    enabled: bool | None = None


class ScheduledTask(ScheduledTaskBase, table=True):
    __tablename__ = "scheduled_task"

    id: int | None = Field(
        default=None,
        sa_column=Column(BIGINT_PK, primary_key=True, autoincrement=True),
    )
    is_running: bool = False
    running_instance_id: str | None = Field(default=None, max_length=64)
    last_run_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    last_status: str | None = Field(default=None, max_length=20)
    last_error: str | None = Field(default=None, sa_type=Text)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class ScheduledTaskPublic(ScheduledTaskBase):
    id: int
    is_running: bool
    running_instance_id: str | None = None
    last_run_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None
    created_at: datetime | None = None


class ScheduledTasksPublic(SQLModel):
    data: list[ScheduledTaskPublic]
    count: int
