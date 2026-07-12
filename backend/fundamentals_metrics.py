#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

from market_config import load_market_config


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
FUND_DIR = DATA_DIR / "fundamentals"
SEC_FACTS_DIR = FUND_DIR / "sec_companyfacts"
USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "Adaptive Interaction Optimizer research contact@example.com",
)


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


def pct(value: float | None) -> float | str:
    if value is None or not math.isfinite(value):
        return ""
    return round(value * 100, 4)


def number(value: float | None, digits: int = 4) -> float | str:
    if value is None or not math.isfinite(value):
        return ""
    return round(value, digits)


def write_index_config() -> None:
    FUND_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        f'header = "User-Agent: {USER_AGENT}"',
        "fail",
        "location",
        "retry = 2",
        "retry-delay = 1",
        'url = "https://www.sec.gov/files/company_tickers.json"',
        f'output = "{FUND_DIR / "company_tickers.json"}"',
    ]
    (FUND_DIR / "sec_index_curl.cfg").write_text("\n".join(lines) + "\n")


def load_sec_ticker_map() -> dict[str, dict]:
    path = FUND_DIR / "company_tickers.json"
    data = json.loads(path.read_text())
    out = {}
    for row in data.values():
        out[row["ticker"].upper()] = row
    return out


def write_companyfacts_config() -> None:
    config = load_market_config()
    ticker_map = load_sec_ticker_map()
    SEC_FACTS_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    lines = [
        f'header = "User-Agent: {USER_AGENT}"',
        "fail",
        "location",
        "retry = 2",
        "retry-delay = 1",
    ]
    for holding in sorted({h.ticker: h for h in config.holdings}.values(), key=lambda h: h.ticker):
        ticker = holding.ticker.upper()
        if "-" in ticker:
            rows.append(
                {
                    "ticker": holding.ticker,
                    "cik": "",
                    "sec_title": "",
                    "mapping_status": "not_applicable",
                    "note": "Crypto pairs and other hyphenated symbols do not have SEC companyfacts.",
                }
            )
            continue
        sec_row = ticker_map.get(ticker)
        if not sec_row:
            rows.append(
                {
                    "ticker": holding.ticker,
                    "cik": "",
                    "sec_title": "",
                    "mapping_status": "missing",
                    "note": "Ticker not found in SEC company_tickers index.",
                }
            )
            continue
        cik = str(sec_row["cik_str"]).zfill(10)
        rows.append(
            {
                "ticker": holding.ticker,
                "cik": cik,
                "sec_title": sec_row["title"],
                "mapping_status": "mapped",
                "note": "",
            }
        )
        lines.extend(
            [
                f'url = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"',
                f'output = "{SEC_FACTS_DIR / (safe_filename(holding.ticker) + ".json")}"',
            ]
        )
    write_csv(FUND_DIR / "sec_ticker_map.csv", ["ticker", "cik", "sec_title", "mapping_status", "note"], rows)
    (FUND_DIR / "sec_companyfacts_curl.cfg").write_text("\n".join(lines) + "\n")


def facts_for(payload: dict, taxonomy: str, concept: str) -> list[dict]:
    concept_data = payload.get("facts", {}).get(taxonomy, {}).get(concept, {})
    units = concept_data.get("units", {})
    facts = []
    for unit_rows in units.values():
        facts.extend(unit_rows)
    return facts


def latest_duration_fact(payload: dict, concepts: list[str], taxonomy: str = "us-gaap") -> dict | None:
    candidates = []
    for concept in concepts:
        for fact in facts_for(payload, taxonomy, concept):
            if "val" not in fact or not fact.get("end") or not fact.get("start"):
                continue
            form = fact.get("form", "")
            if form not in {"10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A"}:
                continue
            days = 0
            try:
                days = (
                    __import__("datetime").date.fromisoformat(fact["end"])
                    - __import__("datetime").date.fromisoformat(fact["start"])
                ).days
            except Exception:
                pass
            candidates.append({**fact, "concept": concept, "duration_days": days})
    if not candidates:
        return None
    return sorted(candidates, key=lambda f: (f.get("end", ""), f.get("filed", "")), reverse=True)[0]


