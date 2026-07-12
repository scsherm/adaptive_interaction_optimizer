#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
from pathlib import Path
from statistics import mean, median

from market_config import load_market_config


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OWNERSHIP_DIR = DATA_DIR / "ownership_positioning"
SHORT_DIR = OWNERSHIP_DIR / "stockanalysis_statistics"
INSTITUTIONAL_DIR = OWNERSHIP_DIR / "businessquant_institutional"


def safe_filename(ticker: str) -> str:
    return ticker.replace("-", "_").replace(".", "_")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def number(value: float | None, digits: int = 4) -> float | str:
    if value is None or not math.isfinite(value):
        return ""
    return round(value, digits)


def parse_human_number(value: str) -> float | None:
    if not value:
        return None
    value = html.unescape(value).strip().replace(",", "").replace("$", "")
    if value in {"", "-", "N/A"}:
        return None
    percent = value.endswith("%")
    if percent:
        value = value[:-1]
    multiplier = 1.0
    upper_value = value.upper()
    if upper_value.endswith("MN"):
        multiplier = 1_000_000.0
        value = value[:-2]
    elif upper_value.endswith("BN"):
        multiplier = 1_000_000_000.0
        value = value[:-2]
    elif upper_value.endswith("TN"):
        multiplier = 1_000_000_000_000.0
        value = value[:-2]
    else:
        suffix = value[-1:].upper()
        if suffix == "K":
            multiplier = 1_000.0
            value = value[:-1]
        elif suffix == "M":
            multiplier = 1_000_000.0
            value = value[:-1]
        elif suffix == "B":
            multiplier = 1_000_000_000.0
            value = value[:-1]
        elif suffix == "T":
            multiplier = 1_000_000_000_000.0
            value = value[:-1]
    try:
        parsed = float(value) * multiplier
    except ValueError:
        return None
    return parsed


def parse_percent(value: str) -> float | None:
    parsed = parse_human_number(value)
    return parsed if parsed is not None else None


def is_equity_like(ticker: str) -> bool:
    return "-" not in ticker


def write_short_interest_config() -> None:
    config = load_market_config()
    SHORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        'user-agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"',
        "location",
        "retry = 1",
        "retry-delay = 1",
    ]
    for holding in sorted({h.ticker: h for h in config.holdings}.values(), key=lambda h: h.ticker):
        if not is_equity_like(holding.ticker):
            continue
        lines.extend(
            [
                f'url = "https://stockanalysis.com/stocks/{holding.ticker.lower()}/statistics/"',
                f'output = "{SHORT_DIR / (safe_filename(holding.ticker) + ".html")}"',
            ]
        )
    (OWNERSHIP_DIR / "stockanalysis_statistics_curl.cfg").write_text("\n".join(lines) + "\n")


def write_institutional_config() -> None:
    config = load_market_config()
    INSTITUTIONAL_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        'user-agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"',
        "location",
        "retry = 1",
        "retry-delay = 1",
    ]
    for holding in sorted({h.ticker: h for h in config.holdings}.values(), key=lambda h: h.ticker):
        if not is_equity_like(holding.ticker):
            continue
        lines.extend(
            [
                f'url = "https://businessquant.com/stocks/{holding.ticker.lower()}/institutional-ownership"',
                f'output = "{INSTITUTIONAL_DIR / (safe_filename(holding.ticker) + ".html")}"',
            ]
        )
    (OWNERSHIP_DIR / "businessquant_institutional_curl.cfg").write_text("\n".join(lines) + "\n")


def extract_stockanalysis_stat(text: str, stat_id: str) -> tuple[str, str] | None:
    pattern = re.compile(
        rf'\{{id:"{re.escape(stat_id)}",title:"[^"]+",value:"(?P<value>[^"]*)",hover:"(?P<hover>[^"]*)"\}}'
    )
    match = pattern.search(text)
    if not match:
        return None
    return match.group("value"), match.group("hover")


