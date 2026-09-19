---
name: ai-knowledge-base
description: Read compact market context and on-demand reports from AI-Knowledge-Base while keeping raw data outside model context.
---

# AI Knowledge Base

Use the `futures-kb` MCP server as the only market-data boundary.

## Data Reading

- Call `daily_report_context` once for the target trading date.
- Use returned computed metrics instead of recalculating indicators.
- Use `research_search` only when the compact news excerpts are insufficient.
- Never request full database tables, raw crawler output, or complete articles.

## Report Storage

- After the final report is complete, call `report_save`.
- Normal daily reports must not call `report_read`.
- If the user asks for historical comparison, call `report_list` first.
- Read only the selected `report_id` with `report_read`.
- Continue with `next_offset` only when the report is truncated.

## Sources

- `futures_intel_daily` is a source report from FuturesIntelTool.
- `openclaw_daily` is the final AI-generated report.
- Do not overwrite or silently merge the two report types.
