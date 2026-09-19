"""Application service shared by the HTTP API and MCP server."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from futures_kb.config import Settings
from futures_kb.crawler import CrawlerRunner
from futures_kb.database import Database
from futures_kb.models import (
    ManualMetricInput,
    MarketBarInput,
    ResearchNoteInput,
)
from futures_kb.reporting import build_daily_report_context, estimate_tokens
from futures_kb.validation import (
    finite_float,
    normalize_symbol,
    normalize_symbols,
    optional_finite_float,
    validate_metric_name,
    validate_trade_date,
)


class FuturesDataService:
    """Validated use cases exposed to transport layers."""

    def __init__(self, database: Database, crawler_runner: CrawlerRunner) -> None:
        self.database = database
        self.crawler_runner = crawler_runner

    def upsert_market_bars(self, payloads: Iterable[MarketBarInput]) -> int:
        records = [_validated_market_bar(item) for item in payloads]
        return self.database.upsert_market_bars(records)

    def upsert_manual_metrics(self, payloads: Iterable[ManualMetricInput]) -> int:
        records = [_validated_manual_metric(item) for item in payloads]
        return self.database.upsert_manual_metrics(records)

    def upsert_research_notes(self, payloads: Iterable[ResearchNoteInput]) -> int:
        records = [_validated_research_note(item) for item in payloads]
        return self.database.upsert_research_notes(records)

    def report_context(
        self, trade_date: str, *, symbols: list[str] | None = None
    ) -> dict:
        return build_daily_report_context(
            self.database,
            validate_trade_date(trade_date),
            symbols=normalize_symbols(symbols) if symbols else None,
        )

    def submit_manual_metrics(
        self, records: Iterable[ManualMetricInput]
    ) -> dict[str, object]:
        payloads = list(records)
        validated = [_validated_manual_metric(item) for item in payloads]
        accepted = self.database.upsert_manual_metrics(validated)
        return {
            "accepted": accepted,
            "trade_dates": sorted({item["trade_date"] for item in validated}),
            "symbols": sorted({item["symbol"] for item in validated}),
        }

    def run_crawler(self, source: str, trade_date: str) -> dict:
        return self.crawler_runner.run(source, trade_date)

    def search_research(
        self,
        query: str,
        *,
        symbols: list[str] | None = None,
        limit: int = 3,
    ) -> dict:
        normalized_symbols = (
            list(normalize_symbols(symbols)) if symbols else None
        )
        items = self.database.search_research(
            query,
            symbols=normalized_symbols,
            limit=max(1, min(limit, 3)),
        )
        results = []
        for item in items:
            content = str(item.get("content") or "").strip().replace("\n", " ")
            excerpt = content[:180]
            if len(content) > 180:
                excerpt += "…"
            results.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "excerpt": excerpt,
                    "source": item["source"],
                    "published_at": item["published_at"],
                    "symbols": item.get("symbols", []),
                }
            )
        payload = {"query": query, "results": results}
        payload["token_estimate"] = estimate_tokens(payload)
        return payload


def create_service(
    *,
    settings: Settings | None = None,
    database: Database | None = None,
    crawler_runner: CrawlerRunner | None = None,
) -> FuturesDataService:
    effective_settings = settings or Settings.from_env()
    effective_database = database or Database(effective_settings.database_path)
    effective_database.initialize()
    effective_crawler = crawler_runner or CrawlerRunner(
        effective_database,
        config_path=effective_settings.crawler_config_path,
        raw_data_dir=effective_settings.raw_data_dir,
    )
    return FuturesDataService(effective_database, effective_crawler)


def _validated_market_bar(payload: MarketBarInput) -> dict:
    return {
        "trade_date": validate_trade_date(payload.trade_date),
        "symbol": normalize_symbol(payload.symbol),
        "contract": payload.contract.strip() or "MAIN",
        "open": optional_finite_float(payload.open, field="open"),
        "high": optional_finite_float(payload.high, field="high"),
        "low": optional_finite_float(payload.low, field="low"),
        "close": finite_float(payload.close, field="close"),
        "settlement": optional_finite_float(payload.settlement, field="settlement"),
        "volume": optional_finite_float(payload.volume, field="volume"),
        "open_interest": optional_finite_float(
            payload.open_interest, field="open_interest"
        ),
        "source": payload.source.strip() or "api",
        "is_main": payload.is_main,
    }


def _validated_manual_metric(payload: ManualMetricInput) -> dict:
    return {
        "trade_date": validate_trade_date(payload.trade_date),
        "symbol": normalize_symbol(payload.symbol),
        "metric": validate_metric_name(payload.metric),
        "value": finite_float(payload.value, field="value"),
        "unit": payload.unit.strip(),
        "source": payload.source.strip() or "manual",
        "confirmed": payload.confirmed,
    }


def _validated_research_note(payload: ResearchNoteInput) -> dict:
    return {
        "id": payload.id.strip(),
        "title": payload.title.strip(),
        "content": payload.content.strip(),
        "source": payload.source.strip() or "manual",
        "published_at": validate_trade_date(payload.published_at),
        "symbols": list(
            dict.fromkeys(normalize_symbol(item) for item in payload.symbols)
        ),
    }
