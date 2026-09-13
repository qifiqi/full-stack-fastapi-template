from datetime import datetime

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, SQLModel

from app.models.common import get_datetime_utc


class SystemConfigBase(SQLModel):
    key: str = Field(primary_key=True, max_length=100)
    value: str = Field(sa_type=Text)


class SystemConfigCreate(SystemConfigBase):
    pass


class SystemConfigUpdate(SQLModel):
    value: str


class SystemConfig(SystemConfigBase, table=True):
    __tablename__ = "system_config"

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


class SystemConfigPublic(SystemConfigBase):
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SystemConfigsPublic(SQLModel):
    data: list[SystemConfigPublic]
    count: int
