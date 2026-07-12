#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from market_config import ROOT


DATA_DIR = ROOT / "data"
SENTIMENT_DIR = DATA_DIR / "sentiment"
RAW_IN = SENTIMENT_DIR / "news_raw.csv"
JSONL_OUT = SENTIMENT_DIR / "news_llm_analysis.jsonl"
CSV_OUT = SENTIMENT_DIR / "news_llm_analysis.csv"
API_URL = "https://api.openai.com/v1/responses"
PROMPT_VERSION = "market_narrative_v1"
DEFAULT_MODEL = "gpt-5.4-nano"

NARRATIVE_TYPES = [
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
]

CSV_FIELDS = [
    "analysis_id",
    "article_key",
    "run_date",
    "source_provider",
    "model",
    "prompt_version",
    "basket",
    "ticker",
    "company_name",
    "query_type",
    "query",
    "published_at",
    "source",
    "domain",
    "title",
    "url",
    "is_relevant",
    "entity_confidence",
    "narrative_type",
    "market_implication",
    "affected_level",
    "affected_tickers",
    "intensity",
    "time_horizon",
    "summary",
    "reasoning_label",
    "confidence",
]


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "is_relevant": {
            "type": "boolean",
            "description": "Whether the article is relevant to the specified basket, ticker, company, or market narrative.",
        },
        "entity_confidence": {
            "type": "number",
            "description": "0 to 1 confidence that the article is actually about the specified basket/ticker/company.",
        },
        "narrative_type": {
            "type": "string",
            "enum": NARRATIVE_TYPES,
            "description": "The dominant market narrative carried by the article.",
        },
        "market_implication": {
            "type": "string",
            "enum": ["positive", "negative", "mixed", "neutral", "unclear"],
            "description": "Market implication for the basket/ticker, not generic article tone.",
        },
        "affected_level": {
            "type": "string",
            "enum": ["ticker", "basket", "macro", "irrelevant"],
        },
        "affected_tickers": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Tickers directly affected by the article, if any.",
        },
        "intensity": {
            "type": "number",
            "description": "0 to 1 strength of the narrative signal.",
        },
        "time_horizon": {
            "type": "string",
            "enum": ["immediate", "short", "medium", "long", "unknown"],
        },
        "summary": {
            "type": "string",
            "description": "One concise sentence explaining the market narrative.",
        },
        "reasoning_label": {
            "type": "string",
            "enum": [
                "bad-world-news-good-sector-demand",
                "company-execution-positive",
                "company-execution-negative",
                "investor-sentiment-positive",
                "investor-sentiment-negative",
                "macro-tailwind",
                "macro-risk",
                "regulatory-overhang",
                "attention-without-clear-implication",
                "not-market-relevant",
                "mixed-or-conflicted",
            ],
        },
        "confidence": {
            "type": "number",
            "description": "0 to 1 confidence in this classification.",
        },
    },
    "required": [
        "is_relevant",
        "entity_confidence",
        "narrative_type",
        "market_implication",
        "affected_level",
        "affected_tickers",
        "intensity",
        "time_horizon",
        "summary",
        "reasoning_label",
        "confidence",
    ],
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def load_existing(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open() as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


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


def analysis_id(article_hash: str, model: str, prompt_version: str) -> str:
    return hashlib.sha256(f"{article_hash}|{model}|{prompt_version}".encode("utf-8")).hexdigest()


def safe_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))


def extract_response_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    texts = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                texts.append(content["text"])
    if texts:
        return "\n".join(texts)
    raise ValueError("OpenAI response did not include output text")


def request_analysis(api_key: str, model: str, article: dict[str, str], timeout: int) -> dict[str, Any]:
    user_payload = {
        "basket": article.get("basket", ""),
        "ticker": article.get("ticker", ""),
        "company_name": article.get("company_name", ""),
        "query_type": article.get("query_type", ""),
        "query": article.get("query", ""),
        "published_at": article.get("published_at", ""),
        "source": article.get("source", ""),
        "domain": article.get("domain", ""),
        "title": article.get("title", ""),
        "url": article.get("url", ""),
        "provider_sentiment_score": article.get("provider_sentiment_score", ""),
        "provider_sentiment_label": article.get("provider_sentiment_label", ""),
        "ticker_relevance_score": article.get("ticker_relevance_score", ""),
        "ticker_sentiment_score": article.get("ticker_sentiment_score", ""),
        "ticker_sentiment_label": article.get("ticker_sentiment_label", ""),
        "topics": article.get("topics", ""),
    }
    body = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You are a market narrative analyst. Classify the market implication of one news headline "
                    "for the specified market basket and ticker. Do not classify generic article tone. "
                    "A negative real-world event can be a positive demand signal for some baskets. "
                    "Be conservative: if the headline is not clearly relevant, mark it irrelevant."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(user_payload, sort_keys=True),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "market_news_narrative",
                "strict": True,
                "schema": SCHEMA,
            }
        },
        "max_output_tokens": 900,
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        parsed = json.loads(response.read().decode("utf-8"))
    return json.loads(extract_response_text(parsed))


