# 基本面数据字段

`daily_report_context.symbols.<code>.fundamental` 现在提供统一的基本面入口。

## 现货价

```json
{
  "spot_quotes": [
    {
      "date": "2026-09-17",
      "price": 1975,
      "unit": "元/吨",
      "spec": "",
      "region": "",
      "quote_type": "basis_implied_spot",
      "contract": "SH2611",
      "definition_id": "jiaoyifamen_main_basis_v1",
      "futures_price": 1885,
      "basis_value": 90,
      "source": "jiaoyifamen"
    }
  ]
}
```

来源包括：

- FuturesIntelTool `spot_prices`
- FuturesIntelTool `basis_history` 中的现货价
- AI-KB `manual_data_submit` 中名称包含 `spot` 的手工数据

每条现货价都保留日期、口径、单位和来源。

## 开工率

```json
{
  "operating_rate": {
    "value": 82.5,
    "unit": "%",
    "date": "2026-09-22",
    "source": "manual"
  }
}
```

支持的 metric：

```text
operating_rate
utilization_rate
开工率
```

## 库存

```json
{
  "inventory": {
    "value": 300000,
    "unit": "t",
    "date": "2026-09-22",
    "source": "manual"
  }
}
```

支持的 metric：

```text
inventory
total_inventory
social_inventory
库存
```

## 仓单

```json
{
  "warehouse_receipts": {
    "value": 12000,
    "unit": "t",
    "date": "2026-09-22",
    "source": "manual"
  }
}
```

支持的 metric：

```text
warehouse_receipts
warehouse_receipt
仓单
```

## 估值参数

烧碱：

```text
raw_salt_price
electricity_price
liquid_chlorine_price
```

PVC：

```text
calcium_carbide_price
ethylene_price
```

焦煤：

```text
premium_discount_structure
```

输出：

```json
{
  "valuation_parameters": {
    "raw_salt_price": {
      "value": 260,
      "unit": "元/吨",
      "date": "2026-09-22",
      "source": "manual"
    }
  }
}
```

## 资讯源

当前配置：

- 东方财富合作资讯
- Nasdaq Commodities
- WSJ Markets

资讯只保留命中 SH/V/JM 关键词的记录，不再把无关通用新闻混入日报。
