"""Deterministic fake crawler used by examples and tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    base_prices = {"SH": 2450.0, "V": 5100.0, "JM": 1280.0}
    close = base_prices[args.source]
    payload = {
        "bars": [
            {
                "trade_date": args.trade_date,
                "symbol": args.source,
                "contract": "MAIN",
                "open": close - 10,
                "high": close + 15,
                "low": close - 18,
                "close": close,
                "settlement": close,
                "volume": 150000,
                "open_interest": 230000,
                "source": "fake-crawler",
                "is_main": True,
            }
        ]
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "success", "source": args.source}))


if __name__ == "__main__":
    main()
