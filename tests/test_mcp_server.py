from __future__ import annotations

import asyncio
import json
from pathlib import Path

from futures_kb.database import Database
from futures_kb.mcp_server import create_mcp_server
from futures_kb.service import create_service


class StubCrawler:
    def run(self, source: str, trade_date: str) -> dict:
        return {
            "source": source.upper(),
            "trade_date": trade_date,
            "status": "success",
            "imported_bars": 1,
        }


def build_server(tmp_path: Path):
    database = Database(tmp_path / "mcp.sqlite3")
    database.initialize()
    service = create_service(
        database=database,
        crawler_runner=StubCrawler(),  # type: ignore[arg-type]
    )
    return create_mcp_server(service=service), database


def tool_payload(result) -> dict:
    if getattr(result, "structuredContent", None):
        return result.structuredContent
    text = result.content[0].text
    return json.loads(text)


def test_mcp_exposes_only_the_first_version_tools(tmp_path: Path) -> None:
    server, _ = build_server(tmp_path)
    tools = asyncio.run(server.list_tools())
    assert {tool.name for tool in tools} == {
        "daily_report_context",
        "manual_data_submit",
        "market_run_crawler",
        "research_search",
        "report_save",
        "report_list",
        "report_read",
    }


def test_mcp_manual_submit_and_report_context(tmp_path: Path) -> None:
    server, database = build_server(tmp_path)
    records = [
        {
            "trade_date": "2026-09-19",
            "symbol": "SH",
            "metric": "spot_price",
            "value": 2450,
            "unit": "",
            "source": "manual",
        }
    ]
    submit_result = asyncio.run(
        server.call_tool("manual_data_submit", {"records": records})
    )
    submitted = tool_payload(submit_result)
    assert submitted["accepted"] == 1
    assert "value" not in json.dumps(submitted)

    bars = []
    for index in range(20):
        bars.append(
            {
                "trade_date": f"2026-08-{index + 1:02d}",
                "symbol": "SH",
                "contract": "MAIN",
                "close": 2400 + index * 5,
                "volume": 100000 + index * 1000,
                "open_interest": 200000 + index * 500,
                "source": "mcp-test",
            }
        )
    database.upsert_market_bars(bars)

    report_result = asyncio.run(
        server.call_tool(
            "daily_report_context",
            {"trade_date": "2026-08-20", "symbols": ["SH"]},
        )
    )
    packet = tool_payload(report_result)
    assert packet["trade_date"] == "2026-08-20"
    assert packet["symbols"]["SH"]["status"] == "ok"
    assert packet["token_estimate"] < 3000
    assert "content" not in json.dumps(packet, ensure_ascii=False)


def test_mcp_research_results_do_not_include_full_article(tmp_path: Path) -> None:
    server, database = build_server(tmp_path)
    database.upsert_research_notes(
        [
            {
                "id": "note-1",
                "title": "焦煤供应观察",
                "content": "全文内容" * 200,
                "source": "test",
                "published_at": "2026-09-19",
                "symbols": ["JM"],
            }
        ]
    )

    result = asyncio.run(
        server.call_tool(
            "research_search",
            {"query": "焦煤", "symbols": ["JM"], "limit": 3},
        )
    )
    payload = tool_payload(result)
    assert payload["results"][0]["id"] == "note-1"
    assert len(payload["results"][0]["excerpt"]) <= 181
    assert "全文内容全文内容" * 100 not in json.dumps(payload, ensure_ascii=False)

def test_mcp_report_tools_keep_content_out_of_list(tmp_path: Path) -> None:
    server, _ = build_server(tmp_path)
    save_result = asyncio.run(
        server.call_tool(
            "report_save",
            {
                "payload": {
                    "trade_date": "2026-09-19",
                    "title": "2026-09-19 期货日报",
                    "content": "SHOULD_ONLY_BE_READ_ON_DEMAND",
                    "symbols": ["SH", "V", "JM"],
                    "summary": "三品种日报摘要",
                }
            },
        )
    )
    saved = tool_payload(save_result)
    assert saved["saved"] is True

    list_result = asyncio.run(
        server.call_tool(
            "report_list",
            {"date_from": "2026-09-19", "date_to": "2026-09-19"},
        )
    )
    listing = tool_payload(list_result)
    assert listing["reports"][0]["report_id"] == saved["report_id"]
    assert "SHOULD_ONLY_BE_READ_ON_DEMAND" not in json.dumps(listing)

    read_result = asyncio.run(
        server.call_tool(
            "report_read",
            {"report_id": saved["report_id"], "max_tokens": 2000},
        )
    )
    report = tool_payload(read_result)
    assert report["content"] == "SHOULD_ONLY_BE_READ_ON_DEMAND"
