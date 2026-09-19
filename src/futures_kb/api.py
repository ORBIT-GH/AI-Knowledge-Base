"""FastAPI application for data ingestion and compact report queries."""

from __future__ import annotations

import secrets
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
)
from futures_kb.service import FuturesDataService, create_service
from futures_kb.validation import validate_trade_date


def create_app(
    *,
    settings: Settings | None = None,
    database: Database | None = None,
    crawler_runner: CrawlerRunner | None = None,
    service: FuturesDataService | None = None,
) -> FastAPI:
    effective_settings = settings or Settings.from_env()
    effective_service = service or create_service(
        settings=effective_settings,
        database=database,
        crawler_runner=crawler_runner,
    )

    app = FastAPI(
        title="Futures AI Knowledge Base",
        version="0.1.0",
        description="External market data service for OpenClaw daily futures reports.",
    )
    app.state.settings = effective_settings
    app.state.database = effective_service.database
    app.state.service = effective_service

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
        return {"upserted": effective_service.upsert_market_bars(payload)}

    @app.post("/api/v1/manual-data", dependencies=[Depends(authorize)])
    def upsert_manual_data(payload: list[ManualMetricInput]) -> dict[str, int]:
        return {"upserted": effective_service.upsert_manual_metrics(payload)}

    @app.post("/api/v1/research", dependencies=[Depends(authorize)])
    def upsert_research(payload: list[ResearchNoteInput]) -> dict[str, int]:
        return {"upserted": effective_service.upsert_research_notes(payload)}

    @app.post("/api/v1/crawlers/{source}/run", dependencies=[Depends(authorize)])
    def run_crawler(source: str, trade_date: str = Query(...)) -> dict:
        try:
            return effective_service.run_crawler(source, trade_date)
        except CrawlerConfigurationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/report-context", dependencies=[Depends(authorize)])
    def report_context(
        trade_date: str = Query(...),
        symbols: str | None = Query(default=None, description="Comma-separated symbols"),
    ) -> dict:
        selected = symbols.split(",") if symbols else None
        return effective_service.report_context(
            validate_trade_date(trade_date),
            symbols=selected,
        )

    return app


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        create_app(settings=settings),
        host=settings.api_host,
        port=settings.api_port,
    )


if __name__ == "__main__":
    main()
