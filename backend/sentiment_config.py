#!/usr/bin/env python3
"""News-search configuration, derived from the universe with optional overrides.

`config/sentiment_queries.yaml` is no longer a mandatory registry that must list
every basket and ticker. It carries global settings plus hand-tuned query
overrides; anything it does not mention is generated from the basket's label,
keywords, and holdings. Adding a ticker to the universe therefore no longer
breaks the sentiment stage.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from universe import ROOT, Basket, Holding, Universe, load_universe


CONFIG_PATH = ROOT / "config" / "sentiment_queries.yaml"

DEFAULT_SETTINGS: dict[str, Any] = {
    "provider": "gdelt_doc",
    "default_days": 90,
    "max_records_per_query": 75,
    "request_pause_seconds": 6.0,
    "language_filter": "sourcelang:eng",
    "valid_query_types": ["investor", "demand_tailwind", "risk", "company_specific"],
    "ambiguous_tickers": [],
    "global_exclude": [],
}


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
    origin: str = "configured"


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

    @property
    def generated_queries(self) -> tuple[SentimentQuery, ...]:
        return tuple(query for query in self.queries if query.origin == "generated")


def _as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def _tuple(value: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in _as_list(value))


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def generate_basket_queries(basket: Basket) -> list[dict[str, str]]:
    """Default basket-level news queries from the basket's own label and keywords."""
    label = basket.label
    keywords = [word for word in basket.keywords if word]
    rows = [{"type": "investor", "term": f"{label} stocks"}]
    if keywords:
        rows.append({"type": "demand_tailwind", "term": " ".join(keywords[:3])})
    rows.append({"type": "risk", "term": f"{label} demand slowdown"})
    return rows


def generate_ticker_queries(basket: Basket, holding: Holding) -> dict[str, Any]:
    """Default company-level query. Anchors on the company name so ambiguous
    tickers (S, NOW, ON, CAT...) never reach the news provider as a bare token."""
    name = holding.name.strip() or holding.ticker
    qualifier = holding.note.strip() or basket.label
    term = f"{name} {qualifier}".strip()
    return {
        "ticker": holding.ticker,
        "company_name": name,
        "aliases": [name],
        "queries": [{"type": "company_specific", "term": term}],
    }


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_overrides(path: Path = CONFIG_PATH) -> dict[str, Any]:
    if not Path(path).exists():
        return {}
    loaded = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Sentiment config must be a mapping: {path}")
    return loaded


def load_sentiment_config(
    path: Path = CONFIG_PATH,
    universe: Universe | None = None,
) -> SentimentConfig:
    data = load_overrides(path)
    settings = {**DEFAULT_SETTINGS, **(data.get("settings") or {})}
    valid_query_types = {str(item) for item in _as_list(settings.get("valid_query_types"))}
    universe = universe or load_universe()

    overrides_by_basket: dict[str, dict[str, Any]] = {}
    for row in _as_list(data.get("baskets")):
        if isinstance(row, dict) and row.get("id"):
            overrides_by_basket[str(row["id"])] = row

    def check_type(query_type: str, where: str) -> str:
        if valid_query_types and query_type not in valid_query_types:
            raise ValueError(f"{where} has invalid query type {query_type!r}")
        return query_type

    queries: list[SentimentQuery] = []
    for basket in universe.baskets:
        override = overrides_by_basket.get(basket.id, {})

        basket_rows = _as_list(override.get("basket_queries"))
        origin = "configured" if basket_rows else "generated"
        if not basket_rows:
            basket_rows = generate_basket_queries(basket)
        for item in basket_rows:
            query_type = check_type(str(item.get("type", "investor")), basket.id)
            queries.append(
                SentimentQuery(
                    basket=basket.id,
                    query_type=query_type,
                    term=str(item["term"]),
                    required=_tuple(item.get("required")),
                    exclude=_tuple(item.get("exclude")),
                    origin=origin,
                )
            )

        ticker_overrides = {
            str(row["ticker"]).upper(): row
            for row in _as_list(override.get("ticker_queries"))
            if isinstance(row, dict) and row.get("ticker")
        }
        for holding in basket.holdings:
            row = ticker_overrides.get(holding.ticker.upper())
            origin = "configured" if row else "generated"
            if row is None:
                row = generate_ticker_queries(basket, holding)
            company_name = str(row.get("company_name", "") or holding.name)
            aliases = _tuple(row.get("aliases")) or (company_name,)
            for item in _as_list(row.get("queries")):
                query_type = check_type(
                    str(item.get("type", "company_specific")), f"{basket.id}/{holding.ticker}"
                )
                queries.append(
                    SentimentQuery(
                        basket=basket.id,
                        ticker=holding.ticker,
                        company_name=company_name,
                        aliases=aliases,
                        query_type=query_type,
                        term=str(item["term"]),
                        required=_tuple(item.get("required")),
                        exclude=_tuple(item.get("exclude")),
                        origin=origin,
                    )
                )

    return SentimentConfig(
        provider=str(settings.get("provider")),
        default_days=int(settings.get("default_days")),
        max_records_per_query=int(settings.get("max_records_per_query")),
        request_pause_seconds=float(settings.get("request_pause_seconds")),
        language_filter=str(settings.get("language_filter", "")),
        ambiguous_tickers={str(value) for value in _as_list(settings.get("ambiguous_tickers"))},
        valid_query_types=valid_query_types,
        global_exclude=_tuple(settings.get("global_exclude")),
        queries=tuple(queries),
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_query_coverage(config: SentimentConfig | None = None) -> list[str]:
    """Query problems worth blocking a run.

    Coverage gaps are no longer possible -- every basket and holding gets a query
    either from the override file or by generation -- so this now only guards
    against ambiguous bare tickers leaking into news search terms.
    """
    sentiment = config or load_sentiment_config()
    errors: list[str] = []
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
            errors.append(
                f"{query.basket}/{query.ticker or 'basket'} uses raw ambiguous token(s) "
                f"{raw_matches}: {query.term}"
            )
    return errors


def coverage_report(config: SentimentConfig | None = None) -> dict[str, Any]:
    """Which queries are hand-tuned vs generated -- diagnostics, not a gate."""
    sentiment = config or load_sentiment_config()
    generated = sentiment.generated_queries
    return {
        "totalQueries": len(sentiment.queries),
        "configuredQueries": len(sentiment.queries) - len(generated),
        "generatedQueries": len(generated),
        "generatedBaskets": sorted({q.basket for q in generated if not q.ticker}),
        "generatedTickers": sorted({f"{q.basket}/{q.ticker}" for q in generated if q.ticker}),
    }


def main() -> int:
    import json

    config = load_sentiment_config()
    problems = validate_query_coverage(config)
    print(
        json.dumps(
            {
                "status": "FAIL" if problems else "PASS",
                **coverage_report(config),
                "problems": problems,
            },
            indent=2,
        )
    )
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
