"""Pydantic request models for the HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MarketBarInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_date: str
    symbol: str
    contract: str = "MAIN"
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    settlement: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    source: str = "api"
    is_main: bool = True


class ManualMetricInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_date: str
    symbol: str
    metric: str
    value: float
    unit: str = ""
    source: str = "manual"
    confirmed: bool = True


class ResearchNoteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    source: str = Field(default="manual", max_length=200)
    published_at: str
    symbols: list[str] = Field(default_factory=list)


class ReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_date: str
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    report_type: str = Field(default="daily", max_length=32)
    symbols: list[str] = Field(default_factory=list)
    summary: str = Field(default="", max_length=1000)
    source: str = Field(default="openclaw", max_length=200)


def market_bar_record(payload: MarketBarInput) -> dict[str, Any]:
    return payload.model_dump()


def manual_metric_record(payload: ManualMetricInput) -> dict[str, Any]:
    return payload.model_dump()


def research_note_record(payload: ResearchNoteInput) -> dict[str, Any]:
    return payload.model_dump()
