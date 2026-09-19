from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from futures_kb.api import create_app
from futures_kb.config import Settings
from futures_kb.crawler import CrawlerConfigurationError, CrawlerRunner
from futures_kb.database import Database


def build_settings(tmp_path: Path, *, api_key: str | None = None) -> Settings:
    return Settings(
        database_path=tmp_path / "api.sqlite3",
        crawler_config_path=tmp_path / "crawlers.json",
        raw_data_dir=tmp_path / "raw",
        api_key=api_key,
    )


def test_api_ingests_and_returns_compact_report(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings=settings)
    client = TestClient(app)

    bars = []
    for index in range(20):
        trade_date = f"2026-09-{index + 1:02d}"
        for symbol, base in (("SH", 2400), ("V", 5100), ("JM", 1250)):
            bars.append(
                {
                    "trade_date": trade_date,
                    "symbol": symbol,
                    "contract": "MAIN",
                    "close": base + index * 5,
                    "volume": 100000 + index * 1000,
                    "open_interest": 200000 + index * 500,
                    "source": "api-test",
                }
            )

    response = client.post("/api/v1/market/bars", json=bars)
    assert response.status_code == 200
    assert response.json() == {"upserted": 60}

    manual_response = client.post(
        "/api/v1/manual-data",
        json=[
            {
                "trade_date": "2026-09-20",
                "symbol": "SH",
                "metric": "spot_price",
                "value": 2520,
                "unit": "",
            }
        ],
    )
    assert manual_response.status_code == 200

    report = client.get(
        "/api/v1/report-context",
        params={"trade_date": "2026-09-20", "symbols": "SH,V,JM"},
    )
    assert report.status_code == 200
    packet = report.json()
    assert packet["data_quality"]["status"] == "complete"
    assert packet["symbols"]["SH"]["metrics"]["basis"] == -25.0
    assert packet["token_estimate"] < 3000
    assert "content" not in json.dumps(packet, ensure_ascii=False)


def test_api_requires_configured_key(tmp_path: Path) -> None:
    settings = build_settings(tmp_path, api_key="secret")
    client = TestClient(create_app(settings=settings))

    assert client.get("/health").status_code == 200
    assert client.post("/api/v1/manual-data", json=[]).status_code == 401
    response = client.post(
        "/api/v1/manual-data",
        json=[],
        headers={"X-API-Key": "secret"},
    )
    assert response.status_code == 200


def test_crawler_runner_imports_allowlisted_output(tmp_path: Path) -> None:
    database = Database(tmp_path / "crawler.sqlite3")
    database.initialize()
    config_path = tmp_path / "crawlers.json"
    config_path.write_text(
        json.dumps(
            {
                "SH": {
                    "command": [
                        sys.executable,
                        str(Path("examples/fake_crawler.py").resolve()),
                        "--source",
                        "{source}",
                        "--trade-date",
                        "{trade_date}",
                        "--output",
                        "{output_path}",
                    ],
                    "cwd": str(Path.cwd()),
                }
            }
        ),
        encoding="utf-8",
    )
    runner = CrawlerRunner(
        database,
        config_path=config_path,
        raw_data_dir=tmp_path / "raw",
    )

    result = runner.run("SH", "2026-09-19")
    assert result["status"] == "success"
    assert result["imported_bars"] == 1
    assert "bars" not in result
    assert database.get_market_history("SH", "2026-09-19")[0]["close"] == 2450.0


def test_crawler_rejects_unconfigured_source(tmp_path: Path) -> None:
    database = Database(tmp_path / "crawler.sqlite3")
    database.initialize()
    config_path = tmp_path / "crawlers.json"
    config_path.write_text("{}", encoding="utf-8")
    runner = CrawlerRunner(
        database,
        config_path=config_path,
        raw_data_dir=tmp_path / "raw",
    )

    try:
        runner.run("SH", "2026-09-19")
    except CrawlerConfigurationError:
        pass
    else:
        raise AssertionError("expected CrawlerConfigurationError")

