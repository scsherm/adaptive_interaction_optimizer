#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from market_config import ROOT
from sentiment_config import SentimentQuery, load_sentiment_config


DATA_DIR = ROOT / "data"
SENTIMENT_DIR = DATA_DIR / "sentiment"
RAW_OUT = SENTIMENT_DIR / "news_raw.csv"
TIMELINE_OUT = SENTIMENT_DIR / "news_timeline_raw.csv"
FETCH_LOG_OUT = SENTIMENT_DIR / "news_fetch_log.csv"
DOC_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
YAHOO_SEARCH_ENDPOINT = "https://query2.finance.yahoo.com/v1/finance/search"
ALPHA_VANTAGE_ENDPOINT = "https://www.alphavantage.co/query"

RAW_FIELDS = [
    "run_date",
    "source_provider",
    "basket",
    "ticker",
    "company_name",
    "query_type",
    "query",
    "gdelt_query",
    "published_at",
    "source",
    "title",
    "url",
    "language",
    "tone_score",
    "domain",
    "source_country",
    "social_image",
    "provider_sentiment_score",
    "provider_sentiment_label",
    "ticker_relevance_score",
    "ticker_sentiment_score",
    "ticker_sentiment_label",
    "topics",
]

TIMELINE_FIELDS = [
    "run_date",
    "source_provider",
    "basket",
    "ticker",
    "company_name",
    "query_type",
    "query",
    "gdelt_query",
    "date",
    "metric",
    "value",
    "norm",
]

LOG_FIELDS = [
    "run_date",
    "source_provider",
    "basket",
    "ticker",
    "query_type",
    "query",
    "mode",
    "url",
    "status",
    "row_count",
    "message",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def now_stamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def timespan(days: int) -> str:
    if days % 30 == 0:
        return f"{days // 30}months"
    if days % 7 == 0:
        return f"{days // 7}weeks"
    return f"{days}d"


def exclusion(term: str) -> str:
    term = term.strip()
    if not term:
        return ""
    if " " in term:
        return f'-"{term}"'
    return f"-{term}"


def build_gdelt_query(spec: SentimentQuery, language_filter: str, global_exclude: tuple[str, ...]) -> str:
    pieces = [spec.term.strip()]
    if language_filter:
        pieces.append(language_filter)
    for term in (*global_exclude, *spec.exclude):
        token = exclusion(term)
        if token:
            pieces.append(token)
    return " ".join(pieces)


def fetch_json(url: str, timeout: int = 45, retries: int = 2) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 market-basket-sentiment/1.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8-sig", errors="replace")
            if body.lstrip().startswith("{") or body.lstrip().startswith("["):
                parsed = json.loads(body)
                if isinstance(parsed, list):
                    return {"items": parsed}
                return parsed
            raise ValueError(body.strip()[:240])
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < retries:
                time.sleep(12 * (attempt + 1))
                continue
            raise
    raise RuntimeError("unreachable fetch retry state")


def endpoint_url(query: str, mode: str, days: int, max_records: int) -> str:
    params = {
        "query": query,
        "mode": mode,
        "format": "json",
        "timespan": timespan(days),
    }
    if mode.lower() == "artlist":
        params["maxrecords"] = str(max_records)
        params["sort"] = "datedesc"
    else:
        params["timelinesmooth"] = "0"
    return DOC_ENDPOINT + "?" + urllib.parse.urlencode(params)


def yahoo_search_url(query: str, max_records: int) -> str:
    params = {
        "q": query,
        "quotesCount": "0",
        "newsCount": str(max_records),
        "listsCount": "0",
        "enableFuzzyQuery": "false",
        "quotesQueryId": "tss_match_phrase_query",
        "multiQuoteQueryId": "multi_quote_single_token_query",
        "newsQueryId": "news_cie_vespa",
        "enableCb": "true",
        "enableNavLinks": "false",
        "enableEnhancedTrivialQuery": "true",
    }
    return YAHOO_SEARCH_ENDPOINT + "?" + urllib.parse.urlencode(params)


def alpha_vantage_url(ticker: str, days: int, max_records: int, api_key: str) -> str:
    since = datetime.now(UTC) - timedelta(days=days)
    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": ticker.replace("-USD", ""),
        "time_from": since.strftime("%Y%m%dT%H%M"),
        "sort": "LATEST",
        "limit": str(max_records),
        "apikey": api_key,
    }
    return ALPHA_VANTAGE_ENDPOINT + "?" + urllib.parse.urlencode(params)


