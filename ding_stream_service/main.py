"""Entry point for the DingTalk stream microservice."""

from __future__ import annotations

import argparse
import logging

import dingtalk_stream

from ding_stream_service.handler import DingStreamEventHandler
from ding_stream_service.settings import DingStreamSettings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id", help="覆盖 .env 中的 DING_STREAM_CLIENT_ID")
    parser.add_argument("--client-secret", help="覆盖 .env 中的 DING_STREAM_CLIENT_SECRET")
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> None:
    configure_logging()
    args = parse_args()

    settings = DingStreamSettings.from_env()
    if args.client_id or args.client_secret:
        settings = DingStreamSettings(
            client_id=args.client_id or settings.client_id,
            client_secret=args.client_secret or settings.client_secret,
        )

    credential = dingtalk_stream.Credential(settings.client_id, settings.client_secret)
    client = dingtalk_stream.DingTalkStreamClient(credential)
    client.register_callback_handler(
        "/v1.0/im/bot/messages/get",
        DingStreamEventHandler(),
    )

    logging.getLogger(__name__).info("钉钉 Stream 微服务启动成功")
    client.start_forever()


if __name__ == "__main__":
    main()
