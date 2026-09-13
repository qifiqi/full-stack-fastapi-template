# 02 · 数据库重设计

> 上级：[../migration-plan.md](../migration-plan.md) · 相关：[03-architecture](03-architecture.md)（运行时锁语义）/ [04-backend](04-backend.md)（模型文件位置）

## 1. 设计原则

| 原则 | 说明 | 针对的旧问题 |
|---|---|---|
| BIGINT 自增主键 | 所有表 `id: Column(BigInteger, primary_key=True, autoincrement=True)` | 旧 Task 用 `String(36)` uuid4 主键：36 字节被 8 张表复制、InnoDB 随机写页分裂、无法按主键排序（处处 `order_by created_at desc, id desc` 兜底）、还支持 `ILIKE '%kw%'` 搜主键 |
| 恢复外键 | 全部 FK + `ON DELETE CASCADE`（弱引用用 `SET NULL`） | 旧库 `20260810_remove_fks` 故意删光外键，级联靠应用代码（data_cleanup.py）拼凑，TaskResult/Return/SummaryIndex 间存在孤儿风险 |
| 热列抽取 | 会出现在 WHERE/ORDER/分页过滤的字段一律抽成真实列 + 索引 | `Task.config ILIKE '%stock_code%'` 全表扫描（backtest_repository.py L74-82） |
| JSON 跨库列 | `sa_type=JSON().with_variant(JSONB(), "postgresql")` | 旧库 9+ 个 JSON 塞 TEXT 列：服务端不可查询、体积大、坏 JSON 静默降级 `{}` |
| 禁方言查询 | 代码不写 `->>`/`JSON_EXTRACT`/窗口函数/CTE | 保证 PG/MySQL 5.7.8+ 随意切换 |
| UTC 时间 | `get_datetime_utc()` + `DateTime(timezone=True)`（MySQL 存 naive UTC） | 旧库 datetime.now 本地时间 |
| Alembic 单基线 | 全新 `initial_schema` 一个迁移建全表，方言中立 DDL | 旧库无基线迁移，靠 create_all + 13 个 ensure_* 运行时补丁 |

**MySQL 5.7 兼容红线**（评审迁移与查询代码时逐条核对）：
1. 无窗口函数、无 CTE —— best/dedupe 用 `is_best` 标志列（写入时维护）或 `NOT EXISTS` 反连接
2. JSON 列不设默认值、不建函数索引（兜底：生成列索引，5.7.6+ 支持）
3. 不依赖 CHECK 约束（5.7 只解析不执行）
4. utf8mb4 下被索引 VARCHAR ≤ 64 字符（现有最长 64，远低于 3072 字节前缀上限）
5. 连接参数追加 `charset=utf8mb4`

## 2. 表定义

约定：所有表含 `created_at DATETIME NOT NULL`（UTC）；标注 updated_at 的含 `updated_at DATETIME NOT NULL`（onupdate）。类型以 SQLAlchemy/SQLModel 表达为准，括号内为 MySQL/PG 实际映射。

### 2.1 `task`（旧 `t_param_tasks`）

| 列 | 类型 | 空 | 默认 | 说明 |
|---|---|---|---|---|
| id | BIGINT PK | 否 | 自增 | 替代 uuid4 |
| name | VARCHAR(255) | 否 | | |
| description | TEXT | 是 | | |
| status | VARCHAR(20) | 否 | `pending` | pending / queued / running / success / error / cancelled |
| task_type | VARCHAR(50) | 否 | `google_sheet` | google_sheet / google_sheet_c4 / google_sheet_c5 / google_sheet_c7 / backtest_training / backtest_multi_product |
| config | JSON | 是 | | 完整任务配置（冷数据，整存整取，禁止路径查询） |
| spreadsheet_id | VARCHAR(64) | 是 | | ★写入时从 config 抽取 |
| stock_code | VARCHAR(32) | 是 | | ★从 config 抽取（批量任务为空） |
| market_type | VARCHAR(8) | 是 | | ★从 config 抽取 |
| current_step | INT | 否 | 0 | |
| total_steps | INT | 否 | 0 | |
| error_message | TEXT | 是 | | watchdog 重试计数沿用 `attempt=N/3` 约定 |
| stop_requested | BOOL | 否 | FALSE | ★新增：API 置位，worker 轮询后转 threading.Event |
| running_instance | VARCHAR(64) | 是 | | ★新增：持有执行的 worker 实例 id |
| heartbeat_at | DATETIME | 是 | | ★新增：worker 每 15s 刷新，watchdog 判活 |
| started_at | DATETIME | 是 | | 旧 start_time |
| finished_at | DATETIME | 是 | | 旧 end_time |

