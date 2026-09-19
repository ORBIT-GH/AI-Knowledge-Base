from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from futures_kb.database import Database


@pytest.fixture
def database(tmp_path: Path) -> Database:
    db = Database(tmp_path / "test.sqlite3")
    db.initialize()
    return db


@pytest.fixture
def seeded_database(database: Database) -> Database:
    start = date(2026, 8, 20)
    bars = []
    for index in range(20):
        trade_date = (start + timedelta(days=index)).isoformat()
        for symbol, base in (("SH", 2300), ("V", 5000), ("JM", 1200)):
            close = base + index * 10
            bars.append(
                {
                    "trade_date": trade_date,
                    "symbol": symbol,
                    "contract": "MAIN",
                    "open": close - 5,
                    "high": close + 12,
                    "low": close - 15,
                    "close": close,
                    "settlement": close,
                    "volume": 100000 + index * 1000,
                    "open_interest": 200000 + index * 500,
                    "source": "fixture",
                    "is_main": True,
                }
            )
    database.upsert_market_bars(bars)
    database.upsert_manual_metrics(
        [
            {
                "trade_date": "2026-09-08",
                "symbol": "SH",
                "metric": "spot_price",
                "value": 2520,
                "unit": "",
                "source": "manual",
            },
            {
                "trade_date": "2026-09-06",
                "symbol": "SH",
                "metric": "inventory",
                "value": 320000,
                "unit": "t",
                "source": "manual",
            },
            {
                "trade_date": "2026-09-08",
                "symbol": "SH",
                "metric": "inventory",
                "value": 300000,
                "unit": "t",
                "source": "manual",
            },
        ]
    )
    database.upsert_research_notes(
        [
            {
                "id": "news-1",
                "title": "氯碱装置检修",
                "content": "某氯碱企业计划检修，影响烧碱和PVC供应。" + "x" * 300,
                "source": "test",
                "published_at": "2026-09-08",
                "symbols": ["SH", "V"],
            }
        ]
    )
    return database
