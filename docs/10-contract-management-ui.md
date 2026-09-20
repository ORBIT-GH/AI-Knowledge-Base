# 合约管理与可视化控制台

## 启动

```powershell
uv run futures-kb-api
```

浏览器打开：

```text
http://127.0.0.1:8787/ui
```

## 页面功能

- 显示每个品种的实际主力合约。
- 显示主力日期、持仓量和成交量。
- 显示当前 `contract_override`。
- 从 FuturesIntelTool 可用合约中选择固定合约。
- 保存覆盖后写入 FuturesIntelTool 的 `config/default.json`。
- 点击“恢复自动主力”会删除 `contract_override`。
- 页面可手动刷新 FuturesIntelTool 数据。

## 合约口径

实际主力来自 FuturesIntelTool `contract_master.is_main=1`。

固定合约来自配置：

```json
{
  "code": "SH",
  "name": "烧碱",
  "exchange": "CZCE",
  "contract_override": "SH2701"
}
```

保存覆盖后，下一次 FuturesIntelTool 采集会使用该合约。当前看板会同时显示：

- `main_contract`：数据库中的实际主力。
- `override_contract`：用户设置的固定合约。

两者不同是允许的，不会静默合并。

## API

```http
GET /api/v1/contracts
PUT /api/v1/contracts/{symbol}
```

保存固定合约：

```json
{
  "contract": "SH2701"
}
```

恢复自动主力：

```json
{
  "contract": null
}
```

## 权限

如果设置了：

```text
FUTURES_KB_API_KEY
```

页面会提示输入 API Key，请求会带：

```text
X-API-Key
```

默认只监听 `127.0.0.1`，不要在没有认证的情况下暴露到公网。
