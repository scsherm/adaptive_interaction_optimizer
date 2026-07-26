#!/usr/bin/env python3
"""Tools an agent can call to answer questions about the market baskets.

Provider-independent on purpose: these are plain Python functions plus JSON
schemas. `agent.py` binds them to a model; you can also drive them by hand:

    python agent_tools.py list_baskets
    python agent_tools.py compare_baskets '{"baskets": ["metals", "semiconductors"]}'
    python agent_tools.py run_sql '{"sql": "SELECT * FROM basket_metrics LIMIT 3"}'

Every tool returns JSON-serializable data and reports failures as
`{"error": ...}` rather than raising, so a model can read the message and retry
instead of killing the loop.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

import datastore
from universe import load_universe


# Caps keep a single tool result from swamping the model's context.
MAX_ROWS = 100
MAX_RESULT_CHARS = 24_000

# Tables an agent will want most often, described so it can pick without a
# full schema dump. The catalog has ~34 tables; these are the entry points.
KEY_TABLES = {
    "baskets": "One row per basket: id, label, description, taxonomy path, keywords, holding_count.",
    "holdings": "Basket membership: basket, ticker, name, note. Join key for every ticker-level table.",
    "candidates": "Tickers eligible for a basket but not necessarily held (is_holding flag).",
    "basket_metrics": "Headline basket performance: total_return_pct, annualized_vol_pct, max_drawdown_pct, return_vol_ratio, best/worst constituent.",
    "basket_advanced_price": "Basket price detail: 5/10/20d returns, drawdown, rolling vol, beta/corr/capture vs SPY, QQQ, BTC-USD.",
    "basket_fundamentals": "Basket median/average fundamentals: revenue growth, margins, FCF margin, net cash.",
    "basket_positioning": "Basket options and short-volume medians: put/call ratios, IV, short volume ratio.",
    "basket_ownership_positioning": "Basket short interest and institutional ownership aggregates.",
    "basket_news_sentiment": "Basket sentiment: tone, attention, momentum, spike scores, sentiment_state, primary_signal, risk_signal.",
    "ticker_news_sentiment": "Per-ticker sentiment with the same score family plus top positive/negative headlines and URLs.",
    "advanced_price_metrics": "Per-ticker price detail (same shape as basket_advanced_price).",
    "fundamentals_metrics": "Per-ticker SEC fundamentals.",
    "short_interest_metrics": "Per-ticker short interest: short_pct_float, days_to_cover, short_interest_change_pct.",
    "institutional_ownership_metrics": "Per-ticker institutional ownership levels and changes.",
    "options_positioning_metrics": "Per-ticker options: put/call open interest and volume ratios, IV.",
    "basket_daily": "Daily basket index level time series (basket, date, value).",
    "constituent_metrics": "Per-ticker return/vol/drawdown over the window. Keyed by ticker; its basket_memberships column is a display string, so join to `holdings` to filter by basket.",
}

COMPARE_SOURCES = {
    "performance": "basket_metrics",
    "price": "basket_advanced_price",
    "fundamentals": "basket_fundamentals",
    "positioning": "basket_positioning",
    "sentiment": "basket_news_sentiment",
}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[..., Any]


def _jsonable(value: Any) -> Any:
    """Normalize DuckDB values into JSON-native types.

    Dates, decimals and the like would otherwise depend on a `default=str`
    fallback at the serialization boundary; converting here means the model
    always sees an ISO string rather than whatever repr happened to produce.
    """
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _clip(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep a result under the context cap, telling the model if rows were cut."""
    payload = _jsonable(payload)
    encoded = json.dumps(payload, default=str)
    if len(encoded) <= MAX_RESULT_CHARS:
        return payload
    rows = payload.get("rows")
    if isinstance(rows, list) and rows:
        keep = max(1, len(rows) // 2)
        while keep > 1:
            trial = {**payload, "rows": rows[:keep], "truncated": True,
                     "truncatedNote": f"Showing {keep} of {len(rows)} rows; narrow the query for more."}
            if len(json.dumps(trial, default=str)) <= MAX_RESULT_CHARS:
                return trial
            keep //= 2
    return {
        "error": "Result too large to return. Select fewer columns or add a WHERE/LIMIT clause.",
        "approxChars": len(encoded),
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def list_baskets() -> dict[str, Any]:
    """Orientation: what baskets exist, what they mean, how they performed."""
    try:
        universe = load_universe()
        perf = {
            row["basket"]: row
            for row in datastore.query(
                "SELECT basket, total_return_pct, annualized_vol_pct, max_drawdown_pct, rank "
                "FROM basket_metrics"
            )
        }
        rows = []
        for basket in universe.baskets:
            metrics = perf.get(basket.id, {})
            rows.append(
                {
                    "id": basket.id,
                    "label": basket.label,
                    "description": basket.description,
                    "taxonomyPath": " / ".join(basket.path),
                    "holdings": len(basket.holdings),
                    "rank": metrics.get("rank"),
                    "totalReturnPct": metrics.get("total_return_pct"),
                    "annualizedVolPct": metrics.get("annualized_vol_pct"),
                    "maxDrawdownPct": metrics.get("max_drawdown_pct"),
                }
            )
        return _clip(
            {
                "window": {
                    "start": universe.start_date.isoformat(),
                    "end": universe.end_date.isoformat(),
                    "weighting": universe.weighting,
                },
                "rows": rows,
            }
        )
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def describe_tables(tables: list[str] | None = None) -> dict[str, Any]:
    """Schema discovery. No argument gives the table list; names give full columns."""
    try:
        entries = {entry["table"]: entry for entry in datastore.catalog()}
        if not tables:
            return _clip(
                {
                    "note": "Call describe_tables with names for full column lists.",
                    "rows": [
                        {
                            "table": name,
                            "rows": entries[name].get("rows"),
                            "about": KEY_TABLES.get(name, ""),
                        }
                        for name in sorted(entries)
                    ],
                }
            )
        unknown = [name for name in tables if name not in entries]
        described = [
            {
                "table": name,
                "rows": entries[name].get("rows"),
                "about": KEY_TABLES.get(name, ""),
                "columns": entries[name].get("columns", []),
            }
            for name in tables
            if name in entries
        ]
        result: dict[str, Any] = {"rows": described}
        if unknown:
            result["unknownTables"] = unknown
            result["availableTables"] = sorted(entries)
        return _clip(result)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def run_sql(sql: str, limit: int = MAX_ROWS) -> dict[str, Any]:
    """Read-only DuckDB query over every pipeline table plus the universe."""
    try:
        limit = max(1, min(int(limit), MAX_ROWS))
        rows = datastore.query(sql, limit=limit)
        return _clip({"sql": sql, "rowCount": len(rows), "rows": rows})
    except datastore.DatastoreError as exc:
        return {"error": str(exc), "hint": "Only read statements are permitted."}
    except Exception as exc:
        return {
            "error": f"{type(exc).__name__}: {exc}",
            "hint": "Call describe_tables to check table and column names.",
        }


def compare_baskets(
    baskets: list[str] | None = None,
    dimension: str = "performance",
    metrics: list[str] | None = None,
) -> dict[str, Any]:
    """Side-by-side basket comparison on one dimension, without writing SQL."""
    try:
        table = COMPARE_SOURCES.get(dimension)
        if table is None:
            return {
                "error": f"Unknown dimension {dimension!r}",
                "availableDimensions": sorted(COMPARE_SOURCES),
            }
        known = set(load_universe().basket_ids)
        selected = [b for b in (baskets or sorted(known)) if b in known]
        unknown = [b for b in (baskets or []) if b not in known]
        if not selected:
            return {"error": "No known baskets selected", "availableBaskets": sorted(known)}

        entry = next((e for e in datastore.catalog() if e["table"] == table), None)
        columns = [c["name"] for c in (entry or {}).get("columns", [])]
        if metrics:
            missing = [m for m in metrics if m not in columns]
            chosen = [m for m in metrics if m in columns]
            if not chosen:
                return {"error": f"None of those metrics exist on {table}", "availableMetrics": columns}
        else:
            missing, chosen = [], [c for c in columns if c != "basket"][:10]

        select = ", ".join(f'"{c}"' for c in ["basket", *chosen])
        placeholders = ", ".join("?" for _ in selected)
        rows = datastore.query(
            f"SELECT {select} FROM \"{table}\" WHERE basket IN ({placeholders})",
            selected,
            limit=MAX_ROWS,
        )
        result: dict[str, Any] = {"dimension": dimension, "source": table, "rows": rows}
        if unknown:
            result["unknownBaskets"] = unknown
            result["availableBaskets"] = sorted(known)
        if missing:
            result["unknownMetrics"] = missing
            result["availableMetrics"] = columns
        return _clip(result)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def basket_detail(basket: str) -> dict[str, Any]:
    """Everything about one basket: definition, holdings, metrics, sentiment."""
    try:
        universe = load_universe()
        found = universe.get(basket)
        if found is None:
            return {"error": f"Unknown basket {basket!r}", "availableBaskets": sorted(universe.basket_ids)}
        # constituent_metrics is keyed by ticker alone (its `basket_memberships`
        # column is a joined string, not a key), so the basket filter comes from
        # `holdings`.
        holdings = datastore.query(
            """
            SELECT h.ticker, h.name, h.note,
                   c.total_return_pct, c.max_drawdown_pct, c.annualized_vol_pct,
                   si.short_pct_float, si.short_interest_change_pct,
                   s.news_tone_score, s.sentiment_state
            FROM holdings h
            LEFT JOIN constituent_metrics c ON c.ticker = h.ticker
            LEFT JOIN short_interest_metrics si ON si.ticker = h.ticker
            LEFT JOIN ticker_news_sentiment s ON s.ticker = h.ticker AND s.basket = h.basket
            WHERE h.basket = ?
            ORDER BY h.ticker
            """,
            [basket],
            limit=MAX_ROWS,
        )
        metrics = datastore.query("SELECT * FROM basket_metrics WHERE basket = ?", [basket], limit=1)
        sentiment = datastore.query(
            "SELECT basket_sentiment_state, basket_news_tone_score, basket_attention_score, "
            "primary_signal, risk_signal FROM basket_news_sentiment WHERE basket = ?",
            [basket],
            limit=1,
        )
        return _clip(
            {
                "id": found.id,
                "label": found.label,
                "description": found.description,
                "taxonomyPath": " / ".join(found.path),
                "keywords": list(found.keywords),
                "metrics": metrics[0] if metrics else {},
                "sentiment": sentiment[0] if sentiment else {},
                "rows": holdings,
            }
        )
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="list_baskets",
        description=(
            "List every basket with its description, taxonomy path, holding count, and headline "
            "performance. Call this first when you need to know what exists."
        ),
        parameters={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        fn=list_baskets,
    ),
    ToolSpec(
        name="describe_tables",
        description=(
            "Inspect the queryable schema. Call with no arguments for the table list, or with table "
            "names for their exact columns. Use this before run_sql to get column names right."
        ),
        parameters={
            "type": "object",
            "properties": {
                "tables": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Table names to describe in full. Omit for the overview.",
                }
            },
            "required": [],
            "additionalProperties": False,
        },
        fn=describe_tables,
    ),
    ToolSpec(
        name="run_sql",
        description=(
            "Run a read-only DuckDB SELECT over the pipeline data. Join ticker-level tables to "
            "`holdings` on ticker to filter by basket. Only read statements are allowed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "A single SELECT (or WITH) statement."},
                "limit": {
                    "type": "integer",
                    "description": f"Max rows to return (1-{MAX_ROWS}).",
                },
            },
            "required": ["sql"],
            "additionalProperties": False,
        },
        fn=run_sql,
    ),
    ToolSpec(
        name="compare_baskets",
        description=(
            "Compare baskets side by side on one dimension: performance, price, fundamentals, "
            "positioning, or sentiment. Omit `baskets` to compare all of them."
        ),
        parameters={
            "type": "object",
            "properties": {
                "baskets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Basket ids. Omit for all baskets.",
                },
                "dimension": {
                    "type": "string",
                    "enum": sorted(COMPARE_SOURCES),
                    "description": "Which family of metrics to compare.",
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific columns. Omit for a sensible default set.",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        fn=compare_baskets,
    ),
    ToolSpec(
        name="basket_detail",
        description=(
            "Full detail for one basket: definition, keywords, headline metrics, sentiment state, "
            "and every holding with its return, short interest, and sentiment."
        ),
        parameters={
            "type": "object",
            "properties": {"basket": {"type": "string", "description": "Basket id, e.g. 'metals'."}},
            "required": ["basket"],
            "additionalProperties": False,
        },
        fn=basket_detail,
    ),
)

TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}


def openai_tool_definitions() -> list[dict[str, Any]]:
    """Tool schemas in the shape the OpenAI Responses API expects."""
    return [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
        for tool in TOOLS
    ]


def dispatch(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a tool by name. Never raises -- unknown names and bad arguments
    come back as errors the model can read and correct."""
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        return {"error": f"Unknown tool {name!r}", "availableTools": sorted(TOOLS_BY_NAME)}
    arguments = arguments or {}
    if not isinstance(arguments, dict):
        return {"error": "Arguments must be an object"}
    allowed = set(tool.parameters.get("properties", {}))
    unexpected = [key for key in arguments if key not in allowed]
    if unexpected:
        return {"error": f"Unexpected argument(s): {unexpected}", "expected": sorted(allowed)}
    try:
        return tool.fn(**arguments)
    except TypeError as exc:
        return {"error": f"Bad arguments for {name}: {exc}", "expected": sorted(allowed)}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: agent_tools.py <tool> ['{json arguments}']", file=sys.stderr)
        print(f"tools: {', '.join(sorted(TOOLS_BY_NAME))}", file=sys.stderr)
        return 2
    arguments = json.loads(argv[2]) if len(argv) > 2 else {}
    print(json.dumps(dispatch(argv[1], arguments), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
