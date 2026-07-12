#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import hashlib
import math
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from market_config import load_market_config
from sentiment_config import load_sentiment_config


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SENTIMENT_DIR = DATA_DIR / "sentiment"
RAW_IN = SENTIMENT_DIR / "news_raw.csv"
TIMELINE_IN = SENTIMENT_DIR / "news_timeline_raw.csv"
LLM_IN = SENTIMENT_DIR / "news_llm_analysis.csv"
TICKER_OUT = DATA_DIR / "ticker_news_sentiment.csv"
BASKET_OUT = DATA_DIR / "basket_news_sentiment.csv"
EVENTS_OUT = DATA_DIR / "sentiment_events.csv"
SUMMARY_OUT = DATA_DIR / "sentiment_summary.json"

VALID_STATES = {
    "Positive Investor Momentum",
    "Negative Investor Momentum",
    "Demand Tailwind Spike",
    "Fear-Driven Attention Spike",
    "Crowded Positive",
    "Contrarian Improving",
    "Narrative Breakdown",
    "Ignored / Low Coverage",
    "Mixed / Noisy",
}

POSITIVE_TERMS = {
    "beat",
    "beats",
    "growth",
    "surge",
    "surges",
    "rally",
    "upgrade",
    "upgrades",
    "bullish",
    "record",
    "profit",
    "profits",
    "raises",
    "strong",
    "wins",
    "contract",
    "demand",
    "expansion",
    "partnership",
}

