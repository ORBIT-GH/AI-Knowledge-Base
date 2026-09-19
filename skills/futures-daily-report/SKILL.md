---
name: futures-daily-report
description: Generate a Chinese daily futures report from FuturesIntelTool data through AI-Knowledge-Base and persist the final report.
---

# Futures Daily Report

This skill orchestrates the pipeline:

```text
FuturesIntelTool -> AI-Knowledge-Base -> OpenClaw -> final report
```

## Execution Order

1. Follow `futures-intel-source` when freshness needs to be checked or refreshed.
2. Follow `ai-knowledge-base` to call `daily_report_context`.
3. Use only returned computed fields and bounded news excerpts.
4. Mark `partial` or `failed` source status clearly.
5. Generate the final Chinese report with conditional scenarios.
6. Call `report_save` with `report_type="openclaw_daily"`.

## Report Rules

- Write in Chinese.
- Cite source report or news IDs when used.
- Never invent prices, inventory, basis, policy, or source links.
- Do not state certainty about direction.
- Define trigger and invalidation conditions.
- Keep the final report under 2,000 Chinese characters unless the user asks for detail.
- Do not repeat the entire input packet.

## Required Sections

1. Data quality, source, and as-of time.
2. SH, V, and JM snapshot.
3. Cross-market and industrial-chain observations.
4. News and policy items actually present in the packet.
5. Conditional scenarios, validation signals, and invalidation conditions.
