# 04 · 后端移植

> 上级：[../migration-plan.md](../migration-plan.md) · 相关：[01-scope](01-scope-and-style.md)（范围）/ [02-database](02-database.md)（模型）/ [03-architecture](03-architecture.md)（worker）

## 1. 目标目录结构

```
backend/app/
├── api/
│   ├── deps.py                 # 修 P0 语法错误；SessionDep 沿用；业务路由不用 CurrentUser
│   ├── main.py                 # 注册 15 个新路由模块
│   └── routes/
│       ├── tasks.py            # 任务 CRUD + 动作
│       ├── task_results.py     # 结果/收益序列
│       ├── global_preview.py   backtest.py       model_summary.py
│       ├── exports.py          performance_analysis.py
│       ├── google_sheets.py    google_sheet_tokens.py
│       ├── scheduled_tasks.py  task_templates.py
│       ├── stocks.py           configs.py
│       ├── navigation.py       logs.py           meta.py
├── models/                     # __init__ 重导出（alembic env 依赖 app.models 命名空间）
│   ├── task.py  task_result.py  return_series.py  google_sheet.py
│   ├── scheduled_task.py  config.py  stock.py  navigation.py  backtest.py
├── crud/                       # __init__ 重导出；按域一文件，模板函数风格
├── services/                   # 业务服务（不 import fastapi）
│   ├── google_sheet/           # client.py token_service.py registry_service.py
│   ├── google_sheet_tasks/     # base.py c3.py c4.py c5.py c7.py check_policy.py kline_prep.py result_payload.py
│   ├── tasks/                  # creation.py runtime_api.py logs.py restart.py error_handling.py data_cleanup.py return_series.py errors.py
│   ├── backtest/               # report_query.py multi_product_preview.py training.py multi_product.py
│   ├── model_summary/          # extractor.py query.py backfill.py
│   ├── export/                 # csv_zip.py workbook.py word_template.py report_service.py report_charts.py
│   ├── performance_analysis/   # 原子包直移
│   ├── market/                 # kline_service.py yf_api.py akshare_api.py dfcf_api.py qq_api.py kline_adjustment.py
│   ├── notify/                 # dingtalk.py（webhook）
│   ├── config_manager.py  task_template_service.py  stock_search_service.py
│   ├── stock_metadata_service.py  navigation_service.py  log_query_service.py
├── core/
│   ├── config.py               # Settings 扩展（见 §5）
│   ├── workers.py              # TaskManager、TASK_TYPE_REGISTRY、poller/heartbeat/watchdog
│   └── scheduler.py            # croniter 循环 + job 子进程管理
├── worker.py                   # 入口：python -m app.worker [--job ID --instance ID]
stock_sdk/                      # 原样复制（生成的 HTTP 客户端）
```

## 2. Flask 解耦模式对照（逐类替换，不多不少）

