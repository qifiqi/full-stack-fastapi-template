"""Task log writing (4000-char truncation preserved from the source)."""

import logging
from typing import Any

from sqlmodel import Session

from app.crud import create_task_log, list_task_logs
from app.models import TaskLogCreate

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4000
_TRUNCATION_SUFFIX = "...（日志已截断）"


def normalize_message(message: Any) -> str:
    text = "" if message is None else str(message)
    if len(text) <= MAX_MESSAGE_LENGTH:
        return text
    return text[: MAX_MESSAGE_LENGTH - len(_TRUNCATION_SUFFIX)] + _TRUNCATION_SUFFIX


def add_task_log(session: Session, task_id: int, level: str, message: str) -> None:
    """Write a task log row; failures are logged and never break the task chain."""
    try:
        create_task_log(
            session=session,
            log_in=TaskLogCreate(
                task_id=task_id,
                level=(level or "INFO").upper()[:20],
                message=normalize_message(message),
            ),
        )
    except Exception:
        logger.exception("写入任务日志失败: task_id=%s", task_id)
        session.rollback()


def get_task_logs(
    session: Session,
    task_id: int,
    *,
    skip: int = 0,
    limit: int = 500,
    level: str | None = None,
) -> tuple[list[Any], int]:
    return list_task_logs(
        session=session, task_id=task_id, skip=skip, limit=limit, level=level
    )