索引：`idx_task_status_created(status, created_at)`、`idx_task_type_status(task_type, status)`、`idx_task_spreadsheet(spreadsheet_id)`
删除（旧列）：`created_by_user_id`（决策①）。

旧表问题对照：uuid4 主键 / config TEXT 全量 json.loads 才能 serde（`to_dict` L350）/ 重启任务重复存储大 JSON / 耗时统计 Python 循环（task_repository.py L142-151 `yield_per(1000)` 累加）。

### 2.2 `task_log`（旧 `t_param_task_logs`）

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | BIGINT PK | 否 | 旧为 Int，统一 BIGINT |
| task_id | BIGINT FK→task CASCADE | 否 | 旧无 FK |
| level | VARCHAR(20) | 否 | |
| message | TEXT | 否 | 沿用 4000 字符截断（旧因整段收益序列写进日志才定的规范） |

索引：`idx_task_log_task_created(task_id, created_at)`（沿用旧 idx_task_logs_task_timestamp）

### 2.3 `task_result`（旧 `t_param_task_results` ＋ `t_param_task_result_summary_index` 合并重构）

| 列 | 类型 | 空 | 默认 | 说明 |
|---|---|---|---|---|
| id | BIGINT PK | 否 | 自增 | |
| task_id | BIGINT FK→task CASCADE | 否 | | 旧无 FK |
| step_index | INT | 否 | | |
| success | BOOL | 否 | TRUE | |
| error_message | TEXT | 是 | | |
| params | JSON | 是 | | ★旧 parameters TEXT——每行 ~10KB K线 JSON（旧迁移注释自述） |
| result | JSON | 是 | | ★旧 result TEXT/MySQL MEDIUMTEXT（旧迁移：C7 结果可超 64KB TEXT 上限） |
| stock_code | VARCHAR(64) | 是 | | ★写入时 extractor 抽取（替代汇总表） |
| stock_name | VARCHAR(255) | 是 | | ★ |
| model_key | VARCHAR(255) | 否 | `default` | ★ |
| model_name | VARCHAR(255) | 是 | | ★ |
| period_key | VARCHAR(32) | 是 | | ★ |
| year_label | VARCHAR(64) | 是 | | ★ |
| kline_range | VARCHAR(128) | 是 | | ★ |
| best_metric_name | VARCHAR(100) | 是 | | ★ |
| best_metric_value | DOUBLE | 是 | | ★（FLOAT→DOUBLE，避免指标精度丢失） |
| is_best | BOOL | 否 | FALSE | ★写入维护：同 (task_id, stock_code, model_key) 出现更优值时翻转新旧两行 |
| result_timestamp | DATETIME | 否 | | 旧 timestamp |
| created_at | DATETIME | 否 | | |

索引：`idx_result_task_step(task_id, step_index)`、`idx_result_stock(stock_code)`、`idx_result_task_best(task_id, is_best)`、`idx_result_created(created_at)`、`idx_result_period(period_key)`

旧表问题对照：params/result 每行 json.loads（`to_dict` 双解析；`get_export_entity` 因"预解析破坏双重解析语义"被迫返回裸串）；`return_series_id` 裸指针无外键；汇总表全表扫描重建（jobs.py 每 20 任务一批 delete+reinsert）、best_only=false 时 Python 过滤分页（query.py L121-206）、`page_summary_index` 物化全量再分页双重执行（backtest_repository.py L312-320）。

