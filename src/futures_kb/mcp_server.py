"""MCP stdio and Streamable HTTP server for OpenClaw."""

from __future__ import annotations

import argparse
from typing import Any

from mcp.server.mcpserver import MCPServer

from futures_kb.config import Settings
from futures_kb.crawler import CrawlerConfigurationError
from futures_kb.models import ManualMetricInput, ReportInput
from futures_kb.service import FuturesDataService, create_service


def create_mcp_server(
    *,
    settings: Settings | None = None,
    service: FuturesDataService | None = None,
) -> MCPServer:
    effective_service = service or create_service(settings=settings)
    server = MCPServer(
        name="futures-kb",
        title="Futures AI Knowledge Base",
        version="0.1.0",
        instructions=(
            "External data boundary for OpenClaw. Use daily_report_context as the "
            "only market data source for the daily report. Do not request raw bars, "
            "crawler payloads, full news articles, or historical exports. Use "
            "manual_data_submit for user-provided daily metrics, market_run_crawler "
            "only for allowlisted crawler execution, and research_search only when "
            "a focused news or policy lookup is needed. The service can use its native "
            "database or FuturesIntelTool while keeping the same tool contract. Past reports "
            "are never auto-loaded; call report_list first and report_read only for a "
            "selected report."
        ),
    )

    @server.tool(
        name="daily_report_context",
        title="Daily report context",
        description=(
            "Return one compact computed packet for SH, V, and JM. This is the only "
            "market payload that should enter the report context."
        ),
    )
    def daily_report_context(
        trade_date: str, symbols: list[str] | None = None
    ) -> dict[str, Any]:
        return effective_service.report_context(trade_date, symbols=symbols)

    @server.tool(
        name="manual_data_submit",
        title="Submit manual daily data",
        description=(
            "Validate and upsert structured spot, inventory, operating-rate, or other "
            "daily metrics. The tool returns counts only, not the submitted dataset."
        ),
    )
    def manual_data_submit(records: list[ManualMetricInput]) -> dict[str, object]:
        return effective_service.submit_manual_metrics(records)

    @server.tool(
        name="market_run_crawler",
        title="Run allowlisted market crawler",
        description=(
            "Run the configured native crawler or FuturesIntelTool refresh for one "
            "supported symbol and date. Only run status is returned."
        ),
    )
    def market_run_crawler(source: str, trade_date: str) -> dict[str, Any]:
        try:
            return effective_service.run_crawler(source, trade_date)
        except CrawlerConfigurationError as exc:
            return {
                "source": source.upper(),
                "trade_date": trade_date,
                "status": "failed",
                "imported_bars": 0,
                "error": str(exc),
            }

    @server.tool(
        name="report_save",
        title="Save generated report",
        description=(
            "Persist a completed report outside model context. Re-saving the same "
            "date, type, title, and source updates the existing report."
        ),
    )
    def report_save(payload: ReportInput) -> dict[str, object]:
        return effective_service.save_report(payload)

    @server.tool(
        name="report_list",
        title="List past reports",
        description=(
            "Return compact report metadata and short summaries only. Use this "
            "before reading any past report; full report content is never returned."
        ),
    )
    def report_list(
        query: str | None = None,
        symbols: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 5,
    ) -> dict[str, object]:
        return effective_service.list_reports(
            query=query,
            symbols=symbols,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

    @server.tool(
        name="report_read",
        title="Read selected past report",
        description=(
            "Read one selected report with a token budget. Use next_offset to "
            "continue only when necessary."
        ),
    )
    def report_read(
        report_id: str,
        offset: int = 0,
        max_tokens: int = 2000,
    ) -> dict[str, object]:
        return effective_service.read_report(
            report_id,
            offset=offset,
            max_tokens=max_tokens,
        )

    @server.tool(
        name="research_search",
        title="Search research notes",
        description=(
            "Search FuturesIntelTool or native news, announcements, and research notes. "
            "Returns at most three short excerpts with citations."
        ),
    )
    def research_search(
        query: str,
        symbols: list[str] | None = None,
        limit: int = 3,
    ) -> dict[str, Any]:
        return effective_service.search_research(
            query,
            symbols=symbols,
            limit=limit,
        )

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Futures KB MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()

    server = create_mcp_server()
    if args.transport == "stdio":
        server.run("stdio")
    else:
        server.run(
            "streamable-http",
            host=args.host,
            port=args.port,
            streamable_http_path="/mcp",
        )


if __name__ == "__main__":
    main()
