"""Sina 5-minute volume provider for daily report packets."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence
from urllib.request import Request, urlopen


URL_TEMPLATE = (
    "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/"
    "var%20_=/InnerFuturesNewService.getFewMinLine?symbol={contract}&type=5"
)


@dataclass
class IntradayResult:
    available: bool
    contract: str
    trade_date: str
    payload: dict[str, Any]


def fetch_intraday_volume_5m(
    contract: str,
    expected_date: str,
    *,
    timeout_seconds: int = 10,
    http_text: Callable[[str, int], str] | None = None,
) -> dict[str, Any]:
    """Fetch and summarize the latest 5-minute bars for one contract."""

    getter = http_text or _http_text
    try:
        text = getter(URL_TEMPLATE.format(contract=contract), timeout_seconds)
        raw_bars = _parse_jsonp(text)
        bars = [_normalize_bar(item) for item in raw_bars]
        return _summarize(contract, expected_date, bars)
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "contract": contract,
            "trade_date": expected_date,
            "reason": str(exc),
        }


def _summarize(
    contract: str,
    expected_date: str,
    bars: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not bars:
        raise ValueError("empty 5-minute response")

    days = sorted({str(item["datetime"])[:10] for item in bars})
    if expected_date not in days:
        latest_date = days[-1] if days else None
        return {
            "available": False,
            "contract": contract,
            "trade_date": expected_date,
            "latest_available_date": latest_date,
            "reason": "requested trading date is not present in 5-minute data",
        }

    day_bars = [dict(item) for item in bars if str(item["datetime"]).startswith(expected_date)]
    if not day_bars:
        raise ValueError("no bars for requested trading date")

    volumes = [float(item["v"]) for item in day_bars]
    total_volume = sum(volumes)
    average_volume = total_volume / len(volumes)
    last = day_bars[-1]
    latest_ratio = float(last["v"]) / average_volume if average_volume else None

    previous_days = [day for day in days if day < expected_date][-5:]
    cutoff_time = str(last["datetime"])[11:16]
    previous_cumulative: list[float] = []
    previous_per_bar: list[float] = []
    for day in previous_days:
        day_data = [
            dict(item)
            for item in bars
            if str(item["datetime"]).startswith(day)
            and str(item["datetime"])[11:16] <= cutoff_time
        ]
        if not day_data:
            continue
        cumulative = sum(float(item["v"]) for item in day_data)
        previous_cumulative.append(cumulative)
        previous_per_bar.append(cumulative / len(day_data))

    previous_cumulative_average = (
        sum(previous_cumulative) / len(previous_cumulative)
        if previous_cumulative
        else None
    )
    previous_bar_average = (
        sum(previous_per_bar) / len(previous_per_bar)
        if previous_per_bar
        else None
    )
    day_ratio = (
        total_volume / previous_cumulative_average
        if previous_cumulative_average not in (None, 0)
        else None
    )
    per_bar_ratio = (
        average_volume / previous_bar_average
        if previous_bar_average not in (None, 0)
        else None
    )

    open_price = float(day_bars[0]["o"])
    last_price = float(last["c"])
    day_change_pct = (
        (last_price / open_price - 1) * 100 if open_price not in (None, 0) else None
    )
    notable = [
        _compact_bar(item, average_volume)
        for item in day_bars
        if average_volume and float(item["v"]) / average_volume >= 1.5
    ]
    recent = [_compact_bar(item, average_volume) for item in day_bars[-12:]]
    return {
        "available": True,
        "contract": contract,
        "trade_date": expected_date,
        "as_of_time": str(last["datetime"])[11:16],
        "bar_count": len(day_bars),
        "total_volume": round(total_volume, 2),
        "average_volume_per_bar": round(average_volume, 2),
        "latest_bar_volume": round(float(last["v"]), 2),
        "latest_volume_ratio": _round(latest_ratio),
        "intraday_volume_ratio": _round(day_ratio),
        "per_bar_volume_ratio": _round(per_bar_ratio),
        "volume_band": _band(day_ratio or per_bar_ratio or 0),
        "latest_volume_band": _band(latest_ratio or 0),
        "price_volume_pair": _price_volume_pair(day_change_pct, latest_ratio),
        "day_change_pct": _round(day_change_pct),
        "high": _round(max(float(item["h"]) for item in day_bars)),
        "low": _round(min(float(item["l"]) for item in day_bars)),
        "notable_bars": notable,
        "bars_5m_recent": recent,
        "source": "sina:getFewMinLine:5",
    }


def _compact_bar(item: Mapping[str, Any], average_volume: float) -> dict[str, Any]:
    ratio = float(item["v"]) / average_volume if average_volume else None
    return {
        "time": str(item["datetime"])[11:16],
        "open": _round(item["o"]),
        "high": _round(item["h"]),
        "low": _round(item["l"]),
        "close": _round(item["c"]),
        "volume": _round(item["v"]),
        "ratio": _round(ratio),
        "band": _band(ratio or 0),
    }


def _normalize_bar(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "datetime": str(item["d"]),
        "o": float(item["o"]),
        "h": float(item["h"]),
        "l": float(item["l"]),
        "c": float(item["c"]),
        "v": float(item["v"]),
    }


def _parse_jsonp(text: str) -> list[dict[str, Any]]:
    start = text.find("(")
    end = text.rfind(")")
    if start < 0 or end <= start:
        raise ValueError("invalid JSONP response")
    payload = json.loads(text[start + 1 : end])
    if not isinstance(payload, list):
        raise ValueError("5-minute response is not a list")
    return payload


def _http_text(url: str, timeout_seconds: int) -> str:
    request = Request(
        url,
        headers={
            "Referer": "https://finance.sina.com.cn/",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8", errors="replace")


def _band(ratio: float) -> str:
    if ratio < 0.7:
        return "缩量"
    if ratio <= 1.5:
        return "正常"
    if ratio <= 2.5:
        return "放量"
    return "爆量"


def _price_volume_pair(change_pct: float | None, ratio: float | None) -> str:
    if change_pct is None or ratio is None:
        return "量能判读不足"
    up = change_pct > 0
    if ratio >= 1.5:
        return "放量上涨（多头主动，涨势可信）" if up else "放量下跌（空头主动，跌势可信）"
    if ratio < 0.7:
        return "缩量上涨（无量反弹/滞涨，易回落）" if up else "缩量下跌（无量阴跌，易反抽）"
    return "常量上涨（跟随为主）" if up else "常量下跌（跟随为主）"


def _round(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return round(number, 4)
