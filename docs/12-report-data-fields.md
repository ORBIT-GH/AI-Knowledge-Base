# 日报数据字段

`daily_report_context` 现在为每个品种返回三类新增字段。

## 1. 当日快照

```json
{
  "daily_snapshot": {
    "trade_date": "2026-09-18",
    "contract": "SH2701",
    "open": 1940,
    "high": 1975,
    "low": 1928,
    "close": 1966,
    "settlement": 1963,
    "previous_settlement": 1948,
    "amplitude_pct": 2.41,
    "volume": 500000,
    "open_interest": 120000,
    "source": "sina"
  }
}
```

振幅计算：

```text
(high - low) / previous_settlement × 100
```

如果昨结缺失，则回退使用昨收。

## 2. 近 20 日 K 线

```json
{
  "daily_bars_20d": [
    {
      "d": "2026-08-24",
      "o": 1900,
      "h": 1920,
      "l": 1890,
      "c": 1910,
      "s": 1908,
      "ps": 1890,
      "v": 350000,
      "oi": 110000
    }
  ]
}
```

字段：

- `d`：交易日
- `o`：开盘
- `h`：最高
- `l`：最低
- `c`：收盘
- `s`：结算
- `ps`：昨结
- `v`：成交量
- `oi`：持仓量

最多返回 20 个完整交易日。

## 3. 5 分钟量能

```json
{
  "intraday_volume_5m": {
    "available": true,
    "contract": "SH2701",
    "trade_date": "2026-09-21",
    "as_of_time": "11:25",
    "bar_count": 48,
    "total_volume": 125000,
    "average_volume_per_bar": 2604,
    "latest_bar_volume": 4200,
    "latest_volume_ratio": 1.61,
    "intraday_volume_ratio": 1.32,
    "per_bar_volume_ratio": 1.14,
    "volume_band": "正常",
    "latest_volume_band": "放量",
    "price_volume_pair": "放量上涨（多头主动，涨势可信）",
    "day_change_pct": 0.82,
    "notable_bars": [],
    "bars_5m_recent": [],
    "source": "sina:getFewMinLine:5"
  }
}
```

量能档位：

```text
< 0.7       缩量
0.7 - 1.5   正常
1.5 - 2.5   放量
> 2.5       爆量
```

数据源与原有 `fetch_minute_stats.mjs` 一致，但由 AI-KB 在后台获取并转成结构化字段。

## 开关

```text
FUTURES_KB_FETCH_5M=1
FUTURES_KB_5M_TIMEOUT_SECONDS=10
```

如果关闭，字段仍存在，但会返回：

```json
{
  "available": false,
  "reason": "5-minute fetch is disabled"
}
```

接口失败时不会让整个日报失败，而是明确标记不可用。
