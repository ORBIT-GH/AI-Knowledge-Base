from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from futures_kb.api import create_app
from futures_kb.config import Settings
from futures_kb.futures_intel import FuturesIntelAdapter
from futures_kb.service import create_service


def build_futures_intel_fixture(root: Path) -> Path:
    config_dir = root / "config"
    data_dir = root / "data"
    reports_dir = root / "reports" / "2026-09-10"
    config_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    reports_dir.mkdir(parents=True)

    database_path = data_dir / "market.sqlite"
    (config_dir / "default.json").write_text(
        json.dumps(
            {
                "database": "data/market.sqlite",
                "reports_dir": "reports",
                "products": [
                    {"code": "SH", "name": "烧碱", "exchange": "CZCE"},
                    {"code": "V", "name": "PVC", "exchange": "DCE"},
                    {"code": "JM", "name": "焦煤", "exchange": "DCE"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    stamp = "2026-09-10T18:05:00+08:00"
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        CREATE TABLE contract_master (
            trading_date TEXT NOT NULL,
            product_code TEXT NOT NULL,
            contract TEXT NOT NULL,
            exchange TEXT NOT NULL DEFAULT '',
            open_interest REAL,
            volume REAL,
            rank INTEGER,
            is_main INTEGER NOT NULL DEFAULT 0,
            rule_version TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            PRIMARY KEY (trading_date, contract)
        );
        CREATE TABLE futures_daily (
            trading_date TEXT NOT NULL,
            product_code TEXT NOT NULL,
            contract TEXT NOT NULL,
            exchange TEXT NOT NULL DEFAULT '',
            period TEXT NOT NULL DEFAULT '1d',
            session TEXT NOT NULL DEFAULT 'full',
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            settlement REAL,
            previous_settlement REAL,
            volume REAL,
            open_interest REAL,
            source TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            PRIMARY KEY (trading_date, contract, period, session)
        );
        CREATE TABLE positions (
            trading_date TEXT NOT NULL,
            product_code TEXT NOT NULL,
            contract TEXT NOT NULL,
            member TEXT NOT NULL,
            side TEXT NOT NULL,
            rank INTEGER,
            position REAL NOT NULL,
            change REAL,
            source TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );
        CREATE TABLE basis_history (
            quote_date TEXT NOT NULL,
            product_code TEXT NOT NULL,
            contract TEXT NOT NULL,
            definition_id TEXT NOT NULL,
            basis_value REAL,
            spot_price REAL,
            futures_price REAL,
            source TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );
        CREATE TABLE spot_prices (
            quote_date TEXT NOT NULL,
            product_code TEXT NOT NULL,
            spec TEXT NOT NULL DEFAULT '',
            region TEXT NOT NULL DEFAULT '',
            quote_type TEXT NOT NULL DEFAULT '',
            price REAL,
            unit TEXT NOT NULL DEFAULT '元/吨',
            source TEXT NOT NULL,
            source_url TEXT NOT NULL DEFAULT '',
            raw_json TEXT NOT NULL DEFAULT '{}',
            fetched_at TEXT NOT NULL
        );
        CREATE TABLE coal_prices (
            quote_date TEXT NOT NULL,
            benchmark TEXT NOT NULL,
            price REAL,
            change_pct REAL,
            unit TEXT NOT NULL DEFAULT '元/吨',
            source TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );
        CREATE TABLE news_items (
            content_hash TEXT PRIMARY KEY,
            published_at TEXT,
            first_seen_at TEXT NOT NULL,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL DEFAULT '',
            products_json TEXT NOT NULL DEFAULT '[]',
            tags_json TEXT NOT NULL DEFAULT '[]',
            raw_path TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE report_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trading_date TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            report_dir TEXT NOT NULL,
            status TEXT NOT NULL,
            manifest_json TEXT NOT NULL
        );
        """
    )
    connection.execute(
        """
        INSERT INTO contract_master VALUES (
            '2026-09-10', 'SH', 'SH2611', 'CZCE', 234242, 467719, 1, 1,
            'v1_oi_then_volume', ?
        )
        """,
        (stamp,),
    )
    connection.executemany(
        """
        INSERT INTO futures_daily VALUES (
            ?, 'SH', 'SH2611', 'CZCE', '1d', 'full', ?, ?, ?, ?, ?, ?, ?, ?, 'sina', ?
        )
        """,
        [
            ("2026-09-09", 1968, 1995, 1952, 1970, 1973, 1948, 561340, 236842, stamp),
            ("2026-09-10", 1969, 2022, 1953, 2001, 2001, 1973, 467719, 234242, stamp),
        ],
    )
    connection.execute(
        """
        INSERT INTO positions VALUES (
            '2026-09-10', 'SH', 'SH2611', '国泰君安', 'long', 1, 1000, 20,
            'jiaoyifamen', ?
        )
        """,
        (stamp,),
    )
    connection.execute(
        """
        INSERT INTO basis_history VALUES (
            '2026-09-10', 'SH', 'SH2611', 'main_basis', -7.5, 1993.5,
            2001, 'jiaoyifamen', ?
        )
        """,
        (stamp,),
    )
    connection.execute(
        """
        INSERT INTO spot_prices VALUES (
            '2026-09-10', 'SH', '32%液碱', '山东', 'spot', 1993.5,
            '元/吨', 'manual', '', '{}', ?
        )
        """,
        (stamp,),
    )
    connection.execute(
        """
        INSERT INTO coal_prices VALUES (
            '2026-09-10', '秦皇岛5500', 680, 0.5, '元/吨', 'CCTD', ?
        )
        """,
        (stamp,),
    )
    connection.execute(
        """
        INSERT INTO news_items VALUES (
            'news-1', '2026-09-10', ?, 'rss', '氯碱装置检修',
            '某氯碱装置计划检修，影响烧碱供应。', 'https://example.invalid/news',
            '["SH","V"]', '[]', ''
        )
        """,
        (stamp,),
    )

    manifest = {
        "schema_version": "1",
        "report_type": "futures-daily-brief",
        "trading_date": "2026-09-10",
        "effective_market_date": "2026-09-10",
        "generated_at": stamp,
        "status": "success",
        "products": [
            {"code": "SH", "name": "烧碱", "contract": "SH2611", "missing": False}
        ],
    }
    (reports_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    (reports_dir / "daily-brief.md").write_text(
        "# 期货资讯日报 2026-09-10\n\n烧碱 SH2611 收盘 2001。\n",
        encoding="utf-8",
    )
    (reports_dir / "anomalies.json").write_text('{"items": []}\n', encoding="utf-8")
    (reports_dir / "success.ok").write_text(stamp + "\n", encoding="utf-8")
    connection.execute(
        """
        INSERT INTO report_runs(
            trading_date, generated_at, report_dir, status, manifest_json
        ) VALUES ('2026-09-10', ?, ?, 'success', ?)
        """,
        (stamp, str(reports_dir), json.dumps(manifest, ensure_ascii=False)),
    )
    connection.commit()
    connection.close()
    return root


def test_adapter_builds_compact_context_from_futures_intel_db(tmp_path: Path) -> None:
    root = build_futures_intel_fixture(tmp_path)
    adapter = FuturesIntelAdapter(root=root)

    packet = adapter.build_daily_report_context("2026-09-10", symbols=["SH"])

    assert packet["source"] == "FuturesIntelTool"
    assert packet["symbols"]["SH"]["status"] == "ok"
    assert packet["symbols"]["SH"]["metrics"]["contract"] == "SH2611"
    assert packet["symbols"]["SH"]["metrics"]["close"] == 2001.0
    assert packet["symbols"]["SH"]["metrics"]["change_1d_pct"] == 1.4192
    assert packet["symbols"]["SH"]["manual_metrics"]["basis"]["basis_value"] == -7.5
    assert packet["news"][0]["id"] == "news-1"
    assert packet["token_estimate"] < 3000
    assert "content" not in json.dumps(packet["symbols"]["SH"])
    assert "intraday_volume_5m" in packet["data_quality"]["missing_sections"]
    assert packet["data_quality"]["analysis_capabilities"]["intraday_volume_5m"][
        "available"
    ] is False


def test_adapter_lists_and_reads_source_report_on_demand(tmp_path: Path) -> None:
    root = build_futures_intel_fixture(tmp_path)
    adapter = FuturesIntelAdapter(root=root)

    listing = adapter.list_reports(date_from="2026-09-10", date_to="2026-09-10")
    assert listing[0]["id"] == "fi_daily_2026-09-10"
    assert "content" not in listing[0]
    assert "期货资讯日报" in listing[0]["summary"]

    report = adapter.read_report("fi_daily_2026-09-10", max_tokens=2000)
    assert report["report_type"] == "futures_intel_daily"
    assert "烧碱 SH2611" in report["content"]


def test_adapter_searches_futures_intel_news(tmp_path: Path) -> None:
    root = build_futures_intel_fixture(tmp_path)
    adapter = FuturesIntelAdapter(root=root)

    results = adapter.search_news("检修", symbols=["SH"], limit=3)
    assert results[0]["id"] == "news-1"
    assert results[0]["symbols"] == ["SH", "V"]


def test_adapter_runs_configured_refresh_command(tmp_path: Path) -> None:
    root = build_futures_intel_fixture(tmp_path)
    fake_cli = tmp_path / "fake_futures_intel.py"
    fake_cli.write_text(
        "import argparse, json\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--config')\n"
        "parser.add_argument('mode')\n"
        "parser.add_argument('--date')\n"
        "args = parser.parse_args()\n"
        "print(json.dumps({'status': 'success', 'report_dir': 'reports/' + args.date, "
        "'anomaly_count': 0}))\n",
        encoding="utf-8",
    )
    adapter = FuturesIntelAdapter(
        root=root,
        command=(sys.executable, str(fake_cli)),
    )

    result = adapter.run_refresh("2026-09-11", mode="run")
    assert result["status"] == "success"
    assert result["source"] == "FuturesIntelTool"
    assert result["anomaly_count"] == 0
    assert result.get("skipped") is not True
    assert "daily-brief" not in json.dumps(result)


def test_adapter_skips_refresh_when_source_report_is_fresh(tmp_path: Path) -> None:
    root = build_futures_intel_fixture(tmp_path)
    adapter = FuturesIntelAdapter(
        root=root,
        command=("this-command-must-not-run",),
    )

    result = adapter.run_refresh("2026-09-10", mode="run")

    assert result["status"] == "success"
    assert result["skipped"] is True
    assert result["reason"] == "source_report_is_fresh"


def test_adapter_keeps_positions_when_contract_differs_and_flags_duplicate_spot(
    tmp_path: Path,
) -> None:
    root = build_futures_intel_fixture(tmp_path)
    database_path = root / "data" / "market.sqlite"
    connection = sqlite3.connect(database_path)
    stamp = "2026-09-10T18:05:00+08:00"
    connection.execute(
        """
        INSERT INTO contract_master VALUES (
            '2026-09-10', 'SH', 'SH2701', 'CZCE', 80000, 50000, 1, 1,
            'override', ?
        )
        """,
        (stamp,),
    )
    connection.execute(
        """
        INSERT INTO futures_daily VALUES (
            '2026-09-10', 'SH', 'SH2701', 'CZCE', '1d', 'full', 1969, 2022,
            1953, 2001, 2001, 1973, 467719, 234242, 'sina', ?
        )
        """,
        (stamp,),
    )
    connection.execute(
        """
        INSERT INTO contract_master VALUES (
            '2026-09-10', 'JM', 'JM2701', 'DCE', 457244, 1112876, 1, 1,
            'v1_oi_then_volume', ?
        )
        """,
        (stamp,),
    )
    connection.execute(
        """
        INSERT INTO futures_daily VALUES (
            '2026-09-10', 'JM', 'JM2701', 'DCE', '1d', 'full', 1580, 1600,
            1560, 1580, 1580, 1616, 1112876, 457244, 'sina', ?
        )
        """,
        (stamp,),
    )
    connection.execute("UPDATE basis_history SET spot_price=1975, basis_value=90 WHERE product_code='SH'")
    connection.execute(
        """
        INSERT INTO basis_history VALUES (
            '2026-09-10', 'JM', 'JM2701', 'main_basis', 395, 1975, 1580,
            'jiaoyifamen', ?
        )
        """,
        (stamp,),
    )
    connection.commit()
    connection.close()

    adapter = FuturesIntelAdapter(root=root)
    packet = adapter.build_daily_report_context(
        "2026-09-10", symbols=["SH", "JM"]
    )

    sh = packet["symbols"]["SH"]
    assert sh["manual_metrics"]["positions_contract"] == ["SH2611"]
    assert sh["manual_metrics"]["positions"]
    assert any("持仓合约与报告主力不一致" in item for item in sh["anomalies"])
    assert any("跨品种现货价同值告警" in item for item in sh["anomalies"])
    assert any("跨品种现货价同值告警" in item for item in packet["symbols"]["JM"]["anomalies"])


def test_service_routes_tools_to_futures_intel_backend(tmp_path: Path) -> None:
    root = build_futures_intel_fixture(tmp_path)
    settings = Settings(
        database_path=tmp_path / "native.sqlite3",
        crawler_config_path=tmp_path / "crawlers.json",
        raw_data_dir=tmp_path / "raw",
        backend="futures-intel",
        futures_intel_root=root,
    )
    service = create_service(settings=settings)

    service.database.upsert_manual_metrics(
        [
            {
                "trade_date": "2026-09-10",
                "symbol": "SH",
                "metric": "raw_salt_price",
                "value": 260,
                "unit": "元/吨",
                "source": "manual",
            },
            {
                "trade_date": "2026-09-10",
                "symbol": "SH",
                "metric": "electricity_price",
                "value": 0.55,
                "unit": "元/度",
                "source": "manual",
            },
            {
                "trade_date": "2026-09-10",
                "symbol": "SH",
                "metric": "liquid_chlorine_price",
                "value": 120,
                "unit": "元/吨",
                "source": "manual",
            },
            {
                "trade_date": "2026-09-10",
                "symbol": "SH",
                "metric": "intraday_volume_ratio",
                "value": 1.8,
                "unit": "x",
                "source": "manual",
            },
        ]
    )
    service.database.upsert_research_notes(
        [
            {
                "id": "native-news-1",
                "title": "人工补充新闻",
                "content": "人工确认的氯碱装置动态。",
                "source": "manual",
                "published_at": "2026-09-10",
                "symbols": ["SH"],
            }
        ]
    )

    packet = service.report_context("2026-09-10", symbols=["SH"])
    assert packet["source"] == "FuturesIntelTool"
    assert packet["symbols"]["SH"]["metrics"]["contract"] == "SH2611"
    assert packet["symbols"]["SH"]["manual_metrics"]["supplemental"][
        "raw_salt_price"
    ]["value"] == 260
    assert packet["data_quality"]["analysis_capabilities"]["intraday_volume_5m"][
        "available"
    ] is True
    assert "SH:raw_salt_price" not in packet["data_quality"]["missing_sections"]
    assert "native-news-1" in {item["id"] for item in packet["news"]}

    listing = service.list_reports(
        date_from="2026-09-10",
        date_to="2026-09-10",
    )
    assert listing["reports"][0]["report_id"] == "fi_daily_2026-09-10"

    report = service.read_report("fi_daily_2026-09-10", max_tokens=2000)
    assert "烧碱 SH2611" in report["content"]

    news = service.search_research("检修", symbols=["SH"], limit=3)
    assert news["results"][0]["id"] == "news-1"


def test_contract_api_and_ui(tmp_path: Path) -> None:
    root = build_futures_intel_fixture(tmp_path)
    settings = Settings(
        database_path=tmp_path / "native.sqlite3",
        crawler_config_path=tmp_path / "crawlers.json",
        raw_data_dir=tmp_path / "raw",
        backend="futures-intel",
        futures_intel_root=root,
    )
    client = TestClient(create_app(settings=settings))

    ui = client.get("/ui")
    assert ui.status_code == 200
    assert "合约管理" in ui.text
    assert "apiKey" in ui.text
    assert "prompt(" not in ui.text

    overview = client.get("/api/v1/contracts")
    assert overview.status_code == 200
    sh = next(item for item in overview.json()["products"] if item["symbol"] == "SH")
    assert sh["main_contract"] == "SH2611"

    updated = client.put("/api/v1/contracts/SH", json={"contract": "SH2701"})
    assert updated.status_code == 200
    assert updated.json()["override_contract"] == "SH2701"
    config = json.loads(
        (root / "config" / "default.json").read_text(encoding="utf-8")
    )
    sh_config = next(item for item in config["products"] if item["code"] == "SH")
    assert sh_config["contract_override"] == "SH2701"

    automatic = client.put("/api/v1/contracts/SH", json={"contract": None})
    assert automatic.status_code == 200
    assert automatic.json()["override_contract"] is None
    config = json.loads(
        (root / "config" / "default.json").read_text(encoding="utf-8")
    )
    sh_config = next(item for item in config["products"] if item["code"] == "SH")
    assert "contract_override" not in sh_config
