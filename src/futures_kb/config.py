"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_path: Path
    crawler_config_path: Path
    raw_data_dir: Path
    api_key: str | None = None
    api_host: str = "127.0.0.1"
    api_port: int = 8787

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_path=Path(
                os.getenv("FUTURES_KB_DB", "data/futures_kb.sqlite3")
            ).resolve(),
            crawler_config_path=Path(
                os.getenv(
                    "FUTURES_KB_CRAWLER_CONFIG",
                    "config/crawlers.local.json",
                )
            ).resolve(),
            raw_data_dir=Path(
                os.getenv("FUTURES_KB_RAW_DIR", "data/raw")
            ).resolve(),
            api_key=os.getenv("FUTURES_KB_API_KEY") or None,
            api_host=os.getenv("FUTURES_KB_API_HOST", "127.0.0.1"),
            api_port=int(os.getenv("FUTURES_KB_API_PORT", "8787")),
        )
