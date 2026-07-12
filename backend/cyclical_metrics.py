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
RSI_PERIOD = 14
STOCH_RSI_PERIOD = 14
SHORT_MA = 20
LONG_MA = 50
HISTORY_LOOKBACK = 252


def read_csv(name: str) -> list[dict[str, str]]:
    path = DATA_DIR / name
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def number(value: float | None, digits: int = 4) -> float | str:
    if value is None or not math.isfinite(value):
        return ""
    return round(value, digits)


def pct(value: float | None) -> float | str:
    if value is None or not math.isfinite(value):
        return ""
    return round(value * 100, 4)


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def percentile_rank(values: list[float | None], current: float | None) -> float | None:
    if current is None or not math.isfinite(current):
        return None
    xs = sorted(value for value in values if value is not None and math.isfinite(value))
    if not xs:
        return None
    below = sum(1 for value in xs if value < current)
    equal = sum(1 for value in xs if value == current)
    return (below + 0.5 * equal) / len(xs) * 100


def zscore(values: list[float | None], current: float | None) -> float | None:
    if current is None or not math.isfinite(current):
        return None
    xs = [value for value in values if value is not None and math.isfinite(value)]
    if len(xs) < 5:
        return None
    sigma = pstdev(xs)
    if sigma == 0:
        return None
    return (current - mean(xs)) / sigma


def rolling_mean(values: list[float], index: int, periods: int) -> float | None:
    if index + 1 < periods:
        return None
    return mean(values[index + 1 - periods : index + 1])


def rolling_std(values: list[float], index: int, periods: int) -> float | None:
    if index + 1 < periods:
        return None
    window = values[index + 1 - periods : index + 1]
    if len(window) < 2:
        return None
    sigma = pstdev(window)
    return sigma if sigma > 0 else None


def rolling_return(values: list[float], index: int, periods: int) -> float | None:
    if index < periods:
        return None
    base = values[index - periods]
    return values[index] / base - 1 if base else None


def rolling_realized_vol(values: list[float], index: int, periods: int, annualization: int) -> float | None:
    if index < periods:
        return None
    returns = []
    for i in range(index - periods + 1, index + 1):
        prior = values[i - 1]
        if prior:
            returns.append(values[i] / prior - 1)
    if len(returns) < 3:
        return None
    return pstdev(returns) * math.sqrt(annualization) * 100


def rsi_series(values: list[float], period: int = RSI_PERIOD) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return out
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, period + 1):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = mean(gains)
    avg_loss = mean(losses)

    def calc(gain: float, loss: float) -> float:
        if loss == 0:
            return 100.0
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    out[period] = calc(avg_gain, avg_loss)
    for i in range(period + 1, len(values)):
        change = values[i] - values[i - 1]
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        out[i] = calc(avg_gain, avg_loss)
    return out


def stoch_rsi_series(rsis: list[float | None], period: int = STOCH_RSI_PERIOD) -> list[float | None]:
    out: list[float | None] = [None] * len(rsis)
    for i in range(len(rsis)):
        window = [value for value in rsis[max(0, i + 1 - period) : i + 1] if value is not None]
        current = rsis[i]
        if current is None or len(window) < period:
            continue
        low = min(window)
        high = max(window)
        out[i] = 50.0 if high == low else (current - low) / (high - low) * 100
    return out


def price_position(values: list[float], index: int, periods: int) -> float | None:
    if index + 1 < periods:
        return None
    window = values[index + 1 - periods : index + 1]
    low = min(window)
    high = max(window)
    if high == low:
        return 50.0
    return (values[index] - low) / (high - low) * 100


def classify_cycle(heat: float | None, washout: float | None, vol_pctile: float | None) -> str:
    if heat is None and washout is None:
        return "Insufficient history"
    if heat is not None and heat >= 85:
        return "Momentum Extreme"
    if washout is not None and washout >= 85:
        return "Washed Out"
    if vol_pctile is not None and vol_pctile <= 20:
        return "Quiet Compression"
    if vol_pctile is not None and vol_pctile >= 80:
        return "Volatility Expansion"
    if heat is not None and heat >= 65:
        return "Upper Range"
    if washout is not None and washout >= 65:
        return "Lower Range"
    return "Neutral"


def grouped_price_rows() -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv("raw_prices.csv"):
        grouped[row["ticker"]].append(row)
    return {
        ticker: sorted(rows, key=lambda item: item["date"])
        for ticker, rows in grouped.items()
    }


