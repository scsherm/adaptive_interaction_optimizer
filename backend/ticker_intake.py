#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import json
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from category_workbench import TAXONOMY, category_state, dump_baskets_yaml, load_config_data
from market_config import ROOT, load_market_config
from taxonomy_config import add_taxonomy_candidate, load_effective_taxonomy, load_taxonomy_config


DATA_DIR = ROOT / "data"
CONTEXT_DIR = DATA_DIR / "ticker_context"
API_URL = "https://api.openai.com/v1/responses"
YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
STOCKANALYSIS_PROFILE_URL = "https://stockanalysis.com/stocks/{ticker}/company/"
DEFAULT_MODEL = "gpt-5.4-nano"
CONTEXT_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
CONTEXT_CACHE_VERSION = 2
USER_AGENT = "Mozilla/5.0 market-basket-analysis/1.0 contact@example.com"

STOPWORDS = {
    "A", "ADD", "ALL", "AN", "AND", "ARE", "AS", "AT", "BE", "BUT", "BY", "CAN", "DO", "FOR", "FROM",
    "HAVE", "I", "IF", "IN", "INTO", "IS", "IT", "ITS", "LIKE", "MAYBE", "ME", "NO",
    "NOW", "OF", "OK", "ON", "OPENAI", "OR", "PLEASE", "PLS", "RUN", "SHOULD", "SO", "STOCK", "STOCKS",
    "THAT", "THE", "THEM", "THIS", "TICKER", "TICKERS", "TO", "TOO", "WANT", "WE",
    "WITH", "YES", "YOU",
}


CLASSIFICATION_SCHEMA_BASE = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "classifications": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "ticker": {"type": "string"},
                    "is_valid_public_ticker": {"type": "boolean"},
                    "company_name": {"type": "string"},
                    "recommended_basket": {"type": "string"},
                    "taxonomy_path": {"type": "array", "items": {"type": "string"}},
                    "secondary_exposures": {"type": "array", "items": {"type": "string"}},
                    "alternate_baskets": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                    "rationale": {"type": "string"},
                    "suggested_note": {"type": "string"},
                    "needs_review": {"type": "boolean"},
                },
                "required": [
                    "ticker",
                    "is_valid_public_ticker",
                    "company_name",
                    "recommended_basket",
                    "taxonomy_path",
                    "secondary_exposures",
                    "alternate_baskets",
                    "confidence",
                    "rationale",
                    "suggested_note",
                    "needs_review",
                ],
            },
        }
    },
    "required": ["classifications"],
}


def read_csv(name: str) -> list[dict[str, str]]:
    path = DATA_DIR / name
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def safe_filename(ticker: str) -> str:
    return ticker.replace("-", "_").replace(".", "_")


def context_cache_path(ticker: str) -> Path:
    return CONTEXT_DIR / f"{safe_filename(ticker.upper())}.json"


