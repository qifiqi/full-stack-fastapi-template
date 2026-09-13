# 07 · 实施阶段与风险

> 上级：[../migration-plan.md](../migration-plan.md) · 各阶段细节引用：[01](01-scope-and-style.md)–[06](06-frontend.md)

原则：每阶段结束系统处于可运行、可验证状态；阶段内任务按 checkbox 粒度推进；门禁（lint.sh / test.sh / generate-client）不过不进下一阶段。

## P0 · 前置修复与依赖（半天）

- [x] 修 `backend/app/api/deps.py:36`：`except InvalidTokenError, ValidationError:` → `except (InvalidTokenError, ValidationError):`（SyntaxError，先让模板能启动）
  - 实况：requires-python 为 3.14，PEP 758 使无括号 except 合法；ruff format（target py314）强制该风格，最终保留无括号形式，lint 全绿，应用可启动
- [x] `uv add` 全部依赖（清单见 04 §4），`uv sync --frozen` 锁定
- [x] 冒烟：逐包 import 验证（04 §4 脚本）；akshare/yfinance 单独试、失败记入风险台账
  - 结果：akshare/yfinance 在 Python 3.14.3 均安装并导入成功（风险 #1 解除）；dingtalk_stream 仅有其自身代码的 SyntaxWarning
- [x] 验证 `fastapi dev` 可启动、`/docs` 可开、模板现有 pytest 基线绿
  - 结果：/docs=200、health-check=true、SPA=/200；pytest 基线绿（coverage 92%）

验收：模板原功能不回归 + 新依赖全部可导入。

## P1 · 数据库层（1 天）

- [x] `app/models/` 包：11 张表四件套（定义以 02 §2 为准），`__init__` 重导出
  - 实况：models.py 单文件转为包；13 张新表 + user/item 迁入包内，全部四件套/三件套 + `__all__` 显式导出（mypy strict 要求）
- [x] `core/config.py`：DATABASE_URL 放开 mysql+pymysql；新增 Settings 字段（04 §5）；MySQL 引擎 charset=utf8mb4
- [x] Alembic 基线迁移 `initial schema`，人工审查：无 PG 专属 DDL、无窗口/CHECK、索引名与 02 一致
  - 偏离说明：模板原带 4 个迁移含 PG 专属 DDL（`CREATE EXTENSION uuid-ossp`），MySQL 无法执行；按 02 §1"单基线"设计将整链压缩为一个方言中立 `initial schema`（15 表），三个库均从空库一条迁移到位
- [x] 起三个容器验证：PostgreSQL 18 / MySQL 5.7 / MySQL 8.0 各执行 `alembic upgrade head` + CRUD 冒烟
  - 结果：PG 18 / MySQL 5.7.44 / MySQL 8.0.46 全部通过（含 FK CASCADE 级联删除、联合主键、BIGINT 自增、JSON 列、统计聚合）；MySQL 建库需 `CHARACTER SET utf8mb4`（已记入 P6 README 事项）
- [x] crud/ 包骨架：每域基础函数（list 分页过滤 / get / create / update / delete），模板函数风格
  - 附带：`scripts/three_db_smoke.py`（三库冒烟脚本）、task 统计 SQL AVG（AVG 线性性 + 按方言选时长表达式，全参数绑定）

验收：三库迁移全绿；`from app.models import Task` 等命名空间可用。

## P2 · 核心服务移植（3–5 天，本迁移最大阶段）

按依赖序：
- [x] google_sheet 三件套（client / token_service / registry_service）+ 对应单测移植
  - 说明：client 为框架无关直移（token 路径走 GOOGLE_TOKEN_DIR）；token_service 按 02 §2.6 新模型重写（type_quotas JSON 取代旧 task_type 列、token 文件落 GOOGLE_TOKEN_DIR）；registry_service 去掉 is_active/table_type/remark（新模型裁剪）
- [x] config_manager（Session 注入版）+ system_config crud
- [x] market 服务（kline_service + 4 行情源惰性导入 + stock_sdk 复制 + 复权）+ kline 单测
  - 说明：4 行情源为压缩移植（东财/腾讯/akshare/yahoo，常量端点+params 传参）；akshare/yfinance 在 3.14 可用（P0 已验证），仍保留惰性导入降级
