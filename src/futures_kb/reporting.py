"""Deterministic feature calculation and compact daily report packets."""

from __future__ import annotations

import json
import math
import statistics
from datetime import date, datetime, timedelta, timezone
from typing import Any, Sequence

from futures_kb.constants import (
    DEFAULT_SYMBOLS,
    MAX_MANUAL_METRICS,
    MAX_NEWS_EXCERPT_CHARS,
    MAX_NEWS_ITEMS,
    SYMBOL_NAMES,
)
from futures_kb.database import Database


SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")


def build_daily_report_context(
    database: Database,
    trade_date: str,
    *,
    symbols: Sequence[str] | None = None,
    news_limit: int = MAX_NEWS_ITEMS,
) -> dict[str, Any]:
    """Build the only market payload that should enter OpenClaw context."""

    selected_symbols = _normalize_symbols(symbols)
    parsed_date = date.fromisoformat(trade_date)

    market: dict[str, Any] = {}
    for symbol in selected_symbols:
        market[symbol] = _build_symbol_context(database, symbol, parsed_date.isoformat())

    research = database.get_recent_research(
        selected_symbols,
        parsed_date.isoformat(),
        days=7,
        limit=max(1, min(news_limit, MAX_NEWS_ITEMS)),
    )
    news = [_compact_news_item(item) for item in research]

    data_quality = _build_data_quality(database, selected_symbols, parsed_date.isoformat(), market)
    cross_market = _build_cross_market(market)

    packet: dict[str, Any] = {
        "trade_date": parsed_date.isoformat(),
        "generated_at": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
        "symbols": market,
        "cross_market": cross_market,
        "news": news,
        "data_quality": data_quality,
    }
    packet["token_estimate"] = estimate_tokens(packet)
    return packet


def estimate_tokens(value: Any) -> int:
    """Estimate mixed Chinese/English JSON tokens without loading a tokenizer."""

    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return max(1, math.ceil(len(text.encode("utf-8")) / 3.5))


def _build_symbol_context(
    database: Database, symbol: str, trade_date: str
) -> dict[str, Any]:
    history = database.get_market_history(symbol, trade_date, limit=20)
    if not history:
        return {
            "name": SYMBOL_NAMES.get(symbol, symbol),
            "status": "missing_market_data",
            "metrics": {},
            "anomalies": ["未找到行情数据"],
        }

    latest = history[0]
    previous = history[1] if len(history) > 1 else None
    close = float(latest["close"])
    closes = [float(item["close"]) for item in history]
    volumes = [float(item["volume"]) for item in history if item.get("volume") is not None]

    metrics: dict[str, Any] = {
        "contract": latest["contract"],
        "close": _round(close),
        "change_1d_pct": _pct_change(close, previous["close"] if previous else None),
        "change_5d_pct": _pct_change(close, history[4]["close"] if len(history) >= 5 else None),
        "ma5": _round(statistics.fmean(closes[:5])) if len(closes) >= 5 else None,
        "ma20": _round(statistics.fmean(closes[:20])) if len(closes) >= 20 else None,
        "volume": _round(latest.get("volume")),
        "volume_z20": _zscore(latest.get("volume"), volumes),
        "open_interest": _round(latest.get("open_interest")),
        "open_interest_change_1d": _delta(
            latest.get("open_interest"), previous.get("open_interest") if previous else None
        ),
        "open_interest_change_1d_pct": _pct_change(
            latest.get("open_interest"), previous.get("open_interest") if previous else None
        ),
        "source": latest["source"],
        "market_date": latest["trade_date"],
    }

    manual = database.get_manual_metrics(symbol, trade_date, limit=MAX_MANUAL_METRICS)
    compact_manual: dict[str, Any] = {}
    for metric_name, record in sorted(manual.items()):
        compact_manual[metric_name] = {
            "value": _round(record["value"]),
            "unit": record["unit"],
            "date": record["trade_date"],
            "source": record["source"],
        }
        if "inventory" in metric_name:
            previous_metric = database.get_previous_metric(symbol, metric_name, trade_date)
            if previous_metric:
                compact_manual[metric_name]["change"] = _delta(
                    record["value"], previous_metric["value"]
                )
                compact_manual[metric_name]["change_pct"] = _pct_change(
                    record["value"], previous_metric["value"]
                )

    spot = compact_manual.get("spot_price")
    if spot and spot.get("unit") == "":
        metrics["basis"] = _round(close - float(spot["value"]))

    anomalies = _detect_anomalies(metrics, compact_manual)
    return {
        "name": SYMBOL_NAMES.get(symbol, symbol),
        "status": "ok",
        "metrics": metrics,
        "manual_metrics": compact_manual,
        "anomalies": anomalies,
    }


