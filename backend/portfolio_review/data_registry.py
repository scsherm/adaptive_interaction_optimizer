from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


SOURCE_FILES = {
    "raw_prices": "raw_prices.csv",
    "fundamentals": "fundamentals_metrics.csv",
    "sentiment": "ticker_news_sentiment.csv",
    "options": "options_positioning_metrics.csv",
    "ownership": "institutional_ownership_metrics.csv",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def ticker_key(row: dict[str, str]) -> str:
    return str(row.get("ticker", "")).upper()


def build_data_registry(data_dir: Path) -> dict[str, Any]:
    sources: dict[str, Any] = {}
    tickers: dict[str, Any] = {}
    for name, relative in SOURCE_FILES.items():
        path = data_dir / relative
        rows = read_csv(path)
        sources[name] = {
            "path": str(path),
            "exists": path.exists(),
            "row_count": len(rows),
        }
        if name == "raw_prices":
            by_ticker: dict[str, list[str]] = {}
            for row in rows:
                ticker = ticker_key(row)
                date = row.get("date", "")
                if ticker and date:
                    by_ticker.setdefault(ticker, []).append(date)
            for ticker, dates in by_ticker.items():
                ordered = sorted(dates)
                tickers.setdefault(ticker, {})
                tickers[ticker].update(
                    {
                        "price_rows": len(ordered),
                        "first_price_date": ordered[0],
                        "last_price_date": ordered[-1],
                    }
                )
            continue

        for row in rows:
            ticker = ticker_key(row)
            if not ticker:
                continue
            tickers.setdefault(ticker, {})
            field = f"{name}_rows"
            tickers[ticker][field] = int(tickers[ticker].get(field, 0)) + 1

    return {"sources": sources, "tickers": tickers}