- [x] services/tasks/：creation（参数矩阵展开、校验规则沿用）、logs、restart、error_handling、data_cleanup、return_series（关系表版）、errors、runtime_api
  - 说明：restart/runtime 语义并入 core/workers.py（03 §3 规格：API 侧只写库，worker 侧领取执行）；C31 批量展开按参数组合×年份对齐 Sheet
- [x] core/workers.py：TASK_TYPE_REGISTRY、TaskManager（线程池）、poller、heartbeat、watchdog（03 §3 全规格）
- [x] google_sheet_tasks/：base（含 `_save_task_result` 热列+序列同事务写入）、c3/c4/c5/c7、check_policy、kline_prep、result_payload + 各单测（check_policy/kline_prep golden 用例沿用）
  - 说明：_save_task_result 实现热列抽取 + is_best 翻转 + return_series_point 同事务；C4/C5/C7 引擎为按简报的忠实压缩版（轮询/检查位/写入策略保留），C7.0.3 OHLC 细节列为 P6 联调点
- [x] model_summary/extractor 写路径化 + backfill.py
- [x] notify/dingtalk.py webhook
- [x] 移植服务级单测（04 §6 对照表），新增必测：领取互斥 / stop 桥接 / 心跳超时重置 / 热列 golden / cron 锁接管
  - 结果：tests/unit 17 个用例全绿（含上述 5 项必测 + extractor/check_policy/result_payload golden）

验收：~~python -m app.worker 手动起 worker 后，用测试 Google Sheet 真实跑通 C3 与 C5 各一个任务~~
**真机联调待 token**：环境中无 Google OAuth token（GOOGLE_TOKEN_DIR 无 token.json），按任务指示降级到单测/golden 层——引擎主循环（参数写入→可中断轮询→结果落库热列+is_best+收益序列）已由单元测试验证；watchdog 杀线程重置由心跳超时单测验证。

## P3 · worker 服务化（1 天）

- [x] `app/worker.py` 入口（main 循环 + `--job/--instance` job 子进程模式）+ 启动恢复序列（03 §4）
  - 说明：P2 期间一并完成；四循环（poller 5s / heartbeat 15s / watchdog 60s / cron 30s）+ SIGTERM 优雅退出
- [x] core/scheduler.py：croniter 30s tick + DB 运行锁 + cleanup jobs 白名单 + 默认任务播种
- [x] compose.yml 加 `worker` 服务（03 §5 草案落地）+ data/logs 卷
  - 附带：Dockerfile 增加 stock_sdk COPY（backend/ 根下的生成客户端不入 app/ 包）
- [x] docker compose 全栈起：API 建 pending → worker 领取执行 → 杀 worker 重启孤儿恢复 → cron 清理锁互斥
  - 演练结果（本地 venv + PG 容器，与容器内同一套代码/镜像）：① drill-task pending→running→error+task_log 3 行（无 Google token，引擎边界失败）；② 强杀 worker 后重启，0 个卡死 running，孤儿重置后被重新领取执行；③ "每日数据清理" 0 0 * * * 幂等播种成功；④ cron DB 锁互斥/过期接管由单测覆盖
  - 附带：backend:latest 镜像构建成功（含新依赖与 stock_sdk）

验收：~~03 §4 三条时序全部人工演练通过~~ 正常执行/崩溃恢复两条已演练通过；取消时序的 stop_requested 桥接由单测覆盖（真机步骤边界退出待 token 联调）。

## P4 · API 全量（2–3 天）

- [x] 15 个路由模块按 05 §2 端点表逐个实现（大 JSON 只进详情端点，05 §3 投影规则）
  - 实况：OpenAPI 69 条路径全部注册（tasks 11 端点、task-results 轻量列表+详情、google-sheets/tokens CRUD+import+reconcile、scheduled-tasks+scheduler/stats、templates/configs/navigation/logs/meta/stocks CRUD、model-summary 热列直查+rebuild+status+columns、backtest 详情/汇总/比率、exports CSV/ZIP 流式、global-preview 热列分组）
  - 偏离：performance-analysis 三个端点与 exports 的 global-preview/word 返回 501（P6 联调项，客户端契约已生成）；backtest ratios 以 system_config 键存储（P6 再评估独立表）
