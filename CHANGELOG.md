# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/) 的基本结构。

## [0.2.0] - 2026-09-19

### Added

- FuturesIntelTool SQLite and report-directory compatibility adapter.
- Read-only mapping for contract_master, futures_daily, positions, basis_history, spot_prices, coal_prices, news_items, and report_runs.
- `futures-intel-source` skill for controlled refreshes and freshness checks.
- `ai-knowledge-base` skill for compact context and on-demand report retrieval.
- Merged report listing for FuturesIntelTool source reports and final OpenClaw reports.
- FuturesIntelTool refresh invocation through the existing `market_run_crawler` MCP tool.
- Compatibility documentation and synthetic integration tests.

### Changed

- `daily_report_context`, `research_search`, `report_list`, and `report_read` now route to FuturesIntelTool when `FUTURES_KB_BACKEND=futures-intel`.
- Expanded supported symbols to include `M` for FuturesIntelTool compatibility.
- MCP version now follows the package version.

## [0.1.0] - 2026-09-19

### Added

- SQLite 行情、手工指标、资讯、爬虫运行和往期报告存储。
- 烧碱、PVC、焦煤日报特征计算。
- FastAPI 数据导入与查询接口。
- MCP stdio 和 Streamable HTTP 服务。
- OpenClaw `futures-daily-report` Skill。
- 受控爬虫白名单适配器。
- 往期报告按需读取工具：`report_save`、`report_list`、`report_read`。
- token 预算和报告分页读取。
- API、MCP 和真实 stdio 集成测试。
- 架构、流程、API、OpenClaw 和报告存储文档。
