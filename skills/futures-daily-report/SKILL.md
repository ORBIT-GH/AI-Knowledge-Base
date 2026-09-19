---
name: futures-daily-report
description: Generate a Chinese daily futures report for SH, V, and JM using the futures-kb MCP tools while keeping raw data outside context.
---

# Futures Daily Report

Use the `futures-kb` MCP server as the external data boundary.

## Required data flow

1. Call `daily_report_context` once with the target `trade_date`.
2. Do not request raw K-lines, crawler JSON, full articles, or historical exports.
3. Do not calculate indicators yourself; use the returned computed fields.
4. If `data_quality.status` is `partial`, clearly mark missing data before analysis.
5. Use `research_search` only when the packet's news excerpts are insufficient.
6. Use `manual_data_submit` only when the user explicitly provides structured daily data.
7. Use `market_run_crawler` only when the user explicitly asks to refresh data.

## Past report retrieval

- After the final report is complete, call `report_save`.
- Do not automatically call `report_read` for a normal daily report.
- If the user asks for historical comparison, call `report_list` first.
- Read only the selected `report_id` with `report_read`.
- If `report_read` returns `truncated: true`, continue with `next_offset` only when needed.
- Never load all past reports into context.

## Report rules

- Write in Chinese.
- Separate facts, observations, and conditional scenarios.
- Cite news IDs when using a news item.
- Never invent prices, inventory, basis, policy, or source links.
- Do not state certainty about direction; define trigger and invalidation conditions.
- Keep the final report under 2,000 Chinese characters unless the user asks for detail.
- Do not repeat the entire input packet.

## Required sections

1. Data quality and as-of time.
2. SH, V, and JM snapshot with the most important changes.
3. Cross-market and industrial-chain observations.
4. News and policy items actually present in the packet.
5. Conditional scenarios, validation signals, and invalidation conditions.