| Flask 模式（旧） | FastAPI/模板模式（新） | 涉及文件 |
|---|---|---|
| `create_app()` 应用工厂 + `current_app.config` | `Settings` 单例直接 import；DB 用 `session_factory`（worker）或 `SessionDep`（路由） | config_manager、scheduler_service、task_watchdog、kline_service（1 处 L79-80）、backtest_*_service（BASE_URL）、google_sheet_tasks/*、task/runtime、task/logs |
| `g.current_user` | 删除（决策①）；`created_by_user_id` 不再写 | task_api POST、admin_api、export_api /model-summary |
| 蓝图 `Blueprint` + `@bp.route` + `jsonify` | `APIRouter` + decorator + Pydantic 响应模型 | 全部 routes/ |
| `@login_required / @admin_required` | 删除装饰器；无鉴权 | 全部业务路由 |
| `request.get_json()` / `request.args` | Pydantic 请求体 / Query 参数声明 | 全部 routes/ |
| `stream_with_context` + generator | `StreamingResponse`（NDJSON 保留逐行 `json.dumps`+\n 协议） | performance_analysis_api |
| `send_file` / BytesIO 下载 | `StreamingResponse` + Content-Disposition | export_api |
| `before_first_request` / bootstrap_app | `app/worker.py` main() 顺序初始化 | startup 逻辑 |
| `db`（Flask-SQLAlchemy 全局）+ `db.session` | `sqlmodel.Session(engine)` / 注入 Session；worker 线程各自 `with Session(engine)` | repositories → crud、全部 services |
| Flask-Migrate + create_all + ensure_* | Alembic 基线迁移一次到位 | 废弃 13 个 ensure_* 补丁 |
| `app.notifier = DingTalkNotifier` 挂 app | `services/notify/dingtalk.py` 普通模块函数 | app/__init__.py L96 |
| Flask `current_app.logger` | 标准 logging（worker 用 concurrent-log-handler） | initialize_logging 段 |

## 3. 文件移植映射（services 层，旧→新）

| 旧 | 新 | 改造量 |
|---|---|---|
| google_sheet_client.py (642) | services/google_sheet/client.py | 小：token 路径 Settings 化 |
| google_sheet_token_service.py (378) | services/google_sheet/token_service.py | 中：current_app→注入 |
| google_sheet_registry_service.py (162) | services/google_sheet/registry_service.py | 小 |
| task/creation.py | services/tasks/creation.py | 中：uuid4→BIGINT（原 L229/L654）；config 直接 dict |
| task/runtime.py | 拆 services/tasks/runtime_api.py（锁检查外的状态写库）+ core/workers.py（领取/执行） | 大：见 03 |
| task/facade.py + registry.py | core/workers.py | 大：进 worker 进程 |
| task/logs.py、restart.py、error_handling.py、data_cleanup.py | services/tasks/ 同名 | 小 |
| task_watchdog.py | core/workers.py watchdog 段 | 中：判活改心跳 |
| task/runtime_view.py | services/tasks/runtime_view.py | 中：仪表盘聚合 SQL 化（02 §4 #5/#6） |
| google_sheet_tasks/base.py (含 `_save_task_result` L968-1019) | 同名 | 中：写入热列+序列同事务 |
| google_sheet_tasks/c3/c4/c5/c7.py | 同名 | 小：json.loads 热点改热列读 |
| google_sheet_tasks/check_policy.py、kline_prep.py、result_payload.py | 同名 | 直移 |
| model_summary/extractor.py | 同名 | 小：改为写路径调用 + backfill 复用 |
| model_summary/query.py、jobs.py、service.py | query.py + backfill.py（jobs 裁剪） | 大：热列直查重写（02 §4 #3/#4） |
| backtest_report_query_service.py | services/backtest/report_query.py | 大：`_build_c3_summary_rows` L274-472 每行 50 次 metric 解析段按热列重写 |
| backtest_multi_product_preview.py、backtest_training_service.py、backtest_multi_product_service.py | services/backtest/ 同名 | 中 |
| backtest_excel_service.py、export_service.py、export_workbook_service.py、word_export_template.py、strategy_backtest_report_service.py、strategy_backtest_report_charts.py | services/export/ 同名 | 小（框架无关） |
| performance_analysis/ 包 | 同名 | 小：SSE/NDJSON 输出走 StreamingResponse |
| kline_service.py + utils/yf_api、akshare_api、dfcf_api、qq_api、kline_adjustment | services/market/ | 中：惰性导入 akshare/yfinance（见 §4） |
| scheduler_service.py (630) + scheduled_task_worker.py (151) | core/scheduler.py + services/tasks/cleanup_jobs.py | 大：APScheduler→croniter（03 §3.4）；job 白名单沿用 |
| config_manager.py | services/config_manager.py | 中：init_app→显式初始化 |
| stock_search/metadata/navigation/log_query/task_template_service、summary_contract | 同名 | 小 |
| utils/ding_talk_notifier.py | services/notify/dingtalk.py | 直移 |
| utils/task_error_utils.py、errors.py、exceptions/ | services/tasks/errors.py 等 | 直移 |
| repositories/（11 文件） | crud/ 包 | 中：查询问题按 02 §4 修复；窗口函数段重写 |
| stock_sdk/ | 原样复制 | 无 |
| ding_stream_service/ | 目录保留，改导入 | 中：create_app→新任务入口函数 |

## 4. 依赖与 Python 3.14

前置：**修 `backend/app/api/deps.py:36`**：`except InvalidTokenError, ValidationError:` → `except (InvalidTokenError, ValidationError):`（现态 SyntaxError，应用无法启动）。

| 包 | 版本策略 | 3.14 风险 | 兜底 |
|---|---|---|---|
| gspread、google-auth、google-auth-oauthlib、google-auth-httplib2 | latest | 无（纯 Python） | — |
| tenacity、croniter、PyMySQL、openpyxl、python-docx | latest | 无（纯 Python） | — |
| pandas / numpy | ≥2.3.3 / ≥2.3.2（cp314 轮子起点） | 低（需 latest） | uv 解析失败再谈 |
| matplotlib | latest（cp314 轮子） | 低 | 图表导出降级 |
| concurrent-log-handler、dingtalk-stream | latest | 中 | P0 冒烟暴露；不行就 vendor |
| akshare | latest | **高**（重依赖树） | 惰性导入：`try: import akshare` 失败→该源注册表跳过；核心 Sheet 校验链不依赖 |
| yfinance | latest | 中（curl_cffi/lxml 轮子） | 同上，降级 stock_sdk/dfcf/qq 源 |

冒烟脚本（P0 验收）：`uv sync` 后逐包 `python -c "import gspread, google.oauth2.credentials, tenacity, croniter, pandas, numpy, matplotlib, openpyxl, docx, pymysql, concurrent_log_handler, dingtalk_stream"`；akshare/yfinance 单独试、单独报。

## 5. 配置项（core/config.py Settings 新增）

| 字段 | 环境变量 | 默认 | 说明 |
|---|---|---|---|
| google_token_dir | GOOGLE_TOKEN_DIR | ./data | OAuth token 文件目录（挂卷） |
| stock_base_url | STOCK_BASE_URL | "" | DY.Stock.Api 地址 |
| task_max_workers | TASK_MAX_WORKERS | 8 | 全局并发（可被 SystemConfig 覆盖） |
| task_concurrency_<type> | 同名 | 4 | 按类型并发 |
| execution_delay_min/max | 同名 | 20 / 30 | 步骤间延迟秒（旧 config.py L261-268 语义） |
| scheduled_task_lock_timeout_hours | 同名 | 6 | 调度锁接管阈值 |
| worker_instance_id | WORKER_INSTANCE_ID | hostname | 领取/心跳标识 |
| ding_talk_access_token / ding_talk_secret | 同名 | "" | webhook 机器人 |
| ding_stream_client_id / secret | 同名 | "" | stream 服务 |
| base_url | BASE_URL | "" | 钉钉通知里的详情链接 |

`DATABASE_URL` 校验器改动：放开 `mysql+pymysql://` scheme（现仅 PostgreSQLDsn 重写 psycopg）；MySQL 引擎参数追加 `connect_args={"charset": "utf8mb4"}`。SystemConfig 表内配置（并发、清理保留天数等）沿用 config_manager 运行时读取，优先级高于 env 默认。

## 6. 测试移植

| 旧测试 | 处理 |
|---|---|
| tests/unit/ ~50 个（check_policy、kline、scheduler 锁、watchdog、task 生命周期、export、schemas、repositories） | 适配：`app_factory` fixture → `session_factory` + Settings fixture；SQLite per-test 沿用（JSON variant 降级 TEXT 不影响断言）；断言里 uuid 字符串改 int id |
| tests/integration/ 14 个（test_client 走 Flask） | 不直接移植；等价覆盖由模板式 FastAPI 集成测试承接：`backend/tests/api/routes/test_<域>.py`，用 `client` + `db` fixture（真实 PG via compose） |
| test_auth_* 4 个 | 不迁（决策①） |
| 顶层可移植性测试（MySQL/PG 方言、SDK bool 编码、startup 编排） | 方言测试保留思想 → P1 的三容器迁移验证脚本；SDK 测试直移 |

新增必须覆盖：worker 领取互斥（两 poller 抢同一行只成功一次）、stop_requested 桥接、心跳超时 watchdog 重置、热列抽取正确性（对 C3/C5 各一条样例 result JSON 的 golden 断言）、cron 锁逾期接管。

## 7. 移植验收口径（每个服务模块完成时）

1. lint.sh（mypy strict/ty/ruff）零新增告警
2. 对应单测移植并绿
3. 无 `flask`/`current_app`/`g` 残留导入（CI grep 检查）
4. 无窗口函数/CTE/方言 JSON 路径（grep `OVER`、`WITH RECURSIVE`、`->>`、`JSON_EXTRACT`）
5. 路由层 response_model 齐全，generate-client 已跑
