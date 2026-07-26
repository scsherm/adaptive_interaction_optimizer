#!/usr/bin/env python3
"""Tests for the canonical universe layer and the DuckDB datastore.

The headline test is `test_new_basket_needs_only_universe_yaml`: adding a basket
must require exactly one file edit. Basket definitions were previously spread
across five places, so that property is asserted rather than assumed.

Run directly, or via `npm run check`.
"""
from __future__ import annotations

import copy
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import universe as U  # noqa: E402
import category_workbench  # noqa: E402
import sentiment_config  # noqa: E402
import ticker_intake  # noqa: E402
from market_config import load_market_config  # noqa: E402
from taxonomy_config import load_effective_taxonomy  # noqa: E402


NEW_BASKET = {
    "id": "datacenter_cooling",
    "label": "Datacenter Cooling",
    "short": "Cooling",
    "color": "#5fd4c4",
    "accent": "oklch(80% 0.12 190)",
    "path": ["Industrials", "Thermal Management", "Datacenter Cooling"],
    "description": "Liquid cooling, thermal management, and heat rejection for AI datacenters.",
    "keywords": ["liquid cooling", "thermal management", "heat exchanger"],
    "intake": {"priority": 4, "confidence": 0.76, "keywords": ["liquid cooling", "thermal management"]},
    "holdings": [
        {"ticker": "VRT", "name": "Vertiv", "note": "datacenter thermal management"},
        {"ticker": "MOD", "name": "Modine Manufacturing", "note": "heat exchangers / datacenter cooling"},
    ],
    "candidates": [
        {"ticker": "VRT", "name": "Vertiv", "note": "datacenter thermal management"},
        {"ticker": "MOD", "name": "Modine Manufacturing", "note": "heat exchangers / datacenter cooling"},
        {"ticker": "SPXC", "name": "SPX Technologies", "note": "cooling systems"},
    ],
}


class Sandbox:
    """Swap in a scratch universe.yaml, then always restore the real one."""

    def __init__(self, mutate):
        self.mutate = mutate
        self.original = U.UNIVERSE_PATH.read_text()

    def __enter__(self):
        data = U.load_universe_data()
        self.mutate(data)
        U.save_universe_data(data)
        return data

    def __exit__(self, *exc):
        U.UNIVERSE_PATH.write_text(self.original)
        U.invalidate_cache()
        return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_universe_loads_and_validates():
    universe = U.load_universe()
    assert universe.baskets, "expected at least one basket"
    assert universe.holdings, "expected holdings"
    problems = U.validate(universe)
    assert problems == [], f"universe.yaml has problems: {problems}"


def test_every_holding_is_a_candidate():
    for basket in U.load_universe().baskets:
        candidates = basket.candidates_by_ticker
        for holding in basket.holdings:
            assert holding.ticker in candidates, f"{holding.ticker} missing from {basket.id} candidates"


def test_yaml_round_trip_is_lossless():
    data = U.load_universe_data()
    reparsed = U.parse_universe(
        __import__("yaml").safe_load(U.dump_universe_yaml(copy.deepcopy(data)))
    )
    original = U.parse_universe(data)
    assert reparsed == original, "dump/load round trip changed the universe"


def test_boolean_ticker_is_rejected_not_silently_eaten():
    """Bare ON/NO/YES are YAML 1.1 booleans; they must error, not become True."""
    data = U.load_universe_data()
    data["baskets"][0]["holdings"][0]["ticker"] = True
    try:
        U.parse_universe(data)
    except U.UniverseError as exc:
        assert "boolean" in str(exc).lower(), f"unhelpful message: {exc}"
        return
    raise AssertionError("a boolean ticker was accepted")


def test_on_semiconductor_survives_serialization():
    """ON is the canary: it round-trips through YAML only if it stays quoted."""
    semis = U.load_universe().get("semiconductors")
    assert semis is not None
    assert "ON" in semis.candidates_by_ticker, "ON Semiconductor was eaten by the YAML boolean rule"


def test_public_collections_are_lists():
    """Downstream modules concatenate and index these (e.g. `HOLDINGS + BENCHMARKS`
    in market_basket_analysis.py), so tuples break the pipeline at runtime even
    though every module still imports cleanly."""
    config = load_market_config()
    for name in ("baskets", "benchmarks", "holdings", "symbol_decisions"):
        value = getattr(config, name)
        assert isinstance(value, list), f"config.{name} is {type(value).__name__}, expected list"
    basket = config.baskets[0]
    for name in ("holdings", "candidates", "path", "keywords"):
        value = getattr(basket, name)
        assert isinstance(value, list), f"basket.{name} is {type(value).__name__}, expected list"
    assert len(config.holdings + config.benchmarks) == len(config.holdings) + len(config.benchmarks)


def test_intake_rules_are_priority_ordered():
    rules = U.load_universe().intake_rules
    priorities = [rule.priority for _, rule in rules]
    assert priorities == sorted(priorities), f"intake rules out of order: {priorities}"


def test_heuristic_matches_from_config():
    basket, confidence, reason = ticker_intake.strong_heuristic_basket(
        {"businessSummary": "trapped ion qubit quantum computing"}
    )
    assert basket == "quantum", f"expected quantum, got {basket}"
    assert confidence > 0 and "quantum" in reason


