#!/usr/bin/env python3
"""Category/basket editing surface for the workstation API.

All basket knowledge is read from `universe.py`; this module only adapts it to
the JSON shapes the workstation expects and applies guarded mutations.
"""
from __future__ import annotations

import csv
import json
from datetime import date
from typing import Any

from market_config import ROOT, latest_completed_us_equity_session, load_market_config
from universe import (
    add_holding_row,
    load_universe,
    load_universe_data,
    remove_holding_row,
    save_universe_data,
    validate as validate_universe,
)


DATA_DIR = ROOT / "data"


def read_csv(name: str) -> list[dict[str, str]]:
    path = DATA_DIR / name
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def coverage_indexes() -> dict[str, set[str]]:
    source = {row["ticker"] for row in read_csv("source_metadata.csv") if row.get("ticker")}
    fundamentals = {
        row["ticker"]
        for row in read_csv("fundamentals_metrics.csv")
        if row.get("ticker") and row.get("coverage_status") not in {"", "missing"}
    }
    options = {
        row["ticker"]
        for row in read_csv("options_positioning_metrics.csv")
        if row.get("ticker") and row.get("coverage_status") not in {"", "missing"}
    }
    short_interest = {
        row["ticker"]
        for row in read_csv("short_interest_metrics.csv")
        if row.get("ticker") and row.get("coverage_status") not in {"", "missing"}
    }
    institutional = {
        row["ticker"]
        for row in read_csv("institutional_ownership_metrics.csv")
        if row.get("ticker") and row.get("coverage_status") not in {"", "missing"}
    }
    return {
        "price": source,
        "fundamentals": fundamentals,
        "options": options,
        "shortInterest": short_interest,
        "institutional": institutional,
    }


def candidate_map(category_id: str) -> dict[str, dict[str, str]]:
    basket = load_universe().get(category_id)
    if basket is None:
        return {}
    return {
        candidate.ticker: {
            "ticker": candidate.ticker,
            "name": candidate.name,
            "note": candidate.note,
        }
        for candidate in basket.candidates
    }


def current_holdings() -> dict[str, list[dict[str, str]]]:
    return {
        basket.id: [
            {"ticker": holding.ticker, "name": holding.name, "note": holding.note}
            for holding in basket.holdings
        ]
        for basket in load_universe().baskets
    }


def price_refresh_status() -> dict[str, Any]:
    config = load_market_config()
    latest_session = latest_completed_us_equity_session()
    source_rows = {
        row["ticker"].upper(): row
        for row in read_csv("source_metadata.csv")
        if row.get("ticker")
    }
    configured = sorted(
        {
            *(holding.ticker.upper() for holding in config.holdings),
            *(benchmark.ticker.upper() for benchmark in config.benchmarks),
        }
    )
    start = config.start_date.isoformat()
    end = config.end_date.isoformat()
    end_date_behind_latest = config.end_date < latest_session
    missing = [ticker for ticker in configured if ticker not in source_rows]
    stale_prices = []
    late_history_gaps = []
    minor_calendar_gaps = []
    for ticker in configured:
        if ticker not in source_rows:
            continue
        last_date = source_rows[ticker].get("last_date", "")
        if last_date and date.fromisoformat(last_date) < config.end_date:
            stale_prices.append({"ticker": ticker, "lastDate": last_date})
        if not source_rows[ticker].get("first_date", ""):
            continue
        first_date = source_rows[ticker]["first_date"]
        if first_date <= start:
            continue
        gap = (date.fromisoformat(first_date) - config.start_date).days
        item = {"ticker": ticker, "firstDate": first_date, "gapDays": gap}
        if gap > 7:
            late_history_gaps.append(item)
        else:
            minor_calendar_gaps.append(item)
    broad_cache_gap = len(late_history_gaps) > max(2, round(len(configured) * 0.1))
    later_than_start = late_history_gaps if broad_cache_gap else []
    source_history_gaps = [] if broad_cache_gap else late_history_gaps
    cached_first_dates = [
        row.get("first_date", "")
        for row in source_rows.values()
        if row.get("first_date", "")
    ]
    reasons = []
    if later_than_start:
        earliest = min(item["firstDate"] for item in later_than_start if item["firstDate"])
        reasons.append(
            f"Configured start date {start} is earlier than cached price history for "
            f"{len(later_than_start)} configured tickers; earliest cached start is {earliest}."
        )
    if missing:
        examples = ", ".join(missing[:6])
        suffix = "..." if len(missing) > 6 else ""
        reasons.append(f"{len(missing)} configured tickers have no cached price data: {examples}{suffix}")
    broad_stale_cache = len(stale_prices) > max(2, round(len(configured) * 0.1))
    refresh_stale_prices = stale_prices if broad_stale_cache else []
    source_stale_prices = [] if broad_stale_cache else stale_prices
    if refresh_stale_prices:
        examples = ", ".join(f"{item['ticker']} {item['lastDate']}" for item in refresh_stale_prices[:6])
        suffix = "..." if len(stale_prices) > 6 else ""
        reasons.append(
            f"{len(refresh_stale_prices)} configured tickers have cached prices older than configured end date {end}: "
            f"{examples}{suffix}"
        )
    if end_date_behind_latest:
        reasons.append(
            f"Configured end date {end} is behind the latest completed U.S. equity session "
            f"{latest_session.isoformat()}."
        )
    return {
        "required": bool(missing or later_than_start or refresh_stale_prices or end_date_behind_latest),
        "configuredStartDate": start,
        "configuredEndDate": end,
        "latestCompletedSession": latest_session.isoformat(),
        "endDateBehindLatest": end_date_behind_latest,
        "earliestCachedDate": min(cached_first_dates) if cached_first_dates else "",
        "missingTickers": missing,
        "stalePrices": stale_prices,
        "refreshStalePrices": refresh_stale_prices,
        "sourceStalePrices": source_stale_prices,
        "laterThanStart": later_than_start,
        "sourceHistoryGaps": source_history_gaps,
        "minorCalendarGaps": minor_calendar_gaps,
        "reasons": reasons,
    }


