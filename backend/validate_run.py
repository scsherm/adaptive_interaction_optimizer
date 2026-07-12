#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from market_config import load_market_config


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DASHBOARD = ROOT / "market-basket-dashboard.html"

REQUIRED_DATA_FILES = [
    "basket_definitions.csv",
    "source_metadata.csv",
    "raw_prices.csv",
    "normalized_prices.csv",
    "constituent_metrics.csv",
    "advanced_price_metrics.csv",
    "basket_advanced_price.csv",
    "cyclical_technical_metrics.csv",
    "basket_cyclical_technical.csv",
    "basket_breadth_daily.csv",
    "fundamentals_metrics.csv",
    "fundamentals_coverage.csv",
    "basket_fundamentals.csv",
    "short_volume_metrics.csv",
    "options_positioning_metrics.csv",
    "positioning_coverage.csv",
    "basket_positioning.csv",
    "short_interest_metrics.csv",
    "institutional_ownership_metrics.csv",
    "ownership_positioning_coverage.csv",
    "basket_ownership_positioning.csv",
    "basket_daily.csv",
    "basket_metrics.csv",
    "analysis_summary.json",
    "analysis_brief.md",
]


def read_csv(name: str) -> list[dict[str, str]]:
    path = DATA_DIR / name
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def days_between(left: str, right: date) -> int | None:
    if not left:
        return None
    return (date.fromisoformat(left) - right).days


