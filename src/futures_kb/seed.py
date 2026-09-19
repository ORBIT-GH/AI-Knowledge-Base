"""Seed deterministic demo data for local evaluation."""

from __future__ import annotations

import argparse
import math
from datetime import date, timedelta

from futures_kb.config import Settings
from futures_kb.constants import DEFAULT_SYMBOLS, SYMBOL_NAMES
from futures_kb.database import Database


BASE_PRICES = {"SH": 2400.0, "V": 5200.0, "JM": 1250.0}


def seed(database: Database, *, end_date: str, days: int = 60) -> dict[str, int]:
    database.initialize()
    parsed_end = date.fromisoformat(end_date)
    start = parsed_end - timedelta(days=days - 1)

    bars: list[dict] = []
    manual: list[dict] = []
    for offset in range(days):
        trade_date = (start + timedelta(days=offset)).isoformat()
        for index, symbol in enumerate(DEFAULT_SYMBOLS):
            base = BASE_PRICES[symbol]
            close = base + offset * (2.0 + index) + math.sin(offset / 3) * 18
            bars.append(
                {
                    "trade_date": trade_date,
                    "symbol": symbol,
                    "contract": "MAIN",
                    "open": close - 8,
                    "high": close + 20,
                    "low": close - 22,
                    "close": round(close, 2),
                    "settlement": round(close, 2),
                    "volume": 120000 + offset * 800 + index * 5000,
                    "open_interest": 210000 + offset * 300 + index * 10000,
                    "source": "seed",
                    "is_main": True,
                }
            )

        if offset % 5 == 0:
            for index, symbol in enumerate(DEFAULT_SYMBOLS):
                base = BASE_PRICES[symbol]
                manual.append(
                    {
                        "trade_date": trade_date,
                        "symbol": symbol,
                        "metric": "spot_price",
                        "value": round(base + offset * (2.0 + index) - 12, 2),
                        "unit": "",
                        "source": "seed",
                    }
                )
                manual.append(
                    {
                        "trade_date": trade_date,
                        "symbol": symbol,
                        "metric": "inventory",
                        "value": 300000 + index * 100000 - offset * 450,
                        "unit": "t",
                        "source": "seed",
                    }
                )

    research = [
        {
            "id": f"seed-news-{parsed_end.isoformat()}",
            "title": "示例：氯碱与黑色产业链观察",
            "content": "这是用于本地验证的示例资讯。正式使用时应替换为你的爬虫和资讯源。",
            "source": "seed",
            "published_at": parsed_end.isoformat(),
            "symbols": list(DEFAULT_SYMBOLS),
        }
    ]

    database.upsert_market_bars(bars)
    database.upsert_manual_metrics(manual)
    database.upsert_research_notes(research)
    return {"market_bars": len(bars), "manual_metrics": len(manual), "research": len(research)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo futures data")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--days", type=int, default=60)
    args = parser.parse_args()

    settings = Settings.from_env()
    database = Database(settings.database_path)
    counts = seed(database, end_date=args.date, days=args.days)
    print(f"database: {settings.database_path}")
    print(f"symbols: {', '.join(f'{key}={value}' for key, value in SYMBOL_NAMES.items())}")
    print(f"inserted: {counts}")


if __name__ == "__main__":
    main()
