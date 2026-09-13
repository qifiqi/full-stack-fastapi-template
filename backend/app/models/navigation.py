from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel

from app.models.common import BIGINT_PK, get_datetime_utc


class NavigationMenuItemBase(SQLModel):
    title: str = Field(max_length=100)
    path: str = Field(max_length=255)
    icon: str | None = Field(default=None, max_length=100)
    group_name: str | None = Field(default=None, max_length=50)
    sort_order: int = 0
    is_visible: bool = True


class NavigationMenuItemCreate(NavigationMenuItemBase):
    pass


class NavigationMenuItemUpdate(SQLModel):
    title: str | None = Field(default=None, max_length=100)
    path: str | None = Field(default=None, max_length=255)
    icon: str | None = Field(default=None, max_length=100)
    group_name: str | None = Field(default=None, max_length=50)
    sort_order: int | None = None
    is_visible: bool | None = None


class NavigationMenuItem(NavigationMenuItemBase, table=True):
    __tablename__ = "navigation_menu_item"

    id: int | None = Field(
        default=None,
        sa_column=Column(BIGINT_PK, primary_key=True, autoincrement=True),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class NavigationMenuItemPublic(NavigationMenuItemBase):
    id: int
    created_at: datetime | None = None


class NavigationMenuItemsPublic(SQLModel):
    data: list[NavigationMenuItemPublic]
    count: int