def annual_facts(payload: dict, concepts: list[str], taxonomy: str = "us-gaap") -> list[dict]:
    candidates = []
    for concept in concepts:
        for fact in facts_for(payload, taxonomy, concept):
            if "val" not in fact or not fact.get("end") or not fact.get("start"):
                continue
            if fact.get("form") not in {"10-K", "10-K/A", "20-F", "20-F/A"}:
                continue
            try:
                duration = (
                    __import__("datetime").date.fromisoformat(fact["end"])
                    - __import__("datetime").date.fromisoformat(fact["start"])
                ).days
            except Exception:
                duration = 0
            if duration < 250:
                continue
            candidates.append({**fact, "concept": concept, "duration_days": duration})
    dedup: dict[str, dict] = {}
    for fact in sorted(candidates, key=lambda f: (f.get("end", ""), f.get("filed", ""))):
        dedup[fact["end"]] = fact
    return sorted(dedup.values(), key=lambda f: f["end"])


def latest_instant_fact(payload: dict, concepts: list[str], taxonomy: str = "us-gaap") -> dict | None:
    candidates = []
    for concept in concepts:
        for fact in facts_for(payload, taxonomy, concept):
            if "val" not in fact or not fact.get("end") or fact.get("start"):
                continue
            form = fact.get("form", "")
            if form not in {"10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A"}:
                continue
            candidates.append({**fact, "concept": concept})
    if not candidates:
        return None
    return sorted(candidates, key=lambda f: (f.get("end", ""), f.get("filed", "")), reverse=True)[0]


def fact_value(fact: dict | None) -> float | None:
    if not fact:
        return None
    try:
        return float(fact["val"])
    except Exception:
        return None


def latest_annual_fact(payload: dict, concepts: list[str], taxonomy: str = "us-gaap") -> dict | None:
    facts = annual_facts(payload, concepts, taxonomy)
    return facts[-1] if facts else None


def sum_latest_instants(payload: dict, concepts: list[str]) -> tuple[float | None, str]:
    values = []
    dates = []
    for concept in concepts:
        fact = latest_instant_fact(payload, [concept])
        value = fact_value(fact)
        if value is not None:
            values.append(value)
            dates.append(fact.get("end", ""))
    if not values:
        return None, ""
    return sum(values), max(dates)


