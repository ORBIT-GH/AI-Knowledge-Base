# API 与爬虫接入说明

## 1. 启动 API

```powershell
Copy-Item config/crawlers.example.json config/crawlers.local.json
uv run futures-kb-api
```

默认数据库：`data/futures_kb.sqlite3`。  
默认监听：`127.0.0.1:8787`。

## 2. 写入行情

```http
POST /api/v1/market/bars
Content-Type: application/json
```

请求体必须是数组，字段包括：

```json
[
  {
    "trade_date": "2026-09-19",
    "symbol": "SH",
    "contract": "MAIN",
    "open": 2440,
    "high": 2470,
    "low": 2428,
    "close": 2455,
    "settlement": 2452,
    "volume": 150000,
    "open_interest": 230000,
    "source": "my-api",
    "is_main": true
  }
]
```

## 3. 写入手工数据

```http
POST /api/v1/manual-data
```

每个指标一条记录：

```json
[
  {
    "trade_date": "2026-09-19",
    "symbol": "SH",
    "metric": "spot_price",
    "value": 2470,
    "unit": "",
    "source": "manual"
  },
  {
    "trade_date": "2026-09-19",
    "symbol": "SH",
    "metric": "inventory",
    "value": 318000,
    "unit": "t",
    "source": "manual"
  }
]
```

相同日期、品种、指标和来源重复提交时会更新，不会生成重复行。

## 4. 写入资讯

```http
POST /api/v1/research
```

接口只保存资讯；日报数据包只返回截断摘要。

## 5. 运行爬虫

```http
POST /api/v1/crawlers/SH/run?trade_date=2026-09-19
```

程序执行顺序：

1. 将品种转换为大写并检查是否在 `SH/V/JM` 白名单。
2. 校验交易日期。
3. 从 `config/crawlers.local.json` 读取该品种的命令数组。
4. 替换 `{source}`、`{trade_date}`、`{output_path}`。
5. 使用 `shell=False` 执行命令。
6. 读取标准 JSON。
7. 将 bars 写入 SQLite。
8. 返回运行 ID、状态和导入数量，不返回 bars 内容。

配置文件是受信任的本地文件。OpenClaw 只能选择白名单品种和日期，不能提交命令行。

## 6. 获取日报数据包

```http
GET /api/v1/report-context?trade_date=2026-09-19&symbols=SH,V,JM
```

这是 OpenClaw 唯一应该读取的市场数据接口。返回内容包含计算后的指标、资讯摘要和数据质量，不包含完整历史行情。
