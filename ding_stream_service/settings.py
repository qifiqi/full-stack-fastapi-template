"""Configuration for the DingTalk stream microservice."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DingStreamSettings:
    client_id: str
    client_secret: str

    @classmethod
    def from_env(cls) -> "DingStreamSettings":
        env_files = [PROJECT_ROOT / ".env"]
        load_dotenv(env_files[0])
        app_env = os.getenv("APP_ENV", "development").strip().lower() or "development"
        env_app_file = PROJECT_ROOT / f".env.{app_env}"
        env_files.append(env_app_file)
        load_dotenv(env_app_file, override=True)

        client_id = os.getenv("DING_STREAM_CLIENT_ID", "").strip()
        client_secret = os.getenv("DING_STREAM_CLIENT_SECRET", "").strip()

        if not client_id or not client_secret:
            checked = ", ".join(
                str(path.relative_to(PROJECT_ROOT)) if path.exists() else f"{path.name}(不存在)"
                for path in env_files
            )
            raise ValueError(
                "缺少钉钉 Stream 凭据：请在项目根目录 .env 或 .env."
                f"{app_env} 中配置 DING_STREAM_CLIENT_ID 和 DING_STREAM_CLIENT_SECRET"
                f"（本次检查的文件：{checked}；当前 APP_ENV={app_env}）"
            )

        return cls(
            client_id=client_id,
            client_secret=client_secret,
        )
