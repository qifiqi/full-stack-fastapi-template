"""Task operations for the DingTalk stream service (new task entrypoints).

The Flask ``create_app``/``task_manager`` singletons are replaced by direct
SQLModel queries against the shared DB: listing tasks by status group and
"restarting" = copying a task into a fresh pending row (worker picks it up).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from sqlmodel import Session, col, select

from app.core.db import engine
from app.models import Task
from app.services.tasks.creation import create_task_with_config

logger = logging.getLogger(__name__)

RESTART_ACTION_RE = re.compile(r"(?:断点重启|重启任务|任务重启|重启|restart)", re.I)
RESTART_ERROR_TASKS_RE = re.compile(
    r"(?:重启异常任务|重启错误任务|重启失败任务|restart\s+error\s+tasks)", re.I
)
TASK_ID_FIELD_RE = re.compile(
    r"(?:任务\s*ID|task[_\s-]*id|taskId)\*{0,2}\s*[：:]\s*`?([A-Za-z0-9_-]{1,64})", re.I
)
TASK_NAME_FIELD_RE = re.compile(
    r"(?:任务名称|任务名|task\s*name)\*{0,2}\s*[：:]\s*(.+)", re.I
)
DIRECT_RESTART_RE = re.compile(
    r"^\s*(?:断点重启|重启任务|任务重启|重启|restart)\s*(?:任务)?\s*(.+?)\s*$", re.I | re.S
)
RUNNING_TASK_RE = re.compile(r"(?:查看)?(?:当前)?(?:运行中|运行)(?:的)?(?:任务|项目)", re.I)
STOPPED_TASK_RE = re.compile(r"(?:查看)?(?:停止|已停止|结束)(?:的)?(?:任务|项目)", re.I)
PAGE_RE = re.compile(r"第\s*(\d+)\s*页")
PER_PAGE_RE = re.compile(r"每页\s*(\d+)\s*(?:条|个)?")
LIMIT_RE = re.compile(r"(?:数量|最多|前)\s*(\d+)\s*(?:条|个)?")
STOPPED_STATUSES = ["success", "cancelled", "error", "pending"]
DEFAULT_BATCH_RESTART_LIMIT = 5
MAX_BATCH_RESTART_LIMIT = 20


@dataclass(frozen=True)
class ParsedRestartCommand:
    target: str
    target_type: Literal["id", "name"]


@dataclass(frozen=True)
class ParsedListCommand:
    status_group: Literal["running", "stopped"]
    page: int = 1
    per_page: int = 5


@dataclass(frozen=True)
class ParsedBatchRestartCommand:
    status: Literal["error"] = "error"
    limit: int = DEFAULT_BATCH_RESTART_LIMIT


def _session() -> Session:
    return Session(engine, expire_on_commit=False)


def list_tasks(command: ParsedListCommand) -> dict[str, Any]:
    statuses = ["running"] if command.status_group == "running" else list(STOPPED_STATUSES)
    with _session() as session:
        statement = (
            select(Task)
            .where(col(Task.status).in_(statuses))
            .order_by(col(Task.created_at).desc())
        )
        rows = list(session.exec(statement).all())
    total = len(rows)
    start = (command.page - 1) * command.per_page
    page_rows = rows[start : start + command.per_page]
    lines = [
        f"#{t.id} [{t.status}] {t.name} ({t.current_step}/{t.total_steps})"
        for t in page_rows
    ]
    return {
        "total": total,
        "page": command.page,
        "per_page": command.per_page,
        "tasks": [
            {"id": int(t.id or 0), "status": t.status, "name": t.name} for t in page_rows
        ],
        "text": "\n".join(lines) if lines else "没有符合条件的任务",
    }


def restart_task_by_ref(target: str, target_type: Literal["id", "name"]) -> dict[str, Any]:
    """Copy the referenced task into a fresh pending row (create-restart semantics)."""
    with _session() as session:
        if target_type == "id":
            try:
                task_id = int(target)
            except ValueError:
                return {"ok": False, "text": f"任务 ID 非法: {target}"}
            statement = select(Task).where(col(Task.id) == task_id)
        else:
            statement = (
                select(Task)
                .where(col(Task.name) == target)
                .order_by(col(Task.created_at).desc())
            )
        original = session.exec(statement).first()
        if original is None:
            return {"ok": False, "text": f"未找到任务: {target}"}
        config = original.config if isinstance(original.config, dict) else {}
        new_task = create_task_with_config(
            session,
            name=f"{original.name} (重启)",
            description=f"{original.description or ''}基于任务 {original.id} 重启".strip(),
            task_type=original.task_type,
            config=config,
        )
        return {
            "ok": True,
            "task_id": int(new_task.id or 0),
            "text": f"已基于任务 #{original.id} 创建重启任务 #{new_task.id}（pending，等待 worker 领取）",
        }


def restart_error_tasks(limit: int) -> dict[str, Any]:
    restarted: list[int] = []
    with _session() as session:
        statement = (
            select(Task)
            .where(col(Task.status) == "error")
            .order_by(col(Task.finished_at).desc())
        )
        failed = list(session.exec(statement).all())[:limit]
    for original in failed:
        result = restart_task_by_ref(str(original.id), "id")
        if result.get("ok"):
            restarted.append(int(result["task_id"]))
    text = (
        f"已重启 {len(restarted)} 个异常任务: {', '.join('#' + str(i) for i in restarted)}"
        if restarted
        else "没有可重启的异常任务"
    )
    return {"ok": bool(restarted), "task_ids": restarted, "text": text}


def parse_restart_command(text: str) -> ParsedRestartCommand | None:
    if not RESTART_ACTION_RE.search(text):
        return None
    id_match = TASK_ID_FIELD_RE.search(text)
    if id_match:
        return ParsedRestartCommand(target=id_match.group(1), target_type="id")
    name_match = TASK_NAME_FIELD_RE.search(text)
    direct = DIRECT_RESTART_RE.search(text)
    raw_target = (
        name_match.group(1) if name_match else (direct.group(1) if direct else "")
    ).strip()
    raw_target = raw_target.strip("`* ")
    if not raw_target:
        return None
    return ParsedRestartCommand(target=raw_target, target_type="name")


def parse_batch_restart_command(text: str) -> ParsedBatchRestartCommand | None:
    if not RESTART_ERROR_TASKS_RE.search(text):
        return None
    limit = DEFAULT_BATCH_RESTART_LIMIT
    limit_match = LIMIT_RE.search(text)
    if limit_match:
        limit = min(int(limit_match.group(1)), MAX_BATCH_RESTART_LIMIT)
    return ParsedBatchRestartCommand(limit=limit)


def parse_list_command(text: str) -> ParsedListCommand | None:
    is_running = bool(RUNNING_TASK_RE.search(text))
    is_stopped = bool(STOPPED_TASK_RE.search(text))
    if not is_running and not is_stopped:
        return None
    page = 1
    per_page = 5
    page_match = PAGE_RE.search(text)
    if page_match:
        page = max(1, int(page_match.group(1)))
    per_page_match = PER_PAGE_RE.search(text)
    if per_page_match:
        per_page = min(max(1, int(per_page_match.group(1))), 20)
    return ParsedListCommand(
        status_group="running" if is_running else "stopped",
        page=page,
        per_page=per_page,
    )


@dataclass(frozen=True)
class TaskCommandResult:
    handled: bool
    message: str = ""


class TaskCommandService:
    """Entry point consumed by the stream handler (old task_manager role)."""

    def handle_message(self, text: str) -> TaskCommandResult:
        batch = parse_batch_restart_command(text)
        if batch is not None:
            result = restart_error_tasks(batch.limit)
            return TaskCommandResult(handled=True, message=result["text"])

        restart = parse_restart_command(text)
        if restart is not None:
            result = restart_task_by_ref(restart.target, restart.target_type)
            return TaskCommandResult(handled=True, message=result["text"])

        listing = parse_list_command(text)
        if listing is not None:
            result = list_tasks(listing)
            header = f"共 {result['total']} 个任务（第 {result['page']} 页）:\n"
            return TaskCommandResult(handled=True, message=header + result["text"])

        return TaskCommandResult(handled=False)

