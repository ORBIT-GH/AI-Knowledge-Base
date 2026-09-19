from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from futures_kb.api import create_app
from futures_kb.config import Settings
from futures_kb.database import Database
from futures_kb.models import ReportInput
from futures_kb.reporting import build_daily_report_context
from futures_kb.service import create_service


class StubCrawler:
    def run(self, source: str, trade_date: str) -> dict:
        return {"source": source, "trade_date": trade_date, "status": "success"}


def build_service(database: Database):
    return create_service(database=database, crawler_runner=StubCrawler())  # type: ignore[arg-type]


def test_report_store_is_idempotent_and_list_hides_content(database: Database) -> None:
    service = build_service(database)
    first = service.save_report(
        ReportInput(
            trade_date="2026-09-18",
            title="2026-09-18 期货日报",
            content="第一天完整报告",
            symbols=["SH", "V", "JM"],
            summary="第一天摘要",
        )
    )
    second = service.save_report(
        ReportInput(
            trade_date="2026-09-18",
            title="2026-09-18 期货日报",
            content="更新后的完整报告",
            symbols=["SH", "V", "JM"],
            summary="更新后的摘要",
        )
    )

    assert second["report_id"] == first["report_id"]
    assert second["updated"] is True
    listing = service.list_reports(date_from="2026-09-18", date_to="2026-09-18")
    assert listing["reports"][0]["summary"] == "更新后的摘要"
    assert all("content" not in item for item in listing["reports"])


def test_report_read_is_budgeted_and_offset_resumes(database: Database) -> None:
    service = build_service(database)
    content = "烧碱库存下降。" * 300
    saved = service.save_report(
        ReportInput(
            trade_date="2026-09-18",
            title="长篇日报",
            content=content,
            symbols=["SH"],
        )
    )

    first = service.read_report(str(saved["report_id"]), max_tokens=200)
    assert first["truncated"] is True
    assert first["content_token_estimate"] <= 200
    assert first["next_offset"] > 0
    assert first["total_token_estimate"] > first["content_token_estimate"]

    second = service.read_report(
        str(saved["report_id"]),
        offset=int(first["next_offset"]),
        max_tokens=4000,
    )
    assert second["content"]
    assert content == first["content"] + second["content"]


def test_daily_report_context_does_not_include_saved_reports(
    seeded_database: Database,
) -> None:
    service = build_service(seeded_database)
    marker = "SHOULD_NOT_APPEAR_IN_DAILY_CONTEXT"
    service.save_report(
        ReportInput(
            trade_date="2026-09-08",
            title="往期日报",
            content=marker,
            symbols=["SH", "V", "JM"],
        )
    )

    packet = build_daily_report_context(seeded_database, "2026-09-08")
    assert marker not in json.dumps(packet, ensure_ascii=False)
    assert "past_reports" not in packet


def test_report_api_save_list_and_read(tmp_path: Path) -> None:
    settings = Settings(
        database_path=tmp_path / "reports.sqlite3",
        crawler_config_path=tmp_path / "crawlers.json",
        raw_data_dir=tmp_path / "raw",
    )
    app = create_app(settings=settings)
    client = TestClient(app)

    save_response = client.post(
        "/api/v1/reports",
        json={
            "trade_date": "2026-09-18",
            "title": "2026-09-18 期货日报",
            "content": "烧碱、PVC、焦煤日报正文。",
            "symbols": ["SH", "V", "JM"],
            "summary": "三品种日报摘要",
        },
    )
    assert save_response.status_code == 200
    report_id = save_response.json()["report_id"]

    list_response = client.get(
        "/api/v1/reports",
        params={"date_from": "2026-09-18", "date_to": "2026-09-18"},
    )
    assert list_response.status_code == 200
    assert list_response.json()["reports"][0]["report_id"] == report_id

    read_response = client.get(
        f"/api/v1/reports/{report_id}",
        params={"max_tokens": 200},
    )
    assert read_response.status_code == 200
    assert read_response.json()["content"] == "烧碱、PVC、焦煤日报正文。"

