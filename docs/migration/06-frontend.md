# 06 · React 前端

> 上级：[../migration-plan.md](../migration-plan.md) · 相关：[05-api](05-api.md)（本文件所有 API 引用）

## 1. 硬性约定（模板模式，逐条对应现有实现）

| 约定 | 参照实现 |
|---|---|
| 文件路由：`src/routes/_layout/<page>.tsx` 导出 `createFileRoute`；routeTree 由 vite 插件自动生成，**不手改** | `routes/_layout/items.tsx` |
| 请求一律走生成的 SDK：`import { TasksService } from "@/client"`；**不手写 axios 调用** | `src/client/sdk.gen.ts` |
| 查询：`get<Name>QueryOptions()` + `useSuspenseQuery` + `<Suspense fallback={<Pending…/>}>`；改数据 `useMutation` + `onSettled invalidateQueries` | items 页全套 |
| 表单：react-hook-form + zod resolver + `useCustomToast`/`handleError` | `components/Items/AddItem.tsx` |
| 导航：`src/components/Sidebar/Main.tsx` 的 items 数组加 `{path, title, icon}` | 同文件 |
| 删除确认：`components/Common/ActionsMenu.tsx` 模式的 Dialog | 同文件 |
| 改过 API → 先跑 `scripts/generate-client.sh` 再写页面 | 根 scripts/ |
| 登录沿用模板：`_layout.tsx` 守卫 + `login.tsx` 不动；不建 signup 入口（内部工具） | 现状保留 |

旧 Vue 的三个模式**不迁移**：`{status,code,message,data}` 信封拦截器（新 API 裸数据）、401→refresh 静默续期（模板 client 已带 401 处理）、`usePolling.js`（改用 React Query `refetchInterval`）。

## 2. 目录规划

```
frontend/src/
├── routes/_layout/
│   ├── index.tsx                    # 仪表盘（原 admin/Dashboard）
│   ├── tasks/                       # index | create | $taskId | export
│   ├── results.tsx                  # 全局结果表（原 admin/Results）
│   ├── google-sheets.tsx  google-sheet-tokens.tsx  scheduled-tasks.tsx
│   ├── task-templates.tsx  configs.tsx  logs.tsx  navigation.tsx
│   ├── backtest-training/           # index | create | $taskId | global-preview | result | result-export
│   ├── backtest-multi/              # 同上五页
│   ├── global-preview/single-product.tsx
│   ├── model-summary.tsx  performance-analysis/{index,v1,v2,weight-combination}.tsx
│   └── eastmoney-kline.tsx
└── components/
    ├── Tasks/        # TaskTable、TaskStatusBadge、CreateTaskForm(按 task_type 切配置段)、
    │                 #   BatchCreateForm、TaskLogsPanel、StopConfirmDialog
    ├── TaskResults/  # ResultTable、ResultDetailDrawer(懒加载完整 JSON)、ReturnSeriesChart
    ├── Backtest/     # 回测两域共用：SummaryRows、PreviewGroup、RatioEditor、ExportPreview
    ├── ModelSummary/ # SummaryGrid、BestFilterBar、BackfillDialog
    ├── PerfAnalysis/ # WeightCombinationTable(虚拟滚动)、AnalyzeForm、NdjsonStreamConsumer
    ├── Sheets/       # SheetRegistryTable、TokenPoolTable、TokenImportDialog
    ├── Scheduler/    # CronField(zod 校验)、ScheduleTable
    └── Shared/       # StatCard、LogLevelBadge、DatetimeRange、VirtualTable
```

## 3. 页面规划（40 个旧 Vue 页 → 逐页规格）

批次：**B1 任务主线 → B2 资源管理 → B3 回测 → B4 分析**。每页标注：数据源（SDK 方法）、轮询、特殊要求。

### B1 任务主线

| 页面 | 内容 | SDK 调用 | 特殊要求 |
|---|---|---|---|
| `_layout/index.tsx`（原 admin/Dashboard.vue） | 统计卡（任务数/状态分布/平均耗时）+ 最近任务表 + 在跑任务心跳状态 | TasksService.readTasks（statistics）、readTaskStatusCheck | refetchInterval 15–30s；后端已 SQL 聚合 |
| `tasks/index.tsx`（原 task/List + TaskListInner） | 表格：状态徽章/类型/Sheet/进度步骤/耗时/操作（详情·取消·重启·重建·删除）；keyword 搜索 | readTasks、cancelTask、restartTask、createRestartTask、deleteTask | 批量创建入口按钮；status/type 过滤 tabs |
| `tasks/create.tsx`（原 task/Create + CreateC3/C31/C4/C5/C7） | 单页表单：选 task_type → 动态配置段（Sheet 选择、参数矩阵编辑器、K线源、随机价规则、模板载入） | createTask、createBatchTask、listTaskTemplates、searchStocks、listGoogleSheets | 参数矩阵编辑器是最复杂控件（行列增删、批量粘贴）；模板载入回填表单 |
| `tasks/$taskId.tsx`（原 task/Detail） | Tab：概览（status-check 轮询）· 日志（级别过滤、自动滚底）· 结果表 · 全局预览入口 | readTask、readTaskStatusCheck、readTaskLogs、listTaskResults | status-check refetchInterval：running 时 10s，否则停 |
| `tasks/export.tsx`（原 task/MergeExport） | 多任务勾选合并导出 CSV/ZIP | batchExport（POST /exports/tasks/batch） | blob 下载 + 进度提示（≤10 任务） |
| `results.tsx`（原 admin/Results） | 全局结果检索：task/stock/period/success 过滤，行点击开详情抽屉 | listTaskResults、readTaskResult、deleteTaskResult | 详情抽屉**懒加载**完整 params/result JSON（列表不带大 JSON）；收益序列折线图（ReturnSeriesChart，轻量图表库沿用模板依赖策略） |

