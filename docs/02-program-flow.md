# 第一版程序流程

## 1. 启动

`futures-kb-api` 读取 `FUTURES_KB_DB`，默认使用 `data/futures_kb.sqlite3`，初始化数据库后启动 FastAPI。

## 2. 数据写入

### 爬虫

1. `market_run_crawler` 校验品种和交易日期。
2. 从 `config/crawlers.local.json` 读取白名单命令。
3. 使用 `shell=False` 执行爬虫。
4. 爬虫把标准 JSON 写入 `data/raw/<source>/<trade_date>.json`。
5. 服务读取 JSON，将行情写入 SQLite。
6. OpenClaw 只收到运行状态和导入条数。

### 手工数据

1. 用户通过 HTTP 或 MCP 提交结构化记录。
2. 服务校验日期、品种、指标名和数值。
3. 使用唯一键执行 upsert，重复提交不会产生重复记录。
4. OpenClaw 只收到接收数量和版本信息。

### 资讯

1. 资讯保存到 SQLite。
2. 检索时只返回标题、短摘要、来源和发布时间。
3. 不返回全文。

## 3. 日报数据包

1. 读取指定交易日的主力连续行情。
2. 计算涨跌幅、MA5、MA20、持仓变化、成交量 Z-Score。
3. 读取现货、库存等手工指标并计算基差和变化。
4. 标记异常。
5. 检索最多三条相关资讯。
6. 生成固定字段的数据包。
7. 按字符数估算 token，并记录在 `token_estimate`。

## 4. OpenClaw 报告

1. OpenClaw 定时任务调用 `daily_report_context`。
2. 模型根据数据包生成条件式分析。
3. 模型引用资讯 ID 和数据日期。
4. 如果数据质量异常，报告必须明确标记。
5. 报告生成完成后归档该会话。

## 5. 测试

- 单元测试验证计算、校验和存储。
- API 测试验证 HTTP 请求。
- 爬虫测试使用本地假爬虫，不访问网络。
- 端到端测试验证数据导入到日报数据包完整链路。
- MCP stdio 集成测试会启动真实子进程，验证工具发现和日报数据包调用。