def metric_row_from_payload(ticker: str, payload: dict, map_row: dict[str, str]) -> dict:
    revenue_facts = annual_facts(
        payload,
        [
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet",
            "SalesRevenueGoodsNet",
        ],
    )
    latest_revenue = revenue_facts[-1] if revenue_facts else None
    prior_revenue = revenue_facts[-2] if len(revenue_facts) > 1 else None
    revenue = fact_value(latest_revenue)
    prior_revenue_value = fact_value(prior_revenue)
    revenue_growth = (
        revenue / prior_revenue_value - 1
        if revenue is not None and prior_revenue_value not in {None, 0}
        else None
    )
    gross_profit = fact_value(latest_annual_fact(payload, ["GrossProfit"]))
    operating_income = fact_value(latest_annual_fact(payload, ["OperatingIncomeLoss"]))
    net_income = fact_value(latest_annual_fact(payload, ["NetIncomeLoss", "ProfitLoss"]))
    cfo = fact_value(latest_annual_fact(payload, ["NetCashProvidedByUsedInOperatingActivities"]))
    capex_fact = latest_annual_fact(payload, ["PaymentsToAcquirePropertyPlantAndEquipment"])
    capex = fact_value(capex_fact)
    fcf = cfo - capex if cfo is not None and capex is not None else None
    cash_fact = latest_instant_fact(
        payload,
        [
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        ],
    )
    cash = fact_value(cash_fact)
    debt, debt_date = sum_latest_instants(
        payload,
        [
            "ShortTermBorrowings",
            "LongTermDebtCurrent",
            "LongTermDebtNoncurrent",
            "FinanceLeaseLiabilityCurrent",
            "FinanceLeaseLiabilityNoncurrent",
        ],
    )
    if debt is None:
        debt_fact = latest_instant_fact(
            payload,
            ["LongTermDebt", "LongTermDebtAndFinanceLeaseObligations"],
        )
        debt = fact_value(debt_fact)
        debt_date = debt_fact.get("end", "") if debt_fact else ""
    shares_fact = latest_instant_fact(payload, ["EntityCommonStockSharesOutstanding"], taxonomy="dei")
    shares = fact_value(shares_fact)
    latest_period = max(
        [
            value
            for value in [
                latest_revenue.get("end", "") if latest_revenue else "",
                cash_fact.get("end", "") if cash_fact else "",
                debt_date,
                shares_fact.get("end", "") if shares_fact else "",
            ]
            if value
        ],
        default="",
    )
    available_count = sum(
        value is not None
        for value in [revenue, revenue_growth, gross_profit, operating_income, net_income, cfo, fcf, cash, debt, shares]
    )
    status = "full" if revenue is not None and available_count >= 7 else "partial" if available_count else "missing"
    return {
        "ticker": ticker,
        "coverage_status": status,
        "source": "SEC companyfacts",
        "as_of_date": latest_period,
        "cik": map_row.get("cik", ""),
        "sec_title": map_row.get("sec_title", ""),
        "latest_revenue": number(revenue, 2),
        "revenue_growth_yoy_pct": pct(revenue_growth),
        "gross_margin_pct": pct(gross_profit / revenue) if revenue not in {None, 0} and gross_profit is not None else "",
        "operating_margin_pct": pct(operating_income / revenue) if revenue not in {None, 0} and operating_income is not None else "",
        "net_income_margin_pct": pct(net_income / revenue) if revenue not in {None, 0} and net_income is not None else "",
        "operating_cash_flow": number(cfo, 2),
        "free_cash_flow": number(fcf, 2),
        "free_cash_flow_margin_pct": pct(fcf / revenue) if revenue not in {None, 0} and fcf is not None else "",
        "cash": number(cash, 2),
        "debt": number(debt, 2),
        "net_cash": number(cash - debt, 2) if cash is not None and debt is not None else "",
        "shares_outstanding": number(shares, 2),
        "available_metric_count": available_count,
        "note": "" if status != "missing" else "No usable SEC companyfacts metrics.",
    }


