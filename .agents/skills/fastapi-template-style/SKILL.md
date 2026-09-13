---
name: fastapi-template-style
description: 本仓库（full-stack-fastapi-template）后端代码风格与 API 接口风格的强制约束。在本仓库编写或修改任何后端 Python 代码、API 路由、SQLModel 模型、CRUD、Alembic 迁移、后端测试，或做 google_sheet_task 迁移开发时必须加载本 skill——即使用户没有明确提到"风格"或"规范"。
---

# full-stack-fastapi-template 后端风格约束

本仓库的所有后端代码必须与模板现有代码风格一致。模板本身就是权威规范：**动手前先读同域的现有实现**（如 `backend/app/api/routes/items.py`、`backend/app/models.py`、`backend/app/crud.py`），新代码应当看起来像模板原生代码，而不是外来迁移代码。

为什么这么严格：模板带有完整的质量门禁（mypy --strict、ty、ruff）和自动生成的前端客户端（openapi-ts），任何风格偏离都会导致 lint 失败、客户端类型错乱或迁移冲突。

## 铁律速查

1. **同步端点**：路由处理函数用 `def`，不用 `async def`（模板全同步 SQLAlchemy）。数据库/网络阻塞调用不要出现在 async 上下文。
2. **显式 response_model**：每个端点声明 `response_model=XxxPublic`，返回注解 `-> Any`。
3. **依赖注入**：数据库会话用 `SessionDep`，不要手写 `Session(engine)`（请求作用域）；后台 worker 线程/子进程例外，自己管理 Session 生命周期。
4. **四件套模型**：每个实体 = `XBase` + `XCreate` + `XUpdate` + `X(table=True)` + `XPublic` + `XsPublic`，写在 `app/models/` 包（导出保持在 `app.models` 命名空间，alembic env 依赖它）。
5. **CRUD 是普通函数**：keyword-only 参数（`*, session: Session, ...`），不用类。创建用 `Model.model_validate(obj_in, update={...})`，更新用 `model_dump(exclude_unset=True)` + `db_obj.sqlmodel_update(...)`，之后 `add/commit/refresh`。
6. **错误处理**：用 `HTTPException` + 正确状态码（404 Not found、403 Not enough permissions、400 bad request），detail 用英文短句。不自定义全局异常信封。
7. **删除操作**返回 `Message(message="...")`。
8. **禁止 print**（ruff T201）；日志用 logging。
9. **时间**：一律 `get_datetime_utc()`（UTC）+ `sa_type=DateTime(timezone=True)`。
10. **SQL 安全红线**：一切查询走 SQLModel/SQLAlchemy 表达式（天然参数绑定），禁止 f-string/`%` 拼接 SQL，禁止把用户输入直接放进 `text()`。
11. **MySQL 5.7 兼容**：本库要求同时支持 PostgreSQL 与 MySQL 5.7.8+。查询和迁移**禁用窗口函数、CTE、CHECK 约束**（5.7 不支持或只解析不执行）；group 内取最优/best 去重用写入时维护的标志列（如 `is_best`）或 `NOT EXISTS` 反连接实现；JSON 列不设默认值、不建函数索引；被索引的 VARCHAR 长度 ≤ 64。

## 路由模块骨架（照此结构写）

```python
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import SessionDep
from app.models import Task, TaskCreate, TaskPublic, TasksPublic, TaskUpdate, Message

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/", response_model=TasksPublic)
def read_tasks(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve tasks.
    """
    count_statement = select(func.count()).select_from(Task)
    count = session.exec(count_statement).one()
    statement = (
        select(Task).order_by(col(Task.created_at).desc()).offset(skip).limit(limit)
    )
    tasks = session.exec(statement).all()
    return TasksPublic(data=[TaskPublic.model_validate(t) for t in tasks], count=count)


@router.get("/{id}", response_model=TaskPublic)
def read_task(session: SessionDep, id: int) -> Any:
    """
    Get task by ID.
    """
    task = session.get(Task, id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/", response_model=TaskPublic)
def create_task(*, session: SessionDep, task_in: TaskCreate) -> Any:
    """
    Create new task.
    """
    task = Task.model_validate(task_in)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.delete("/{id}")
def delete_task(session: SessionDep, id: int) -> Message:
    """
    Delete a task.
    """
    task = session.get(Task, id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    session.delete(task)
    session.commit()
    return Message(message="Task deleted successfully")
```

