# FuturesIntelTool 兼容说明

## 目标

AI-Knowledge-Base 不重复实现爬虫，而是兼容 `ORBIT-GH/FuturesIntelTool` 的 SQLite 数据库和报告目录。

数据流：

```text
FuturesIntelTool
  -> market.sqlite
  -> reports/<date>/daily-brief.md
  -> reports/latest.json
  -> AI-Knowledge-Base
  -> OpenClaw
```

## 支持的数据

兼容适配器只读以下 FuturesIntelTool 表：

- `contract_master`
- `futures_daily`
- `positions`
- `basis_history`
- `spot_prices`
- `coal_prices`
- `news_items`
- `report_runs`

不会复制或修改 FuturesIntelTool 数据库。

## 配置

```powershell
$env:FUTURES_KB_BACKEND = "futures-intel"
$env:FUTURES_INTEL_ROOT = "$env:LOCALAPPDATA\FuturesIntelTool"
```

也可以指定配置文件：

```powershell
$env:FUTURES_INTEL_CONFIG = "C:\Users\Administrator\AppData\Local\FuturesIntelTool\config\default.json"
```

如果使用源码目录 `E:\资讯爬虫`，将 `FUTURES_INTEL_ROOT` 指向该目录，并保留 `FUTURES_INTEL_CONFIG` 指向用户数据目录。这样刷新命令可以使用源码，而行情数据库仍从用户目录读取。

```text
<root>\src\futures_intel
```

程序会使用当前 Python 以 `-m futures_intel` 方式运行。

## 读取流程

1. `daily_report_context` 根据交易日期读取主力合约和日 K。
2. 补充基差、持仓、现货、煤价和新闻。
3. 指标由兼容层确定性计算。
4. 返回内容限制在日报所需字段。
5. 原始 SQLite 行、HTML 和完整新闻正文不会进入 OpenClaw。

## 刷新流程

`market_run_crawler` 在兼容模式下会运行：

```text
futures-intel --config <config> run --date <trade_date>
```

只返回：

- `status`
- `trade_date`
- `report_dir`
- `anomaly_count`
- `exit_code`

不会把完整采集日志或报告正文返回给 OpenClaw。

## 往期报告

`report_list` 和 `report_read` 可以按需读取：

- `report_runs` 表中的 FuturesIntelTool 报告。
- AI-Knowledge-Base 自己保存的最终 OpenClaw 报告。

FuturesIntelTool 报告 ID 格式：

```text
fi_daily_YYYY-MM-DD
```

普通日报不会自动读取往期报告。

## 兼容边界

- 只支持 FuturesIntelTool schema version `1` 对应的表结构。
- 数据库结构变化时需要更新适配器。
- FuturesIntelTool 仓库目前没有 License；本项目只通过公开数据和 CLI 接口兼容，没有复制其源码。
- 两个项目应作为独立进程部署，避免将采集器和 MCP 服务耦合在同一个进程中。

## 数据质量缺口

兼容层会显式返回：

- `missing_sections`
- `news_status`
- `analysis_capabilities.intraday_volume_5m`
- `analysis_capabilities.valuation_inputs`

当不同品种的同日现货价完全相同时，会在相关品种的 `anomalies` 中加入跨品种同值告警。

持仓明细按产品的最新持仓日期读取，不强制绑定报告主力合约。如果持仓合约与主力不一致，会保留明细并添加口径告警。

## Windows 计划任务

如果 `FuturesIntelDaily` 仍指向错误的 `E:\咨询爬虫`，使用管理员 PowerShell 执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\fix_futures_intel_task.ps1
```

脚本会把 action 修正为：

```text
E:\资讯爬虫\scripts\run_daily.ps1
```

日报 Automation 已延迟到 18:25，避免和 18:05 的采集任务竞争。

## 手工补充数据

兼容模式会把 AI-Knowledge-Base 本地手工数据合并到日报包：

- `intraday_volume_ratio`、`volume_ratio_5m` 或 `volume_5m_ratio`：补充量能字段。
- SH：`raw_salt_price`、`electricity_price`、`liquid_chlorine_price`。
- V：`calcium_carbide_price`、`ethylene_price`。
- JM：`premium_discount_structure`。
- 本地导入的新闻会合并到 `news`，并保留来源。

有补充值时，对应 `missing_sections` 会移除，`analysis_capabilities` 会标记为可用。
