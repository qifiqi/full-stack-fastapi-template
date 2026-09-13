from sqlmodel import Field, SQLModel

from app.models.backtest import (
    BacktestProductResultCache,
    BacktestProductResultCacheBase,
    BacktestProductResultCacheCreate,
    BacktestProductResultCachePublic,
    BacktestSheetRunLock,
    BacktestSheetRunLockBase,
    BacktestSheetRunLockCreate,
    BacktestSheetRunLockPublic,
)
from app.models.common import get_datetime_utc
from app.models.config import (
    SystemConfig,
    SystemConfigBase,
    SystemConfigCreate,
    SystemConfigPublic,
    SystemConfigsPublic,
    SystemConfigUpdate,
)
from app.models.google_sheet import (
    GoogleSheet,
    GoogleSheetBase,
    GoogleSheetCreate,
    GoogleSheetPublic,
    GoogleSheetsPublic,
    GoogleSheetToken,
    GoogleSheetTokenBase,
    GoogleSheetTokenCreate,
    GoogleSheetTokenPublic,
    GoogleSheetTokensPublic,
    GoogleSheetTokenUpdate,
    GoogleSheetUpdate,
)
from app.models.item import (
    Item,
    ItemBase,
    ItemCreate,
    ItemPublic,
    ItemsPublic,
    ItemUpdate,
)
from app.models.navigation import (
    NavigationMenuItem,
    NavigationMenuItemBase,
    NavigationMenuItemCreate,
    NavigationMenuItemPublic,
    NavigationMenuItemsPublic,
    NavigationMenuItemUpdate,
)
from app.models.return_series import (
    ReturnSeriesPoint,
    ReturnSeriesPointBase,
    ReturnSeriesPointCreate,
    ReturnSeriesPointPublic,
)
from app.models.scheduled_task import (
    ScheduledTask,
    ScheduledTaskBase,
    ScheduledTaskCreate,
    ScheduledTaskPublic,
    ScheduledTasksPublic,
    ScheduledTaskUpdate,
)
from app.models.stock import (
    StockMetadata,
    StockMetadataBase,
    StockMetadataCreate,
    StockMetadataPublic,
    StockMetadataUpdate,
    StocksMetadataPublic,
)
from app.models.task import (
    Task,
    TaskBase,
    TaskCreate,
    TaskLog,
    TaskLogBase,
    TaskLogCreate,
    TaskLogPublic,
    TaskLogsPublic,
    TaskPublic,
    TasksPublic,
    TaskStatistics,
    TaskStatusCheck,
    TaskTemplate,
    TaskTemplateBase,
    TaskTemplateCreate,
    TaskTemplatePublic,
    TaskTemplatesPublic,
    TaskTemplateUpdate,
    TaskUpdate,
)
from app.models.task_result import (
    TaskResult,
    TaskResultBase,
    TaskResultCreate,
    TaskResultListItem,
    TaskResultListPublic,
    TaskResultPublic,
    TaskResultsPublic,
    TaskResultUpdate,
)
from app.models.user import (
    UpdatePassword,
    User,
    UserBase,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)

__all__ = [
    "BacktestProductResultCache",
    "BacktestProductResultCacheBase",
    "BacktestProductResultCacheCreate",
    "BacktestProductResultCachePublic",
    "BacktestSheetRunLock",
    "BacktestSheetRunLockBase",
    "BacktestSheetRunLockCreate",
    "BacktestSheetRunLockPublic",
    "GoogleSheet",
    "GoogleSheetBase",
    "GoogleSheetCreate",
    "GoogleSheetPublic",
    "GoogleSheetToken",
    "GoogleSheetTokenBase",
    "GoogleSheetTokenCreate",
    "GoogleSheetTokenPublic",
    "GoogleSheetTokensPublic",
    "GoogleSheetTokenUpdate",
    "GoogleSheetUpdate",
    "GoogleSheetsPublic",
    "Item",
    "ItemBase",
    "ItemCreate",
    "ItemPublic",
    "ItemsPublic",
    "ItemUpdate",
    "NavigationMenuItem",
    "NavigationMenuItemBase",
    "NavigationMenuItemCreate",
    "NavigationMenuItemPublic",
    "NavigationMenuItemsPublic",
    "NavigationMenuItemUpdate",
    "NewPassword",
    "ReturnSeriesPoint",
    "ReturnSeriesPointBase",
    "ReturnSeriesPointCreate",
    "ReturnSeriesPointPublic",
    "ScheduledTask",
    "ScheduledTaskBase",
    "ScheduledTaskCreate",
    "ScheduledTaskPublic",
    "ScheduledTasksPublic",
    "ScheduledTaskUpdate",
    "StockMetadata",
    "StockMetadataBase",
    "StockMetadataCreate",
    "StockMetadataPublic",
    "StockMetadataUpdate",
    "StocksMetadataPublic",
    "SystemConfig",
    "SystemConfigBase",
    "SystemConfigCreate",
    "SystemConfigPublic",
    "SystemConfigsPublic",
    "SystemConfigUpdate",
    "Task",
    "TaskBase",
    "TaskCreate",
    "TaskLog",
    "TaskLogBase",
    "TaskLogCreate",
    "TaskLogPublic",
    "TaskLogsPublic",
    "TaskPublic",
    "TaskResult",
    "TaskResultBase",
    "TaskResultCreate",
    "TaskResultListItem",
    "TaskResultListPublic",
    "TaskResultPublic",
    "TaskResultsPublic",
    "TaskResultUpdate",
    "TaskStatistics",
    "TaskStatusCheck",
    "TaskTemplate",
    "TaskTemplateBase",
    "TaskTemplateCreate",
    "TaskTemplatePublic",
    "TaskTemplatesPublic",
    "TaskTemplateUpdate",
    "TasksPublic",
    "TaskUpdate",
    "Token",
    "TokenPayload",
    "UpdatePassword",
    "User",
    "UserBase",
    "UserCreate",
    "UserPublic",
    "UserRegister",
    "UsersPublic",
    "UserUpdate",
    "UserUpdateMe",
    "get_datetime_utc",
]


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