**抽取器复用**：旧 `model_summary/extractor.py` 的 `_extract_c3`/`_extract_c4_c5`/`_extract_backtest`（含 `upgrade_historical_metrics` 旧键名归一）逻辑保留，从"批处理重建"移到 `_save_task_result` 写入路径同步调用；解析失败在写入时报错，不再静默。

**回填工具**：`POST /api/v1/model-summary/rebuild` 保留为修复接口——对指定（或全部）已完成任务在 Python 中重算热列与 is_best 后批量 UPDATE；worker 单实例内执行，进度写 task_log。

### 2.4 `return_series_point`（旧 `t_param_task_results_return`）

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| task_result_id | BIGINT FK→task_result CASCADE | 否 | 联合主键首列 |
| date | DATE | 否 | 联合主键第二列，天然按日期聚簇 |
| index_return | DOUBLE | 是 | 旧 index_return JSON 数组元素 |
| start_return | DOUBLE | 是 | 旧 start_return JSON 数组元素 |

旧表问题对照：`stock_date`/`index_return`/`start_return` 三个**按位置耦合**的 JSON 数组 TEXT 列（return_series.py json.dumps×3 / json.loads×3），外加 stock_code/名称/起止日期/长度等冗余元数据列（stock_code 等已上浮到 task_result 热列，此处不再重复）。拆成关系行后：日期范围查询走主键前缀，无 JSON 解析。

写入：`_save_task_result` 同事务批量 INSERT（~250 交易日/条）。

### 2.5 `google_sheet`（旧 `t_param_google_sheet`）

| 列 | 类型 | 空 | 默认 | 说明 |
|---|---|---|---|---|
| id | BIGINT PK | 否 | 自增 | |
| spreadsheet_id | VARCHAR(255) | 否 | | |
| name | VARCHAR(255) | 是 | | |
| registry_scope | VARCHAR(50) | 否 | `default` | |
| is_in_use | BOOL | 否 | FALSE | 运行占用标志（worker 启动恢复时重置） |
| current_task_id | BIGINT FK→task SET NULL | 是 | | 旧为裸 String(36) 列 |

唯一约束：`(spreadsheet_id, registry_scope)`

### 2.6 `google_sheet_token`（旧 `t_param_google_sheet_tokens`）

| 列 | 类型 | 空 | 默认 | 说明 |
|---|---|---|---|---|
| id | BIGINT PK | 否 | 自增 | |
| name | VARCHAR(255) | 是 | | |
| token_context | JSON | 否 | | ★旧 TEXT；OAuth 用户令牌（token.json 内容），非服务账号 |
| is_active | BOOL | 否 | TRUE | |
| current_in_use_count | INT | 否 | 0 | |
| total_usage_count | INT | 否 | 0 | |
| max_usage_count | INT | 是 | | |
| type_quotas | JSON | 是 | | 按任务类型配额 |

索引：`idx_token_active_usage(is_active, current_in_use_count)`（沿用旧索引语义）

### 2.7 `scheduled_task`（旧 `t_param_scheduled_tasks`）

| 列 | 类型 | 空 | 默认 | 说明 |
|---|---|---|---|---|
| id | BIGINT PK | 否 | 自增 | |
| name | VARCHAR(255) | 否 | | |
| task_type | VARCHAR(50) | 否 | | cleanup_old_logs / cleanup_old_results / cleanup_old_data |
| cron_expression | VARCHAR(64) | 否 | | 5 段 cron，创建时 croniter 校验 |
| params | JSON | 是 | | ★旧 TEXT |
| enabled | BOOL | 否 | TRUE | |
| is_running | BOOL | 否 | FALSE | DB 运行锁 |
| running_instance_id | VARCHAR(64) | 是 | | |
| last_run_at | DATETIME | 是 | | 兼作锁逾期判断（>6h 可接管） |
| last_status | VARCHAR(20) | 是 | | |
| last_error | TEXT | 是 | |