def to_csv_row(record: dict[str, Any]) -> dict[str, Any]:
    analysis = record["analysis"]
    article = record["article"]
    return {
        "analysis_id": record["analysis_id"],
        "article_key": record["article_key"],
        "run_date": record["run_date"],
        "source_provider": "OPENAI_RESPONSES",
        "model": record["model"],
        "prompt_version": record["prompt_version"],
        "basket": article.get("basket", ""),
        "ticker": article.get("ticker", ""),
        "company_name": article.get("company_name", ""),
        "query_type": article.get("query_type", ""),
        "query": article.get("query", ""),
        "published_at": article.get("published_at", ""),
        "source": article.get("source", ""),
        "domain": article.get("domain", ""),
        "title": article.get("title", ""),
        "url": article.get("url", ""),
        "is_relevant": analysis.get("is_relevant", False),
        "entity_confidence": safe_float(analysis.get("entity_confidence")),
        "narrative_type": analysis.get("narrative_type", "irrelevant"),
        "market_implication": analysis.get("market_implication", "unclear"),
        "affected_level": analysis.get("affected_level", "irrelevant"),
        "affected_tickers": ";".join(str(value) for value in analysis.get("affected_tickers", [])),
        "intensity": safe_float(analysis.get("intensity")),
        "time_horizon": analysis.get("time_horizon", "unknown"),
        "summary": analysis.get("summary", ""),
        "reasoning_label": analysis.get("reasoning_label", "not-market-relevant"),
        "confidence": safe_float(analysis.get("confidence")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify cached news rows with OpenAI structured outputs.")
    parser.add_argument("--model", default=os.environ.get("OPENAI_SENTIMENT_MODEL", DEFAULT_MODEL))
    parser.add_argument("--limit", type=int, default=0, help="Maximum new articles to analyze.")
    parser.add_argument("--basket", default="", help="Optional basket id filter.")
    parser.add_argument("--ticker", default="", help="Optional ticker filter.")
    parser.add_argument("--force", action="store_true", help="Re-analyze even if cached results exist.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be analyzed without calling the API.")
    parser.add_argument("--pause", type=float, default=0.2, help="Pause between API requests.")
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.environ.get("OPENAI_SENTIMENT_WORKERS", "4")),
        help="Parallel OpenAI requests to run. Defaults to OPENAI_SENTIMENT_WORKERS or 4.",
    )
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    raw_rows = [
        row for row in read_csv(RAW_IN)
        if row.get("title") and row.get("url")
        and (not args.basket or row.get("basket") == args.basket)
        and (not args.ticker or row.get("ticker") == args.ticker)
    ]
    if not raw_rows:
        print("No raw article rows available for LLM analysis.")
        return 0

    existing_records = load_existing(JSONL_OUT)
    existing_by_id = {row.get("analysis_id", ""): row for row in existing_records}
    pending = []
    for row in raw_rows:
        key = article_key(row)
        record_id = analysis_id(key, args.model, PROMPT_VERSION)
        if not args.force and record_id in existing_by_id:
            continue
        pending.append((key, record_id, row))
    if args.limit:
        pending = pending[: args.limit]

    if args.dry_run:
        print(f"Would analyze {len(pending)} new article(s) using model {args.model}.")
        return 0

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("OPENAI_API_KEY is not set; skipping LLM sentiment analysis.")
        print("Set it externally, then rerun: export OPENAI_API_KEY='...'")
        return 0

    workers = max(1, args.workers)

    def analyze_one(item: tuple[str, str, dict[str, str]]) -> tuple[dict[str, Any] | None, str]:
        key, record_id, article = item
        try:
            analysis = request_analysis(api_key, args.model, article, args.timeout)
            return {
                "analysis_id": record_id,
                "article_key": key,
                "run_date": datetime.now(UTC).isoformat(timespec="seconds"),
                "model": args.model,
                "prompt_version": PROMPT_VERSION,
                "article": article,
                "analysis": analysis,
            }, ""
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            return None, f"OpenAI analysis failed for {article.get('url')}: {str(exc)[:220]}"

    new_records = []
    if workers == 1:
        for index, item in enumerate(pending, start=1):
            record, error = analyze_one(item)
            if record is not None:
                append_jsonl(JSONL_OUT, record)
                existing_by_id[record["analysis_id"]] = record
                new_records.append(record)
                article = record["article"]
                print(f"Analyzed {index}/{len(pending)}: {article.get('basket')}/{article.get('ticker') or 'basket'}")
            elif error:
                print(error)
            if index < len(pending):
                time.sleep(args.pause)
    else:
        print(f"Analyzing {len(pending)} article(s) with {workers} parallel worker(s).")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {}
            for item in pending:
                futures[executor.submit(analyze_one, item)] = item
                if args.pause > 0:
                    time.sleep(args.pause)
            for index, future in enumerate(as_completed(futures), start=1):
                record, error = future.result()
                if record is not None:
                    append_jsonl(JSONL_OUT, record)
                    existing_by_id[record["analysis_id"]] = record
                    new_records.append(record)
                    article = record["article"]
                    print(f"Analyzed {index}/{len(pending)}: {article.get('basket')}/{article.get('ticker') or 'basket'}")
                elif error:
                    print(error)

    all_records = list(existing_by_id.values())
    all_records.sort(key=lambda row: row.get("run_date", ""))
    write_csv(CSV_OUT, [to_csv_row(record) for record in all_records])
    print(f"Wrote {len(all_records)} cached LLM analysis row(s); {len(new_records)} new.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