NEGATIVE_TERMS = {
    "miss",
    "misses",
    "cut",
    "cuts",
    "slowdown",
    "downgrade",
    "downgrades",
    "bearish",
    "lawsuit",
    "probe",
    "hack",
    "breach",
    "attack",
    "loss",
    "losses",
    "decline",
    "falls",
    "drops",
    "warning",
    "risk",
    "bankruptcy",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def as_float(row: dict[str, str], key: str) -> float | None:
    value = row.get(key, "")
    if value == "":
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def round_score(value: float) -> float:
    return round(clamp(value), 4)


def score_value(row: dict[str, Any], key: str, default: float = 50.0) -> float:
    value = row.get(key, "")
    if value == "":
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def article_key(row: dict[str, str]) -> str:
    basis = "|".join(
        [
            row.get("basket", ""),
            row.get("ticker", ""),
            row.get("query_type", ""),
            row.get("title", ""),
            row.get("url", ""),
            row.get("published_at", ""),
        ]
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def parse_day(value: str) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    if "T" in text:
        text = text.split("T", 1)[0]
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def score_from_tone(tone: float | None) -> float:
    if tone is None:
        return 50.0
    return round_score(50.0 + tone * 5.0)


def weighted_score(positive: float, negative: float) -> float | str:
    total = positive + negative
    if total <= 0:
        return ""
    return round_score(50.0 + (positive - negative) / total * 50.0)


def intensity_score(value: float, total: float) -> float | str:
    if total <= 0:
        return ""
    return round_score(value / total * 100.0)


def empty_stats(method: str = "no_coverage") -> dict[str, Any]:
    return {
        "media_tone_raw": "",
        "news_tone_score": "",
        "investor_tone_score": "",
        "mention_volume": 0,
        "mention_volume_7d": 0,
        "mention_volume_zscore": 0.0,
        "attention_score": "",
        "sentiment_momentum_7d": "",
        "sentiment_momentum_30d": "",
        "negative_news_spike_score": "",
        "positive_news_spike_score": "",
        "source_diversity_score": 0.0,
        "coverage_confidence": 0.0,
        "demand_tailwind_score": "",
        "demand_risk_score": "",
        "investor_positive_score": "",
        "investor_negative_score": "",
        "company_positive_score": "",
        "company_risk_score": "",
        "llm_relevant_articles": 0,
        "llm_total_articles": 0,
        "llm_average_confidence": "",
        "scoring_method": method,
    }


def text_tone(title: str) -> float:
    tokens = {
        token.strip(".,:;!?()[]{}\"'").lower()
        for token in title.split()
    }
    positive = len(tokens & POSITIVE_TERMS)
    negative = len(tokens & NEGATIVE_TERMS)
    return float((positive - negative) * 2.5)


def article_tone(row: dict[str, str]) -> float:
    ticker_sentiment = as_float(row, "ticker_sentiment_score")
    if ticker_sentiment is not None:
        return ticker_sentiment * 10.0
    provider_sentiment = as_float(row, "provider_sentiment_score")
    if provider_sentiment is not None:
        return provider_sentiment * 10.0
    tone = as_float(row, "tone_score")
    if tone is not None:
        return tone
    return text_tone(row.get("title", ""))


def zscore(latest: float, values: list[float]) -> float:
    valid = [value for value in values if math.isfinite(value)]
    if len(valid) < 3:
        return 0.0
    stdev = pstdev(valid)
    if stdev == 0:
        return 0.0
    return (latest - mean(valid)) / stdev


def avg(values: list[float]) -> float | None:
    valid = [value for value in values if value is not None and math.isfinite(value)]
    if not valid:
        return None
    return mean(valid)


def period_values(series: dict[date, list[float]], end_day: date, days: int) -> list[float]:
    start = end_day - timedelta(days=days - 1)
    values: list[float] = []
    for day, day_values in series.items():
        if start <= day <= end_day:
            values.extend(day_values)
    return values


def period_sum(series: dict[date, float], end_day: date, days: int) -> float:
    start = end_day - timedelta(days=days - 1)
    return sum(value for day, value in series.items() if start <= day <= end_day)


def daily_values(series: dict[date, float], end_day: date, days: int) -> list[float]:
    start = end_day - timedelta(days=days - 1)
    return [series.get(start + timedelta(days=offset), 0.0) for offset in range(days)]


def source_diversity(rows: list[dict[str, str]]) -> float:
    domains = {row.get("domain", "") for row in rows if row.get("domain")}
    if not rows:
        return 0.0
    return round_score(len(domains) / math.sqrt(len(rows)) * 32.0)


def entity_confidence(row: dict[str, str]) -> float:
    title = row.get("title", "").lower()
    company = row.get("company_name", "").lower()
    query = row.get("query", "").lower()
    if company and company in title:
        return 95.0
    query_terms = [token for token in query.split() if len(token) > 3]
    matches = sum(1 for token in query_terms if token.lower() in title)
    if query_terms:
        return clamp(45 + matches / len(query_terms) * 45)
    return 50.0


def is_market_relevant(row: dict[str, str]) -> bool:
    title = row.get("title", "").lower()
    query_type = row.get("query_type", "")
    market_terms = {
        "stock",
        "stocks",
        "shares",
        "earnings",
        "revenue",
        "profit",
        "analyst",
        "upgrade",
        "downgrade",
        "demand",
        "spending",
        "price",
        "market",
        "sector",
    }
    return query_type != "company_specific" or any(term in title for term in market_terms) or entity_confidence(row) >= 70


def latest_rows_by_key(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row.get(key, ""): row for row in rows}


def market_context_scores() -> tuple[dict[str, float], dict[str, float]]:
    basket_scores: dict[str, float] = {}
    ticker_scores: dict[str, float] = {}
    rotation = latest_rows_by_key(read_csv(DATA_DIR / "basket_rotation_scores.csv"), "basket")
    basket_price = latest_rows_by_key(read_csv(DATA_DIR / "basket_advanced_price.csv"), "basket")
    ticker_price = latest_rows_by_key(read_csv(DATA_DIR / "advanced_price_metrics.csv"), "ticker")

    for basket, row in basket_price.items():
        rotation_row = rotation.get(basket, {})
        rotation_score = as_float(rotation_row, "rotation_score")
        change_5d = as_float(rotation_row, "score_change_5d") or 0.0
        return_20d = as_float(row, "return_20d_pct") or 0.0
        score = (rotation_score if rotation_score is not None else 50.0) * 0.72 + clamp(50 + change_5d * 2.3) * 0.18 + clamp(50 + return_20d * 2.0) * 0.10
        basket_scores[basket] = round_score(score)

    for ticker, row in ticker_price.items():
        return_20d = as_float(row, "return_20d_pct") or 0.0
        drawdown = as_float(row, "current_drawdown_pct") or 0.0
        score = clamp(50 + return_20d * 2.2 + drawdown * 0.9)
        ticker_scores[ticker] = round_score(score)
    return basket_scores, ticker_scores


def build_target_stats(
    target_rows: list[dict[str, str]],
    target_timeline: list[dict[str, str]],
    end_day: date,
) -> dict[str, Any]:
    if not target_rows and not target_timeline:
        return empty_stats()

    tone_by_day: dict[date, list[float]] = defaultdict(list)
    volume_by_day: dict[date, float] = defaultdict(float)
    investor_tone_by_day: dict[date, list[float]] = defaultdict(list)
    demand_volume_by_day: dict[date, float] = defaultdict(float)

    for row in target_timeline:
        day = parse_day(row.get("date", ""))
        value = as_float(row, "value")
        if day is None or value is None:
            continue
        if row.get("metric") == "tone":
            tone_by_day[day].append(value)
            if row.get("query_type") in {"investor", "company_specific"}:
                investor_tone_by_day[day].append(value)
        elif row.get("metric") == "volume_raw":
            volume_by_day[day] += max(0.0, value)
            if row.get("query_type") == "demand_tailwind":
                demand_volume_by_day[day] += max(0.0, value)

    for row in target_rows:
        day = parse_day(row.get("published_at", ""))
        if day is None:
            continue
        tone_value = article_tone(row)
        tone_by_day[day].append(tone_value)
        volume_by_day[day] += 1.0
        if row.get("query_type") in {"investor", "company_specific"}:
            investor_tone_by_day[day].append(tone_value)
        if row.get("query_type") == "demand_tailwind":
            demand_volume_by_day[day] += 1.0

    tone_30 = avg(period_values(tone_by_day, end_day, 30))
    tone_7 = avg(period_values(tone_by_day, end_day, 7))
    tone_prior_7 = avg(period_values(tone_by_day, end_day - timedelta(days=7), 7))
    tone_prior_30 = avg(period_values(tone_by_day, end_day - timedelta(days=30), 30))
    investor_tone_30 = avg(period_values(investor_tone_by_day, end_day, 30))
    volume_30 = period_sum(volume_by_day, end_day, 30)
    volume_7 = period_sum(volume_by_day, end_day, 7)
    previous_7 = period_sum(volume_by_day, end_day - timedelta(days=7), 7)
    z = zscore(volume_7 / 7.0, daily_values(volume_by_day, end_day, 90))
    demand_7 = period_sum(demand_volume_by_day, end_day, 7)
    demand_z = zscore(demand_7 / 7.0, daily_values(demand_volume_by_day, end_day, 90))

    recent_rows = [
        row for row in target_rows
        if (day := parse_day(row.get("published_at", ""))) is not None and end_day - timedelta(days=13) <= day <= end_day
    ]
    negative_recent = [row for row in recent_rows if article_tone(row) <= -2.5]
    positive_recent = [row for row in recent_rows if article_tone(row) >= 2.5]
    negative_score = round_score(50 + min(len(negative_recent), 12) * 4 + max(0.0, -((tone_7 or 0.0) - (tone_prior_7 or 0.0))) * 6)
    positive_score = round_score(50 + min(len(positive_recent), 12) * 4 + max(0.0, ((tone_7 or 0.0) - (tone_prior_7 or 0.0))) * 6)
    momentum_7 = round_score(50 + ((tone_7 or 0.0) - (tone_prior_7 or tone_7 or 0.0)) * 7.5)
    momentum_30 = round_score(50 + ((tone_30 or 0.0) - (tone_prior_30 or tone_30 or 0.0)) * 5.0)
    diversity = source_diversity(target_rows)
    timeline_days = len({parse_day(row.get("date", "")) for row in target_timeline if parse_day(row.get("date", ""))})
    confidence = round_score(min(100.0, len(target_rows) * 2.3 + timeline_days * 0.8 + diversity * 0.25))
    attention = round_score(45 + z * 14 + min(22.0, math.log1p(volume_30) * 3.2) + max(0.0, volume_7 - previous_7) * 0.25)

    return {
        "media_tone_raw": round(tone_30, 4) if tone_30 is not None else "",
        "news_tone_score": score_from_tone(tone_30) if tone_30 is not None else "",
        "investor_tone_score": score_from_tone(investor_tone_30) if investor_tone_30 is not None else "",
        "mention_volume": round(volume_30, 4),
        "mention_volume_7d": round(volume_7, 4),
        "mention_volume_zscore": round(z, 4),
        "attention_score": attention,
        "sentiment_momentum_7d": momentum_7,
        "sentiment_momentum_30d": momentum_30,
        "negative_news_spike_score": negative_score,
        "positive_news_spike_score": positive_score,
        "source_diversity_score": diversity,
        "coverage_confidence": confidence,
        "demand_tailwind_score": round_score(50 + demand_z * 14 + min(24.0, math.log1p(demand_7) * 5.0)),
        "demand_risk_score": "",
        "investor_positive_score": "",
        "investor_negative_score": "",
        "company_positive_score": "",
        "company_risk_score": "",
        "llm_relevant_articles": 0,
        "llm_total_articles": 0,
        "llm_average_confidence": "",
        "scoring_method": "gdelt_fallback",
    }


def build_llm_target_stats(
    llm_rows: list[dict[str, str]],
    raw_rows: list[dict[str, str]],
    timeline_rows: list[dict[str, str]],
    end_day: date,
) -> dict[str, Any]:
    if not llm_rows:
        return build_target_stats(raw_rows, timeline_rows, end_day)

    relevant = [
        row for row in llm_rows
        if parse_bool(row.get("is_relevant", ""))
        and row.get("narrative_type", "") != "irrelevant"
        and score_value(row, "confidence", 0.0) >= 0.35
        and score_value(row, "entity_confidence", 0.0) >= 0.35
    ]
    if not relevant:
        stats = empty_stats("llm")
        stats["mention_volume"] = len(llm_rows)
        stats["llm_total_articles"] = len(llm_rows)
        return stats

    positive_weight = 0.0
    negative_weight = 0.0
    investor_positive = 0.0
    investor_negative = 0.0
    demand_tailwind = 0.0
    demand_risk = 0.0
    company_positive = 0.0
    company_risk = 0.0
    positive_recent = 0.0
    negative_recent = 0.0
    confidence_values = []
    article_days = []

    for row in relevant:
        confidence = score_value(row, "confidence", 0.0)
        entity = score_value(row, "entity_confidence", 0.0)
        intensity = score_value(row, "intensity", 0.0)
        weight = max(0.05, confidence * entity * intensity)
        confidence_values.append(confidence)
        article_day = parse_day(row.get("published_at", ""))
        if article_day is not None:
            article_days.append(article_day)
            if article_day >= end_day - timedelta(days=13):
                if row.get("market_implication") == "positive":
                    positive_recent += weight
                elif row.get("market_implication") == "negative":
                    negative_recent += weight

        implication = row.get("market_implication", "")
        narrative = row.get("narrative_type", "")
        if implication == "positive":
            positive_weight += weight
        elif implication == "negative":
            negative_weight += weight
        elif implication == "mixed":
            positive_weight += weight * 0.45
            negative_weight += weight * 0.45

        if narrative in {"investor_positive", "macro_tailwind"}:
            investor_positive += weight
        elif narrative in {"investor_negative", "macro_risk", "regulatory_risk"}:
            investor_negative += weight
        elif narrative == "demand_tailwind":
            demand_tailwind += weight
        elif narrative == "demand_risk":
            demand_risk += weight
        elif narrative == "company_positive":
            company_positive += weight
        elif narrative == "company_risk":
            company_risk += weight

    total_weight = positive_weight + negative_weight
    investor_total = investor_positive + investor_negative
    company_total = company_positive + company_risk
    demand_total = demand_tailwind + demand_risk
    all_signal_weight = total_weight + demand_total + company_total + investor_total
    article_count = len(relevant)
    diversity = source_diversity(relevant)
    timeline_days = len({parse_day(row.get("date", "")) for row in timeline_rows if parse_day(row.get("date", ""))})
    volume_series: dict[date, float] = defaultdict(float)
    for row in timeline_rows:
        day = parse_day(row.get("date", ""))
        value = as_float(row, "value")
        if day is not None and row.get("metric") == "volume_raw" and value is not None:
            volume_series[day] += max(0.0, value)
    for day in article_days:
        volume_series[day] += 1.0
    volume_30 = period_sum(volume_series, end_day, 30)
    volume_7 = period_sum(volume_series, end_day, 7)
    previous_7 = period_sum(volume_series, end_day - timedelta(days=7), 7)
    volume_z = zscore(volume_7 / 7.0, daily_values(volume_series, end_day, 90))

    confidence = round_score(min(100.0, article_count * 7.5 + timeline_days * 0.5 + diversity * 0.2 + mean(confidence_values) * 25.0))
    attention = round_score(min(100.0, 20.0 + volume_z * 14 + math.log1p(max(volume_30, article_count)) * 8.5 + article_count * 2.5))
    market_score = weighted_score(positive_weight + demand_tailwind + company_positive, negative_weight + demand_risk + company_risk)
    investor_score = weighted_score(investor_positive + company_positive * 0.35, investor_negative + company_risk * 0.35)
    negative_score = intensity_score(negative_recent + demand_risk + company_risk, all_signal_weight)
    positive_score = intensity_score(positive_recent + demand_tailwind + company_positive, all_signal_weight)

    return {
        "media_tone_raw": "",
        "news_tone_score": market_score,
        "investor_tone_score": investor_score,
        "mention_volume": round(volume_30 or article_count, 4),
        "mention_volume_7d": round(volume_7, 4),
        "mention_volume_zscore": round(volume_z, 4),
        "attention_score": attention,
        "sentiment_momentum_7d": "",
        "sentiment_momentum_30d": "",
        "negative_news_spike_score": negative_score,
        "positive_news_spike_score": positive_score,
        "source_diversity_score": diversity,
        "coverage_confidence": confidence,
        "demand_tailwind_score": intensity_score(demand_tailwind, demand_total),
        "demand_risk_score": intensity_score(demand_risk, demand_total),
        "investor_positive_score": intensity_score(investor_positive, investor_total),
        "investor_negative_score": intensity_score(investor_negative, investor_total),
        "company_positive_score": intensity_score(company_positive, company_total),
        "company_risk_score": intensity_score(company_risk, company_total),
        "llm_relevant_articles": article_count,
        "llm_total_articles": len(llm_rows),
        "llm_average_confidence": round(mean(confidence_values), 4) if confidence_values else "",
        "scoring_method": "llm",
    }


def classify_state(row: dict[str, Any]) -> str:
    coverage = score_value(row, "coverage_confidence", 0.0)
    tone = score_value(row, "news_tone_score", 50.0)
    investor = score_value(row, "investor_tone_score", 50.0)
    attention = score_value(row, "attention_score", 0.0)
    momentum = score_value(row, "sentiment_momentum_7d", 50.0)
    negative = score_value(row, "negative_news_spike_score", 0.0)
    positive = score_value(row, "positive_news_spike_score", 0.0)
    market = score_value(row, "market_context_score", 50.0)
    demand = score_value(row, "demand_tailwind_score", 0.0)
    demand_risk = score_value(row, "demand_risk_score", 0.0)
    company_risk = score_value(row, "company_risk_score", 0.0)

    if coverage < 25:
        return "Ignored / Low Coverage"
    if investor >= 68 and attention >= 72 and market >= 63:
        return "Crowded Positive"
    if tone <= 44 and market >= 58 and momentum >= 50:
        return "Contrarian Improving"
    if demand >= 68 and attention >= 45:
        return "Demand Tailwind Spike"
    if attention >= 70 and (negative >= 66 or demand_risk >= 66 or company_risk >= 66):
        return "Fear-Driven Attention Spike"
    if investor >= 62 and momentum >= 57 and positive >= negative:
        return "Positive Investor Momentum"
    if investor <= 42 and momentum <= 46 and market <= 46:
        return "Narrative Breakdown"
    if investor <= 42 or (negative >= 65 and momentum <= 48):
        return "Negative Investor Momentum"
    return "Mixed / Noisy"


def build_reason(row: dict[str, Any]) -> tuple[str, str]:
    positives = []
    risks = []
    if row.get("scoring_method") == "llm":
        positives.append("LLM narrative classification is active")
    if score_value(row, "investor_tone_score") >= 62:
        positives.append("investor-facing coverage is constructive")
    if score_value(row, "sentiment_momentum_7d") >= 58:
        positives.append("tone has improved over the latest week")
    if score_value(row, "attention_score", 0.0) >= 68:
        positives.append("coverage attention is rising")
    if score_value(row, "demand_tailwind_score", 0.0) >= 66:
        positives.append("demand-tailwind narrative is active")
    if not positives:
        positives.append("narrative signal is mixed")

    if score_value(row, "negative_news_spike_score", 0.0) >= 65:
        risks.append("negative narrative pressure is elevated")
    if score_value(row, "demand_risk_score", 0.0) >= 65:
        risks.append("demand-risk narrative is active")
    if score_value(row, "coverage_confidence", 0.0) < 35:
        risks.append("coverage is thin")
    if score_value(row, "attention_score", 0.0) >= 75 and score_value(row, "investor_tone_score") >= 65:
        risks.append("positive narrative may be crowded")
    if score_value(row, "market_context_score") < 42:
        risks.append("market context is not confirming")
    if not risks:
        risks.append("no major sentiment quality flag")
    return "; ".join(positives[:3]), "; ".join(risks[:3])


def top_headlines(rows: list[dict[str, str]]) -> tuple[dict[str, str] | None, dict[str, str] | None]:
    scored = [(article_tone(row), row) for row in rows if row.get("title") and row.get("url")]
    if not scored:
        return None, None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1], scored[-1][1]


def build() -> dict[str, Any]:
    config = load_market_config()
    sentiment_config = load_sentiment_config()
    raw_rows = read_csv(RAW_IN)
    timeline_rows = read_csv(TIMELINE_IN)
    llm_rows = read_csv(LLM_IN)
    raw_article_keys = {article_key(row) for row in raw_rows}
    if raw_article_keys:
        llm_rows = [row for row in llm_rows if row.get("article_key", "") in raw_article_keys]
    basket_context, ticker_context = market_context_scores()
    all_days = [
        day for day in [parse_day(row.get("published_at", "")) for row in raw_rows]
        if day is not None
    ] + [
        day for day in [parse_day(row.get("date", "")) for row in timeline_rows]
        if day is not None
    ] + [
        day for day in [parse_day(row.get("published_at", "")) for row in llm_rows]
        if day is not None
    ]
    end_day = max(all_days, default=config.end_date)
    run_date = datetime.now(UTC).isoformat(timespec="seconds")
    basket_meta = config.basket_meta

    raw_by_entity: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    timeline_by_entity: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    llm_by_entity: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in raw_rows:
        raw_by_entity[(row.get("basket", ""), row.get("ticker", ""))].append(row)
    for row in timeline_rows:
        timeline_by_entity[(row.get("basket", ""), row.get("ticker", ""))].append(row)
    for row in llm_rows:
        llm_by_entity[(row.get("basket", ""), row.get("ticker", ""))].append(row)

    ticker_specs = {
        (query.basket, query.ticker): query
        for query in sentiment_config.queries
        if query.ticker
    }
    ticker_rows = []
    for basket in config.baskets:
        for holding in basket.holdings:
            key = (basket.id, holding.ticker)
            spec = ticker_specs.get(key)
            rows = raw_by_entity.get(key, [])
            timeline = timeline_by_entity.get(key, [])
            llm = llm_by_entity.get(key, [])
            stats = build_llm_target_stats(llm, rows, timeline, end_day)
            stats["market_context_score"] = ticker_context.get(holding.ticker, 50.0)
            stats["sentiment_state"] = classify_state(stats)
            positive, negative = top_headlines(rows)
            ticker_rows.append(
                {
                    "run_date": run_date,
                    "basket": basket.id,
                    "ticker": holding.ticker,
                    "label": basket.label,
                    "company_name": spec.company_name if spec else holding.name,
                    **stats,
                    "top_positive_headline": positive.get("title", "") if positive else "",
                    "top_positive_url": positive.get("url", "") if positive else "",
                    "top_negative_headline": negative.get("title", "") if negative else "",
                    "top_negative_url": negative.get("url", "") if negative else "",
                }
            )

    basket_rows = []
    for basket in config.baskets:
        rows = raw_by_entity.get((basket.id, ""), []) + [
            row for (row_basket, ticker), entity_rows in raw_by_entity.items()
            if row_basket == basket.id and ticker
            for row in entity_rows
        ]
        timeline = timeline_by_entity.get((basket.id, ""), []) + [
            row for (row_basket, ticker), entity_rows in timeline_by_entity.items()
            if row_basket == basket.id and ticker
            for row in entity_rows
        ]
        llm = llm_by_entity.get((basket.id, ""), []) + [
            row for (row_basket, ticker), entity_rows in llm_by_entity.items()
            if row_basket == basket.id and ticker
            for row in entity_rows
        ]
        stats = build_llm_target_stats(llm, rows, timeline, end_day)
        stats["market_context_score"] = basket_context.get(basket.id, 50.0)
        stats["basket_sentiment_state"] = classify_state(stats)
        primary, risk = build_reason(stats)
        basket_rows.append(
            {
                "rank": 0,
                "run_date": run_date,
                "date": end_day.isoformat(),
                "basket": basket.id,
                "label": basket.label,
                "short": basket.short,
                "basket_news_tone_score": stats["news_tone_score"],
                "basket_investor_tone_score": stats["investor_tone_score"],
                "basket_attention_score": stats["attention_score"],
                "basket_sentiment_momentum": stats["sentiment_momentum_7d"],
                "basket_negative_spike_score": stats["negative_news_spike_score"],
                "basket_positive_spike_score": stats["positive_news_spike_score"],
                "source_diversity_score": stats["source_diversity_score"],
                "coverage_confidence": stats["coverage_confidence"],
                "demand_tailwind_score": stats["demand_tailwind_score"],
                "demand_risk_score": stats["demand_risk_score"],
                "investor_positive_score": stats["investor_positive_score"],
                "investor_negative_score": stats["investor_negative_score"],
                "company_positive_score": stats["company_positive_score"],
                "company_risk_score": stats["company_risk_score"],
                "llm_relevant_articles": stats["llm_relevant_articles"],
                "llm_total_articles": stats["llm_total_articles"],
                "llm_average_confidence": stats["llm_average_confidence"],
                "scoring_method": stats["scoring_method"],
                "market_context_score": stats["market_context_score"],
                "basket_sentiment_state": stats["basket_sentiment_state"],
                "mention_volume": stats["mention_volume"],
                "mention_volume_zscore": stats["mention_volume_zscore"],
                "primary_signal": primary,
                "risk_signal": risk,
                "color": basket_meta[basket.id]["color"],
                "accent": basket_meta[basket.id]["accent"],
            }
        )

    basket_rows.sort(
        key=lambda row: (
            score_value(row, "basket_attention_score", 0.0) * 0.35
            + score_value(row, "basket_news_tone_score") * 0.25
            + score_value(row, "basket_sentiment_momentum") * 0.25
            + score_value(row, "coverage_confidence", 0.0) * 0.15
        ),
        reverse=True,
    )
    for rank, row in enumerate(basket_rows, start=1):
        row["rank"] = rank

    event_rows = []
    for row in llm_rows:
        if not parse_bool(row.get("is_relevant", "")):
            continue
        implication = row.get("market_implication", "unclear")
        narrative = row.get("narrative_type", "mixed")
        event_rows.append(
            {
                "run_date": run_date,
                "basket": row.get("basket", ""),
                "ticker": row.get("ticker", ""),
                "query_type": row.get("query_type", ""),
                "event_type": f"LLM {narrative}",
                "event_score": round_score(score_value(row, "intensity", 0.0) * score_value(row, "confidence", 0.0) * 100.0),
                "published_at": row.get("published_at", ""),
                "source": row.get("source", ""),
                "domain": row.get("domain", ""),
                "title": row.get("title", ""),
                "url": row.get("url", ""),
                "tone_score": 1.0 if implication == "positive" else -1.0 if implication == "negative" else 0.0,
                "entity_confidence": round_score(score_value(row, "entity_confidence", 0.0) * 100.0),
                "is_market_relevant": True,
            }
        )
    for key, rows in raw_by_entity.items():
        basket, ticker = key
        if not basket:
            continue
        scored = sorted(
            [(article_tone(row), row) for row in rows if row.get("title") and row.get("url")],
            key=lambda item: item[0],
            reverse=True,
        )
        candidates = scored[:2] + scored[-2:]
        for tone_value, row in candidates:
            event_type = "Positive headline" if tone_value >= 0 else "Negative headline"
            event_rows.append(
                {
                    "run_date": run_date,
                    "basket": basket,
                    "ticker": ticker,
                    "query_type": row.get("query_type", ""),
                    "event_type": event_type,
                    "event_score": score_from_tone(tone_value),
                    "published_at": row.get("published_at", ""),
                    "source": row.get("source", ""),
                    "domain": row.get("domain", ""),
                    "title": row.get("title", ""),
                    "url": row.get("url", ""),
                    "tone_score": round(tone_value, 4),
                    "entity_confidence": round_score(entity_confidence(row)),
                    "is_market_relevant": is_market_relevant(row),
                }
            )
    event_rows = sorted(event_rows, key=lambda row: (row["basket"], row["ticker"], row["published_at"]), reverse=True)[:250]

    ticker_fieldnames = [
        "run_date",
        "basket",
        "ticker",
        "label",
        "company_name",
        "news_tone_score",
        "investor_tone_score",
        "media_tone_raw",
        "mention_volume",
        "mention_volume_7d",
        "mention_volume_zscore",
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
        "llm_relevant_articles",
        "llm_total_articles",
        "llm_average_confidence",
        "scoring_method",
        "market_context_score",
        "sentiment_state",
        "top_positive_headline",
        "top_positive_url",
        "top_negative_headline",
        "top_negative_url",
    ]
    basket_fieldnames = [
        "rank",
        "run_date",
        "date",
        "basket",
        "label",
        "short",
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
        "llm_relevant_articles",
        "llm_total_articles",
        "llm_average_confidence",
        "scoring_method",
        "market_context_score",
        "basket_sentiment_state",
        "mention_volume",
        "mention_volume_zscore",
        "primary_signal",
        "risk_signal",
        "color",
        "accent",
    ]
    event_fieldnames = [
        "run_date",
        "basket",
        "ticker",
        "query_type",
        "event_type",
        "event_score",
        "published_at",
        "source",
        "domain",
        "title",
        "url",
        "tone_score",
        "entity_confidence",
        "is_market_relevant",
    ]
    write_csv(TICKER_OUT, ticker_fieldnames, ticker_rows)
    write_csv(BASKET_OUT, basket_fieldnames, basket_rows)
    write_csv(EVENTS_OUT, event_fieldnames, event_rows)

    providers = sorted({row.get("source_provider", "") for row in raw_rows + timeline_rows if row.get("source_provider")})
    if llm_rows:
        providers.append("OPENAI_RESPONSES")
    summary = {
        "generated_at": run_date,
        "latest_news_date": end_day.isoformat(),
        "provider": " + ".join(providers) if providers else "",
        "raw_article_rows": len(raw_rows),
        "timeline_rows": len(timeline_rows),
        "llm_analysis_rows": len(llm_rows),
        "ticker_rows": len(ticker_rows),
        "basket_rows": len(basket_rows),
        "event_rows": len(event_rows),
        "valid_states": sorted(VALID_STATES),
        "state_counts": {
            state: sum(1 for row in basket_rows if row["basket_sentiment_state"] == state)
            for state in sorted(VALID_STATES)
        },
        "methodology": {
            "news_tone_score": "When LLM analysis is available, market implication is aggregated from structured narrative classifications. Otherwise, GDELT tone is used as a fallback.",
            "attention_score": "Recent seven-day coverage is compared with the trailing daily distribution and scaled with thirty-day volume.",
            "coverage_confidence": "Blend of relevant LLM-classified article count, timeline depth, source diversity, and model confidence.",
            "market_context_score": "Existing price/rotation metrics are used only after news scoring for state classification context.",
        },
    }
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    summary = build()
    print(
        f"Wrote sentiment signals for {summary['basket_rows']} baskets, "
        f"{summary['ticker_rows']} tickers, {summary['event_rows']} events"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
