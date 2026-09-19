"""SQLite persistence for market, manual, research, and crawler data."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from futures_kb.constants import DEFAULT_CONTRACT


SCHEMA = """
CREATE TABLE IF NOT EXISTS market_bars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    contract TEXT NOT NULL DEFAULT 'MAIN',
    open REAL,
    high REAL,
    low REAL,
    close REAL NOT NULL,
    settlement REAL,
    volume REAL,
    open_interest REAL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    is_main INTEGER NOT NULL DEFAULT 1 CHECK (is_main IN (0, 1)),
    UNIQUE (trade_date, symbol, contract, source)
);

CREATE INDEX IF NOT EXISTS idx_market_bars_lookup
    ON market_bars (symbol, contract, trade_date DESC, fetched_at DESC);

CREATE TABLE IF NOT EXISTS manual_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual',
    confirmed INTEGER NOT NULL DEFAULT 1 CHECK (confirmed IN (0, 1)),
    created_at TEXT NOT NULL,
    UNIQUE (trade_date, symbol, metric, source)
);

CREATE INDEX IF NOT EXISTS idx_manual_metrics_lookup
    ON manual_metrics (symbol, metric, trade_date DESC);

CREATE TABLE IF NOT EXISTS research_notes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    published_at TEXT NOT NULL,
    symbols_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_research_notes_published
    ON research_notes (published_at DESC);

