"""FastAPI application for data ingestion and compact report queries."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from futures_kb.config import Settings
from futures_kb.crawler import CrawlerConfigurationError, CrawlerRunner
from futures_kb.database import Database
from futures_kb.models import (
    ManualMetricInput,
    MarketBarInput,
    ResearchNoteInput,
    manual_metric_record,
    market_bar_record,
    research_note_record,
)
from futures_kb.reporting import build_daily_report_context
from futures_kb.validation import (
    finite_float,
    normalize_symbol,
    normalize_symbols,
    optional_finite_float,
    validate_metric_name,
    validate_trade_date,
)


def create_app(
    *,
    settings: Settings | None = None,
    database: Database | None = None,
    crawler_runner: CrawlerRunner | None = None,
) -> FastAPI:
    effective_settings = settings or Settings.from_env()
    effective_database = database or Database(effective_settings.database_path)
    effective_database.initialize()
    effective_crawler = crawler_runner or CrawlerRunner(
        effective_database,
        config_path=effective_settings.crawler_config_path,
        raw_data_dir=effective_settings.raw_data_dir,
    )

    app = FastAPI(
        title="Futures AI Knowledge Base",
        version="0.1.0",
        description="External market data service for OpenClaw daily futures reports.",
    )
    app.state.settings = effective_settings
    app.state.database = effective_database
    app.state.crawler_runner = effective_crawler

    def authorize(
        x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    ) -> None:
        expected = effective_settings.api_key
        if expected and not secrets.compare_digest(x_api_key or "", expected):
            raise HTTPException(status_code=401, detail="invalid API key")

    @app.exception_handler(ValueError)
    async def value_error_handler(_, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": "0.1.0"}

    @app.post("/api/v1/market/bars", dependencies=[Depends(authorize)])
    def upsert_market_bars(payload: list[MarketBarInput]) -> dict[str, int]:
        records = [_validated_market_bar(item) for item in payload]
        return {"upserted": effective_database.upsert_market_bars(records)}

    @app.post("/api/v1/manual-data", dependencies=[Depends(authorize)])
    def upsert_manual_data(payload: list[ManualMetricInput]) -> dict[str, int]:
        records = [_validated_manual_metric(item) for item in payload]
        return {"upserted": effective_database.upsert_manual_metrics(records)}

    @app.post("/api/v1/research", dependencies=[Depends(authorize)])
    def upsert_research(payload: list[ResearchNoteInput]) -> dict[str, int]:
        records = [_validated_research_note(item) for item in payload]
        return {"upserted": effective_database.upsert_research_notes(records)}

    @app.post("/api/v1/crawlers/{source}/run", dependencies=[Depends(authorize)])
    def run_crawler(source: str, trade_date: str = Query(...)) -> dict:
        try:
            return effective_crawler.run(source, trade_date)
        except CrawlerConfigurationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/report-context", dependencies=[Depends(authorize)])
    def report_context(
        trade_date: str = Query(...),
        symbols: str | None = Query(default=None, description="Comma-separated symbols"),
    ) -> dict:
        selected = symbols.split(",") if symbols else None
        return build_daily_report_context(
            effective_database,
            validate_trade_date(trade_date),
            symbols=selected,
        )

    return app


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
        "symbols": list(dict.fromkeys(normalize_symbol(item) for item in payload.symbols)),
    }


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        create_app(settings=settings),
        host=settings.api_host,
        port=settings.api_port,
    )


app = create_app()


if __name__ == "__main__":
    main()