def _detect_anomalies(
    metrics: dict[str, Any], manual_metrics: dict[str, dict[str, Any]]
) -> list[str]:
    anomalies: list[str] = []
    change_1d = metrics.get("change_1d_pct")
    if change_1d is not None and abs(float(change_1d)) >= 2:
        anomalies.append("单日涨跌幅达到或超过2%")

    volume_z = metrics.get("volume_z20")
    if volume_z is not None and abs(float(volume_z)) >= 1.5:
        anomalies.append("成交量偏离20日均值")

    oi_change = metrics.get("open_interest_change_1d_pct")
    if oi_change is not None and abs(float(oi_change)) >= 5:
        anomalies.append("持仓量变化达到或超过5%")

    for metric_name, values in manual_metrics.items():
        if "inventory" not in metric_name:
            continue
        inventory_change = values.get("change_pct")
        if inventory_change is not None and abs(float(inventory_change)) >= 5:
            anomalies.append(f"{metric_name}变化达到或超过5%")
    return anomalies


def _build_data_quality(
    database: Database,
    symbols: Sequence[str],
    trade_date: str,
    market: dict[str, Any],
) -> dict[str, Any]:
    missing_market = [
        symbol for symbol, values in market.items() if values.get("status") != "ok"
    ]
    crawler_runs = database.get_latest_crawler_runs(symbols, trade_date)
    return {
        "status": "complete" if not missing_market else "partial",
        "missing_market_data": missing_market,
        "crawler_runs": crawler_runs,
        "note": "只包含生成报告所需字段；原始数据保留在外部数据库中。",
    }


def _build_cross_market(market: dict[str, Any]) -> dict[str, Any]:
    changes = {
        symbol: values.get("metrics", {}).get("change_1d_pct")
        for symbol, values in market.items()
    }
    sh_change = changes.get("SH")
    v_change = changes.get("V")
    caustic_spread = (
        _round(float(sh_change) - float(v_change))
        if sh_change is not None and v_change is not None
        else None
    )
    return {
        "daily_change_pct": changes,
        "chlor_alkali_relative_change_spread": caustic_spread,
        "relationship_notes": [
            "烧碱与PVC同属氯碱产业链，需结合液氯、开工率和库存共同观察。",
            "焦煤处于黑色产业链上游，应与焦炭、钢材利润和铁水产量联动观察。",
        ],
    }


def _compact_news_item(item: dict[str, Any]) -> dict[str, Any]:
    content = str(item.get("content") or "").strip().replace("\n", " ")
    excerpt = content[:MAX_NEWS_EXCERPT_CHARS]
    if len(content) > MAX_NEWS_EXCERPT_CHARS:
        excerpt += "…"
    return {
        "id": item["id"],
        "title": item["title"],
        "excerpt": excerpt,
        "source": item["source"],
        "published_at": item["published_at"],
        "symbols": item.get("symbols", []),
    }


def _normalize_symbols(symbols: Sequence[str] | None) -> tuple[str, ...]:
    if not symbols:
        return DEFAULT_SYMBOLS
    normalized = tuple(dict.fromkeys(item.strip().upper() for item in symbols if item.strip()))
    unknown = [item for item in normalized if item not in SYMBOL_NAMES]
    if unknown:
        raise ValueError(f"unsupported symbols: {', '.join(unknown)}")
    return normalized


def _pct_change(current: Any, previous: Any) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return _round((float(current) / float(previous) - 1) * 100)


def _delta(current: Any, previous: Any) -> float | None:
    if current is None or previous is None:
        return None
    return _round(float(current) - float(previous))


def _zscore(current: Any, history: Sequence[float]) -> float | None:
    if current is None or len(history) < 5:
        return None
    mean = statistics.fmean(history)
    stdev = statistics.pstdev(history)
    if stdev == 0:
        return 0.0
    return _round((float(current) - mean) / stdev)


def _round(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)