CREATE TABLE IF NOT EXISTS crawler_runs (
    run_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    exit_code INTEGER,
    output_path TEXT,
    imported_bars INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_crawler_runs_lookup
    ON crawler_runs (source, trade_date, started_at DESC);
"""


def utc_now_iso() -> str:
    """Return a stable UTC timestamp for persisted records."""

    return datetime.now(UTC).isoformat(timespec="seconds")


class Database:
    """Small SQLite repository used by the API and MCP layers."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def upsert_market_bars(self, records: Iterable[Mapping[str, Any]]) -> int:
        rows = list(records)
        if not rows:
            return 0

        fetched_at = utc_now_iso()
        with self.connect() as connection:
            for record in rows:
                connection.execute(
                    """
                    INSERT INTO market_bars (
                        trade_date, symbol, contract, open, high, low, close,
                        settlement, volume, open_interest, source, fetched_at, is_main
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (trade_date, symbol, contract, source) DO UPDATE SET
                        open = excluded.open,
                        high = excluded.high,
                        low = excluded.low,
                        close = excluded.close,
                        settlement = excluded.settlement,
                        volume = excluded.volume,
                        open_interest = excluded.open_interest,
                        fetched_at = excluded.fetched_at,
                        is_main = excluded.is_main
                    """,
                    (
                        str(record["trade_date"]),
                        str(record["symbol"]).upper(),
                        str(record.get("contract") or DEFAULT_CONTRACT),
                        _optional_float(record.get("open")),
                        _optional_float(record.get("high")),
                        _optional_float(record.get("low")),
                        float(record["close"]),
                        _optional_float(record.get("settlement")),
                        _optional_float(record.get("volume")),
                        _optional_float(record.get("open_interest")),
                        str(record.get("source") or "crawler"),
                        str(record.get("fetched_at") or fetched_at),
                        1 if record.get("is_main", True) else 0,
                    ),
                )
        return len(rows)

    def get_market_history(
        self,
        symbol: str,
        end_date: str,
        *,
        contract: str = DEFAULT_CONTRACT,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT trade_date, symbol, contract, open, high, low, close,
                       settlement, volume, open_interest, source, fetched_at
                FROM market_bars
                WHERE symbol = ?
                  AND contract = ?
                  AND trade_date <= ?
                  AND is_main = 1
                ORDER BY trade_date DESC, fetched_at DESC
                LIMIT ?
                """,
                (symbol.upper(), contract, end_date, max(limit * 4, limit)),
            ).fetchall()

        seen_dates: set[str] = set()
        history: list[dict[str, Any]] = []
        for row in rows:
            trade_date = str(row["trade_date"])
            if trade_date in seen_dates:
                continue
            seen_dates.add(trade_date)
            history.append(dict(row))
            if len(history) >= limit:
                break
        return history

    def upsert_manual_metrics(self, records: Iterable[Mapping[str, Any]]) -> int:
        rows = list(records)
        if not rows:
            return 0

        created_at = utc_now_iso()
        with self.connect() as connection:
            for record in rows:
                connection.execute(
                    """
                    INSERT INTO manual_metrics (
                        trade_date, symbol, metric, value, unit, source,
                        confirmed, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (trade_date, symbol, metric, source) DO UPDATE SET
                        value = excluded.value,
                        unit = excluded.unit,
                        confirmed = excluded.confirmed,
                        created_at = excluded.created_at
                    """,
                    (
                        str(record["trade_date"]),
                        str(record["symbol"]).upper(),
                        str(record["metric"]),
                        float(record["value"]),
                        str(record.get("unit") or ""),
                        str(record.get("source") or "manual"),
                        1 if record.get("confirmed", True) else 0,
                        created_at,
                    ),
                )
        return len(rows)

    def get_manual_metrics(
        self, symbol: str, as_of_date: str, *, limit: int = 50
    ) -> dict[str, dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT trade_date, symbol, metric, value, unit, source,
                       confirmed, created_at
                FROM manual_metrics
                WHERE symbol = ? AND trade_date <= ?
                ORDER BY trade_date DESC, created_at DESC
                LIMIT ?
                """,
                (symbol.upper(), as_of_date, max(limit * 4, limit)),
            ).fetchall()

        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            metric = str(row["metric"])
            if metric in latest:
                continue
            latest[metric] = dict(row)
            if len(latest) >= limit:
                break
        return latest

    def get_previous_metric(
        self, symbol: str, metric: str, before_date: str
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT trade_date, symbol, metric, value, unit, source, confirmed
                FROM manual_metrics
                WHERE symbol = ? AND metric = ? AND trade_date < ?
                ORDER BY trade_date DESC, created_at DESC
                LIMIT 1
                """,
                (symbol.upper(), metric, before_date),
            ).fetchone()
        return dict(row) if row else None

    def upsert_research_notes(self, records: Iterable[Mapping[str, Any]]) -> int:
        rows = list(records)
        if not rows:
            return 0

        created_at = utc_now_iso()
        with self.connect() as connection:
            for record in rows:
                symbols = [str(item).upper() for item in record.get("symbols", [])]
                connection.execute(
                    """
                    INSERT INTO research_notes (
                        id, title, content, source, published_at, symbols_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (id) DO UPDATE SET
                        title = excluded.title,
                        content = excluded.content,
                        source = excluded.source,
                        published_at = excluded.published_at,
                        symbols_json = excluded.symbols_json
                    """,
                    (
                        str(record["id"]),
                        str(record["title"]),
                        str(record["content"]),
                        str(record.get("source") or "manual"),
                        str(record["published_at"]),
                        json.dumps(symbols, ensure_ascii=False),
                        created_at,
                    ),
                )
        return len(rows)

    def search_research(
        self,
        query: str,
        *,
        symbols: Sequence[str] | None = None,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        normalized_query = query.strip()
        with self.connect() as connection:
            if normalized_query:
                pattern = f"%{normalized_query}%"
                rows = connection.execute(
                    """
                    SELECT id, title, content, source, published_at, symbols_json
                    FROM research_notes
                    WHERE title LIKE ? OR content LIKE ?
                    ORDER BY published_at DESC
                    LIMIT ?
                    """,
                    (pattern, pattern, max(limit * 5, limit)),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT id, title, content, source, published_at, symbols_json
                    FROM research_notes
                    ORDER BY published_at DESC
                    LIMIT ?
                    """,
                    (max(limit * 5, limit),),
                ).fetchall()

        requested = {item.upper() for item in symbols or []}
        results: list[dict[str, Any]] = []
        for row in rows:
            item_symbols = set(json.loads(row["symbols_json"] or "[]"))
            if requested and not requested.intersection(item_symbols):
                continue
            result = dict(row)
            result["symbols"] = sorted(item_symbols)
            result.pop("symbols_json", None)
            results.append(result)
            if len(results) >= limit:
                break
        return results

    def get_recent_research(
        self,
        symbols: Sequence[str],
        as_of_date: str,
        *,
        days: int = 7,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        start_date = _iso_date_minus_days(as_of_date, days)
        requested = {item.upper() for item in symbols}
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, content, source, published_at, symbols_json
                FROM research_notes
                WHERE published_at >= ? AND published_at <= ?
                ORDER BY published_at DESC
                LIMIT ?
                """,
                (start_date, as_of_date, max(limit * 8, limit)),
            ).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            item_symbols = set(json.loads(row["symbols_json"] or "[]"))
            if not requested.intersection(item_symbols) and item_symbols:
                continue
            result = dict(row)
            result["symbols"] = sorted(item_symbols)
            result.pop("symbols_json", None)
            results.append(result)
            if len(results) >= limit:
                break
        return results

    def record_crawler_run(self, record: Mapping[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO crawler_runs (
                    run_id, source, trade_date, status, started_at, finished_at,
                    exit_code, output_path, imported_bars, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (run_id) DO UPDATE SET
                    status = excluded.status,
                    finished_at = excluded.finished_at,
                    exit_code = excluded.exit_code,
                    output_path = excluded.output_path,
                    imported_bars = excluded.imported_bars,
                    error = excluded.error
                """,
                (
                    str(record["run_id"]),
                    str(record["source"]).upper(),
                    str(record["trade_date"]),
                    str(record["status"]),
                    str(record["started_at"]),
                    record.get("finished_at"),
                    record.get("exit_code"),
                    record.get("output_path"),
                    int(record.get("imported_bars") or 0),
                    record.get("error"),
                ),
            )

    def get_latest_crawler_runs(
        self, symbols: Sequence[str], as_of_date: str
    ) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        with self.connect() as connection:
            for symbol in symbols:
                row = connection.execute(
                    """
                    SELECT run_id, source, trade_date, status, started_at, finished_at,
                           exit_code, output_path, imported_bars, error
                    FROM crawler_runs
                    WHERE source = ? AND trade_date <= ?
                    ORDER BY trade_date DESC, started_at DESC
                    LIMIT 1
                    """,
                    (symbol.upper(), as_of_date),
                ).fetchone()
                if row:
                    result[symbol.upper()] = dict(row)
        return result


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _iso_date_minus_days(value: str, days: int) -> str:
    from datetime import date, timedelta

    parsed = date.fromisoformat(value)
    return (parsed - timedelta(days=days)).isoformat()