def category_state() -> dict[str, Any]:
    universe = load_universe()
    categories = [
        {
            "id": basket.id,
            "label": basket.label,
            "short": basket.short,
            "color": basket.color,
            "taxonomyPath": list(basket.path),
            "description": basket.description,
            "keywords": list(basket.keywords),
            "holdings": [
                {"ticker": holding.ticker, "name": holding.name, "note": holding.note}
                for holding in basket.holdings
            ],
            "candidateCount": len(basket.candidates),
        }
        for basket in universe.baskets
    ]
    return {
        "methodology": {
            "startDate": universe.start_date.isoformat(),
            "endDate": universe.end_date.isoformat(),
            "weighting": universe.weighting,
            "priceField": universe.price_field,
        },
        "categories": categories,
        "priceRefresh": price_refresh_status(),
    }


def search_category(category_id: str, query: str = "") -> list[dict[str, Any]]:
    basket = load_universe().get(category_id)
    if basket is None:
        raise KeyError(f"Unknown category: {category_id}")
    query = query.strip().upper()
    holding_tickers = basket.holding_tickers
    coverage = coverage_indexes()
    results = []
    for candidate in basket.candidates:
        ticker = candidate.ticker
        haystack = f"{ticker} {candidate.name} {candidate.note}".upper()
        if query and query not in haystack:
            continue
        coverage_flags = {key: ticker in values for key, values in coverage.items()}
        coverage_score = round(sum(1 for value in coverage_flags.values() if value) / len(coverage_flags) * 100)
        results.append(
            {
                "ticker": ticker,
                "name": candidate.name,
                "note": candidate.note,
                "reason": f"Predetermined {basket.description} taxonomy: {candidate.note}.",
                "confidence": 100 if ticker in holding_tickers else 86,
                "alreadyInBasket": ticker in holding_tickers,
                "coverage": coverage_flags,
                "coverageScore": coverage_score,
            }
        )
    return sorted(results, key=lambda row: (not row["alreadyInBasket"], -row["coverageScore"], row["ticker"]))


def set_start_date(value: str) -> dict[str, Any]:
    parsed = date.fromisoformat(value)
    data = load_universe_data()
    end_date = date.fromisoformat(str(data["methodology"]["end_date"]))
    if parsed > end_date:
        raise ValueError(f"Start date {parsed.isoformat()} cannot be after end date {end_date.isoformat()}")
    data["methodology"]["start_date"] = parsed.isoformat()
    save_universe_data(data)
    return category_state()


def add_candidate(category_id: str, ticker: str) -> dict[str, Any]:
    ticker = ticker.upper().strip()
    candidates = candidate_map(category_id)
    if not candidates:
        raise KeyError(f"Unknown category: {category_id}")
    if ticker not in candidates:
        raise ValueError(f"{ticker} is not eligible for {category_id} under the predetermined taxonomy")
    candidate = candidates[ticker]
    data = load_universe_data()
    add_holding_row(data, category_id, ticker, candidate["name"], candidate["note"])
    save_universe_data(data)
    return category_state()


def remove_holding(category_id: str, ticker: str) -> dict[str, Any]:
    ticker = ticker.upper().strip()
    data = load_universe_data()
    basket = next((row for row in data.get("baskets", []) if row.get("id") == category_id), None)
    if basket is None:
        raise KeyError(f"Unknown category: {category_id}")
    if len(basket.get("holdings", [])) <= 1:
        raise ValueError("A category must keep at least one holding")
    remove_holding_row(data, category_id, ticker)
    save_universe_data(data)
    return category_state()


def validate_taxonomy() -> list[str]:
    return validate_universe()


def main() -> int:
    universe = load_universe()
    problems = validate_taxonomy()
    if problems:
        print(json.dumps({"status": "FAIL", "problems": problems}, indent=2))
        return 1
    print(json.dumps({"status": "PASS", "categories": len(universe.baskets)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
