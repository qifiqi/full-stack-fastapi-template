# 05 · API 设计

> 上级：[../migration-plan.md](../migration-plan.md) · 相关：[04-backend](04-backend.md)（路由文件位置）/ [06-frontend](06-frontend.md)（消费方）

## 1. 全局约定

- 前缀：全部挂 `settings.API_V1_STR`（`/api/v1`）；业务路由不接鉴权依赖（决策①）
- 风格：模板式 REST——同步 `def`、显式 `response_model`、`HTTPException` 错误、删除返回 `Message`、docstring 一句英文（进 OpenAPI 摘要，驱动 TS 方法名）
- 分页：`skip: int = 0, limit: int = 100`；列表响应一律 `XxxPublic { data: [...], count: int }`
- 过滤参数：显式 Query 声明（status/task_type/stock_code/keyword…），禁止裸 dict 透传
- **废除旧信封**：不返回 `{status, code, message, data}`；错误语义由 HTTP 状态码 + `detail` 表达
- 时间字段：ISO 8601 UTC（Pydantic datetime 序列化）
- 改端点/模型 → 必跑 `scripts/generate-client.sh`（openapi-ts，`<Tag>Service.<operation>` 命名来自 `custom_generate_unique_id`：`{tag}-{name}`）

## 2. 端点清单

### 2.1 tasks（`api/routes/tasks.py`，prefix=/tasks，tag=tasks）
| 方法 | 路径 | 参数/请求体 | 响应 | 说明 |
|---|---|---|---|---|
| GET | `/` | skip/limit/status?/task_type?/spreadsheet_id?/stock_code?/keyword? | TasksPublic | 含统计聚合（总数、按状态计数、平均耗时 SQL AVG） |
| POST | `/` | TaskCreate | TaskPublic | 参数矩阵展开校验；仅写 pending 行 |
| POST | `/batch-create` | TaskBatchCreate（多股票×组合×Sheet） | list[TaskPublic] | 笛卡尔积展开，并发满置 queued |
| GET | `/{id}` | — | TaskPublic | 含 config |
| DELETE | `/{id}` | — | Message | 级联删结果/序列/日志（FK CASCADE） |
| PUT | `/{id}/config` | TaskConfigUpdate | TaskPublic | 仅 pending 可改，否则 409 |
| POST | `/{id}/cancel` | — | TaskPublic | 置 stop_requested；未运行 409 |
| POST | `/{id}/restart` | — | TaskPublic | 旧 stop-confirmation+restart 语义：校验后 worker 侧重跑 |
| POST | `/{id}/create-restart` | — | TaskPublic | 复制新任务行（config 原样，status=pending） |
| GET | `/{id}/logs` | skip/limit/level? | TaskLogsPublic | 按 created_at desc |
| GET | `/{id}/status-check` | — | TaskStatusCheck | 轻量：status/current_step/total_steps/heartbeat_at/最近一条日志；前端 15–30s 轮询用 |

### 2.2 task_results（prefix=/task-results，tag=task-results）
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/tasks/{task_id}/results`（挂在 tasks 下） | 分页 + success? 过滤；返回 TaskResultsPublic（热列 + 按需 params/result 摘要） |
| GET | `/{id}` | TaskResultPublic（含完整 params/result JSON） |
| DELETE | `/{id}` | Message（级联 return_series_point） |
| GET | `/{id}/return-series` | ?start=YYYY-MM-DD&end=… → list[ReturnSeriesPointPublic]（主键前缀范围查） |

### 2.3 global_preview（prefix=/global-preview，tag=global-preview）
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/tasks/{task_id}` | 全局预览初始 payload（热列直查重写 `_build_global_preview_initial_payload`） |
| POST | `/tasks/{task_id}/preview-group` | PreviewGroupRequest → 分组预览 payload |

### 2.4 backtest（prefix=/backtest，tag=backtest；训练/多产品统一命名空间，task_result 自带类型）
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/task-results/{id}` | 回测详情结果 |
| GET | `/task-results/{id}/export-preview` | 导出预览 |
| GET | `/task-summary/{task_id}` | 任务级汇总 |
| POST | `/calculate-ratios` | RatioCalcRequest → 比率计算 |
| PUT | `/ratios` | 保存比率修改 |

### 2.5 model_summary（prefix=/model-summary，tag=model-summary）
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | best_only?/stock_code?/market_type?/period_key?/task_type?/skip/limit → ModelSummaryPublic；is_best 热列直查 |
| POST | `/rebuild` | BackfillRequest（task_ids?/all）→ 触发 worker 回填（热列修复工具，非重建汇总表） |
| GET | `/rebuild/status` | 回填进度 |

### 2.6 exports（prefix=/exports，tag=exports）
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/tasks/{task_id}` | ?format=csv|zip → StreamingResponse（流式，替代旧全量 to_dict） |
| POST | `/tasks/batch` | ≤10 任务打包（沿用 MAX_BATCH_TASKS=10） |
| GET | `/global-previews/{task_id}` | 预览导出 |
| POST | `/backtest-reports/word` | Word 报告（python-docx） |
| GET | `/model-summary` | 汇总导出 Excel |

### 2.7 performance_analysis（prefix=/performance-analysis，tag=performance-analysis）
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/analyze` | 同步分析 |
| POST | `/v1/analyze` | NDJSON 流式（StreamingResponse，逐行 `json.dumps` + `\n`，前端 fetch reader 消费） |
| POST | `/v1/weight-combination` | 权重组合（结果可达 10 万行，分块流式输出） |

### 2.8 google_sheets / google_sheet_tokens
| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/google-sheets` | 列表（含 is_in_use）/新建 |
| GET/PUT/DELETE | `/google-sheets/{id}` | 详情/改/删 |
| GET/POST | `/google-sheet-tokens` | token 池列表（含用量）/导入 |
| GET/PUT/DELETE | `/google-sheet-tokens/{id}` | 详情/改（含启用）/删 |
| POST | `/google-sheet-tokens/import` | 批量导入 token 文件 |
| POST | `/google-sheet-tokens/reconcile` | 占用对账（DB↔实际使用） |