要点：docstring 是简短英文一句话（它进入 OpenAPI 摘要，驱动生成的 TS 方法名）；`col()` 用于需要类型化的列表达式；路由注册在 `app/api/main.py` 中 `api_router.include_router(xxx.router)`。

## 模型四件套（照此结构写）

```python
from datetime import UTC, datetime

from sqlalchemy import JSON, BigInteger, Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


class TaskBase(SQLModel):
    name: str = Field(max_length=255)
    status: str = Field(default="pending", max_length=20, index=True)


class TaskCreate(TaskBase):
    pass


class TaskUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, max_length=20)


class Task(TaskBase, table=True):
    __tablename__ = "task"
    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    config: dict | None = Field(
        default=None,
        sa_type=JSON().with_variant(JSONB(), "postgresql"),
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class TaskPublic(TaskBase):
    id: int
    created_at: datetime | None = None


class TasksPublic(SQLModel):
    data: list[TaskPublic]
    count: int
```

## 本仓库已批准的偏离（仅此三条，其余零容忍）

模板默认值在迁移场景下有三处已获批准的替换（决策记录见 `docs/migration-plan.md` §1.4）：

1. **主键用 BIGINT 自增**（`Column(BigInteger, primary_key=True, autoincrement=True)`），不用模板默认的 `uuid.UUID`。关联外键写 `Field(foreign_key="task.id", ondelete="CASCADE")`，并在父表关系上配 `cascade_delete=True`。
2. **JSON 列跨库写法**：`sa_type=JSON().with_variant(JSONB(), "postgresql")`——PG 得 JSONB，MySQL（5.7.8+）得原生 JSON，SQLite（单测）降级 TEXT。**代码中禁止方言级 JSON 路径查询**（`->>` / `JSON_EXTRACT`），可查询字段一律抽成真实列。
3. **业务路由不注入 `CurrentUser`**：迁移自 google_sheet_task 的业务接口不做用户/权限控制；模板自带登录仅作入口门禁，`login.py`/`users.py`/`private.py` 保持模板原样不动。

除这三条外，任何"源项目是这么写的"都不构成偏离模板风格的理由。

## 新增一个域模块的完整流程

1. 模型：`app/models/<域>.py` 定义四件套，在 `app/models/__init__.py` 重导出
2. 迁移：`cd backend && alembic revision --autogenerate -m "add xxx tables"` → 人工检查生成的迁移（不得含 PG 专属 DDL）→ `alembic upgrade head`
3. CRUD：`app/crud/<域>.py` 普通函数，`app/crud/__init__.py` 重导出
4. 业务服务：`app/services/<域>/`，服务层不 import fastapi（路由层才碰 HTTP 概念）
5. 路由：`app/api/routes/<域>.py`，注册进 `app/api/main.py`
6. 新配置：`app/core/config.py` 的 `Settings` 加字段 + 顶层 `.env` + `compose.yml` 的 backend.environment
7. 测试：`backend/tests/api/routes/test_<域>.py`，用现成 `client`、`db` fixture；service 级单测放 `backend/tests/unit/`
8. **重新生成前端客户端**：仓库根 `scripts/generate-client.sh`（改了任何端点/模型后必须跑）
9. 质量门禁：`backend/scripts/lint.sh`（mypy --strict + ty + ruff）和 `backend/scripts/test.sh` 全绿才算完成

## 测试风格

- 集成测试：普通函数 + `client`（TestClient）fixture，直接调 `client.get(f"{settings.API_V1_STR}/tasks/")`，断言 response.json() 与状态码；不 mock 数据库，走 compose 起的真实 Postgres
- 单元测试（服务逻辑）：per-test SQLite 文件库（`JSON().with_variant` 在 SQLite 降级为 TEXT，不影响），fixture 里 `SQLModel.metadata.create_all/drop_all`
- 服务层函数与 FastAPI 解耦（不 import fastapi），这样单测不需要起 HTTP 栈

## 提交前检查清单

- [ ] 新代码读起来像模板原生代码（同步端点、四件套、crud 函数、HTTPException）
- [ ] 无方言级 SQL、无拼接 SQL、无 print、时间全部 UTC
- [ ] 改过端点/模型 → 跑了 `scripts/generate-client.sh`
- [ ] `backend/scripts/lint.sh` 与 `backend/scripts/test.sh` 全绿
- [ ] 迁移文件不含 PG 专属 DDL，MySQL 5.7.8+ 可直接执行（无窗口函数/CTE/CHECK，JSON 列无默认值）