def request_url(url: str, timeout: int = 12) -> tuple[int, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return int(getattr(response, "status", 200)), response.read().decode("utf-8", errors="replace")


def read_cached_context(ticker: str) -> dict[str, Any] | None:
    path = context_cache_path(ticker)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    fetched_at = payload.get("fetchedAtEpoch", 0)
    if payload.get("cacheVersion") != CONTEXT_CACHE_VERSION:
        return None
    if isinstance(fetched_at, (int, float)) and time.time() - fetched_at <= CONTEXT_CACHE_TTL_SECONDS:
        payload["cacheStatus"] = "cached"
        return payload
    return None


def write_cached_context(ticker: str, payload: dict[str, Any]) -> None:
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    context_cache_path(ticker).write_text(json.dumps(payload, indent=2, sort_keys=True))


def save_config_data(data: dict[str, Any]) -> None:
    from market_config import CONFIG_PATH

    CONFIG_PATH.write_text(dump_baskets_yaml(data))


def clean_ticker(value: str) -> str:
    ticker = value.strip().upper()
    ticker = ticker.removeprefix("$")
    ticker = ticker.replace("/", "-") if ticker.endswith("/USD") else ticker
    return ticker


def valid_ticker_shape(ticker: str) -> bool:
    if len(ticker) > 12:
        return False
    return bool(re.fullmatch(r"[A-Z0-9]{1,6}(?:[.-][A-Z0-9]{1,5})?(?:-USD)?", ticker))


def current_memberships() -> dict[str, list[str]]:
    memberships: dict[str, list[str]] = {}
    for basket in load_market_config().baskets:
        for holding in basket.holdings:
            memberships.setdefault(holding.ticker.upper(), []).append(basket.id)
    return memberships


def known_candidate_index() -> dict[str, dict[str, Any]]:
    taxonomy = load_effective_taxonomy(TAXONOMY)
    index: dict[str, dict[str, Any]] = {}
    for basket_id, row in taxonomy.items():
        for ticker, name, note in row.get("candidates", []):
            ticker = ticker.upper()
            index.setdefault(
                ticker,
                {
                    "ticker": ticker,
                    "name": name,
                    "note": note,
                    "basket": basket_id,
                    "taxonomyPath": row.get("path", []),
                    "candidateBaskets": [],
                },
            )
            index[ticker]["candidateBaskets"].append(basket_id)
    return index


def known_symbols() -> set[str]:
    symbols = set(current_memberships())
    symbols.update(row.get("ticker", "").upper() for row in read_csv("source_metadata.csv") if row.get("ticker"))
    symbols.update(known_candidate_index())
    return {ticker for ticker in symbols if ticker}


def sec_index_context(ticker: str) -> dict[str, Any]:
    path = DATA_DIR / "fundamentals" / "company_tickers.json"
    if not path.exists():
        return {"source": "sec_cache", "status": "missing"}
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"source": "sec_cache", "status": "error"}
    for row in payload.values() if isinstance(payload, dict) else []:
        if not isinstance(row, dict):
            continue
        if str(row.get("ticker", "")).upper() == ticker.upper():
            return {
                "source": "sec_cache",
                "status": "ok",
                "companyName": row.get("title", ""),
                "cik": row.get("cik_str", ""),
            }
    return {"source": "sec_cache", "status": "not_found"}


def yahoo_context(ticker: str) -> dict[str, Any]:
    url = f"{YAHOO_SEARCH_URL}?q={quote_plus(ticker)}&quotesCount=8&newsCount=0"
    try:
        status, text = request_url(url)
        payload = json.loads(text)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return {"source": "yahoo_search", "status": "error", "url": url, "error": str(exc)[:180]}
    quotes = payload.get("quotes", []) if isinstance(payload, dict) else []
    exact = None
    normalized = ticker.upper().replace(".", "-")
    for quote in quotes:
        symbol = str(quote.get("symbol", "")).upper()
        if symbol == ticker.upper() or symbol == normalized:
            exact = quote
            break
    if not exact:
        return {
            "source": "yahoo_search",
            "status": "not_found",
            "url": url,
            "alternates": [
                {
                    "symbol": quote.get("symbol", ""),
                    "name": quote.get("longname") or quote.get("shortname", ""),
                    "quoteType": quote.get("quoteType", ""),
                    "exchange": quote.get("exchDisp") or quote.get("exchange", ""),
                }
                for quote in quotes[:5]
                if isinstance(quote, dict)
            ],
        }
    return {
        "source": "yahoo_search",
        "status": "ok" if status < 400 else "error",
        "url": url,
        "symbol": exact.get("symbol", ""),
        "companyName": exact.get("longname") or exact.get("shortname", ""),
        "shortName": exact.get("shortname", ""),
        "exchange": exact.get("exchDisp") or exact.get("exchange", ""),
        "exchangeCode": exact.get("exchange", ""),
        "quoteType": exact.get("quoteType", ""),
        "sector": exact.get("sectorDisp") or exact.get("sector", ""),
        "industry": exact.get("industryDisp") or exact.get("industry", ""),
    }