def analyze() -> None:
    config = load_market_config()
    FUND_DIR.mkdir(parents=True, exist_ok=True)
    SEC_FACTS_DIR.mkdir(parents=True, exist_ok=True)
    map_path = FUND_DIR / "sec_ticker_map.csv"
    if not map_path.exists():
        write_companyfacts_config()
    map_rows = {row["ticker"]: row for row in read_csv(map_path)}
    rows = []
    raw_index = {}
    for holding in sorted({h.ticker: h for h in config.holdings}.values(), key=lambda h: h.ticker):
        map_row = map_rows.get(holding.ticker, {})
        if map_row.get("mapping_status") != "mapped":
            rows.append(
                {
                    "ticker": holding.ticker,
                    "coverage_status": map_row.get("mapping_status", "missing"),
                    "source": "SEC companyfacts",
                    "as_of_date": "",
                    "cik": map_row.get("cik", ""),
                    "sec_title": map_row.get("sec_title", ""),
                    "latest_revenue": "",
                    "revenue_growth_yoy_pct": "",
                    "gross_margin_pct": "",
                    "operating_margin_pct": "",
                    "net_income_margin_pct": "",
                    "operating_cash_flow": "",
                    "free_cash_flow": "",
                    "free_cash_flow_margin_pct": "",
                    "cash": "",
                    "debt": "",
                    "net_cash": "",
                    "shares_outstanding": "",
                    "available_metric_count": 0,
                    "note": map_row.get("note", "No SEC ticker mapping."),
                }
            )
            continue
        path = SEC_FACTS_DIR / f"{safe_filename(holding.ticker)}.json"
        if not path.exists():
            rows.append(
                {
                    "ticker": holding.ticker,
                    "coverage_status": "missing",
                    "source": "SEC companyfacts",
                    "as_of_date": "",
                    "cik": map_row.get("cik", ""),
                    "sec_title": map_row.get("sec_title", ""),
                    "latest_revenue": "",
                    "revenue_growth_yoy_pct": "",
                    "gross_margin_pct": "",
                    "operating_margin_pct": "",
                    "net_income_margin_pct": "",
                    "operating_cash_flow": "",
                    "free_cash_flow": "",
                    "free_cash_flow_margin_pct": "",
                    "cash": "",
                    "debt": "",
                    "net_cash": "",
                    "shares_outstanding": "",
                    "available_metric_count": 0,
                    "note": "SEC companyfacts file has not been downloaded.",
                }
            )
            continue
        payload = json.loads(path.read_text())
        raw_index[holding.ticker] = {
            "cik": map_row.get("cik", ""),
            "entity_name": payload.get("entityName", ""),
            "fact_taxonomies": sorted(payload.get("facts", {}).keys()),
        }
        rows.append(metric_row_from_payload(holding.ticker, payload, map_row))
    fields = [
        "ticker",
        "coverage_status",
        "source",
        "as_of_date",
        "cik",
        "sec_title",
        "latest_revenue",
        "revenue_growth_yoy_pct",
        "gross_margin_pct",
        "operating_margin_pct",
        "net_income_margin_pct",
        "operating_cash_flow",
        "free_cash_flow",
        "free_cash_flow_margin_pct",
        "cash",
        "debt",
        "net_cash",
        "shares_outstanding",
        "available_metric_count",
        "note",
    ]
    write_csv(DATA_DIR / "fundamentals_metrics.csv", fields, rows)
    coverage_rows = []
    for basket in config.baskets:
        basket_rows = [row for row in rows if row["ticker"] in {h.ticker for h in basket.holdings}]
        full = sum(row["coverage_status"] == "full" for row in basket_rows)
        partial = sum(row["coverage_status"] == "partial" for row in basket_rows)
        usable = full + partial
        coverage_rows.append(
            {
                "basket": basket.id,
                "constituents": len(basket.holdings),
                "full_count": full,
                "partial_count": partial,
                "missing_count": len(basket.holdings) - usable,
                "usable_coverage_pct": round(usable / len(basket.holdings) * 100, 4),
            }
        )
    write_csv(
        DATA_DIR / "fundamentals_coverage.csv",
        ["basket", "constituents", "full_count", "partial_count", "missing_count", "usable_coverage_pct"],
        coverage_rows,
    )
    (FUND_DIR / "fundamentals_raw_index.json").write_text(json.dumps(raw_index, indent=2))


def aggregate() -> None:
    config = load_market_config()
    metric_rows = read_csv(DATA_DIR / "fundamentals_metrics.csv")
    by_ticker = {row["ticker"]: row for row in metric_rows}
    fields_to_aggregate = [
        "revenue_growth_yoy_pct",
        "gross_margin_pct",
        "operating_margin_pct",
        "net_income_margin_pct",
        "free_cash_flow_margin_pct",
        "net_cash",
    ]
    rows = []
    for basket in config.baskets:
        holdings = [by_ticker.get(h.ticker) for h in basket.holdings if h.ticker in by_ticker]
        usable = [row for row in holdings if row["coverage_status"] in {"full", "partial"}]
        row = {
            "basket": basket.id,
            "constituents": len(basket.holdings),
            "usable_fundamentals_count": len(usable),
            "usable_fundamentals_pct": round(len(usable) / len(basket.holdings) * 100, 4),
        }
        for field in fields_to_aggregate:
            values = [float(item[field]) for item in usable if item.get(field) not in {"", None}]
            row[f"median_{field}"] = number(median(values) if values else None)
            row[f"average_{field}"] = number(mean(values) if values else None)
        rows.append(row)
    write_csv(
        DATA_DIR / "basket_fundamentals.csv",
        [
            "basket",
            "constituents",
            "usable_fundamentals_count",
            "usable_fundamentals_pct",
            *[f"median_{field}" for field in fields_to_aggregate],
            *[f"average_{field}" for field in fields_to_aggregate],
        ],
        rows,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["write-index-config", "write-companyfacts-config", "analyze", "aggregate"])
    args = parser.parse_args()
    if args.command == "write-index-config":
        write_index_config()
    elif args.command == "write-companyfacts-config":
        write_companyfacts_config()
    elif args.command == "analyze":
        analyze()
    elif args.command == "aggregate":
        aggregate()


if __name__ == "__main__":
    main()
