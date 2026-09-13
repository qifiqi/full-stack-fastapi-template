"""DingTalk webhook notifier (worker-side port; no Flask, no RBAC lookups)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import logging
import socket
import time
from typing import Any

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

NOTIFY_KEYWORDS = {"error": "告警", "success": "任务完成"}

# Constant webhook endpoint; dynamic values travel as query params only.
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send"


def _assert_webhook_endpoint_safe() -> None:
    """SSRF guard: pinned https host that resolves to globally-routable IPs."""
    hostname = "oapi.dingtalk.com"
    try:
        addr_infos = socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise ValueError("钉钉 webhook 域名解析失败") from exc
    for info in addr_infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError(f"钉钉 webhook 解析到非公网地址: {ip}")


def _generate_signature(secret: str) -> tuple[str, str]:
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"), string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
    ).digest()
    sign = urllib_parse_quote(base64.b64encode(hmac_code))
    return timestamp, sign


def urllib_parse_quote(value: bytes) -> str:
    import urllib.parse

    return urllib.parse.quote_plus(value)


def _build_markdown_text(
    keyword: str,
    fields: list[tuple[str, Any]],
    *,
    summary: str | None = None,
    detail_url: str | None = None,
) -> str:
    lines = [f"### {keyword}", ""]
    for label, value in fields:
        normalized_value = str(value or "").strip() or "-"
        lines.append(f"- **{label}**：{normalized_value}")
    summary_text = str(summary or "").strip()
    if summary_text:
        lines.extend(["", "> 摘要", f"> {summary_text}"])
    if detail_url:
        lines.extend(["", f"[查看详情]({detail_url})"])
    return "\n".join(lines)


def send_task_notification(
    *,
    task_id: int | str,
    task_name: str = "",
    notify_type: str = "error",
    summary: str | None = None,
    detail_url: str | None = None,
) -> dict[str, Any] | None:
    """Fire-and-forget webhook; never raises into the task chain."""
    try:
        return _send_task_notification(
            task_id=task_id,
            task_name=task_name,
            notify_type=notify_type,
            summary=summary,
            detail_url=detail_url,
        )
    except Exception as e:
        logger.error("发送钉钉消息失败: %s", e)
        return {"error": str(e)}


def _send_task_notification(
    *,
    task_id: int | str,
    task_name: str,
    notify_type: str,
    summary: str | None,
    detail_url: str | None,
) -> dict[str, Any] | None:
    if not settings.ding_talk_access_token or not settings.ding_talk_secret:
        logger.info("钉钉通知未配置，跳过: task_id=%s", task_id)
        return None

    keyword = NOTIFY_KEYWORDS.get(notify_type, "通知")
    title = (
        f"{keyword} - {'任务执行完成' if notify_type == 'success' else '任务执行失败'}"
    )
    target_url = detail_url
    if not target_url and settings.base_url:
        target_url = f"{settings.base_url.rstrip('/')}/tasks/{task_id}"

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": _build_markdown_text(
                keyword,
                [
                    ("任务状态", title),
                    ("任务名称", task_name or "-"),
                    ("任务ID", str(task_id)),
                    ("通知时间", time.strftime("%Y-%m-%d %H:%M:%S")),
                ],
                summary=summary,
                detail_url=target_url,
            ),
        },
        "at": {"isAtAll": False},
    }
    return send_message(payload)


def send_message(data: dict[str, Any]) -> dict[str, Any] | None:
    if not settings.ding_talk_access_token or not settings.ding_talk_secret:
        logger.error("钉钉通知发送失败: access_token 或 secret 未配置")
        return {"error": "ding_talk_not_configured"}

    _assert_webhook_endpoint_safe()
    timestamp, sign = _generate_signature(settings.ding_talk_secret)
    response = requests.post(
        DINGTALK_WEBHOOK,
        params={
            "access_token": settings.ding_talk_access_token,
            "timestamp": timestamp,
            "sign": sign,
        },
        json=data,
        timeout=10,
        allow_redirects=False,
    )
    response.raise_for_status()
    result: dict[str, Any] = response.json()
    if result.get("errcode") not in (None, 0):
        logger.error("钉钉通知发送失败: %s", result)
    else:
        logger.info("钉钉通知发送成功")
    return result
