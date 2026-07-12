#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from market_config import load_market_config


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DASHBOARD = ROOT / "market-basket-dashboard.html"
CONFIG = load_market_config()
BASKET_META = CONFIG.basket_meta


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open(newline="") as f:
        return list(csv.DictReader(f))


def read_json(name: str) -> dict:
    path = DATA_DIR / name
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def as_float(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    return float(value) if value != "" else 0.0


def maybe_float(row: dict[str, str], key: str) -> float | None:
    value = row.get(key, "")
    return float(value) if value != "" else None


def as_int(row: dict[str, str], key: str) -> int:
    value = row.get(key, "")
    return int(float(value)) if value != "" else 0


def maybe_int(row: dict[str, str], key: str) -> int | None:
    value = row.get(key, "")
    return int(float(value)) if value != "" else None


def by_key(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row[key]: row for row in rows}


def build_data() -> dict:
    basket_advanced = by_key(read_csv("basket_advanced_price.csv"), "basket")
    basket_fundamentals = by_key(read_csv("basket_fundamentals.csv"), "basket")
    basket_positioning = by_key(read_csv("basket_positioning.csv"), "basket")
    basket_ownership = by_key(read_csv("basket_ownership_positioning.csv"), "basket")
    basket_cyclical = by_key(read_csv("basket_cyclical_technical.csv"), "basket")

    metrics = []
    for row in read_csv("basket_metrics.csv"):
        basket = row["basket"]
        meta = BASKET_META[basket]
        advanced = basket_advanced.get(basket, {})
        fundamentals = basket_fundamentals.get(basket, {})
        positioning = basket_positioning.get(basket, {})
        ownership = basket_ownership.get(basket, {})
        cyclical = basket_cyclical.get(basket, {})
        metrics.append(
            {
                "rank": as_int(row, "rank"),
                "basket": basket,
                "label": meta["label"],
                "short": meta["short"],
                "color": meta["color"],
                "accent": meta["accent"],
                "startDate": row["start_date"],
                "endDate": row["end_date"],
                "constituentsUsed": as_int(row, "constituents_used"),
                "returnPct": as_float(row, "total_return_pct"),
                "annualizedVolPct": as_float(row, "annualized_vol_pct"),
                "maxDrawdownPct": as_float(row, "max_drawdown_pct"),
                "returnVolRatio": as_float(row, "return_vol_ratio"),
                "returnDrawdownRatio": as_float(row, "return_drawdown_ratio"),
                "bestConstituent": row["best_constituent"],
                "bestConstituentReturnPct": as_float(row, "best_constituent_return_pct"),
                "worstConstituent": row["worst_constituent"],
                "worstConstituentReturnPct": as_float(row, "worst_constituent_return_pct"),
                "positiveCount": as_int(row, "participation_positive_count"),
                "positivePct": as_float(row, "participation_positive_pct"),
                "return5dPct": maybe_float(advanced, "return_5d_pct"),
                "return10dPct": maybe_float(advanced, "return_10d_pct"),
                "return20dPct": maybe_float(advanced, "return_20d_pct"),
                "currentDrawdownPct": maybe_float(advanced, "current_drawdown_pct"),
                "distanceFromHighPct": maybe_float(advanced, "distance_from_high_pct"),
                "reboundFromLowPct": maybe_float(advanced, "rebound_from_low_pct"),
                "windowHighDate": advanced.get("window_high_date", ""),
                "windowLowDate": advanced.get("window_low_date", ""),
                "rollingVol10dPct": maybe_float(advanced, "rolling_vol_10d_pct"),
                "rollingVol20dPct": maybe_float(advanced, "rolling_vol_20d_pct"),
                "betaVsSpy": maybe_float(advanced, "beta_vs_SPY"),
                "corrVsSpy": maybe_float(advanced, "corr_vs_SPY"),
                "upCaptureVsSpy": maybe_float(advanced, "up_capture_vs_SPY"),
                "downCaptureVsSpy": maybe_float(advanced, "down_capture_vs_SPY"),
                "betaVsQqq": maybe_float(advanced, "beta_vs_QQQ"),
                "corrVsQqq": maybe_float(advanced, "corr_vs_QQQ"),
                "upCaptureVsQqq": maybe_float(advanced, "up_capture_vs_QQQ"),
                "downCaptureVsQqq": maybe_float(advanced, "down_capture_vs_QQQ"),
                "betaVsBtc": maybe_float(advanced, "beta_vs_BTC-USD"),
                "corrVsBtc": maybe_float(advanced, "corr_vs_BTC-USD"),
                "upCaptureVsBtc": maybe_float(advanced, "up_capture_vs_BTC-USD"),
                "downCaptureVsBtc": maybe_float(advanced, "down_capture_vs_BTC-USD"),
                "positive20dCount": maybe_int(advanced, "positive_constituents_return_20d_pct"),
                "revenueGrowthYoyPct": maybe_float(fundamentals, "median_revenue_growth_yoy_pct"),
                "grossMarginPct": maybe_float(fundamentals, "median_gross_margin_pct"),
                "operatingMarginPct": maybe_float(fundamentals, "median_operating_margin_pct"),
                "netIncomeMarginPct": maybe_float(fundamentals, "median_net_income_margin_pct"),
                "freeCashFlowMarginPct": maybe_float(fundamentals, "median_free_cash_flow_margin_pct"),
                "netCash": maybe_float(fundamentals, "median_net_cash"),
                "fundamentalsCoveragePct": maybe_float(fundamentals, "usable_fundamentals_pct"),
                "shortVolumeRatioPct": maybe_float(positioning, "median_short_volume_ratio_pct"),
                "shortVolume5FileRatioPct": maybe_float(positioning, "median_5file_short_volume_ratio_pct"),
                "putCallOpenInterestRatio": maybe_float(positioning, "median_put_call_open_interest_ratio"),
                "putCallVolumeRatio": maybe_float(positioning, "median_put_call_volume_ratio"),
                "optionsIvPct": maybe_float(positioning, "median_options_iv_pct"),
                "optionsCoveragePct": maybe_float(positioning, "options_coverage_pct"),
                "shortInterestCoveragePct": maybe_float(ownership, "short_interest_coverage_pct"),
                "institutionalCoveragePct": maybe_float(ownership, "institutional_coverage_pct"),
                "shortPctFloat": maybe_float(ownership, "median_short_pct_float"),
                "averageShortPctFloat": maybe_float(ownership, "average_short_pct_float"),
                "daysToCover": maybe_float(ownership, "median_days_to_cover"),
                "institutionalOwnershipPct": maybe_float(ownership, "median_institutional_ownership_pct"),
                "institutionalSharesChangedQoqPct": maybe_float(ownership, "median_institutional_shares_changed_qoq_pct"),
                "institutionalInvestorCount": maybe_float(ownership, "median_institutional_investor_count"),
                "cyclicalCoveragePct": maybe_float(cyclical, "cyclical_coverage_pct"),
                "rsi14Percentile": maybe_float(cyclical, "median_rsi_14_percentile"),
                "stochRsi14Percentile": maybe_float(cyclical, "median_stoch_rsi_14_percentile"),
                "technicalHeatScore": maybe_float(cyclical, "median_technical_heat_score"),
                "technicalWashoutScore": maybe_float(cyclical, "median_technical_washout_score"),
                "technicalExtremeScore": maybe_float(cyclical, "median_technical_extreme_score"),
                "cyclicalState": cyclical.get("dominant_cyclical_state", ""),
            }
        )

    daily: dict[str, list[dict]] = {basket: [] for basket in BASKET_META}
    for row in read_csv("basket_daily.csv"):
        basket = row["basket"]
        if basket not in daily:
            continue
        daily[basket].append(
            {
                "date": row["date"],
                "index": as_float(row, "basket_index"),
                "reporting": as_int(row, "constituents_reporting"),
                "filled": as_int(row, "constituents_filled"),
                "total": as_int(row, "constituents_total"),
            }
        )

    definitions: dict[str, dict[str, dict[str, str]]] = {basket: {} for basket in BASKET_META}
    for row in read_csv("basket_definitions.csv"):
        definitions[row["basket"]][row["ticker"]] = {
            "ticker": row["ticker"],
            "name": row["name"],
            "note": row["note"],
        }

    ticker_series: dict[str, list[dict]] = {}
    for row in read_csv("normalized_prices.csv"):
        ticker_series.setdefault(row["ticker"], []).append(
            {
                "date": row["date"],
                "value": as_float(row, "normalized_value"),
            }
        )

    constituents: dict[str, list[dict]] = {basket: [] for basket in BASKET_META}
    benchmark_tickers = {"SPY", "QQQ", "BTC-USD"}
    benchmarks = {}
    tickers = []
    ticker_advanced = by_key(read_csv("advanced_price_metrics.csv"), "ticker")
    ticker_fundamentals = by_key(read_csv("fundamentals_metrics.csv"), "ticker")
    ticker_short_interest = by_key(read_csv("short_interest_metrics.csv"), "ticker")
    ticker_institutional = by_key(read_csv("institutional_ownership_metrics.csv"), "ticker")
    ticker_options = by_key(read_csv("options_positioning_metrics.csv"), "ticker")
    ticker_short_volume = by_key(read_csv("short_volume_metrics.csv"), "ticker")
    ticker_cyclical = by_key(read_csv("cyclical_technical_metrics.csv"), "ticker")
    for row in read_csv("constituent_metrics.csv"):
        ticker = row["ticker"]
        basket_ids = [basket for basket in row["basket_memberships"].split(";") if basket in BASKET_META]
        advanced = ticker_advanced.get(ticker, {})
        fundamentals = ticker_fundamentals.get(ticker, {})
        short_interest = ticker_short_interest.get(ticker, {})
        institutional = ticker_institutional.get(ticker, {})
        options = ticker_options.get(ticker, {})
        short_volume = ticker_short_volume.get(ticker, {})
        cyclical = ticker_cyclical.get(ticker, {})
        metric = {
            "ticker": ticker,
            "name": row["name"],
            "startDate": row["start_date"],
            "endDate": row["end_date"],
            "startAdjClose": as_float(row, "start_adj_close"),
            "endAdjClose": as_float(row, "end_adj_close"),
            "returnPct": as_float(row, "total_return_pct"),
            "maxDrawdownPct": as_float(row, "max_drawdown_pct"),
            "annualizedVolPct": as_float(row, "annualized_vol_pct"),
            "latestVolume": row["latest_volume"],
            "rowCount": as_int(row, "row_count"),
            "series": ticker_series.get(ticker, []),
            "baskets": [
                {
                    "basket": basket,
                    "label": BASKET_META[basket]["label"],
                    "short": BASKET_META[basket]["short"],
                    "color": BASKET_META[basket]["color"],
                }
                for basket in basket_ids
            ],
            "return5dPct": maybe_float(advanced, "return_5d_pct"),
            "return10dPct": maybe_float(advanced, "return_10d_pct"),
            "return20dPct": maybe_float(advanced, "return_20d_pct"),
            "currentDrawdownPct": maybe_float(advanced, "current_drawdown_pct"),
            "distanceFromHighPct": maybe_float(advanced, "distance_from_high_pct"),
            "reboundFromLowPct": maybe_float(advanced, "rebound_from_low_pct"),
            "windowHighDate": advanced.get("window_high_date", ""),
            "windowLowDate": advanced.get("window_low_date", ""),
            "rollingVol10dPct": maybe_float(advanced, "rolling_vol_10d_pct"),
            "rollingVol20dPct": maybe_float(advanced, "rolling_vol_20d_pct"),
            "betaVsSpy": maybe_float(advanced, "beta_vs_SPY"),
            "corrVsSpy": maybe_float(advanced, "corr_vs_SPY"),
            "upCaptureVsSpy": maybe_float(advanced, "up_capture_vs_SPY"),
            "downCaptureVsSpy": maybe_float(advanced, "down_capture_vs_SPY"),
            "betaVsQqq": maybe_float(advanced, "beta_vs_QQQ"),
            "corrVsQqq": maybe_float(advanced, "corr_vs_QQQ"),
            "upCaptureVsQqq": maybe_float(advanced, "up_capture_vs_QQQ"),
            "downCaptureVsQqq": maybe_float(advanced, "down_capture_vs_QQQ"),
            "betaVsBtc": maybe_float(advanced, "beta_vs_BTC-USD"),
            "corrVsBtc": maybe_float(advanced, "corr_vs_BTC-USD"),
            "revenueGrowthYoyPct": maybe_float(fundamentals, "revenue_growth_yoy_pct"),
            "grossMarginPct": maybe_float(fundamentals, "gross_margin_pct"),
            "operatingMarginPct": maybe_float(fundamentals, "operating_margin_pct"),
            "freeCashFlowMarginPct": maybe_float(fundamentals, "free_cash_flow_margin_pct"),
            "netCash": maybe_float(fundamentals, "net_cash"),
            "fundamentalsStatus": fundamentals.get("coverage_status", ""),
            "fundamentalsAsOfDate": fundamentals.get("as_of_date", ""),
            "shortPctFloat": maybe_float(short_interest, "short_pct_float"),
            "sharesShort": maybe_float(short_interest, "shares_short"),
            "daysToCover": maybe_float(short_interest, "days_to_cover"),
            "shortInterestChangePct": maybe_float(short_interest, "short_interest_change_pct"),
            "shortInterestStatus": short_interest.get("coverage_status", ""),
            "institutionalOwnershipPct": maybe_float(institutional, "institutional_ownership_pct"),
            "institutionalSharesChangedQoqPct": maybe_float(institutional, "institutional_shares_changed_qoq_pct"),
            "institutionalInvestorCount": maybe_float(institutional, "institutional_investor_count"),
            "institutionalAsOfDate": institutional.get("as_of_date", ""),
            "institutionalStatus": institutional.get("coverage_status", ""),
            "shortVolumeRatioPct": maybe_float(short_volume, "short_volume_ratio_pct"),
            "shortVolume5FileRatioPct": maybe_float(short_volume, "avg_5file_short_volume_ratio_pct"),
            "shortVolumeAsOfDate": short_volume.get("as_of_date", ""),
            "putCallOpenInterestRatio": maybe_float(options, "put_call_open_interest_ratio"),
            "putCallVolumeRatio": maybe_float(options, "put_call_volume_ratio"),
            "optionsIvPct": maybe_float(options, "median_iv_pct"),
            "optionsAsOfTimestamp": options.get("as_of_timestamp", ""),
            "optionsStatus": options.get("coverage_status", ""),
            "cyclicalAsOfDate": cyclical.get("as_of_date", ""),
            "cyclicalLookbackCount": maybe_int(cyclical, "lookback_observations"),
            "rsi14": maybe_float(cyclical, "rsi_14"),
            "rsi14Percentile": maybe_float(cyclical, "rsi_14_percentile"),
            "stochRsi14": maybe_float(cyclical, "stoch_rsi_14"),
            "stochRsi14Percentile": maybe_float(cyclical, "stoch_rsi_14_percentile"),
            "pricePosition20d": maybe_float(cyclical, "price_position_20d"),
            "pricePosition50d": maybe_float(cyclical, "price_position_50d"),
            "distanceFrom20dmaPct": maybe_float(cyclical, "distance_from_20dma_pct"),
            "distanceFrom20dmaPercentile": maybe_float(cyclical, "distance_from_20dma_percentile"),
            "distanceFrom20dmaZscore": maybe_float(cyclical, "distance_from_20dma_zscore"),
            "distanceFrom50dmaPct": maybe_float(cyclical, "distance_from_50dma_pct"),
            "distanceFrom50dmaPercentile": maybe_float(cyclical, "distance_from_50dma_percentile"),
            "distanceFrom50dmaZscore": maybe_float(cyclical, "distance_from_50dma_zscore"),
            "return5dZscore": maybe_float(cyclical, "return_5d_zscore"),
            "volumeZscore20d": maybe_float(cyclical, "volume_zscore_20d"),
            "realizedVol20dPct": maybe_float(cyclical, "realized_vol_20d_pct"),
            "realizedVol20dPercentile": maybe_float(cyclical, "realized_vol_20d_percentile"),
            "bollingerPercentB": maybe_float(cyclical, "bollinger_percent_b"),
            "bollingerPercentBPercentile": maybe_float(cyclical, "bollinger_percent_b_percentile"),
            "technicalHeatScore": maybe_float(cyclical, "technical_heat_score"),
            "technicalWashoutScore": maybe_float(cyclical, "technical_washout_score"),
            "technicalExtremeScore": maybe_float(cyclical, "technical_extreme_score"),
            "cyclicalState": cyclical.get("cyclical_state", ""),
        }
        if ticker in benchmark_tickers:
            benchmarks[ticker] = metric
        elif basket_ids:
            tickers.append(metric)
        for basket in row["basket_memberships"].split(";"):
            if basket in constituents:
                item = dict(metric)
                item["note"] = definitions.get(basket, {}).get(ticker, {}).get("note", "")
                constituents[basket].append(item)

    for items in constituents.values():
        items.sort(key=lambda item: item["returnPct"], reverse=True)

    basket_metric_by_id = {item["basket"]: item for item in metrics}
    attribution = {}
    for basket, items in constituents.items():
        divisor = basket_metric_by_id.get(basket, {}).get("constituentsUsed") or len(items) or 1
        attribution[basket] = sorted(
            [
                {
                    "ticker": item["ticker"],
                    "name": item["name"],
                    "returnPct": item["returnPct"],
                    "contributionPct": item["returnPct"] / divisor,
                    "return20dPct": item.get("return20dPct"),
                    "currentDrawdownPct": item.get("currentDrawdownPct"),
                    "reboundFromLowPct": item.get("reboundFromLowPct"),
                    "shortPctFloat": item.get("shortPctFloat"),
                    "institutionalSharesChangedQoqPct": item.get("institutionalSharesChangedQoqPct"),
                    "freeCashFlowMarginPct": item.get("freeCashFlowMarginPct"),
                }
                for item in items
            ],
            key=lambda item: item["contributionPct"],
            reverse=True,
        )

    return {
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "methodology": {
            "startDate": CONFIG.start_date.isoformat(),
            "endDate": CONFIG.end_date.isoformat(),
            "source": CONFIG.source,
            "weighting": CONFIG.weighting,
            "priceField": CONFIG.price_field,
            "dataStatus": CONFIG.data_status,
        },
        "metrics": metrics,
        "daily": daily,
        "constituents": constituents,
        "tickers": tickers,
        "attribution": attribution,
        "benchmarks": benchmarks,
        "alpacaMarketStatus": read_json("alpaca_market_status.json"),
        "symbolNotes": CONFIG.symbol_decisions,
    }


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Market Basket Performance Dashboard</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #080807;
      --bg-2: #10100d;
      --panel: #151513;
      --panel-2: #1b1b17;
      --panel-3: #23231d;
      --line: rgb(226 236 255 / 0.12);
      --line-strong: rgb(226 236 255 / 0.24);
      --text: #f2f0e8;
      --muted: #a9aaa0;
      --faint: #747467;
      --good: #4bd6b8;
      --bad: #ef6c86;
      --warn: #f2c95d;
      --hot: #ff8f5f;
      --blue: #6bb7ff;
      --shadow: 0 22px 60px rgb(0 0 0 / 0.34);
      --radius: 8px;
      --mono: "SFMono-Regular", "Roboto Mono", ui-monospace, Menlo, Consolas, monospace;
      --sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }

    html { background: var(--bg); }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: var(--sans);
      background:
        linear-gradient(180deg, rgb(19 19 16 / 0.98), rgb(8 8 7 / 1) 58rem),
        repeating-linear-gradient(90deg, rgb(255 255 255 / 0.026) 0 1px, transparent 1px 84px),
        repeating-linear-gradient(0deg, rgb(255 255 255 / 0.018) 0 1px, transparent 1px 84px);
      color: var(--text);
      font-variant-numeric: tabular-nums;
    }

    button, input {
      font: inherit;
    }

    button {
      color: inherit;
    }

    .app {
      width: min(1480px, calc(100% - 32px));
      margin: 0 auto;
      padding: 28px 0 44px;
    }

    .topbar {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 24px;
      align-items: start;
      padding: 14px 0 28px;
      border-bottom: 1px solid var(--line);
    }

    .eyebrow {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
    }

    .chip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 28px;
      padding: 6px 9px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgb(255 255 255 / 0.035);
      color: var(--muted);
      font-size: 0.75rem;
      font-weight: 700;
      letter-spacing: 0;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .chip strong {
      color: var(--text);
      font-weight: 800;
    }

    h1 {
      margin: 0;
      max-width: 900px;
      font-size: 2.8rem;
      line-height: 1.02;
      letter-spacing: 0;
      font-weight: 900;
    }

    .lede {
      max-width: 820px;
      margin: 14px 0 0;
      color: #b9c5cf;
      font-size: 1rem;
      line-height: 1.55;
    }

    .data-status {
      width: 320px;
      padding: 16px;
      border: 1px solid rgb(242 201 93 / 0.24);
      border-radius: var(--radius);
      background: linear-gradient(180deg, rgb(242 201 93 / 0.11), rgb(242 201 93 / 0.035));
      box-shadow: var(--shadow);
    }

    .status-label {
      color: var(--warn);
      font-size: 0.72rem;
      font-weight: 900;
      text-transform: uppercase;
    }

    .status-copy {
      margin-top: 8px;
      color: #d8d3bd;
      font-size: 0.86rem;
      line-height: 1.45;
    }

    .metric-strip {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin: 20px 0 22px;
    }

    .kpi {
      min-height: 126px;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: linear-gradient(180deg, rgb(255 255 255 / 0.06), rgb(255 255 255 / 0.025));
      box-shadow: 0 18px 40px rgb(0 0 0 / 0.18);
    }

    .kpi .label {
      color: var(--muted);
      font-size: 0.76rem;
      font-weight: 800;
      text-transform: uppercase;
    }

    .kpi .value {
      margin-top: 12px;
      font-size: 2rem;
      line-height: 1;
      font-weight: 900;
    }

    .kpi .sub {
      margin-top: 10px;
      color: var(--muted);
      font-size: 0.84rem;
      line-height: 1.4;
    }

    .layout {
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(360px, 0.8fr);
      gap: 14px;
      align-items: start;
    }

    .panel {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: linear-gradient(180deg, rgb(255 255 255 / 0.055), rgb(255 255 255 / 0.022));
      box-shadow: 0 18px 40px rgb(0 0 0 / 0.19);
      overflow: hidden;
      container-type: inline-size;
    }

    .panel-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      min-height: 64px;
      padding: 16px 18px;
      border-bottom: 1px solid var(--line);
    }

    .panel-title {
      margin: 0;
      font-size: 0.92rem;
      font-weight: 900;
      letter-spacing: 0;
    }

    .panel-note {
      margin-top: 4px;
      color: var(--muted);
      font-size: 0.78rem;
      line-height: 1.35;
    }

    .panel-body {
      padding: 14px;
    }

    .panel-body.flush {
      padding: 0;
    }

    .grid-2 {
      display: grid;
      grid-template-columns: minmax(0, 1.06fr) minmax(320px, 0.94fr);
      gap: 14px;
    }

    .full {
      grid-column: 1 / -1;
    }

    .chart {
      min-height: 0;
    }

    .chart svg {
      display: block;
      width: 100%;
      height: auto;
    }

    .axis text,
    .svg-label {
      fill: var(--muted);
      font-size: 11px;
      font-weight: 700;
    }

    .axis-line,
    .grid-line {
      stroke: rgb(230 238 255 / 0.12);
      shape-rendering: crispEdges;
    }

    .zero-line {
      stroke: rgb(230 238 255 / 0.35);
      stroke-width: 1.2;
    }

    .bar-row,
    .bubble,
    .line-hit,
    .sector-row,
    .breadth-row {
      cursor: pointer;
    }

    .bar-row:hover rect,
    .sector-row:hover,
    .breadth-row:hover,
    .score-row:hover {
      filter: brightness(1.13);
    }

    .controls {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 4px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgb(0 0 0 / 0.18);
    }

    .control-btn {
      min-height: 30px;
      padding: 6px 10px;
      border: 0;
      border-radius: 999px;
      background: transparent;
      color: var(--muted);
      font-size: 0.76rem;
      font-weight: 800;
      cursor: pointer;
      white-space: nowrap;
    }

    .control-btn[aria-pressed="true"] {
      background: rgb(255 255 255 / 0.12);
      color: var(--text);
    }

    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      padding: 0 14px 14px;
    }

    .legend button {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      min-height: 28px;
      padding: 5px 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgb(255 255 255 / 0.035);
      color: var(--muted);
      font-size: 0.74rem;
      font-weight: 800;
      cursor: pointer;
    }

    .legend button.active {
      color: var(--text);
      border-color: rgb(255 255 255 / 0.28);
      background: rgb(255 255 255 / 0.09);
    }

    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: currentColor;
      flex: 0 0 auto;
    }

    .detail {
      position: sticky;
      top: 12px;
      max-height: calc(100vh - 24px);
      overflow-y: auto;
    }

    .detail-hero {
      padding: 18px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, rgb(255 255 255 / 0.06), rgb(255 255 255 / 0.02));
    }

    .detail-name {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
    }

    .detail-name h2 {
      margin: 0;
      font-size: 1.4rem;
      line-height: 1.1;
      letter-spacing: 0;
    }

    .rank-pill {
      min-width: 48px;
      padding: 7px 9px;
      border-radius: 999px;
      border: 1px solid var(--line);
      text-align: center;
      color: var(--muted);
      font-size: 0.74rem;
      font-weight: 900;
      white-space: nowrap;
    }

    .detail-return {
      margin-top: 20px;
      font-size: 2.55rem;
      line-height: 1;
      font-weight: 950;
      letter-spacing: 0;
    }

    .mini-stats {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      margin-top: 16px;
    }

    .mini-stat {
      min-height: 74px;
      padding: 11px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: rgb(0 0 0 / 0.14);
    }

    .mini-stat span {
      display: block;
      color: var(--muted);
      font-size: 0.7rem;
      font-weight: 800;
      text-transform: uppercase;
    }

    .mini-stat strong {
      display: block;
      margin-top: 8px;
      font-size: 1.02rem;
    }

    .detail-thesis {
      margin-top: 14px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: rgb(0 0 0 / 0.16);
      color: #d5d0c0;
      font-size: 0.82rem;
      line-height: 1.45;
    }

    .profile-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      padding: 12px;
      border-bottom: 1px solid var(--line);
    }

    .profile-card {
      min-height: 82px;
      padding: 11px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: rgb(255 255 255 / 0.028);
    }

    .profile-card span {
      display: block;
      color: var(--muted);
      font-size: 0.68rem;
      font-weight: 850;
      text-transform: uppercase;
    }

    .profile-card strong {
      display: block;
      margin-top: 8px;
      font-size: 1rem;
    }

    .profile-card small {
      display: block;
      margin-top: 5px;
      color: var(--faint);
      font-size: 0.7rem;
      line-height: 1.25;
    }

    .detail-tabs {
      display: flex;
      gap: 4px;
      padding: 12px 12px 0;
      overflow-x: auto;
    }

    .detail-tabs button {
      min-height: 30px;
      padding: 6px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgb(255 255 255 / 0.035);
      color: var(--muted);
      font-size: 0.72rem;
      font-weight: 850;
      cursor: pointer;
      white-space: nowrap;
    }

    .detail-tabs button[aria-pressed="true"] {
      color: var(--text);
      border-color: rgb(255 255 255 / 0.28);
      background: rgb(255 255 255 / 0.12);
    }

    .table-wrap {
      overflow-x: auto;
    }

    table {
      width: 100%;
      border-collapse: collapse;
    }

    th, td {
      padding: 10px 10px;
      border-bottom: 1px solid rgb(226 236 255 / 0.08);
      text-align: left;
      vertical-align: middle;
      white-space: nowrap;
    }

    th {
      color: var(--muted);
      font-size: 0.68rem;
      text-transform: uppercase;
      font-weight: 900;
    }

    td {
      color: #dce6ee;
      font-size: 0.78rem;
    }

    .ticker {
      color: var(--text);
      font-weight: 900;
    }

    .muted {
      color: var(--muted);
    }

    .pos { color: var(--good); }
    .neg { color: var(--bad); }
    .warn { color: var(--warn); }

    .sector-list {
      display: grid;
      gap: 8px;
      padding: 12px;
    }

    .sector-row {
      display: grid;
      grid-template-columns: 28px minmax(0, 1fr) 78px 78px 78px;
      align-items: center;
      gap: 10px;
      min-height: 56px;
      padding: 9px 10px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: rgb(255 255 255 / 0.028);
    }

    .sector-row.active {
      border-color: rgb(255 255 255 / 0.34);
      background: rgb(255 255 255 / 0.07);
    }

    .rank {
      color: var(--faint);
      font-family: var(--mono);
      font-size: 0.76rem;
      font-weight: 800;
    }

    .sector-title {
      min-width: 0;
      font-weight: 900;
      overflow-wrap: anywhere;
    }

    .sector-sub {
      margin-top: 3px;
      color: var(--muted);
      font-size: 0.72rem;
    }

    .value-cell {
      text-align: right;
      font-family: var(--mono);
      font-size: 0.82rem;
      font-weight: 900;
    }

    .score-board {
      display: grid;
      gap: 9px;
      padding: 12px;
    }

    .score-row {
      display: grid;
      grid-template-columns: 32px minmax(150px, 1fr) minmax(150px, 0.9fr) 74px 74px 74px;
      align-items: center;
      gap: 10px;
      min-height: 58px;
      padding: 9px 10px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: rgb(255 255 255 / 0.028);
      cursor: pointer;
    }

    .score-row.active {
      border-color: rgb(255 255 255 / 0.34);
      background: rgb(255 255 255 / 0.075);
    }

    .score-track {
      position: relative;
      height: 10px;
      border-radius: 999px;
      background: rgb(255 255 255 / 0.09);
      overflow: hidden;
    }

    .score-bar {
      position: absolute;
      inset: 0 auto 0 0;
      width: var(--score);
      border-radius: inherit;
      background: linear-gradient(90deg, var(--good), var(--warn), var(--hot));
    }

    .score-label {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 6px;
      color: var(--muted);
      font-size: 0.7rem;
      font-weight: 850;
      text-transform: uppercase;
    }

    .heatmap {
      overflow-x: auto;
    }

    .heat-row {
      display: grid;
      grid-template-columns: 150px repeat(8, minmax(82px, 1fr));
      min-width: 860px;
      border-bottom: 1px solid rgb(226 236 255 / 0.08);
    }

    .heat-row.header {
      position: sticky;
      top: 0;
      z-index: 1;
      background: rgb(15 15 13 / 0.98);
    }

    .heat-cell {
      min-height: 44px;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      padding: 8px 9px;
      border-right: 1px solid rgb(226 236 255 / 0.07);
      color: #f6f1e4;
      font-family: var(--mono);
      font-size: 0.76rem;
      font-weight: 850;
      white-space: nowrap;
    }

    .heat-cell:first-child {
      justify-content: flex-start;
      color: var(--text);
      font-family: var(--sans);
      font-size: 0.78rem;
      font-weight: 900;
    }

    .heat-row.header .heat-cell {
      min-height: 38px;
      color: var(--muted);
      background: rgb(255 255 255 / 0.032);
      font-family: var(--sans);
      font-size: 0.66rem;
      text-transform: uppercase;
    }

    .coverage-badge {
      display: inline-flex;
      min-height: 22px;
      align-items: center;
      padding: 3px 7px;
      border-radius: 999px;
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 0.68rem;
      font-weight: 850;
      white-space: nowrap;
    }

    .explorer-toolbar {
      display: grid;
      grid-template-columns: minmax(220px, 0.9fr) minmax(0, 1.4fr);
      gap: 10px;
      align-items: center;
      padding: 12px;
      border-bottom: 1px solid var(--line);
      background: rgb(0 0 0 / 0.12);
    }

    .search-input {
      width: 100%;
      min-height: 38px;
      padding: 8px 11px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgb(0 0 0 / 0.2);
      color: var(--text);
      outline: none;
    }

    .search-input:focus {
      border-color: var(--line-strong);
      box-shadow: 0 0 0 3px rgb(107 183 255 / 0.12);
    }

    .toolbar-group {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      justify-content: flex-end;
    }

    .ticker-table-wrap {
      max-height: 560px;
      overflow: auto;
    }

    .ticker-table {
      min-width: 1180px;
    }

    .ticker-table thead {
      position: sticky;
      top: 0;
      z-index: 2;
      background: rgb(16 16 14 / 0.98);
    }

    .ticker-row {
      cursor: pointer;
    }

    .ticker-row.active,
    .ticker-row:hover {
      background: rgb(255 255 255 / 0.045);
    }

    .ticker-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
      margin-top: 5px;
    }

    .ticker-tag {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      min-height: 20px;
      padding: 3px 6px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      font-size: 0.66rem;
      font-weight: 850;
    }

    .attribution-list {
      display: grid;
      gap: 8px;
      padding: 12px;
    }

    .attribution-row {
      display: grid;
      grid-template-columns: 86px minmax(150px, 1fr) minmax(170px, 1.1fr) 76px 76px;
      align-items: center;
      gap: 10px;
      min-height: 50px;
      padding: 8px 9px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: rgb(255 255 255 / 0.028);
      cursor: pointer;
    }

    .attribution-row.active,
    .attribution-row:hover {
      border-color: var(--line-strong);
      background: rgb(255 255 255 / 0.06);
    }

    .bar-track {
      height: 10px;
      border-radius: 999px;
      background: rgb(255 255 255 / 0.08);
      overflow: hidden;
    }

    .bar-fill {
      height: 100%;
      width: var(--bar);
      border-radius: inherit;
      background: var(--bar-color, var(--good));
    }

    .ticker-profile {
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.9fr);
      gap: 0;
    }

    .ticker-profile-main {
      padding: 16px;
      border-right: 1px solid var(--line);
    }

    .ticker-profile-side {
      padding: 12px;
    }

    .ticker-title {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 10px;
      margin-bottom: 12px;
    }

    .ticker-title h2 {
      margin: 0;
      font-size: 1.45rem;
      line-height: 1.1;
    }

    .profile-metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
      margin: 12px 0;
    }

    .profile-metric {
      min-height: 74px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: rgb(255 255 255 / 0.028);
    }

    .profile-metric span {
      display: block;
      color: var(--muted);
      font-size: 0.68rem;
      font-weight: 850;
      text-transform: uppercase;
    }

    .profile-metric strong {
      display: block;
      margin-top: 8px;
      font-size: 1rem;
    }

    .profile-chart {
      min-height: 260px;
    }

    .profile-note {
      margin-top: 10px;
      color: var(--muted);
      font-size: 0.78rem;
      line-height: 1.4;
    }

    .breadth {
      display: grid;
      gap: 8px;
      padding: 12px;
    }

    .breadth-row {
      display: grid;
      grid-template-columns: minmax(110px, 1fr) auto 54px;
      align-items: center;
      gap: 10px;
      min-height: 42px;
      padding: 8px 9px;
      border-radius: var(--radius);
      border: 1px solid transparent;
    }

    .breadth-row.active {
      border-color: var(--line-strong);
      background: rgb(255 255 255 / 0.045);
    }

    .breadth-dots {
      display: grid;
      grid-template-columns: repeat(8, 9px);
      gap: 5px;
    }

    .breadth-dots i {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: rgb(255 255 255 / 0.13);
    }

    .breadth-dots i.on {
      background: var(--good);
      box-shadow: 0 0 14px rgb(75 214 184 / 0.24);
    }

    .notes {
      display: grid;
      gap: 8px;
      padding: 14px;
    }

    .note {
      padding: 10px 12px;
      border-left: 2px solid var(--warn);
      background: rgb(242 201 93 / 0.055);
      color: #d3d0c1;
      font-size: 0.78rem;
      line-height: 1.42;
    }

    .spark {
      width: 82px;
      height: 28px;
    }

    .tooltip {
      position: fixed;
      z-index: 20;
      max-width: 280px;
      padding: 9px 10px;
      border: 1px solid var(--line-strong);
      border-radius: var(--radius);
      background: rgb(9 12 16 / 0.96);
      box-shadow: var(--shadow);
      color: var(--text);
      font-size: 0.76rem;
      line-height: 1.35;
      pointer-events: none;
      opacity: 0;
      transform: translate(-999px, -999px);
      transition: opacity 120ms ease;
    }

    .tooltip.show {
      opacity: 1;
    }

    @container (max-width: 620px) {
      .panel-header {
        display: grid;
        align-items: start;
      }
    }

    @media (max-width: 1160px) {
      .layout,
      .grid-2,
      .ticker-profile {
        grid-template-columns: 1fr;
      }

      .detail {
        position: static;
      }

      .data-status {
        width: auto;
      }
    }

    @media (max-width: 860px) {
      .app {
        width: min(100% - 20px, 760px);
        padding-top: 16px;
      }

      .topbar,
      .metric-strip,
      .explorer-toolbar {
        grid-template-columns: 1fr;
      }

      .toolbar-group {
        justify-content: flex-start;
      }

      h1 {
        font-size: 2.05rem;
      }

      .sector-row {
        grid-template-columns: 24px minmax(0, 1fr) 72px;
      }

      .sector-row .value-cell:nth-last-child(-n+2) {
        display: none;
      }

      .score-row {
        grid-template-columns: 24px minmax(0, 1fr);
      }

      .score-row > div:nth-child(n+3) {
        display: none;
      }

      .attribution-row {
        grid-template-columns: 72px minmax(0, 1fr) 74px;
      }

      .attribution-row > div:nth-child(3),
      .attribution-row > div:nth-child(5) {
        display: none;
      }

      .mini-stats,
      .profile-grid,
      .profile-metrics {
        grid-template-columns: 1fr;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        scroll-behavior: auto !important;
        transition-duration: 0.01ms !important;
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
      }
    }
  </style>
