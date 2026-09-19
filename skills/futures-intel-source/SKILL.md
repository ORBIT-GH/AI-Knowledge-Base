---
name: futures-intel-source
description: Refresh and validate FuturesIntelTool data through the futures-kb MCP server before generating a futures report.
---

# Futures Intel Source

Use this skill when the report depends on fresh FuturesIntelTool data.

## Refresh Rules

1. Check whether the requested trading date already has a successful report.
2. If data is missing or stale, call `market_run_crawler` once for one supported symbol and the target date.
3. Do not call the refresh repeatedly.
4. Accept the result only when `status` is `success` or `partial`.
5. If `status` is `failed`, stop and report the data failure. Do not invent data.

## Output Boundary

- Do not read raw HTML, full SQLite rows, logs, or the complete news corpus.
- The refresh tool returns only status, report directory, exit code, and anomaly count.
- After refresh, call `daily_report_context` to obtain the compact analysis packet.

## Supported Symbols

- `SH`: 烧碱
- `V`: PVC
- `JM`: 焦煤
- `M`: 豆粕，存在 FuturesIntelTool 数据时可使用
