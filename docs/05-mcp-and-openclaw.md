# MCP 与 OpenClaw 接入

## 1. 本地启动

先安装依赖并生成演示数据：

```powershell
uv sync --extra dev
uv run futures-kb-seed --date 2026-09-19 --days 60
```

MCP 默认使用 `data/futures_kb.sqlite3`。可以通过 `FUTURES_KB_DB` 修改。

## 2. 注册 stdio MCP

在仓库根目录执行：

```powershell
$repo = (Resolve-Path .).Path
$python = Join-Path $repo ".venv\Scripts\python.exe"

openclaw mcp add futures-kb `
  --command $python `
  --arg '-m' `
  --arg 'futures_kb.mcp_server' `
  --cwd $repo `
  --include 'daily_report_context,manual_data_submit,market_run_crawler,research_search,report_save,report_list,report_read'

openclaw mcp doctor futures-kb --probe
```

stdio 模式由 OpenClaw 启动和停止 MCP 进程，适合第一版本机部署。

## 3. 可选 HTTP 模式

```powershell
uv run futures-kb-mcp --transport streamable-http --host 127.0.0.1 --port 8790
```

端点：

```text
http://127.0.0.1:8790/mcp
```

只有放在可信本机网络时才直接使用 HTTP。如果暴露到其他机器，必须在前面增加认证网关。

## 4. MCP 工具

### daily_report_context

输入：

```json
{
  "trade_date": "2026-09-19",
  "symbols": ["SH", "V", "JM"]
}
```

输出是完整日报所需的最小市场数据包。

### manual_data_submit

输入结构化记录数组。服务只返回接收数量和涉及品种，不回显全部数据。

### market_run_crawler

只允许 `SH`、`V`、`JM`。命令来自 `config/crawlers.local.json`，OpenClaw 不能提交命令行。

### report_save

保存 OpenClaw 已完成的报告。相同日期、类型、标题和来源重复保存时更新原记录，不自动放入任何对话上下文。

### report_list

只返回往期报告目录和短摘要，不返回正文。AI 在需要历史比较时先调用此工具。

### report_read

读取一个选中的 `report_id`。默认最多 2,000 token，正文过长时返回 `truncated` 和 `next_offset`。只有用户明确要求看历史报告或对比时调用。

### research_search

最多返回三条短摘要。完整文章继续保存在 SQLite。

## 5. 安装 Skills

将以下目录复制或链接到 OpenClaw 的 workspace skill 根目录：

```text
skills/futures-intel-source
skills/ai-knowledge-base
skills/futures-daily-report
```

如果使用 FuturesIntelTool 作为数据后端，在启动 MCP 前设置：

```powershell
$env:FUTURES_KB_BACKEND = "futures-intel"
$env:FUTURES_INTEL_ROOT = "$env:LOCALAPPDATA\FuturesIntelTool"
```

OpenClaw 选择 Skill 后，会遵守以下边界：

- 先按 `futures-intel-source` 检查或刷新数据。
- 每次报告只调用一次 `daily_report_context`。
- 不让模型读取原始数据。
- 不自行计算指标。
- 数据缺失时标记报告不完整。
- 仅在需要时检索资讯。

## 6. 每日 Automation

在 OpenClaw 中创建独立任务，使用 `isolated` session。示意命令：

```powershell
openclaw automations create "10 16 * * 1-5" `
  "使用 futures-daily-report Skill，生成今天的烧碱、PVC、焦煤期货日报。先调用 daily_report_context，只使用返回的数据，不需要完整历史行情。最后按 Skill 模板输出，并调用 report_save 保存报告。" `
  --name "期货日报" `
  --tz "Asia/Shanghai" `
  --session isolated `
  --announce
```

`isolated` 每次创建独立会话，避免日报内容跨天累积。实际渠道参数根据 OpenClaw 配置补充。

## 7. Token 边界

进入 OpenClaw 的只有：

```text
daily_report_context 返回的数据包
+ research_search 的少量摘要
+ 用户要求查看历史时，report_list 的目录和 report_read 的选中报告
+ 最终报告
```

不会进入 OpenClaw：

```text
全部历史 K 线
爬虫 HTML/JSON
新闻全文
向量
数据库记录
手工数据的完整表
未被调用的往期报告正文
```