### B2 资源管理

| 页面 | 内容 | SDK 调用 | 特殊要求 |
|---|---|---|---|
| `google-sheets.tsx`（原 admin/GoogleSheets） | Sheet 注册表：spreadsheet_id/name/scope/占用状态；CRUD | GoogleSheetsService.* | 占用中禁删（后端 409 → handleError toast） |
| `google-sheet-tokens.tsx` | token 池：用量进度条（total/max）、启用开关、类型配额编辑、导入、对账 | GoogleSheetTokensService.*（含 import、reconcile） | token_context 不回显明文（脱敏显示名称） |
| `scheduled-tasks.tsx`（原 admin/Scheduler） | cron 列表：表达式/启停/上次运行/锁状态；新建（CronField 控件）+ 立即运行；worker 统计卡 | ScheduledTasksService.*、getSchedulerStats | CronField 用 zod 五段校验 + 常用模板下拉 |
| `task-templates.tsx`（原 admin/Templates） | 模板 CRUD，config JSON 编辑器 | TaskTemplatesService.* | JSON 编辑器带格式化/校验 |
| `configs.tsx`（原 admin/Config） | SystemConfig 键值表 + 校验入口 | ConfigsService.* | 敏感值遮蔽 |
| `logs.tsx`（原 admin/Logs） | 全局日志查询：级别/任务/时间范围过滤，分页 | LogsService.readLogs | 时间范围用 DatetimeRange 共用组件 |
| `navigation.tsx`（原 admin/Navigation） | 导航菜单项 CRUD + 排序 | NavigationService.* | 无 permission 字段 |

### B3 回测

| 页面 | 内容 | SDK 调用 | 特殊要求 |
|---|---|---|---|
| `backtest-training/*`（原 backtest/ 六页）与 `backtest-multi/*`（原 backtest-multi/ 五页） | create（参数组编辑）/ 列表 / 详情 / 全局预览（分组对比）/ 结果（比率表）/ 导出预览 | BacktestService.*（task-results、task-summary、calculate-ratios、ratios、export-preview）+ TasksService | 两域**共用** components/Backtest/ 全部组件（旧 Vue 是复制粘贴的两套，重写时合并）；预览页复用 global-preview 分组逻辑 |

### B4 分析

| 页面 | 内容 | SDK 调用 | 特殊要求 |
|---|---|---|---|
| `model-summary.tsx`（原 admin/ModelSummary） | 最优结果网格：stock/period/model 维度过滤、best_only 开关、回填按钮+进度 | ModelSummaryService.readModelSummary、rebuild、rebuildStatus | best_only=true/false 两视图都走热列直查；回填轮询 status |
| `performance-analysis/index.tsx` + `v1.tsx` + `v2.tsx` | 分析表单 + NDJSON 流式渲染 | analyzeAnalyze / v1Analyze | **fetch + ReadableStream 逐行 JSON.parse**（SDK 不支持 NDJSON），封装 `components/PerfAnalysis/NdjsonStreamConsumer` |
| `performance-analysis/weight-combination.tsx`（原 WeightCombination.vue） | 权重组合结果表（旧版实测 10 万行、DOM 渲染 5–10s） | v1WeightCombination（流式） | **VirtualTable（TanStack Virtual）行虚拟化**，分块流式 append；行数/耗时展示 |
| `global-preview/single-product.tsx`（原 SingleProduct.vue） | 单产品全局预览 | GlobalPreviewService.* | 分组表格 |
| `eastmoney-kline.tsx`（原 admin/EastmoneyKline.vue） | K线查询/图表（走 market 服务） | StocksService + kline 数据端点 | 图表复用 ReturnSeriesChart 图表组件 |

## 4. 侧边栏结构（Sidebar/Main.tsx items）

```
仪表盘 /          任务管理 /tasks        创建任务 /tasks/create
结果查询 /results  全局预览 /global-preview/single-product
回测训练 /backtest-training            回测多产品 /backtest-multi
模型汇总 /model-summary                性能分析 /performance-analysis
Google Sheets /google-sheets          Token 池 /google-sheet-tokens
调度任务 /scheduled-tasks              任务模板 /task-templates
系统配置 /configs                      日志查询 /logs
导航管理 /navigation                   东财K线 /eastmoney-kline
```

（`/api/meta/nav` 不迁移，菜单静态定义；旧"用户/角色"入口不建。）

## 5. B1–B4 交付口径

- 每批次：generate-client 已更新 → 页面联调通过 → `bun run lint` + 现有 playwright 冒烟不回归
- B1 完成即可端到端演示：建任务（C3）→ worker 执行 → 详情页轮询 → 结果/收益序列可见
- 虚拟滚动、NDJSON 流式消费是 B4 两个技术风险点，提前在 B1 的结果表（常规分页）上验证表格基座