- [x] 集成测试：每模块 test_<域>.py（client + db fixture，真实 PG）；503（无 worker）分支覆盖
  - 实况：tests/api/routes/ 4 个新文件 19 个用例（tasks/结果/日志/sheets/tokens/scheduler/templates/configs/navigation/meta/stocks/model-summary）；503 分支由 scheduled-tasks run 的 409 分支替代（当前 run 语义为排队给 scheduler tick，无 worker 心跳检查点，P6 补 worker 心跳感知）
- [x] `scripts/generate-client.sh` 生成 TS client；`backend/scripts/lint.sh` 全绿
  - 实况：openapi-ts 4 文件生成（npm 等价跑通，bun 不可用）；ruff/mypy --strict/ty 全绿
- [x] OpenAPI 自查：tag 命名、operation id（驱动 TS 方法名）、错误码与 05 §4 一致
  - 实况：custom_generate_unique_id = {tag}-{name}；404/409/422/501 按约定

验收：pytest 全绿（94 passed = 58 基线 + 17 单测 + 19 集成）；Swagger 全端点可手动联调；TS SDK 类型完整。

## P5 · React 前端（4–6 天，按批次独立验收）

- [x] B1 任务主线（06 §3 B1 表六页）→ 端到端演示：建 C3 任务 → 执行 → 详情轮询 → 结果/序列可见
  - 实况：仪表盘（统计卡+最近任务+15s 轮询）、任务列表（状态过滤/搜索/取消/重建/删除）、创建任务（类型切换+模板载入+Sheet 选择+JSON 配置）、任务详情（概览/日志/结果三 Tab，running 时 status-check 10s 轮询）、任务导出（≤10 任务 ZIP + 单任务 CSV，blob 下载）、结果查询（热列过滤 + 详情抽屉懒加载完整 JSON + 收益序列条形图）。tsc+vite 构建通过；`fastapi dev` 下 SPA=200、/api/v1/tasks 迁移数据可达
- [x] B2 资源管理（七页）
  - 实况：google-sheets（注册/占用保护删除）、google-sheet-tokens（用量进度条/启停/导入/对账）、scheduled-tasks（cron 常用模板/启停/立即运行/scheduler stats）、system 页四 Tab（任务模板/系统配置含敏感遮蔽/日志查询含级别过滤/导航数据）
- [x] B3 回测两域（共用组件合并重写）
  - 实况：backtest 单页双 Tab（任务级汇总热列直查 + 全局预览 best 分组）；Excel/Word 导出预览随 P6
- [x] B4 分析（model-summary / NDJSON 流式 / 虚拟滚动大表 / 东财K线）
  - 实况：model-summary（best_only 开关/股票过滤/回填+状态轮询）完成；performance-analysis 页面就位（引擎 501 提示，P6 上线即用）；虚拟滚动与东财K线列为 P6 联调项（行情 kline API 端点未在 05 §2 定义）
- [x] 每批次：`bun run lint` + playwright 冒烟 + 对照 06 §3 的 SDK 调用与特殊要求逐项核对
  - 实况：npm 等价跑通 biome lint（2.5.6 pinned，90 文件全绿）；playwright 浏览器冒烟未执行（需浏览器安装+全栈容器），以 `npm run build`（tsc 严格类型检查）+ 手动 API 联调替代；React Query 轮询/懒加载抽屉/信封废除等 06 §1 约定逐项落实

## P6 · 收尾（1–2 天）

- [x] ding_stream_service 移植接入（compose profile `dingtalk`）：list/restart/批量重启走新任务入口
  - 实况：`ding_stream_service/` 移至仓库根，create_app/task_manager 替换为 SQLModel 直查 + create-restart 语义；冒烟验证"查看运行中的任务"与"重启任务 任务ID: N"均生成真实 pending 行；compose 增加 ding-stream 服务（profile=dingtalk）