### 2.9 scheduled_tasks（prefix=/scheduled-tasks，tag=scheduled-tasks）
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 列表（含锁状态/last_run_at/next fire） |
| POST | `/` | 新建（croniter 校验表达式，非法 422） |
| PUT/DELETE | `/{id}` | 改/删（运行中删除 409） |
| POST | `/{id}/toggle` | 启停 |
| POST | `/{id}/run` | 立即运行（由 cron-scheduler 下个 tick 领取，见 03 §3.4） |
| GET | `/scheduler/stats` | worker 实例、在跑任务数、下次触发时间 |

### 2.10 其余
| 模块 | 端点 | 说明 |
|---|---|---|
| task_templates | GET/POST `/task-templates`；PUT/DELETE `/{id}` | 模板 CRUD |
| stocks | GET `/stocks/search`（?keyword&market）；GET `/stocks/{market}/{code}` | 搜索 + 元数据 |
| configs | GET `/configs`；GET `/configs/validate`；PUT `/configs/{key}` | SystemConfig 读写/校验 |
| navigation | GET/POST `/navigation-menu-items`；PUT/DELETE `/{id}` | 无 permission 列 |
| logs | GET `/logs`（?level&task_id&start&end&skip&limit）；GET `/logs/latest` | 日志查询 |
| meta | GET `/meta/versions`；GET `/meta/enums` | 枚举（task_type/status/market 等单一来源） |

## 3. 核心 schema 形状

```python
class TaskBase(SQLModel):
    name: str
    description: str | None = None
    task_type: str
    config: dict | None = None

class TaskPublic(TaskBase):
    id: int
    status: str
    spreadsheet_id: str | None
    stock_code: str | None
    current_step: int
    total_steps: int
    error_message: str | None
    stop_requested: bool
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime | None

class TasksPublic(SQLModel):
    data: list[TaskPublic]
    count: int
    statistics: TaskStatistics | None = None   # GET /tasks 携带：按状态计数、平均耗时秒

class TaskStatusCheck(SQLModel):
    id: int
    status: str
    current_step: int
    total_steps: int
    heartbeat_at: datetime | None
    running_instance: str | None
    latest_log: str | None

class TaskResultPublic(SQLModel):
    id: int
    task_id: int
    step_index: int
    success: bool
    error_message: str | None
    params: dict | None          # 完整 JSON（列表页用 TaskResultListItem，不带大 JSON）
    result: dict | None
    stock_code: str | None
    stock_name: str | None
    model_key: str
    model_name: str | None
    period_key: str | None
    best_metric_name: str | None
    best_metric_value: float | None
    is_best: bool
    result_timestamp: datetime

class TaskResultListItem(SQLModel):
    """列表/分页专用：热列 + 轻量 result 摘要，绝不携带 params/result 大 JSON"""
    id: int
    task_id: int
    step_index: int
    success: bool
    stock_code: str | None
    model_key: str
    period_key: str | None
    best_metric_name: str | None
    best_metric_value: float | None
    is_best: bool
    result_timestamp: datetime
```

设计规则：**大 JSON（params/result）只在详情端点返回**；列表/轮询端点一律轻量投影——这是"每次处理数据都慢"问题的 API 层配套。

## 4. 状态码约定

| 场景 | 码 |
|---|---|
| 成功 | 200（POST 创建也 200，模板风格不要求 201） |
| 不存在 | 404 `Xxx not found` |
| 状态冲突（cancel 未运行任务、运行中删模板、pending 外改 config） | 409 |
| 校验失败（cron 非法、参数矩阵非法） | 422（FastAPI 自动）+ 自定义 detail |
| worker 不可用（run 手动触发时无 worker 心跳） | 503 |

## 5. 与旧接口对照（前端联调查表用）

| 旧 | 新 | 主要变化 |
|---|---|---|
| GET `/api/tasks` | GET `/api/v1/tasks` | 信封→裸数据；统计内置 |
| POST `/api/tasks/batch-create` | POST `/api/v1/tasks/batch-create` | 不再同步启动，仅入队 |
| GET `/api/tasks/{id}/status-check` | 同名 v1 | 增 heartbeat_at/running_instance |
| GET `/api/tasks/{id}/logs` | 同名 v1 | 信封→裸数据 |
| GET `/api/results`、`/api/results/{id}` | `/api/v1/task-results…` | 归入 task-results 命名空间 |
| `/backtest-training/api/*`、`/backtest-multi-product/api/*` | `/api/v1/backtest/*` | 两套合一 |
| POST `/api/google-sheet/worksheets`、`/api/google-sheets*`、`/api/google-sheet-tokens/*` | `/api/v1/google-sheets*`、`/api/v1/google-sheet-tokens/*` | worksheets 合并进 sheets 域 |
| `/api/admin/scheduler/*` | `/api/v1/scheduled-tasks/*` + `/scheduler/stats` | 去 admin 前缀（无 RBAC） |
| `/api/admin/model-summary*` | `/api/v1/model-summary/*` | rebuild 语义改为热列回填 |
| `/api/meta/nav` | 删除 | 前端侧边栏本地定义（06） |
| `/api/auth/*`、`/api/auth/sso/exchange` | 模板自带 `/api/v1/login/*` | 仅入口登录 |