def decode_js_string(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value


def clean_html_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def extract_js_string(text: str, key: str) -> str:
    pattern = re.compile(rf'{re.escape(key)}:"(?P<value>(?:\\.|[^"\\])*)"')
    match = pattern.search(text)
    return decode_js_string(match.group("value")) if match else ""


def stockanalysis_context(ticker: str) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Z0-9]{1,6}", ticker):
        return {"source": "stockanalysis_profile", "status": "skipped"}
    slug = ticker.lower()
    url = STOCKANALYSIS_PROFILE_URL.format(ticker=slug)
    try:
        status, text = request_url(url)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return {"source": "stockanalysis_profile", "status": "error", "url": url, "error": str(exc)[:180]}
    if status >= 400 or "404 - Page not found" in text:
        return {"source": "stockanalysis_profile", "status": "not_found", "url": url}
    description = clean_html_text(extract_js_string(text, "description"))
    name = ""
    profile_name_match = re.search(r"profile:\{name:\"(?P<value>(?:\\.|[^\"\\])*)\"", text)
    if profile_name_match:
        name = decode_js_string(profile_name_match.group("value"))
    sector = ""
    industry = ""
    sector_match = re.search(r"sector:\{value:\"(?P<value>(?:\\.|[^\"\\])*)\"", text)
    industry_match = re.search(r"industry:\{value:\"(?P<value>(?:\\.|[^\"\\])*)\"", text)
    if sector_match:
        sector = decode_js_string(sector_match.group("value"))
    if industry_match:
        industry = decode_js_string(industry_match.group("value"))
    return {
        "source": "stockanalysis_profile",
        "status": "ok" if description or sector or industry else "partial",
        "url": url,
        "companyName": name,
        "sector": sector,
        "industry": industry,
        "businessSummary": description[:1200],
    }


def strong_heuristic_basket(row: dict[str, Any]) -> tuple[str, float, str]:
    text = " ".join(
        str(row.get(key, ""))
        for key in ["companyName", "sector", "industry", "businessSummary", "localNote"]
    ).lower()
    checks = [
        ("quantum", 0.78, ["quantum", "qubit", "post-quantum", "quantum-safe", "annealing"]),
        ("semiconductors", 0.74, ["semiconductor", "chip", "gallium nitride", "silicon carbide", "power ic"]),
        ("power_grid", 0.72, ["nuclear", "fission", "power plant", "electricity", "electrical equipment", "utility", "grid"]),
        ("btc_mining_ai_pivot", 0.72, ["bitcoin mining", "crypto mining", "data center", "hpc", "hashrate"]),
        ("fertilizer", 0.78, ["fertilizer", "potash", "phosphate", "nitrogen", "ammonia", "crop nutrient"]),
        ("photonics", 0.74, ["photonics", "optical", "laser", "fiber", "transceiver"]),
        ("cybersecurity", 0.74, ["cybersecurity", "endpoint security", "zero trust", "identity security", "firewall"]),
        ("rare_earth_minerals", 0.74, ["rare earth", "critical minerals", "lithium", "antimony", "strategic metals"]),
        ("oil_tankers", 0.74, ["tanker", "marine transportation", "product tankers", "crude tankers"]),
        ("oil", 0.72, ["oil and gas", "exploration and production", "oilfield", "refining", "crude oil"]),
        ("construction", 0.72, ["homebuilder", "construction", "aggregates", "building materials", "equipment rental"]),
        ("software", 0.68, ["software", "saas", "cloud platform", "data platform", "observability"]),
        ("metals", 0.68, ["copper", "aluminum", "steel", "iron ore", "base metals"]),
    ]
    for basket_id, confidence, needles in checks:
        for needle in needles:
            if needle in text:
                return basket_id, confidence, f"Context keyword match: {needle}"
    return "", 0.0, ""


