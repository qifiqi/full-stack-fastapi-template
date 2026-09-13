# 03 · 执行架构（worker）

> 上级：[../migration-plan.md](../migration-plan.md) · 相关：[02-database](02-database.md)（锁字段定义）/ [04-backend](04-backend.md)（代码位置）

## 1. 为什么必须独立 worker

模板生产命令 `fastapi run --workers 4` 会起 4 个 API 进程。任务执行的内存状态——ThreadPoolExecutor、stop `threading.Event`、线程句柄（watchdog 驱逐用）——只能存在一份，否则同一任务被多个进程重复执行、取消信号丢失。旧系统单进程 gunicorn + 进程内 TaskManager 的前提在新部署形态下不成立。

**拆分原则**：API 进程零执行状态，一切通过数据库传递；worker 是唯一消费者。

```
┌──────────────┐  POST /tasks → 插入 pending 行   ┌─────────────┐
│  API ×4      │ ───────────────────────────────→ │  Postgres / │
│  (fastapi ×4 │  cancel → stop_requested=TRUE     │  MySQL      │
│   无状态)     │  status-check → 读行 + 最近日志   │             │
└──────────────┘                                   └──────┬──────┘
                                                          │ 轮询领取 / 心跳 / 状态回写
                                                   ┌──────┴──────────────────┐
                                                   │ worker ×1（compose 服务）│
                                                   │ · task-poller  (3–5s)   │
                                                   │ · heartbeat    (15s)    │
                                                   │ · watchdog     (60s)    │
                                                   │ · cron-scheduler(30s)   │
                                                   │ · ThreadPoolExecutor    │
                                                   │   TASK_TYPE_REGISTRY×6  │
                                                   └─────────────────────────┘
```

## 2. 任务状态机

```
             创建(单建/批量/重启复制)                    API cancel
 pending ─────────────────────────→ queued ─────────→ pending
    │  worker 领取(UPDATE抢到,行数=1)    ▲                   │
    ▼                                  │ 并发释放后重排      │
 running ──→ success (finished_at)     └───────────────────┘
    │  │
    │  └─→ error   ── watchdog(可重试错误, attempt<3) ──→ pending
    │        └─── API restart → 复制新行(pending)，旧行不动
    └─→ cancelled（stop_requested 被 worker 置 Event，步骤边界退出）
```

- `queued`：批量创建时全局/类型并发已满（沿用旧 `batch_create_and_start_task` 的排队语义）
- `running` 行必带 `running_instance` + `heartbeat_at`
- watchdog 与 worker 启动恢复是仅有的两个能把 `running` 改回 `pending` 的组件；API 永远不直接改 `running`

## 3. worker 内部四个循环 + 执行器

### 3.1 task-poller（每 3–5s）
1. 读配置：全局并发 `TASK_MAX_WORKERS`（默认 8）、按类型 `TASK_CONCURRENCY_*`（默认 4）——来自 SystemConfig，热更新
2. 统计在跑：`SELECT task_type, COUNT(*) FROM task WHERE status='running' AND running_instance=:me GROUP BY task_type`（DB 是唯一事实源，进程内计数仅作快照）
3. 领取：`SELECT id, task_type FROM task WHERE status IN ('pending','queued') ORDER BY created_at LIMIT :slots`（STRAIGHT 顺序，无跳号）→ 逐条 `UPDATE task SET status='running', running_instance=:me, heartbeat_at=now(), started_at=COALESCE(started_at,now()) WHERE id=:id AND status IN ('pending','queued')`，影响行数=1 才提交线程池；=0 说明被其他实例抢走（为将来 worker 多实例预留）
4. 取消桥接：扫 `status='running' AND running_instance=:me AND stop_requested=TRUE` → 对应 `threading.Event.set()`（替代旧进程内直接 stop；runner 在每个步骤边界检查，执行 delay 20–30s 可被打断）
5. 回写进度：runner 完成每个 step 更新 `current_step`

### 3.2 heartbeat（每 15s）
`UPDATE task SET heartbeat_at=now() WHERE status='running' AND running_instance=:me`，单条批量 UPDATE。watchdog 以 `heartbeat_at` 超时为判死依据（旧系统靠"最近日志时间 >30 分钟"，日志时间受执行 delay 影响，误判率高）。

### 3.3 watchdog（每 60s，逻辑对齐旧 task_watchdog.py）
扫描窗口：`created_at` 在 5 天内（沿用旧约定）且 status='running'：
- `heartbeat_at` 超时（>10 分钟无心跳 = 线程死亡/卡死）→ 驱逐：从线程池移除句柄（`force_detach_running_task` 语义）、释放 Sheet/token 占用、`attempt+1 < 3` 则重置 pending 并记日志，否则置 error
- error 结果为可重试网络/Google 错误（error_handling.py 分类表沿用）→ 同上重置
- 重启计数沿用 `attempt=N/3` 写在 error_message 的旧约定，移植时改为独立列可选（P2 决定，默认沿用不迁移数据无包袱）
另扫 `scheduled_task` 锁：`is_running=TRUE AND last_run_at < now()-6h` 允许接管（STALE_LOCK 语义）。