def analyze_short_interest() -> list[dict]:
    config = load_market_config()
    rows = []
    for holding in sorted({h.ticker: h for h in config.holdings}.values(), key=lambda h: h.ticker):
        if not is_equity_like(holding.ticker):
            rows.append(
                {
                    "ticker": holding.ticker,
                    "coverage_status": "not_applicable",
                    "source": "StockAnalysis statistics",
                    "as_of_date": "",
                    "shares_short": "",
                    "shares_short_previous": "",
                    "short_interest_change_pct": "",
                    "short_pct_shares_out": "",
                    "short_pct_float": "",
                    "days_to_cover": "",
                    "note": "Crypto pairs do not have equity short interest.",
                }
            )
            continue
        path = SHORT_DIR / f"{safe_filename(holding.ticker)}.html"
        if not path.exists():
            rows.append(
                {
                    "ticker": holding.ticker,
                    "coverage_status": "missing",
                    "source": "StockAnalysis statistics",
                    "as_of_date": "",
                    "shares_short": "",
                    "shares_short_previous": "",
                    "short_interest_change_pct": "",
                    "short_pct_shares_out": "",
                    "short_pct_float": "",
                    "days_to_cover": "",
                    "note": "StockAnalysis statistics page has not been downloaded.",
                }
            )
            continue
        text = path.read_text(errors="ignore")
        if "404 - Page not found" in text:
            rows.append(
                {
                    "ticker": holding.ticker,
                    "coverage_status": "missing",
                    "source": "StockAnalysis statistics",
                    "as_of_date": "",
                    "shares_short": "",
                    "shares_short_previous": "",
                    "short_interest_change_pct": "",
                    "short_pct_shares_out": "",
                    "short_pct_float": "",
                    "days_to_cover": "",
                    "note": "StockAnalysis statistics page returned 404.",
                }
            )
            continue
        short_interest = extract_stockanalysis_stat(text, "shortInterest")
        prior_short = extract_stockanalysis_stat(text, "shortPriorMonth")
        short_shares = extract_stockanalysis_stat(text, "shortShares")
        short_float = extract_stockanalysis_stat(text, "shortFloat")
        short_ratio = extract_stockanalysis_stat(text, "shortRatio")
        shares_short = parse_human_number(short_interest[1] if short_interest else "")
        shares_short_previous = parse_human_number(prior_short[1] if prior_short else "")
        short_pct_shares_out = parse_percent(short_shares[1] if short_shares else "")
        short_pct_float = parse_percent(short_float[1] if short_float else "")
        days_to_cover = parse_human_number(short_ratio[1] if short_ratio else "")
        change = (
            shares_short / shares_short_previous - 1
            if shares_short is not None and shares_short_previous not in {None, 0}
            else None
        )
        coverage = (
            "full"
            if shares_short is not None and short_pct_float is not None and days_to_cover is not None
            else "partial"
            if shares_short is not None
            else "missing"
        )
        rows.append(
            {
                "ticker": holding.ticker,
                "coverage_status": coverage,
                "source": "StockAnalysis statistics",
                "as_of_date": "",
                "shares_short": number(shares_short, 2),
                "shares_short_previous": number(shares_short_previous, 2),
                "short_interest_change_pct": number(change * 100 if change is not None else None),
                "short_pct_shares_out": number(short_pct_shares_out, 4),
                "short_pct_float": number(short_pct_float, 4),
                "days_to_cover": number(days_to_cover, 4),
                "note": "True short-interest snapshot from StockAnalysis page." if coverage == "full" else "Partial short-interest snapshot; some float fields were unavailable.",
            }
        )
    return rows


def extract_businessquant_stat(text: str, label: str) -> str:
    pattern = re.compile(
        r'<div class="bq-stats-item"><strong>(?P<value>[^<]*)</strong><span>'
        + re.escape(label)
        + r"</span></div>",
    )
    match = pattern.search(text)
    if not match:
        return ""
    return re.sub(r"<.*?>", "", html.unescape(match.group("value"))).strip()


def extract_institutional_as_of(text: str) -> str:
    match = re.search(
        r"(?:as of|through|ending|for|in) ([A-Z][a-z]+(?: \d{1,2},)? \d{4})",
        text,
    )
    if match:
        return match.group(1)
    return ""


def extract_first_number(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S)
        if match:
            return match.group("value")
    return ""


def extract_institutional_fallbacks(text: str) -> dict[str, float | None]:
    ownership = parse_percent(
        extract_first_number(
            text,
            [
                r"(?:held|controlled)\s+(?P<value>[0-9,.]+)%\s+of\s+(?:[A-Za-z]+\s+)?outstanding shares",
                r"representing\s+(?P<value>[0-9,.]+)%\s+of\s+(?:total\s+)?shares outstanding",
            ],
        )
    )
    shares = parse_human_number(
        extract_first_number(
            text,
            [
                r"held\s+(?P<value>[0-9,.]+(?:K|M|Mn|B|Bn|T|Tn)?)\s+shares",
                r"position .*? amounted to\s+(?P<value>[0-9,.]+(?:K|M|Mn|B|Bn|T|Tn)?)\s+shares",
            ],
        )
    )
    holder_count = parse_human_number(
        extract_first_number(
            text,
            [
                r'total_records":(?P<value>[0-9,]+)',
                r"(?P<value>[0-9,]+)\s+institutional investors",
                r"appears in\s+(?P<value>[0-9,]+)\s+institutional",
                r"showed up in the 13F filings of\s+(?P<value>[0-9,]+)\s+institutional",
            ],
        )
    )
    shares_outstanding = None
    if ownership not in {None, 0} and shares is not None:
        shares_outstanding = shares / (ownership / 100)
    return {
        "shares_outstanding": shares_outstanding,
        "institutional_shares": shares,
        "institutional_ownership_pct": ownership,
        "institutional_investor_count": holder_count,
    }