def fetch_external_context(ticker: str, refresh: bool = False) -> dict[str, Any]:
    if not refresh:
        cached = read_cached_context(ticker)
        if cached:
            return cached
    sources = [sec_index_context(ticker)]
    yahoo = yahoo_context(ticker)
    sources.append(yahoo)
    stock = stockanalysis_context(ticker)
    sources.append(stock)
    merged: dict[str, Any] = {
        "ticker": ticker,
        "companyName": "",
        "sector": "",
        "industry": "",
        "exchange": "",
        "instrumentType": "",
        "businessSummary": "",
        "sourceUrls": [],
        "contextSources": sources,
        "externalContextStatus": "missing",
        "fetchedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "fetchedAtEpoch": time.time(),
        "cacheStatus": "fresh",
        "cacheVersion": CONTEXT_CACHE_VERSION,
    }
    for source in sources:
        if source.get("status") not in {"ok", "partial"}:
            continue
        merged["companyName"] = merged["companyName"] or source.get("companyName", "")
        merged["sector"] = merged["sector"] or source.get("sector", "")
        merged["industry"] = merged["industry"] or source.get("industry", "")
        merged["exchange"] = merged["exchange"] or source.get("exchange", "")
        merged["instrumentType"] = merged["instrumentType"] or source.get("quoteType", "")
        merged["businessSummary"] = merged["businessSummary"] or source.get("businessSummary", "")
        if source.get("url"):
            merged["sourceUrls"].append(source["url"])
    if any(source.get("status") == "ok" for source in sources):
        merged["externalContextStatus"] = "ok"
    elif any(source.get("status") == "partial" for source in sources):
        merged["externalContextStatus"] = "partial"
    heuristic_basket, heuristic_confidence, heuristic_reason = strong_heuristic_basket(merged)
    merged["heuristicBasket"] = heuristic_basket
    merged["heuristicConfidence"] = heuristic_confidence
    merged["heuristicReason"] = heuristic_reason
    write_cached_context(ticker, merged)
    return merged


def apply_external_context(row: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    enriched = {**row}
    for key in ["companyName", "sector", "industry", "exchange", "instrumentType", "businessSummary"]:
        if context.get(key):
            enriched[key] = context[key]
    enriched["externalContextStatus"] = context.get("externalContextStatus", "missing")
    enriched["contextSources"] = context.get("contextSources", [])
    enriched["sourceUrls"] = context.get("sourceUrls", [])
    enriched["contextCacheStatus"] = context.get("cacheStatus", "")
    enriched["heuristicBasket"] = context.get("heuristicBasket", "")
    enriched["heuristicConfidence"] = context.get("heuristicConfidence", 0)
    enriched["heuristicReason"] = context.get("heuristicReason", "")
    if enriched.get("externalContextStatus") in {"ok", "partial"} and enriched.get("validationStatus") == "needs_review":
        enriched["validationStatus"] = "web_context"
    return enriched


def enrich_context_rows(rows: list[dict[str, Any]], refresh: bool = False, workers: int = 8) -> list[dict[str, Any]]:
    if not rows:
        return []
    workers = max(1, min(workers, 12))
    by_ticker: dict[str, dict[str, Any]] = {}
    if workers == 1 or len(rows) == 1:
        for row in rows:
            by_ticker[row["ticker"]] = fetch_external_context(row["ticker"], refresh=refresh)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(fetch_external_context, row["ticker"], refresh): row["ticker"]
                for row in rows
            }
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    by_ticker[ticker] = future.result()
                except Exception as exc:  # pragma: no cover - surfaced in API row context
                    by_ticker[ticker] = {
                        "ticker": ticker,
                        "externalContextStatus": "error",
                        "contextSources": [{"source": "context_worker", "status": "error", "error": str(exc)[:180]}],
                    }
    return [apply_external_context(row, by_ticker.get(row["ticker"], {})) for row in rows]


def parse_tickers(text: str) -> list[str]:
    text = text or ""
    symbols = known_symbols()
    commaish = "," in text or "\n" in text or ";" in text
    tokens = re.findall(r"\$?[A-Za-z][A-Za-z0-9]{0,5}(?:[.-][A-Za-z0-9]{1,5})?(?:-USD)?", text)
    parsed: list[str] = []
    seen: set[str] = set()
    for raw in tokens:
        ticker = clean_ticker(raw)
        if not valid_ticker_shape(ticker):
            continue
        raw_core = raw.removeprefix("$")
        explicit = raw.startswith("$") or raw_core.isupper() or any(ch in raw_core for ch in ".-")
        if not explicit and not commaish and ticker not in symbols:
            continue
        if not explicit and ticker in STOPWORDS:
            continue
        if ticker in STOPWORDS and ticker not in symbols and not raw.startswith("$"):
            continue
        if ticker not in seen:
            parsed.append(ticker)
            seen.add(ticker)
    return parsed


