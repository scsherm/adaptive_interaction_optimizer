#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from market_config import ROOT, load_market_config, load_minimal_yaml


CONFIG_PATH = ROOT / "config" / "sentiment_queries.yaml"


@dataclass(frozen=True)
class SentimentQuery:
    basket: str
    query_type: str
    term: str
    ticker: str = ""
    company_name: str = ""
    aliases: tuple[str, ...] = ()
    required: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class SentimentConfig:
    provider: str
    default_days: int
    max_records_per_query: int
    request_pause_seconds: float
    language_filter: str
    ambiguous_tickers: set[str]
    valid_query_types: set[str]
    global_exclude: tuple[str, ...]
    queries: tuple[SentimentQuery, ...]


def _as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_sentiment_config(path: Path = CONFIG_PATH) -> SentimentConfig:
    data = load_minimal_yaml(path)
    settings = data.get("settings", {})
    valid_query_types = set(_as_list(settings.get("valid_query_types")))
    queries: list[SentimentQuery] = []

    for basket in data.get("baskets", []):
        basket_id = str(basket["id"])
        for item in _as_list(basket.get("basket_queries")):
            query_type = str(item.get("type", "investor"))
            if valid_query_types and query_type not in valid_query_types:
                raise ValueError(f"{basket_id} has invalid query type {query_type!r}")
            queries.append(
                SentimentQuery(
                    basket=basket_id,
                    query_type=query_type,
                    term=str(item["term"]),
                    required=tuple(str(value) for value in _as_list(item.get("required"))),
                    exclude=tuple(str(value) for value in _as_list(item.get("exclude"))),
                )
            )
        for ticker_row in _as_list(basket.get("ticker_queries")):
            ticker = str(ticker_row["ticker"])
            company_name = str(ticker_row.get("company_name", ""))
            aliases = tuple(str(value) for value in _as_list(ticker_row.get("aliases")))
            for item in _as_list(ticker_row.get("queries")):
                query_type = str(item.get("type", "company_specific"))
                if valid_query_types and query_type not in valid_query_types:
                    raise ValueError(f"{basket_id}/{ticker} has invalid query type {query_type!r}")
                queries.append(
                    SentimentQuery(
                        basket=basket_id,
                        ticker=ticker,
                        company_name=company_name,
                        aliases=aliases,
                        query_type=query_type,
                        term=str(item["term"]),
                        required=tuple(str(value) for value in _as_list(item.get("required"))),
                        exclude=tuple(str(value) for value in _as_list(item.get("exclude"))),
                    )
                )

    return SentimentConfig(
        provider=str(settings.get("provider", "gdelt_doc")),
        default_days=int(settings.get("default_days", 90)),
        max_records_per_query=int(settings.get("max_records_per_query", 75)),
        request_pause_seconds=float(settings.get("request_pause_seconds", 6)),
        language_filter=str(settings.get("language_filter", "")),
        ambiguous_tickers={str(value) for value in _as_list(settings.get("ambiguous_tickers"))},
        valid_query_types=valid_query_types,
        global_exclude=tuple(str(value) for value in _as_list(settings.get("global_exclude"))),
        queries=tuple(queries),
    )


def validate_query_coverage(config: SentimentConfig | None = None) -> list[str]:
    sentiment = config or load_sentiment_config()
    market = load_market_config()
    errors: list[str] = []
    expected_baskets = {basket.id for basket in market.baskets}
    configured_baskets = {query.basket for query in sentiment.queries}
    missing_baskets = sorted(expected_baskets - configured_baskets)
    if missing_baskets:
        errors.append(f"Missing sentiment queries for baskets: {', '.join(missing_baskets)}")

    expected_pairs = {(holding.basket, holding.ticker) for holding in market.holdings}
    configured_pairs = {
        (query.basket, query.ticker)
        for query in sentiment.queries
        if query.ticker
    }
    missing_pairs = sorted(expected_pairs - configured_pairs)
    if missing_pairs:
        formatted = ", ".join(f"{basket}/{ticker}" for basket, ticker in missing_pairs)
        errors.append(f"Missing ticker sentiment queries for: {formatted}")

    ambiguous_terms = []
    for query in sentiment.queries:
        tokens = {token.strip("()\"'").upper() for token in query.term.split()}
        normalized_term = query.term.strip("()\"'").upper()
        company_tokens = {token.strip("()\"'").upper() for token in query.company_name.split()}
        alias_tokens = {
            token.strip("()\"'").upper()
            for alias in query.aliases
            for token in alias.split()
        }
        raw_matches = sorted(
            token
            for token in tokens & sentiment.ambiguous_tickers
            if normalized_term == token or (token not in company_tokens and token not in alias_tokens)
        )
        if raw_matches:
            ambiguous_terms.append(f"{query.basket}/{query.ticker or 'basket'} uses raw ambiguous token(s) {raw_matches}: {query.term}")
    if ambiguous_terms:
        errors.extend(ambiguous_terms)
    return errors
