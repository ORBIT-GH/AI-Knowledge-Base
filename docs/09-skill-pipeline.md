# Skill 流程

## 设计目标

三个 Skill 分工，不让任何一个 Skill 直接读取大数据。

```text
FuturesIntelTool
  -> futures-intel-source
  -> AI-Knowledge-Base
  -> ai-knowledge-base
  -> OpenClaw
  -> futures-daily-report
  -> report_save
```

## futures-intel-source

职责：

- 检查数据是否新鲜。
- 通过 `market_run_crawler` 触发 FuturesIntelTool。
- 获取运行状态。
- 数据失败时停止。

不负责：

- 读取完整数据库。
- 读取 HTML 或完整新闻。
- 生成报告。

## ai-knowledge-base

职责：

- 通过 `daily_report_context` 获取精简指标。
- 通过 `research_search` 获取少量新闻摘要。
- 通过 `report_list` 和 `report_read` 按需读取往期报告。
- 通过 `report_save` 保存最终报告。

不负责：

- 判断交易方向。
- 运行爬虫。
- 读取原始数据。

## futures-daily-report

职责：

- 按顺序组合前两个 Skill。
- 规定日报模板。
- 标记数据缺失和口径冲突。
- 生成条件式情景分析。
- 保存最终报告。

## 普通日报上下文

```text
FuturesIntelTool 运行状态
+ daily_report_context 精简数据包
+ 最多三条新闻摘要
+ 最终报告
```

默认不包含：

```text
完整 SQLite
完整新闻正文
HTML
往期报告全文
爬虫日志
```

## 历史对比

只有用户要求历史对比时才执行：

```text
report_list -> 选择 report_id -> report_read
```

默认不会把全部往期报告加载进上下文。