def context_rows(tickers: list[str], original_text: str = "") -> list[dict[str, Any]]:
    source = {row.get("ticker", "").upper(): row for row in read_csv("source_metadata.csv") if row.get("ticker")}
    fundamentals = {row.get("ticker", "").upper(): row for row in read_csv("fundamentals_metrics.csv") if row.get("ticker")}
    memberships = current_memberships()
    candidate_index = known_candidate_index()
    rows = []
    for ticker in tickers:
        source_row = source.get(ticker, {})
        fundamentals_row = fundamentals.get(ticker, {})
        candidate_row = candidate_index.get(ticker, {})
        name = (
            source_row.get("name")
            or fundamentals_row.get("sec_title")
            or candidate_row.get("name")
            or ticker
        )
        existing = memberships.get(ticker, [])
        rows.append(
            {
                "ticker": ticker,
                "companyName": name,
                "exchange": source_row.get("exchange", ""),
                "instrumentType": source_row.get("instrument_type", ""),
                "sourceSymbol": source_row.get("source_symbol", ""),
                "fundamentalsTitle": fundamentals_row.get("sec_title", ""),
                "existingBaskets": existing,
                "alreadyInConfig": bool(existing),
                "localCandidateBasket": candidate_row.get("basket", ""),
                "localCandidateBaskets": candidate_row.get("candidateBaskets", []),
                "localTaxonomyPath": candidate_row.get("taxonomyPath", []),
                "localNote": candidate_row.get("note", ""),
                "externalContextStatus": "",
                "contextSources": [],
                "sourceUrls": [],
                "sector": "",
                "industry": "",
                "businessSummary": "",
                "heuristicBasket": "",
                "heuristicConfidence": 0,
                "heuristicReason": "",
                "validationStatus": "cached" if source_row else "known_taxonomy" if candidate_row else "needs_review",
                "originalText": original_text,
            }
        )
    return rows


def parse_intake(text: str) -> dict[str, Any]:
    tickers = parse_tickers(text)
    return {
        "tickers": tickers,
        "rows": context_rows(tickers, text),
        "parsedAt": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def context_intake(text: str, refresh: bool = False, workers: int | None = None) -> dict[str, Any]:
    parsed = parse_intake(text)
    worker_count = workers or int(os.environ.get("TICKER_CONTEXT_WORKERS", "8"))
    rows = enrich_context_rows(parsed["rows"], refresh=refresh, workers=worker_count)
    return {
        **parsed,
        "rows": rows,
        "contextFetchedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "contextWorkers": max(1, min(worker_count, 12)),
    }


def model_from_config() -> str:
    config = load_taxonomy_config()
    classification = config.get("classification", {}) if isinstance(config.get("classification"), dict) else {}
    env_var = str(classification.get("env_model_var") or "OPENAI_TICKER_MODEL")
    return os.environ.get(env_var) or os.environ.get("OPENAI_MODEL") or str(classification.get("default_model") or DEFAULT_MODEL)


def openai_status(session_key: str = "", session_model: str = "") -> dict[str, Any]:
    return {
        "hasSessionKey": bool(session_key),
        "hasEnvKey": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
        "model": session_model or model_from_config(),
        "sessionOnly": bool(session_key),
    }


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


def taxonomy_prompt_rows() -> list[dict[str, Any]]:
    config = load_market_config()
    labels = {basket.id: basket.label for basket in config.baskets}
    effective = load_effective_taxonomy(TAXONOMY)
    rows = []
    for basket in config.baskets:
        row = effective.get(basket.id, {})
        rows.append(
            {
                "basket_id": basket.id,
                "label": labels[basket.id],
                "taxonomy_path": row.get("path", []),
                "description": row.get("description", ""),
                "keywords": row.get("keywords", []),
                "current_holdings": [
                    {"ticker": holding.ticker, "name": holding.name, "note": holding.note}
                    for holding in basket.holdings
                ],
            }
        )
    return rows


def request_openai_classification(
    api_key: str,
    model: str,
    rows: list[dict[str, Any]],
    original_text: str,
    timeout: int = 60,
) -> dict[str, Any]:
    basket_ids = [row["basket_id"] for row in taxonomy_prompt_rows()]
    schema = json.loads(json.dumps(CLASSIFICATION_SCHEMA_BASE))
    schema["properties"]["classifications"]["items"]["properties"]["recommended_basket"]["enum"] = basket_ids + ["unclassified"]
    schema["properties"]["classifications"]["items"]["properties"]["alternate_baskets"]["items"]["enum"] = basket_ids
    body = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": (
                    "You classify user-supplied market tickers into an existing layered investment taxonomy. "
                    "Use only the provided basket_id values for recommended_basket. Do not invent new basket ids. "
                    "Prefer exact business exposure over generic sector labels. If a ticker is invalid or cannot be "
                    "classified from the supplied context, use recommended_basket='unclassified' and needs_review=true. "
                    "Return concise rationale and a short basket note suitable for a config file."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "original_user_text": original_text,
                        "taxonomy": taxonomy_prompt_rows(),
                        "tickers": rows,
                        "classification_instruction": (
                            "Use web_context fields such as sector, industry, businessSummary, and contextSources. "
                            "The Yahoo/StockAnalysis/SEC context is more reliable than the bare ticker symbol."
                        ),
                    },
                    sort_keys=True,
                ),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "ticker_taxonomy_classification",
                "strict": True,
                "schema": schema,
            }
        },
        "max_output_tokens": 2200,
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


