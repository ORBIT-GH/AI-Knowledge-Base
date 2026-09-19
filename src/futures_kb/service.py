"""Application service shared by the HTTP API and MCP server."""

from __future__ import annotations

import hashlib
from typing import Iterable

from futures_kb.config import Settings
from futures_kb.crawler import CrawlerRunner
from futures_kb.database import Database
from futures_kb.models import (
    ManualMetricInput,
    MarketBarInput,
    ReportInput,
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

    def save_report(self, payload: ReportInput) -> dict[str, object]:
        trade_date = validate_trade_date(payload.trade_date)
        title = payload.title.strip()
        content = payload.content.strip()
        report_type = payload.report_type.strip().lower() or "daily"
        source = payload.source.strip() or "openclaw"
        symbols = list(
            dict.fromkeys(normalize_symbol(item) for item in payload.symbols)
        )
        summary = payload.summary.strip()
        if not summary:
            summary = content[:180].replace("\n", " ")
            if len(content) > 180:
                summary += "…"

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        identity = f"{trade_date}|{report_type}|{title}|{source}"
        report_id = "rep_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        existing = self.database.get_report(report_id)
        self.database.upsert_report(
            {
                "id": report_id,
                "trade_date": trade_date,
                "title": title,
                "report_type": report_type,
                "symbols": symbols,
                "summary": summary,
                "content": content,
                "source": source,
                "content_hash": content_hash,
            }
        )
        return {
            "report_id": report_id,
            "saved": True,
            "updated": existing is not None,
            "trade_date": trade_date,
            "token_estimate": estimate_tokens(content),
        }

    def list_reports(
        self,
        *,
        query: str | None = None,
        symbols: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 5,
    ) -> dict[str, object]:
        normalized_symbols = list(normalize_symbols(symbols)) if symbols else None
        reports = self.database.list_reports(
            query=query,
            symbols=normalized_symbols,
            date_from=validate_trade_date(date_from) if date_from else None,
            date_to=validate_trade_date(date_to) if date_to else None,
            limit=max(1, min(limit, 10)),
        )
        items = [
            {
                "report_id": item["id"],
                "trade_date": item["trade_date"],
                "title": item["title"],
                "report_type": item["report_type"],
                "symbols": item["symbols"],
                "summary": item["summary"][:240],
                "source": item["source"],
                "updated_at": item["updated_at"],
                "content_chars": item["content_chars"],
            }
            for item in reports
        ]
        result: dict[str, object] = {"reports": items}
        result["token_estimate"] = estimate_tokens(result)
        return result

    def read_report(
        self,
        report_id: str,
        *,
        offset: int = 0,
        max_tokens: int = 2000,
    ) -> dict[str, object]:
        report = self.database.get_report(report_id)
        if report is None:
            raise ValueError(f"report not found: {report_id}")
        safe_max_tokens = max(200, min(max_tokens, 4000))
        content, next_offset, truncated = _slice_text_by_token_budget(
            str(report["content"]),
            offset=max(0, offset),
            max_tokens=safe_max_tokens,
        )
        return {
            "report_id": report["id"],
            "trade_date": report["trade_date"],
            "title": report["title"],
            "report_type": report["report_type"],
            "symbols": report["symbols"],
            "content": content,
            "offset": max(0, offset),
            "next_offset": next_offset,
            "truncated": truncated,
            "content_token_estimate": estimate_tokens(content),
            "total_token_estimate": estimate_tokens(report["content"]),
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


def _slice_text_by_token_budget(
    text: str, *, offset: int, max_tokens: int
) -> tuple[str, int, bool]:
    safe_offset = max(0, min(offset, len(text)))
    remaining = text[safe_offset:]
    if estimate_tokens(remaining) <= max_tokens:
        return remaining, len(text), False

    low = 0
    high = len(remaining)
    while low < high:
        middle = (low + high + 1) // 2
        if estimate_tokens(remaining[:middle]) <= max_tokens:
            low = middle
        else:
            high = middle - 1
    clipped = remaining[:low]
    return clipped, safe_offset + low, True


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
