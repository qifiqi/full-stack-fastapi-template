"""Task-domain error types, retryable classification and error records.

Ported from google_sheet_task (utils/task_error_utils.py, exceptions/, task/error_handling.py).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from http.client import RemoteDisconnected
from typing import Any, cast

import requests
from sqlmodel import Session
from tenacity import RetryError
from urllib3.exceptions import ProtocolError

from app.crud import create_task_log
from app.models import TaskLogCreate

NETWORK_ERROR_PREFIX = "[NETWORK_RETRYABLE]"
WATCHDOG_RESTART_PREFIX = "[WATCHDOG_FORCE_RESTART]"
GOOGLE_SHEET_EXECUTION_ERROR_PREFIX = "[GOOGLE_SHEET_RETRYABLE]"

TASK_ERROR_MESSAGE_MAX_LENGTH = 500


class RetryableNetworkTaskError(Exception):
    """A network-layer error that is safe for the watchdog to auto-restart."""


class AppException(Exception):
    http_status = 500

    def __init__(
        self,
        message: str | None = None,
        *,
        code: int | None = None,
        detail: Any = None,
    ) -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__
        self.code = code if code is not None else self.http_status
        self.detail = detail

    def __str__(self) -> str:
        return self.message


class BadRequestError(AppException):
    http_status = 400


class ValidationError(BadRequestError):
    pass


class NotFoundError(AppException):
    http_status = 404


class ConflictError(AppException):
    http_status = 409


class ServiceError(AppException):
    http_status = 500


# Keep the source project's naming; do not shadow pydantic's ValidationError.


class SheetCheckError(Exception):
    """Sheet template check produced '#'-like invalid values."""


def iter_exception_chain(exc: BaseException | None) -> Iterator[BaseException]:
    seen: set[int] = set()
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        if isinstance(current, RetryError):
            last_attempt = getattr(current, "last_attempt", None)
            inner = None
            if last_attempt is not None:
                try:
                    inner = last_attempt.exception()
                except Exception:
                    inner = None
            current = (
                inner
                or getattr(current, "__cause__", None)
                or getattr(current, "__context__", None)
            )
            continue
        current = getattr(current, "__cause__", None) or getattr(
            current, "__context__", None
        )


def unwrap_exception(exc: BaseException | None) -> BaseException | None:
    result = exc
    for item in iter_exception_chain(exc):
        result = item
    return result or exc


def is_retryable_network_error(exc: BaseException | None) -> bool:
    if exc is None:
        return False

    try:
        from gspread.exceptions import APIError as GSpreadAPIError
    except Exception:
        GSpreadAPIError = None  # type: ignore[assignment,misc]

    network_types = (
        requests.ConnectionError,
        requests.RequestException,
        requests.Timeout,
        ProtocolError,
        RemoteDisconnected,
    )
    network_keywords = (
        "connection",
        "disconnected",
        "aborted",
        "remote end",
        "protocol error",
        "network",
        "timeout",
        "timed out",
        "broken pipe",
        "connection reset",
        "temporarily unavailable",
        "service unavailable",
    )

    for item in iter_exception_chain(exc):
        if isinstance(item, RetryableNetworkTaskError):
            return True
        if isinstance(item, network_types):
            return True
        if GSpreadAPIError is not None and isinstance(item, GSpreadAPIError):
            resp = getattr(item, "response", None)
            status = getattr(resp, "status_code", None)
            if isinstance(status, int) and (status == 429 or status >= 500):
                return True
        error_text = str(item).lower()
        if any(keyword in error_text for keyword in network_keywords):
            return True

    return False


@dataclass(frozen=True)
class TaskErrorRecord:
    trace_id: str
    task_id: int
    phase: str
    exception_type: str
    message: str
    traceback_text: str


def _get_session(session: Session | None, session_factory: Any) -> Session | None:
    if session is not None:
        return session
    if session_factory is not None:
        return cast("Session", session_factory())
    return None


def build_task_error_record(
    exc: BaseException, phase: str, task_id: int
) -> TaskErrorRecord:
    import traceback as _tb

    root = unwrap_exception(exc)
    record = TaskErrorRecord(
        trace_id=uuid.uuid4().hex[:12],
        task_id=task_id,
        phase=phase,
        exception_type=type(root or exc).__name__,
        message=str(root or exc),
        traceback_text=_tb.format_exc(),
    )
    return record


def format_task_error_message(record: TaskErrorRecord) -> str:
    message = f"trace_id={record.trace_id} {record.exception_type}: {record.message}"
    return message[:TASK_ERROR_MESSAGE_MAX_LENGTH]


def format_task_error_log(record: TaskErrorRecord) -> str:
    return (
        f"trace_id={record.trace_id} task_id={record.task_id} phase={record.phase} "
        f"{record.exception_type}: {record.message}\n{record.traceback_text}"
    )


def record_task_exception(
    task_id: int,
    exc: BaseException,
    phase: str,
    *,
    session: Session | None = None,
    session_factory: Any = None,
    mark_error: bool = True,
    update_task_error: Any = None,
) -> TaskErrorRecord:
    """Persist error state + log row for a failing task execution.

    ``update_task_error(task_id, error_message)`` is injected by the caller
    (worker) so this module stays decoupled from the Task model CRUD.
    """
    record = build_task_error_record(exc, phase, task_id)
    owned: Session | None = None
    try:
        owned = _get_session(session, session_factory)
        if owned is not None:
            with owned as s:
                create_task_log(
                    session=s,
                    log_in=TaskLogCreate(
                        task_id=task_id,
                        level="ERROR",
                        message=format_task_error_log(record),
                    ),
                )
                if mark_error and update_task_error is not None:
                    update_task_error(task_id, format_task_error_message(record), s)
    except Exception:
        pass
    return record
