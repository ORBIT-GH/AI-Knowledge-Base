"""Validation helpers shared by HTTP, MCP, and crawler adapters."""

from __future__ import annotations

import math
import re
from datetime import date
from typing import Any, Sequence

from futures_kb.constants import SYMBOL_NAMES


_METRIC_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def validate_trade_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError(f"invalid trade_date: {value}") from exc


def normalize_symbol(value: str) -> str:
    symbol = value.strip().upper()
    if symbol not in SYMBOL_NAMES:
        raise ValueError(f"unsupported symbol: {value}")
    return symbol


def normalize_symbols(values: Sequence[str] | None) -> tuple[str, ...]:
    if not values:
        return tuple(SYMBOL_NAMES)
    normalized = tuple(dict.fromkeys(normalize_symbol(item) for item in values if item.strip()))
    if not normalized:
        raise ValueError("at least one symbol is required")
    return normalized


def validate_metric_name(value: str) -> str:
    metric = value.strip().lower()
    if not _METRIC_PATTERN.fullmatch(metric):
        raise ValueError(f"invalid metric name: {value}")
    return metric


def finite_float(value: Any, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def optional_finite_float(value: Any, *, field: str) -> float | None:
    if value is None or value == "":
        return None
    return finite_float(value, field=field)
