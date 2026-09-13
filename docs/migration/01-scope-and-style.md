# 01 · 迁移范围与风格约束

> 上级：[../migration-plan.md](../migration-plan.md) · 相关：[02-database](02-database.md) / [04-backend](04-backend.md)

## 1. 技术栈对照

| 层 | 源（google_sheet_task） | 目标（本模板） | 迁移方式 |
|---|---|---|---|
| Web 框架 | Flask + 17 API 蓝图 + 10 页面蓝图 | FastAPI + APIRouter | 重写路由层 |
| ORM | Flask-SQLAlchemy（models.py 933 行单文件） | SQLModel（models/ 包） | 按新 schema 重写 |
| 迁移 | Flask-Migrate，21 个版本，无基线，靠 create_all + ensure_* 补丁 | Alembic 全新基线 | 只建新，不搬旧 |
| 数据库 | MySQL（现用）/ PostgreSQL / SQLite | PostgreSQL（默认）/ MySQL 5.7.8+ / SQLite（单测） | 代码级双兼容 |
| 异步任务 | 进程内 ThreadPoolExecutor + APScheduler + watchdog 线程（Flask 进程内） | 独立 worker 服务（同源码不同入口） | 重构（见 03） |
| 调度 | APScheduler BackgroundScheduler + croniter 校验，子进程执行 | croniter 轮询循环 + 子进程执行 | 重写 ~50 行循环 |
| 前端 | Vue 3.5 + Element Plus + Naive UI + axios（53 个 .vue + 43 个 legacy HTML） | React 19 + TanStack + Radix + 生成式 SDK | 全量重写 |
| 鉴权 | 自研 JWT（access/refresh/token_version）+ RBAC + SSO 对接 | 模板自带 JWT 登录（单管理员） | 业务接口不接鉴权 |
| 部署 | nginx + gunicorn + Dockerfile | Traefik + `fastapi run --workers 4` + compose + 新增 worker 服务 | 新 compose 编排 |
| 限流 | Flask-Limiter | 无 | 不迁移（需要时按模板风格补 slowapi） |
| 日志 | concurrent-log-handler + logs/ 目录 | 同库沿用（worker 内使用） | 直移 |

## 2. 迁移清单（改造后迁移）

### 2.1 Google Sheets 集成
| 旧模块 | 说明 | 改造点 |
|---|---|---|
| `app/services/google_sheet_client.py`（642 行） | gspread 封装：OAuth token 文件（`data/token.json`，scopes=spreadsheets）、代理、断线重连、超时 | 纯逻辑直移；token 文件路径改 Settings 配置 |
| `app/services/google_sheet_token_service.py`（378 行） | token 池：用量计数、按任务类型配额、增量占用 `increment_usage` | `current_app` → Settings/Session 注入 |
| `app/services/google_sheet_registry_service.py`（162 行） | Sheet 注册表、占用状态 | 直移 |
| `app/routes/google_sheet_api.py` | Sheet/token 的 CRUD + import + reconcile | 重写为 FastAPI 路由 |

### 2.2 任务系统
| 旧模块 | 说明 | 改造点 |
|---|---|---|
| `app/services/task/creation.py` | 单建/批量建任务（股票 × 参数组合 × Sheet 笛卡尔积）、参数矩阵展开、config 校验（K线源归一、随机价规则）、重启任务复制 | uuid4→BIGINT；config JSON 不再 dumps/loads 往返 |
| `app/services/task/runtime.py` | start_task：Sheet 运行锁、token 预留、并发额度（全局 8/类型 4）、注册 stop Event、派发 | 拆两半：API 侧（写库）+ worker 侧（领取/执行），见 03 |
| `app/services/task/facade.py` + `registry.py` | TaskManager（进程内线程池）+ 6 类任务注册表 | 收敛到 worker 进程，注册表保留 |
| `app/services/task/logs.py` | 每步骤写 TaskLog（4000 字符截断） | 直移 |
| `app/services/task/restart.py` | 重启/重建任务语义 | 新建行 pending，由 worker 领取 |
| `app/services/task/error_handling.py` | 错误分类（可重试网络/Sheet 错误）、trace id | 直移 |
| `app/services/task_watchdog.py` | 60s 扫描：30 分钟无日志判死、强制驱逐重启（上限 3 次，`attempt=N/3` 记在 error_message） | 判活依据从进程内存改为心跳列 |
| `app/services/task/data_cleanup.py` | 按任务清结果/序列/锁 | 直移，挂到 cron 清理任务 |
| `app/services/google_sheet_tasks/`（base/c3/c4/c5/c7/check_policy/kline_prep/result_payload） | 四类 Sheet 校验引擎，写参数→轮询结果格→写回 | `_save_task_result` 增加热列抽取；`app=` 注入改显式依赖 |

### 2.3 结果与导出
| 旧模块 | 说明 | 改造点 |
|---|---|---|
| `app/services/model_summary/`（extractor/query/jobs） | 指标抽取 + 汇总查询 + 全量重建 | extractor 移到写入路径抽热列；query 改热列直查；jobs 裁剪为回填工具 |
| `app/services/backtest_report_query_service.py` | C3 汇总行/全局预览构建（最大 json.loads 热点） | 按热列重写查询段 |
| `app/services/backtest_multi_product_preview.py`、`backtest_training_service.py`、`backtest_multi_product_service.py` | 回测训练/多产品 | BASE_URL 注入，其余直移 |
| `app/services/export_service.py`（CSV/ZIP 流式）、`export_workbook_service.py`（openpyxl）、`word_export_template.py`（python-docx）、`strategy_backtest_report_service.py`、`strategy_backtest_report_charts.py`（matplotlib） | 导出家族 | 直移（与框架无关），路由层用 StreamingResponse |
| `app/services/performance_analysis/` | 性能分析 + 权重组合（NDJSON 流式） | 直移；StreamingResponse 输出 |
| `app/utils/return_series.py` | 收益序列 3 平行数组 build/parse | 重写为 return_series_point 行读写 |

