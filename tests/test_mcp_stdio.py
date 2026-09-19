from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from futures_kb.database import Database
from futures_kb.seed import seed


def test_mcp_stdio_transport_discovers_and_calls_tools(tmp_path: Path) -> None:
    database_path = tmp_path / "stdio.sqlite3"
    database = Database(database_path)
    database.initialize()
    seed(database, end_date="2026-09-19", days=20)

    async def exercise() -> None:
        environment = os.environ.copy()
        environment["FUTURES_KB_DB"] = str(database_path)
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "futures_kb.mcp_server"],
            cwd=Path.cwd(),
            env=environment,
        )
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {tool.name for tool in tools.tools} == {
                    "daily_report_context",
                    "manual_data_submit",
                    "market_run_crawler",
                    "research_search",
                }

                result = await session.call_tool(
                    "daily_report_context",
                    {"trade_date": "2026-09-19", "symbols": ["SH", "V", "JM"]},
                )
                payload = getattr(result, "structured_content", None) or getattr(
                    result, "structuredContent", None
                )
                if not payload:
                    payload = json.loads(result.content[0].text)
                assert payload["data_quality"]["status"] == "complete"
                assert payload["token_estimate"] < 3000

    asyncio.run(exercise())