def domain_from_url(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    except ValueError:
        return ""


def parse_seen_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC).isoformat(timespec="seconds")
        except ValueError:
            pass
    return text


def parse_unix_date(value: Any) -> str:
    try:
        timestamp = int(float(value))
    except (TypeError, ValueError):
        return ""
    return datetime.fromtimestamp(timestamp, UTC).isoformat(timespec="seconds")


def first_value(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return ""


def parse_articles(payload: dict[str, Any], spec: SentimentQuery, gdelt_query: str, run_date: str) -> list[dict[str, Any]]:
    articles = payload.get("articles") or payload.get("items") or payload.get("results") or []
    rows = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        url = str(first_value(article, ("url", "URL", "link", "uri")))
        domain = str(first_value(article, ("domain", "sourceDomain", "sourceurl")) or domain_from_url(url))
        rows.append(
            {
                "run_date": run_date,
                "source_provider": "GDELT_DOC",
                "basket": spec.basket,
                "ticker": spec.ticker,
                "company_name": spec.company_name,
                "query_type": spec.query_type,
                "query": spec.term,
                "gdelt_query": gdelt_query,
                "published_at": parse_seen_date(first_value(article, ("seendate", "seenDate", "date", "published_at"))),
                "source": str(first_value(article, ("source", "sourceName", "domain")) or domain),
                "title": str(first_value(article, ("title", "headline", "name"))),
                "url": url,
                "language": str(first_value(article, ("language", "lang", "sourcelang"))),
                "tone_score": str(first_value(article, ("tone", "tonescore", "tone_score", "avgTone"))),
                "domain": domain,
                "source_country": str(first_value(article, ("sourcecountry", "sourceCountry"))),
                "social_image": str(first_value(article, ("socialimage", "image", "imageurl"))),
                "provider_sentiment_score": "",
                "provider_sentiment_label": "",
                "ticker_relevance_score": "",
                "ticker_sentiment_score": "",
                "ticker_sentiment_label": "",
                "topics": "",
            }
        )
    return rows


def yahoo_query(spec: SentimentQuery) -> str:
    if spec.company_name:
        return spec.company_name
    if spec.aliases:
        return spec.aliases[0]
    return spec.term


def yahoo_image(article: dict[str, Any]) -> str:
    thumbnail = article.get("thumbnail")
    if not isinstance(thumbnail, dict):
        return ""
    resolutions = thumbnail.get("resolutions")
    if not isinstance(resolutions, list) or not resolutions:
        return ""
    first = resolutions[0]
    if isinstance(first, dict):
        return str(first.get("url", ""))
    return ""


def parse_yahoo_articles(
    payload: dict[str, Any],
    spec: SentimentQuery,
    query: str,
    run_date: str,
    days: int,
) -> list[dict[str, Any]]:
    rows = []
    cutoff = datetime.now(UTC).timestamp() - days * 86400
    for article in payload.get("news", []):
        if not isinstance(article, dict):
            continue
        published_ts = article.get("providerPublishTime")
        try:
            if published_ts is not None and float(published_ts) < cutoff:
                continue
        except (TypeError, ValueError):
            pass
        url = str(article.get("link", ""))
        related = article.get("relatedTickers", [])
        related_text = ";".join(str(item) for item in related) if isinstance(related, list) else ""
        domain = domain_from_url(url)
        rows.append(
            {
                "run_date": run_date,
                "source_provider": "YAHOO_FINANCE",
                "basket": spec.basket,
                "ticker": spec.ticker,
                "company_name": spec.company_name,
                "query_type": spec.query_type,
                "query": spec.term,
                "gdelt_query": f"yahoo:{query}",
                "published_at": parse_unix_date(published_ts),
                "source": str(article.get("publisher", "") or domain),
                "title": str(article.get("title", "")),
                "url": url,
                "language": "English",
                "tone_score": "",
                "domain": domain,
                "source_country": "",
                "social_image": yahoo_image(article),
                "related_tickers": related_text,
                "provider_sentiment_score": "",
                "provider_sentiment_label": "",
                "ticker_relevance_score": "",
                "ticker_sentiment_score": "",
                "ticker_sentiment_label": "",
                "topics": "",
            }
        )
    return rows


def alpha_topics(article: dict[str, Any]) -> str:
    topics = article.get("topics", [])
    if not isinstance(topics, list):
        return ""
    values = []
    for topic in topics:
        if isinstance(topic, dict):
            name = topic.get("topic", "")
            relevance = topic.get("relevance_score", "")
            if name:
                values.append(f"{name}:{relevance}")
    return ";".join(values)


def alpha_ticker_sentiment(article: dict[str, Any], ticker: str) -> dict[str, str]:
    normalized = ticker.replace("-USD", "").upper()
    rows = article.get("ticker_sentiment", [])
    if not isinstance(rows, list):
        return {}
    fallback = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not fallback:
            fallback = row
        row_ticker = str(row.get("ticker", "")).replace("CRYPTO:", "").upper()
        if row_ticker == normalized:
            return row
    return fallback


def parse_alpha_vantage_articles(
    payload: dict[str, Any],
    spec: SentimentQuery,
    query: str,
    run_date: str,
) -> tuple[list[dict[str, Any]], str]:
    if "Note" in payload:
        return [], str(payload["Note"])
    if "Information" in payload:
        return [], str(payload["Information"])
    if "Error Message" in payload:
        return [], str(payload["Error Message"])
    rows = []
    for article in payload.get("feed", []):
        if not isinstance(article, dict):
            continue
        url = str(article.get("url", ""))
        ticker_row = alpha_ticker_sentiment(article, spec.ticker)
        rows.append(
            {
                "run_date": run_date,
                "source_provider": "ALPHA_VANTAGE_NEWS_SENTIMENT",
                "basket": spec.basket,
                "ticker": spec.ticker,
                "company_name": spec.company_name,
                "query_type": spec.query_type,
                "query": spec.term,
                "gdelt_query": f"alpha_vantage:{query}",
                "published_at": parse_seen_date(article.get("time_published", "")),
                "source": str(article.get("source", "")),
                "title": str(article.get("title", "")),
                "url": url,
                "language": "English",
                "tone_score": "",
                "domain": str(article.get("source_domain", "") or domain_from_url(url)),
                "source_country": "",
                "social_image": str(article.get("banner_image", "")),
                "provider_sentiment_score": str(article.get("overall_sentiment_score", "")),
                "provider_sentiment_label": str(article.get("overall_sentiment_label", "")),
                "ticker_relevance_score": str(ticker_row.get("relevance_score", "")),
                "ticker_sentiment_score": str(ticker_row.get("ticker_sentiment_score", "")),
                "ticker_sentiment_label": str(ticker_row.get("ticker_sentiment_label", "")),
                "topics": alpha_topics(article),
            }
        )
    return rows, ""


def timeline_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("timeline", "Timeline", "data", "items", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            rows: list[dict[str, Any]] = []
            for item in value:
                if not isinstance(item, dict):
                    continue
                if isinstance(item.get("data"), list):
                    series_name = item.get("series", "")
                    for point in item["data"]:
                        if isinstance(point, dict):
                            point_row = dict(point)
                            point_row["series"] = series_name
                            rows.append(point_row)
                    continue
                rows.append(item)
            return rows
    return []


def parse_timeline(
    payload: dict[str, Any],
    spec: SentimentQuery,
    gdelt_query: str,
    run_date: str,
    metric: str,
) -> list[dict[str, Any]]:
    rows = []
    for item in timeline_entries(payload):
        date_value = first_value(item, ("date", "datetime", "time", "Date"))
        metric_value = first_value(item, ("value", "Value", "tone", "volume", "count", "articles"))
        rows.append(
            {
                "run_date": run_date,
                "source_provider": "GDELT_DOC",
                "basket": spec.basket,
                "ticker": spec.ticker,
                "company_name": spec.company_name,
                "query_type": spec.query_type,
                "query": spec.term,
                "gdelt_query": gdelt_query,
                "date": parse_seen_date(date_value),
                "metric": metric,
                "value": metric_value,
                "norm": first_value(item, ("norm", "Norm")),
            }
        )
    return rows


def dedupe_rows(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen = set()
    unique = []
    for row in rows:
        dedupe_key = tuple(str(row.get(key, "")) for key in keys)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        unique.append(row)
    return unique


def log_row(
    run_date: str,
    spec: SentimentQuery,
    provider: str,
    mode: str,
    url: str,
    status: str,
    row_count: int,
    message: str = "",
) -> dict[str, Any]:
    return {
        "run_date": run_date,
        "source_provider": provider,
        "basket": spec.basket,
        "ticker": spec.ticker,
        "query_type": spec.query_type,
        "query": spec.term,
        "mode": mode,
        "url": url,
        "status": status,
        "row_count": row_count,
        "message": message,
    }


def selected_queries(args: argparse.Namespace) -> list[SentimentQuery]:
    config = load_sentiment_config()
    queries = []
    for query in config.queries:
        if args.basket and query.basket != args.basket:
            continue
        if args.ticker and query.ticker != args.ticker:
            continue
        if args.query_type and query.query_type != args.query_type:
            continue
        queries.append(query)
    if args.limit_queries:
        queries = queries[: args.limit_queries]
    return queries


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch external news sentiment and attention data.")
    parser.add_argument(
        "--provider",
        choices=["yahoo", "gdelt", "alpha_vantage", "all"],
        default="yahoo",
        help="News provider to fetch. Alpha Vantage supplies direct sentiment fields when ALPHAVANTAGE_API_KEY is set.",
    )
    parser.add_argument("--days", type=int, default=0, help="Lookback window. Defaults to config setting.")
    parser.add_argument("--basket", default="", help="Optional basket id to fetch.")
    parser.add_argument("--ticker", default="", help="Optional ticker to fetch.")
    parser.add_argument("--query-type", default="", help="Optional query type to fetch.")
    parser.add_argument("--max-records", type=int, default=0, help="Max article records per query.")
    parser.add_argument("--limit-queries", type=int, default=0, help="Safety limit for smoke tests.")
    parser.add_argument("--refresh", action="store_true", help="Replace cached sentiment rows instead of merging.")
    parser.add_argument("--skip-articles", action="store_true", help="Skip ArtList article fetches.")
    parser.add_argument("--skip-timelines", action="store_true", help="Skip TimelineVolRaw and TimelineTone fetches.")
    args = parser.parse_args()

    config = load_sentiment_config()
    days = args.days or config.default_days
    max_records = args.max_records or config.max_records_per_query
    run_date = now_stamp()
    queries = selected_queries(args)
    alpha_key = os.environ.get("ALPHAVANTAGE_API_KEY", "").strip()
    if args.provider == "alpha_vantage" and not alpha_key:
        print("ALPHAVANTAGE_API_KEY is not set; skipping Alpha Vantage sentiment fetch without modifying cached data.")
        return 0
    raw_rows: list[dict[str, Any]] = [] if args.refresh else read_csv(RAW_OUT)
    timeline_rows: list[dict[str, Any]] = [] if args.refresh else read_csv(TIMELINE_OUT)
    log_rows: list[dict[str, Any]] = [] if args.refresh else read_csv(FETCH_LOG_OUT)
    request_count = 0

    for spec in queries:
        if args.provider in {"alpha_vantage", "all"} and spec.ticker and not args.skip_articles:
            if not alpha_key:
                log_rows.append(log_row(run_date, spec, "ALPHA_VANTAGE_NEWS_SENTIMENT", "news_sentiment", "", "error", 0, "ALPHAVANTAGE_API_KEY is not set"))
                print(f"{spec.basket}/{spec.ticker} alpha_vantage news_sentiment: skipped (ALPHAVANTAGE_API_KEY is not set)")
            else:
                if request_count:
                    time.sleep(12.1)
                query = spec.ticker
                url = alpha_vantage_url(query, days, max_records, alpha_key)
                safe_url = url.replace(alpha_key, "REDACTED")
                try:
                    payload = fetch_json(url)
                    rows, message = parse_alpha_vantage_articles(payload, spec, query, run_date)
                    status = "ok" if not message else "error"
                    raw_rows.extend(rows)
                    log_rows.append(log_row(run_date, spec, "ALPHA_VANTAGE_NEWS_SENTIMENT", "news_sentiment", safe_url, status, len(rows), message))
                    print(f"{spec.basket}/{spec.ticker} alpha_vantage news_sentiment: {len(rows)} rows" + (f" ({message[:80]})" if message else ""))
                except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                    message = str(exc).replace("\n", " ")[:240]
                    log_rows.append(log_row(run_date, spec, "ALPHA_VANTAGE_NEWS_SENTIMENT", "news_sentiment", safe_url, "error", 0, message))
                    print(f"{spec.basket}/{spec.ticker} alpha_vantage news_sentiment: error: {message}")
                request_count += 1

        if args.provider in {"yahoo", "all"} and spec.ticker and not args.skip_articles:
            if request_count:
                time.sleep(0.35)
            query = yahoo_query(spec)
            url = yahoo_search_url(query, max_records)
            try:
                payload = fetch_json(url)
                rows = parse_yahoo_articles(payload, spec, query, run_date, days)
                raw_rows.extend(rows)
                log_rows.append(log_row(run_date, spec, "YAHOO_FINANCE", "news", url, "ok", len(rows)))
                print(f"{spec.basket}/{spec.ticker} yahoo news: {len(rows)} rows")
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                message = str(exc).replace("\n", " ")[:240]
                log_rows.append(log_row(run_date, spec, "YAHOO_FINANCE", "news", url, "error", 0, message))
                print(f"{spec.basket}/{spec.ticker} yahoo news: error: {message}")
            request_count += 1

        if args.provider in {"gdelt", "all"}:
            gdelt_query = build_gdelt_query(spec, config.language_filter, config.global_exclude)
            modes = []
            if not args.skip_articles:
                modes.append(("artlist", "articles"))
            if not args.skip_timelines:
                modes.extend([("timelinevolraw", "volume_raw"), ("timelinetone", "tone")])
            for mode, metric in modes:
                if request_count:
                    time.sleep(config.request_pause_seconds)
                url = endpoint_url(gdelt_query, mode, days, max_records)
                try:
                    payload = fetch_json(url)
                    if mode == "artlist":
                        rows = parse_articles(payload, spec, gdelt_query, run_date)
                        raw_rows.extend(rows)
                    else:
                        rows = parse_timeline(payload, spec, gdelt_query, run_date, metric)
                        timeline_rows.extend(rows)
                    log_rows.append(log_row(run_date, spec, "GDELT_DOC", mode, url, "ok", len(rows)))
                    print(f"{spec.basket}/{spec.ticker or 'basket'} {mode}: {len(rows)} rows")
                except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                    message = str(exc).replace("\n", " ")[:240]
                    log_rows.append(log_row(run_date, spec, "GDELT_DOC", mode, url, "error", 0, message))
                    print(f"{spec.basket}/{spec.ticker or 'basket'} {mode}: error: {message}")
                request_count += 1

    raw_rows = dedupe_rows(raw_rows, ("basket", "ticker", "published_at", "url", "title"))
    timeline_rows = dedupe_rows(timeline_rows, ("basket", "ticker", "query_type", "query", "date", "metric"))
    write_csv(RAW_OUT, RAW_FIELDS, raw_rows)
    write_csv(TIMELINE_OUT, TIMELINE_FIELDS, timeline_rows)
    write_csv(FETCH_LOG_OUT, LOG_FIELDS, log_rows)
    print(f"Wrote {len(raw_rows)} raw articles, {len(timeline_rows)} timeline rows, {len(log_rows)} fetch log rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
