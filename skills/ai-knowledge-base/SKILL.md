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

## Supplemental Daily Data

Use `manual_data_submit` for data that FuturesIntelTool does not collect.

- For 5-minute volume, submit `intraday_volume_ratio`, `volume_ratio_5m`, or `volume_5m_ratio`.
- For SH valuation, submit `raw_salt_price`, `electricity_price`, and `liquid_chlorine_price`.
- For V valuation, submit `calcium_carbide_price` and `ethylene_price`.
- For JM structure, submit `premium_discount_structure`.
- Import manually verified news through the local AI-KB research endpoint or database.

The compatible daily packet merges these values and removes the corresponding missing-section flags.

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
