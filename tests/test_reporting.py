from futures_kb.reporting import build_daily_report_context, estimate_tokens


def test_report_context_contains_compact_computed_metrics(seeded_database) -> None:
    packet = build_daily_report_context(seeded_database, "2026-09-08")

    assert packet["data_quality"]["status"] == "complete"
    assert packet["symbols"]["SH"]["metrics"]["change_1d_pct"] == 0.4032
    assert packet["symbols"]["SH"]["metrics"]["basis"] == -30.0
    assert packet["symbols"]["SH"]["manual_metrics"]["inventory"]["change_pct"] == -6.25
    assert "inventory变化达到或超过5%" in packet["symbols"]["SH"]["anomalies"]
    assert packet["news"][0]["id"] == "news-1"
    assert len(packet["news"][0]["excerpt"]) <= 181
    assert "content" not in packet["news"][0]
    assert packet["token_estimate"] < 3000
    assert packet["token_estimate"] == estimate_tokens(
        {key: value for key, value in packet.items() if key != "token_estimate"}
    )


def test_market_upsert_is_idempotent(database) -> None:
    record = {
        "trade_date": "2026-09-08",
        "symbol": "SH",
        "contract": "MAIN",
        "close": 2500,
        "source": "fixture",
    }
    database.upsert_market_bars([record, {**record, "close": 2510}])

    history = database.get_market_history("SH", "2026-09-08")
    assert len(history) == 1
    assert history[0]["close"] == 2510


def test_missing_market_data_is_reported(database) -> None:
    packet = build_daily_report_context(database, "2026-09-08")

    assert packet["data_quality"]["status"] == "partial"
    assert packet["data_quality"]["missing_market_data"] == ["SH", "V", "JM"]
    assert packet["symbols"]["SH"]["status"] == "missing_market_data"

