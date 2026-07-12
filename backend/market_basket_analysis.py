#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from statistics import mean, pstdev
from urllib.parse import quote

from market_config import Holding, load_market_config


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
YAHOO_DIR = DATA_DIR / "yahoo"

CONFIG = load_market_config()
START_DATE = CONFIG.start_date
END_DATE = CONFIG.end_date
HOLDINGS = CONFIG.holdings
BENCHMARKS = CONFIG.benchmarks
BASKET_LABELS = CONFIG.basket_labels
SYMBOL_DECISIONS = CONFIG.symbol_decisions
MIN_BASKET_START_COVERAGE = 0.75
PRICE_HISTORY_BUFFER_DAYS = 540


def unix_seconds(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())


def safe_filename(ticker: str) -> str:
    return ticker.replace("-", "_").replace(".", "_")


def unique_holdings() -> list[Holding]:
    by_ticker: dict[str, Holding] = {}
    for holding in HOLDINGS + BENCHMARKS:
        by_ticker.setdefault(holding.ticker, holding)
    return sorted(by_ticker.values(), key=lambda h: h.ticker)


def write_basket_definitions() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (DATA_DIR / "basket_definitions.csv").open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["basket", "ticker", "name", "weighting", "note"],
        )
        writer.writeheader()
        for holding in HOLDINGS:
            writer.writerow(
                {
                    "basket": holding.basket,
                    "ticker": holding.ticker,
                    "name": holding.name,
                    "weighting": "equal",
                    "note": holding.note,
                }
            )


def write_curl_config() -> None:
    YAHOO_DIR.mkdir(parents=True, exist_ok=True)
    history_start = START_DATE - timedelta(days=PRICE_HISTORY_BUFFER_DAYS)
    period1 = unix_seconds(history_start)
    period2 = unix_seconds(END_DATE + timedelta(days=1))
    lines = [
        'user-agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"',
        "http1.1",
        "fail",
        "location",
        "retry = 2",
        "retry-delay = 1",
    ]
    for holding in unique_holdings():
        ticker = quote(holding.ticker, safe="")
        url = (
            f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
            f"?period1={period1}&period2={period2}"
            "&interval=1d&events=history&includeAdjustedClose=true"
        )
        output = YAHOO_DIR / f"{safe_filename(holding.ticker)}.json"
        lines.extend(
            [
                "url = " + json.dumps(url),
                "output = " + json.dumps(str(output)),
            ]
        )
    (DATA_DIR / "yahoo_chart_curl.cfg").write_text("\n".join(lines) + "\n")


def parse_chart(path: Path, ticker: str) -> tuple[dict, list[dict]]:
    payload = json.loads(path.read_text())
    chart = payload.get("chart", {})
    if chart.get("error"):
        raise ValueError(f"{ticker}: Yahoo error: {chart['error']}")
    result = chart.get("result") or []
    if not result:
        raise ValueError(f"{ticker}: no chart result")
    result0 = result[0]
    meta = result0.get("meta", {})
    timestamps = result0.get("timestamp") or []
    quote_rows = (result0.get("indicators", {}).get("quote") or [{}])[0]
    adj_rows = (result0.get("indicators", {}).get("adjclose") or [{}])[0]
    adjclose = adj_rows.get("adjclose") or []
    close = quote_rows.get("close") or []
    volume = quote_rows.get("volume") or []
    rows: list[dict] = []
    for i, ts in enumerate(timestamps):
        row_date = datetime.fromtimestamp(ts, tz=UTC).date().isoformat()
        adj = adjclose[i] if i < len(adjclose) else None
        raw_close = close[i] if i < len(close) else None
        if adj is None and raw_close is None:
            continue
        rows.append(
            {
                "date": row_date,
                "ticker": ticker,
                "adj_close": float(adj if adj is not None else raw_close),
                "close": float(raw_close if raw_close is not None else adj),
                "volume": int(volume[i]) if i < len(volume) and volume[i] is not None else "",
                "currency": meta.get("currency", ""),
                "instrument_type": meta.get("instrumentType", ""),
                "exchange": meta.get("exchangeName", ""),
                "source": CONFIG.source,
            }
        )
    return meta, rows


def pct(value: float) -> float:
    return value * 100.0


def max_drawdown(index_values: list[float]) -> float:
    peak = -math.inf
    worst = 0.0
    for value in index_values:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1)
    return pct(worst)


def annualized_vol(daily_returns: list[float]) -> float:
    if len(daily_returns) < 2:
        return 0.0
    return pct(pstdev(daily_returns) * math.sqrt(252))


def min_start_constituents(total: int) -> int:
    return max(1, math.ceil(total * MIN_BASKET_START_COVERAGE))