### 3.4 cron-scheduler（每 30s）
1. 加载 `scheduled_task WHERE enabled=TRUE`
2. croniter 算每个表达式 next fire；到期 → DB 运行锁领取（02 §2.7 锁语义；`last_run_at` 超 6h 可强制接管）
3. 执行：`subprocess.Popen([sys.executable, "-m", "app.worker", "--job", str(task_id), "--instance", instance_id])`，stdout 追加 `logs/scheduled_task_<id>.log`（对齐旧 scheduled_task_worker.py 子进程模型，避免内存泄漏长驻）
4. job 子进程只允许三种类型：cleanup_old_logs / cleanup_old_results / cleanup_old_data（旧 worker 白名单语义），完成后释放锁、写 last_status/last_error
5. 手动"立即运行"（API run 按钮）：置 `last_run_at=NULL` 并由 cron-scheduler 下个 tick 领取——不复刻旧"daemon 线程直接跑"的双路径
6. 种子任务：每日数据清理 `0 0 * * *`（清理 10 天前数据），幂等播种

### 3.5 执行器（ThreadPoolExecutor）
- `TASK_TYPE_REGISTRY` 六类沿用：`google_sheet`→C3Service、`google_sheet_c4`、`google_sheet_c5`、`google_sheet_c7`、`backtest_training`、`backtest_multi_product`
- runner 签名统一 `(task_id: int, session_factory, settings, stop_event)`——不再传 Flask app
- C3/C4/C5/C7 的 `execute_task` 主循环（参数批次 → 写 Sheet → 轮询结果格 → 写 TaskResult）直移；`_save_task_result` 内增热列抽取 + return_series_point 批量插入（同事务）
- Sheet 运行锁：执行前 `backtest_sheet_run_lock` 插入（唯一约束冲突=被占）+ `google_sheet.is_in_use` 置位；token 预留 `increment_usage` 配额检查沿用
- 回测串行链：任务完成回调 `_start_next_pending_backtest_task`（同 Sheet pending 任务按 created_at 顺序提升）沿用
- 完成通知：钉钉 webhook（成功/失败播报，含 BASE_URL 详情链接）

## 4. 关键时序

### 创建 → 执行（正常路径）
```
前端 → POST /api/v1/tasks（参数矩阵展开校验通过）
API:  INSERT task(status=pending, config=JSON, 热列) → 202 返回 TaskPublic
worker poller(≤5s): UPDATE→running(实例+心跳) → 提交线程
runner: 锁 Sheet → 预留 token → 循环 steps{写参数 → delay(可被stop打断) → 轮询 → _save_task_result(热列+序列+日志)}
结束: status=success/error, finished_at, 钉钉通知, 释放占用, 链式提升下一个回测任务
```

### 取消
```
前端 → POST /tasks/{id}/cancel → API: stop_requested=TRUE（行不存在/未运行则 409）
poller(≤5s): 发现 → stop_event.set()
runner: 步骤边界退出 → status=cancelled + 已完成 steps 保留 → 释放占用
```

### worker 崩溃恢复（启动时顺序执行）
1. 删除 `backtest_sheet_run_lock` 全部行（进程内执行态，重启即失效——对齐旧 `_recover_runtime_resources`）
2. 重置 `google_sheet.is_in_use=FALSE`、`google_sheet_token.current_in_use_count=0`
3. `running` 且 `running_instance=本实例` → 重置 pending（attempt 计数照常）
4. 删除孤儿 `running_instance` 指向不存在实例且心跳超 10 分钟的行 → pending
5. 播种默认 scheduled_task（幂等）
6. 启动四循环

### SIGTERM 优雅退出
poller 停止领取 → 等待在跑 step 完成（上限一个 step 周期）→ 未完任务留在 running（下次启动按崩溃恢复路径接管）→ 释放本实例 scheduled_task 锁 → 退出。

## 5. compose 服务定义（草案）

```yaml
# compose.yml 追加
  worker:
    image: backend:latest          # 复用 backend 镜像
    depends_on:
      db:
        condition: service_healthy
        restart: true
    environment:                   # 与 backend 相同变量 + 以下新增
      WORKER_INSTANCE_ID: ${HOSTNAME}
      GOOGLE_TOKEN_DIR: /run/secrets/google-tokens
      STOCK_BASE_URL: ${STOCK_BASE_URL:-}
      DING_TALK_ACCESS_TOKEN: ${DING_TALK_ACCESS_TOKEN:-}
      DING_TALK_SECRET: ${DING_TALK_SECRET:-}
    volumes:
      - app-logs:/app/backend/logs
      - app-data:/app/backend/data # Google OAuth token 文件目录
    command: ["python", "-m", "app.worker"]
    restart: unless-stopped
    # 不挂 Traefik label（不对外）
```

`ding_stream_service` 另起可选服务（compose profile `dingtalk`），入口 `python -m ding_stream_service`，代码内 create_app 替换为 `app.worker` 提供的任务查询/重启函数。

## 6. 为什么不用 APScheduler / Celery

| 方案 | 结论 |
|---|---|
| APScheduler 3.x | 仅用其 cron 触发；Python 3.14 官方支持止步 3.13，兼容风险不值得 —— croniter + 30s 轮询 ~50 行等价替代（旧系统本就只支持 cron 循环 + DB 锁，无复杂触发需求） |
| Celery/ARQ + Redis | 需新增 Redis 依赖与双库（MySQL 场景 broker 兼容差）；本场景任务量（单批数百 step、每 step 20–30s 间隔）远不到需要分布式队列的量级 |
| 进程内多线程（现状） | 保留！worker 内部就是 ThreadPoolExecutor，I/O 密集型 Sheet 校验天然适合线程；变化的只是"从 API 进程挪到专用进程" |
