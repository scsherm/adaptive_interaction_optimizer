from __future__ import annotations

import csv
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote


PRICE_FIELDS = ["date", "ticker", "adj_close", "close", "volume", "currency", "instrument_type", "exchange", "source"]
SOURCE = "Yahoo Finance chart API"
USER_AGENT = "Mozilla/5.0 market-basket-analysis/1.0 contact@example.com"


def unix_seconds(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PRICE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def yahoo_chart_url(ticker: str, start: date, end: date) -> str:
    symbol = quote(ticker, safe="")
    return (
        f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?period1={unix_seconds(start)}&period2={unix_seconds(end + timedelta(days=1))}"
        "&interval=1d&events=history&includeAdjustedClose=true"
    )


def fetch_json(url: str, timeout: int = 20) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def fetch_text(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain,*/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def sp500_tickers_from_html(html: str) -> list[str]:
    tickers = []
    for match in re.finditer(r"<tr>\s*<td>\s*<a[^>]*>\s*([A-Z][A-Z.\-]{0,8})\s*</a>", html, flags=re.I):
        ticker = match.group(1).upper().replace(".", "-")
        if ticker not in tickers:
            tickers.append(ticker)
    return tickers


def fetch_sp500_tickers(timeout: int = 20) -> list[str]:
    html = fetch_text("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", timeout=timeout)
    return sp500_tickers_from_html(html)


def chart_rows(payload: dict[str, Any], ticker: str) -> list[dict[str, Any]]:
    chart = payload.get("chart", {})
    if chart.get("error"):
        raise ValueError(f"{ticker}: Yahoo chart error: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        return []
    result = results[0]
    meta = result.get("meta", {})
    timestamps = result.get("timestamp") or []
    quote_rows = (result.get("indicators", {}).get("quote") or [{}])[0]
    adj_rows = (result.get("indicators", {}).get("adjclose") or [{}])[0]
    closes = quote_rows.get("close") or []
    volumes = quote_rows.get("volume") or []
    adj_closes = adj_rows.get("adjclose") or []
    rows = []
    for index, timestamp in enumerate(timestamps):
        adj_close = adj_closes[index] if index < len(adj_closes) else None
        close = closes[index] if index < len(closes) else None
        if adj_close is None and close is None:
            continue
        rows.append(
            {
                "date": datetime.fromtimestamp(timestamp, tz=UTC).date().isoformat(),
                "ticker": ticker.upper(),
                "adj_close": float(adj_close if adj_close is not None else close),
                "close": float(close if close is not None else adj_close),
                "volume": int(volumes[index]) if index < len(volumes) and volumes[index] is not None else "",
                "currency": meta.get("currency", ""),
                "instrument_type": meta.get("instrumentType", ""),
                "exchange": meta.get("exchangeName", ""),
                "source": SOURCE,
            }
        )
    return rows


def merge_price_rows(existing_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for row in existing_rows:
        key = (str(row.get("ticker", "")).upper(), str(row.get("date", "")))
        if key[0] and key[1]:
            merged[key] = dict(row)
    for row in new_rows:
        key = (str(row.get("ticker", "")).upper(), str(row.get("date", "")))
        if key[0] and key[1]:
            updated = dict(row)
            updated["ticker"] = key[0]
            merged[key] = updated
    return sorted(merged.values(), key=lambda row: (str(row.get("ticker", "")), str(row.get("date", ""))))


def fetch_public_price_history(
    data_dir: Path,
    tickers: list[str],
    start: date,
    end: date,
    timeout: int = 20,
    max_workers: int = 8,
) -> dict[str, Any]:
    fetched_rows: list[dict[str, Any]] = []
    errors = []
    unique_tickers = sorted({ticker.upper() for ticker in tickers if ticker})

    def fetch_one(ticker: str) -> tuple[str, list[dict[str, Any]], str]:
        try:
            return ticker, chart_rows(fetch_json(yahoo_chart_url(ticker, start, end), timeout=timeout), ticker), ""
        except Exception as exc:  # noqa: BLE001
            return ticker, [], str(exc)[:240]

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        futures = [executor.submit(fetch_one, ticker) for ticker in unique_tickers]
        for future in as_completed(futures):
            ticker, rows, error = future.result()
            fetched_rows.extend(rows)
            if error:
                errors.append({"ticker": ticker, "error": error})

    price_path = data_dir / "raw_prices.csv"
    merged = merge_price_rows(read_csv(price_path), fetched_rows)
    write_csv(price_path, merged)
    return {
        "requested_tickers": len(unique_tickers),
        "fetched_rows": len(fetched_rows),
        "merged_rows": len(merged),
        "errors": errors,
        "path": str(price_path),
    }


def default_start_date(years: int) -> date:
    return date.today() - timedelta(days=max(1, years) * 365)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Fetch and merge public market price history.")
    parser.add_argument("--data-dir", default=str(Path(__file__).resolve().parents[1] / "data"))
    parser.add_argument("--tickers", default="", help="Comma-separated ticker list.")
    parser.add_argument("--universe", choices=["manual", "sp500"], default="manual")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--max-tickers", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    tickers = [ticker.strip().upper() for ticker in args.tickers.split(",") if ticker.strip()]
    if args.universe == "sp500":
        tickers.extend(fetch_sp500_tickers())
    tickers = sorted(set(tickers))
    if args.max_tickers:
        tickers = tickers[: args.max_tickers]
    result = fetch_public_price_history(
        Path(args.data_dir),
        tickers,
        start=default_start_date(args.years),
        end=date.today(),
        max_workers=args.workers,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