锁语义（沿用旧 acquire_run_lock，跨实例互斥）：领取 = `UPDATE ... SET is_running=TRUE, running_instance_id=:id, last_run_at=now WHERE id=:id AND is_running=FALSE`，影响行数=1 才算抢到；释放 = 实例退出时 `WHERE running_instance_id=:id` 置回。

### 2.8 `system_config`（旧 `t_param_system_configs`）

| 列 | 类型 | 说明 |
|---|---|---|
| key | VARCHAR(100) PK | |
| value | TEXT NOT NULL | |
| updated_at | DATETIME NOT NULL | |

### 2.9 `task_template`（旧 `t_param_task_templates`）

| 列 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | |
| name | VARCHAR(255) NOT NULL | |
| description | TEXT NULL | |
| config | JSON NULL | ★旧 TEXT |
| updated_at | DATETIME NOT NULL | |

### 2.10 `stock_metadata`（旧 `t_param_stock_metadata`）

| 列 | 类型 | 空 | 说明 |
|---|---|---|---|
| id | BIGINT PK | 否 | |
| stock_code | VARCHAR(32) | 否 | 唯一约束 (stock_code, market_type) |
| market_type | VARCHAR(8) | 否 | |
| name | VARCHAR(255) | 是 | ★热列 |
| exchange | VARCHAR(50) | 是 | ★热列 |
| raw | JSON | 是 | 原始完整数据（冷） |
| updated_at | DATETIME | 否 | |

### 2.11 `navigation_menu_item`（旧 `t_param_navigation_menu_items`）

| 列 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | |
| title | VARCHAR(100) NOT NULL | |
| path | VARCHAR(255) NOT NULL | |
| icon | VARCHAR(100) NULL | |
| group_name | VARCHAR(50) NULL | |
| sort_order | INT NOT NULL DEFAULT 0 | |
| is_visible | BOOL NOT NULL DEFAULT TRUE | |

删除（旧列）：`permission`（决策①）。

### 2.12 `backtest_sheet_run_lock`（旧 `t_param_backtest_sheet_run_locks`）

| 列 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | |
| spreadsheet_id | VARCHAR(255) NOT NULL UNIQUE | 一个 Sheet 同时只允许一个任务 |
| task_id | BIGINT FK→task CASCADE NOT NULL | |
| task_type | VARCHAR(50) NULL | |
| updated_at | DATETIME NOT NULL | |

worker 启动恢复时删除全部残留行（进程内执行态，见 03）。

### 2.13 `backtest_product_result_cache`（旧 `t_param_backtest_product_result_cache`）

| 列 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | |
| batch_id | VARCHAR(64) NOT NULL | |
| cache_key | VARCHAR(64) NOT NULL | 唯一约束 (batch_id, cache_key) |
| result | JSON NOT NULL | ★旧 result_json TEXT |
| returns | JSON NULL | ★旧 returns_json TEXT |
| source_task_id | BIGINT FK→task SET NULL | |
| source_step_index | INT NULL | |

## 3. 删除不建

| 旧表 | 去向 |
|---|---|
| t_param_user / t_param_role / t_param_permission / t_param_user_roles / t_param_role_permissions | 决策①，模板自带 user 表替代入口门禁 |
| t_param_task_result_summary_index | 职责并入 task_result 热列（§2.3） |
| t_param_task_results_return | 拆为 return_series_point（§2.4） |

## 4. 性能修复清单（旧代码位置 → 新方案）