def build_ticker_rows() -> list[dict]:
    config = load_market_config()
    source_metadata = {row["ticker"]: row for row in read_csv("source_metadata.csv")}
    rows_by_ticker = grouped_price_rows()
    output = []
    for ticker, rows in sorted(rows_by_ticker.items()):
        rows = [row for row in rows if row["date"] <= config.end_date.isoformat()]
        if not rows:
            continue
        dates = [row["date"] for row in rows]
        prices = [float(row["adj_close"]) for row in rows]
        volumes = [float(row["volume"] or 0) for row in rows]
        annualization = 365 if source_metadata.get(ticker, {}).get("instrument_type") == "CRYPTOCURRENCY" else 252
        idx = len(prices) - 1
        start = max(0, idx + 1 - HISTORY_LOOKBACK)

        rsis = rsi_series(prices)
        stoch_rsis = stoch_rsi_series(rsis)
        distance_20 = [
            ((prices[i] / ma) - 1) * 100 if (ma := rolling_mean(prices, i, SHORT_MA)) else None
            for i in range(len(prices))
        ]
        distance_50 = [
            ((prices[i] / ma) - 1) * 100 if (ma := rolling_mean(prices, i, LONG_MA)) else None
            for i in range(len(prices))
        ]
        returns_5d = [rolling_return(prices, i, 5) for i in range(len(prices))]
        realized_vol_20 = [rolling_realized_vol(prices, i, 20, annualization) for i in range(len(prices))]
        bollinger_b = []
        for i in range(len(prices)):
            ma = rolling_mean(prices, i, SHORT_MA)
            sigma = rolling_std(prices, i, SHORT_MA)
            if ma is None or sigma is None:
                bollinger_b.append(None)
            else:
                upper = ma + 2 * sigma
                lower = ma - 2 * sigma
                bollinger_b.append(None if upper == lower else (prices[i] - lower) / (upper - lower) * 100)

        volume_mean = rolling_mean(volumes, idx, 20)
        volume_std = rolling_std(volumes, idx, 20)
        volume_z = (volumes[idx] - volume_mean) / volume_std if volume_mean is not None and volume_std else None
        rsi_pctile = percentile_rank(rsis[start:], rsis[idx])
        stoch_pctile = percentile_rank(stoch_rsis[start:], stoch_rsis[idx])
        distance_20_pctile = percentile_rank(distance_20[start:], distance_20[idx])
        distance_50_pctile = percentile_rank(distance_50[start:], distance_50[idx])
        vol_pctile = percentile_rank(realized_vol_20[start:], realized_vol_20[idx])
        bollinger_pctile = percentile_rank(bollinger_b[start:], bollinger_b[idx])
        return_5d_z = zscore(returns_5d[start:], returns_5d[idx])
        distance_20_z = zscore(distance_20[start:], distance_20[idx])
        distance_50_z = zscore(distance_50[start:], distance_50[idx])

        heat_inputs = [
            rsi_pctile,
            stoch_pctile,
            price_position(prices, idx, 50),
            distance_20_pctile,
            bollinger_pctile,
        ]
        heat_values = [value for value in heat_inputs if value is not None]
        heat_score = mean(heat_values) if heat_values else None
        washout_inputs = [
            100 - rsi_pctile if rsi_pctile is not None else None,
            100 - stoch_pctile if stoch_pctile is not None else None,
            100 - price_position(prices, idx, 50) if price_position(prices, idx, 50) is not None else None,
            100 - distance_20_pctile if distance_20_pctile is not None else None,
            100 - bollinger_pctile if bollinger_pctile is not None else None,
        ]
        washout_values = [value for value in washout_inputs if value is not None]
        washout_score = mean(washout_values) if washout_values else None
        percentile_extremes = [
            abs(value - 50) * 2
            for value in [rsi_pctile, stoch_pctile, distance_20_pctile, distance_50_pctile, vol_pctile, bollinger_pctile]
            if value is not None
        ]
        extreme_score = mean(percentile_extremes) if percentile_extremes else None
        output.append(
            {
                "ticker": ticker,
                "as_of_date": dates[idx],
                "history_observations": len(prices),
                "lookback_observations": len([value for value in rsis[start:] if value is not None]),
                "rsi_14": number(rsis[idx]),
                "rsi_14_percentile": number(rsi_pctile),
                "stoch_rsi_14": number(stoch_rsis[idx]),
                "stoch_rsi_14_percentile": number(stoch_pctile),
                "price_position_20d": number(price_position(prices, idx, 20)),
                "price_position_50d": number(price_position(prices, idx, 50)),
                "distance_from_20dma_pct": number(distance_20[idx]),
                "distance_from_20dma_percentile": number(distance_20_pctile),
                "distance_from_20dma_zscore": number(distance_20_z),
                "distance_from_50dma_pct": number(distance_50[idx]),
                "distance_from_50dma_percentile": number(distance_50_pctile),
                "distance_from_50dma_zscore": number(distance_50_z),
                "return_5d_zscore": number(return_5d_z),
                "volume_zscore_20d": number(volume_z),
                "realized_vol_20d_pct": number(realized_vol_20[idx]),
                "realized_vol_20d_percentile": number(vol_pctile),
                "bollinger_percent_b": number(bollinger_b[idx]),
                "bollinger_percent_b_percentile": number(bollinger_pctile),
                "technical_heat_score": number(heat_score),
                "technical_washout_score": number(washout_score),
                "technical_extreme_score": number(extreme_score),
                "cyclical_state": classify_cycle(heat_score, washout_score, vol_pctile),
            }
        )
    return output


