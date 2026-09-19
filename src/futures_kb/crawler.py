"""Controlled crawler execution and standard JSON import."""

from __future__ import annotations

import json
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from futures_kb.constants import DEFAULT_CONTRACT
from futures_kb.database import Database
from futures_kb.validation import (
    finite_float,
    normalize_symbol,
    optional_finite_float,
    validate_trade_date,
)


class CrawlerConfigurationError(ValueError):
    """Raised when a crawler is not configured or the config is invalid."""


class CrawlerRunner:
    """Run only commands explicitly listed in a local JSON configuration."""

    def __init__(
        self,
        database: Database,
        *,
        config_path: str | Path,
        raw_data_dir: str | Path,
        cwd: str | Path | None = None,
    ) -> None:
        self.database = database
        self.config_path = Path(config_path)
        self.raw_data_dir = Path(raw_data_dir)
        self.cwd = Path(cwd).resolve() if cwd else self.config_path.parent.resolve()

    def run(self, source: str, trade_date: str) -> dict[str, Any]:
        symbol = normalize_symbol(source)
        normalized_date = validate_trade_date(trade_date)
        config = self._load_config()
        source_config = config.get(symbol)
        if not isinstance(source_config, Mapping):
            raise CrawlerConfigurationError(f"crawler is not configured for {symbol}")

        command_template = source_config.get("command")
        if (
            not isinstance(command_template, list)
            or not command_template
            or not all(isinstance(item, str) and item for item in command_template)
        ):
            raise CrawlerConfigurationError(f"invalid command for {symbol}")

        output_path = self.raw_data_dir / symbol / f"{normalized_date}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        timeout_seconds = int(source_config.get("timeout_seconds", 60))
        substitutions = {
            "source": symbol,
            "trade_date": normalized_date,
            "output_path": str(output_path.resolve()),
        }
        command = [item.format(**substitutions) for item in command_template]
        run_id = uuid.uuid4().hex
        started_at = datetime.now(UTC).isoformat(timespec="seconds")

        self.database.record_crawler_run(
            {
                "run_id": run_id,
                "source": symbol,
                "trade_date": normalized_date,
                "status": "running",
                "started_at": started_at,
                "output_path": str(output_path),
            }
        )

        try:
            completed = subprocess.run(
                command,
                cwd=source_config.get("cwd") or self.cwd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return self._record_failure(
                run_id,
                symbol,
                normalized_date,
                started_at,
                output_path,
                error=str(exc),
            )

        stdout = completed.stdout.strip()
        if completed.returncode != 0:
            return self._record_failure(
                run_id,
                symbol,
                normalized_date,
                started_at,
                output_path,
                exit_code=completed.returncode,
                error=(completed.stderr or stdout or "crawler failed")[-2000:],
            )

        if stdout and not output_path.exists():
            output_path.write_text(stdout, encoding="utf-8")

        if not output_path.exists():
            return self._record_failure(
                run_id,
                symbol,
                normalized_date,
                started_at,
                output_path,
                exit_code=completed.returncode,
                error="crawler produced no output file or stdout JSON",
            )

        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            bars = _extract_bars(payload, expected_symbol=symbol, expected_date=normalized_date)
            imported = self.database.upsert_market_bars(bars)
        except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
            return self._record_failure(
                run_id,
                symbol,
                normalized_date,
                started_at,
                output_path,
                exit_code=completed.returncode,
                error=f"invalid crawler output: {exc}",
            )

        finished_at = datetime.now(UTC).isoformat(timespec="seconds")
        self.database.record_crawler_run(
            {
                "run_id": run_id,
                "source": symbol,
                "trade_date": normalized_date,
                "status": "success",
                "started_at": started_at,
                "finished_at": finished_at,
                "exit_code": completed.returncode,
                "output_path": str(output_path),
                "imported_bars": imported,
            }
        )
        return {
            "run_id": run_id,
            "source": symbol,
            "trade_date": normalized_date,
            "status": "success",
            "imported_bars": imported,
            "output_path": str(output_path),
        }

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            raise CrawlerConfigurationError(
                f"crawler config does not exist: {self.config_path}"
            )
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CrawlerConfigurationError("crawler config is invalid JSON") from exc
        if not isinstance(payload, dict):
            raise CrawlerConfigurationError("crawler config must be a JSON object")
        return payload

    def _record_failure(
        self,
        run_id: str,
        symbol: str,
        trade_date: str,
        started_at: str,
        output_path: Path,
        *,
        exit_code: int | None = None,
        error: str,
    ) -> dict[str, Any]:
        finished_at = datetime.now(UTC).isoformat(timespec="seconds")
        self.database.record_crawler_run(
            {
                "run_id": run_id,
                "source": symbol,
                "trade_date": trade_date,
                "status": "failed",
                "started_at": started_at,
                "finished_at": finished_at,
                "exit_code": exit_code,
                "output_path": str(output_path),
                "error": error,
            }
        )
        return {
            "run_id": run_id,
            "source": symbol,
            "trade_date": trade_date,
            "status": "failed",
            "imported_bars": 0,
            "error": error,
        }


def _extract_bars(
    payload: Any, *, expected_symbol: str, expected_date: str
) -> list[dict[str, Any]]:
    raw_bars = payload.get("bars") if isinstance(payload, dict) else payload
    if not isinstance(raw_bars, list) or not raw_bars:
        raise ValueError("expected a non-empty JSON list or an object with a bars list")

    bars: list[dict[str, Any]] = []
    for item in raw_bars:
        if not isinstance(item, Mapping):
            raise ValueError("each bar must be an object")
        symbol = normalize_symbol(str(item.get("symbol") or expected_symbol))
        if symbol != expected_symbol:
            raise ValueError(f"bar symbol {symbol} does not match crawler source {expected_symbol}")
        trade_date = validate_trade_date(str(item.get("trade_date") or expected_date))
        if trade_date != expected_date:
            raise ValueError(
                f"bar trade_date {trade_date} does not match crawler run {expected_date}"
            )
        bars.append(
            {
                "trade_date": trade_date,
                "symbol": symbol,
                "contract": str(item.get("contract") or DEFAULT_CONTRACT),
                "open": optional_finite_float(item.get("open"), field="open"),
                "high": optional_finite_float(item.get("high"), field="high"),
                "low": optional_finite_float(item.get("low"), field="low"),
                "close": finite_float(item.get("close"), field="close"),
                "settlement": optional_finite_float(
                    item.get("settlement"), field="settlement"
                ),
                "volume": optional_finite_float(item.get("volume"), field="volume"),
                "open_interest": optional_finite_float(
                    item.get("open_interest"), field="open_interest"
                ),
                "source": str(item.get("source") or f"crawler:{symbol}"),
                "is_main": bool(item.get("is_main", True)),
            }
        )
    return bars