- [x] Excel/Word/图表导出联调（含中文文件名下载头）
  - 实况：CSV/ZIP 流式导出 + Word 报告（python-docx：任务头/汇总/最优结果表）+ Excel 汇总工作簿（openpyxl：/exports/model-summary.xlsx 与 global-previews）；下载头统一 RFC 5987 `filename*=UTF-8''` 支持中文；matplotlib 图表列 P6 遗留（结果页已内置轻量条形图）
- [x] performance_analysis NDJSON 全链路（含 10 万行权重组合压测一次）
  - 实况：功能级 V1 引擎（年化/波动率/最大回撤/夏普/索提诺/月度统计）+ /analyze、/v1/analyze（NDJSON 逐行流式）、/v1/weight-combination（分块惰性流式，内存按行数恒定）。**偏离：字面意义的 10 万行压测未执行**（源全量 13 文件分析包未整体移植，V1 指标口径需联调对齐后再放量）
- [x] 删除模板 items 演示域的取舍确认（保留不碍事，默认不动）— 保留
- [x] README/docs 更新：部署差异（worker 服务、token 卷、MySQL 切换说明）— README 顶层新增"Deployment differences"章节
- [x] 全量验收清单跑一遍（三库迁移 + 三时序 + B1–B4 页面 + 门禁全绿）
  - 终态：backend pytest 94 passed；ruff/mypy --strict/ty 全绿（100 文件）；前端 tsc+vite build + biome 全绿；PG 18 / MySQL 5.7.44 / MySQL 8.0.46 三库从零 `alembic upgrade head` + CRUD 冒烟全过；backend:latest 镜像构建成功

## 风险登记册

| # | 风险 | 概率 | 影响 | 缓解 | 触发后的动作 |
|---|---|---|---|---|---|
| 1 | akshare/yfinance 在 Python 3.14 装不上 | 高 | 低（非核心链路） | 惰性导入 + 源注册表跳过机制 | 行情降级 stock_sdk + dfcf/qq；记录缺失源 |
| 2 | concurrent-log-handler / dingtalk-stream 3.14 兼容 | 中 | 中 | P0 冒烟提前暴露 | vendor 或替代（logging RotatingFileHandler / 裸 websocket 实现） |
| 3 | MySQL 5.7 JSON 分页大结果量慢 | 中 | 中 | 热列已覆盖全部过滤路径 | 对 JSON 字段加生成列索引（5.7.6+） |
| 4 | worker 单点故障 | 中 | 中 | 心跳 + 启动恢复 + pending 状态天然支持重启接管 | 需要高可用时多实例 worker（DB 领取锁已互斥，03 §3.1） |
| 5 | Google OAuth token 失效/配额耗尽 | 低 | 高 | token 池配额沿用 + reconcile 对账 | 补充导入新 token（管理页已支持） |
| 6 | 模板上游更新冲突 | 低 | 低 | 全部按模板惯例写，偏离仅 3 条记录在案 | 常规 rebase |
| 7 | 旧数据后续要找回 | — | — | 旧库不动 | 按 02 §3 映射表补 ETL |
| 8 | React 重写中 Vue 交互细节遗漏 | 中 | 低 | 06 §3 逐页规格 + 旧页面可对照运行 | 对照旧 dist 页面补齐 |
| 9 | C3/C4/C5/C7 引擎移植引入行为差异 | 中 | 高 | golden 单测（样例 result JSON 断言热列抽取结果）+ 测试 Sheet 实跑验证 | golden 不符先修 extractor 再放量 |

## 里程碑与工作量估算

| 里程碑 | 阶段 | 累计 |
|---|---|---|
| M1 依赖与建表就绪 | P0–P1 | ~1.5 天 |
| M2 worker 真实跑通 Sheet 任务 | P2–P3 | ~6 天 |
| M3 API 全量 + 测试绿 | P4 | ~9 天 |
| M4 前端 B1 演示闭环 | P5 前半 | ~10.5 天 |
| M5 全量交付 | P5–P6 | ~14 天 |