def build_basket_rows(ticker_rows: list[dict]) -> list[dict]:
    config = load_market_config()
    by_ticker = {row["ticker"]: row for row in ticker_rows}
    rows = []
    for basket in config.baskets:
        items = [by_ticker[h.ticker] for h in basket.holdings if h.ticker in by_ticker]

        def values(field: str) -> list[float]:
            return [float(row[field]) for row in items if row.get(field) not in {"", None}]

        states: dict[str, int] = {}
        for row in items:
            state = str(row.get("cyclical_state") or "")
            states[state] = states.get(state, 0) + 1
        rows.append(
            {
                "basket": basket.id,
                "cyclical_coverage_count": len(values("technical_extreme_score")),
                "cyclical_coverage_pct": number(len(values("technical_extreme_score")) / len(basket.holdings) * 100 if basket.holdings else None),
                "median_rsi_14_percentile": number(median(values("rsi_14_percentile")) if values("rsi_14_percentile") else None),
                "median_stoch_rsi_14_percentile": number(median(values("stoch_rsi_14_percentile")) if values("stoch_rsi_14_percentile") else None),
                "median_technical_heat_score": number(median(values("technical_heat_score")) if values("technical_heat_score") else None),
                "median_technical_washout_score": number(median(values("technical_washout_score")) if values("technical_washout_score") else None),
                "median_technical_extreme_score": number(median(values("technical_extreme_score")) if values("technical_extreme_score") else None),
                "dominant_cyclical_state": max(states.items(), key=lambda item: item[1])[0] if states else "Insufficient history",
            }
        )
    return rows


def main() -> None:
    ticker_rows = build_ticker_rows()
    write_csv(
        DATA_DIR / "cyclical_technical_metrics.csv",
        [
            "ticker",
            "as_of_date",
            "history_observations",
            "lookback_observations",
            "rsi_14",
            "rsi_14_percentile",
            "stoch_rsi_14",
            "stoch_rsi_14_percentile",
            "price_position_20d",
            "price_position_50d",
            "distance_from_20dma_pct",
            "distance_from_20dma_percentile",
            "distance_from_20dma_zscore",
            "distance_from_50dma_pct",
            "distance_from_50dma_percentile",
            "distance_from_50dma_zscore",
            "return_5d_zscore",
            "volume_zscore_20d",
            "realized_vol_20d_pct",
            "realized_vol_20d_percentile",
            "bollinger_percent_b",
            "bollinger_percent_b_percentile",
            "technical_heat_score",
            "technical_washout_score",
            "technical_extreme_score",
            "cyclical_state",
        ],
        ticker_rows,
    )
    write_csv(
        DATA_DIR / "basket_cyclical_technical.csv",
        [
            "basket",
            "cyclical_coverage_count",
            "cyclical_coverage_pct",
            "median_rsi_14_percentile",
            "median_stoch_rsi_14_percentile",
            "median_technical_heat_score",
            "median_technical_washout_score",
            "median_technical_extreme_score",
            "dominant_cyclical_state",
        ],
        build_basket_rows(ticker_rows),
    )


if __name__ == "__main__":
    main()