| # | 旧问题（位置） | 新方案 |
|---|---|---|
| 1 | 每次序列化 json.loads params+result（models.py `to_dict`×5；服务层 20+ 处：backtest_report_query_service.py L181/281/862/1005、runtime_view.py L144-145、export_service.py L145 等） | JSON(B) 服务端解析存储；写入时一次序列化，列表/分页/导出零应用层解析 |
| 2 | 汇总表全量重建：扫全部完成任务 × 全部结果，20 任务/批 delete+reinsert（model_summary/jobs.py L37-118） | 汇总表删除；extractor 移到写入路径；rebuild 仅作回填修复 |
| 3 | best_only=false 加载全部 (Task,TaskResult) 对，Python 过滤+分页（model_summary/query.py L121-206） | task_result 热列 WHERE + LIMIT/OFFSET + COUNT 直查 |
| 4 | page_summary_index 物化全量过滤集再分页（backtest_repository.py L312-320），依赖窗口函数（MySQL 8+） | is_best 标志 + idx_result_task_best 直查；兜底 NOT EXISTS；单查询分页 |
| 5 | 任务列表 Python 循环算平均耗时（task_repository.py L142-151） | SQL `AVG`（started_at/finished_at） |
| 6 | 仪表盘每任务加载全部结果只为计数，16 任务 × 每 15-30s 轮询（runtime_view.py L136-199、235-279；config.py L277-300） | COUNT/GROUP BY 聚合 + 最近 N 条热列直查 |
| 7 | `config ILIKE '%stock_code%'`（backtest_repository.py L74-82）；任务搜索 ILIKE 主键/名称 | spreadsheet_id/stock_code 热列等值；搜索限定 name/description 前缀索引友好写法 |
| 8 | 收益序列 3 平行 JSON 数组按位置耦合（return_series.py dumps×3/loads×3） | return_series_point 关系表，主键前缀日期范围查询 |
| 9 | 坏 JSON 静默降级 `{}`（models.py `_json_object_or_empty` L14-21）；导出被迫保留"双重解析语义"（task_result_repository.py L185-191） | JSON 列由 DB 保证结构；解析失败写入时报错 |
| 10 | 重启任务 json.loads→json.dumps 往返复制 config（creation.py L654+） | 新行 config 直接引用同值（ORM 赋值同一 dict，序列化一次） |
| 11 | dashboard/preview 一次性加载"数十 KB/行"config 投影（task_repository.py L297-305） | 热列投影替代 config 投影 |

## 5. SQLModel 骨架示例（task_result 节选）

```python
from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class TaskResult(SQLModel, table=True):
    __tablename__ = "task_result"
    __table_args__ = (
        Index("idx_result_task_step", "task_id", "step_index"),
        Index("idx_result_stock", "stock_code"),
        Index("idx_result_task_best", "task_id", "is_best"),
        Index("idx_result_period", "period_key"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    task_id: int = Field(foreign_key="task.id", nullable=False, ondelete="CASCADE")
    step_index: int
    success: bool = Field(default=True, sa_column=Column(Boolean, nullable=False))
    params: dict | None = Field(default=None, sa_type=JSON_TYPE)   # type: ignore
    result: dict | None = Field(default=None, sa_type=JSON_TYPE)   # type: ignore
    stock_code: str | None = Field(default=None, max_length=64)
    is_best: bool = Field(default=False)
    result_timestamp: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
```

其余表按同一模式落在 `backend/app/models/` 包（task.py / task_result.py / return_series.py / google_sheet.py / scheduled_task.py / config.py / stock.py / navigation.py / backtest.py），`__init__.py` 重导出保持 `from app.models import X` 兼容 alembic env。

## 6. 迁移与验证

- 基线迁移：`alembic revision --autogenerate -m "initial schema"` 后人工审查：无 PG 专属 DDL、索引名与 §2 一致、MySQL 5.7.8 可执行
- 验证矩阵：PostgreSQL 18 / MySQL 5.7 / MySQL 8.0 三个容器各执行 `alembic upgrade head` + 冒烟 CRUD
- 生产默认 PG（模板 DATABASE_URL）；切 MySQL 仅改 `DATABASE_URL=mysql+pymysql://...?charset=utf8mb4`
