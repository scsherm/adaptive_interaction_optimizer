#!/usr/bin/env python3
"""Tests for the agent tool layer.

No API calls: this covers the tools themselves and the contract the model sees.
The tools must never raise -- a model has to be able to read an error and retry.

Run directly, or via `npm run check`.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import agent_tools as AT  # noqa: E402
from universe import load_universe  # noqa: E402


def test_tool_schemas_are_well_formed():
    for tool in AT.TOOLS:
        assert tool.name and tool.description, f"{tool.name}: missing name/description"
        params = tool.parameters
        assert params.get("type") == "object", f"{tool.name}: parameters must be an object schema"
        assert params.get("additionalProperties") is False, f"{tool.name}: must forbid extra properties"
        for required in params.get("required", []):
            assert required in params.get("properties", {}), (
                f"{tool.name}: required field {required!r} is not declared in properties"
            )


def test_openai_definitions_match_registry():
    definitions = AT.openai_tool_definitions()
    assert len(definitions) == len(AT.TOOLS)
    for definition in definitions:
        assert definition["type"] == "function"
        assert definition["name"] in AT.TOOLS_BY_NAME
        # Must survive a JSON round trip -- it goes over the wire.
        json.dumps(definition)


def test_dispatch_rejects_unknown_tool():
    result = AT.dispatch("frobnicate", {})
    assert "error" in result and "availableTools" in result


def test_dispatch_rejects_unexpected_arguments():
    result = AT.dispatch("list_baskets", {"nope": 1})
    assert "error" in result, "unexpected arguments should be reported"
    assert "expected" in result


def test_dispatch_handles_non_dict_arguments():
    assert "error" in AT.dispatch("list_baskets", ["not", "a", "dict"])


def test_list_baskets_covers_the_universe():
    result = AT.dispatch("list_baskets", {})
    assert "error" not in result, result
    ids = {row["id"] for row in result["rows"]}
    assert ids == set(load_universe().basket_ids)
    assert result["window"]["start"] and result["window"]["end"]


def test_describe_tables_overview_and_detail():
    overview = AT.dispatch("describe_tables", {})
    assert "error" not in overview, overview
    names = {row["table"] for row in overview["rows"]}
    for expected in ("holdings", "basket_metrics", "ticker_news_sentiment"):
        assert expected in names, f"{expected} missing from the catalog"

    detail = AT.dispatch("describe_tables", {"tables": ["basket_metrics"]})
    columns = {c["name"] for c in detail["rows"][0]["columns"]}
    assert "total_return_pct" in columns


def test_describe_tables_reports_unknown_names():
    result = AT.dispatch("describe_tables", {"tables": ["not_a_table"]})
    assert result.get("unknownTables") == ["not_a_table"]
    assert result.get("availableTables"), "should suggest what is available"


def test_run_sql_reads_and_refuses_writes():
    ok = AT.dispatch("run_sql", {"sql": "SELECT basket, ticker FROM holdings", "limit": 5})
    assert "error" not in ok, ok
    assert len(ok["rows"]) == 5 and ok["rowCount"] == 5

    for statement in ("DROP TABLE holdings", "DELETE FROM holdings", "UPDATE holdings SET ticker='X'"):
        blocked = AT.dispatch("run_sql", {"sql": statement})
        assert "error" in blocked, f"{statement!r} was not refused"


def test_run_sql_errors_are_actionable():
    result = AT.dispatch("run_sql", {"sql": "SELECT * FROM does_not_exist"})
    assert "error" in result and "hint" in result, "a bad query should tell the model what to do next"


def test_run_sql_limit_is_capped():
    result = AT.dispatch("run_sql", {"sql": "SELECT * FROM raw_prices", "limit": 100_000})
    assert "error" not in result, result
    assert len(result["rows"]) <= AT.MAX_ROWS


def test_compare_baskets_dimensions():
    for dimension in AT.COMPARE_SOURCES:
        result = AT.dispatch("compare_baskets", {"baskets": ["metals"], "dimension": dimension})
        assert "error" not in result, f"{dimension}: {result}"
        assert result["rows"], f"{dimension} returned no rows"


def test_compare_baskets_reports_unknown_inputs():
    unknown_dimension = AT.dispatch("compare_baskets", {"dimension": "vibes"})
    assert "error" in unknown_dimension and "availableDimensions" in unknown_dimension

    unknown_basket = AT.dispatch("compare_baskets", {"baskets": ["metals", "nonsense"]})
    assert unknown_basket.get("unknownBaskets") == ["nonsense"]

    unknown_metric = AT.dispatch(
        "compare_baskets", {"baskets": ["metals"], "metrics": ["not_a_column"]}
    )
    assert "error" in unknown_metric and "availableMetrics" in unknown_metric


def test_basket_detail_matches_the_universe():
    universe = load_universe()
    basket = universe.baskets[0]
    result = AT.dispatch("basket_detail", {"basket": basket.id})
    assert "error" not in result, result
    assert result["label"] == basket.label
    assert {row["ticker"] for row in result["rows"]} == basket.holding_tickers

    missing = AT.dispatch("basket_detail", {"basket": "no_such_basket"})
    assert "error" in missing and "availableBaskets" in missing


def test_results_are_json_serializable():
    """Tool output crosses a JSON boundary to the model; dates must not break it."""
    for name, arguments in [
        ("list_baskets", {}),
        ("describe_tables", {}),
        ("basket_detail", {"basket": load_universe().baskets[0].id}),
        ("run_sql", {"sql": "SELECT * FROM basket_metrics", "limit": 3}),
        ("compare_baskets", {"dimension": "sentiment"}),
    ]:
        result = AT.dispatch(name, arguments)
        json.dumps(result, default=str)
        # `default=str` is the safety net; the payload should not need it.
        json.dumps(result)


def test_large_results_are_clipped_not_dropped():
    result = AT.dispatch("run_sql", {"sql": "SELECT * FROM raw_prices", "limit": AT.MAX_ROWS})
    encoded = json.dumps(result, default=str)
    assert len(encoded) <= AT.MAX_RESULT_CHARS + 2000, "result exceeded the context cap"

    clipped = AT._clip({"rows": [{"pad": "x" * 500} for _ in range(500)]})
    assert clipped.get("truncated") or "error" in clipped, "oversized payload was not handled"


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    failures = []
    for test in tests:
        try:
            test()
        except Exception as exc:
            failures.append((test.__name__, traceback.format_exc()))
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"ok   {test.__name__}")
    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    if failures:
        print("\n" + "=" * 60)
        for name, tb in failures:
            print(f"\n{name}\n{tb}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
