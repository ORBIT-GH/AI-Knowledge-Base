"""Read-only compatibility adapter for ORBIT-GH/FuturesIntelTool.

This module interoperates with FuturesIntelTool's published SQLite schema and
report-file contract. It does not copy or vendor that project's source code.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from futures_kb.constants import (
    DEFAULT_SYMBOLS,
    MAX_NEWS_EXCERPT_CHARS,
    MAX_NEWS_ITEMS,
    SYMBOL_NAMES,
)
from futures_kb.intraday import fetch_intraday_volume_5m
from futures_kb.reporting import estimate_tokens
from futures_kb.validation import normalize_symbol, normalize_symbols, validate_trade_date


SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")
SUPPORTED_REFRESH_MODES = {"collect", "report", "run", "scheduled-run"}
CONTRACT_PATTERN = re.compile(r"^[A-Z]{1,3}\d{3,4}$")


class FuturesIntelError(RuntimeError):
    """Raised when FuturesIntelTool data cannot be resolved or queried."""


@dataclass
class FuturesIntelAdapter:
    """Expose FuturesIntelTool data through the AI-KB service contract."""

    root: Path | None = None
    config_path: Path | None = None
    command: tuple[str, ...] | None = None
    timeout_seconds: int = 300
    fetch_5m: bool = False
    intraday_timeout_seconds: int = 10
    _intraday_cache: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        detected_root = self._detect_root()
        self.root = detected_root
        resolved_config = self._detect_config()
        self.config_path = resolved_config
        config = self._read_config(resolved_config)
        self.config = config
        base = resolved_config.parent.parent if resolved_config else detected_root

        database_value = config.get("database", "data/market.sqlite")
        reports_value = config.get("reports_dir", "reports")
        self.database_path = _resolve_under(base, database_value)
        self.reports_dir = _resolve_under(base, reports_value)
        self.source_dir = detected_root / "src" if (detected_root / "src" / "futures_intel").exists() else None

    @property
    def available(self) -> bool:
        return self.database_path.exists()

    def build_daily_report_context(
        self,
        trade_date: str,
        *,
        symbols: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        normalized_date = validate_trade_date(trade_date)
        selected = (
            tuple(normalize_symbols(symbols))
            if symbols
            else tuple(DEFAULT_SYMBOLS)
        )
        market: dict[str, Any] = {}
        for symbol in selected:
            market[symbol] = self._product_context(symbol, normalized_date)

        news = self._recent_news(selected, normalized_date, limit=MAX_NEWS_ITEMS)
        _apply_cross_product_warnings(market)
        packet: dict[str, Any] = {
            "trade_date": normalized_date,
            "generated_at": datetime.now(SHANGHAI).isoformat(timespec="seconds"),
            "source": "FuturesIntelTool",
            "symbols": market,
            "cross_market": _cross_market(market),
            "news": news,
            "data_quality": self._data_quality(
                selected,
                normalized_date,
                market,
                news,
            ),
        }
        packet["token_estimate"] = estimate_tokens(packet)
        return packet

    def list_reports(
        self,
        *,
        query: str | None = None,
        symbols: Sequence[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        requested = {item.upper() for item in symbols or []}
        normalized_query = (query or "").strip().lower()
        results: list[dict[str, Any]] = []
        for record in self._report_records():
            trade_date = str(record["trade_date"])
            if date_from and trade_date < date_from:
                continue
            if date_to and trade_date > date_to:
                continue
            report_symbols = sorted(record.get("symbols", []))
            if requested and not requested.intersection(report_symbols):
                continue
            summary = record.get("summary", "")
            searchable = f"{record.get('title', '')}\n{summary}\n{record.get('manifest_text', '')}".lower()
            if normalized_query and normalized_query not in searchable:
                continue
            results.append(
                {
                    "id": record["id"],
                    "trade_date": trade_date,
                    "title": record["title"],
                    "report_type": "futures_intel_daily",
                    "symbols": report_symbols,
                    "summary": summary,
                    "source": "FuturesIntelTool",
                    "updated_at": record["updated_at"],
                    "content_chars": record["content_chars"],
                }
            )
            if len(results) >= limit:
                break
        return results

    def read_report(
        self,
        report_id: str,
        *,
        offset: int = 0,
        max_tokens: int = 2000,
    ) -> dict[str, Any]:
        record = next(
            (item for item in self._report_records() if item["id"] == report_id),
            None,
        )
        if record is None:
            raise FuturesIntelError(f"FuturesIntelTool report not found: {report_id}")

        brief_path = Path(record["report_dir"]) / "daily-brief.md"
        if not brief_path.exists():
            raise FuturesIntelError(f"daily-brief.md not found: {brief_path}")
        content = brief_path.read_text(encoding="utf-8")
        safe_offset = max(0, offset)
        safe_max_tokens = max(200, min(max_tokens, 4000))
        clipped, next_offset, truncated = _slice_text_by_token_budget(
            content,
            offset=safe_offset,
            max_tokens=safe_max_tokens,
        )
        return {
            "report_id": report_id,
            "trade_date": record["trade_date"],
            "title": record["title"],
            "report_type": "futures_intel_daily",
            "symbols": record.get("symbols", []),
            "content": clipped,
            "offset": safe_offset,
            "next_offset": next_offset,
            "truncated": truncated,
            "content_token_estimate": estimate_tokens(clipped),
            "total_token_estimate": estimate_tokens(content),
        }

    def search_news(
        self,
        query: str,
        *,
        symbols: Sequence[str] | None = None,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        selected = {item.upper() for item in symbols or []}
        clauses = ["1=1"]
        parameters: list[Any] = []
        if query.strip():
            pattern = f"%{query.strip()}%"
            clauses.append("(title LIKE ? OR summary LIKE ?)")
            parameters.extend([pattern, pattern])
        parameters.append(max(limit * 8, limit))
        rows = self._query(
            f"""
            SELECT content_hash, published_at, first_seen_at, source, title,
                   summary, url, products_json
            FROM news_items
            WHERE {' AND '.join(clauses)}
            ORDER BY COALESCE(published_at, first_seen_at) DESC
            LIMIT ?
            """,
            parameters,
        )
        results: list[dict[str, Any]] = []
        for row in rows:
            item_symbols = set(_json_list(row["products_json"]))
            if selected and not selected.intersection(item_symbols):
                continue
            results.append(_compact_news(dict(row), item_symbols))
            if len(results) >= limit:
                break
        return results

    def contract_overview(self) -> dict[str, Any]:
        config = self._read_config(self.config_path)
        products = config.get("products") or [
            {"code": symbol, "name": SYMBOL_NAMES.get(symbol, symbol)}
            for symbol in DEFAULT_SYMBOLS
        ]
        items: list[dict[str, Any]] = []
        for product in products:
            if not isinstance(product, Mapping):
                continue
            symbol = str(product.get("code") or "").upper()
            if not symbol:
                continue
            main = self._query(
                """
                SELECT trading_date, contract, exchange, open_interest, volume
                FROM contract_master
                WHERE product_code=? AND is_main=1
                ORDER BY trading_date DESC LIMIT 1
                """,
                (symbol,),
            )
            available = self._available_contracts(symbol)
            items.append(
                {
                    "symbol": symbol,
                    "name": str(product.get("name") or SYMBOL_NAMES.get(symbol, symbol)),
                    "exchange": str(product.get("exchange") or ""),
                    "override_contract": product.get("contract_override") or None,
                    "main_contract": main[0]["contract"] if main else None,
                    "main_contract_date": main[0]["trading_date"] if main else None,
                    "available_contracts": available,
                }
            )
        return {
            "source": "FuturesIntelTool",
            "config_path": str(self.config_path) if self.config_path else None,
            "products": items,
        }

    def set_contract_override(
        self,
        symbol: str,
        contract: str | None,
    ) -> dict[str, Any]:
        normalized_symbol = normalize_symbol(symbol)
        if not self.config_path or not self.config_path.exists():
            raise FuturesIntelError("FuturesIntelTool config not found")
        normalized_contract = (contract or "").strip().upper()
        if normalized_contract in {"", "AUTO", "AUTOMATIC"}:
            normalized_contract = None
        if normalized_contract and not CONTRACT_PATTERN.fullmatch(normalized_contract):
            raise FuturesIntelError(f"invalid contract code: {contract}")

        config = self._read_config(self.config_path)
        products = config.get("products")
        if not isinstance(products, list):
            raise FuturesIntelError("FuturesIntelTool config products must be a list")
        target = next(
            (
                product
                for product in products
                if isinstance(product, dict)
                and str(product.get("code") or "").upper() == normalized_symbol
            ),
            None,
        )
        if target is None:
            raise FuturesIntelError(f"product not found in config: {normalized_symbol}")
        if normalized_contract:
            target["contract_override"] = normalized_contract
        else:
            target.pop("contract_override", None)

        temp_path = self.config_path.with_suffix(self.config_path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temp_path, self.config_path)
        self.config = config
        overview = self.contract_overview()
        product = next(
            item for item in overview["products"] if item["symbol"] == normalized_symbol
        )
        return {
            "updated": True,
            "symbol": normalized_symbol,
            "override_contract": normalized_contract,
            "product": product,
        }

    def _available_contracts(self, symbol: str) -> list[dict[str, Any]]:
        rows = self._query(
            """
            SELECT contract, exchange, open_interest, volume, is_main
            FROM contract_master
            WHERE product_code=?
              AND trading_date=(SELECT MAX(trading_date) FROM contract_master WHERE product_code=?)
            ORDER BY is_main DESC, open_interest DESC, contract
            LIMIT 30
            """,
            (symbol, symbol),
        )
        return [
            {
                "contract": row["contract"],
                "exchange": row["exchange"],
                "open_interest": row["open_interest"],
                "volume": row["volume"],
                "is_main": bool(row["is_main"]),
            }
            for row in rows
        ]

    def run_refresh(
        self,
        trade_date: str,
        *,
        mode: str = "run",
    ) -> dict[str, Any]:
        normalized_date = validate_trade_date(trade_date)
        if mode not in SUPPORTED_REFRESH_MODES:
            raise FuturesIntelError(f"unsupported FuturesIntelTool mode: {mode}")

        latest = self._latest_report_record()
        if (
            latest
            and str(latest.get("trade_date")) == normalized_date
            and str(latest.get("status") or "").lower() in {"success", "partial"}
        ):
            return {
                "source": "FuturesIntelTool",
                "trade_date": normalized_date,
                "mode": mode,
                "status": "success",
                "skipped": True,
                "reason": "source_report_is_fresh",
                "report_dir": latest.get("report_dir"),
                "anomaly_count": _report_anomaly_count(latest),
            }

        base_command, environment = self._refresh_command()
        command = [
            *base_command,
            "--config",
            str(self.config_path),
            mode,
            "--date",
            normalized_date,
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
                check=False,
                env=environment,
                cwd=self.root,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "source": "FuturesIntelTool",
                "trade_date": normalized_date,
                "mode": mode,
                "status": "failed",
                "error": str(exc),
            }

        parsed = _last_json_value(completed.stdout)
        result: dict[str, Any] = {
            "source": "FuturesIntelTool",
            "trade_date": normalized_date,
            "mode": mode,
            "status": "success" if completed.returncode == 0 else "failed",
            "exit_code": completed.returncode,
        }
        if isinstance(parsed, dict):
            for key in ("status", "report_dir", "anomaly_count", "message"):
                if key in parsed:
                    result[key] = parsed[key]
            if completed.returncode != 0:
                result["status"] = "failed"
        elif completed.returncode != 0:
            result["error"] = (completed.stderr or completed.stdout or "command failed")[-2000:]
        return result

    def _product_context(self, symbol: str, trade_date: str) -> dict[str, Any]:
        main_rows = self._query(
            """
            SELECT trading_date, product_code, contract, exchange, open_interest,
                   volume, rank, is_main, rule_version, fetched_at
            FROM contract_master
            WHERE product_code=? AND is_main=1 AND trading_date<=?
            ORDER BY trading_date DESC LIMIT 1
            """,
            (symbol, trade_date),
        )
        if not main_rows:
            return {
                "name": SYMBOL_NAMES.get(symbol, symbol),
                "status": "missing_main_contract",
                "metrics": {},
                "anomalies": ["未找到主力合约数据"],
            }

        main = dict(main_rows[0])
        contract = str(main["contract"])
        bar_rows = self._query(
            """
            SELECT trading_date, product_code, contract, exchange, open, high, low,
                   close, settlement, previous_settlement, volume, open_interest,
                   source, fetched_at
            FROM futures_daily
            WHERE product_code=? AND contract=? AND period='1d' AND session='full'
              AND trading_date<=?
            ORDER BY trading_date DESC LIMIT 20
            """,
            (symbol, contract, trade_date),
        )
        if not bar_rows:
            return {
                "name": SYMBOL_NAMES.get(symbol, symbol),
                "status": "missing_daily_bar",
                "metrics": {},
                "anomalies": ["未找到日K数据"],
            }

        latest = dict(bar_rows[0])
        previous = dict(bar_rows[1]) if len(bar_rows) > 1 else None
        close = _number(latest.get("close"))
        previous_baseline = (
            _number(previous.get("settlement")) or _number(previous.get("close"))
            if previous
            else None
        )
        closes = [_number(row["close"]) for row in bar_rows if _number(row["close"]) is not None]
        metrics = {
            "contract": contract,
            "exchange": main.get("exchange"),
            "close": _round(close),
            "change_1d_pct": (
                _round((close / previous_baseline - 1) * 100)
                if close is not None and previous_baseline not in (None, 0)
                else None
            ),
            "ma5": _round(sum(closes[:5]) / len(closes[:5])) if closes[:5] else None,
            "ma20": _round(sum(closes[:20]) / len(closes[:20])) if closes[:20] else None,
            "volume": _round(latest.get("volume")),
            "volume_change_pct": (
                _round((float(latest["volume"]) / float(previous["volume"]) - 1) * 100)
                if previous
                and latest.get("volume") is not None
                and previous.get("volume") not in (None, 0)
                else None
            ),
            "open_interest": _round(latest.get("open_interest")),
            "open_interest_change_1d": (
                _round(float(latest["open_interest"]) - float(previous["open_interest"]))
                if previous
                and latest.get("open_interest") is not None
                and previous.get("open_interest") is not None
                else None
            ),
            "source": latest.get("source"),
            "market_date": latest.get("trading_date"),
        }

        basis_rows = self._query(
            """
            SELECT quote_date, contract, definition_id, basis_value, spot_price,
                   futures_price, source
            FROM basis_history
            WHERE product_code=? AND quote_date<=?
            ORDER BY quote_date DESC, fetched_at DESC LIMIT 1
            """,
            (symbol, trade_date),
        )
        basis = dict(basis_rows[0]) if basis_rows else None
        if basis and basis.get("basis_value") is not None:
            history = self._query(
                """
                SELECT basis_value FROM basis_history
                WHERE product_code=? AND quote_date<=? AND basis_value IS NOT NULL
                ORDER BY quote_date
                """,
                (symbol, trade_date),
            )
            values = [float(row["basis_value"]) for row in history]
            current = float(basis["basis_value"])
            basis["percentile"] = (
                sum(1 for value in values if value <= current) / len(values) * 100
                if values
                else None
            )

        position_rows = self._query(
            """
            SELECT trading_date, contract, member, side, rank, position, change, source
            FROM positions
            WHERE product_code=? AND trading_date<=? AND rank<=3
            ORDER BY trading_date DESC, side, rank
            LIMIT 30
            """,
            (symbol, trade_date),
        )
        latest_position_date = (
            str(position_rows[0]["trading_date"]) if position_rows else None
        )
        positions = [
            dict(row)
            for row in position_rows
            if latest_position_date is not None
            and str(row["trading_date"]) == latest_position_date
        ][:12]
        position_contracts = sorted(
            {str(item.get("contract")) for item in positions if item.get("contract")}
        )
        spots = [
            dict(row)
            for row in self._query(
                """
                SELECT quote_date, spec, region, quote_type, price, unit, source
                FROM spot_prices
                WHERE product_code=? AND quote_date<=?
                ORDER BY quote_date DESC, fetched_at DESC LIMIT 20
                """,
                (symbol, trade_date),
            )
        ]
        basis_spot_quotes = [
            dict(row)
            for row in self._query(
                """
                SELECT quote_date, contract, definition_id, spot_price,
                       futures_price, basis_value, source
                FROM basis_history
                WHERE product_code=? AND quote_date<=? AND spot_price IS NOT NULL
                ORDER BY quote_date DESC, fetched_at DESC LIMIT 5
                """,
                (symbol, trade_date),
            )
        ]
        coal = []
        if symbol == "JM":
            coal = [
                dict(row)
                for row in self._query(
                    """
                    SELECT quote_date, benchmark, price, change_pct, unit, source
                    FROM coal_prices
                    WHERE quote_date<=?
                    ORDER BY quote_date DESC, benchmark LIMIT 5
                    """,
                    (trade_date,),
                )
            ]

        daily_snapshot = {
            "trade_date": latest.get("trading_date"),
            "contract": contract,
            "open": _round(latest.get("open")),
            "high": _round(latest.get("high")),
            "low": _round(latest.get("low")),
            "close": _round(latest.get("close")),
            "settlement": _round(latest.get("settlement")),
            "previous_settlement": _round(latest.get("previous_settlement")),
            "amplitude_pct": _amplitude_pct(latest),
            "volume": _round(latest.get("volume")),
            "open_interest": _round(latest.get("open_interest")),
            "source": latest.get("source"),
        }
        daily_bars_20d = [
            {
                "d": row["trading_date"],
                "o": _round(row.get("open")),
                "h": _round(row.get("high")),
                "l": _round(row.get("low")),
                "c": _round(row.get("close")),
                "s": _round(row.get("settlement")),
                "ps": _round(row.get("previous_settlement")),
                "v": _round(row.get("volume")),
                "oi": _round(row.get("open_interest")),
            }
            for row in map(dict, reversed(bar_rows))
        ]

        anomalies: list[str] = []
        if not basis:
            anomalies.append("未找到基差数据")
        elif str(basis.get("contract")) != contract:
            anomalies.append("基差合约与报告主力合约不一致")
        if not positions:
            anomalies.append("未找到持仓明细")
        elif contract not in position_contracts:
            anomalies.append(
                "持仓合约与报告主力不一致：持仓 "
                + "、".join(position_contracts)
                + f"，主力 {contract}"
            )
        spot_quotes = [
            {
                "date": item.get("quote_date"),
                "price": _round(item.get("price")),
                "unit": item.get("unit") or "元/吨",
                "spec": item.get("spec") or "",
                "region": item.get("region") or "",
                "quote_type": item.get("quote_type") or "spot",
                "contract": None,
                "definition_id": None,
                "source": item.get("source"),
            }
            for item in spots
        ]
        spot_quotes.extend(
            {
                "date": item.get("quote_date"),
                "price": _round(item.get("spot_price")),
                "unit": "元/吨",
                "spec": "",
                "region": "",
                "quote_type": "basis_implied_spot",
                "contract": item.get("contract"),
                "definition_id": item.get("definition_id"),
                "futures_price": _round(item.get("futures_price")),
                "basis_value": _round(item.get("basis_value")),
                "source": item.get("source"),
            }
            for item in basis_spot_quotes
        )

        return {
            "name": SYMBOL_NAMES.get(symbol, symbol),
            "status": "ok",
            "daily_snapshot": daily_snapshot,
            "daily_bars_20d": daily_bars_20d,
            "intraday_volume_5m": self._intraday_volume(contract, trade_date),
            "metrics": metrics,
            "manual_metrics": {
                "basis": _compact_mapping(basis),
                "positions": [_compact_mapping(item) for item in positions],
                "positions_contract": position_contracts or None,
                "spot_quotes": spot_quotes,
                "operating_rate": None,
                "inventory": None,
                "warehouse_receipts": None,
                "valuation_parameters": {},
                "spot_prices": [_compact_mapping(item) for item in spots],
                "coal_prices": [_compact_mapping(item) for item in coal],
            },
            "fundamental": {
                "spot_quotes": spot_quotes,
                "operating_rate": None,
                "inventory": None,
                "warehouse_receipts": None,
                "valuation_parameters": {},
            },
            "anomalies": anomalies,
        }

    def _intraday_volume(self, contract: str, trade_date: str) -> dict[str, Any]:
        if not self.fetch_5m:
            return {
                "available": False,
                "contract": contract,
                "trade_date": trade_date,
                "reason": "5-minute fetch is disabled",
            }
        key = (contract, trade_date)
        if key not in self._intraday_cache:
            self._intraday_cache[key] = fetch_intraday_volume_5m(
                contract,
                trade_date,
                timeout_seconds=self.intraday_timeout_seconds,
            )
        return self._intraday_cache[key]

    def _recent_news(
        self,
        symbols: Sequence[str],
        trade_date: str,
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        rows = self._query(
            """
            SELECT content_hash, published_at, first_seen_at, source, title,
                   summary, url, products_json
            FROM news_items
            WHERE substr(COALESCE(published_at, first_seen_at), 1, 10) <= ?
            ORDER BY COALESCE(published_at, first_seen_at) DESC
            LIMIT ?
            """,
            (trade_date, max(limit * 8, limit)),
        )
        selected = {item.upper() for item in symbols}
        results: list[dict[str, Any]] = []
        for row in rows:
            item_symbols = set(_json_list(row["products_json"]))
            if not item_symbols or not selected.intersection(item_symbols):
                continue
            results.append(_compact_news(dict(row), item_symbols))
            if len(results) >= limit:
                break
        return results

    def _data_quality(
        self,
        symbols: Sequence[str],
        trade_date: str,
        market: Mapping[str, Any],
        news: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        missing = [symbol for symbol, item in market.items() if item.get("status") != "ok"]
        missing_sections: list[str] = []
        valuation_missing: dict[str, list[str]] = {}
        expected_valuation = {
            "SH": ["raw_salt_price", "electricity_price", "liquid_chlorine_price"],
            "V": ["calcium_carbide_price", "ethylene_price"],
            "JM": ["basis_percentile", "premium_discount_structure"],
        }
        for symbol, item in market.items():
            manual = item.get("manual_metrics", {}) if isinstance(item, Mapping) else {}
            if not manual.get("positions"):
                missing_sections.append(f"{symbol}:positions")
            if not manual.get("basis"):
                missing_sections.append(f"{symbol}:basis")
            missing_valuation = list(expected_valuation.get(symbol, []))
            basis = manual.get("basis")
            if isinstance(basis, Mapping) and basis.get("percentile") is not None:
                missing_valuation = [
                    value for value in missing_valuation if value != "basis_percentile"
                ]
            if missing_valuation:
                valuation_missing[symbol] = missing_valuation
        if not news:
            missing_sections.append("news")
        intraday_available = {
            symbol: bool(item.get("intraday_volume_5m", {}).get("available"))
            for symbol, item in market.items()
        }
        if not intraday_available or not all(intraday_available.values()):
            missing_sections.append("intraday_volume_5m")
        for symbol, values in valuation_missing.items():
            missing_sections.extend(f"{symbol}:{value}" for value in values)

        latest = self._latest_report_record()
        return {
            "status": "complete" if not missing and not missing_sections else "partial",
            "missing_market_data": missing,
            "missing_sections": sorted(set(missing_sections)),
            "news_status": "ok" if news else "no_entries",
            "news_source_configured": bool(self.config.get("rss_feeds")),
            "analysis_capabilities": {
                "intraday_volume_5m": {
                    "available": bool(intraday_available)
                    and all(intraday_available.values()),
                    "symbols": intraday_available,
                    "source": "sina:getFewMinLine:5",
                },
                "valuation_inputs": valuation_missing,
            },
            "source": "FuturesIntelTool",
            "database": str(self.database_path),
            "reports_dir": str(self.reports_dir),
            "latest_source_report": (
                {
                    "trading_date": latest["trade_date"],
                    "status": latest.get("status"),
                    "report_id": latest["id"],
                }
                if latest
                else None
            ),
            "requested_trade_date": trade_date,
            "symbols": list(symbols),
            "note": "只读 FuturesIntelTool；原始数据未进入 OpenClaw 上下文。",
        }

    def _report_records(self) -> list[dict[str, Any]]:
        if self._table_exists("report_runs"):
            rows = self._query(
                """
                SELECT trading_date, generated_at, report_dir, status, manifest_json
                FROM report_runs
                ORDER BY trading_date DESC, generated_at DESC
                LIMIT 1000
                """
            )
            records = [
                self._record_from_row(dict(row))
                for row in rows
                if Path(str(row["report_dir"])).exists()
            ]
            if records:
                return records

        records: list[dict[str, Any]] = []
        if self.reports_dir.exists():
            for manifest_path in sorted(
                self.reports_dir.glob("*/manifest.json"),
                reverse=True,
            ):
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                row = {
                    "trading_date": manifest.get("trading_date", manifest_path.parent.name),
                    "generated_at": manifest.get("generated_at", ""),
                    "report_dir": str(manifest_path.parent),
                    "status": manifest.get("status", "unknown"),
                    "manifest_json": json.dumps(manifest, ensure_ascii=False),
                }
                records.append(self._record_from_row(row))
        return records

    def _record_from_row(self, row: Mapping[str, Any]) -> dict[str, Any]:
        report_dir = Path(str(row["report_dir"]))
        try:
            manifest = json.loads(str(row.get("manifest_json") or "{}"))
        except json.JSONDecodeError:
            manifest = {}
        brief_path = report_dir / "daily-brief.md"
        summary = ""
        content_chars = 0
        if brief_path.exists():
            content = brief_path.read_text(encoding="utf-8")
            content_chars = len(content)
            summary = " ".join(content.strip().split())[:180]
        products = manifest.get("products", [])
        symbols = sorted(
            {
                str(item.get("code", "")).upper()
                for item in products
                if item.get("code")
            }
        )
        return {
            "id": f"fi_daily_{row['trading_date']}",
            "trade_date": str(row["trading_date"]),
            "title": f"FuturesIntelTool 期货日报 {row['trading_date']}",
            "symbols": symbols,
            "summary": summary,
            "status": row.get("status"),
            "updated_at": row.get("generated_at") or "",
            "report_dir": str(report_dir),
            "content_chars": content_chars,
            "manifest_text": json.dumps(manifest, ensure_ascii=False),
        }

    def _latest_report_record(self) -> dict[str, Any] | None:
        records = self._report_records()
        return records[0] if records else None

    def _refresh_command(self) -> tuple[list[str], dict[str, str]]:
        environment = os.environ.copy()
        if self.command:
            return list(self.command), environment
        executable = shutil.which("futures-intel")
        if executable:
            return [executable], environment
        if not self.config_path or not self.config_path.exists():
            raise FuturesIntelError(
                "FuturesIntelTool config not found; set FUTURES_INTEL_ROOT or FUTURES_INTEL_CONFIG"
            )
        if not self.source_dir:
            raise FuturesIntelError(
                "futures-intel CLI is not installed and FuturesIntelTool source directory was not found"
            )
        existing = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = (
            f"{self.source_dir}{os.pathsep}{existing}" if existing else str(self.source_dir)
        )
        return [sys.executable, "-m", "futures_intel"], environment

    def _detect_root(self) -> Path:
        if self.root is not None:
            return Path(self.root).expanduser().resolve()
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            return (Path(local_app_data) / "FuturesIntelTool").resolve()
        return Path.cwd().resolve()

    def _detect_config(self) -> Path | None:
        candidates: list[Path] = []
        if self.config_path is not None:
            candidates.append(Path(self.config_path).expanduser())
        if self.root is not None:
            candidates.append(self.root / "config" / "default.json")
        candidates.append(Path.cwd() / "config" / "default.json")
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved.exists():
                return resolved
        return candidates[0].resolve() if candidates else None

    def _read_config(self, path: Path | None) -> dict[str, Any]:
        if not path or not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FuturesIntelError(f"invalid FuturesIntelTool config: {path}") from exc
        if not isinstance(payload, dict):
            raise FuturesIntelError("FuturesIntelTool config must be a JSON object")
        return payload

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        if not self.database_path.exists():
            raise FuturesIntelError(
                f"FuturesIntelTool database not found: {self.database_path}"
            )
        connection = sqlite3.connect(
            f"{self.database_path.resolve().as_uri()}?mode=ro",
            uri=True,
            timeout=15,
        )
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def _query(
        self, sql: str, parameters: Sequence[Any] = ()
    ) -> list[sqlite3.Row]:
        with self._connection() as connection:
            return list(connection.execute(sql, parameters).fetchall())

    def _table_exists(self, name: str) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (name,),
            ).fetchone()
        return row is not None


def _amplitude_pct(bar: Mapping[str, Any]) -> float | None:
    high = _number(bar.get("high"))
    low = _number(bar.get("low"))
    baseline = _number(bar.get("previous_settlement")) or _number(bar.get("close"))
    if high is None or low is None or baseline in (None, 0):
        return None
    return _round((high - low) / baseline * 100)


def _report_anomaly_count(record: Mapping[str, Any]) -> int:
    report_dir = Path(str(record.get("report_dir") or ""))
    path = report_dir / "anomalies.json"
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    items = payload.get("items") if isinstance(payload, Mapping) else None
    return len(items) if isinstance(items, list) else 0


def _apply_cross_product_warnings(market: Mapping[str, Any]) -> None:
    values: dict[tuple[str, float], list[str]] = {}
    for symbol, item in market.items():
        if not isinstance(item, Mapping):
            continue
        manual = item.get("manual_metrics", {})
        basis = manual.get("basis") if isinstance(manual, Mapping) else None
        if not isinstance(basis, Mapping):
            continue
        spot = _number(basis.get("spot_price"))
        quote_date = basis.get("quote_date")
        if spot is None or not quote_date:
            continue
        values.setdefault((str(quote_date), float(spot)), []).append(symbol)

    for (quote_date, spot), entries in values.items():
        symbols = sorted(set(entries))
        if len(symbols) < 2:
            continue
        warning = (
            f"跨品种现货价同值告警：{quote_date} {spot:g} 元/吨同时出现于 "
            + "、".join(symbols)
            + "，疑似混用或口径错误，基差不得直接使用，需核实来源"
        )
        for symbol in symbols:
            anomalies = market[symbol].setdefault("anomalies", [])
            if warning not in anomalies:
                anomalies.append(warning)


def _resolve_under(base: Path, value: Any) -> Path:
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _json_list(value: Any) -> list[str]:
    try:
        parsed = json.loads(str(value or "[]"))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).upper() for item in parsed]


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any) -> float | None:
    number = _number(value)
    return round(number, 4) if number is not None else None


def _compact_mapping(value: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    compact: dict[str, Any] = {}
    for key, item in value.items():
        if key in {"raw_json", "manifest_json"}:
            continue
        if isinstance(item, float):
            compact[key] = round(item, 4)
        else:
            compact[key] = item
    return compact


def _compact_news(item: Mapping[str, Any], symbols: set[str]) -> dict[str, Any]:
    summary = str(item.get("summary") or "").strip().replace("\n", " ")
    excerpt = summary[:MAX_NEWS_EXCERPT_CHARS]
    if len(summary) > MAX_NEWS_EXCERPT_CHARS:
        excerpt += "…"
    return {
        "id": item.get("content_hash") or item.get("id"),
        "title": item.get("title", ""),
        "excerpt": excerpt,
        "source": item.get("source", ""),
        "published_at": item.get("published_at") or item.get("first_seen_at"),
        "symbols": sorted(symbols),
        "url": item.get("url", ""),
    }


def _cross_market(market: Mapping[str, Any]) -> dict[str, Any]:
    changes = {
        symbol: item.get("metrics", {}).get("change_1d_pct")
        for symbol, item in market.items()
    }
    sh_change = changes.get("SH")
    v_change = changes.get("V")
    return {
        "daily_change_pct": changes,
        "chlor_alkali_relative_change_spread": (
            _round(float(sh_change) - float(v_change))
            if sh_change is not None and v_change is not None
            else None
        ),
        "relationship_notes": [
            "烧碱与PVC同属氯碱产业链，需结合液氯、开工率和库存共同观察。",
            "焦煤处于黑色产业链上游，应与焦炭、钢材利润和铁水产量联动观察。",
        ],
    }


def _slice_text_by_token_budget(
    text: str, *, offset: int, max_tokens: int
) -> tuple[str, int, bool]:
    safe_offset = max(0, min(offset, len(text)))
    remaining = text[safe_offset:]
    if estimate_tokens(remaining) <= max_tokens:
        return remaining, len(text), False

    low = 0
    high = len(remaining)
    while low < high:
        middle = (low + high + 1) // 2
        if estimate_tokens(remaining[:middle]) <= max_tokens:
            low = middle
        else:
            high = middle - 1
    clipped = remaining[:low]
    return clipped, safe_offset + low, True


def _last_json_value(stdout: str) -> Any:
    text = stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for line in reversed(text.splitlines()):
            candidate = line.strip()
            if not candidate:
                continue
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return None
