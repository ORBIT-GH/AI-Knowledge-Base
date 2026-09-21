from __future__ import annotations

import json

from futures_kb.intraday import fetch_intraday_volume_5m


def test_fetch_intraday_volume_summarizes_5m_bars() -> None:
    bars = []
    for day in ("2026-09-09", "2026-09-10"):
        volumes = (50, 50, 100) if day == "2026-09-09" else (100, 100, 200)
        for minute, volume in zip(("09:00", "09:05", "09:10"), volumes, strict=True):
            bars.append(
                {
                    "d": f"{day} {minute}:00",
                    "o": 100,
                    "h": 102,
                    "l": 99,
                    "c": 101,
                    "v": volume,
                }
            )
    payload = "var _ = (" + json.dumps(bars) + ");"

    result = fetch_intraday_volume_5m(
        "SH2701",
        "2026-09-10",
        http_text=lambda _url, _timeout: payload,
    )

    assert result["available"] is True
    assert result["trade_date"] == "2026-09-10"
    assert result["total_volume"] == 400.0
    assert result["intraday_volume_ratio"] == 2.0
    assert result["bars_5m_recent"][-1]["volume"] == 200.0
    assert result["source"] == "sina:getFewMinLine:5"


def test_fetch_intraday_volume_reports_unavailable_for_other_date() -> None:
    bars = [
        {
            "d": "2026-09-10 09:00:00",
            "o": 100,
            "h": 102,
            "l": 99,
            "c": 101,
            "v": 100,
        }
    ]
    payload = "var _ = (" + json.dumps(bars) + ");"

    result = fetch_intraday_volume_5m(
        "SH2701",
        "2026-09-11",
        http_text=lambda _url, _timeout: payload,
    )

    assert result["available"] is False
    assert result["latest_available_date"] == "2026-09-10"