def chunked(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    size = max(1, size)
    return [items[index:index + size] for index in range(0, len(items), size)]


def classify_chunks(
    api_key: str,
    model: str,
    rows: list[dict[str, Any]],
    original_text: str,
    timeout: int,
    workers: int,
    chunk_size: int,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    chunks = chunked(rows, chunk_size)
    workers = max(1, min(workers, len(chunks) or 1))
    by_ticker: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    if workers == 1 or len(chunks) == 1:
        for chunk in chunks:
            try:
                response = request_openai_classification(api_key, model, chunk, original_text, timeout=timeout)
                for item in response.get("classifications", []):
                    if item.get("ticker"):
                        by_ticker[clean_ticker(item["ticker"])] = item
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                tickers = ", ".join(row["ticker"] for row in chunk)
                errors.append(f"{tickers}: {str(exc)[:180]}")
        return by_ticker, errors
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(request_openai_classification, api_key, model, chunk, original_text, timeout): chunk
            for chunk in chunks
        }
        for future in as_completed(futures):
            chunk = futures[future]
            try:
                response = future.result()
                for item in response.get("classifications", []):
                    if item.get("ticker"):
                        by_ticker[clean_ticker(item["ticker"])] = item
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                tickers = ", ".join(row["ticker"] for row in chunk)
                errors.append(f"{tickers}: {str(exc)[:180]}")
    return by_ticker, errors


def normalize_confidence(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, parsed))


