from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from portfolio_review.data_registry import build_data_registry
from portfolio_review.ml_models import build_price_history_training_rows


BENCHMARK_TICKERS = {"SPY", "QQQ", "BTC-USD", "BTC/USD"}


def is_equity_training_symbol(ticker: str) -> bool:
    ticker = ticker.upper()
    return ticker not in BENCHMARK_TICKERS and not ticker.endswith("-USD") and not ticker.endswith("/USD")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def select_training_universe_tickers(
    data_dir: Path,
    seed_tickers: list[str] | None = None,
    min_price_rows: int = 120,
    max_tickers: int = 500,
) -> list[str]:
    registry = build_data_registry(data_dir)
    seed_set = {ticker.upper() for ticker in seed_tickers or [] if ticker}
    eligible = []
    for ticker, info in registry.get("tickers", {}).items():
        if not is_equity_training_symbol(ticker):
            continue
        if int(info.get("price_rows", 0)) >= min_price_rows:
            eligible.append(ticker)
    combined = sorted(set(eligible).union(seed_set))
    return combined[:max_tickers]


def build_training_dataset(
    data_dir: Path,
    tickers: list[str],
    as_of_date: str | None = None,
    max_rows: int | None = None,
) -> dict[str, Any]:
    rows = build_price_history_training_rows(read_csv(data_dir / "raw_prices.csv"), tickers)
    if as_of_date:
        rows = [row for row in rows if str(row.get("label_end_date", "")) <= as_of_date]
    if max_rows and len(rows) > max_rows:
        rows = rows[-max_rows:]
    return {
        "row_count": len(rows),
        "tickers": sorted({str(row.get("ticker", "")) for row in rows}),
        "rows": rows,
    }