</head>
<body>
  <main class="app">
    <header class="topbar">
      <div>
        <div class="eyebrow">
          <span class="chip"><strong>Window</strong> <span id="window-chip"></span></span>
          <span class="chip"><strong>Method</strong> Equal-weighted</span>
          <span class="chip"><strong>Scale</strong> Indexed to 100</span>
        </div>
        <h1>Market basket performance since early March</h1>
        <p class="lede">A finance-grade view of twelve sector baskets, normalized to the same starting line so leadership, volatility, drawdown, and breadth are visible without mixing stories.</p>
      </div>
      <aside class="data-status">
        <div class="status-label">Data status</div>
        <div class="status-copy" id="data-status"></div>
      </aside>
    </header>

    <section class="metric-strip" id="metric-strip" aria-label="Summary metrics"></section>

    <section class="layout">
      <div class="grid-2">
        <article class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Return leaderboard</h2>
              <div class="panel-note">Total basket return. Benchmark markers use SPY, QQQ, and BTC.</div>
            </div>
          </div>
          <div class="panel-body chart" id="leaderboard-chart"></div>
        </article>

        <article class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Risk / return map</h2>
              <div class="panel-note">Higher is better; farther right means more annualized volatility.</div>
            </div>
          </div>
          <div class="panel-body chart" id="scatter-chart"></div>
        </article>

        <article class="panel full">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">$100 invested in each basket</h2>
              <div class="panel-note">Indexed basket path from March 2 with the selected sector emphasized.</div>
            </div>
            <div class="controls" aria-label="Performance chart view">
              <button class="control-btn" data-view="leaders" aria-pressed="true">Leaders</button>
              <button class="control-btn" data-view="all" aria-pressed="false">All</button>
            </div>
          </div>
          <div class="panel-body chart" id="performance-chart"></div>
          <div class="legend" id="line-legend"></div>
        </article>

        <article class="panel full">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Leadership and setup score</h2>
              <div class="panel-note">Composite of momentum, rebound, squeeze pressure, institutional sponsorship, and fundamentals.</div>
            </div>
            <div class="controls" aria-label="Signal score sort">
              <button class="control-btn" data-signal="opportunityScore" aria-pressed="true">Composite</button>
              <button class="control-btn" data-signal="squeezeScore" aria-pressed="false">Squeeze</button>
              <button class="control-btn" data-signal="sponsorScore" aria-pressed="false">Sponsors</button>
              <button class="control-btn" data-signal="fundamentalScore" aria-pressed="false">Fundamentals</button>
            </div>
          </div>
          <div class="score-board" id="signal-board"></div>
        </article>

        <article class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Short interest vs institutional bid</h2>
              <div class="panel-note">True short interest against quarterly institutional share change; bubble size is 20-day return.</div>
            </div>
          </div>
          <div class="panel-body chart" id="ownership-chart"></div>
        </article>

        <article class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Fundamental quality map</h2>
              <div class="panel-note">Revenue growth versus free-cash-flow margin, colored by sector and sized by total return.</div>
            </div>
          </div>
          <div class="panel-body chart" id="fundamentals-chart"></div>
        </article>

        <article class="panel full">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Cross-asset factor heatmap</h2>
              <div class="panel-note">Price, risk, positioning, institutional sponsorship, and fundamentals in one scan.</div>
            </div>
          </div>
          <div class="panel-body flush heatmap" id="factor-heatmap"></div>
        </article>

        <article class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Drawdown discipline</h2>
              <div class="panel-note">Worst peak-to-trough decline during the window.</div>
            </div>
          </div>
          <div class="panel-body chart" id="drawdown-chart"></div>
        </article>

        <article class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Breadth</h2>
              <div class="panel-note">Positive constituents out of eight.</div>
            </div>
          </div>
          <div class="breadth" id="breadth-panel"></div>
        </article>

        <article class="panel full">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Basket table</h2>
              <div class="panel-note">Sort to compare return, risk-adjusted quality, volatility, drawdown, or participation.</div>
            </div>
            <div class="controls" aria-label="Sort sectors">
              <button class="control-btn" data-sort="returnPct" aria-pressed="true">Return</button>
              <button class="control-btn" data-sort="returnVolRatio" aria-pressed="false">Quality</button>
              <button class="control-btn" data-sort="annualizedVolPct" aria-pressed="false">Vol</button>
              <button class="control-btn" data-sort="maxDrawdownPct" aria-pressed="false">Drawdown</button>
              <button class="control-btn" data-sort="positivePct" aria-pressed="false">Breadth</button>
              <button class="control-btn" data-sort="shortPctFloat" aria-pressed="false">Short %</button>
            </div>
          </div>
          <div class="sector-list" id="sector-list"></div>
        </article>

        <article class="panel full">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Selected basket attribution</h2>
              <div class="panel-note">Equal-weight return contribution by ticker for the selected sector.</div>
            </div>
          </div>
          <div class="attribution-list" id="basket-attribution"></div>
        </article>

        <article class="panel full">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Global ticker explorer</h2>
              <div class="panel-note">Search, screen, sort, and click through every configured constituent.</div>
            </div>
          </div>
          <div class="explorer-toolbar">
            <input class="search-input" id="ticker-search" type="search" placeholder="Search ticker or company" aria-label="Search tickers">
            <div class="toolbar-group" aria-label="Ticker setup filters">
              <button class="control-btn" data-ticker-filter="all" aria-pressed="true">All</button>
              <button class="control-btn" data-ticker-filter="selected" aria-pressed="false">Selected sector</button>
              <button class="control-btn" data-ticker-filter="momentum" aria-pressed="false">Momentum</button>
              <button class="control-btn" data-ticker-filter="squeeze" aria-pressed="false">Squeeze</button>
              <button class="control-btn" data-ticker-filter="institutional" aria-pressed="false">Inst bid</button>
              <button class="control-btn" data-ticker-filter="quality" aria-pressed="false">Quality</button>
              <button class="control-btn" data-ticker-filter="rebound" aria-pressed="false">Rebound</button>
              <button class="control-btn" data-ticker-filter="risk" aria-pressed="false">High risk</button>
            </div>
            <div></div>
            <div class="toolbar-group" aria-label="Ticker sort controls">
              <button class="control-btn" data-ticker-sort="returnPct" aria-pressed="true">Return</button>
              <button class="control-btn" data-ticker-sort="return20dPct" aria-pressed="false">20D</button>
              <button class="control-btn" data-ticker-sort="currentDrawdownPct" aria-pressed="false">Drawdown</button>
              <button class="control-btn" data-ticker-sort="reboundFromLowPct" aria-pressed="false">Rebound</button>
              <button class="control-btn" data-ticker-sort="shortPctFloat" aria-pressed="false">Short %</button>
              <button class="control-btn" data-ticker-sort="optionsIvPct" aria-pressed="false">IV</button>
              <button class="control-btn" data-ticker-sort="institutionalSharesChangedQoqPct" aria-pressed="false">Inst QoQ</button>
              <button class="control-btn" data-ticker-sort="freeCashFlowMarginPct" aria-pressed="false">FCF</button>
            </div>
          </div>
          <div class="ticker-table-wrap" id="ticker-explorer"></div>
        </article>

        <article class="panel full">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Ticker profile</h2>
              <div class="panel-note">Selected ticker versus its basket path, with price, positioning, ownership, and fundamentals.</div>
            </div>
          </div>
          <div id="ticker-profile"></div>
        </article>
      </div>

      <aside class="panel detail" aria-label="Selected basket detail">
        <div id="detail-panel"></div>
      </aside>
    </section>
  </main>

  <div class="tooltip" id="tooltip" role="tooltip"></div>

  <script type="application/json" id="dashboard-data">__DATA__</script>
  <script>
    const DATA = JSON.parse(document.getElementById("dashboard-data").textContent);
    const metrics = DATA.metrics.slice().sort((a, b) => a.rank - b.rank);
    const byBasket = new Map(metrics.map((item) => [item.basket, item]));
    const tickers = DATA.tickers.slice().sort((a, b) => b.returnPct - a.returnPct);
    const byTicker = new Map(tickers.map((item) => [item.ticker, item]));
    const tooltip = document.getElementById("tooltip");
    let selectedBasket = metrics[0].basket;
    let selectedTicker = (DATA.constituents[selectedBasket] || [])[0]?.ticker || tickers[0]?.ticker;
    let lineView = "leaders";
    let sortKey = "returnPct";
    let signalSort = "opportunityScore";
    let detailView = "positioning";
    let tickerFilter = "all";
    let tickerSort = "returnPct";
    let tickerSearch = "";

    const isNum = (value) => Number.isFinite(value);
    const fmtPct = (value, digits = 1) => `${value >= 0 ? "+" : ""}${value.toFixed(digits)}%`;
    const fmtPlainPct = (value, digits = 1) => `${value.toFixed(digits)}%`;
    const fmtMaybePct = (value, digits = 1, signed = true) => isNum(value) ? (signed ? fmtPct(value, digits) : fmtPlainPct(value, digits)) : "n/a";
    const fmtMaybeRatio = (value, digits = 2) => isNum(value) ? `${value.toFixed(digits)}x` : "n/a";
    const fmtPrice = (value) => value >= 100 ? value.toFixed(2) : value.toFixed(4);
    const fmtCompact = (value) => {
      if (!isNum(value)) return "n/a";
      const abs = Math.abs(value);
      const sign = value < 0 ? "-" : "";
      if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(1)}T`;
      if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(1)}B`;
      if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
      return `${sign}$${abs.toFixed(0)}`;
    };
    const cls = (value) => value >= 0 ? "pos" : "neg";
    const maybeCls = (value) => !isNum(value) ? "muted" : cls(value);

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function scale(value, inMin, inMax, outMin, outMax) {
      if (inMax === inMin) return (outMin + outMax) / 2;
      return outMin + ((value - inMin) / (inMax - inMin)) * (outMax - outMin);
    }

    function clamp(value, min = 0, max = 1) {
      return Math.max(min, Math.min(max, value));
    }

    function valuesFor(key) {
      return metrics.map((item) => item[key]).filter(isNum);
    }

    function tickerValuesFor(key) {
      return tickers.map((item) => item[key]).filter(isNum);
    }

    function norm(value, key, higherIsBetter = true, fallback = 0.45) {
      if (!isNum(value)) return fallback;
      const values = valuesFor(key);
      if (values.length < 2) return fallback;
      const min = Math.min(...values);
      const max = Math.max(...values);
      if (min === max) return fallback;
      const raw = (value - min) / (max - min);
      return higherIsBetter ? raw : 1 - raw;
    }

    function averageScores(items) {
      const valid = items.filter(isNum);
      if (!valid.length) return 0.45;
      return valid.reduce((sum, value) => sum + value, 0) / valid.length;
    }

    function tickerNorm(value, key, higherIsBetter = true, fallback = 0.45) {
      if (!isNum(value)) return fallback;
      const values = tickerValuesFor(key);
      if (values.length < 2) return fallback;
      const min = Math.min(...values);
      const max = Math.max(...values);
      if (min === max) return fallback;
      const raw = (value - min) / (max - min);
      return higherIsBetter ? raw : 1 - raw;
    }

    function hydrateScores() {
      metrics.forEach((m) => {
        m.absDrawdownPct = Math.abs(m.maxDrawdownPct);
      });
      metrics.forEach((m) => {
        const currentDrawdownScore = norm(m.currentDrawdownPct, "currentDrawdownPct", true, 0.45);
        const drawdownDisciplineScore = norm(m.absDrawdownPct, "absDrawdownPct", false, 0.45);
        m.momentumScore = averageScores([
          norm(m.return20dPct, "return20dPct"),
          norm(m.return5dPct, "return5dPct"),
          norm(m.reboundFromLowPct, "reboundFromLowPct"),
          currentDrawdownScore,
        ]);
        m.squeezeScore = averageScores([
          norm(m.shortPctFloat, "shortPctFloat"),
          norm(m.optionsIvPct, "optionsIvPct"),
          norm(m.reboundFromLowPct, "reboundFromLowPct"),
          norm(m.return20dPct, "return20dPct"),
        ]);
        m.sponsorScore = averageScores([
          norm(m.institutionalOwnershipPct, "institutionalOwnershipPct"),
          norm(m.institutionalSharesChangedQoqPct, "institutionalSharesChangedQoqPct"),
          isNum(m.institutionalCoveragePct) ? clamp(m.institutionalCoveragePct / 100) : 0.35,
        ]);
        m.fundamentalScore = averageScores([
          norm(m.revenueGrowthYoyPct, "revenueGrowthYoyPct"),
          norm(m.grossMarginPct, "grossMarginPct"),
          norm(m.operatingMarginPct, "operatingMarginPct"),
          norm(m.freeCashFlowMarginPct, "freeCashFlowMarginPct"),
        ]);
        m.opportunityScore = clamp(
          (m.momentumScore * 0.3)
          + (m.squeezeScore * 0.25)
          + (m.sponsorScore * 0.23)
          + (m.fundamentalScore * 0.17)
          + (drawdownDisciplineScore * 0.05)
        );
      });
      tickers.forEach((t) => {
        t.absDrawdownPct = Math.abs(t.maxDrawdownPct);
      });
      tickers.forEach((t) => {
        t.momentumScore = averageScores([
          tickerNorm(t.return20dPct, "return20dPct"),
          tickerNorm(t.return10dPct, "return10dPct"),
          tickerNorm(t.return5dPct, "return5dPct"),
          tickerNorm(t.reboundFromLowPct, "reboundFromLowPct"),
        ]);
        t.squeezeScore = averageScores([
          tickerNorm(t.shortPctFloat, "shortPctFloat"),
          tickerNorm(t.optionsIvPct, "optionsIvPct"),
          tickerNorm(t.return20dPct, "return20dPct"),
          tickerNorm(t.currentDrawdownPct, "currentDrawdownPct"),
        ]);
        t.sponsorScore = averageScores([
          tickerNorm(t.institutionalOwnershipPct, "institutionalOwnershipPct"),
          tickerNorm(t.institutionalSharesChangedQoqPct, "institutionalSharesChangedQoqPct"),
          tickerNorm(t.institutionalInvestorCount, "institutionalInvestorCount"),
        ]);
        t.fundamentalScore = averageScores([
          tickerNorm(t.revenueGrowthYoyPct, "revenueGrowthYoyPct"),
          tickerNorm(t.grossMarginPct, "grossMarginPct"),
          tickerNorm(t.operatingMarginPct, "operatingMarginPct"),
          tickerNorm(t.freeCashFlowMarginPct, "freeCashFlowMarginPct"),
        ]);
        t.opportunityScore = clamp(
          (t.momentumScore * 0.32)
          + (t.squeezeScore * 0.24)
          + (t.sponsorScore * 0.22)
          + (t.fundamentalScore * 0.17)
          + (tickerNorm(t.absDrawdownPct, "absDrawdownPct", false, 0.45) * 0.05)
        );
      });
    }

    hydrateScores();

    function polyline(points) {
      return points.map((point) => `${point[0].toFixed(1)},${point[1].toFixed(1)}`).join(" ");
    }

    function pathFrom(points) {
      if (!points.length) return "";
      return `M ${points.map((point) => `${point[0].toFixed(1)} ${point[1].toFixed(1)}`).join(" L ")}`;
    }

    function showTip(event, html) {
      tooltip.innerHTML = html;
      tooltip.classList.add("show");
      moveTip(event);
    }

    function moveTip(event) {
      const pad = 14;
      const rect = tooltip.getBoundingClientRect();
      let x = event.clientX + pad;
      let y = event.clientY + pad;
      if (x + rect.width > window.innerWidth - 8) x = event.clientX - rect.width - pad;
      if (y + rect.height > window.innerHeight - 8) y = event.clientY - rect.height - pad;
      tooltip.style.transform = `translate(${x}px, ${y}px)`;
    }

    function hideTip() {
      tooltip.classList.remove("show");
      tooltip.style.transform = "translate(-999px, -999px)";
    }

    function wireTips(root = document) {
      root.querySelectorAll("[data-tip]").forEach((node) => {
        node.addEventListener("mousemove", (event) => showTip(event, node.dataset.tip));
        node.addEventListener("mouseleave", hideTip);
      });
    }

    function setSelected(basket) {
      selectedBasket = basket;
      const basketTop = (DATA.constituents[basket] || [])[0];
      if (basketTop) selectedTicker = basketTop.ticker;
      renderAll();
    }

    function setSelectedTicker(ticker) {
      selectedTicker = ticker;
      const item = byTicker.get(ticker);
      if (item && !item.baskets.some((basket) => basket.basket === selectedBasket) && item.baskets[0]) {
        selectedBasket = item.baskets[0].basket;
      }
      renderAll();
    }

    function renderHeader() {
      document.getElementById("window-chip").textContent = `${DATA.methodology.startDate} to ${DATA.methodology.endDate}`;
      document.getElementById("data-status").textContent = DATA.methodology.dataStatus;
      const winner = metrics[0];
      const bestSetup = metrics.slice().sort((a, b) => b.opportunityScore - a.opportunityScore)[0];
      const squeeze = metrics.slice().sort((a, b) => (b.shortPctFloat ?? -1) - (a.shortPctFloat ?? -1))[0];
      const sponsor = metrics.slice().sort((a, b) => (b.institutionalSharesChangedQoqPct ?? -999) - (a.institutionalSharesChangedQoqPct ?? -999))[0];
      const bench = DATA.benchmarks;
      document.getElementById("metric-strip").innerHTML = `
        <div class="kpi">
          <div class="label">Best basket</div>
          <div class="value pos">${escapeHtml(winner.short)} ${fmtPct(winner.returnPct, 1)}</div>
          <div class="sub">Rank 1 with ${fmtMaybePct(winner.return20dPct, 1)} over the last 20 sessions.</div>
        </div>
        <div class="kpi">
          <div class="label">Best setup</div>
          <div class="value">${escapeHtml(bestSetup.short)} ${(bestSetup.opportunityScore * 100).toFixed(0)}</div>
          <div class="sub">Composite score across price action, positioning, sponsors, and fundamentals.</div>
        </div>
        <div class="kpi">
          <div class="label">Squeeze pressure</div>
          <div class="value warn">${escapeHtml(squeeze.short)} ${fmtMaybePct(squeeze.shortPctFloat, 1, false)}</div>
          <div class="sub">Median true short interest as a share of float.</div>
        </div>
        <div class="kpi">
          <div class="label">Institutional bid</div>
          <div class="value ${maybeCls(sponsor.institutionalSharesChangedQoqPct)}">${escapeHtml(sponsor.short)} ${fmtMaybePct(sponsor.institutionalSharesChangedQoqPct, 1)}</div>
          <div class="sub">Median institutional shares changed QoQ. QQQ: ${fmtPct(bench.QQQ.returnPct, 1)}.</div>
        </div>
      `;
    }

    function renderLeaderboard() {
      const width = 900;
      const rowH = 36;
      const top = 28;
      const left = 164;
      const right = 74;
      const bottom = 42;
      const height = top + bottom + rowH * metrics.length;
      const minReturn = Math.min(-20, ...metrics.map((m) => m.returnPct));
      const maxReturn = Math.max(55, ...metrics.map((m) => m.returnPct));
      const x = (value) => scale(value, minReturn, maxReturn, left, width - right);
      const zeroX = x(0);
      const ticks = [-20, 0, 20, 40, 60];
      const bench = Object.entries(DATA.benchmarks).filter(([ticker]) => ["SPY", "QQQ", "BTC-USD"].includes(ticker));
      let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Ranked basket returns">`;
      svg += `<rect width="${width}" height="${height}" fill="transparent"></rect>`;
      ticks.forEach((tick) => {
        const tx = x(tick);
        svg += `<line class="grid-line" x1="${tx}" y1="${top - 12}" x2="${tx}" y2="${height - bottom + 8}"></line>`;
        svg += `<text class="svg-label" x="${tx}" y="${height - 12}" text-anchor="middle">${tick}%</text>`;
      });
      svg += `<line class="zero-line" x1="${zeroX}" y1="${top - 12}" x2="${zeroX}" y2="${height - bottom + 8}"></line>`;
      bench.forEach(([ticker, item], i) => {
        const bx = x(item.returnPct);
        const label = ticker === "BTC-USD" ? "BTC" : ticker;
        svg += `<line x1="${bx}" y1="${top - 18}" x2="${bx}" y2="${height - bottom + 8}" stroke="${i === 0 ? "#8ba0ad" : i === 1 ? "#6bb7ff" : "#f6b35b"}" stroke-width="1.5" stroke-dasharray="4 5" opacity="0.9"></line>`;
        svg += `<text class="svg-label" x="${bx + 5}" y="${top - 10}">${label}</text>`;
      });
      metrics.forEach((m, i) => {
        const y = top + i * rowH;
        const barX = Math.min(zeroX, x(m.returnPct));
        const barW = Math.abs(x(m.returnPct) - zeroX);
        const isSelected = m.basket === selectedBasket;
        const tip = `${escapeHtml(m.label)}<br>Return: <strong>${fmtPct(m.returnPct, 2)}</strong><br>Vol: ${fmtPlainPct(m.annualizedVolPct, 1)}<br>Drawdown: ${fmtPlainPct(m.maxDrawdownPct, 1)}<br>Breadth: ${m.positiveCount}/${m.constituentsUsed}`;
        svg += `<g class="bar-row" data-basket="${m.basket}" data-tip="${tip}">`;
        svg += `<text x="${left - 14}" y="${y + 23}" text-anchor="end" fill="${isSelected ? "#edf3f7" : "#b9c5cf"}" font-size="13" font-weight="850">${escapeHtml(m.label)}</text>`;
        svg += `<rect x="${barX}" y="${y + 7}" width="${Math.max(2, barW)}" height="20" rx="5" fill="${m.returnPct >= 0 ? m.color : "#ef6c86"}" opacity="${isSelected ? "1" : "0.72"}"></rect>`;
        svg += `<text x="${m.returnPct >= 0 ? x(m.returnPct) + 8 : x(m.returnPct) - 8}" y="${y + 22}" text-anchor="${m.returnPct >= 0 ? "start" : "end"}" fill="${m.returnPct >= 0 ? "#dffcf6" : "#ffdce3"}" font-size="12" font-weight="900">${fmtPct(m.returnPct, 1)}</text>`;
        svg += `<text x="18" y="${y + 23}" fill="#63717e" font-size="12" font-family="var(--mono)" font-weight="800">#${m.rank}</text>`;
        svg += `</g>`;
      });
      svg += `</svg>`;
      const el = document.getElementById("leaderboard-chart");
      el.innerHTML = svg;
      el.querySelectorAll(".bar-row").forEach((row) => row.addEventListener("click", () => setSelected(row.dataset.basket)));
      wireTips(el);
    }

    function selectedLineBaskets() {
      if (lineView === "all") return metrics.map((m) => m.basket);
      const leaders = metrics.slice(0, 4).map((m) => m.basket);
      if (!leaders.includes(selectedBasket)) leaders.push(selectedBasket);
      return leaders;
    }

    function renderPerformance() {
      const width = 1080;
      const height = 420;
      const left = 58;
      const right = 118;
      const top = 34;
      const bottom = 42;
      const baskets = selectedLineBaskets();
      const series = baskets.map((basket) => ({ basket, meta: byBasket.get(basket), rows: DATA.daily[basket] }));
      const allValues = series.flatMap((s) => s.rows.map((r) => r.index));
      const minY = Math.floor((Math.min(...allValues) - 4) / 10) * 10;
      const maxY = Math.ceil((Math.max(...allValues) + 4) / 10) * 10;
      const dates = Array.from(new Set(series.flatMap((s) => s.rows.map((r) => r.date)))).sort();
      const dateIndex = new Map(dates.map((date, idx) => [date, idx]));
      const xDate = (date) => scale(dateIndex.get(date), 0, dates.length - 1, left, width - right);
      const y = (value) => scale(value, minY, maxY, height - bottom, top);
      const ticksY = [];
      for (let v = minY; v <= maxY; v += 10) ticksY.push(v);
      let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Indexed basket performance lines">`;
      svg += `<rect width="${width}" height="${height}" fill="transparent"></rect>`;
      ticksY.forEach((tick) => {
        svg += `<line class="grid-line" x1="${left}" y1="${y(tick)}" x2="${width - right}" y2="${y(tick)}"></line>`;
        svg += `<text class="svg-label" x="${left - 10}" y="${y(tick) + 4}" text-anchor="end">${tick}</text>`;
      });
      [0, 0.25, 0.5, 0.75, 1].forEach((pct) => {
        const idx = Math.round((dates.length - 1) * pct);
        if (!dates[idx]) return;
        svg += `<text class="svg-label" x="${xDate(dates[idx])}" y="${height - 14}" text-anchor="middle">${dates[idx].slice(5)}</text>`;
      });
      svg += `<line class="zero-line" x1="${left}" y1="${y(100)}" x2="${width - right}" y2="${y(100)}" opacity="0.55"></line>`;
      series.forEach((s) => {
        const points = s.rows.map((row) => [xDate(row.date), y(row.index)]);
        const isSelected = s.basket === selectedBasket;
        const last = s.rows[s.rows.length - 1];
        const strokeWidth = isSelected ? 4.2 : 2.3;
        const opacity = isSelected ? 1 : 0.58;
        const tip = `${escapeHtml(s.meta.label)}<br>Latest index: <strong>${last.index.toFixed(2)}</strong><br>Return: ${fmtPct(s.meta.returnPct, 2)}`;
        svg += `<path d="${pathFrom(points)}" fill="none" stroke="${s.meta.color}" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round" opacity="${opacity}"></path>`;
        svg += `<path class="line-hit" data-basket="${s.basket}" data-tip="${tip}" d="${pathFrom(points)}" fill="none" stroke="transparent" stroke-width="14"></path>`;
        svg += `<circle cx="${points[points.length - 1][0]}" cy="${points[points.length - 1][1]}" r="${isSelected ? 5.5 : 4.2}" fill="${s.meta.color}" opacity="${opacity}"></circle>`;
        svg += `<text x="${width - right + 10}" y="${points[points.length - 1][1] + 4}" fill="${s.meta.color}" font-size="12" font-weight="900">${escapeHtml(s.meta.short)}</text>`;
      });
      svg += `</svg>`;
      const el = document.getElementById("performance-chart");
      el.innerHTML = svg;
      el.querySelectorAll(".line-hit").forEach((line) => line.addEventListener("click", () => setSelected(line.dataset.basket)));
      wireTips(el);

      const legend = document.getElementById("line-legend");
      legend.innerHTML = metrics.map((m) => `
        <button class="${m.basket === selectedBasket ? "active" : ""}" data-basket="${m.basket}" title="Focus ${escapeHtml(m.label)}">
          <span class="dot" style="color:${m.color}"></span>${escapeHtml(m.short)}
        </button>
      `).join("");
      legend.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => setSelected(button.dataset.basket)));
    }

    function renderScatter() {
      const width = 620;
      const height = 420;
      const left = 58;
      const right = 36;
      const top = 28;
      const bottom = 52;
      const minX = 20;
      const maxX = 86;
      const minY = -24;
      const maxY = 56;
      const x = (value) => scale(value, minX, maxX, left, width - right);
      const y = (value) => scale(value, minY, maxY, height - bottom, top);
      let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Risk return scatter plot">`;
      svg += `<rect width="${width}" height="${height}" fill="transparent"></rect>`;
      [20, 35, 50, 65, 80].forEach((tick) => {
        svg += `<line class="grid-line" x1="${x(tick)}" y1="${top}" x2="${x(tick)}" y2="${height - bottom}"></line>`;
        svg += `<text class="svg-label" x="${x(tick)}" y="${height - 18}" text-anchor="middle">${tick}%</text>`;
      });
      [-20, 0, 20, 40].forEach((tick) => {
        svg += `<line class="grid-line" x1="${left}" y1="${y(tick)}" x2="${width - right}" y2="${y(tick)}"></line>`;
        svg += `<text class="svg-label" x="${left - 9}" y="${y(tick) + 4}" text-anchor="end">${tick}%</text>`;
      });
      svg += `<line class="zero-line" x1="${left}" y1="${y(0)}" x2="${width - right}" y2="${y(0)}"></line>`;
      metrics.forEach((m) => {
        const r = 5 + (m.positivePct / 100) * 7;
        const isSelected = m.basket === selectedBasket;
        const tip = `${escapeHtml(m.label)}<br>Return: <strong>${fmtPct(m.returnPct, 2)}</strong><br>Vol: ${fmtPlainPct(m.annualizedVolPct, 1)}<br>Positive: ${m.positiveCount}/8`;
        svg += `<g class="bubble" data-basket="${m.basket}" data-tip="${tip}">`;
        if (isSelected) {
          svg += `<circle cx="${x(m.annualizedVolPct)}" cy="${y(m.returnPct)}" r="${r + 6}" fill="none" stroke="${m.color}" stroke-width="2" opacity="0.72"></circle>`;
        }
        svg += `<circle cx="${x(m.annualizedVolPct)}" cy="${y(m.returnPct)}" r="${r}" fill="${m.color}" opacity="${isSelected ? "0.96" : "0.72"}"></circle>`;
        svg += `<text x="${x(m.annualizedVolPct) + r + 5}" y="${y(m.returnPct) + 4}" fill="${isSelected ? "#edf3f7" : "#aebbc5"}" font-size="11" font-weight="850">${escapeHtml(m.short)}</text>`;
        svg += `</g>`;
      });
      svg += `<text class="svg-label" x="${(left + width - right) / 2}" y="${height - 4}" text-anchor="middle">Annualized volatility</text>`;
      svg += `<text class="svg-label" x="16" y="${(top + height - bottom) / 2}" text-anchor="middle" transform="rotate(-90 16 ${(top + height - bottom) / 2})">Total return</text>`;
      svg += `</svg>`;
      const el = document.getElementById("scatter-chart");
      el.innerHTML = svg;
      el.querySelectorAll(".bubble").forEach((bubble) => bubble.addEventListener("click", () => setSelected(bubble.dataset.basket)));
      wireTips(el);
    }

    function renderSignalBoard() {
      const labels = {
        opportunityScore: "Composite",
        squeezeScore: "Squeeze",
        sponsorScore: "Sponsors",
        fundamentalScore: "Fundamentals",
      };
      const sorted = metrics.slice().sort((a, b) => b[signalSort] - a[signalSort]);
      const el = document.getElementById("signal-board");
      el.innerHTML = sorted.map((m, i) => {
        const score = m[signalSort] * 100;
        const tip = `${escapeHtml(m.label)}<br>${labels[signalSort]} score: <strong>${score.toFixed(1)}</strong><br>20D return: ${fmtMaybePct(m.return20dPct, 1)}<br>Short interest: ${fmtMaybePct(m.shortPctFloat, 1, false)}<br>Institutional QoQ: ${fmtMaybePct(m.institutionalSharesChangedQoqPct, 1)}`;
        return `
          <div class="score-row ${m.basket === selectedBasket ? "active" : ""}" data-basket="${m.basket}" data-tip="${tip}">
            <div class="rank">#${i + 1}</div>
            <div>
              <div class="sector-title">${escapeHtml(m.label)}</div>
              <div class="sector-sub">${escapeHtml(m.short)} / Rank ${m.rank} by total return</div>
            </div>
            <div>
              <div class="score-label"><span>${labels[signalSort]}</span><strong>${score.toFixed(0)}</strong></div>
              <div class="score-track"><div class="score-bar" style="--score:${score.toFixed(1)}%"></div></div>
            </div>
            <div class="value-cell ${maybeCls(m.return20dPct)}">${fmtMaybePct(m.return20dPct, 1)}</div>
            <div class="value-cell warn">${fmtMaybePct(m.shortPctFloat, 1, false)}</div>
            <div class="value-cell ${maybeCls(m.institutionalSharesChangedQoqPct)}">${fmtMaybePct(m.institutionalSharesChangedQoqPct, 1)}</div>
          </div>
        `;
      }).join("");
      el.querySelectorAll(".score-row").forEach((row) => row.addEventListener("click", () => setSelected(row.dataset.basket)));
      wireTips(el);
    }

    function domainFor(values, fallbackMin, fallbackMax, pad = 0.08) {
      const filtered = values.filter(isNum);
      if (!filtered.length) return [fallbackMin, fallbackMax];
      let min = Math.min(fallbackMin, ...filtered);
      let max = Math.max(fallbackMax, ...filtered);
      if (min === max) {
        min -= 1;
        max += 1;
      }
      const room = (max - min) * pad;
      return [min - room, max + room];
    }

    function renderOwnershipMap() {
      const usable = metrics.filter((m) => isNum(m.shortPctFloat) && isNum(m.institutionalSharesChangedQoqPct));
      const width = 620;
      const height = 420;
      const left = 62;
      const right = 34;
      const top = 30;
      const bottom = 58;
      const [minX, maxX] = domainFor(usable.map((m) => m.shortPctFloat), 0, 30, 0.05);
      const [minY, maxY] = domainFor(usable.map((m) => m.institutionalSharesChangedQoqPct), -6, 14, 0.12);
      const maxAbsReturn = Math.max(1, ...usable.map((m) => Math.abs(m.return20dPct || 0)));
      const x = (value) => scale(value, minX, maxX, left, width - right);
      const y = (value) => scale(value, minY, maxY, height - bottom, top);
      let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Short interest and institutional ownership map">`;
      svg += `<rect width="${width}" height="${height}" fill="transparent"></rect>`;
      [0, 10, 20, 30].forEach((tick) => {
        if (tick < minX || tick > maxX) return;
        svg += `<line class="grid-line" x1="${x(tick)}" y1="${top}" x2="${x(tick)}" y2="${height - bottom}"></line>`;
        svg += `<text class="svg-label" x="${x(tick)}" y="${height - 22}" text-anchor="middle">${tick}%</text>`;
      });
      [-5, 0, 5, 10, 15].forEach((tick) => {
        if (tick < minY || tick > maxY) return;
        svg += `<line class="grid-line" x1="${left}" y1="${y(tick)}" x2="${width - right}" y2="${y(tick)}"></line>`;
        svg += `<text class="svg-label" x="${left - 9}" y="${y(tick) + 4}" text-anchor="end">${tick}%</text>`;
      });
      svg += `<line class="zero-line" x1="${left}" y1="${y(0)}" x2="${width - right}" y2="${y(0)}"></line>`;
      usable.forEach((m) => {
        const radius = 6 + clamp(Math.abs(m.return20dPct || 0) / maxAbsReturn) * 11;
        const isSelected = m.basket === selectedBasket;
        const tip = `${escapeHtml(m.label)}<br>Short interest: <strong>${fmtMaybePct(m.shortPctFloat, 2, false)}</strong><br>Institutional shares QoQ: ${fmtMaybePct(m.institutionalSharesChangedQoqPct, 2)}<br>20D return: ${fmtMaybePct(m.return20dPct, 2)}<br>Institutional ownership: ${fmtMaybePct(m.institutionalOwnershipPct, 1, false)}`;
        svg += `<g class="bubble" data-basket="${m.basket}" data-tip="${tip}">`;
        if (isSelected) svg += `<circle cx="${x(m.shortPctFloat)}" cy="${y(m.institutionalSharesChangedQoqPct)}" r="${radius + 7}" fill="none" stroke="${m.color}" stroke-width="2"></circle>`;
        svg += `<circle cx="${x(m.shortPctFloat)}" cy="${y(m.institutionalSharesChangedQoqPct)}" r="${radius}" fill="${m.color}" opacity="${isSelected ? "0.98" : "0.7"}"></circle>`;
        svg += `<text x="${x(m.shortPctFloat) + radius + 5}" y="${y(m.institutionalSharesChangedQoqPct) + 4}" fill="${isSelected ? "#f2f0e8" : "#b9b7aa"}" font-size="11" font-weight="850">${escapeHtml(m.short)}</text>`;
        svg += `</g>`;
      });
      svg += `<text class="svg-label" x="${(left + width - right) / 2}" y="${height - 5}" text-anchor="middle">Median short interest / float</text>`;
      svg += `<text class="svg-label" x="16" y="${(top + height - bottom) / 2}" text-anchor="middle" transform="rotate(-90 16 ${(top + height - bottom) / 2})">Institutional shares changed QoQ</text>`;
      svg += `</svg>`;
      const el = document.getElementById("ownership-chart");
      el.innerHTML = svg;
      el.querySelectorAll(".bubble").forEach((bubble) => bubble.addEventListener("click", () => setSelected(bubble.dataset.basket)));
      wireTips(el);
    }

    function renderFundamentalsMap() {
      const usable = metrics.filter((m) => isNum(m.revenueGrowthYoyPct) && isNum(m.freeCashFlowMarginPct));
      const width = 620;
      const height = 420;
      const left = 62;
      const right = 34;
      const top = 30;
      const bottom = 58;
      const [minX, maxX] = domainFor(usable.map((m) => m.revenueGrowthYoyPct), -10, 50, 0.08);
      const [minY, maxY] = domainFor(usable.map((m) => m.freeCashFlowMarginPct), -160, 40, 0.05);
      const maxAbsReturn = Math.max(1, ...usable.map((m) => Math.abs(m.returnPct || 0)));
      const x = (value) => scale(value, minX, maxX, left, width - right);
      const y = (value) => scale(value, minY, maxY, height - bottom, top);
      let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Revenue growth and free cash flow margin map">`;
      svg += `<rect width="${width}" height="${height}" fill="transparent"></rect>`;
      [-10, 0, 20, 40, 60].forEach((tick) => {
        if (tick < minX || tick > maxX) return;
        svg += `<line class="grid-line" x1="${x(tick)}" y1="${top}" x2="${x(tick)}" y2="${height - bottom}"></line>`;
        svg += `<text class="svg-label" x="${x(tick)}" y="${height - 22}" text-anchor="middle">${tick}%</text>`;
      });
      [-160, -80, 0, 40].forEach((tick) => {
        if (tick < minY || tick > maxY) return;
        svg += `<line class="grid-line" x1="${left}" y1="${y(tick)}" x2="${width - right}" y2="${y(tick)}"></line>`;
        svg += `<text class="svg-label" x="${left - 9}" y="${y(tick) + 4}" text-anchor="end">${tick}%</text>`;
      });
      svg += `<line class="zero-line" x1="${left}" y1="${y(0)}" x2="${width - right}" y2="${y(0)}"></line>`;
      svg += `<line class="zero-line" x1="${x(0)}" y1="${top}" x2="${x(0)}" y2="${height - bottom}" opacity="0.65"></line>`;
      usable.forEach((m) => {
        const radius = 6 + clamp(Math.abs(m.returnPct || 0) / maxAbsReturn) * 11;
        const isSelected = m.basket === selectedBasket;
        const tip = `${escapeHtml(m.label)}<br>Revenue growth: <strong>${fmtMaybePct(m.revenueGrowthYoyPct, 2)}</strong><br>FCF margin: ${fmtMaybePct(m.freeCashFlowMarginPct, 2)}<br>Gross margin: ${fmtMaybePct(m.grossMarginPct, 1, false)}<br>Total return: ${fmtPct(m.returnPct, 2)}`;
        svg += `<g class="bubble" data-basket="${m.basket}" data-tip="${tip}">`;
        if (isSelected) svg += `<circle cx="${x(m.revenueGrowthYoyPct)}" cy="${y(m.freeCashFlowMarginPct)}" r="${radius + 7}" fill="none" stroke="${m.color}" stroke-width="2"></circle>`;
        svg += `<circle cx="${x(m.revenueGrowthYoyPct)}" cy="${y(m.freeCashFlowMarginPct)}" r="${radius}" fill="${m.color}" opacity="${isSelected ? "0.98" : "0.68"}"></circle>`;
        svg += `<text x="${x(m.revenueGrowthYoyPct) + radius + 5}" y="${y(m.freeCashFlowMarginPct) + 4}" fill="${isSelected ? "#f2f0e8" : "#b9b7aa"}" font-size="11" font-weight="850">${escapeHtml(m.short)}</text>`;
        svg += `</g>`;
      });
      svg += `<text class="svg-label" x="${(left + width - right) / 2}" y="${height - 5}" text-anchor="middle">Median revenue growth YoY</text>`;
      svg += `<text class="svg-label" x="16" y="${(top + height - bottom) / 2}" text-anchor="middle" transform="rotate(-90 16 ${(top + height - bottom) / 2})">Median free-cash-flow margin</text>`;
      svg += `</svg>`;
      const el = document.getElementById("fundamentals-chart");
      el.innerHTML = svg;
      el.querySelectorAll(".bubble").forEach((bubble) => bubble.addEventListener("click", () => setSelected(bubble.dataset.basket)));
      wireTips(el);
    }

    function heatBackground(value, key, higherIsBetter = true, palette = "green") {
      if (!isNum(value)) return "background:rgb(255 255 255 / 0.025);color:#747467;";
      const score = clamp(norm(value, key, higherIsBetter, 0.5));
      if (palette === "amber") {
        return `background:rgb(242 201 93 / ${0.12 + score * 0.46});`;
      }
      if (palette === "blue") {
        return `background:rgb(107 183 255 / ${0.11 + score * 0.42});`;
      }
      const hue = 352 + score * 170;
      return `background:hsl(${hue} 62% 43% / ${0.18 + score * 0.46});`;
    }

    function renderHeatmap() {
      const rows = metrics.slice().sort((a, b) => b.opportunityScore - a.opportunityScore);
      const columns = [
        ["Return", "returnPct", (v) => fmtMaybePct(v, 1), true, "green"],
        ["20D", "return20dPct", (v) => fmtMaybePct(v, 1), true, "green"],
        ["Cur DD", "currentDrawdownPct", (v) => fmtMaybePct(v, 1), true, "green"],
        ["Rebound", "reboundFromLowPct", (v) => fmtMaybePct(v, 1), true, "blue"],
        ["Short %", "shortPctFloat", (v) => fmtMaybePct(v, 1, false), true, "amber"],
        ["Inst QoQ", "institutionalSharesChangedQoqPct", (v) => fmtMaybePct(v, 1), true, "green"],
        ["Rev YoY", "revenueGrowthYoyPct", (v) => fmtMaybePct(v, 1), true, "green"],
        ["FCF Mgn", "freeCashFlowMarginPct", (v) => fmtMaybePct(v, 1), true, "green"],
      ];
      const header = `<div class="heat-row header"><div class="heat-cell">Basket</div>${columns.map((col) => `<div class="heat-cell">${col[0]}</div>`).join("")}</div>`;
      const body = rows.map((m) => {
        const cells = columns.map(([label, key, formatter, higherIsBetter, palette]) => {
          const value = m[key];
          const tip = `${escapeHtml(m.label)}<br>${label}: <strong>${formatter(value)}</strong>`;
          return `<div class="heat-cell" data-tip="${tip}" style="${heatBackground(value, key, higherIsBetter, palette)}">${formatter(value)}</div>`;
        }).join("");
        return `<div class="heat-row" data-basket="${m.basket}"><div class="heat-cell"><span class="dot" style="color:${m.color};margin-right:8px"></span>${escapeHtml(m.short)}</div>${cells}</div>`;
      }).join("");
      const el = document.getElementById("factor-heatmap");
      el.innerHTML = header + body;
      el.querySelectorAll(".heat-row[data-basket]").forEach((row) => row.addEventListener("click", () => setSelected(row.dataset.basket)));
      wireTips(el);
    }

    function renderDrawdown() {
      const width = 620;
      const rowH = 31;
      const top = 22;
      const left = 142;
      const right = 70;
      const height = top + 40 + rowH * metrics.length;
      const maxDD = Math.max(...metrics.map((m) => Math.abs(m.maxDrawdownPct)));
      const x = (value) => scale(value, 0, maxDD, left, width - right);
      let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Max drawdown bars">`;
      svg += `<rect width="${width}" height="${height}" fill="transparent"></rect>`;
      [0, 10, 20, 30].forEach((tick) => {
        if (tick > maxDD + 3) return;
        svg += `<line class="grid-line" x1="${x(tick)}" y1="${top - 8}" x2="${x(tick)}" y2="${height - 30}"></line>`;
        svg += `<text class="svg-label" x="${x(tick)}" y="${height - 10}" text-anchor="middle">${tick}%</text>`;
      });
      metrics.forEach((m, i) => {
        const y = top + i * rowH;
        const w = x(Math.abs(m.maxDrawdownPct)) - left;
        const isSelected = m.basket === selectedBasket;
        const tip = `${escapeHtml(m.label)}<br>Max drawdown: <strong>${fmtPlainPct(m.maxDrawdownPct, 2)}</strong>`;
        svg += `<g class="bar-row" data-basket="${m.basket}" data-tip="${tip}">`;
        svg += `<text x="${left - 12}" y="${y + 18}" text-anchor="end" fill="${isSelected ? "#edf3f7" : "#aebbc5"}" font-size="12" font-weight="850">${escapeHtml(m.short)}</text>`;
        svg += `<rect x="${left}" y="${y + 6}" width="${Math.max(2, w)}" height="16" rx="5" fill="#ef6c86" opacity="${isSelected ? "0.96" : "0.56"}"></rect>`;
        svg += `<text x="${left + w + 7}" y="${y + 18}" fill="#ffdce3" font-size="11" font-weight="850">${fmtPlainPct(m.maxDrawdownPct, 1)}</text>`;
        svg += `</g>`;
      });
      svg += `</svg>`;
      const el = document.getElementById("drawdown-chart");
      el.innerHTML = svg;
      el.querySelectorAll(".bar-row").forEach((row) => row.addEventListener("click", () => setSelected(row.dataset.basket)));
      wireTips(el);
    }

    function renderBreadth() {
      const el = document.getElementById("breadth-panel");
      el.innerHTML = metrics.map((m) => {
        const dots = Array.from({ length: 8 }, (_, i) => `<i class="${i < m.positiveCount ? "on" : ""}"></i>`).join("");
        return `
          <div class="breadth-row ${m.basket === selectedBasket ? "active" : ""}" data-basket="${m.basket}">
            <div class="sector-title">${escapeHtml(m.short)}</div>
            <div class="breadth-dots" style="--good:${m.color}">${dots}</div>
            <div class="value-cell">${m.positiveCount}/8</div>
          </div>
        `;
      }).join("");
      el.querySelectorAll(".breadth-row").forEach((row) => row.addEventListener("click", () => setSelected(row.dataset.basket)));
    }

    function renderSectorList() {
      const sorted = metrics.slice().sort((a, b) => {
        const av = isNum(a[sortKey]) ? a[sortKey] : -9999;
        const bv = isNum(b[sortKey]) ? b[sortKey] : -9999;
        if (sortKey === "annualizedVolPct") return av - bv;
        if (sortKey === "maxDrawdownPct") return bv - av;
        return bv - av;
      });
      const el = document.getElementById("sector-list");
      el.innerHTML = sorted.map((m) => `
        <div class="sector-row ${m.basket === selectedBasket ? "active" : ""}" data-basket="${m.basket}">
          <div class="rank">#${m.rank}</div>
          <div>
            <div class="sector-title">${escapeHtml(m.label)}</div>
            <div class="sector-sub">Best ${escapeHtml(m.bestConstituent)} ${fmtPct(m.bestConstituentReturnPct, 1)} / Worst ${escapeHtml(m.worstConstituent)} ${fmtPct(m.worstConstituentReturnPct, 1)}</div>
          </div>
          <div class="value-cell ${cls(m.returnPct)}">${fmtPct(m.returnPct, 1)}</div>
          <div class="value-cell warn">${fmtMaybePct(m.shortPctFloat, 1, false)}</div>
          <div class="value-cell ${maybeCls(m.institutionalSharesChangedQoqPct)}">${fmtMaybePct(m.institutionalSharesChangedQoqPct, 1)}</div>
        </div>
      `).join("");
      el.querySelectorAll(".sector-row").forEach((row) => row.addEventListener("click", () => setSelected(row.dataset.basket)));
    }

    function makeSparkline(series, color) {
      if (!series || series.length < 2) return "";
      const width = 82;
      const height = 28;
      const pad = 3;
      const values = series.map((item) => item.value);
      const min = Math.min(...values);
      const max = Math.max(...values);
      const points = values.map((value, i) => [
        scale(i, 0, values.length - 1, pad, width - pad),
        scale(value, min, max, height - pad, pad),
      ]);
      return `<svg class="spark" viewBox="0 0 ${width} ${height}" aria-hidden="true"><path d="${pathFrom(points)}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>`;
    }

    function tickerBasketTags(item) {
      return item.baskets.map((basket) => `
        <span class="ticker-tag"><span class="dot" style="color:${basket.color}"></span>${escapeHtml(basket.short)}</span>
      `).join("");
    }

    function tickerSetupLabels(item) {
      const labels = [];
      if (isNum(item.return20dPct) && item.return20dPct >= 15) labels.push("Momentum");
      if (isNum(item.shortPctFloat) && item.shortPctFloat >= 15 && (!isNum(item.return20dPct) || item.return20dPct >= 0)) labels.push("Squeeze");
      if (isNum(item.institutionalSharesChangedQoqPct) && item.institutionalSharesChangedQoqPct >= 5) labels.push("Inst bid");
      if (isNum(item.freeCashFlowMarginPct) && item.freeCashFlowMarginPct >= 10 && isNum(item.revenueGrowthYoyPct) && item.revenueGrowthYoyPct > 0) labels.push("Quality");
      if (isNum(item.currentDrawdownPct) && item.currentDrawdownPct <= -8 && isNum(item.reboundFromLowPct) && item.reboundFromLowPct >= 20) labels.push("Rebound");
      if ((isNum(item.annualizedVolPct) && item.annualizedVolPct >= 85) || (isNum(item.optionsIvPct) && item.optionsIvPct >= 100) || item.maxDrawdownPct <= -30) labels.push("High risk");
      return labels.length ? labels : ["Watch"];
    }

    function tickerMatchesFilter(item) {
      if (tickerFilter === "all") return true;
      if (tickerFilter === "selected") return item.baskets.some((basket) => basket.basket === selectedBasket);
      if (tickerFilter === "momentum") return isNum(item.return20dPct) && item.return20dPct >= 12;
      if (tickerFilter === "squeeze") return isNum(item.shortPctFloat) && item.shortPctFloat >= 15 && (!isNum(item.return20dPct) || item.return20dPct >= 0);
      if (tickerFilter === "institutional") return isNum(item.institutionalSharesChangedQoqPct) && item.institutionalSharesChangedQoqPct >= 5;
      if (tickerFilter === "quality") return isNum(item.freeCashFlowMarginPct) && item.freeCashFlowMarginPct >= 10 && isNum(item.revenueGrowthYoyPct) && item.revenueGrowthYoyPct > 0;
      if (tickerFilter === "rebound") return isNum(item.currentDrawdownPct) && item.currentDrawdownPct <= -8 && isNum(item.reboundFromLowPct) && item.reboundFromLowPct >= 20;
      if (tickerFilter === "risk") return (isNum(item.annualizedVolPct) && item.annualizedVolPct >= 85) || (isNum(item.optionsIvPct) && item.optionsIvPct >= 100) || item.maxDrawdownPct <= -30;
      return true;
    }

    function filteredTickers() {
      const query = tickerSearch.trim().toLowerCase();
      return tickers
        .filter((item) => {
          if (!query) return true;
          return item.ticker.toLowerCase().includes(query) || item.name.toLowerCase().includes(query);
        })
        .filter(tickerMatchesFilter)
        .sort((a, b) => {
          const av = isNum(a[tickerSort]) ? a[tickerSort] : -99999;
          const bv = isNum(b[tickerSort]) ? b[tickerSort] : -99999;
          if (tickerSort === "currentDrawdownPct") return av - bv;
          return bv - av;
        });
    }

    function renderBasketAttribution() {
      const rows = DATA.attribution[selectedBasket] || [];
      const maxAbs = Math.max(1, ...rows.map((item) => Math.abs(item.contributionPct)));
      const el = document.getElementById("basket-attribution");
      el.innerHTML = rows.map((item) => {
        const active = item.ticker === selectedTicker;
        const width = clamp(Math.abs(item.contributionPct) / maxAbs) * 100;
        const tip = `${escapeHtml(item.ticker)}<br>Return: <strong>${fmtPct(item.returnPct, 2)}</strong><br>Equal-weight contribution: ${fmtPct(item.contributionPct, 2)}<br>20D: ${fmtMaybePct(item.return20dPct, 1)}<br>Short interest: ${fmtMaybePct(item.shortPctFloat, 1, false)}`;
        return `
          <div class="attribution-row ${active ? "active" : ""}" data-ticker="${item.ticker}" data-tip="${tip}">
            <div class="ticker">${escapeHtml(item.ticker)}</div>
            <div><div class="sector-title">${escapeHtml(item.name)}</div><div class="sector-sub">${fmtMaybePct(item.return20dPct, 1)} 20D / ${fmtMaybePct(item.currentDrawdownPct, 1)} cur DD</div></div>
            <div class="bar-track"><div class="bar-fill" style="--bar:${width.toFixed(1)}%;--bar-color:${item.contributionPct >= 0 ? "var(--good)" : "var(--bad)"}"></div></div>
            <div class="value-cell ${cls(item.returnPct)}">${fmtPct(item.returnPct, 1)}</div>
            <div class="value-cell ${cls(item.contributionPct)}">${fmtPct(item.contributionPct, 1)}</div>
          </div>
        `;
      }).join("");
      el.querySelectorAll(".attribution-row").forEach((row) => row.addEventListener("click", () => setSelectedTicker(row.dataset.ticker)));
      wireTips(el);
    }

    function renderTickerExplorer() {
      const rows = filteredTickers();
      const el = document.getElementById("ticker-explorer");
      const body = rows.map((item) => {
        const active = item.ticker === selectedTicker;
        const labels = tickerSetupLabels(item).map((label) => `<span class="ticker-tag">${escapeHtml(label)}</span>`).join("");
        return `
          <tr class="ticker-row ${active ? "active" : ""}" data-ticker="${item.ticker}">
            <td><span class="ticker">${escapeHtml(item.ticker)}</span><div class="muted">${escapeHtml(item.name)}</div></td>
            <td><div class="ticker-tags">${tickerBasketTags(item)}</div></td>
            <td><div class="ticker-tags">${labels}</div></td>
            <td class="${cls(item.returnPct)}">${fmtPct(item.returnPct, 1)}</td>
            <td class="${maybeCls(item.return20dPct)}">${fmtMaybePct(item.return20dPct, 1)}</td>
            <td class="${maybeCls(item.currentDrawdownPct)}">${fmtMaybePct(item.currentDrawdownPct, 1)}</td>
            <td>${fmtMaybePct(item.reboundFromLowPct, 1, false)}</td>
            <td class="warn">${fmtMaybePct(item.shortPctFloat, 1, false)}</td>
            <td>${fmtMaybePct(item.optionsIvPct, 0, false)}</td>
            <td class="${maybeCls(item.institutionalSharesChangedQoqPct)}">${fmtMaybePct(item.institutionalSharesChangedQoqPct, 1)}</td>
            <td class="${maybeCls(item.revenueGrowthYoyPct)}">${fmtMaybePct(item.revenueGrowthYoyPct, 1)}</td>
            <td class="${maybeCls(item.freeCashFlowMarginPct)}">${fmtMaybePct(item.freeCashFlowMarginPct, 1)}</td>
            <td>${(item.opportunityScore * 100).toFixed(0)}</td>
          </tr>
        `;
      }).join("");
      el.innerHTML = `
        <table class="ticker-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Baskets</th>
              <th>Setup</th>
              <th>Return</th>
              <th>20D</th>
              <th>Cur DD</th>
              <th>Rebound</th>
              <th>Short %</th>
              <th>IV</th>
              <th>Inst QoQ</th>
              <th>Rev YoY</th>
              <th>FCF</th>
              <th>Score</th>
            </tr>
          </thead>
          <tbody>${body || `<tr><td colspan="13" class="muted">No tickers match the current screen.</td></tr>`}</tbody>
        </table>
      `;
      el.querySelectorAll(".ticker-row").forEach((row) => row.addEventListener("click", () => setSelectedTicker(row.dataset.ticker)));
    }

    function tickerProfileChart(item, basketId) {
      const basket = byBasket.get(basketId);
      const basketRows = (DATA.daily[basketId] || []).map((row) => ({ date: row.date, value: row.index }));
      const qqqRows = (DATA.benchmarks.QQQ?.series || []).map((row) => ({ date: row.date, value: row.value }));
      const series = [
        { label: item.ticker, color: basket?.color || "#4bd6b8", rows: item.series || [], width: 3.8 },
        { label: basket?.short || "Basket", color: "#f2c95d", rows: basketRows, width: 2.4 },
        { label: "QQQ", color: "#6bb7ff", rows: qqqRows, width: 1.8 },
      ].filter((entry) => entry.rows.length > 1);
      if (!series.length) return "";
      const width = 900;
      const height = 300;
      const left = 54;
      const right = 80;
      const top = 24;
      const bottom = 38;
      const dates = Array.from(new Set(series.flatMap((entry) => entry.rows.map((row) => row.date)))).sort();
      const dateIndex = new Map(dates.map((date, index) => [date, index]));
      const values = series.flatMap((entry) => entry.rows.map((row) => row.value));
      const minY = Math.floor((Math.min(...values) - 4) / 10) * 10;
      const maxY = Math.ceil((Math.max(...values) + 4) / 10) * 10;
      const x = (date) => scale(dateIndex.get(date), 0, dates.length - 1, left, width - right);
      const y = (value) => scale(value, minY, maxY, height - bottom, top);
      let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(item.ticker)} indexed comparison chart">`;
      svg += `<rect width="${width}" height="${height}" fill="transparent"></rect>`;
      for (let tick = minY; tick <= maxY; tick += 10) {
        svg += `<line class="grid-line" x1="${left}" y1="${y(tick)}" x2="${width - right}" y2="${y(tick)}"></line>`;
        svg += `<text class="svg-label" x="${left - 8}" y="${y(tick) + 4}" text-anchor="end">${tick}</text>`;
      }
      svg += `<line class="zero-line" x1="${left}" y1="${y(100)}" x2="${width - right}" y2="${y(100)}" opacity="0.6"></line>`;
      series.forEach((entry) => {
        const points = entry.rows.map((row) => [x(row.date), y(row.value)]);
        const last = points[points.length - 1];
        svg += `<path d="${pathFrom(points)}" fill="none" stroke="${entry.color}" stroke-width="${entry.width}" stroke-linecap="round" stroke-linejoin="round"></path>`;
        svg += `<circle cx="${last[0]}" cy="${last[1]}" r="4.2" fill="${entry.color}"></circle>`;
        svg += `<text x="${width - right + 9}" y="${last[1] + 4}" fill="${entry.color}" font-size="12" font-weight="900">${escapeHtml(entry.label)}</text>`;
      });
      [0, 0.5, 1].forEach((pct) => {
        const date = dates[Math.round((dates.length - 1) * pct)];
        if (date) svg += `<text class="svg-label" x="${x(date)}" y="${height - 12}" text-anchor="middle">${date.slice(5)}</text>`;
      });
      svg += `</svg>`;
      return svg;
    }

    function tickerNarrative(item) {
      const pieces = [];
      if (isNum(item.return20dPct) && item.return20dPct >= 15) pieces.push(`${fmtMaybePct(item.return20dPct, 1)} over 20 sessions`);
      if (isNum(item.shortPctFloat) && item.shortPctFloat >= 15) pieces.push(`${fmtMaybePct(item.shortPctFloat, 1, false)} short interest`);
      if (isNum(item.institutionalSharesChangedQoqPct) && item.institutionalSharesChangedQoqPct >= 5) pieces.push(`${fmtMaybePct(item.institutionalSharesChangedQoqPct, 1)} institutional shares QoQ`);
      if (isNum(item.currentDrawdownPct) && item.currentDrawdownPct <= -10) pieces.push(`${fmtMaybePct(item.currentDrawdownPct, 1)} below its window high`);
      if (isNum(item.freeCashFlowMarginPct) && item.freeCashFlowMarginPct < 0) pieces.push(`${fmtMaybePct(item.freeCashFlowMarginPct, 1)} FCF margin`);
      if (!pieces.length) pieces.push("a less extreme setup across the tracked factors");
      return `${escapeHtml(item.ticker)}: ${pieces.join(", ")}. Ticker score ${(item.opportunityScore * 100).toFixed(0)} / 100.`;
    }

    function renderTickerProfile() {
      const item = byTicker.get(selectedTicker) || tickers[0];
      if (!item) return;
      const profileBasketId = item.baskets.some((basket) => basket.basket === selectedBasket) ? selectedBasket : item.baskets[0]?.basket;
      const basket = profileBasketId ? byBasket.get(profileBasketId) : null;
      const el = document.getElementById("ticker-profile");
      el.innerHTML = `
        <div class="ticker-profile">
          <div class="ticker-profile-main">
            <div class="ticker-title">
              <h2>${escapeHtml(item.ticker)}</h2>
              <span class="muted">${escapeHtml(item.name)}</span>
              ${basket ? `<span class="coverage-badge">${escapeHtml(basket.short)}</span>` : ""}
            </div>
            <div class="profile-chart">${tickerProfileChart(item, profileBasketId)}</div>
            <div class="profile-note">${tickerNarrative(item)}</div>
          </div>
          <div class="ticker-profile-side">
            <div class="profile-metrics">
              <div class="profile-metric"><span>Total return</span><strong class="${cls(item.returnPct)}">${fmtPct(item.returnPct, 2)}</strong></div>
              <div class="profile-metric"><span>20D / 5D</span><strong>${fmtMaybePct(item.return20dPct, 1)} / ${fmtMaybePct(item.return5dPct, 1)}</strong></div>
              <div class="profile-metric"><span>Cur drawdown</span><strong class="${maybeCls(item.currentDrawdownPct)}">${fmtMaybePct(item.currentDrawdownPct, 1)}</strong></div>
              <div class="profile-metric"><span>Rebound</span><strong>${fmtMaybePct(item.reboundFromLowPct, 1, false)}</strong></div>
              <div class="profile-metric"><span>Short interest</span><strong class="warn">${fmtMaybePct(item.shortPctFloat, 1, false)}</strong></div>
              <div class="profile-metric"><span>Options IV</span><strong>${fmtMaybePct(item.optionsIvPct, 0, false)}</strong></div>
              <div class="profile-metric"><span>Inst ownership</span><strong>${fmtMaybePct(item.institutionalOwnershipPct, 1, false)}</strong></div>
              <div class="profile-metric"><span>Inst QoQ</span><strong class="${maybeCls(item.institutionalSharesChangedQoqPct)}">${fmtMaybePct(item.institutionalSharesChangedQoqPct, 1)}</strong></div>
              <div class="profile-metric"><span>Revenue YoY</span><strong class="${maybeCls(item.revenueGrowthYoyPct)}">${fmtMaybePct(item.revenueGrowthYoyPct, 1)}</strong></div>
              <div class="profile-metric"><span>Gross margin</span><strong>${fmtMaybePct(item.grossMarginPct, 1, false)}</strong></div>
              <div class="profile-metric"><span>FCF margin</span><strong class="${maybeCls(item.freeCashFlowMarginPct)}">${fmtMaybePct(item.freeCashFlowMarginPct, 1)}</strong></div>
              <div class="profile-metric"><span>Net cash</span><strong>${fmtCompact(item.netCash)}</strong></div>
            </div>
            <div class="notes">
              <div class="note">Sources: price from Yahoo chart data; fundamentals from SEC companyfacts when available; true short interest from StockAnalysis snapshot; options from Cboe delayed snapshot; institutional ownership from BusinessQuant 13F aggregation.</div>
              <div class="note">Coverage: fundamentals ${escapeHtml(item.fundamentalsStatus || "n/a")}; short interest ${escapeHtml(item.shortInterestStatus || "n/a")}; options ${escapeHtml(item.optionsStatus || "n/a")}; institutional ${escapeHtml(item.institutionalStatus || "n/a")}.</div>
            </div>
          </div>
        </div>
      `;
    }

    function setupNarrative(m) {
      const setup = [];
      if (isNum(m.shortPctFloat) && m.shortPctFloat >= 15) setup.push(`heavy true short interest at ${fmtMaybePct(m.shortPctFloat, 1, false)} of float`);
      if (isNum(m.reboundFromLowPct) && m.reboundFromLowPct >= 40) setup.push(`a ${fmtMaybePct(m.reboundFromLowPct, 1, false)} rebound from the window low`);
      if (isNum(m.currentDrawdownPct) && m.currentDrawdownPct === 0) setup.push("price at a window high");
      if (isNum(m.currentDrawdownPct) && m.currentDrawdownPct < -8) setup.push(`${fmtMaybePct(m.currentDrawdownPct, 1)} below the window high`);
      if (isNum(m.institutionalSharesChangedQoqPct) && m.institutionalSharesChangedQoqPct > 5) setup.push(`institutional shares up ${fmtMaybePct(m.institutionalSharesChangedQoqPct, 1)} QoQ`);
      if (isNum(m.freeCashFlowMarginPct) && m.freeCashFlowMarginPct < -25) setup.push(`weak median FCF margin at ${fmtMaybePct(m.freeCashFlowMarginPct, 1)}`);
      if (!setup.length) setup.push("a balanced profile without a single extreme factor");
      return `${escapeHtml(m.short)} shows ${setup.join(", ")}. Composite score ${(m.opportunityScore * 100).toFixed(0)} / 100.`;
    }

    function detailTable(rows, m) {
      if (detailView === "fundamentals") {
        return {
          headers: ["Ticker", "Return", "Rev YoY", "Gross", "Op Mgn", "FCF Mgn", "Net cash"],
          rows: rows.map((item) => `
            <tr class="ticker-row ${item.ticker === selectedTicker ? "active" : ""}" data-ticker="${item.ticker}">
              <td><span class="ticker">${escapeHtml(item.ticker)}</span><div class="muted">${escapeHtml(item.name)}</div></td>
              <td class="${cls(item.returnPct)}">${fmtPct(item.returnPct, 2)}</td>
              <td class="${maybeCls(item.revenueGrowthYoyPct)}">${fmtMaybePct(item.revenueGrowthYoyPct, 1)}</td>
              <td>${fmtMaybePct(item.grossMarginPct, 1, false)}</td>
              <td class="${maybeCls(item.operatingMarginPct)}">${fmtMaybePct(item.operatingMarginPct, 1)}</td>
              <td class="${maybeCls(item.freeCashFlowMarginPct)}">${fmtMaybePct(item.freeCashFlowMarginPct, 1)}</td>
              <td>${fmtCompact(item.netCash)}</td>
            </tr>
          `).join(""),
        };
      }
      if (detailView === "positioning") {
        return {
          headers: ["Ticker", "Return", "Short %", "Days", "Short vol", "P/C OI", "IV", "Inst QoQ"],
          rows: rows.map((item) => `
            <tr class="ticker-row ${item.ticker === selectedTicker ? "active" : ""}" data-ticker="${item.ticker}">
              <td><span class="ticker">${escapeHtml(item.ticker)}</span><div class="muted">${escapeHtml(item.name)}</div></td>
              <td class="${cls(item.returnPct)}">${fmtPct(item.returnPct, 2)}</td>
              <td class="warn">${fmtMaybePct(item.shortPctFloat, 1, false)}</td>
              <td>${isNum(item.daysToCover) ? item.daysToCover.toFixed(2) : "n/a"}</td>
              <td>${fmtMaybePct(item.shortVolumeRatioPct, 1, false)}</td>
              <td>${isNum(item.putCallOpenInterestRatio) ? item.putCallOpenInterestRatio.toFixed(2) : "n/a"}</td>
              <td>${fmtMaybePct(item.optionsIvPct, 0, false)}</td>
              <td class="${maybeCls(item.institutionalSharesChangedQoqPct)}">${fmtMaybePct(item.institutionalSharesChangedQoqPct, 1)}</td>
            </tr>
          `).join(""),
        };
      }
      return {
        headers: ["Ticker", "Return", "20D", "Cur DD", "Rebound", "Beta QQQ", "Path"],
        rows: rows.map((item) => `
          <tr class="ticker-row ${item.ticker === selectedTicker ? "active" : ""}" data-ticker="${item.ticker}">
            <td><span class="ticker">${escapeHtml(item.ticker)}</span><div class="muted">${escapeHtml(item.note || item.name)}</div></td>
            <td class="${cls(item.returnPct)}">${fmtPct(item.returnPct, 2)}</td>
            <td class="${maybeCls(item.return20dPct)}">${fmtMaybePct(item.return20dPct, 1)}</td>
            <td class="${maybeCls(item.currentDrawdownPct)}">${fmtMaybePct(item.currentDrawdownPct, 1)}</td>
            <td>${fmtMaybePct(item.reboundFromLowPct, 1, false)}</td>
            <td>${isNum(item.betaVsQqq) ? item.betaVsQqq.toFixed(2) : "n/a"}</td>
            <td>${makeSparkline(item.series, m.color)}</td>
          </tr>
        `).join(""),
      };
    }

    function renderDetail() {
      const m = byBasket.get(selectedBasket);
      const rows = DATA.constituents[selectedBasket] || [];
      const table = detailTable(rows, m);
      const headers = table.headers.map((header) => `<th>${header}</th>`).join("");
      document.getElementById("detail-panel").innerHTML = `
        <div class="detail-hero" style="border-top: 3px solid ${m.color}">
          <div class="detail-name">
            <h2>${escapeHtml(m.label)}</h2>
            <div class="rank-pill">Rank ${m.rank}</div>
          </div>
          <div class="detail-return ${cls(m.returnPct)}">${fmtPct(m.returnPct, 2)}</div>
          <div class="mini-stats">
            <div class="mini-stat"><span>20D</span><strong class="${maybeCls(m.return20dPct)}">${fmtMaybePct(m.return20dPct, 1)}</strong></div>
            <div class="mini-stat"><span>Current DD</span><strong class="${maybeCls(m.currentDrawdownPct)}">${fmtMaybePct(m.currentDrawdownPct, 1)}</strong></div>
            <div class="mini-stat"><span>Rebound</span><strong>${fmtMaybePct(m.reboundFromLowPct, 1, false)}</strong></div>
            <div class="mini-stat"><span>Short %</span><strong class="warn">${fmtMaybePct(m.shortPctFloat, 1, false)}</strong></div>
            <div class="mini-stat"><span>Inst QoQ</span><strong class="${maybeCls(m.institutionalSharesChangedQoqPct)}">${fmtMaybePct(m.institutionalSharesChangedQoqPct, 1)}</strong></div>
            <div class="mini-stat"><span>Rev YoY</span><strong class="${maybeCls(m.revenueGrowthYoyPct)}">${fmtMaybePct(m.revenueGrowthYoyPct, 1)}</strong></div>
          </div>
          <div class="detail-thesis">${setupNarrative(m)}</div>
        </div>
        <div class="profile-grid">
          <div class="profile-card"><span>Price risk</span><strong>${fmtPlainPct(m.annualizedVolPct, 1)} vol</strong><small>Beta QQQ ${isNum(m.betaVsQqq) ? m.betaVsQqq.toFixed(2) : "n/a"} / max DD ${fmtPlainPct(m.maxDrawdownPct, 1)}</small></div>
          <div class="profile-card"><span>Fundamentals</span><strong>${fmtMaybePct(m.freeCashFlowMarginPct, 1)} FCF</strong><small>${fmtMaybePct(m.fundamentalsCoveragePct, 0, false)} coverage / gross ${fmtMaybePct(m.grossMarginPct, 1, false)}</small></div>
          <div class="profile-card"><span>Options</span><strong>${fmtMaybePct(m.optionsIvPct, 0, false)} IV</strong><small>Put/call OI ${isNum(m.putCallOpenInterestRatio) ? m.putCallOpenInterestRatio.toFixed(2) : "n/a"} / short vol ${fmtMaybePct(m.shortVolumeRatioPct, 1, false)}</small></div>
          <div class="profile-card"><span>Ownership</span><strong>${fmtMaybePct(m.institutionalOwnershipPct, 1, false)} inst</strong><small>${fmtMaybePct(m.institutionalCoveragePct, 0, false)} coverage / ${isNum(m.institutionalInvestorCount) ? m.institutionalInvestorCount.toFixed(0) : "n/a"} median investors</small></div>
        </div>
        <div class="panel-header">
          <div>
            <h2 class="panel-title">Ticker drilldown</h2>
            <div class="panel-note"><span class="coverage-badge">Short ${fmtMaybePct(m.shortInterestCoveragePct, 0, false)} coverage</span> <span class="coverage-badge">Institutional ${fmtMaybePct(m.institutionalCoveragePct, 0, false)} coverage</span></div>
          </div>
        </div>
        <div class="detail-tabs">
          <button data-detail-view="positioning" aria-pressed="${detailView === "positioning" ? "true" : "false"}">Positioning</button>
          <button data-detail-view="fundamentals" aria-pressed="${detailView === "fundamentals" ? "true" : "false"}">Fundamentals</button>
          <button data-detail-view="price" aria-pressed="${detailView === "price" ? "true" : "false"}">Price</button>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr>${headers}</tr></thead>
            <tbody>${table.rows}</tbody>
          </table>
        </div>
      `;
      document.querySelectorAll("[data-detail-view]").forEach((button) => {
        button.addEventListener("click", () => {
          detailView = button.dataset.detailView;
          renderDetail();
        });
      });
      document.querySelectorAll("#detail-panel .ticker-row").forEach((row) => {
        row.addEventListener("click", () => setSelectedTicker(row.dataset.ticker));
      });
    }

    function renderControls() {
      document.querySelectorAll("[data-view]").forEach((button) => {
        button.setAttribute("aria-pressed", button.dataset.view === lineView ? "true" : "false");
      });
      document.querySelectorAll("[data-sort]").forEach((button) => {
        button.setAttribute("aria-pressed", button.dataset.sort === sortKey ? "true" : "false");
      });
      document.querySelectorAll("[data-signal]").forEach((button) => {
        button.setAttribute("aria-pressed", button.dataset.signal === signalSort ? "true" : "false");
      });
      document.querySelectorAll("[data-ticker-filter]").forEach((button) => {
        button.setAttribute("aria-pressed", button.dataset.tickerFilter === tickerFilter ? "true" : "false");
      });
      document.querySelectorAll("[data-ticker-sort]").forEach((button) => {
        button.setAttribute("aria-pressed", button.dataset.tickerSort === tickerSort ? "true" : "false");
      });
      const tickerSearchInput = document.getElementById("ticker-search");
      if (tickerSearchInput && tickerSearchInput.value !== tickerSearch) {
        tickerSearchInput.value = tickerSearch;
      }
    }

    function renderAll() {
      const steps = [
        ["controls", renderControls],
        ["leaderboard", renderLeaderboard],
        ["scatter", renderScatter],
        ["performance", renderPerformance],
        ["signals", renderSignalBoard],
        ["ownership", renderOwnershipMap],
        ["fundamentals", renderFundamentalsMap],
        ["heatmap", renderHeatmap],
        ["drawdown", renderDrawdown],
        ["breadth", renderBreadth],
        ["sector list", renderSectorList],
        ["attribution", renderBasketAttribution],
        ["ticker explorer", renderTickerExplorer],
        ["ticker profile", renderTickerProfile],
        ["detail", renderDetail],
      ];
      window.dashboardErrors = [];
      window.dashboardSteps = [];
      steps.forEach(([name, fn]) => {
        window.dashboardSteps.push(name);
        document.body.dataset.dashboardSteps = window.dashboardSteps.join(",");
        try {
          fn();
        } catch (error) {
          window.dashboardErrors.push({ name, message: error.message });
          document.body.dataset.dashboardErrors = window.dashboardErrors.map((item) => `${item.name}: ${item.message}`).join(" | ");
          console.error(`Dashboard render failed: ${name}`, error);
        }
      });
    }

    document.querySelectorAll("[data-view]").forEach((button) => {
      button.addEventListener("click", () => {
        lineView = button.dataset.view;
        renderAll();
      });
    });

    document.querySelectorAll("[data-sort]").forEach((button) => {
      button.addEventListener("click", () => {
        sortKey = button.dataset.sort;
        renderAll();
      });
    });

    document.querySelectorAll("[data-signal]").forEach((button) => {
      button.addEventListener("click", () => {
        signalSort = button.dataset.signal;
        renderAll();
      });
    });

    document.querySelectorAll("[data-ticker-filter]").forEach((button) => {
      button.addEventListener("click", () => {
        tickerFilter = button.dataset.tickerFilter;
        renderAll();
      });
    });

    document.querySelectorAll("[data-ticker-sort]").forEach((button) => {
      button.addEventListener("click", () => {
        tickerSort = button.dataset.tickerSort;
        renderAll();
      });
    });

    document.getElementById("ticker-search").addEventListener("input", (event) => {
      tickerSearch = event.target.value;
      renderControls();
      renderTickerExplorer();
    });

    renderHeader();
    renderAll();
  </script>