def csv_writer(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_analysis_brief(summary: dict, metadata: list[dict]) -> None:
    basket_metrics = summary["basket_metrics"]
    times = sorted(r["regular_market_time"] for r in metadata if r["regular_market_time"])
    snapshot = f"{times[0]} to {times[-1]}" if times else "n/a"
    benchmark_rows = {
        row["ticker"]: row
        for row in csv.DictReader((DATA_DIR / "constituent_metrics.csv").open())
    }
    lines = [
        "# Market Basket Analysis",
        "",
        f"Window: {START_DATE.isoformat()} through {END_DATE.isoformat()}",
        "",
        "Methodology:",
        f"- {CONFIG.weighting}.",
        "- Each constituent is normalized to 100 from its first available adjusted close on or after the start date.",
        "- Basket index compounds the equal-weighted daily return of active constituents.",
        f"- A basket begins once at least {MIN_BASKET_START_COVERAGE:.0%} of configured constituents have price history.",
        "- Late-listed/relisted constituents enter after their first available return; missing same-day prices for active constituents are treated as flat.",
        f"- {CONFIG.data_status}",
        f"- {CONFIG.source} timestamps span {snapshot}.",
        "",
        "Symbol decisions:",
    ]
    lines.extend(f"- {note}" for note in SYMBOL_DECISIONS)
    lines.extend(
        [
            "",
            "Ranked basket results:",
            "",
            "| Rank | Basket | Return | Ann. vol | Max drawdown | Return/vol | Best | Worst | Positive constituents |",
            "|---:|---|---:|---:|---:|---:|---|---|---:|",
        ]
    )
    for row in basket_metrics:
        lines.append(
            "| {rank} | {basket} | {ret:.2f}% | {vol:.2f}% | {dd:.2f}% | {rv:.2f} | {best} ({best_ret:.2f}%) | {worst} ({worst_ret:.2f}%) | {pos}/{total} |".format(
                rank=row["rank"],
                basket=BASKET_LABELS.get(row["basket"], row["basket"]),
                ret=float(row["total_return_pct"]),
                vol=float(row["annualized_vol_pct"]),
                dd=float(row["max_drawdown_pct"]),
                rv=float(row["return_vol_ratio"]),
                best=row["best_constituent"],
                best_ret=float(row["best_constituent_return_pct"]),
                worst=row["worst_constituent"],
                worst_ret=float(row["worst_constituent_return_pct"]),
                pos=row["participation_positive_count"],
                total=row["constituents_used"],
            )
        )
    lines.extend(["", "Benchmark context:", ""])
    for ticker in ["SPY", "QQQ", "BTC-USD"]:
        row = benchmark_rows.get(ticker)
        if row:
            lines.append(
                f"- {ticker}: {float(row['total_return_pct']):.2f}% from {row['start_date']} to {row['end_date']}."
            )
    lines.extend(
        [
            "",
            "Initial assessment:",
            "- Semiconductors led the period with the strongest absolute return and full positive participation.",
            "- Cybersecurity and BTC mining / AI pivot also showed broad participation, but the mining basket carried materially higher volatility and drawdown.",
            "- Photonics had strong headline performance but was less clean internally: AXTI drove a large share while IPGP was negative.",
            "- Oil was positive with full participation and much lower volatility than the high-beta technology baskets.",
            "- Software was mixed despite a positive basket return; only half the constituents were positive.",
            "- Construction, power/grid, and rare earth minerals lagged; rare earths had the weakest return and weakest breadth.",
        ]
    )
    (DATA_DIR / "analysis_brief.md").write_text("\n".join(lines) + "\n")


def analyze() -> None:
    write_basket_definitions()
    metadata: list[dict] = []
    price_rows: list[dict] = []
    row_by_ticker: dict[str, list[dict]] = {}
    errors: list[dict] = []

    for holding in unique_holdings():
        path = YAHOO_DIR / f"{safe_filename(holding.ticker)}.json"
        try:
            meta, rows = parse_chart(path, holding.ticker)
        except Exception as exc:  # noqa: BLE001
            errors.append({"ticker": holding.ticker, "error": str(exc)})
            continue
        first_date = rows[0]["date"] if rows else ""
        last_date = rows[-1]["date"] if rows else ""
        metadata.append(
            {
                "ticker": holding.ticker,
                "source_symbol": meta.get("symbol", ""),
                "name": meta.get("longName") or meta.get("shortName") or holding.name,
                "currency": meta.get("currency", ""),
                "instrument_type": meta.get("instrumentType", ""),
                "exchange": meta.get("fullExchangeName") or meta.get("exchangeName") or "",
                "regular_market_time": datetime.fromtimestamp(
                    meta.get("regularMarketTime", 0), tz=UTC
                ).isoformat()
                if meta.get("regularMarketTime")
                else "",
                "regular_market_price": meta.get("regularMarketPrice", ""),
                "first_date": first_date,
                "last_date": last_date,
                "row_count": len(rows),
            }
        )
        row_by_ticker[holding.ticker] = rows
        price_rows.extend(rows)

    csv_writer(
        DATA_DIR / "source_metadata.csv",
        [
            "ticker",
            "source_symbol",
            "name",
            "currency",
            "instrument_type",
            "exchange",
            "regular_market_time",
            "regular_market_price",
            "first_date",
            "last_date",
            "row_count",
        ],
        metadata,
    )
    csv_writer(
        DATA_DIR / "raw_prices.csv",
        [
            "date",
            "ticker",
            "adj_close",
            "close",
            "volume",
            "currency",
            "instrument_type",
            "exchange",
            "source",
        ],
        sorted(price_rows, key=lambda r: (r["ticker"], r["date"])),
    )
    error_path = DATA_DIR / "data_errors.csv"
    if errors:
        csv_writer(error_path, ["ticker", "error"], errors)
    elif error_path.exists():
        error_path.unlink()

    normalized_rows: list[dict] = []
    constituent_metrics: list[dict] = []
    normalized_by_ticker: dict[str, dict[str, float]] = {}
    returns_by_ticker: dict[str, dict[str, float]] = {}

    for holding in unique_holdings():
        rows = row_by_ticker.get(holding.ticker, [])
        rows = [r for r in rows if START_DATE.isoformat() <= r["date"] <= END_DATE.isoformat()]
        if not rows:
            continue
        start_row = next((r for r in rows if r["date"] >= START_DATE.isoformat()), rows[0])
        start_price = start_row["adj_close"]
        series = {r["date"]: r["adj_close"] / start_price * 100 for r in rows}
        normalized_by_ticker[holding.ticker] = series
        daily_returns: dict[str, float] = {}
        prev = None
        high = -math.inf
        for r in rows:
            current = r["adj_close"]
            high = max(high, current)
            if prev is not None:
                daily_returns[r["date"]] = current / prev - 1
            prev = current
            normalized_rows.append(
                {
                    "date": r["date"],
                    "ticker": holding.ticker,
                    "normalized_value": round(series[r["date"]], 6),
                    "adj_close": round(r["adj_close"], 6),
                }
            )
        returns_by_ticker[holding.ticker] = daily_returns
        latest = rows[-1]
        final_return = latest["adj_close"] / start_price - 1
        highs = [r["adj_close"] for r in rows]
        constituent_metrics.append(
            {
                "basket_memberships": ";".join(
                    sorted({h.basket for h in HOLDINGS if h.ticker == holding.ticker})
                )
                or holding.basket,
                "ticker": holding.ticker,
                "name": holding.name,
                "start_date": start_row["date"],
                "end_date": latest["date"],
                "start_adj_close": round(start_price, 6),
                "end_adj_close": round(latest["adj_close"], 6),
                "total_return_pct": round(pct(final_return), 4),
                "max_drawdown_pct": round(
                    max_drawdown([r["adj_close"] / start_price * 100 for r in rows]), 4
                ),
                "annualized_vol_pct": round(annualized_vol(list(daily_returns.values())), 4),
                "latest_volume": latest["volume"],
                "row_count": len(rows),
            }
        )

    csv_writer(
        DATA_DIR / "normalized_prices.csv",
        ["date", "ticker", "normalized_value", "adj_close"],
        sorted(normalized_rows, key=lambda r: (r["ticker"], r["date"])),
    )
    csv_writer(
        DATA_DIR / "constituent_metrics.csv",
        [
            "basket_memberships",
            "ticker",
            "name",
            "start_date",
            "end_date",
            "start_adj_close",
            "end_adj_close",
            "total_return_pct",
            "max_drawdown_pct",
            "annualized_vol_pct",
            "latest_volume",
            "row_count",
        ],
        sorted(constituent_metrics, key=lambda r: (r["basket_memberships"], r["ticker"])),
    )

    basket_rows: list[dict] = []
    basket_metrics: list[dict] = []
    basket_holdings: dict[str, list[Holding]] = {}
    for holding in HOLDINGS:
        basket_holdings.setdefault(holding.basket, []).append(holding)

    for basket, holdings in sorted(basket_holdings.items()):
        valid = [h for h in holdings if h.ticker in normalized_by_ticker]
        basket_dates = sorted(
            {day for h in valid for day in normalized_by_ticker[h.ticker].keys()}
        )
        basket_series: list[tuple[str, float]] = []
        first_date_by_ticker = {
            h.ticker: min(normalized_by_ticker[h.ticker]) for h in valid
        }
        minimum_active = min_start_constituents(len(valid))
        basket_index: float | None = None
        for day in basket_dates:
            active = [
                h for h in valid if first_date_by_ticker[h.ticker] <= day
            ]
            if len(active) < minimum_active:
                continue
            reporting_count = 0
            filled_count = 0
            day_returns: list[float] = []
            for h in active:
                if day in normalized_by_ticker[h.ticker]:
                    reporting_count += 1
                else:
                    filled_count += 1
                ticker_return = returns_by_ticker.get(h.ticker, {}).get(day)
                if ticker_return is not None:
                    day_returns.append(ticker_return)
                elif first_date_by_ticker[h.ticker] < day:
                    day_returns.append(0.0)
            if basket_index is None:
                basket_index = 100.0
            elif day_returns:
                basket_index *= 1 + mean(day_returns)
            basket_series.append((day, basket_index))
            basket_rows.append(
                {
                    "date": day,
                    "basket": basket,
                    "basket_index": round(basket_index, 6),
                    "constituents_reporting": reporting_count,
                    "constituents_filled": filled_count,
                    "constituents_total": len(valid),
                }
            )
        if not basket_series:
            continue
        index_values = [v for _, v in basket_series]
        daily_returns = [
            index_values[i] / index_values[i - 1] - 1 for i in range(1, len(index_values))
        ]
        final_index = index_values[-1]
        basket_return = final_index - 100
        basket_vol = annualized_vol(daily_returns)
        basket_drawdown = max_drawdown(index_values)
        returns = []
        for h in valid:
            series = normalized_by_ticker[h.ticker]
            end_day = basket_series[-1][0]
            available_days = [day for day in series if day <= end_day]
            if available_days:
                returns.append((h.ticker, series[max(available_days)] - 100))
        returns_sorted = sorted(returns, key=lambda x: x[1], reverse=True)
        basket_metrics.append(
            {
                "basket": basket,
                "start_date": basket_series[0][0],
                "end_date": basket_series[-1][0],
                "constituents_used": len(valid),
                "total_return_pct": round(basket_return, 4),
                "annualized_vol_pct": round(basket_vol, 4),
                "max_drawdown_pct": round(basket_drawdown, 4),
                "return_vol_ratio": round(basket_return / basket_vol, 4)
                if basket_vol
                else "",
                "return_drawdown_ratio": round(basket_return / abs(basket_drawdown), 4)
                if basket_drawdown
                else "",
                "best_constituent": returns_sorted[0][0] if returns_sorted else "",
                "best_constituent_return_pct": round(returns_sorted[0][1], 4)
                if returns_sorted
                else "",
                "worst_constituent": returns_sorted[-1][0] if returns_sorted else "",
                "worst_constituent_return_pct": round(returns_sorted[-1][1], 4)
                if returns_sorted
                else "",
                "participation_positive_count": sum(1 for _, r in returns if r > 0),
                "participation_positive_pct": round(
                    sum(1 for _, r in returns if r > 0) / len(returns) * 100, 4
                )
                if returns
                else "",
            }
        )

    basket_metrics = sorted(basket_metrics, key=lambda r: r["total_return_pct"], reverse=True)
    for rank, row in enumerate(basket_metrics, start=1):
        row["rank"] = rank

    csv_writer(
        DATA_DIR / "basket_daily.csv",
        [
            "date",
            "basket",
            "basket_index",
            "constituents_reporting",
            "constituents_filled",
            "constituents_total",
        ],
        sorted(basket_rows, key=lambda r: (r["basket"], r["date"])),
    )
    csv_writer(
        DATA_DIR / "basket_metrics.csv",
        [
            "rank",
            "basket",
            "start_date",
            "end_date",
            "constituents_used",
            "total_return_pct",
            "annualized_vol_pct",
            "max_drawdown_pct",
            "return_vol_ratio",
            "return_drawdown_ratio",
            "best_constituent",
            "best_constituent_return_pct",
            "worst_constituent",
            "worst_constituent_return_pct",
            "participation_positive_count",
            "participation_positive_pct",
        ],
        basket_metrics,
    )

    summary = {
        "methodology": {
            "start_date": START_DATE.isoformat(),
            "end_date": END_DATE.isoformat(),
            "weighting": "equal-weighted constituents, normalized to 100 on first available row on or after start date",
            "price_field": CONFIG.price_field,
            "source": CONFIG.source,
            "note": CONFIG.data_status,
            "basket_return_method": "equal-weighted daily returns of active constituents",
            "basket_min_start_coverage_pct": pct(MIN_BASKET_START_COVERAGE),
            "late_history_policy": "late-listed/relisted constituents enter after their first available return",
        },
        "basket_metrics": basket_metrics,
        "data_errors": errors,
    }
    (DATA_DIR / "analysis_summary.json").write_text(json.dumps(summary, indent=2))
    write_analysis_brief(summary, metadata)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["write-config", "analyze"])
    args = parser.parse_args()
    if args.command == "write-config":
        write_basket_definitions()
        write_curl_config()
    elif args.command == "analyze":
        analyze()


if __name__ == "__main__":
    main()
