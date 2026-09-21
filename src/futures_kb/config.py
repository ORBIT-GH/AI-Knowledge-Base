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
    backend: str = "native"
    futures_intel_root: Path | None = None
    futures_intel_config: Path | None = None
    futures_intel_timeout_seconds: int = 300
    fetch_5m: bool = False
    intraday_timeout_seconds: int = 10

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
            backend=os.getenv("FUTURES_KB_BACKEND", "native").strip().lower(),
            futures_intel_root=_optional_path(os.getenv("FUTURES_INTEL_ROOT")),
            futures_intel_config=_optional_path(os.getenv("FUTURES_INTEL_CONFIG")),
            futures_intel_timeout_seconds=int(
                os.getenv("FUTURES_INTEL_TIMEOUT_SECONDS", "300")
            ),
            fetch_5m=os.getenv("FUTURES_KB_FETCH_5M", "0").strip().lower()
            in {"1", "true", "yes", "on"},
            intraday_timeout_seconds=int(
                os.getenv("FUTURES_KB_5M_TIMEOUT_SECONDS", "10")
            ),
        )


def _optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    return Path(value).expanduser().resolve()
