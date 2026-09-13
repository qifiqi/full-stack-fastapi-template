"""Google Sheets gspread client (ported from google_sheet_task, framework-free)."""

import functools
import logging
import time
from typing import Any

import gspread
from google.oauth2.credentials import Credentials
from gspread import Cell
from gspread.utils import a1_to_rowcol, rowcol_to_a1

from app.services.tasks.errors import (
    RetryableNetworkTaskError,
    is_retryable_network_error,
)

logger = logging.getLogger(__name__)


class GoogleSheet:
    """Google Sheet client wrapper."""

    def __init__(
        self,
        spreadsheet_id: str,
        sheet_name: str | None = None,
        token_file: str = "data/token.json",
        proxy_url: str | None = None,
        task_id: int | None = None,
        http_timeout: int | None = None,
    ) -> None:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        self.client = None
        self.sheet = None
        self.spreadsheet_id = spreadsheet_id
        self.title = None
        self.worksheet = None
        self.task_id = task_id
        self._last_reconnect_exception = None
        self._sheet_name = sheet_name
        self._token_file = token_file
        self._proxy_url = proxy_url
        self._SCOPES = scopes
        self._http_timeout = http_timeout

        try:
            self._connect_and_select_worksheet()
        except Exception as e:
            logger.error(
                "%s初始化Google Sheet连接失败: %s (spreadsheet=%s, sheet=%s, token=%s)",
                self._log_ctx(),
                e,
                self.spreadsheet_id,
                self._sheet_name,
                self._token_file,
            )
            if is_retryable_network_error(e):
                raise RetryableNetworkTaskError(
                    f"{self._log_ctx()}初始化Google Sheet连接失败: {e}"
                ) from e
            raise

    def _connect_and_select_worksheet(self) -> None:
        creds = Credentials.from_authorized_user_file(
            self._token_file, scopes=self._SCOPES
        )
        self.client = gspread.authorize(credentials=creds)

        self._apply_proxy_settings()
        self._apply_default_timeout()
        self.sheet = self.client.open_by_key(self.spreadsheet_id)
        self.title = self.sheet.title

        if not self._sheet_name:
            return

        try:
            self.worksheet = self.sheet.worksheet(self._sheet_name)
            return
        except Exception:
            try:
                titles = [ws.title for ws in self.sheet.worksheets()]
            except Exception:
                titles = []

            target_lower = str(self._sheet_name).strip().lower()
            matched_title = None
            for t in titles:
                if str(t).strip().lower() == target_lower:
                    matched_title = t
                    break

            if matched_title:
                self.worksheet = self.sheet.worksheet(matched_title)
                self._sheet_name = matched_title
                return

            raise Exception(
                f"请先选择工作表: '{self._sheet_name}' 不存在，可用工作表: {titles}"
            )

    def _log_ctx(self) -> str:
        parts = []
        if self.task_id:
            parts.append(f"task_id={self.task_id}")
        if self.spreadsheet_id:
            parts.append(f"spreadsheet_id={self.spreadsheet_id}")
        if self._sheet_name:
            parts.append(f"sheet_name={self._sheet_name}")
        return f"[{' '.join(parts)}] " if parts else ""

    def _apply_default_timeout(self, timeout: int | None = None) -> None:
        if not self.client:
            return

        if timeout is None:
            timeout = self._http_timeout
        if timeout is None:
            try:
                from app.services.config_manager import (
                    get_config_manager,
                    try_get_config_manager,
                )

                manager = try_get_config_manager() or get_config_manager()
                timeout = int(manager.get_config("google_sheet_http_timeout", 30))
            except Exception:
                timeout = 30

        set_timeout = getattr(self.client, "set_timeout", None)
        if callable(set_timeout):
            try:
                set_timeout(timeout)
                return
            except Exception:
                logger.debug(
                    "%s通过 client.set_timeout 设置超时失败",
                    self._log_ctx(),
                    exc_info=True,
                )

        session = self._get_client_session()
        if not session:
            return

        if getattr(session, "_timeout_patched", False):
            session._default_timeout = timeout
            return

        original_request = session.request

        @functools.wraps(original_request)
        def request_with_timeout(method: str, url: str, **kwargs: Any) -> Any:
            kwargs.setdefault("timeout", getattr(session, "_default_timeout", timeout))
            return original_request(method, url, **kwargs)

        session._default_timeout = timeout
        session.request = request_with_timeout
        session._timeout_patched = True

    def _get_client_session(self) -> Any:
        if not self.client:
            return None

        session = getattr(self.client, "session", None)
        if session is not None:
            return session

        http_client = getattr(self.client, "http_client", None)
        if http_client is not None:
            session = getattr(http_client, "session", None)
            if session is not None:
                return session

        internal_http_client = getattr(self.client, "_http_client", None)
        if internal_http_client is not None:
            session = getattr(internal_http_client, "session", None)
            if session is not None:
                return session

        return None

    def _apply_proxy_settings(self) -> None:
        """Proxy is applied to the client session only, never to os.environ."""
        if not self.client or not self._proxy_url:
            return

        proxy_url = str(self._proxy_url).strip()
        if not proxy_url.lower().startswith(("http://", "https://", "socks")):
            return

        logger.info("%s使用代理：%s", self._log_ctx(), proxy_url)

        session = self._get_client_session()
        if session is None:
            return

        try:
            session.proxies.update({"http": proxy_url, "https": proxy_url})
        except Exception:
            logger.warning("%s写入 session 代理失败", self._log_ctx(), exc_info=True)

    def get_row(self, row: int) -> list[Any]:
        return self.worksheet.row_values(row)

    def get_last_row(self, col_letter: str) -> int:
        try:
            _, column_number = a1_to_rowcol(f"{str(col_letter).strip().upper()}1")
            col_data = self.worksheet.col_values(column_number)
            return len(col_data) if col_data else 0
        except Exception as e:
            logger.error("获取最后非空行错误。错误内容：%s", e)
            return -1

    def clear_range(self, range_a1: str) -> None:
        self._ensure_worksheet()
        if not range_a1:
            return
        logger.info("%s清空区间: %s", self._log_ctx(), range_a1)

        def _clear_operation() -> None:
            self.worksheet.batch_clear([range_a1])

        self._retry_network_operation(_clear_operation, f"clear_range({range_a1})")

    def clear_jumped_cells(self, cell_refs: list[str]) -> Any:
        self._ensure_worksheet()

        if not cell_refs:
            return None

        valid_refs = []
        for cell_ref in cell_refs:
            if not cell_ref or not isinstance(cell_ref, str):
                continue
            try:
                a1_to_rowcol(cell_ref)
            except Exception:
                continue
            valid_refs.append(cell_ref)

        if not valid_refs:
            return None

        def _clear_operation() -> None:
            self.worksheet.batch_clear(valid_refs)

        return self._retry_network_operation(_clear_operation, "clear_jumped_cells")

    def update_cell(self, cell_address: str, cell_value: Any) -> None:
        try:
            if not cell_address:
                raise ValueError("单元格地址不能为空")

            if cell_value is None:
                cell_value = ""
            elif not isinstance(cell_value, (int, float, str, bool)):
                cell_value = str(cell_value)

            def _update_operation() -> None:
                self.worksheet.update(cell_address, [[cell_value]])

            self._retry_network_operation(
                _update_operation, f"update_cell({cell_address})"
            )
        except Exception as e:
            error_msg = f"{self._log_ctx()}更新单元格 {cell_address} 失败，值: {cell_value}, 错误: {e}"
            logger.error(error_msg)
            raise Exception(error_msg) from e

    def update_jumped_cells(self, cell_updates: dict[str, Any]) -> Any:
        self._ensure_worksheet()

        if not cell_updates:
            return None

        try:
            cells = []
            for cell_address, value in cell_updates.items():
                if not cell_address or not isinstance(cell_address, str):
                    continue
                row, col = gspread.utils.a1_to_rowcol(cell_address)
                cells.append(Cell(row, col, value))

            if not cells:
                return None

            def _update_operation() -> Any:
                return self.worksheet.update_cells(cells)

            return self._retry_network_operation(
                _update_operation, "update_jumped_cells"
            )
        except Exception as e:
            logger.error("%s更新跳跃单元格失败: %s", self._log_ctx(), e, exc_info=True)
            raise

    def get_cell(self, cell_ref: str) -> Any:
        def _get_cell_operation() -> Any:
            return self.worksheet.get(cell_ref)[0][0]

        return self._retry_network_operation(
            _get_cell_operation, f"get_cell({cell_ref})"
        )

    def get_range(
        self, range_a1: str, value_render_option: str = "FORMATTED_VALUE"
    ) -> dict[str, Any]:
        self._ensure_worksheet()
        if not range_a1:
            return {}

        def _get_range_operation() -> dict[str, Any]:
            values_2d = self.worksheet.get(
                range_a1, value_render_option=value_render_option
            )
            start_row, start_col = a1_to_rowcol(range_a1.split(":")[0])
            result: dict[str, Any] = {}
            for r_idx, row in enumerate(values_2d):
                for c_idx, value in enumerate(row):
                    cell_a1 = rowcol_to_a1(start_row + r_idx, start_col + c_idx)
                    result[cell_a1] = value
            return result

        return self._retry_network_operation(
            _get_range_operation, f"get_range({range_a1})"
        )

    def get_ranges(
        self, range_a1_list: list[str], value_render_option: str = "FORMATTED_VALUE"
    ) -> dict[str, dict[str, Any]]:
        self._ensure_worksheet()

        if not range_a1_list:
            return {}

        normalized_ranges = [r for r in range_a1_list if r]
        if not normalized_ranges:
            return {}

        try:

            def _get_ranges_operation() -> list[Any]:
                return self.worksheet.batch_get(
                    normalized_ranges, value_render_option=value_render_option
                )

            batch_values = self._retry_network_operation(
                _get_ranges_operation, "get_ranges"
            )

            results: dict[str, dict[str, Any]] = {}
            for range_a1, values_2d in zip(
                normalized_ranges, batch_values, strict=False
            ):
                start_row, start_col = a1_to_rowcol(range_a1.split(":")[0])
                range_result: dict[str, Any] = {}
                for r_idx, row in enumerate(values_2d):
                    for c_idx, value in enumerate(row):
                        cell_a1 = rowcol_to_a1(start_row + r_idx, start_col + c_idx)
                        range_result[cell_a1] = value
                results[range_a1] = range_result

            for range_a1 in normalized_ranges:
                results.setdefault(range_a1, {})

            return results

        except Exception as e:
            logger.error("%s批量获取区间失败: %s", self._log_ctx(), e, exc_info=True)
            results = {}
            for range_a1 in normalized_ranges:
                try:
                    results[range_a1] = self.get_range(
                        range_a1, value_render_option=value_render_option
                    )
                except Exception as range_error:
                    logger.error(
                        "%s获取区间 %s 失败: %s", self._log_ctx(), range_a1, range_error
                    )
                    results[range_a1] = {}
            return results

    def get_range_2d(
        self, range_a1: str, value_render_option: str = "FORMATTED_VALUE"
    ) -> list[list[Any]]:
        self._ensure_worksheet()
        if not range_a1:
            return []

        def _get_range_operation() -> list[list[Any]]:
            return self.worksheet.get(range_a1, value_render_option=value_render_option)

        return self._retry_network_operation(
            _get_range_operation, f"get_range({range_a1})"
        )

    def get_cells_batch(self, cell_refs: list[str]) -> dict[str, Any]:
        self._ensure_worksheet()

        if not cell_refs:
            return {}

        try:

            def _batch_get_operation() -> list[Any]:
                return self.worksheet.batch_get(list(cell_refs))

            batch_values = self._retry_network_operation(
                _batch_get_operation, "get_cells_batch"
            )

            results: dict[str, Any] = {}
            for i, cell_ref in enumerate(cell_refs):
                if i < len(batch_values) and batch_values[i]:
                    value = batch_values[i][0][0] if batch_values[i][0] else ""
                    results[cell_ref] = value
                else:
                    results[cell_ref] = ""
            return results

        except Exception as e:
            logger.error("%s批量获取单元格失败: %s", self._log_ctx(), e, exc_info=True)
            results = {}
            for cell_ref in cell_refs:
                try:
                    results[cell_ref] = self.get_cell(cell_ref)
                except Exception as cell_error:
                    logger.error(
                        "%s获取单元格 %s 失败: %s",
                        self._log_ctx(),
                        cell_ref,
                        cell_error,
                    )
                    results[cell_ref] = ""
            return results

    def get_all_worksheets(self) -> list[str]:
        if not self.sheet:
            raise ValueError("未初始化Google Sheet连接")
        return [ws.title for ws in self.sheet.worksheets()]

    def _reconnect(self) -> bool:
        try:
            self._last_reconnect_exception = None
            logger.info("%s尝试重新连接Google Sheet", self._log_ctx())
            self.close()
            creds = Credentials.from_authorized_user_file(
                self._token_file, scopes=self._SCOPES
            )
            self.client = gspread.authorize(credentials=creds)

            self._apply_proxy_settings()
            self._apply_default_timeout()
            self.sheet = self.client.open_by_key(self.spreadsheet_id)
            self.title = self.sheet.title

            if self._sheet_name:
                try:
                    self.worksheet = self.sheet.worksheet(self._sheet_name)
                except Exception:
                    titles = [ws.title for ws in self.sheet.worksheets()]
                    target_lower = str(self._sheet_name).strip().lower()
                    matched_title = None
                    for t in titles:
                        if str(t).strip().lower() == target_lower:
                            matched_title = t
                            break
                    if matched_title:
                        self.worksheet = self.sheet.worksheet(matched_title)
                        self._sheet_name = matched_title
                    else:
                        raise Exception(
                            f"请先选择工作表: '{self._sheet_name}' 不存在，可用工作表: {titles}"
                        )
            logger.info("%sGoogle Sheet重新连接成功", self._log_ctx())
            return True
        except Exception as e:
            self._last_reconnect_exception = e
            logger.error("%s重新连接Google Sheet失败: %s", self._log_ctx(), e)
            return False

    def _is_network_error(self, exception: Exception) -> bool:
        try:
            from gspread.exceptions import APIError as _GSAPIError

            if isinstance(exception, _GSAPIError):
                resp = getattr(exception, "response", None)
                status = getattr(resp, "status_code", None)
                if isinstance(status, int) and (status >= 500 or status == 429):
                    return True
        except Exception:
            pass

        error_str = str(exception).lower()
        network_keywords = [
            "connection",
            "disconnected",
            "aborted",
            "remote end",
            "protocol error",
            "network",
            "timeout",
            "broken pipe",
            " 500",
            " 502",
            " 503",
            " 504",
            " 429",
        ]
        return any(keyword in error_str for keyword in network_keywords)

    def _ensure_worksheet(self) -> None:
        if not self.worksheet:
            if not self._reconnect():
                if self._last_reconnect_exception is not None:
                    if is_retryable_network_error(self._last_reconnect_exception):
                        raise RetryableNetworkTaskError(
                            f"{self._log_ctx()}重连Google Sheet失败: {self._last_reconnect_exception}"
                        ) from self._last_reconnect_exception
                    raise self._last_reconnect_exception
                raise Exception("请先选择工作表")

    def _retry_network_operation(
        self,
        operation: Any,
        operation_name: str,
        max_retries: int = 3,
        delay: int = 2,
        reconnect_on_error: bool = True,
    ) -> Any:
        last_exception: Exception | None = None
        for attempt in range(max_retries):
            try:
                self._ensure_worksheet()
                return operation()
            except Exception as e:
                if not self._is_network_error(e):
                    raise

                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = delay * (2**attempt)
                    logger.warning(
                        "%s网络错误 (尝试 %s/%s): %s. %s秒后重试...",
                        operation_name,
                        attempt + 1,
                        max_retries,
                        e,
                        wait_time,
                    )
                    if reconnect_on_error:
                        self._reconnect()
                    time.sleep(wait_time)
                else:
                    logger.error(
                        "%s网络错误，已重试 %s 次仍失败: %s",
                        operation_name,
                        max_retries,
                        e,
                    )
                    raise RetryableNetworkTaskError(
                        f"{self._log_ctx()}{operation_name} 网络错误，已重试 {max_retries} 次仍失败: {e}"
                    ) from e
        raise last_exception  # pragma: no cover

    def close(self) -> None:
        try:
            self.worksheet = None
            self.sheet = None
            if self.client:
                try:
                    session = self._get_client_session()
                    if session and hasattr(session, "close"):
                        session.close()
                except Exception:
                    pass
            self.client = None
        except Exception as e:
            logger.warning("关闭Google Sheet连接时出错: %s", e)

    def __enter__(self) -> GoogleSheet:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
