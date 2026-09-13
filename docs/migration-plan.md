# google_sheet_task → full-stack-fastapi-template 迁移方案（总纲）

> 状态：设计定稿，待实施
> 源项目：`C:\Users\fuqing\Desktop\google_sheet_task`（Flask + Vue 3，~36.5k 行后端，76 个测试文件）
> 目标项目：本仓库 full-stack-fastapi-template（FastAPI + SQLModel + React 19）
> 详细设计：`docs/migration/` 下的 7 个专题文档

## 已确认决策

| # | 决策 |
|---|---|
| ① | 登录/权限（RBAC/SSO/JWT）不迁移；保留模板自带登录作入口门禁，业务接口无权限控制 |
| ② | 全新空库，不迁移旧数据；旧库不动留作历史查询 |
| ③ | Task 主键由 uuid4 改为自增 BIGINT，关联表恢复外键约束 + CASCADE |
| ④ | 前端 53 个 Vue 页面全部用 React 19 重写，废弃 legacy Jinja 页面 |
| ⑤ | 同一套代码支持 PostgreSQL / MySQL 5.7.8+（含 8.0+）切换，代码禁用方言级特性 |
| ⑥ | 整体风格、代码风格、接口风格强制按模板执行，已沉淀为 skill `.agents/skills/fastapi-template-style` |
| ⑦ | 任务执行收敛到独立 worker 服务（单实例），API 进程无状态化，解决 4 worker 重复执行问题 |
| ⑧ | 调度不用 APScheduler，用 croniter 轮询循环（Python 3.14 兼容风险规避） |
| ⑨ | "结果库"汇总表删除，热列在结果写入时抽取落库（消除全表扫描重建） |

## 文档地图

| 文档 | 内容 | 读者场景 |
|---|---|---|
| [01-scope-and-style.md](migration/01-scope-and-style.md) | 技术栈对照、迁移/不迁移/改造三类清单、风格约束（强制） | 动任何代码之前 |
| [02-database.md](migration/02-database.md) | 11 张新表逐列定义、索引/外键、旧表→新表映射、10 项性能修复、回填工具 | 建模型/写迁移/写查询时 |
| [03-architecture.md](migration/03-architecture.md) | worker 进程模型、任务状态机、领取/心跳/watchdog/cron 四循环、关键时序、compose 定义 | 写任务引擎/worker 时 |
| [04-backend.md](migration/04-backend.md) | 目录结构、40+ 文件移植映射、Flask 解耦模式、依赖与 Python 3.14 策略、配置项、测试移植 | 移植每个服务时 |
| [05-api.md](migration/05-api.md) | 全局约定、15 个路由模块端点级设计（参数/请求体/响应/错误码）、核心 schema | 写路由/生成客户端/前端联调时 |
| [06-frontend.md](migration/06-frontend.md) | 40 个页面逐页规划（组件/调用 API/特殊要求）、组件目录、B1–B4 批次 | 写 React 页面时 |
| [07-phases.md](migration/07-phases.md) | P0–P6 阶段任务清单（checkbox 级）、验收标准、风险登记册 | 执行与验收时 |

## 一页速览（细节都在子文档）

- **数据库**：uuid4→BIGINT、JSON TEXT→JSON(B)、热列写入时抽取、收益序列拆关系表、汇总表删除、外键恢复
- **执行**：API 只写库，worker 领取执行（ThreadPoolExecutor + 心跳 + watchdog），croniter 做 cron 调度
- **后端**：services/ 按域打包移植，Flask 耦合点（current_app/g/蓝图）按 §04 对照表解耦
- **API**：`/api/v1` 标准 REST，废除 `{status,code,message,data}` 信封，改端点后必跑 generate-client
- **前端**：TanStack Router 文件路由 + React Query + 生成的类型化 SDK，B1 任务主线先行
- **门禁**：`backend/scripts/lint.sh`（mypy strict + ty + ruff）与 `backend/scripts/test.sh` 全绿
- **前置阻塞**：`backend/app/api/deps.py:36` Python 2 语法 SyntaxError，P0 先修