def write_report(report: dict[str, Any]) -> None:
    qa_json = DATA_DIR / "qa_report.json"
    qa_md = DATA_DIR / "qa_report.md"
    qa_json.write_text(json.dumps(report, indent=2))

    lines = [
        "# Market Basket QA Report",
        "",
        f"Status: {report['status']}",
        f"Generated: {report['generated_at']}",
        "",
        "Summary:",
    ]
    for key, value in report["summary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "Errors:"])
    if report["errors"]:
        lines.extend(f"- {error}" for error in report["errors"])
    else:
        lines.append("- None")
    lines.extend(["", "Warnings:"])
    if report["warnings"]:
        lines.extend(f"- {warning}" for warning in report["warnings"])
    else:
        lines.append("- None")
    qa_md.write_text("\n".join(lines) + "\n")


def extract_dashboard_data() -> dict[str, Any] | None:
    if not DASHBOARD.exists():
        return None
    match = re.search(
        r'<script type="application/json" id="dashboard-data">(.*?)</script>',
        DASHBOARD.read_text(),
    )
    if not match:
        return None
    return json.loads(match.group(1))


def validate() -> int:
    config = load_market_config()
    errors: list[str] = []
    warnings: list[str] = []

    for name in REQUIRED_DATA_FILES:
        if not (DATA_DIR / name).exists():
            errors.append(f"Missing required data file: data/{name}")

    if not DASHBOARD.exists():
        errors.append("Missing dashboard: market-basket-dashboard.html")

    expected_baskets = {basket.id for basket in config.baskets}
    expected_tickers = {holding.ticker for holding in config.holdings}
    expected_tickers.update(holding.ticker for holding in config.benchmarks)

    definitions = read_csv("basket_definitions.csv")
    definition_counts = Counter(row["basket"] for row in definitions)
    configured_counts = {basket.id: len(basket.holdings) for basket in config.baskets}
    for basket in config.baskets:
        actual = definition_counts.get(basket.id, 0)
        expected = configured_counts[basket.id]
        if actual != expected:
            errors.append(
                f"{basket.id} has {actual} configured constituents in basket_definitions.csv; expected {expected} from config"
            )
        elif actual != config.expected_constituents_per_basket:
            warnings.append(
                f"{basket.id} has {actual} configured constituents; template target is {config.expected_constituents_per_basket}"
            )
    unknown_definition_baskets = set(definition_counts) - expected_baskets
    if unknown_definition_baskets:
        errors.append(f"Unexpected baskets in basket_definitions.csv: {sorted(unknown_definition_baskets)}")

    source_rows = read_csv("source_metadata.csv")
    source_by_ticker = {row["ticker"]: row for row in source_rows}
    missing_source = sorted(expected_tickers - set(source_by_ticker))
    if missing_source:
        errors.append(f"Missing source metadata for tickers: {', '.join(missing_source)}")

    stale_source = []
    for ticker, row in source_by_ticker.items():
        if ticker not in expected_tickers:
            continue
        last_date = row.get("last_date", "")
        if last_date and date.fromisoformat(last_date) < config.end_date:
            stale_source.append(f"{ticker} last price date {last_date}")
    if stale_source:
        warnings.append("Some tickers did not have latest-date source rows: " + "; ".join(stale_source))

    if (DATA_DIR / "data_errors.csv").exists():
        errors.append("data/data_errors.csv exists; inspect failed ticker downloads before trusting the run")

    advanced_rows = read_csv("advanced_price_metrics.csv")
    advanced_tickers = {row["ticker"] for row in advanced_rows}
    missing_advanced = sorted(expected_tickers - advanced_tickers)
    if missing_advanced:
        errors.append(f"Missing advanced price metrics for tickers: {', '.join(missing_advanced)}")

    basket_advanced = read_csv("basket_advanced_price.csv")
    basket_advanced_ids = {row["basket"] for row in basket_advanced}
    missing_basket_advanced = sorted(expected_baskets - basket_advanced_ids)
    if missing_basket_advanced:
        errors.append(f"Missing basket advanced price metrics for: {', '.join(missing_basket_advanced)}")

    cyclical_rows = read_csv("cyclical_technical_metrics.csv")
    cyclical_tickers = {row["ticker"] for row in cyclical_rows}
    missing_cyclical = sorted(expected_tickers - cyclical_tickers)
    if missing_cyclical:
        errors.append(f"Missing cyclical technical metrics for tickers: {', '.join(missing_cyclical)}")
    basket_cyclical = read_csv("basket_cyclical_technical.csv")
    basket_cyclical_ids = {row["basket"] for row in basket_cyclical}
    missing_basket_cyclical = sorted(expected_baskets - basket_cyclical_ids)
    if missing_basket_cyclical:
        errors.append(f"Missing basket cyclical technical metrics for: {', '.join(missing_basket_cyclical)}")

    breadth_rows = read_csv("basket_breadth_daily.csv")
    latest_breadth = {}
    for row in breadth_rows:
        if row["date"] >= latest_breadth.get(row["basket"], ""):
            latest_breadth[row["basket"]] = row["date"]
    for basket in config.baskets:
        latest = latest_breadth.get(basket.id)
        if latest != config.end_date.isoformat():
            gap = None if not latest else (config.end_date - date.fromisoformat(latest)).days
            message = f"{basket.id} basket_breadth_daily latest date is {latest}; expected {config.end_date}"
            if gap is not None and 0 < gap <= 3:
                warnings.append(message)
            else:
                errors.append(message)

    basket_metrics = read_csv("basket_metrics.csv")
    metrics_by_basket = {row["basket"]: row for row in basket_metrics}
    missing_metrics = sorted(expected_baskets - set(metrics_by_basket))
    if missing_metrics:
        errors.append(f"Missing basket metrics for: {', '.join(missing_metrics)}")
    extra_metrics = sorted(set(metrics_by_basket) - expected_baskets)
    if extra_metrics:
        errors.append(f"Unexpected basket metrics for: {', '.join(extra_metrics)}")

    for basket_id, row in metrics_by_basket.items():
        used = int(float(row["constituents_used"]))
        expected = configured_counts.get(basket_id)
        if expected is None:
            continue
        if used != expected:
            errors.append(
                f"{basket_id} metrics used {used} constituents; expected {expected} from config"
            )
        start_gap = days_between(row["start_date"], config.start_date)
        if start_gap is None or start_gap < 0:
            errors.append(f"{basket_id} start_date {row['start_date']} is before config {config.start_date}")
        elif start_gap > 7:
            errors.append(
                f"{basket_id} start_date {row['start_date']} is {start_gap} days after config {config.start_date}; refresh or inspect price coverage"
            )
        elif start_gap > 0:
            warnings.append(
                f"{basket_id} starts on first available trading row {row['start_date']} after configured start {config.start_date}"
            )
        end_gap = days_between(row["end_date"], config.end_date)
        if end_gap is None:
            errors.append(f"{basket_id} end_date is missing")
        elif end_gap > 0:
            errors.append(f"{basket_id} end_date {row['end_date']} is after config {config.end_date}")
        elif end_gap < -3:
            errors.append(
                f"{basket_id} end_date {row['end_date']} is {abs(end_gap)} days before config {config.end_date}; inspect stale price coverage"
            )
        elif end_gap < 0:
            warnings.append(f"{basket_id} end_date {row['end_date']} is before configured end {config.end_date}")

    fundamentals_rows = read_csv("fundamentals_metrics.csv")
    fundamentals_tickers = {row["ticker"] for row in fundamentals_rows}
    missing_fundamentals = sorted({h.ticker for h in config.holdings} - fundamentals_tickers)
    if missing_fundamentals:
        errors.append(f"Missing fundamentals coverage rows for tickers: {', '.join(missing_fundamentals)}")
    old_cutoff = config.end_date - timedelta(days=540)
    usable_fundamentals = 0
    for row in fundamentals_rows:
        status = row.get("coverage_status", "")
        if status in {"full", "partial"}:
            usable_fundamentals += 1
            as_of = row.get("as_of_date", "")
            if not as_of:
                warnings.append(f"{row['ticker']} has usable fundamentals but no as_of_date")
            elif date.fromisoformat(as_of) < old_cutoff:
                warnings.append(f"{row['ticker']} fundamentals are stale: {as_of}")
        if status not in {"full", "partial", "missing", "not_applicable"}:
            errors.append(f"{row['ticker']} has unexpected fundamentals coverage_status {status!r}")

    basket_fundamentals = read_csv("basket_fundamentals.csv")
    missing_basket_fundamentals = sorted(expected_baskets - {row["basket"] for row in basket_fundamentals})
    if missing_basket_fundamentals:
        errors.append(f"Missing basket fundamentals rows for: {', '.join(missing_basket_fundamentals)}")

    short_rows = read_csv("short_volume_metrics.csv")
    options_rows = read_csv("options_positioning_metrics.csv")
    missing_short_rows = sorted({h.ticker for h in config.holdings} - {row["ticker"] for row in short_rows})
    missing_options_rows = sorted({h.ticker for h in config.holdings} - {row["ticker"] for row in options_rows})
    if missing_short_rows:
        errors.append(f"Missing short-volume positioning rows for tickers: {', '.join(missing_short_rows)}")
    if missing_options_rows:
        errors.append(f"Missing options positioning rows for tickers: {', '.join(missing_options_rows)}")
    for row in short_rows:
        status = row.get("coverage_status", "")
        if status == "full":
            as_of = row.get("as_of_date", "")
            if not as_of:
                errors.append(f"{row['ticker']} has short-volume coverage but no as_of_date")
            elif date.fromisoformat(f"{as_of[:4]}-{as_of[4:6]}-{as_of[6:]}") > config.end_date:
                errors.append(f"{row['ticker']} short-volume as_of_date is after config end date")
        if status not in {"full", "missing", "not_applicable"}:
            errors.append(f"{row['ticker']} has unexpected short-volume coverage_status {status!r}")
    option_full_count = 0
    for row in options_rows:
        status = row.get("coverage_status", "")
        if status == "full":
            option_full_count += 1
            if not row.get("as_of_timestamp", ""):
                warnings.append(f"{row['ticker']} options coverage has no as_of_timestamp")
        if status not in {"full", "missing", "not_applicable"}:
            errors.append(f"{row['ticker']} has unexpected options coverage_status {status!r}")

    basket_positioning = read_csv("basket_positioning.csv")
    missing_basket_positioning = sorted(expected_baskets - {row["basket"] for row in basket_positioning})
    if missing_basket_positioning:
        errors.append(f"Missing basket positioning rows for: {', '.join(missing_basket_positioning)}")

    true_short_rows = read_csv("short_interest_metrics.csv")
    institutional_rows = read_csv("institutional_ownership_metrics.csv")
    missing_true_short_rows = sorted({h.ticker for h in config.holdings} - {row["ticker"] for row in true_short_rows})
    missing_institutional_rows = sorted({h.ticker for h in config.holdings} - {row["ticker"] for row in institutional_rows})
    if missing_true_short_rows:
        errors.append(f"Missing true short-interest rows for tickers: {', '.join(missing_true_short_rows)}")
    if missing_institutional_rows:
        errors.append(f"Missing institutional ownership rows for tickers: {', '.join(missing_institutional_rows)}")

    true_short_usable_count = 0
    for row in true_short_rows:
        status = row.get("coverage_status", "")
        if status in {"full", "partial"}:
            true_short_usable_count += 1
        if status not in {"full", "partial", "missing", "not_applicable"}:
            errors.append(f"{row['ticker']} has unexpected true short-interest coverage_status {status!r}")

    institutional_full_count = 0
    for row in institutional_rows:
        status = row.get("coverage_status", "")
        if status == "full":
            institutional_full_count += 1
            if not row.get("as_of_date", ""):
                warnings.append(f"{row['ticker']} institutional ownership coverage has no as_of_date")
        if status not in {"full", "missing", "not_applicable"}:
            errors.append(f"{row['ticker']} has unexpected institutional ownership coverage_status {status!r}")

    basket_ownership_positioning = read_csv("basket_ownership_positioning.csv")
    basket_ownership_ids = {row["basket"] for row in basket_ownership_positioning}
    missing_basket_ownership = sorted(expected_baskets - basket_ownership_ids)
    if missing_basket_ownership:
        errors.append(f"Missing basket ownership positioning rows for: {', '.join(missing_basket_ownership)}")
    low_institutional_coverage = [
        f"{row['basket']} {float(row['institutional_coverage_pct']):.1f}%"
        for row in basket_ownership_positioning
        if row["basket"] != "crypto"
        and row.get("institutional_coverage_pct", "")
        and float(row["institutional_coverage_pct"]) < 50
    ]
    if low_institutional_coverage:
        warnings.append(
            "Low institutional ownership coverage for baskets: " + "; ".join(low_institutional_coverage)
        )

    daily_rows = read_csv("basket_daily.csv")
    latest_daily_by_basket: dict[str, str] = {}
    filled_latest: dict[str, str] = {}
    for row in daily_rows:
        basket = row["basket"]
        if row["date"] >= latest_daily_by_basket.get(basket, ""):
            latest_daily_by_basket[basket] = row["date"]
            filled_latest[basket] = row.get("constituents_filled", "0")
    for basket in config.baskets:
        latest = latest_daily_by_basket.get(basket.id)
        if latest != config.end_date.isoformat():
            gap = None if not latest else (config.end_date - date.fromisoformat(latest)).days
            message = f"{basket.id} basket_daily latest date is {latest}; expected {config.end_date}"
            if gap is not None and 0 < gap <= 3:
                warnings.append(message)
            else:
                errors.append(message)
        filled = int(float(filled_latest.get(basket.id, "0")))
        if filled:
            warnings.append(f"{basket.id} uses {filled} forward-filled constituent prices on latest date")

    dashboard_data = extract_dashboard_data()
    if dashboard_data is None:
        errors.append("Dashboard JSON payload is missing or unreadable")
    else:
        dashboard_metrics = {row["basket"]: row for row in dashboard_data.get("metrics", [])}
        for basket_id, csv_row in metrics_by_basket.items():
            dash_row = dashboard_metrics.get(basket_id)
            if not dash_row:
                errors.append(f"Dashboard missing metrics for {basket_id}")
                continue
            comparisons = [
                ("total_return_pct", "returnPct"),
                ("annualized_vol_pct", "annualizedVolPct"),
                ("max_drawdown_pct", "maxDrawdownPct"),
                ("return_vol_ratio", "returnVolRatio"),
            ]
            for csv_key, dash_key in comparisons:
                if abs(float(csv_row[csv_key]) - float(dash_row[dash_key])) > 1e-9:
                    errors.append(f"Dashboard mismatch for {basket_id} {csv_key}")

    unused_cache = []
    yahoo_dir = DATA_DIR / "yahoo"
    if yahoo_dir.exists():
        expected_cache_names = {
            ticker.replace("-", "_").replace(".", "_") + ".json" for ticker in expected_tickers
        }
        unused_cache = sorted(path.name for path in yahoo_dir.glob("*.json") if path.name not in expected_cache_names)
    if unused_cache:
        warnings.append(f"Unused cached Yahoo files present: {', '.join(unused_cache[:8])}")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "generated_at": date.today().isoformat(),
        "summary": {
            "configured_baskets": len(config.baskets),
            "configured_holdings": len(config.holdings),
            "configured_benchmarks": len(config.benchmarks),
            "basket_metrics_rows": len(basket_metrics),
            "advanced_price_rows": len(advanced_rows),
            "cyclical_technical_rows": len(cyclical_rows),
            "usable_fundamentals_rows": usable_fundamentals,
            "options_full_rows": option_full_count,
            "true_short_interest_rows": true_short_usable_count,
            "institutional_full_rows": institutional_full_count,
            "source_metadata_rows": len(source_rows),
            "dashboard_present": DASHBOARD.exists(),
            "warnings": len(warnings),
            "errors": len(errors),
        },
        "errors": errors,
        "warnings": warnings,
    }
    write_report(report)
    print(f"QA {report['status']}: {len(errors)} errors, {len(warnings)} warnings")
    print(DATA_DIR / "qa_report.md")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(validate())