def analyze_institutional_ownership() -> list[dict]:
    config = load_market_config()
    rows = []
    for holding in sorted({h.ticker: h for h in config.holdings}.values(), key=lambda h: h.ticker):
        if not is_equity_like(holding.ticker):
            rows.append(
                {
                    "ticker": holding.ticker,
                    "coverage_status": "not_applicable",
                    "source": "BusinessQuant institutional ownership",
                    "as_of_date": "",
                    "shares_outstanding": "",
                    "institutional_shares": "",
                    "institutional_ownership_pct": "",
                    "institutional_value": "",
                    "institutional_shares_changed_qoq_pct": "",
                    "institutional_investor_count": "",
                    "note": "Crypto pairs do not have equity institutional ownership.",
                }
            )
            continue
        path = INSTITUTIONAL_DIR / f"{safe_filename(holding.ticker)}.html"
        if not path.exists():
            rows.append(
                {
                    "ticker": holding.ticker,
                    "coverage_status": "missing",
                    "source": "BusinessQuant institutional ownership",
                    "as_of_date": "",
                    "shares_outstanding": "",
                    "institutional_shares": "",
                    "institutional_ownership_pct": "",
                    "institutional_value": "",
                    "institutional_shares_changed_qoq_pct": "",
                    "institutional_investor_count": "",
                    "note": "BusinessQuant institutional ownership page has not been downloaded.",
                }
            )
            continue
        text = path.read_text(errors="ignore")
        shares_outstanding = extract_businessquant_stat(text, "Shares Outstanding")
        institutional_shares = extract_businessquant_stat(text, "Shares held by institutions")
        institutional_value = extract_businessquant_stat(text, "Value of institutional holdings")
        institutional_ownership = extract_businessquant_stat(text, "Institutional ownership %")
        shares_changed = extract_businessquant_stat(text, "Shares Changed QoQ")
        holder_count = extract_businessquant_stat(text, "No. of institutional investors")
        shares_outstanding_value = parse_human_number(shares_outstanding)
        institutional_shares_value = parse_human_number(institutional_shares)
        institutional_value_number = parse_human_number(institutional_value)
        institutional_ownership_value = parse_percent(institutional_ownership)
        shares_changed_value = parse_percent(shares_changed)
        holder_count_value = parse_human_number(holder_count)
        fallback = extract_institutional_fallbacks(text)
        if institutional_ownership_value in {None, 0}:
            institutional_ownership_value = fallback["institutional_ownership_pct"]
        if institutional_shares_value in {None, 0}:
            institutional_shares_value = fallback["institutional_shares"]
        if holder_count_value in {None, 0}:
            holder_count_value = fallback["institutional_investor_count"]
        if shares_outstanding_value in {None, 0}:
            shares_outstanding_value = fallback["shares_outstanding"]
        has_real_snapshot = any(
            value is not None and value > 0
            for value in (
                shares_outstanding_value,
                institutional_shares_value,
                institutional_value_number,
                holder_count_value,
            )
        )
        coverage = "full" if institutional_ownership_value is not None and has_real_snapshot else "missing"
        rows.append(
            {
                "ticker": holding.ticker,
                "coverage_status": coverage,
                "source": "BusinessQuant institutional ownership",
                "as_of_date": extract_institutional_as_of(text),
                "shares_outstanding": number(shares_outstanding_value, 2) if coverage == "full" else "",
                "institutional_shares": number(institutional_shares_value, 2) if coverage == "full" else "",
                "institutional_ownership_pct": number(institutional_ownership_value, 4) if coverage == "full" else "",
                "institutional_value": number(institutional_value_number, 2) if coverage == "full" else "",
                "institutional_shares_changed_qoq_pct": number(shares_changed_value, 4) if coverage == "full" else "",
                "institutional_investor_count": number(holder_count_value, 0) if coverage == "full" else "",
                "note": "Third-party 13F aggregation snapshot." if coverage == "full" else "No usable institutional ownership snapshot.",
            }
        )
    return rows