def test_sentiment_queries_cover_every_holding():
    config = sentiment_config.load_sentiment_config()
    universe = U.load_universe()
    covered = {(q.basket, q.ticker) for q in config.queries if q.ticker}
    expected = {(h.basket, h.ticker) for h in universe.holdings}
    missing = expected - covered
    assert not missing, f"holdings without a sentiment query: {sorted(missing)[:5]}"


def test_sentiment_query_validation_passes():
    problems = sentiment_config.validate_query_coverage()
    assert problems == [], f"sentiment query problems: {problems}"


def test_new_basket_needs_only_universe_yaml():
    """Adding a basket must require exactly one file edit and nothing else."""

    def add(data):
        data["baskets"].append(copy.deepcopy(NEW_BASKET))

    with Sandbox(add):
        config = load_market_config()
        assert "datacenter_cooling" in config.basket_labels, "new basket missing from market config"

        # No hardcoded taxonomy to update.
        taxonomy = load_effective_taxonomy()
        assert taxonomy["datacenter_cooling"]["description"], "taxonomy did not pick up the basket"

        # The server refuses to boot on taxonomy problems -- there must be none.
        assert category_workbench.validate_taxonomy() == [], "validation rejected the new basket"

        state = category_workbench.category_state()
        ids = [row["id"] for row in state["categories"]]
        assert "datacenter_cooling" in ids, "workstation state missing the new basket"

        # Candidate search works with no separate candidate registry.
        results = category_workbench.search_category("datacenter_cooling")
        assert len(results) == 3, f"expected 3 candidates, got {len(results)}"
        assert results[0]["alreadyInBasket"] is True

        # Sentiment queries generate instead of hard-failing on missing config.
        sentiment = sentiment_config.load_sentiment_config()
        generated = {q.ticker for q in sentiment.generated_queries if q.ticker}
        assert {"VRT", "MOD"} <= generated, f"expected generated ticker queries, got {generated}"
        assert sentiment_config.validate_query_coverage(sentiment) == []

        # Generated terms anchor on company names, never a bare ambiguous ticker.
        for query in sentiment.generated_queries:
            assert query.term.strip(), "generated an empty query term"

        # Intake heuristics pick it up from the same file.
        basket, _, _ = ticker_intake.strong_heuristic_basket(
            {"businessSummary": "liquid cooling systems for datacenters"}
        )
        assert basket == "datacenter_cooling", f"intake did not route to the new basket: {basket}"

    # Sandbox restored.
    assert "datacenter_cooling" not in load_market_config().basket_labels


def test_structurally_invalid_config_never_reaches_disk():
    original = U.UNIVERSE_PATH.read_text()
    data = U.load_universe_data()
    data["baskets"].append(copy.deepcopy(data["baskets"][0]))  # duplicate basket id
    try:
        U.save_universe_data(data)
    except U.UniverseError:
        pass
    else:
        U.UNIVERSE_PATH.write_text(original)
        U.invalidate_cache()
        raise AssertionError("invalid config was written")
    assert U.UNIVERSE_PATH.read_text() == original, "a failed save modified the file"


def test_empty_basket_saves_but_fails_the_pipeline_gate():
    """A new basket starts empty, so saving it must work; running on it must not."""

    def add_empty(data):
        data["baskets"].append(
            {
                "id": "scratch",
                "label": "Scratch",
                "short": "Scratch",
                "color": "#888888",
                "accent": "oklch(60% 0.02 250)",
                "description": "Placeholder basket with no holdings yet.",
                "holdings": [],
                "candidates": [],
            }
        )

    with Sandbox(add_empty):
        problems = U.validate()
        assert any("scratch" in problem for problem in problems), (
            f"an empty basket should be reported by validate(), got {problems}"
        )


def test_datastore_catalog_and_join():
    try:
        from datastore import DatastoreError, catalog, query
    except Exception as exc:  # pragma: no cover
        raise AssertionError(f"datastore import failed: {exc}") from exc

    tables = {entry["table"] for entry in catalog()}
    for required in ("baskets", "holdings", "candidates", "benchmarks"):
        assert required in tables, f"missing universe table: {required}"

    rows = query("SELECT basket, count(*) AS n FROM holdings GROUP BY basket ORDER BY basket")
    universe = U.load_universe()
    assert len(rows) == len(universe.baskets), "holdings table disagrees with the universe"

    # Writes are refused by default so an agent cannot mutate artifacts.
    try:
        query("DROP TABLE holdings")
    except DatastoreError:
        pass
    else:
        raise AssertionError("a write statement was allowed through query()")


def test_datastore_excludes_stale_rotation_tables():
    from datastore import catalog

    tables = {entry["table"] for entry in catalog()}
    assert "basket_rotation_scores" not in tables, "stale rotation artifact is still exposed"


# ---------------------------------------------------------------------------


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    failures = []
    for test in tests:
        try:
            test()
        except Exception as exc:
            failures.append((test.__name__, exc, traceback.format_exc()))
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"ok   {test.__name__}")
    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    if failures:
        print("\n" + "=" * 60)
        for name, _, tb in failures:
            print(f"\n{name}\n{tb}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
