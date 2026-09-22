# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/) 的基本结构。

## [0.2.9] - 2026-09-22

### Fixed

- Keep valuation parameter gaps in `missing_sections` instead of removing them unconditionally.
- Mark report packets `partial` when operating rate, inventory, warehouse receipts, valuation parameters, or news are unavailable.
- Filter legacy seed news from compatible packets.
- Preserve real RSS news only when it matches SH, V, or JM product keywords.

## [0.2.8] - 2026-09-22

### Added

- Per-symbol `fundamental` object in daily report packets.
- Multi-source spot quotes with date, quote type, unit, contract, and source.
- Explicit operating rate, inventory, and warehouse receipt fields.
- Explicit valuation parameter values for SH, V, and JM.
- Manual metric aliases for operating rate, inventory, and warehouse receipts.
- Real RSS source configuration for Eastmoney, Nasdaq Commodities, and WSJ Markets.
- Source and product filtering for news to prevent unrelated articles entering reports.
- Filtering of legacy seed demo data from production packets.

## [0.2.7] - 2026-09-21

### Added

- Per-symbol `daily_snapshot` with OHLC, settlement, previous settlement, volume, open interest, and amplitude.
- Per-symbol `daily_bars_20d` with the latest 20 daily bars.
- Structured `intraday_volume_5m` provider based on Sina 5-minute futures data.
- Intraday volume ratio, latest-bar ratio, volume band, price-volume pair, notable bars, and recent 12 bars.
- `FUTURES_KB_FETCH_5M` and `FUTURES_KB_5M_TIMEOUT_SECONDS` configuration.
- Fallback behavior that marks 5-minute availability without failing the whole report.

## [0.2.6] - 2026-09-20

### Added

- New AI Knowledge application icon with book, knowledge network, and futures trend elements.
- Multi-size ICO resource for Windows Explorer, taskbar, title bar, and executable.
- Reproducible Pillow-based icon generation script.
- PyInstaller and GitHub Release workflows now embed the icon.

## [0.2.5] - 2026-09-20

### Added

- Native Tkinter desktop window for Windows.
- Contract management tab with fixed-contract and automatic-main actions.
- Daily context viewer tab.
- On-demand past report browser tab.
- `futures-kb-desktop` console entry point.
- PyInstaller build script producing `AIKnowledgeBase.exe`.
- Automatic FuturesIntelTool backend detection for the desktop executable.

## [0.2.4] - 2026-09-20

### Fixed

- Replace browser `prompt()` authentication with an inline API Key input compatible with the Codex in-app browser.
- Persist the API Key only in browser session storage.
- Add a UI regression test ensuring `prompt()` is not used.

## [0.2.3] - 2026-09-20

### Added

- Dependency-free web control panel at `/ui`.
- Contract overview with actual main contract and configured override.
- Contract selection from FuturesIntelTool's latest `contract_master` records.
- Contract override save and automatic-main-contract reset.
- Contract management API endpoints.
- Web UI refresh button for triggering FuturesIntelTool collection.

## [0.2.2] - 2026-09-20

### Added

- Merge AI-KB native manual metrics into FuturesIntelTool-compatible daily packets.
- Support supplemental `intraday_volume_ratio` as the source for the 5-minute volume section.
- Support supplemental SH valuation fields: raw salt, electricity, and liquid chlorine prices.
- Support supplemental PVC valuation fields: calcium carbide and ethylene prices.
- Support supplemental JM premium/discount structure inputs.
- Merge locally imported news from AI-KB into the compatible daily packet.
- Mark missing report sections as complete when corresponding supplemental data is supplied.

## [0.2.1] - 2026-09-20

### Fixed

- Read FuturesIntelTool positions by product and latest position date instead of filtering only by the report main contract.
- Preserve position details when the exchange top-20 contract differs from the report main contract and add a clear anomaly.
- Detect identical spot prices across different products and block silent basis reuse.
- Add basis percentile calculation for compatible products.
- Declare missing report capabilities explicitly, including 5-minute volume, valuation inputs, news, basis, and positions.
- Skip FuturesIntelTool refresh when a successful or partial source report for the same trading date already exists.
- Add `tzdata` as a runtime dependency so FuturesIntelTool can execute inside the AI-KB environment on Windows.
- Add an administrator script to repair the Windows scheduled task path from `E:\咨询爬虫` to `E:\资讯爬虫`.
- Move the Xiaomaomao daily report automation from 18:05 to 18:25 to avoid racing the collector.

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
