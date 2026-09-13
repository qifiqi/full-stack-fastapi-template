# DingTalk Stream 微服务

这是当前项目内的独立微服务，不挂载到 Flask `run.py`，用于接收钉钉机器人消息并执行任务运维指令（查询/断点重启任务等）。

## 入口

```powershell
# 推荐：自动选择 .venv / venv / env 中的 Python（run_ding.bat 会设 APP_ENV=production）
.\run_ding.bat

# 或手动用项目虚拟环境启动
.venv\Scripts\python.exe run_ding.py
.venv\Scripts\python.exe -m ding_stream_service
```

> 不要直接用系统 `python` 启动：系统 Python 若未安装 `dingtalk-stream` 会报
> `ModuleNotFoundError: No module named 'dingtalk_stream'`。依赖装在项目 `.venv` 里
> （`pip install -r requirements.txt`）。目录内没有 `run.py`，`python .\ding_stream_service\run.py` 是旧文档的失效写法。

## 模块结构

| 文件 | 职责 |
|---|---|
| `main.py` | 入口：日志、参数解析（`--client-id/--client-secret` 可覆盖 env）、注册回调处理器、`client.start_forever()` |
| `settings.py` | `DingStreamSettings.from_env()`：读取 `.env` + `.env.{APP_ENV}`（后者 override）中的 `DING_STREAM_CLIENT_ID` / `DING_STREAM_CLIENT_SECRET` |
| `handler.py` | `DingStreamEventHandler`：处理 `/v1.0/im/bot/messages/get` 事件，经 sessionWebhook 回复 markdown |
| `task_commands.py` | 任务指令解析与执行：懒加载 `create_app()` 后查询/重启任务，带会话级列表缓存（10 分钟 TTL） |
| `message_format.py` | markdown 回复消息拼装 |

## 配置

复用项目根目录 `.env`（及 `.env.{APP_ENV}`，`run_ding.bat` 固定 `APP_ENV=production`）：

```env
DING_STREAM_CLIENT_ID=
DING_STREAM_CLIENT_SECRET=
```

任一缺失会在启动时抛 `ValueError`，不会带错配置上线。

## 钉钉命令

```text
查看运行任务 第1页 每页5条
查看停止任务 第1页 每页10条
重启任务 <任务ID>
重启任务 <任务名称>
重启异常任务
重启异常任务 数量10
断点重启 <任务ID>
重启第N个        （重启最近一次查询结果中的第 N 条）
```

任务重启指令默认使用断点恢复。任务名必须精确匹配且唯一；如果名称重复，请使用任务 ID。
`重启异常任务` 会批量断点重启最近的 `error` 任务，默认 5 个，单次最多 20 个。

当前钉钉告警 markdown 可直接作为输入的一部分，例如：

```text
断点重启
### 告警
- **任务名称**：AAPL回测
- **任务ID**：abcdef12-3456-7890-abcd-ef1234567890
```

也支持从任务详情 URL 的 `task_id` / `taskId` 查询参数中识别目标。

所有回复统一使用钉钉机器人 `markdown` 消息类型：

```text
### 标题

- **字段**：值

> 摘要
> 补充说明
```

## 常见报错

| 现象 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: No module named 'dingtalk_stream'` | 用了系统 Python（未装依赖） | 改用 `run_ding.bat` 或 `.venv\Scripts\python.exe run_ding.py` |
| `ValueError: 请在项目根目录 .env 中配置 DING_STREAM_CLIENT_ID...` | `.env` / `.env.{APP_ENV}` 缺少钉钉 Stream 凭据 | 在 `.env` 补充两个键（钉钉开放平台应用凭据）；服务端凭据通常在部署机 `.env.production` |
| 钉钉指令回复"执行失败" | 指令处理时才懒加载 Flask `create_app()`，失败会以错误消息回给机器人 | 看 `logs/` 与控制台日志中的异常栈 |
