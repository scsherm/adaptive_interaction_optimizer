#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, median, pstdev

from market_config import load_market_config


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
MIN_BASKET_START_COVERAGE = 0.75


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open(newline="") as f:
        return list(csv.DictReader(f))


def analysis_window_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    config = load_market_config()
    start = config.start_date.isoformat()
    end = config.end_date.isoformat()
    return [row for row in rows if start <= row.get("date", "") <= end]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def pct(value: float) -> float:
    return value * 100.0


def round_or_blank(value: float | None, digits: int = 4) -> float | str:
    if value is None or not math.isfinite(value):
        return ""
    return round(value, digits)


def return_n(values: list[float], periods: int) -> float | None:
    if len(values) <= periods:
        return None
    return pct(values[-1] / values[-periods - 1] - 1)


def daily_returns(series: list[tuple[str, float]]) -> dict[str, float]:
    returns = {}
    for i in range(1, len(series)):
        prev = series[i - 1][1]
        current = series[i][1]
        if prev:
            returns[series[i][0]] = current / prev - 1
    return returns


def correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mx = mean(xs)
    my = mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / len(xs)
    sx = pstdev(xs)
    sy = pstdev(ys)
    if sx == 0 or sy == 0:
        return None
    return cov / (sx * sy)


def beta(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    my = mean(ys)
    variance = sum((y - my) ** 2 for y in ys) / len(ys)
    if variance == 0:
        return None
    mx = mean(xs)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / len(xs)
    return cov / variance


def aligned_returns(
    asset_returns: dict[str, float], benchmark_returns: dict[str, float]
) -> tuple[list[float], list[float]]:
    dates = sorted(set(asset_returns) & set(benchmark_returns))
    return [asset_returns[d] for d in dates], [benchmark_returns[d] for d in dates]


def capture_ratio(
    asset_returns: dict[str, float], benchmark_returns: dict[str, float], side: str
) -> float | None:
    pairs = []
    for day in sorted(set(asset_returns) & set(benchmark_returns)):
        benchmark_return = benchmark_returns[day]
        if side == "up" and benchmark_return > 0:
            pairs.append((asset_returns[day], benchmark_return))
        elif side == "down" and benchmark_return < 0:
            pairs.append((asset_returns[day], benchmark_return))
    if len(pairs) < 3:
        return None
    asset_avg = mean(a for a, _ in pairs)
    benchmark_avg = mean(b for _, b in pairs)
    if benchmark_avg == 0:
        return None
    return asset_avg / benchmark_avg


def volatility(values: list[float], annualization: int, periods: int | None = None) -> float | None:
    selected = values[-periods:] if periods else values
    if len(selected) < 3:
        return None
    return pct(pstdev(selected) * math.sqrt(annualization))


def min_start_constituents(total: int) -> int:
    return max(1, math.ceil(total * MIN_BASKET_START_COVERAGE))


def window_stats(series: list[tuple[str, float]]) -> dict[str, float | str | None]:
    if not series:
        return {}
    values = [value for _, value in series]
    latest = values[-1]
    high_idx, high_value = max(enumerate(values), key=lambda item: item[1])
    low_idx, low_value = min(enumerate(values), key=lambda item: item[1])
    return {
        "window_high": high_value,
        "window_high_date": series[high_idx][0],
        "window_low": low_value,
        "window_low_date": series[low_idx][0],
        "current_drawdown_pct": pct(latest / high_value - 1) if high_value else None,
        "distance_from_high_pct": pct(latest / high_value - 1) if high_value else None,
        "rebound_from_low_pct": pct(latest / low_value - 1) if low_value else None,
    }


def series_from_rows(rows: list[dict[str, str]], value_field: str) -> dict[str, list[tuple[str, float]]]:
    if not rows:
        return {}
    grouped: dict[str, list[tuple[str, float]]] = defaultdict(list)
    key_field = "ticker" if "ticker" in rows[0] else "basket"
    for row in rows:
        grouped[row[key_field]].append((row["date"], float(row[value_field])))
    return {key: sorted(values) for key, values in grouped.items()}


def annualization_for_ticker(ticker: str, source_metadata: dict[str, dict[str, str]]) -> int:
    return 365 if source_metadata.get(ticker, {}).get("instrument_type") == "CRYPTOCURRENCY" else 252


def benchmark_metrics(
    returns: dict[str, float], benchmark_returns: dict[str, dict[str, float]]
) -> dict[str, float | None]:
    metrics = {}
    for benchmark in ["SPY", "QQQ", "BTC-USD"]:
        b_returns = benchmark_returns.get(benchmark, {})
        xs, ys = aligned_returns(returns, b_returns)
        metrics[f"beta_vs_{benchmark}"] = beta(xs, ys)
        metrics[f"corr_vs_{benchmark}"] = correlation(xs, ys)
        metrics[f"up_capture_vs_{benchmark}"] = capture_ratio(returns, b_returns, "up")
        metrics[f"down_capture_vs_{benchmark}"] = capture_ratio(returns, b_returns, "down")
    return metrics


def build_ticker_metrics() -> tuple[list[dict], dict[str, list[tuple[str, float]]], dict[str, dict[str, float]]]:
    raw_rows = analysis_window_rows(read_csv("raw_prices.csv"))
    source_metadata = {row["ticker"]: row for row in read_csv("source_metadata.csv")}
    grouped = series_from_rows(raw_rows, "adj_close")
    returns_by_ticker = {ticker: daily_returns(series) for ticker, series in grouped.items()}
    benchmark_returns = {ticker: returns_by_ticker.get(ticker, {}) for ticker in ["SPY", "QQQ", "BTC-USD"]}

    rows = []
    for ticker, series in sorted(grouped.items()):
        values = [value for _, value in series]
        returns = list(returns_by_ticker[ticker].values())
        annualization = annualization_for_ticker(ticker, source_metadata)
        stats = window_stats(series)
        benchmark_stats = benchmark_metrics(returns_by_ticker[ticker], benchmark_returns)
        row = {
            "ticker": ticker,
            "start_date": series[0][0],
            "end_date": series[-1][0],
            "observations": len(series),
            "return_5d_pct": round_or_blank(return_n(values, 5)),
            "return_10d_pct": round_or_blank(return_n(values, 10)),
            "return_20d_pct": round_or_blank(return_n(values, 20)),
            "current_drawdown_pct": round_or_blank(stats.get("current_drawdown_pct")),
            "distance_from_high_pct": round_or_blank(stats.get("distance_from_high_pct")),
            "rebound_from_low_pct": round_or_blank(stats.get("rebound_from_low_pct")),
            "window_high_date": stats.get("window_high_date", ""),
            "window_low_date": stats.get("window_low_date", ""),
            "rolling_vol_10d_pct": round_or_blank(volatility(returns, annualization, 10)),
            "rolling_vol_20d_pct": round_or_blank(volatility(returns, annualization, 20)),
        }
        for key, value in benchmark_stats.items():
            row[key] = round_or_blank(value)
        rows.append(row)
    return rows, grouped, returns_by_ticker


def build_breadth_daily(
    price_series: dict[str, list[tuple[str, float]]],
    normalized_series: dict[str, list[tuple[str, float]]],
) -> list[dict]:
    config = load_market_config()
    rows = []
    for basket in config.baskets:
        available_tickers = [
            holding.ticker for holding in basket.holdings if holding.ticker in normalized_series
        ]
        if not available_tickers:
            continue
        dates = sorted({day for ticker in available_tickers for day, _ in normalized_series[ticker]})
        latest_norm: dict[str, float] = {}
        latest_above_10: dict[str, bool] = {}
        latest_high: dict[str, float] = {}
        rolling_values: dict[str, list[float]] = defaultdict(list)
        series_by_date = {
            ticker: dict(normalized_series[ticker]) for ticker in available_tickers
        }
        first_date_by_ticker = {
            ticker: min(series_by_date[ticker]) for ticker in available_tickers
        }
        minimum_active = min_start_constituents(len(available_tickers))
        for day in dates:
            active_tickers = [
                ticker for ticker in available_tickers if first_date_by_ticker[ticker] <= day
            ]
            if len(active_tickers) < minimum_active:
                continue
            reporting = 0
            for ticker in active_tickers:
                if day not in series_by_date[ticker]:
                    continue
                value = series_by_date[ticker][day]
                reporting += 1
                latest_norm[ticker] = value
                rolling_values[ticker].append(value)
                latest_high[ticker] = max(latest_high.get(ticker, value), value)
                if len(rolling_values[ticker]) >= 10:
                    latest_above_10[ticker] = value > mean(rolling_values[ticker][-10:])
            positive = sum(1 for value in latest_norm.values() if value > 100)
            above_10dma = sum(1 for value in latest_above_10.values() if value)
            at_window_high = sum(
                1
                for ticker, value in latest_norm.items()
                if value >= latest_high.get(ticker, value) * 0.999
            )
            rows.append(
                {
                    "date": day,
                    "basket": basket.id,
                    "positive_since_start_count": positive,
                    "positive_since_start_pct": round(positive / len(active_tickers) * 100, 4),
                    "above_10dma_count": above_10dma,
                    "above_10dma_pct": round(above_10dma / len(active_tickers) * 100, 4),
                    "at_window_high_count": at_window_high,
                    "at_window_high_pct": round(at_window_high / len(active_tickers) * 100, 4),
                    "constituents_reporting": reporting,
                    "constituents_total": len(basket.holdings),
                }
            )
    return rows


def build_basket_metrics(
    ticker_metric_rows: list[dict],
    basket_series: dict[str, list[tuple[str, float]]],
    basket_returns: dict[str, dict[str, float]],
) -> list[dict]:
    config = load_market_config()
    ticker_metrics = {row["ticker"]: row for row in ticker_metric_rows}
    benchmark_returns = {ticker: daily_returns(series) for ticker, series in basket_series.items() if ticker in {"SPY", "QQQ", "BTC-USD"}}
    # Benchmark basket_series usually does not include SPY/QQQ, so fall back to ticker-level returns.
    raw_rows = analysis_window_rows(read_csv("raw_prices.csv"))
    raw_grouped = series_from_rows(raw_rows, "adj_close")
    benchmark_returns = {ticker: daily_returns(raw_grouped[ticker]) for ticker in ["SPY", "QQQ", "BTC-USD"] if ticker in raw_grouped}

    rows = []
    for basket in config.baskets:
        series = basket_series[basket.id]
        values = [value for _, value in series]
        returns = list(basket_returns[basket.id].values())
        stats = window_stats(series)
        benchmark_stats = benchmark_metrics(basket_returns[basket.id], benchmark_returns)

        def constituent_values(key: str) -> list[float]:
            values_out = []
            for holding in basket.holdings:
                value = ticker_metrics.get(holding.ticker, {}).get(key, "")
                if value != "":
                    values_out.append(float(value))
            return values_out

        row = {
            "basket": basket.id,
            "start_date": series[0][0],
            "end_date": series[-1][0],
            "return_5d_pct": round_or_blank(return_n(values, 5)),
            "return_10d_pct": round_or_blank(return_n(values, 10)),
            "return_20d_pct": round_or_blank(return_n(values, 20)),
            "current_drawdown_pct": round_or_blank(stats.get("current_drawdown_pct")),
            "distance_from_high_pct": round_or_blank(stats.get("distance_from_high_pct")),
            "rebound_from_low_pct": round_or_blank(stats.get("rebound_from_low_pct")),
            "window_high_date": stats.get("window_high_date", ""),
            "window_low_date": stats.get("window_low_date", ""),
            "rolling_vol_10d_pct": round_or_blank(volatility(returns, 252, 10)),
            "rolling_vol_20d_pct": round_or_blank(volatility(returns, 252, 20)),
        }
        for key, value in benchmark_stats.items():
            row[key] = round_or_blank(value)
        for key in ["return_5d_pct", "return_10d_pct", "return_20d_pct", "rebound_from_low_pct"]:
            vals = constituent_values(key)
            row[f"median_constituent_{key}"] = round_or_blank(median(vals) if vals else None)
            row[f"positive_constituents_{key}"] = sum(1 for value in vals if value > 0)
        rows.append(row)
    return rows


def main() -> None:
    ticker_rows, price_series, _returns_by_ticker = build_ticker_metrics()
    normalized_series = series_from_rows(read_csv("normalized_prices.csv"), "normalized_value")
    basket_series = series_from_rows(read_csv("basket_daily.csv"), "basket_index")
    basket_returns = {basket: daily_returns(series) for basket, series in basket_series.items()}

    benchmark_fields = []
    for benchmark in ["SPY", "QQQ", "BTC-USD"]:
        benchmark_fields.extend(
            [
                f"beta_vs_{benchmark}",
                f"corr_vs_{benchmark}",
                f"up_capture_vs_{benchmark}",
                f"down_capture_vs_{benchmark}",
            ]
        )
    base_fields = [
        "ticker",
        "start_date",
        "end_date",
        "observations",
        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",
        "current_drawdown_pct",
        "distance_from_high_pct",
        "rebound_from_low_pct",
        "window_high_date",
        "window_low_date",
        "rolling_vol_10d_pct",
        "rolling_vol_20d_pct",
    ]
    write_csv(DATA_DIR / "advanced_price_metrics.csv", base_fields + benchmark_fields, ticker_rows)

    breadth_rows = build_breadth_daily(price_series, normalized_series)
    write_csv(
        DATA_DIR / "basket_breadth_daily.csv",
        [
            "date",
            "basket",
            "positive_since_start_count",
            "positive_since_start_pct",
            "above_10dma_count",
            "above_10dma_pct",
            "at_window_high_count",
            "at_window_high_pct",
            "constituents_reporting",
            "constituents_total",
        ],
        breadth_rows,
    )

    basket_rows = build_basket_metrics(ticker_rows, basket_series, basket_returns)
    basket_fields = [
        "basket",
        "start_date",
        "end_date",
        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",
        "current_drawdown_pct",
        "distance_from_high_pct",
        "rebound_from_low_pct",
        "window_high_date",
        "window_low_date",
        "rolling_vol_10d_pct",
        "rolling_vol_20d_pct",
    ]
    extra_fields = []
    for key in ["return_5d_pct", "return_10d_pct", "return_20d_pct", "rebound_from_low_pct"]:
        extra_fields.extend([f"median_constituent_{key}", f"positive_constituents_{key}"])
    write_csv(DATA_DIR / "basket_advanced_price.csv", basket_fields + benchmark_fields + extra_fields, basket_rows)


if __name__ == "__main__":
    main()