### 2.4 行情数据
| 旧模块 | 说明 | 改造点 |
|---|---|---|
| `app/services/kline_service.py` | K线获取编排（多源兜底、复权） | 唯一一处 `current_app` 读改 Settings |
| `app/utils/yf_api.py`（yfinance，美股/BTC）、`akshare_api.py`（新浪 A股/港股/ETF/基金，0.5s 节流）、`dfcf_api.py`（东财）、`qq_api.py`（腾讯）、`kline_adjustment.py` | 行情源 | 惰性导入（3.14 轮子风险），失败不阻塞核心 |
| `stock_sdk/` | 内部 DY.Stock.Api 生成的 HTTP 客户端 | 原样复制 |

### 2.5 辅助
| 旧模块 | 说明 | 改造点 |
|---|---|---|
| `app/services/config_manager.py` | SystemConfig 数据库配置中心（init_app 模式） | Session 注入重写 |
| `app/services/task_template_service.py`、`stock_search_service.py`、`stock_metadata_service.py`、`navigation_service.py`、`log_query_service.py`、`summary_contract.py` | 各辅助服务 | 小改直移；navigation 去权限过滤 |
| `app/utils/ding_talk_notifier.py` | webhook 机器人通知 | 直移，挂 worker |
| `ding_stream_service/` | 钉钉 stream 机器人独立服务（list/restart/批量重启任务） | create_app 换成新任务入口，其余直移 |
| `app/utils/` 其余（errors、exceptions、task_error_utils 等） | 错误体系 | 直移 |
| `tests/`（约 50 个 service 级单测） | 单元测试 | 适配 SQLModel Session 后移植；4 个 auth 集成测试不迁 |

## 3. 不迁移清单

| 项 | 旧位置 | 理由 |
|---|---|---|
| 登录/JWT/刷新/改密 | `routes/auth_api.py`、`services/auth_service.py`、`repositories/auth_repository.py`、`utils/auth.py` | 决策①；模板自带登录替代 |
| SSO 对接 | `routes/sso.py`、`services/sso_service.py`（SSO_MAIN_VERIFY_URL 令牌交换） | 决策① |
| RBAC 模型与种子 | `models.py` User/Role/Permission + 两关联表、`config.py` PERMISSIONS/SSO_*、`flask init-rbac` | 决策① |
| 权限触点 | `Task.created_by_user_id`、导航 `permission` 列、`/meta/nav` 权限过滤、model-summary 用户过滤 | 决策① |
| 限流 | Flask-Limiter 全套 | 低价值，需要时补 slowapi |
| 页面蓝图 | `routes/pages/`（admin 13 页 + google_sheet + backtest 等静态页路由） | 决策④，React SPA 替代 |
| Legacy Jinja | `templates/` 43 个 HTML + `static/` | 同上 |
| Vue 登录权限页 | `Login.vue`、`admin/Users.vue`、`admin/Roles.vue`、`api/auth.js`、`useAuth.js`、路由守卫、axios 401 刷新逻辑 | 决策①④ |
| auth 测试 | `test_auth_password_policy.py`、`test_auth_token_lifecycle.py`、`test_sso_exchange.py`、`test_page_permission_sync.py` | 随功能废弃 |

## 4. 风格约束（强制）

> **整体风格、代码风格、接口风格一律按本模板现有惯例执行，不引入 Flask 风格。** 完整规范见 skill：`.agents/skills/fastapi-template-style/SKILL.md`（迁移写码前必须加载）。

1. **路由**：同步 `def` 端点；`APIRouter(prefix, tags)`；显式 `response_model`；`-> Any`；`SessionDep`；`HTTPException(404/403/400)`；删除返回 `Message`
2. **模型**：`XBase/XCreate/XUpdate/X(table=True)/XPublic/XsPublic` 四件套；`get_datetime_utc` + `DateTime(timezone=True)`
3. **CRUD**：普通函数 keyword-only；`model_validate(update=...)` 创建、`model_dump(exclude_unset=True)` + `sqlmodel_update` 更新
4. **配置**：pydantic-settings `Settings` + 顶层 `.env` + compose environment
5. **接口**：`/api/v1` 前缀标准 REST；skip/limit 分页；`XxxPublic {data, count}` 列表包装；**废除旧 `{status,code,message,data}` 信封**
6. **联调**：改 API 必跑 `scripts/generate-client.sh`；前端 React Query 消费生成的 SDK
7. **门禁**：`backend/scripts/lint.sh`（mypy --strict、ty、ruff 无 print）+ `backend/scripts/test.sh` 全绿
8. **安全红线**：SQL 全走 SQLAlchemy 表达式参数绑定，禁止拼接
9. **已批准偏离（仅 3 条）**：① BIGINT 自增主键；② `JSON().with_variant(JSONB(), "postgresql")`；③ 业务路由无 `CurrentUser`。其余"源项目这么写"不构成偏离理由
10. **MySQL 5.7 红线**：禁窗口函数/CTE/CHECK；JSON 列无默认值；best/dedupe 用标志列或 NOT EXISTS
