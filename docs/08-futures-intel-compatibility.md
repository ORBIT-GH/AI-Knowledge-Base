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
$env:FUTURES_INTEL_CONFIG = "E:\咨询爬虫\config\default.json"
```

如果没有检测到 `futures-intel` 命令，但找到了源码目录：

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