</body>
</html>
"""


REDESIGNED_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Market Basket Dashboard</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b0b09;
      --surface: #141410;
      --surface-2: #1b1b16;
      --surface-3: #24231d;
      --line: rgb(245 240 222 / 0.12);
      --line-strong: rgb(245 240 222 / 0.24);
      --text: #f5f0e2;
      --muted: #aaa79a;
      --faint: #706e63;
      --good: #58d6b0;
      --bad: #ef6f82;
      --warn: #e8c75f;
      --blue: #72b9ff;
      --radius: 8px;
      --mono: "SFMono-Regular", ui-monospace, Menlo, Consolas, monospace;
      --sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background:
        linear-gradient(180deg, #171710 0, #0b0b09 760px),
        repeating-linear-gradient(90deg, rgb(255 255 255 / 0.025) 0 1px, transparent 1px 88px);
      color: var(--text);
      font-family: var(--sans);
      font-variant-numeric: tabular-nums;
    }

    button, input { font: inherit; }

    button {
      color: inherit;
      cursor: pointer;
    }

    .app {
      width: min(1440px, calc(100% - 32px));
      margin: 0 auto;
      padding: 22px 0 48px;
    }

    .top {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 18px;
      align-items: end;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--line);
    }

    h1 {
      margin: 0;
      font-size: 2rem;
      line-height: 1.05;
      letter-spacing: 0;
    }

    .subhead {
      margin: 8px 0 0;
      color: var(--muted);
      max-width: 780px;
      line-height: 1.45;
      font-size: 0.92rem;
    }

    .nav {
      display: flex;
      gap: 6px;
      padding: 5px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgb(0 0 0 / 0.2);
      white-space: nowrap;
    }

    .nav button,
    .seg button {
      min-height: 32px;
      padding: 7px 12px;
      border: 0;
      border-radius: 999px;
      background: transparent;
      color: var(--muted);
      font-size: 0.78rem;
      font-weight: 850;
    }

    .nav button.active,
    .seg button.active {
      color: var(--text);
      background: rgb(245 240 222 / 0.12);
    }

    .context {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin: 14px 0;
    }

    .chip {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      min-height: 28px;
      padding: 5px 9px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgb(255 255 255 / 0.035);
      color: var(--muted);
      font-size: 0.72rem;
      font-weight: 850;
      text-transform: uppercase;
    }

    .chip strong { color: var(--text); }

    .sector-rail {
      display: grid;
      gap: 8px;
      margin: 0 0 14px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: rgb(255 255 255 / 0.025);
    }

    .rail-label {
      color: var(--muted);
      font-size: 0.68rem;
      font-weight: 950;
      text-transform: uppercase;
    }

    .sector-buttons,
    .compare-buttons {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
    }

    .sector-chip,
    .compare-chip {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      min-height: 31px;
      padding: 6px 9px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgb(255 255 255 / 0.025);
      color: var(--muted);
      font-size: 0.72rem;
      font-weight: 850;
    }

    .sector-chip.active,
    .compare-chip.active,
    .seg button.active {
      color: var(--text);
      border-color: var(--line-strong);
      background: rgb(245 240 222 / 0.12);
      box-shadow: inset 0 -2px 0 var(--active-color, var(--warn));
    }

    .compare-chip.in-compare {
      color: var(--text);
      border-color: var(--active-color, var(--line-strong));
      background: rgb(255 255 255 / 0.065);
    }

    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: currentColor;
      flex: 0 0 auto;
    }

    .kpis {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }

    .kpi,
    .panel,
    .callout {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: linear-gradient(180deg, rgb(255 255 255 / 0.055), rgb(255 255 255 / 0.025));
      box-shadow: 0 18px 44px rgb(0 0 0 / 0.22);
    }

    .kpi {
      min-height: 106px;
      padding: 14px;
    }

    .label {
      color: var(--muted);
      font-size: 0.68rem;
      font-weight: 900;
      text-transform: uppercase;
    }

    .value {
      margin-top: 10px;
      font-size: 1.55rem;
      line-height: 1;
      font-weight: 950;
    }

    .hint {
      margin-top: 8px;
      color: var(--muted);
      font-size: 0.78rem;
      line-height: 1.35;
    }

    .view { display: none; }
    .view.active { display: block; }

    .grid-market {
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(360px, 0.8fr);
      gap: 12px;
    }

    .grid-two {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(360px, 0.78fr);
      gap: 12px;
    }

    .panel-head {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      min-height: 58px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
    }

    .panel-title {
      margin: 0;
      font-size: 0.92rem;
      font-weight: 950;
    }

    .panel-note {
      margin-top: 3px;
      color: var(--muted);
      font-size: 0.75rem;
      line-height: 1.35;
    }

    .panel-body { padding: 14px; }
    .panel-body.flush { padding: 0; }

    .chart {
      min-height: 0;
    }

    svg {
      display: block;
      width: 100%;
      height: auto;
    }

    .axis,
    .svg-label {
      fill: var(--muted);
      font-size: 11px;
      font-weight: 750;
    }

    .grid-line {
      stroke: rgb(245 240 222 / 0.11);
      shape-rendering: crispEdges;
    }

    .zero-line {
      stroke: rgb(245 240 222 / 0.32);
      stroke-width: 1.2;
    }

    .line-hit,
    .line-label,
    svg [data-basket] {
      cursor: pointer;
    }

    .rank-list,
    .sector-list,
    .attribution-list {
      display: grid;
      gap: 8px;
      padding: 12px;
    }

    .row {
      width: 100%;
      display: grid;
      grid-template-columns: 32px minmax(0, 1fr) 86px 80px;
      align-items: center;
      gap: 10px;
      min-height: 52px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: rgb(255 255 255 / 0.025);
      color: inherit;
      cursor: pointer;
      font: inherit;
      text-align: left;
    }

    .row:hover,
    tr:hover {
      background: rgb(255 255 255 / 0.045);
      border-color: var(--line-strong);
    }

    .row.active,
    tr.active {
      background: rgb(255 255 255 / 0.055);
      border-color: var(--line-strong);
      box-shadow: inset 3px 0 0 var(--active-color, var(--warn));
    }

    .rank {
      color: var(--faint);
      font-family: var(--mono);
      font-size: 0.75rem;
      font-weight: 850;
    }

    .name {
      min-width: 0;
      font-weight: 950;
      overflow-wrap: anywhere;
    }

    .sub {
      margin-top: 3px;
      color: var(--muted);
      font-size: 0.72rem;
      line-height: 1.3;
    }

    .num {
      text-align: right;
      font-family: var(--mono);
      font-weight: 900;
      font-size: 0.82rem;
      white-space: nowrap;
    }

    .pos { color: var(--good); }
    .neg { color: var(--bad); }
    .warn { color: var(--warn); }
    .muted { color: var(--muted); }

    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      padding: 12px;
      border-bottom: 1px solid var(--line);
    }

    .search {
      flex: 1 1 240px;
      min-height: 36px;
      padding: 8px 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgb(0 0 0 / 0.22);
      color: var(--text);
      outline: none;
    }

    .search:focus {
      border-color: var(--line-strong);
      box-shadow: 0 0 0 3px rgb(114 185 255 / 0.12);
    }

    .seg {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      padding: 4px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgb(0 0 0 / 0.18);
    }

    .compare-strip {
      display: grid;
      gap: 8px;
      padding: 12px 14px 0;
    }

    .compare-summary {
      color: var(--muted);
      font-size: 0.74rem;
      font-weight: 820;
    }

    .panel-stack {
      display: grid;
      gap: 12px;
    }

    .advanced-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .wide {
      grid-column: 1 / -1;
    }

    .score-list,
    .breadth-list {
      display: grid;
      gap: 8px;
      padding: 12px;
    }

    .score-row {
      width: 100%;
      display: grid;
      grid-template-columns: 32px minmax(0, 1fr) minmax(120px, 0.65fr) 72px 72px 72px;
      align-items: center;
      gap: 10px;
      min-height: 54px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: rgb(255 255 255 / 0.025);
      color: inherit;
      cursor: pointer;
      font: inherit;
      text-align: left;
    }

    .score-row:hover,
    .breadth-row:hover {
      background: rgb(255 255 255 / 0.045);
      border-color: var(--line-strong);
    }

    .score-row.active,
    .breadth-row.active {
      background: rgb(255 255 255 / 0.055);
      border-color: var(--line-strong);
      box-shadow: inset 3px 0 0 var(--active-color, var(--warn));
    }

    .score-track {
      height: 9px;
      border-radius: 999px;
      background: rgb(255 255 255 / 0.08);
      overflow: hidden;
    }

    .score-bar {
      width: var(--score);
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--warn), var(--good));
    }

    .breadth-row {
      width: 100%;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto 52px;
      align-items: center;
      gap: 10px;
      min-height: 42px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: rgb(255 255 255 / 0.025);
      color: inherit;
      cursor: pointer;
      font: inherit;
      text-align: left;
    }

    .breadth-dots {
      display: flex;
      gap: 4px;
    }

    .breadth-dots i {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: rgb(255 255 255 / 0.12);
    }

    .breadth-dots i.on {
      background: var(--active-color, var(--good));
    }

    .table-wrap {
      overflow: auto;
      max-height: 560px;
    }

    table {
      width: 100%;
      min-width: 1020px;
      border-collapse: collapse;
    }

    th,
    td {
      padding: 9px 10px;
      border-bottom: 1px solid rgb(245 240 222 / 0.08);
      text-align: left;
      white-space: nowrap;
      font-size: 0.78rem;
    }

    th {
      position: sticky;
      top: 0;
      z-index: 2;
      background: rgb(20 20 16 / 0.98);
      color: var(--muted);
      font-size: 0.66rem;
      font-weight: 950;
      text-transform: uppercase;
      cursor: pointer;
    }

    td.num { font-size: 0.78rem; }
    tr { cursor: pointer; }

    .tag-row {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
      margin-top: 6px;
    }

    .tag {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      min-height: 20px;
      padding: 3px 7px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      font-size: 0.66rem;
      font-weight: 850;
    }

    .profile {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
      gap: 0;
    }

    .profile-main {
      padding: 16px;
      border-right: 1px solid var(--line);
    }

    .profile-side {
      padding: 14px;
    }

    .profile-title {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: baseline;
      margin-bottom: 10px;
    }

    .profile-title h2 {
      margin: 0;
      font-size: 1.35rem;
      line-height: 1.1;
    }

    .metric-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .mini {
      min-height: 72px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: rgb(255 255 255 / 0.025);
    }

    .mini span {
      display: block;
      color: var(--muted);
      font-size: 0.66rem;
      font-weight: 900;
      text-transform: uppercase;
    }

    .mini strong {
      display: block;
      margin-top: 8px;
      font-size: 1rem;
    }

    .bar-track {
      height: 10px;
      border-radius: 999px;
      background: rgb(255 255 255 / 0.08);
      overflow: hidden;
    }

    .bar-fill {
      width: var(--bar);
      height: 100%;
      border-radius: inherit;
      background: var(--fill, var(--good));
    }

    .heat {
      overflow: auto;
    }

    .heat table {
      min-width: 980px;
    }

    .cell-heat {
      color: var(--text);
      font-family: var(--mono);
      font-weight: 900;
      text-align: right;
    }

    .callout {
      padding: 14px;
      color: #d8d1bc;
      font-size: 0.84rem;
      line-height: 1.45;
    }

    @media (max-width: 1080px) {
      .top,
      .grid-market,
      .grid-two,
      .advanced-grid,
      .profile {
        grid-template-columns: 1fr;
      }

      .nav {
        width: 100%;
        overflow-x: auto;
      }

      .profile-main {
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }
    }

    @media (max-width: 760px) {
      .app {
        width: min(100% - 20px, 720px);
        padding-top: 14px;
      }

      .kpis,
      .metric-grid {
        grid-template-columns: 1fr;
      }

      h1 { font-size: 1.65rem; }

      .row {
        grid-template-columns: 28px minmax(0, 1fr) 76px;
      }

      .row .num:last-child { display: none; }

      .score-row {
        grid-template-columns: 28px minmax(0, 1fr) 72px;
      }

      .score-row > :nth-child(n+4) { display: none; }
    }
  </style>
</head>
<body>
  <main class="app">
    <header class="top">
      <div>
        <h1>Market basket dashboard</h1>
        <p class="subhead">A cleaner workflow for sector leadership, sector drilldown, and ticker research without making you fight a wall of charts.</p>
      </div>
      <nav class="nav" aria-label="Dashboard views">
        <button data-view="market" class="active">Market Map</button>
        <button data-view="sector">Sector Drilldown</button>
        <button data-view="tickers">Ticker Explorer</button>
        <button data-view="advanced">Advanced</button>
      </nav>
    </header>

    <div class="context" id="context"></div>
    <section class="sector-rail" aria-label="Sector selector">
      <div class="rail-label">Current sector</div>
      <div class="sector-buttons" id="sector-rail"></div>
    </section>
    <section class="kpis" id="kpis"></section>

    <section class="view active" id="view-market">
      <div class="grid-market">
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">$100 indexed performance</h2>
              <div class="panel-note">Compare leaders, all sectors, or a custom basket set. Labels and chips are selectable.</div>
            </div>
            <div class="seg">
              <button data-line-mode="leaders" class="active">Top 5</button>
              <button data-line-mode="all">All sectors</button>
              <button data-line-mode="custom">Custom</button>
            </div>
            <div class="seg">
              <button data-benchmark="SPY">SPY</button>
              <button data-benchmark="QQQ">QQQ</button>
              <button data-benchmark="BTC-USD">BTC</button>
            </div>
          </div>
          <div class="compare-strip">
            <div class="compare-summary" id="compare-summary"></div>
            <div class="compare-buttons" id="compare-picker"></div>
          </div>
          <div class="panel-body chart" id="market-line"></div>
        </article>
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">Sector leaderboard</h2>
              <div class="panel-note">Return, setup, and short pressure in one scan.</div>
            </div>
          </div>
          <div class="rank-list" id="leaderboard"></div>
        </article>
      </div>
      <div class="grid-two" style="margin-top:12px">
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">Risk / return</h2>
              <div class="panel-note">Cleaner map: return versus realized volatility.</div>
            </div>
          </div>
          <div class="panel-body chart" id="risk-return"></div>
        </article>
        <aside class="callout" id="market-note"></aside>
      </div>
    </section>

    <section class="view" id="view-sector">
      <section class="sector-rail" aria-label="Sector drilldown selector">
        <div class="rail-label">Drilldown sector</div>
        <div class="sector-buttons" id="sector-rail-local"></div>
      </section>
      <div class="grid-two">
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title" id="sector-title">Sector</h2>
              <div class="panel-note">Path, attribution, and constituent setup.</div>
            </div>
          </div>
          <div class="panel-body chart" id="sector-line"></div>
        </article>
        <aside class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">Sector summary</h2>
              <div class="panel-note">Only the fields that change the read.</div>
            </div>
          </div>
          <div class="panel-body" id="sector-summary"></div>
        </aside>
      </div>
      <div class="grid-two" style="margin-top:12px">
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">Return attribution</h2>
              <div class="panel-note">Equal-weight contribution by ticker.</div>
            </div>
          </div>
          <div class="attribution-list" id="attribution"></div>
        </article>
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">Sector constituents</h2>
              <div class="panel-note">Sortable ticker detail by price action, positioning, or fundamentals.</div>
            </div>
          </div>
          <div class="toolbar">
            <div class="seg">
              <button data-sector-tab="price" class="active">Price Action</button>
              <button data-sector-tab="positioning">Positioning</button>
              <button data-sector-tab="fundamentals">Fundamentals</button>
            </div>
          </div>
          <div class="table-wrap" id="sector-table"></div>
        </article>
      </div>
    </section>

    <section class="view" id="view-tickers">
      <article class="panel">
        <div class="panel-head">
          <div>
            <h2 class="panel-title">Ticker explorer</h2>
            <div class="panel-note">Global screen across all configured names.</div>
          </div>
        </div>
        <div class="toolbar">
          <input id="ticker-search" class="search" type="search" placeholder="Search ticker or company">
          <div class="seg" id="ticker-filters">
            <button data-filter="all" class="active">All</button>
            <button data-filter="selected">Selected sector</button>
            <button data-filter="momentum">Momentum</button>
            <button data-filter="squeeze">Squeeze</button>
            <button data-filter="institutional">Inst bid</button>
            <button data-filter="quality">Quality</button>
            <button data-filter="rebound">Rebound</button>
            <button data-filter="risk">High risk</button>
          </div>
        </div>
        <div class="table-wrap" id="ticker-table"></div>
      </article>
      <article class="panel" style="margin-top:12px">
        <div class="panel-head">
          <div>
            <h2 class="panel-title">Ticker profile</h2>
            <div class="panel-note">Ticker versus basket and QQQ, with the key setup fields.</div>
          </div>
        </div>
        <div id="ticker-profile"></div>
      </article>
    </section>

    <section class="view" id="view-advanced">
      <div class="advanced-grid">
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">Signal board</h2>
              <div class="panel-note">Composite, squeeze, sponsor, and fundamentals scores.</div>
            </div>
            <div class="seg">
              <button data-signal="setupScore" class="active">Composite</button>
              <button data-signal="squeezeScore">Squeeze</button>
              <button data-signal="sponsorScore">Sponsors</button>
              <button data-signal="fundamentalScore">Fundamentals</button>
            </div>
          </div>
          <div class="score-list" id="signal-board"></div>
        </article>
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">Short interest vs institutional bid</h2>
              <div class="panel-note">True short interest against institutional shares changed QoQ.</div>
            </div>
          </div>
          <div class="panel-body chart" id="ownership-chart"></div>
        </article>
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">Fundamental quality map</h2>
              <div class="panel-note">Revenue growth versus free-cash-flow margin.</div>
            </div>
          </div>
          <div class="panel-body chart" id="fundamentals-chart"></div>
        </article>
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">Drawdown discipline</h2>
              <div class="panel-note">Worst peak-to-trough decline during the window.</div>
            </div>
          </div>
          <div class="panel-body chart" id="drawdown-chart"></div>
        </article>
        <article class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">Breadth</h2>
              <div class="panel-note">Positive constituents out of each eight-name basket.</div>
            </div>
          </div>
          <div class="breadth-list" id="breadth-panel"></div>
        </article>
        <article class="panel wide">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">Factor heatmap</h2>
              <div class="panel-note">Dense scan across price, positioning, sponsorship, and fundamentals.</div>
            </div>
          </div>
          <div class="panel-body flush heat" id="heatmap"></div>
        </article>
      </div>
    </section>
  </main>

  <script type="application/json" id="dashboard-data">__DATA__</script>
  <script>
    const DATA = JSON.parse(document.getElementById("dashboard-data").textContent);
    const metrics = DATA.metrics.slice().sort((a, b) => a.rank - b.rank);
    const tickers = DATA.tickers.slice().sort((a, b) => b.returnPct - a.returnPct);
    const byBasket = new Map(metrics.map((m) => [m.basket, m]));
    const byTicker = new Map(tickers.map((t) => [t.ticker, t]));

    let view = "market";
    let selectedBasket = metrics[0].basket;
    let selectedTicker = (DATA.constituents[selectedBasket] || [])[0]?.ticker || tickers[0]?.ticker;
    let basketWasClicked = false;
    let tickerWasClicked = false;
    let lineMode = "leaders";
    let compareBaskets = new Set(metrics.slice(0, 5).map((m) => m.basket));
    let benchmarkToggles = { SPY: false, QQQ: false, "BTC-USD": false };
    let sectorTab = "price";
    let sectorSort = "returnPct";
    let signalSort = "setupScore";
    let tickerFilter = "all";
    let tickerSort = "returnPct";
    let tickerSearch = "";

    const isNum = (v) => Number.isFinite(v);
    const cls = (v) => !isNum(v) ? "muted" : v >= 0 ? "pos" : "neg";
    const fmtPct = (v, d = 1) => !isNum(v) ? "n/a" : `${v >= 0 ? "+" : ""}${v.toFixed(d)}%`;
    const fmtPlainPct = (v, d = 1) => !isNum(v) ? "n/a" : `${v.toFixed(d)}%`;
    const fmtRatio = (v, d = 2) => !isNum(v) ? "n/a" : `${v.toFixed(d)}x`;
    const fmtMoney = (v) => {
      if (!isNum(v)) return "n/a";
      const sign = v < 0 ? "-" : "";
      const abs = Math.abs(v);
      if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(1)}T`;
      if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(1)}B`;
      if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
      return `${sign}$${abs.toFixed(0)}`;
    };
    const esc = (v) => String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
    const clamp = (v, min = 0, max = 1) => Math.max(min, Math.min(max, v));
    const scale = (v, inMin, inMax, outMin, outMax) => inMax === inMin ? (outMin + outMax) / 2 : outMin + ((v - inMin) / (inMax - inMin)) * (outMax - outMin);
    const pathFrom = (points) => points.length ? `M ${points.map((p) => `${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" L ")}` : "";

    function valuesFor(rows, key) {
      return rows.map((row) => row[key]).filter(isNum);
    }

    function norm(rows, value, key, high = true, fallback = 0.45) {
      if (!isNum(value)) return fallback;
      const vals = valuesFor(rows, key);
      if (vals.length < 2) return fallback;
      const min = Math.min(...vals);
      const max = Math.max(...vals);
      if (min === max) return fallback;
      const raw = (value - min) / (max - min);
      return high ? raw : 1 - raw;
    }

    function avg(parts) {
      const valid = parts.filter(isNum);
      return valid.length ? valid.reduce((sum, value) => sum + value, 0) / valid.length : 0.45;
    }

    function hydrateScores() {
      metrics.forEach((m) => { m.absDrawdownPct = Math.abs(m.maxDrawdownPct); });
      tickers.forEach((t) => { t.absDrawdownPct = Math.abs(t.maxDrawdownPct); });
      metrics.forEach((m) => {
        m.momentumScore = avg([norm(metrics, m.return20dPct, "return20dPct"), norm(metrics, m.return5dPct, "return5dPct"), norm(metrics, m.reboundFromLowPct, "reboundFromLowPct"), norm(metrics, m.currentDrawdownPct, "currentDrawdownPct")]);
        m.squeezeScore = avg([norm(metrics, m.shortPctFloat, "shortPctFloat"), norm(metrics, m.optionsIvPct, "optionsIvPct"), norm(metrics, m.reboundFromLowPct, "reboundFromLowPct"), norm(metrics, m.return20dPct, "return20dPct")]);
        m.sponsorScore = avg([norm(metrics, m.institutionalSharesChangedQoqPct, "institutionalSharesChangedQoqPct"), norm(metrics, m.institutionalOwnershipPct, "institutionalOwnershipPct"), isNum(m.institutionalCoveragePct) ? clamp(m.institutionalCoveragePct / 100) : 0.35]);
        m.fundamentalScore = avg([norm(metrics, m.revenueGrowthYoyPct, "revenueGrowthYoyPct"), norm(metrics, m.grossMarginPct, "grossMarginPct"), norm(metrics, m.operatingMarginPct, "operatingMarginPct"), norm(metrics, m.freeCashFlowMarginPct, "freeCashFlowMarginPct")]);
        m.setupScore = clamp((m.momentumScore * 0.33) + (m.squeezeScore * 0.25) + (m.sponsorScore * 0.23) + (m.fundamentalScore * 0.19));
      });
      tickers.forEach((t) => {
        t.momentumScore = avg([norm(tickers, t.return20dPct, "return20dPct"), norm(tickers, t.return10dPct, "return10dPct"), norm(tickers, t.return5dPct, "return5dPct"), norm(tickers, t.reboundFromLowPct, "reboundFromLowPct")]);
        t.squeezeScore = avg([norm(tickers, t.shortPctFloat, "shortPctFloat"), norm(tickers, t.optionsIvPct, "optionsIvPct"), norm(tickers, t.return20dPct, "return20dPct"), norm(tickers, t.currentDrawdownPct, "currentDrawdownPct")]);
        t.sponsorScore = avg([norm(tickers, t.institutionalSharesChangedQoqPct, "institutionalSharesChangedQoqPct"), norm(tickers, t.institutionalOwnershipPct, "institutionalOwnershipPct"), norm(tickers, t.institutionalInvestorCount, "institutionalInvestorCount")]);
        t.fundamentalScore = avg([norm(tickers, t.revenueGrowthYoyPct, "revenueGrowthYoyPct"), norm(tickers, t.grossMarginPct, "grossMarginPct"), norm(tickers, t.operatingMarginPct, "operatingMarginPct"), norm(tickers, t.freeCashFlowMarginPct, "freeCashFlowMarginPct")]);
        t.setupScore = clamp((t.momentumScore * 0.33) + (t.squeezeScore * 0.24) + (t.sponsorScore * 0.22) + (t.fundamentalScore * 0.21));
      });
    }

    hydrateScores();

    function sectorLabel(m) {
      return `<span class="dot" style="color:${m.color}"></span>${esc(m.short)}`;
    }

    function setBasket(basket, targetView = view) {
      selectedBasket = basket;
      basketWasClicked = true;
      const top = (DATA.constituents[basket] || [])[0];
      if (top) selectedTicker = top.ticker;
      tickerWasClicked = false;
      view = targetView;
      render();
    }

    function toggleCompareBasket(basket) {
      lineMode = "custom";
      if (compareBaskets.has(basket) && compareBaskets.size > 1) {
        compareBaskets.delete(basket);
      } else {
        compareBaskets.add(basket);
      }
      selectedBasket = basket;
      basketWasClicked = true;
      render();
    }

    function renderSectorButtons(targetId, targetView = view) {
      const el = document.getElementById(targetId);
      if (!el) return;
      el.innerHTML = metrics.map((m) => `
        <button class="sector-chip ${m.basket === selectedBasket ? "active" : ""}" data-sector-pick="${m.basket}" style="--active-color:${m.color}" title="Select ${esc(m.label)}">
          ${sectorLabel(m)} <span>${fmtPct(m.returnPct)}</span>
        </button>
      `).join("");
      el.querySelectorAll("[data-sector-pick]").forEach((button) => button.addEventListener("click", () => setBasket(button.dataset.sectorPick, targetView)));
    }

    function renderComparePicker() {
      const picker = document.getElementById("compare-picker");
      const summary = document.getElementById("compare-summary");
      if (!picker || !summary) return;
      picker.innerHTML = metrics.map((m) => `
        <button class="compare-chip ${m.basket === selectedBasket ? "active" : ""} ${compareBaskets.has(m.basket) ? "in-compare" : ""}" data-compare-basket="${m.basket}" style="--active-color:${m.color}" title="Toggle ${esc(m.label)} in custom comparison">
          ${sectorLabel(m)}
        </button>
      `).join("");
      const names = Array.from(compareBaskets).map((basket) => byBasket.get(basket)?.short).filter(Boolean);
      const benchmarks = Object.entries(benchmarkToggles).filter(([, enabled]) => enabled).map(([ticker]) => ticker === "BTC-USD" ? "BTC" : ticker);
      summary.textContent = `${lineMode === "custom" ? "Custom compare" : lineMode === "all" ? "All sectors" : "Top 5 leaders"}: ${names.join(", ")}${benchmarks.length ? ` / Benchmarks: ${benchmarks.join(", ")}` : ""}`;
      picker.querySelectorAll("[data-compare-basket]").forEach((button) => button.addEventListener("click", () => toggleCompareBasket(button.dataset.compareBasket)));
    }

    function setTicker(ticker) {
      const item = byTicker.get(ticker);
      if (!item) return;
      selectedTicker = ticker;
      tickerWasClicked = true;
      if (!item.baskets.some((b) => b.basket === selectedBasket) && item.baskets[0]) {
        selectedBasket = item.baskets[0].basket;
        basketWasClicked = true;
      }
      view = "tickers";
      render();
    }

    function renderShell() {
      document.querySelectorAll(".nav button").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
      document.querySelectorAll(".view").forEach((el) => el.classList.toggle("active", el.id === `view-${view}`));
      document.querySelectorAll("[data-line-mode]").forEach((button) => button.classList.toggle("active", button.dataset.lineMode === lineMode));
      document.querySelectorAll("[data-benchmark]").forEach((button) => button.classList.toggle("active", !!benchmarkToggles[button.dataset.benchmark]));
      document.querySelectorAll("[data-filter]").forEach((button) => button.classList.toggle("active", button.dataset.filter === tickerFilter));
      document.querySelectorAll("[data-sector-tab]").forEach((button) => button.classList.toggle("active", button.dataset.sectorTab === sectorTab));
      document.querySelectorAll("[data-signal]").forEach((button) => button.classList.toggle("active", button.dataset.signal === signalSort));
      const m = byBasket.get(selectedBasket);
      const t = byTicker.get(selectedTicker);
      document.getElementById("context").innerHTML = `
        <span class="chip"><strong>Window</strong> ${DATA.methodology.startDate} to ${DATA.methodology.endDate}</span>
        <span class="chip"><strong>Sector</strong> ${sectorLabel(m)}</span>
        <span class="chip"><strong>Ticker</strong> ${esc(t?.ticker || "")}</span>
        <span class="chip"><strong>Method</strong> Equal-weight</span>
      `;
      renderSectorButtons("sector-rail", view);
      renderSectorButtons("sector-rail-local", "sector");
      renderComparePicker();
    }

    function renderKpis() {
      const leader = metrics[0];
      const setup = metrics.slice().sort((a, b) => b.setupScore - a.setupScore)[0];
      const squeeze = metrics.slice().sort((a, b) => (b.shortPctFloat ?? -1) - (a.shortPctFloat ?? -1))[0];
      const inst = metrics.slice().sort((a, b) => (b.institutionalSharesChangedQoqPct ?? -999) - (a.institutionalSharesChangedQoqPct ?? -999))[0];
      document.getElementById("kpis").innerHTML = `
        <div class="kpi"><div class="label">Leader</div><div class="value pos">${esc(leader.short)} ${fmtPct(leader.returnPct)}</div><div class="hint">${fmtPct(leader.return20dPct)} over 20 sessions.</div></div>
        <div class="kpi"><div class="label">Best setup</div><div class="value">${esc(setup.short)} ${(setup.setupScore * 100).toFixed(0)}</div><div class="hint">Composite of trend, squeeze, sponsor, and fundamentals.</div></div>
        <div class="kpi"><div class="label">Short pressure</div><div class="value warn">${esc(squeeze.short)} ${fmtPlainPct(squeeze.shortPctFloat)}</div><div class="hint">Median true short interest / float.</div></div>
        <div class="kpi"><div class="label">Institutional bid</div><div class="value ${cls(inst.institutionalSharesChangedQoqPct)}">${esc(inst.short)} ${fmtPct(inst.institutionalSharesChangedQoqPct)}</div><div class="hint">Median shares changed QoQ.</div></div>
      `;
    }

    function lineChart(containerId, baskets, height = 380, benchmarks = []) {
      const width = 1000;
      const left = 56;
      const right = 100;
      const top = 26;
      const bottom = 40;
      const benchmarkColors = { SPY: "#c4c0b3", QQQ: "#72b9ff", "BTC-USD": "#f6b35b" };
      const basketSeries = baskets.map((basket) => {
        const meta = byBasket.get(basket);
        return meta ? { kind: "basket", id: basket, meta, label: meta.short, color: meta.color, rows: (DATA.daily[basket] || []).map((row) => ({ date: row.date, value: row.index })) } : null;
      }).filter((s) => s && s.rows.length);
      const benchmarkSeries = benchmarks.map((ticker) => {
        const bench = DATA.benchmarks?.[ticker];
        return bench ? { kind: "benchmark", id: ticker, label: ticker === "BTC-USD" ? "BTC" : ticker, color: benchmarkColors[ticker] || "#b9b5a8", rows: (bench.series || []).map((row) => ({ date: row.date, value: row.value })) } : null;
      }).filter((s) => s && s.rows.length);
      const series = [...basketSeries, ...benchmarkSeries];
      const allValues = series.flatMap((s) => s.rows.map((row) => row.value));
      const dates = Array.from(new Set(series.flatMap((s) => s.rows.map((row) => row.date)))).sort();
      const idx = new Map(dates.map((date, i) => [date, i]));
      const minY = Math.floor((Math.min(...allValues, 94) - 4) / 10) * 10;
      const maxY = Math.ceil((Math.max(...allValues, 106) + 4) / 10) * 10;
      const x = (date) => scale(idx.get(date), 0, dates.length - 1, left, width - right);
      const y = (value) => scale(value, minY, maxY, height - bottom, top);
      let svg = `<svg viewBox="0 0 ${width} ${height}" aria-label="Indexed basket lines">`;
      for (let tick = minY; tick <= maxY; tick += 10) {
        svg += `<line class="grid-line" x1="${left}" y1="${y(tick)}" x2="${width - right}" y2="${y(tick)}"></line><text class="svg-label" x="${left - 8}" y="${y(tick) + 4}" text-anchor="end">${tick}</text>`;
      }
      svg += `<line class="zero-line" x1="${left}" y1="${y(100)}" x2="${width - right}" y2="${y(100)}"></line>`;
      series.forEach((s) => {
        const points = s.rows.map((row) => [x(row.date), y(row.value)]);
        const last = points[points.length - 1];
        const selected = s.kind === "basket" && (series.length === 1 || s.id === selectedBasket);
        const dash = s.kind === "benchmark" ? `stroke-dasharray="5 5"` : "";
        svg += `<path d="${pathFrom(points)}" fill="none" stroke="${s.color}" stroke-width="${selected ? 4 : s.kind === "benchmark" ? 1.8 : 2.2}" ${dash} stroke-linecap="round" stroke-linejoin="round" opacity="${selected ? 1 : s.kind === "benchmark" ? 0.68 : 0.62}"></path>`;
        if (s.kind === "basket") svg += `<path data-basket="${s.id}" class="line-hit" d="${pathFrom(points)}" fill="none" stroke="transparent" stroke-width="18"></path>`;
        svg += `<circle cx="${last[0]}" cy="${last[1]}" r="${selected ? 5 : 3.7}" fill="${s.color}"></circle>`;
        svg += `<text ${s.kind === "basket" ? `data-basket="${s.id}" class="line-label"` : ""} x="${width - right + 10}" y="${last[1] + 4}" fill="${s.color}" font-size="12" font-weight="900">${esc(s.label)}</text>`;
      });
      [0, 0.5, 1].forEach((pct) => {
        const date = dates[Math.round((dates.length - 1) * pct)];
        if (date) svg += `<text class="svg-label" x="${x(date)}" y="${height - 12}" text-anchor="middle">${date.slice(5)}</text>`;
      });
      svg += `</svg>`;
      const el = document.getElementById(containerId);
      el.innerHTML = svg;
      el.querySelectorAll("[data-basket]").forEach((node) => node.addEventListener("click", () => setBasket(node.dataset.basket, "sector")));
    }

    function renderMarketLine() {
      let baskets = metrics.slice(0, 5).map((m) => m.basket);
      if (lineMode === "all") baskets = metrics.map((m) => m.basket);
      if (lineMode === "custom") baskets = Array.from(compareBaskets);
      baskets = Array.from(new Set([...baskets, selectedBasket]));
      const benchmarks = Object.entries(benchmarkToggles).filter(([, enabled]) => enabled).map(([ticker]) => ticker);
      lineChart("market-line", baskets, 380, benchmarks);
    }

    function renderLeaderboard() {
      document.getElementById("leaderboard").innerHTML = metrics.map((m) => `
        <button class="row ${m.basket === selectedBasket ? "active" : ""}" data-basket="${m.basket}" style="--active-color:${m.color}">
          <div class="rank">#${m.rank}</div>
          <div><div class="name">${esc(m.label)}</div><div class="sub">${fmtPct(m.return20dPct)} 20D / ${fmtPlainPct(m.shortPctFloat)} short</div></div>
          <div class="num ${cls(m.returnPct)}">${fmtPct(m.returnPct)}</div>
          <div class="num">${(m.setupScore * 100).toFixed(0)}</div>
        </button>
      `).join("");
      document.querySelectorAll("#leaderboard [data-basket]").forEach((node) => node.addEventListener("click", () => setBasket(node.dataset.basket, "sector")));
    }

    function renderRiskReturn() {
      const width = 760;
      const height = 360;
      const left = 56;
      const right = 32;
      const top = 28;
      const bottom = 46;
      const xs = valuesFor(metrics, "annualizedVolPct");
      const ys = valuesFor(metrics, "returnPct");
      const minX = Math.max(0, Math.floor(Math.min(...xs) / 10) * 10 - 5);
      const maxX = Math.ceil(Math.max(...xs) / 10) * 10 + 5;
      const minY = Math.floor(Math.min(...ys, 0) / 10) * 10 - 5;
      const maxY = Math.ceil(Math.max(...ys) / 10) * 10 + 5;
      const x = (v) => scale(v, minX, maxX, left, width - right);
      const y = (v) => scale(v, minY, maxY, height - bottom, top);
      let svg = `<svg viewBox="0 0 ${width} ${height}" aria-label="Risk return map">`;
      for (let tick = Math.ceil(minX / 20) * 20; tick <= maxX; tick += 20) svg += `<line class="grid-line" x1="${x(tick)}" y1="${top}" x2="${x(tick)}" y2="${height - bottom}"></line><text class="svg-label" x="${x(tick)}" y="${height - 16}" text-anchor="middle">${tick}%</text>`;
      for (let tick = Math.ceil(minY / 20) * 20; tick <= maxY; tick += 20) svg += `<line class="grid-line" x1="${left}" y1="${y(tick)}" x2="${width - right}" y2="${y(tick)}"></line><text class="svg-label" x="${left - 8}" y="${y(tick) + 4}" text-anchor="end">${tick}%</text>`;
      svg += `<line class="zero-line" x1="${left}" y1="${y(0)}" x2="${width - right}" y2="${y(0)}"></line>`;
      metrics.forEach((m) => {
        const selected = m.basket === selectedBasket;
        svg += `<g data-basket="${m.basket}" style="cursor:pointer">${selected ? `<circle cx="${x(m.annualizedVolPct)}" cy="${y(m.returnPct)}" r="13" fill="none" stroke="${m.color}" stroke-width="2"></circle>` : ""}<circle cx="${x(m.annualizedVolPct)}" cy="${y(m.returnPct)}" r="${7 + m.setupScore * 5}" fill="${m.color}" opacity="${selected ? 1 : 0.68}"></circle><text x="${x(m.annualizedVolPct) + 10}" y="${y(m.returnPct) + 4}" fill="${selected ? "#f5f0e2" : "#b9b5a8"}" font-size="11" font-weight="850">${esc(m.short)}</text></g>`;
      });
      svg += `</svg>`;
      const el = document.getElementById("risk-return");
      el.innerHTML = svg;
      el.querySelectorAll("[data-basket]").forEach((node) => node.addEventListener("click", () => setBasket(node.dataset.basket, "sector")));
    }

    function renderMarketNote() {
      const m = byBasket.get(selectedBasket);
      document.getElementById("market-note").innerHTML = `<strong>${esc(m.label)}</strong><br><br>${fmtPct(m.returnPct)} total return, ${fmtPct(m.return20dPct)} over 20 sessions, ${fmtPlainPct(m.shortPctFloat)} median short interest, and ${fmtPct(m.institutionalSharesChangedQoqPct)} institutional shares changed QoQ. Use Sector Drilldown for the names driving it.`;
    }

    function renderSector() {
      const m = byBasket.get(selectedBasket);
      document.getElementById("sector-title").textContent = m.label;
      lineChart("sector-line", [selectedBasket], 330);
      document.getElementById("sector-summary").innerHTML = `
        <div class="metric-grid">
          <div class="mini"><span>Return</span><strong class="${cls(m.returnPct)}">${fmtPct(m.returnPct, 2)}</strong></div>
          <div class="mini"><span>5D / 20D</span><strong>${fmtPct(m.return5dPct)} / ${fmtPct(m.return20dPct)}</strong></div>
          <div class="mini"><span>Current drawdown</span><strong class="${cls(m.currentDrawdownPct)}">${fmtPct(m.currentDrawdownPct)}</strong></div>
          <div class="mini"><span>Rebound</span><strong>${fmtPlainPct(m.reboundFromLowPct)}</strong></div>
          <div class="mini"><span>Vol / beta QQQ</span><strong>${fmtPlainPct(m.annualizedVolPct)} / ${fmtRatio(m.betaVsQqq)}</strong></div>
          <div class="mini"><span>Capture QQQ</span><strong>${fmtRatio(m.upCaptureVsQqq)} up / ${fmtRatio(m.downCaptureVsQqq)} down</strong></div>
          <div class="mini"><span>Short interest</span><strong class="warn">${fmtPlainPct(m.shortPctFloat)}</strong></div>
          <div class="mini"><span>Short vol / IV</span><strong>${fmtPlainPct(m.shortVolumeRatioPct)} / ${fmtPlainPct(m.optionsIvPct, 0)}</strong></div>
          <div class="mini"><span>Inst QoQ</span><strong class="${cls(m.institutionalSharesChangedQoqPct)}">${fmtPct(m.institutionalSharesChangedQoqPct)}</strong></div>
          <div class="mini"><span>Inst ownership</span><strong>${fmtPlainPct(m.institutionalOwnershipPct)}</strong></div>
          <div class="mini"><span>Revenue YoY</span><strong class="${cls(m.revenueGrowthYoyPct)}">${fmtPct(m.revenueGrowthYoyPct)}</strong></div>
          <div class="mini"><span>FCF margin</span><strong class="${cls(m.freeCashFlowMarginPct)}">${fmtPct(m.freeCashFlowMarginPct)}</strong></div>
        </div>
        <p class="hint">Best ticker: ${esc(m.bestConstituent)} ${fmtPct(m.bestConstituentReturnPct)}. Worst ticker: ${esc(m.worstConstituent)} ${fmtPct(m.worstConstituentReturnPct)}.</p>
      `;
      renderAttribution();
      renderSectorTable();
    }

    function renderAttribution() {
      const rows = DATA.attribution[selectedBasket] || [];
      const maxAbs = Math.max(1, ...rows.map((r) => Math.abs(r.contributionPct)));
      document.getElementById("attribution").innerHTML = rows.map((r) => `
        <div class="row ${tickerWasClicked && r.ticker === selectedTicker ? "active" : ""}" data-ticker="${r.ticker}" style="--active-color:${byBasket.get(selectedBasket)?.color || "var(--warn)"}">
          <div class="name">${esc(r.ticker)}</div>
          <div><div class="sub">${esc(r.name)}</div><div class="bar-track" style="margin-top:7px"><div class="bar-fill" style="--bar:${(Math.abs(r.contributionPct) / maxAbs * 100).toFixed(1)}%;--fill:${r.contributionPct >= 0 ? "var(--good)" : "var(--bad)"}"></div></div></div>
          <div class="num ${cls(r.returnPct)}">${fmtPct(r.returnPct)}</div>
          <div class="num ${cls(r.contributionPct)}">${fmtPct(r.contributionPct)}</div>
        </div>
      `).join("");
      document.querySelectorAll("#attribution [data-ticker]").forEach((node) => node.addEventListener("click", () => setTicker(node.dataset.ticker)));
    }

    function renderSectorTable() {
      const tabColumns = {
        price: [
          ["Ticker", "ticker", (t) => `<strong>${esc(t.ticker)}</strong><div class="sub">${esc(t.name)}</div>`],
          ["Return", "returnPct", (t) => fmtPct(t.returnPct), (t) => cls(t.returnPct)],
          ["20D", "return20dPct", (t) => fmtPct(t.return20dPct), (t) => cls(t.return20dPct)],
          ["5D", "return5dPct", (t) => fmtPct(t.return5dPct), (t) => cls(t.return5dPct)],
          ["Drawdown", "currentDrawdownPct", (t) => fmtPct(t.currentDrawdownPct), (t) => cls(t.currentDrawdownPct)],
          ["Rebound", "reboundFromLowPct", (t) => fmtPlainPct(t.reboundFromLowPct)],
          ["Vol", "annualizedVolPct", (t) => fmtPlainPct(t.annualizedVolPct)],
          ["Beta QQQ", "betaVsQqq", (t) => fmtRatio(t.betaVsQqq)],
          ["Score", "setupScore", (t) => (t.setupScore * 100).toFixed(0)],
        ],
        positioning: [
          ["Ticker", "ticker", (t) => `<strong>${esc(t.ticker)}</strong><div class="sub">${esc(t.name)}</div>`],
          ["Return", "returnPct", (t) => fmtPct(t.returnPct), (t) => cls(t.returnPct)],
          ["Short %", "shortPctFloat", (t) => fmtPlainPct(t.shortPctFloat), () => "warn"],
          ["Days", "daysToCover", (t) => isNum(t.daysToCover) ? t.daysToCover.toFixed(2) : "n/a"],
          ["Short vol", "shortVolumeRatioPct", (t) => fmtPlainPct(t.shortVolumeRatioPct)],
          ["P/C OI", "putCallOpenInterestRatio", (t) => isNum(t.putCallOpenInterestRatio) ? t.putCallOpenInterestRatio.toFixed(2) : "n/a"],
          ["P/C Vol", "putCallVolumeRatio", (t) => isNum(t.putCallVolumeRatio) ? t.putCallVolumeRatio.toFixed(2) : "n/a"],
          ["IV", "optionsIvPct", (t) => fmtPlainPct(t.optionsIvPct, 0)],
          ["Inst QoQ", "institutionalSharesChangedQoqPct", (t) => fmtPct(t.institutionalSharesChangedQoqPct), (t) => cls(t.institutionalSharesChangedQoqPct)],
        ],
        fundamentals: [
          ["Ticker", "ticker", (t) => `<strong>${esc(t.ticker)}</strong><div class="sub">${esc(t.name)}</div>`],
          ["Return", "returnPct", (t) => fmtPct(t.returnPct), (t) => cls(t.returnPct)],
          ["Rev YoY", "revenueGrowthYoyPct", (t) => fmtPct(t.revenueGrowthYoyPct), (t) => cls(t.revenueGrowthYoyPct)],
          ["Gross", "grossMarginPct", (t) => fmtPlainPct(t.grossMarginPct)],
          ["Op margin", "operatingMarginPct", (t) => fmtPct(t.operatingMarginPct), (t) => cls(t.operatingMarginPct)],
          ["FCF", "freeCashFlowMarginPct", (t) => fmtPct(t.freeCashFlowMarginPct), (t) => cls(t.freeCashFlowMarginPct)],
          ["Net cash", "netCash", (t) => fmtMoney(t.netCash)],
          ["Coverage", "fundamentalsStatus", (t) => esc(t.fundamentalsStatus || "n/a")],
          ["Score", "fundamentalScore", (t) => (t.fundamentalScore * 100).toFixed(0)],
        ],
      };
      const columns = tabColumns[sectorTab] || tabColumns.price;
      if (!columns.some(([, key]) => key === sectorSort)) sectorSort = columns[1][1];
      const rows = (DATA.constituents[selectedBasket] || []).slice().sort((a, b) => {
        if (sectorSort === "ticker") return a.ticker.localeCompare(b.ticker);
        const av = isNum(a[sectorSort]) ? a[sectorSort] : -99999;
        const bv = isNum(b[sectorSort]) ? b[sectorSort] : -99999;
        return sectorSort === "currentDrawdownPct" ? av - bv : bv - av;
      });
      const activeColor = byBasket.get(selectedBasket)?.color || "var(--warn)";
      document.getElementById("sector-table").innerHTML = `<table><thead><tr>${columns.map(([label, key]) => `<th data-sector-sort="${key}">${label}${sectorSort === key ? " ↓" : ""}</th>`).join("")}</tr></thead><tbody>${rows.map((t) => `<tr data-ticker="${t.ticker}" class="${tickerWasClicked && t.ticker === selectedTicker ? "active" : ""}" style="--active-color:${activeColor}">${columns.map(([label, key, format, className], i) => `<td class="${i ? "num " : ""}${className ? className(t) : ""}">${format(t)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
      document.querySelectorAll("#sector-table [data-ticker]").forEach((node) => node.addEventListener("click", () => setTicker(node.dataset.ticker)));
      document.querySelectorAll("#sector-table [data-sector-sort]").forEach((node) => node.addEventListener("click", () => { sectorSort = node.dataset.sectorSort; renderSectorTable(); }));
    }

    function tickerTags(t) {
      const tags = [];
      if (isNum(t.return20dPct) && t.return20dPct >= 12) tags.push("Momentum");
      if (isNum(t.shortPctFloat) && t.shortPctFloat >= 15 && (!isNum(t.return20dPct) || t.return20dPct >= 0)) tags.push("Squeeze");
      if (isNum(t.institutionalSharesChangedQoqPct) && t.institutionalSharesChangedQoqPct >= 5) tags.push("Inst bid");
      if (isNum(t.freeCashFlowMarginPct) && t.freeCashFlowMarginPct >= 10 && isNum(t.revenueGrowthYoyPct) && t.revenueGrowthYoyPct > 0) tags.push("Quality");
      if (isNum(t.currentDrawdownPct) && t.currentDrawdownPct <= -8 && isNum(t.reboundFromLowPct) && t.reboundFromLowPct >= 20) tags.push("Rebound");
      if ((isNum(t.annualizedVolPct) && t.annualizedVolPct >= 85) || (isNum(t.optionsIvPct) && t.optionsIvPct >= 100) || t.maxDrawdownPct <= -30) tags.push("High risk");
      return tags.length ? tags : ["Watch"];
    }

    function tickerPasses(t) {
      if (tickerFilter === "selected" && !t.baskets.some((b) => b.basket === selectedBasket)) return false;
      if (tickerFilter === "momentum" && !(isNum(t.return20dPct) && t.return20dPct >= 12)) return false;
      if (tickerFilter === "squeeze" && !(isNum(t.shortPctFloat) && t.shortPctFloat >= 15 && (!isNum(t.return20dPct) || t.return20dPct >= 0))) return false;
      if (tickerFilter === "institutional" && !(isNum(t.institutionalSharesChangedQoqPct) && t.institutionalSharesChangedQoqPct >= 5)) return false;
      if (tickerFilter === "quality" && !(isNum(t.freeCashFlowMarginPct) && t.freeCashFlowMarginPct >= 10 && isNum(t.revenueGrowthYoyPct) && t.revenueGrowthYoyPct > 0)) return false;
      if (tickerFilter === "rebound" && !(isNum(t.currentDrawdownPct) && t.currentDrawdownPct <= -8 && isNum(t.reboundFromLowPct) && t.reboundFromLowPct >= 20)) return false;
      if (tickerFilter === "risk" && !((isNum(t.annualizedVolPct) && t.annualizedVolPct >= 85) || (isNum(t.optionsIvPct) && t.optionsIvPct >= 100) || t.maxDrawdownPct <= -30)) return false;
      const q = tickerSearch.trim().toLowerCase();
      if (q && !t.ticker.toLowerCase().includes(q) && !t.name.toLowerCase().includes(q)) return false;
      return true;
    }

    function renderTickerTable() {
      const rows = tickers.filter(tickerPasses).sort((a, b) => {
        const av = isNum(a[tickerSort]) ? a[tickerSort] : -99999;
        const bv = isNum(b[tickerSort]) ? b[tickerSort] : -99999;
        return tickerSort === "currentDrawdownPct" ? av - bv : bv - av;
      }).slice(0, 80);
      const headers = [
        ["Ticker", "ticker"],
        ["Return", "returnPct"],
        ["20D", "return20dPct"],
        ["Drawdown", "currentDrawdownPct"],
        ["Short %", "shortPctFloat"],
        ["IV", "optionsIvPct"],
        ["Inst QoQ", "institutionalSharesChangedQoqPct"],
        ["FCF", "freeCashFlowMarginPct"],
        ["Score", "setupScore"],
      ];
      document.getElementById("ticker-table").innerHTML = `<table><thead><tr>${headers.map(([h, key]) => `<th data-sort="${key}">${h}</th>`).join("")}</tr></thead><tbody>${rows.map((t) => `<tr data-ticker="${t.ticker}" class="${tickerWasClicked && t.ticker === selectedTicker ? "active" : ""}"><td><strong>${esc(t.ticker)}</strong><div class="sub">${esc(t.name)}</div><div class="tag-row">${tickerTags(t).slice(0, 3).map((tag) => `<span class="tag">${tag}</span>`).join("")}</div></td><td class="num ${cls(t.returnPct)}">${fmtPct(t.returnPct)}</td><td class="num ${cls(t.return20dPct)}">${fmtPct(t.return20dPct)}</td><td class="num ${cls(t.currentDrawdownPct)}">${fmtPct(t.currentDrawdownPct)}</td><td class="num warn">${fmtPlainPct(t.shortPctFloat)}</td><td class="num">${fmtPlainPct(t.optionsIvPct, 0)}</td><td class="num ${cls(t.institutionalSharesChangedQoqPct)}">${fmtPct(t.institutionalSharesChangedQoqPct)}</td><td class="num ${cls(t.freeCashFlowMarginPct)}">${fmtPct(t.freeCashFlowMarginPct)}</td><td class="num">${(t.setupScore * 100).toFixed(0)}</td></tr>`).join("")}</tbody></table>`;
      document.querySelectorAll("#ticker-table [data-ticker]").forEach((node) => node.addEventListener("click", () => setTicker(node.dataset.ticker)));
      document.querySelectorAll("#ticker-table th[data-sort]").forEach((node) => node.addEventListener("click", () => { tickerSort = node.dataset.sort; renderTickerTable(); }));
    }

    function tickerLine(t, basketId) {
      const basket = byBasket.get(basketId);
      const basketRows = (DATA.daily[basketId] || []).map((r) => ({ date: r.date, value: r.index }));
      const qqqRows = (DATA.benchmarks.QQQ?.series || []).map((r) => ({ date: r.date, value: r.value }));
      const series = [
        { label: t.ticker, color: basket?.color || "#58d6b0", rows: t.series || [], width: 3.6 },
        { label: basket?.short || "Basket", color: "#e8c75f", rows: basketRows, width: 2.2 },
        { label: "QQQ", color: "#72b9ff", rows: qqqRows, width: 1.7 },
      ].filter((s) => s.rows.length > 1);
      const width = 900;
      const height = 300;
      const left = 54;
      const right = 84;
      const top = 24;
      const bottom = 38;
      const dates = Array.from(new Set(series.flatMap((s) => s.rows.map((r) => r.date)))).sort();
      const idx = new Map(dates.map((d, i) => [d, i]));
      const vals = series.flatMap((s) => s.rows.map((r) => r.value));
      const minY = Math.floor((Math.min(...vals) - 4) / 10) * 10;
      const maxY = Math.ceil((Math.max(...vals) + 4) / 10) * 10;
      const x = (date) => scale(idx.get(date), 0, dates.length - 1, left, width - right);
      const y = (value) => scale(value, minY, maxY, height - bottom, top);
      let svg = `<svg viewBox="0 0 ${width} ${height}" aria-label="Ticker comparison">`;
      for (let tick = minY; tick <= maxY; tick += 10) svg += `<line class="grid-line" x1="${left}" y1="${y(tick)}" x2="${width - right}" y2="${y(tick)}"></line><text class="svg-label" x="${left - 8}" y="${y(tick) + 4}" text-anchor="end">${tick}</text>`;
      svg += `<line class="zero-line" x1="${left}" y1="${y(100)}" x2="${width - right}" y2="${y(100)}"></line>`;
      series.forEach((s) => {
        const points = s.rows.map((r) => [x(r.date), y(r.value)]);
        const last = points[points.length - 1];
        svg += `<path d="${pathFrom(points)}" fill="none" stroke="${s.color}" stroke-width="${s.width}" stroke-linecap="round" stroke-linejoin="round"></path><circle cx="${last[0]}" cy="${last[1]}" r="4" fill="${s.color}"></circle><text x="${width - right + 10}" y="${last[1] + 4}" fill="${s.color}" font-size="12" font-weight="900">${esc(s.label)}</text>`;
      });
      svg += `</svg>`;
      return svg;
    }

    function renderTickerProfile() {
      const t = byTicker.get(selectedTicker) || tickers[0];
      const basketId = t.baskets.some((b) => b.basket === selectedBasket) ? selectedBasket : t.baskets[0]?.basket;
      const basket = byBasket.get(basketId);
      document.getElementById("ticker-profile").innerHTML = `<div class="profile"><div class="profile-main"><div class="profile-title"><h2>${esc(t.ticker)}</h2><span class="muted">${esc(t.name)}</span>${basket ? `<span class="tag">${sectorLabel(basket)}</span>` : ""}</div>${tickerLine(t, basketId)}<p class="hint">${esc(t.ticker)} setup: ${tickerTags(t).join(", ")}. Score ${(t.setupScore * 100).toFixed(0)} / 100.</p></div><div class="profile-side"><div class="metric-grid"><div class="mini"><span>Total return</span><strong class="${cls(t.returnPct)}">${fmtPct(t.returnPct, 2)}</strong></div><div class="mini"><span>20D / 5D</span><strong>${fmtPct(t.return20dPct)} / ${fmtPct(t.return5dPct)}</strong></div><div class="mini"><span>Current DD</span><strong class="${cls(t.currentDrawdownPct)}">${fmtPct(t.currentDrawdownPct)}</strong></div><div class="mini"><span>Rebound</span><strong>${fmtPlainPct(t.reboundFromLowPct)}</strong></div><div class="mini"><span>Short interest</span><strong class="warn">${fmtPlainPct(t.shortPctFloat)}</strong></div><div class="mini"><span>Options IV</span><strong>${fmtPlainPct(t.optionsIvPct, 0)}</strong></div><div class="mini"><span>Inst ownership</span><strong>${fmtPlainPct(t.institutionalOwnershipPct)}</strong></div><div class="mini"><span>Inst QoQ</span><strong class="${cls(t.institutionalSharesChangedQoqPct)}">${fmtPct(t.institutionalSharesChangedQoqPct)}</strong></div><div class="mini"><span>Revenue YoY</span><strong class="${cls(t.revenueGrowthYoyPct)}">${fmtPct(t.revenueGrowthYoyPct)}</strong></div><div class="mini"><span>FCF margin</span><strong class="${cls(t.freeCashFlowMarginPct)}">${fmtPct(t.freeCashFlowMarginPct)}</strong></div><div class="mini"><span>Net cash</span><strong>${fmtMoney(t.netCash)}</strong></div><div class="mini"><span>Beta QQQ</span><strong>${fmtRatio(t.betaVsQqq)}</strong></div></div></div></div>`;
    }

    function domainFor(values, fallbackMin, fallbackMax, pad = 0.08) {
      const filtered = values.filter(isNum);
      if (!filtered.length) return [fallbackMin, fallbackMax];
      let min = Math.min(fallbackMin, ...filtered);
      let max = Math.max(fallbackMax, ...filtered);
      if (min === max) {
        min -= 1;
        max += 1;
      }
      const room = (max - min) * pad;
      return [min - room, max + room];
    }

    function renderSignalBoard() {
      const labels = {
        setupScore: "Composite",
        squeezeScore: "Squeeze",
        sponsorScore: "Sponsors",
        fundamentalScore: "Fundamentals",
      };
      const sorted = metrics.slice().sort((a, b) => b[signalSort] - a[signalSort]);
      document.getElementById("signal-board").innerHTML = sorted.map((m, i) => {
        const score = (m[signalSort] || 0) * 100;
        return `
          <button class="score-row ${m.basket === selectedBasket ? "active" : ""}" data-basket="${m.basket}" style="--active-color:${m.color}">
            <div class="rank">#${i + 1}</div>
            <div><div class="name">${esc(m.label)}</div><div class="sub">${esc(m.short)} / Return rank ${m.rank}</div></div>
            <div><div class="sub">${labels[signalSort]}</div><div class="score-track"><div class="score-bar" style="--score:${score.toFixed(1)}%"></div></div></div>
            <div class="num">${score.toFixed(0)}</div>
            <div class="num warn">${fmtPlainPct(m.shortPctFloat)}</div>
            <div class="num ${cls(m.institutionalSharesChangedQoqPct)}">${fmtPct(m.institutionalSharesChangedQoqPct)}</div>
          </button>
        `;
      }).join("");
      document.querySelectorAll("#signal-board [data-basket]").forEach((node) => node.addEventListener("click", () => setBasket(node.dataset.basket, "sector")));
    }

    function scatterMap(containerId, rows, config) {
      const usable = rows.filter((m) => isNum(m[config.xKey]) && isNum(m[config.yKey]));
      const width = 700;
      const height = 420;
      const left = 64;
      const right = 42;
      const top = 28;
      const bottom = 58;
      const [minX, maxX] = domainFor(usable.map((m) => m[config.xKey]), config.xMin, config.xMax, 0.08);
      const [minY, maxY] = domainFor(usable.map((m) => m[config.yKey]), config.yMin, config.yMax, 0.08);
      const maxSize = Math.max(1, ...usable.map((m) => Math.abs(m[config.sizeKey] || 0)));
      const x = (value) => scale(value, minX, maxX, left, width - right);
      const y = (value) => scale(value, minY, maxY, height - bottom, top);
      let svg = `<svg viewBox="0 0 ${width} ${height}" aria-label="${esc(config.label)}">`;
      config.xTicks.forEach((tick) => {
        if (tick < minX || tick > maxX) return;
        svg += `<line class="grid-line" x1="${x(tick)}" y1="${top}" x2="${x(tick)}" y2="${height - bottom}"></line><text class="svg-label" x="${x(tick)}" y="${height - 20}" text-anchor="middle">${tick}%</text>`;
      });
      config.yTicks.forEach((tick) => {
        if (tick < minY || tick > maxY) return;
        svg += `<line class="grid-line" x1="${left}" y1="${y(tick)}" x2="${width - right}" y2="${y(tick)}"></line><text class="svg-label" x="${left - 9}" y="${y(tick) + 4}" text-anchor="end">${tick}%</text>`;
      });
      if (minY < 0 && maxY > 0) svg += `<line class="zero-line" x1="${left}" y1="${y(0)}" x2="${width - right}" y2="${y(0)}"></line>`;
      if (minX < 0 && maxX > 0) svg += `<line class="zero-line" x1="${x(0)}" y1="${top}" x2="${x(0)}" y2="${height - bottom}" opacity="0.65"></line>`;
      usable.forEach((m) => {
        const radius = 6 + clamp(Math.abs(m[config.sizeKey] || 0) / maxSize) * 11;
        const selected = m.basket === selectedBasket;
        svg += `<g data-basket="${m.basket}" style="cursor:pointer">`;
        if (selected) svg += `<circle cx="${x(m[config.xKey])}" cy="${y(m[config.yKey])}" r="${radius + 7}" fill="none" stroke="${m.color}" stroke-width="2"></circle>`;
        svg += `<circle cx="${x(m[config.xKey])}" cy="${y(m[config.yKey])}" r="${radius}" fill="${m.color}" opacity="${selected ? 0.98 : 0.7}"></circle>`;
        svg += `<text x="${x(m[config.xKey]) + radius + 5}" y="${y(m[config.yKey]) + 4}" fill="${selected ? "#f5f0e2" : "#b9b5a8"}" font-size="11" font-weight="850">${esc(m.short)}</text>`;
        svg += `</g>`;
      });
      svg += `<text class="svg-label" x="${(left + width - right) / 2}" y="${height - 5}" text-anchor="middle">${esc(config.xLabel)}</text>`;
      svg += `<text class="svg-label" x="16" y="${(top + height - bottom) / 2}" text-anchor="middle" transform="rotate(-90 16 ${(top + height - bottom) / 2})">${esc(config.yLabel)}</text>`;
      svg += `</svg>`;
      const el = document.getElementById(containerId);
      el.innerHTML = svg;
      el.querySelectorAll("[data-basket]").forEach((node) => node.addEventListener("click", () => setBasket(node.dataset.basket, "sector")));
    }

    function renderOwnershipMap() {
      scatterMap("ownership-chart", metrics, {
        label: "Short interest and institutional bid",
        xKey: "shortPctFloat",
        yKey: "institutionalSharesChangedQoqPct",
        sizeKey: "return20dPct",
        xMin: 0,
        xMax: 30,
        yMin: -6,
        yMax: 14,
        xTicks: [0, 10, 20, 30],
        yTicks: [-5, 0, 5, 10, 15],
        xLabel: "Median short interest / float",
        yLabel: "Institutional shares changed QoQ",
      });
    }

    function renderFundamentalsMap() {
      scatterMap("fundamentals-chart", metrics, {
        label: "Revenue growth and free-cash-flow margin",
        xKey: "revenueGrowthYoyPct",
        yKey: "freeCashFlowMarginPct",
        sizeKey: "returnPct",
        xMin: -10,
        xMax: 50,
        yMin: -160,
        yMax: 40,
        xTicks: [-10, 0, 20, 40, 60],
        yTicks: [-160, -80, 0, 40],
        xLabel: "Median revenue growth YoY",
        yLabel: "Median free-cash-flow margin",
      });
    }

    function renderDrawdown() {
      const width = 700;
      const rowH = 31;
      const top = 22;
      const left = 142;
      const right = 74;
      const height = top + 42 + rowH * metrics.length;
      const maxDD = Math.max(...metrics.map((m) => Math.abs(m.maxDrawdownPct)));
      const x = (value) => scale(value, 0, maxDD, left, width - right);
      let svg = `<svg viewBox="0 0 ${width} ${height}" aria-label="Max drawdown bars">`;
      [0, 10, 20, 30].forEach((tick) => {
        if (tick > maxDD + 3) return;
        svg += `<line class="grid-line" x1="${x(tick)}" y1="${top - 8}" x2="${x(tick)}" y2="${height - 30}"></line><text class="svg-label" x="${x(tick)}" y="${height - 10}" text-anchor="middle">${tick}%</text>`;
      });
      metrics.forEach((m, i) => {
        const y = top + i * rowH;
        const w = x(Math.abs(m.maxDrawdownPct)) - left;
        const selected = m.basket === selectedBasket;
        svg += `<g data-basket="${m.basket}" style="cursor:pointer">`;
        svg += `<text x="${left - 12}" y="${y + 18}" text-anchor="end" fill="${selected ? "#f5f0e2" : "#b9b5a8"}" font-size="12" font-weight="850">${esc(m.short)}</text>`;
        svg += `<rect x="${left}" y="${y + 6}" width="${Math.max(2, w)}" height="16" rx="5" fill="#ef6f82" opacity="${selected ? 0.96 : 0.56}"></rect>`;
        svg += `<text x="${left + w + 7}" y="${y + 18}" fill="#ffdce3" font-size="11" font-weight="850">${fmtPlainPct(m.maxDrawdownPct, 1)}</text>`;
        svg += `</g>`;
      });
      svg += `</svg>`;
      const el = document.getElementById("drawdown-chart");
      el.innerHTML = svg;
      el.querySelectorAll("[data-basket]").forEach((node) => node.addEventListener("click", () => setBasket(node.dataset.basket, "sector")));
    }

    function renderBreadth() {
      document.getElementById("breadth-panel").innerHTML = metrics.map((m) => {
        const dots = Array.from({ length: 8 }, (_, i) => `<i class="${i < m.positiveCount ? "on" : ""}"></i>`).join("");
        return `
          <button class="breadth-row ${m.basket === selectedBasket ? "active" : ""}" data-basket="${m.basket}" style="--active-color:${m.color}">
            <div><div class="name">${esc(m.short)}</div><div class="sub">${fmtPlainPct(m.positivePct)} positive constituents</div></div>
            <div class="breadth-dots">${dots}</div>
            <div class="num">${m.positiveCount}/8</div>
          </button>
        `;
      }).join("");
      document.querySelectorAll("#breadth-panel [data-basket]").forEach((node) => node.addEventListener("click", () => setBasket(node.dataset.basket, "sector")));
    }

    function heatStyle(value, rows, key, high = true) {
      if (!isNum(value)) return "background:rgb(255 255 255 / 0.025);color:var(--faint)";
      const score = norm(rows, value, key, high, 0.5);
      const hue = 356 + score * 160;
      return `background:hsl(${hue} 62% 42% / ${0.18 + score * 0.46})`;
    }

    function renderHeatmap() {
      const cols = [
        ["Return", "returnPct", true],
        ["20D", "return20dPct", true],
        ["Cur DD", "currentDrawdownPct", true],
        ["Rebound", "reboundFromLowPct", true],
        ["Short", "shortPctFloat", true],
        ["Inst QoQ", "institutionalSharesChangedQoqPct", true],
        ["Rev", "revenueGrowthYoyPct", true],
        ["FCF", "freeCashFlowMarginPct", true],
      ];
      const rows = metrics.slice().sort((a, b) => b.setupScore - a.setupScore);
      document.getElementById("heatmap").innerHTML = `<table><thead><tr><th>Sector</th>${cols.map(([c]) => `<th>${c}</th>`).join("")}</tr></thead><tbody>${rows.map((m) => `<tr data-basket="${m.basket}"><td><strong>${sectorLabel(m)}</strong></td>${cols.map(([label, key, high]) => `<td class="cell-heat" style="${heatStyle(m[key], metrics, key, high)}">${key === "setupScore" ? (m[key] * 100).toFixed(0) : key === "shortPctFloat" ? fmtPlainPct(m[key]) : fmtPct(m[key])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
      document.querySelectorAll("#heatmap [data-basket]").forEach((node) => node.addEventListener("click", () => setBasket(node.dataset.basket, "sector")));
    }

    function render() {
      renderShell();
      renderKpis();
      if (view === "market") {
        renderMarketLine();
        renderLeaderboard();
        renderRiskReturn();
        renderMarketNote();
      }
      if (view === "sector") renderSector();
      if (view === "tickers") {
        renderTickerTable();
        renderTickerProfile();
      }
      if (view === "advanced") {
        renderSignalBoard();
        renderOwnershipMap();
        renderFundamentalsMap();
        renderDrawdown();
        renderBreadth();
        renderHeatmap();
      }
    }

    document.querySelectorAll(".nav button").forEach((button) => button.addEventListener("click", () => { view = button.dataset.view; render(); }));
    document.querySelectorAll("[data-line-mode]").forEach((button) => button.addEventListener("click", () => {
      lineMode = button.dataset.lineMode;
      if (lineMode === "custom" && !compareBaskets.size) compareBaskets.add(selectedBasket);
      render();
    }));
    document.querySelectorAll("[data-benchmark]").forEach((button) => button.addEventListener("click", () => {
      const key = button.dataset.benchmark;
      benchmarkToggles[key] = !benchmarkToggles[key];
      render();
    }));
    document.querySelectorAll("[data-sector-tab]").forEach((button) => button.addEventListener("click", () => {
      sectorTab = button.dataset.sectorTab;
      sectorSort = sectorTab === "price" ? "returnPct" : sectorTab === "positioning" ? "shortPctFloat" : "revenueGrowthYoyPct";
      render();
    }));
    document.querySelectorAll("[data-signal]").forEach((button) => button.addEventListener("click", () => {
      signalSort = button.dataset.signal;
      render();
    }));
    document.querySelectorAll("[data-filter]").forEach((button) => button.addEventListener("click", () => { tickerFilter = button.dataset.filter; render(); }));
    document.getElementById("ticker-search").addEventListener("input", (event) => { tickerSearch = event.target.value; renderTickerTable(); });

    render();
  </script>
</body>
</html>
"""


def main() -> None:
    data = build_data()
    html = REDESIGNED_HTML_TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    DASHBOARD.write_text(html)
    print(DASHBOARD)


if __name__ == "__main__":
    main()