def aggregate(short_rows: list[dict], institutional_rows: list[dict]) -> list[dict]:
    config = load_market_config()
    short_by_ticker = {row["ticker"]: row for row in short_rows}
    institutional_by_ticker = {row["ticker"]: row for row in institutional_rows}
    rows = []
    for basket in config.baskets:
        short_items = [
            short_by_ticker[h.ticker]
            for h in basket.holdings
            if short_by_ticker.get(h.ticker, {}).get("coverage_status") in {"full", "partial"}
        ]
        institutional_items = [
            institutional_by_ticker[h.ticker]
            for h in basket.holdings
            if institutional_by_ticker.get(h.ticker, {}).get("coverage_status") == "full"
        ]

        def values(items: list[dict], field: str) -> list[float]:
            return [float(row[field]) for row in items if row.get(field) not in {"", None}]

        short_pct_float = values(short_items, "short_pct_float")
        days_to_cover = values(short_items, "days_to_cover")
        institutional_pct = values(institutional_items, "institutional_ownership_pct")
        qoq_change = values(institutional_items, "institutional_shares_changed_qoq_pct")
        holder_counts = values(institutional_items, "institutional_investor_count")
        rows.append(
            {
                "basket": basket.id,
                "constituents": len(basket.holdings),
                "short_interest_coverage_count": len(short_items),
                "short_interest_coverage_pct": round(len(short_items) / len(basket.holdings) * 100, 4),
                "institutional_coverage_count": len(institutional_items),
                "institutional_coverage_pct": round(len(institutional_items) / len(basket.holdings) * 100, 4),
                "median_short_pct_float": number(median(short_pct_float) if short_pct_float else None),
                "average_short_pct_float": number(mean(short_pct_float) if short_pct_float else None),
                "median_days_to_cover": number(median(days_to_cover) if days_to_cover else None),
                "median_institutional_ownership_pct": number(median(institutional_pct) if institutional_pct else None),
                "average_institutional_ownership_pct": number(mean(institutional_pct) if institutional_pct else None),
                "median_institutional_shares_changed_qoq_pct": number(median(qoq_change) if qoq_change else None),
                "median_institutional_investor_count": number(median(holder_counts) if holder_counts else None),
            }
        )
    return rows


def analyze() -> None:
    short_rows = analyze_short_interest()
    institutional_rows = analyze_institutional_ownership()
    write_csv(
        DATA_DIR / "short_interest_metrics.csv",
        [
            "ticker",
            "coverage_status",
            "source",
            "as_of_date",
            "shares_short",
            "shares_short_previous",
            "short_interest_change_pct",
            "short_pct_shares_out",
            "short_pct_float",
            "days_to_cover",
            "note",
        ],
        short_rows,
    )
    write_csv(
        DATA_DIR / "institutional_ownership_metrics.csv",
        [
            "ticker",
            "coverage_status",
            "source",
            "as_of_date",
            "shares_outstanding",
            "institutional_shares",
            "institutional_ownership_pct",
            "institutional_value",
            "institutional_shares_changed_qoq_pct",
            "institutional_investor_count",
            "note",
        ],
        institutional_rows,
    )
    basket_rows = aggregate(short_rows, institutional_rows)
    write_csv(
        DATA_DIR / "basket_ownership_positioning.csv",
        [
            "basket",
            "constituents",
            "short_interest_coverage_count",
            "short_interest_coverage_pct",
            "institutional_coverage_count",
            "institutional_coverage_pct",
            "median_short_pct_float",
            "average_short_pct_float",
            "median_days_to_cover",
            "median_institutional_ownership_pct",
            "average_institutional_ownership_pct",
            "median_institutional_shares_changed_qoq_pct",
            "median_institutional_investor_count",
        ],
        basket_rows,
    )
    write_csv(
        DATA_DIR / "ownership_positioning_coverage.csv",
        [
            "basket",
            "short_interest_coverage_pct",
            "institutional_coverage_pct",
            "short_interest_source",
            "institutional_source",
        ],
        [
            {
                "basket": row["basket"],
                "short_interest_coverage_pct": row["short_interest_coverage_pct"],
                "institutional_coverage_pct": row["institutional_coverage_pct"],
                "short_interest_source": "StockAnalysis statistics snapshot",
                "institutional_source": "BusinessQuant 13F aggregation snapshot",
            }
            for row in basket_rows
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["write-short-config", "write-institutional-config", "analyze"])
    args = parser.parse_args()
    if args.command == "write-short-config":
        write_short_interest_config()
    elif args.command == "write-institutional-config":
        write_institutional_config()
    elif args.command == "analyze":
        analyze()


if __name__ == "__main__":
    main()
