# 期货 AI 知识库

第一版目标：把烧碱、PVC、焦煤的行情、手工数据、资讯和报告数据与 OpenClaw 上下文分离。OpenClaw 通过 MCP 只获取一份精简的每日报告数据包，不读取完整爬虫结果和历史数据库。

## 第一版能力

- SQLite 行情、手工指标、资讯和爬虫运行记录。
- 烧碱 `SH`、PVC `V`、焦煤 `JM` 的行情特征计算。
- 每日报告数据包 `daily_report_context`。
- 手工数据提交、资讯检索和受控爬虫运行接口。
- FastAPI 服务与 MCP stdio 服务。
- OpenClaw Skill 和每日自动化接入示例。
- 单元测试和端到端测试。

## 快速开始

```powershell
uv sync --extra dev
uv run pytest
uv run futures-kb-seed
uv run futures-kb-api
```

MCP 服务单独运行：

```powershell
uv run futures-kb-mcp
```

详细说明：

- [架构说明](docs/01-architecture.md)
- [程序流程](docs/02-program-flow.md)
- [存储与特征](docs/03-storage-and-features.md)
- [API 与爬虫](docs/04-api-and-crawler.md)
- [MCP 与 OpenClaw 接入](docs/05-mcp-and-openclaw.md)
- [往期报告存储](docs/06-report-storage.md)
