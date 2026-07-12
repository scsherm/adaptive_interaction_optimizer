#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from market_config import load_market_config
from sentiment_config import load_sentiment_config, validate_query_coverage
from sentiment_signals import VALID_STATES


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SENTIMENT_DIR = DATA_DIR / "sentiment"
REPORT_JSON = DATA_DIR / "sentiment_qa_report.json"
REPORT_MD = DATA_DIR / "sentiment_qa_report.md"

REQUIRED_FILES = [
    SENTIMENT_DIR / "news_raw.csv",
    SENTIMENT_DIR / "news_fetch_log.csv",
    SENTIMENT_DIR / "news_timeline_raw.csv",
    DATA_DIR / "ticker_news_sentiment.csv",
    DATA_DIR / "basket_news_sentiment.csv",
    DATA_DIR / "sentiment_events.csv",
    DATA_DIR / "sentiment_summary.json",
]

BASKET_SCORE_FIELDS = [
    "basket_news_tone_score",
    "basket_investor_tone_score",
    "basket_attention_score",
    "basket_sentiment_momentum",
    "basket_negative_spike_score",
    "basket_positive_spike_score",
    "source_diversity_score",
    "coverage_confidence",
    "demand_tailwind_score",
    "demand_risk_score",
    "investor_positive_score",
    "investor_negative_score",
    "company_positive_score",
    "company_risk_score",
    "market_context_score",
]

TICKER_SCORE_FIELDS = [
    "news_tone_score",
    "investor_tone_score",
    "attention_score",
    "sentiment_momentum_7d",
    "sentiment_momentum_30d",
    "negative_news_spike_score",
    "positive_news_spike_score",
    "source_diversity_score",
    "coverage_confidence",
    "demand_tailwind_score",
    "demand_risk_score",
    "investor_positive_score",
    "investor_negative_score",
    "company_positive_score",
    "company_risk_score",
    "market_context_score",
]