def classify_intake(
    text: str,
    api_key: str,
    model: str = "",
    timeout: int = 60,
    context_workers: int | None = None,
    llm_workers: int | None = None,
    chunk_size: int | None = None,
    refresh_context: bool = False,
) -> dict[str, Any]:
    if not api_key:
        raise ValueError("OpenAI key is not active. Enter a key for this server session or export OPENAI_API_KEY.")
    parsed = context_intake(
        text,
        refresh=refresh_context,
        workers=context_workers or int(os.environ.get("TICKER_CONTEXT_WORKERS", "8")),
    )
    rows = parsed["rows"]
    if not rows:
        return {**parsed, "model": model or model_from_config(), "rows": []}
    model = model or model_from_config()
    by_ticker, classification_errors = classify_chunks(
        api_key,
        model,
        rows,
        text,
        timeout=timeout,
        workers=llm_workers or int(os.environ.get("OPENAI_TICKER_WORKERS", "4")),
        chunk_size=chunk_size or int(os.environ.get("OPENAI_TICKER_CHUNK_SIZE", "5")),
    )

    taxonomy = load_effective_taxonomy(TAXONOMY)
    basket_ids = set(taxonomy)
    classified_rows = []
    for row in rows:
        result = by_ticker.get(row["ticker"], {})
        heuristic_basket = row.get("heuristicBasket", "")
        recommended = str(
            result.get("recommended_basket")
            or row.get("localCandidateBasket")
            or heuristic_basket
            or "unclassified"
        )
        if recommended not in basket_ids:
            recommended = "unclassified"
        path = result.get("taxonomy_path") or (taxonomy.get(recommended, {}).get("path", []) if recommended != "unclassified" else [])
        company_name = str(result.get("company_name") or row.get("companyName") or row["ticker"])
        suggested_note = str(result.get("suggested_note") or row.get("localNote") or "LLM-classified candidate")
        confidence = normalize_confidence(result.get("confidence"))
        if not result and heuristic_basket:
            confidence = normalize_confidence(row.get("heuristicConfidence"))
            suggested_note = suggested_note if suggested_note != "LLM-classified candidate" else row.get("heuristicReason") or "web-context heuristic candidate"
        rationale = str(result.get("rationale") or "")
        if not rationale:
            if heuristic_basket:
                rationale = row.get("heuristicReason") or "Web context produced a strong taxonomy keyword match."
            elif row.get("externalContextStatus") in {"ok", "partial"}:
                rationale = "Web context found the company, but the LLM did not return a confident basket."
            else:
                rationale = "No LLM rationale returned."
        classified_rows.append(
            {
                **row,
                "companyName": company_name,
                "recommendedBasket": recommended,
                "taxonomyPath": path,
                "secondaryExposures": result.get("secondary_exposures", []),
                "alternateBaskets": [item for item in result.get("alternate_baskets", []) if item in basket_ids],
                "confidence": confidence,
                "rationale": rationale,
                "suggestedNote": suggested_note,
                "needsReview": bool(result.get("needs_review", confidence < 0.65 or recommended == "unclassified" or not result)),
                "isValidPublicTicker": bool(result.get("is_valid_public_ticker", row["validationStatus"] != "needs_review")),
                "selected": recommended != "unclassified" and not row.get("alreadyInConfig") and bool(result),
            }
        )
    return {
        **parsed,
        "rows": classified_rows,
        "model": model,
        "classificationErrors": classification_errors,
        "llmWorkers": llm_workers or int(os.environ.get("OPENAI_TICKER_WORKERS", "4")),
        "classifiedAt": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def add_approved_tickers(rows: list[dict[str, Any]]) -> dict[str, Any]:
    config = load_market_config()
    basket_ids = {basket.id for basket in config.baskets}
    config_data = load_config_data()
    added = []
    skipped = []
    for row in rows:
        if not row.get("selected", True):
            continue
        ticker = clean_ticker(str(row.get("ticker", "")))
        basket_id = str(row.get("basket") or row.get("recommendedBasket") or "")
        if not ticker or not valid_ticker_shape(ticker):
            skipped.append({"ticker": ticker, "reason": "Invalid ticker shape"})
            continue
        if basket_id not in basket_ids:
            skipped.append({"ticker": ticker, "reason": f"Unknown basket: {basket_id}"})
            continue
        name = str(row.get("name") or row.get("companyName") or ticker).strip() or ticker
        note = str(row.get("note") or row.get("suggestedNote") or "LLM-classified candidate").strip()
        taxonomy_path = [str(part) for part in row.get("taxonomyPath", []) if str(part).strip()]
        for basket in config_data["baskets"]:
            if basket["id"] != basket_id:
                continue
            existing = {holding["ticker"].upper() for holding in basket["holdings"]}
            if ticker in existing:
                skipped.append({"ticker": ticker, "basket": basket_id, "reason": "Already in basket"})
                break
            basket["holdings"].append({"ticker": ticker, "name": name, "note": note})
            add_taxonomy_candidate(basket_id, ticker, name, note, taxonomy_path)
            added.append({"ticker": ticker, "basket": basket_id, "name": name, "note": note})
            break
    if added:
        save_config_data(config_data)
    return {
        "added": added,
        "skipped": skipped,
        "state": category_state(),
    }
