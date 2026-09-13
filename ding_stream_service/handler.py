"""DingTalk stream event handler."""

from __future__ import annotations

import logging
import random
import re
import time
from typing import Any

import dingtalk_stream
import requests

from ding_stream_service.message_format import build_markdown_message
from ding_stream_service.task_commands import TaskCommandService


logger = logging.getLogger(__name__)


def build_dingtalk_reply_payload(reply_text: str) -> dict[str, Any]:
    """Build a DingTalk robot message payload for sessionWebhook replies."""
    title = _extract_markdown_title(reply_text)
    text = reply_text
    if not title:
        # Keep every reply on the same DingTalk message type even when callers
        # accidentally return plain text.
        title = "任务助手"
        text = build_markdown_message(title, [], summary=reply_text)
    return {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": text,
        },
    }


class DingStreamEventHandler(dingtalk_stream.EventHandler):
    def __init__(self):
        self.task_command_service = TaskCommandService()

    async def process(self, event: dingtalk_stream.EventMessage):
        try:
            logger.info("收到事件类型: %s", event.headers.event_type)
            msg_data = event.data
            if "text" in msg_data and "conversationId" in msg_data:
                return await self.handle_bot_message(event)

            logger.info("非消息事件，已忽略")
        except Exception as exc:
            logger.exception("处理钉钉事件失败: %s", exc)

        return dingtalk_stream.AckMessage.STATUS_OK, "OK"

    async def handle_bot_message(self, event: dingtalk_stream.EventMessage):
        msg_data = event.data

        text_content = msg_data.get("text", {}).get("content", "").strip()
        sender_id = msg_data.get("senderId", "")
        sender_nick = msg_data.get("senderNick", "")
        conversation_id = msg_data.get("conversationId", "")
        conversation_type = msg_data.get("conversationType", "")
        session_webhook = msg_data.get("sessionWebhook", "")

        logger.info(
            "收到钉钉消息 sender=%s sender_id=%s conversation_id=%s type=%s",
            sender_nick,
            sender_id,
            conversation_id,
            "group" if conversation_type == "2" else "single",
        )

        if not text_content:
            logger.info("消息内容为空，跳过处理")
            return dingtalk_stream.AckMessage.STATUS_OK, "OK"

        reply_text = self.process_message(text_content, sender_nick, conversation_id)
        if reply_text:
            await self.send_reply_via_webhook(session_webhook, reply_text)

        return dingtalk_stream.AckMessage.STATUS_OK, "OK"

    def process_message(
        self,
        text: str,
        sender_nick: str,
        conversation_id: str = "default",
    ) -> str:
        text = re.sub(r"@[\u4e00-\u9fa5a-zA-Z0-9_]+", "", text).strip()
        logger.info("处理后消息: %s", text)

        if not text:
            return self.build_help_menu(sender_nick)

        task_command_result = self.task_command_service.handle_message(
            text,
            sender_nick,
            conversation_id,
        )
        if task_command_result.handled:
            return task_command_result.message

        if text in ["帮助", "help", "功能", "菜单", "?", "？"]:
            return self.build_help_menu(sender_nick)


        if text in ["你好", "您好", "hi", "hello", "hey", "大家好"]:
            greetings = [
                "你好，欢迎使用任务运维助手。",
                "Hi，很高兴见到你。",
                "你好，回复“帮助”查看功能菜单。",
            ]
            return build_markdown_message(
                "任务助手",
                [("用户", sender_nick), ("处理结果", "已收到问候")],
                summary=random.choice(greetings),
            )

        if text in ["时间", "几点", "现在几点", "当前时间"]:
            current_time = time.strftime("%Y年%m月%d日 %H:%M:%S")
            return build_markdown_message(
                "时间查询",
                [("用户", sender_nick), ("当前时间", current_time)],
            )

        if text in ["日期", "今天", "几号", "今天几号"]:
            current_date = time.strftime("%Y年%m月%d日")
            weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][
                time.localtime().tm_wday
            ]
            return build_markdown_message(
                "日期查询",
                [("用户", sender_nick), ("当前日期", f"{current_date} {weekday}")],
            )

        if any(keyword in text for keyword in ["谢谢", "感谢", "多谢", "thanks", "thank"]):
            return build_markdown_message(
                "任务助手",
                [("用户", sender_nick), ("处理结果", "已收到")],
                summary="不客气。",
            )

        if text:
            return build_markdown_message(
                "未识别指令",
                [("用户", sender_nick), ("消息内容", text)],
                summary="回复“帮助”查看可用指令。",
            )

        return self.build_help_menu(sender_nick)

    def build_help_menu(self, sender_nick: str) -> str:
        return build_markdown_message(
            "任务助手菜单",
            [
                ("用户", sender_nick),
                ("查看运行任务", "查看当前 running 任务"),
                ("查看停止任务", "查看 completed / cancelled / error 任务"),
                ("重启任务 <任务ID或任务名>", "按断点重启任务"),
                ("重启异常任务", "批量断点重启最近的 error 任务，默认 5 个"),
                ("断点重启 <钉钉告警内容>", "从告警中识别任务ID并重启"),
                ("时间", "查看当前时间"),
                ("日期", "显示今天日期"),
                ("帮助", "显示此菜单"),
            ],
            summary=(
                "分页示例：查看运行任务 第2页 每页5条；查看停止任务 第1页 每页10条\n"
                "组合示例：重启异常任务；重启异常任务 数量10"
            ),
        )

    async def send_reply_via_webhook(self, webhook_url: str, reply_text: str) -> None:
        if not webhook_url:
            logger.warning("sessionWebhook 为空，无法发送回复")
            return

        try:
            payload = build_dingtalk_reply_payload(reply_text)
            logger.info(
                "发送钉钉回复: msgtype=%s title=%s content_length=%s",
                payload.get("msgtype"),
                payload.get("markdown", {}).get("title"),
                len(reply_text or ""),
            )
            response = requests.post(
                webhook_url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            response.raise_for_status()
            result = response.json()
            if result.get("errcode") != 0:
                logger.warning("钉钉回复失败: %s", result)
                return
            logger.info("钉钉回复发送成功")
        except Exception as exc:
            logger.exception("发送钉钉回复失败: %s", exc)


def _extract_markdown_title(reply_text: str) -> str | None:
    first_line = str(reply_text or "").splitlines()[0].strip()
    if not first_line.startswith("### "):
        return None
    title = first_line.removeprefix("### ").strip()
    return title or None