ALWAYS_NUMERIC_FIELDS = {"coverage_confidence", "source_diversity_score", "market_context_score"}
LLM_NUMERIC_FIELDS = {"entity_confidence", "intensity", "confidence"}
LLM_NARRATIVE_TYPES = {
    "investor_positive",
    "investor_negative",
    "demand_tailwind",
    "demand_risk",
    "company_positive",
    "company_risk",
    "macro_tailwind",
    "macro_risk",
    "regulatory_risk",
    "attention_only",
    "mixed",
    "irrelevant",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def parse_day(value: str) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    if "T" in text:
        text = text.split("T", 1)[0]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def as_float(value: str) -> float | None:
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def write_report(report: dict[str, Any]) -> None:
    REPORT_JSON.write_text(json.dumps(report, indent=2))
    lines = [
        "# Sentiment QA Report",
        "",
        f"Status: {report['status']}",
        f"Generated: {report['generated_at']}",
        "",
        "Summary:",
    ]
    for key, value in report["summary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "Errors:"])
    lines.extend([f"- {item}" for item in report["errors"]] or ["- None"])
    lines.extend(["", "Warnings:"])
    lines.extend([f"- {item}" for item in report["warnings"]] or ["- None"])
    REPORT_MD.write_text("\n".join(lines) + "\n")


def validate_score_range(rows: list[dict[str, str]], fields: list[str], label_key: str, errors: list[str]) -> None:
    for row in rows:
        label = row.get(label_key, "")
        for field in fields:
            value = as_float(row.get(field, ""))
            if value is None:
                if field in ALWAYS_NUMERIC_FIELDS:
                    errors.append(f"{label} missing numeric {field}")
                continue
            elif value < 0 or value > 100:
                errors.append(f"{label} {field} outside 0-100: {value}")


def validate_llm_rows(rows: list[dict[str, str]], errors: list[str], warnings: list[str]) -> None:
    seen_ids = set()
    for row in rows:
        analysis_id = row.get("analysis_id", "")
        if not analysis_id:
            errors.append("LLM analysis row missing analysis_id")
        elif analysis_id in seen_ids:
            errors.append(f"Duplicate LLM analysis_id: {analysis_id}")
        seen_ids.add(analysis_id)
        if row.get("narrative_type", "") not in LLM_NARRATIVE_TYPES:
            errors.append(f"{analysis_id} invalid LLM narrative_type {row.get('narrative_type')!r}")
        if row.get("market_implication", "") not in {"positive", "negative", "mixed", "neutral", "unclear"}:
            errors.append(f"{analysis_id} invalid market_implication {row.get('market_implication')!r}")
        for field in LLM_NUMERIC_FIELDS:
            value = as_float(row.get(field, ""))
            if value is None:
                errors.append(f"{analysis_id} missing LLM numeric {field}")
            elif value < 0 or value > 1:
                errors.append(f"{analysis_id} LLM {field} outside 0-1: {value}")
        if row.get("is_relevant", "").lower() not in {"true", "false"}:
            warnings.append(f"{analysis_id} has non-standard is_relevant value {row.get('is_relevant')!r}")


def scan_for_api_key_leaks(paths: list[Path], errors: list[str]) -> None:
    key_pattern = re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")
    env_pattern = re.compile(r"OPENAI_API_KEY\s*=\s*['\"]?sk-[A-Za-z0-9_-]{20,}", re.IGNORECASE)
    for path in paths:
        if not path.exists() or path.is_dir():
            continue
        text = path.read_text(errors="ignore")
        if key_pattern.search(text) or env_pattern.search(text):
            errors.append(f"Potential API key leak in {path.relative_to(ROOT)}")


def validate() -> int:
    market = load_market_config()
    sentiment = load_sentiment_config()
    expected_baskets = {basket.id for basket in market.baskets}
    expected_pairs = {(holding.basket, holding.ticker) for holding in market.holdings}
    errors: list[str] = []
    warnings: list[str] = []

    for path in REQUIRED_FILES:
        if not path.exists():
            errors.append(f"Missing sentiment file: {path.relative_to(ROOT)}")

    errors.extend(validate_query_coverage(sentiment))

    raw_rows = read_csv(SENTIMENT_DIR / "news_raw.csv")
    timeline_rows = read_csv(SENTIMENT_DIR / "news_timeline_raw.csv")
    fetch_log = read_csv(SENTIMENT_DIR / "news_fetch_log.csv")
    basket_rows = read_csv(DATA_DIR / "basket_news_sentiment.csv")
    ticker_rows = read_csv(DATA_DIR / "ticker_news_sentiment.csv")
    events = read_csv(DATA_DIR / "sentiment_events.csv")
    llm_rows = read_csv(SENTIMENT_DIR / "news_llm_analysis.csv")
    summary = read_json(DATA_DIR / "sentiment_summary.json")

    if not raw_rows:
        errors.append("No raw news rows in data/sentiment/news_raw.csv")
    if not fetch_log:
        errors.append("No fetch log rows in data/sentiment/news_fetch_log.csv")
    if not timeline_rows:
        warnings.append("No timeline rows in data/sentiment/news_timeline_raw.csv; attention/tone scores are article-only")

    raw_baskets = {row.get("basket", "") for row in raw_rows}
    missing_raw_baskets = sorted(expected_baskets - raw_baskets)
    if missing_raw_baskets:
        warnings.append(f"No raw news rows yet for baskets: {', '.join(missing_raw_baskets)}")

    basket_ids = {row.get("basket", "") for row in basket_rows}
    missing_baskets = sorted(expected_baskets - basket_ids)
    extra_baskets = sorted(basket_ids - expected_baskets)
    if missing_baskets:
        errors.append(f"Missing basket sentiment rows for: {', '.join(missing_baskets)}")
    if extra_baskets:
        errors.append(f"Unexpected basket sentiment rows for: {', '.join(extra_baskets)}")

    ticker_pairs = {(row.get("basket", ""), row.get("ticker", "")) for row in ticker_rows}
    missing_tickers = sorted(expected_pairs - ticker_pairs)
    if missing_tickers:
        formatted = ", ".join(f"{basket}/{ticker}" for basket, ticker in missing_tickers)
        errors.append(f"Missing ticker sentiment rows for: {formatted}")

    validate_score_range(basket_rows, BASKET_SCORE_FIELDS, "basket", errors)
    validate_score_range(ticker_rows, TICKER_SCORE_FIELDS, "ticker", errors)
    validate_llm_rows(llm_rows, errors, warnings)
    scan_for_api_key_leaks(
        [
            SENTIMENT_DIR / "news_llm_analysis.csv",
            SENTIMENT_DIR / "news_llm_analysis.jsonl",
            DATA_DIR / "sentiment_summary.json",
            DATA_DIR / "basket_news_sentiment.csv",
            DATA_DIR / "ticker_news_sentiment.csv",
        ],
        errors,
    )

    for row in basket_rows:
        state = row.get("basket_sentiment_state", "")
        if state not in VALID_STATES:
            errors.append(f"{row.get('basket', '')} invalid basket_sentiment_state {state!r}")
        if not row.get("primary_signal"):
            warnings.append(f"{row.get('basket', '')} has no primary_signal")
        if not row.get("risk_signal"):
            warnings.append(f"{row.get('basket', '')} has no risk_signal")

    for row in ticker_rows:
        state = row.get("sentiment_state", "")
        if state not in VALID_STATES:
            errors.append(f"{row.get('basket', '')}/{row.get('ticker', '')} invalid sentiment_state {state!r}")

    raw_titles_missing = sum(1 for row in raw_rows if not row.get("title") or not row.get("url"))
    if raw_rows and raw_titles_missing / len(raw_rows) > 0.1:
        warnings.append(f"{raw_titles_missing} raw rows are missing title or URL")

    domain_counts = Counter(row.get("domain", "") for row in raw_rows if row.get("domain"))
    if raw_rows and domain_counts:
        top_domain, top_count = domain_counts.most_common(1)[0]
        if top_count / len(raw_rows) > 0.45:
            warnings.append(f"Source concentration is high: {top_domain} is {top_count}/{len(raw_rows)} raw rows")
    elif raw_rows:
        warnings.append("Raw rows have no source domain coverage")

    latest_days = [day for day in [parse_day(row.get("published_at", "")) for row in raw_rows] if day is not None]
    latest_day = max(latest_days, default=None)
    today = datetime.now(UTC).date()
    if latest_day is None and raw_rows:
        warnings.append("Could not parse latest raw news date")
    elif latest_day is not None:
        age = (today - latest_day).days
        if age > 7:
            warnings.append(f"Raw sentiment data is stale: latest article is {latest_day.isoformat()} ({age} days old)")

    latest_fetch_status: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in fetch_log:
        key = (row.get("basket", ""), row.get("ticker", ""), row.get("query", ""), row.get("mode", ""))
        if row.get("run_date", "") >= latest_fetch_status.get(key, {}).get("run_date", ""):
            latest_fetch_status[key] = row
    failed_fetches = [row for row in latest_fetch_status.values() if row.get("status") != "ok"]
    if failed_fetches:
        warnings.append(f"{len(failed_fetches)} sentiment fetches logged errors")

    states = Counter(row.get("basket_sentiment_state", "") for row in basket_rows)
    low_coverage = [row["basket"] for row in basket_rows if row.get("basket_sentiment_state") == "Ignored / Low Coverage"]
    if len(low_coverage) == len(basket_rows) and basket_rows:
        warnings.append("All baskets are low coverage; fetch a wider window or more queries before relying on states")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "summary": {
            "configured_queries": len(sentiment.queries),
            "raw_rows": len(raw_rows),
            "timeline_rows": len(timeline_rows),
            "llm_rows": len(llm_rows),
            "fetch_log_rows": len(fetch_log),
            "basket_rows": len(basket_rows),
            "ticker_rows": len(ticker_rows),
            "event_rows": len(events),
            "latest_raw_news_date": latest_day.isoformat() if latest_day else "",
            "states": ", ".join(f"{state}:{count}" for state, count in sorted(states.items()) if state),
            "top_sources": ", ".join(f"{domain}:{count}" for domain, count in domain_counts.most_common(5)),
            "summary_latest_news_date": summary.get("latest_news_date", ""),
            "warnings": len(warnings),
            "errors": len(errors),
        },
        "errors": errors,
        "warnings": warnings,
    }
    write_report(report)
    print(f"Sentiment QA {report['status']}: {len(errors)} errors, {len(warnings)} warnings")
    print(REPORT_MD)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(validate())
