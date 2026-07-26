#!/usr/bin/env python3
"""Taxonomy view over the canonical universe.

Kept as a module so the intake and workbench call sites keep their shape, but
there is no separate taxonomy file any more -- path, description, keywords, and
the candidate set are basket fields in `config/universe.yaml`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from universe import (
    UNIVERSE_PATH,
    add_candidate_row,
    load_universe,
    load_universe_data,
    save_universe_data,
)


TAXONOMY_CONFIG_PATH = UNIVERSE_PATH

DEFAULT_CLASSIFICATION = {
    "default_model": "gpt-5.4-nano",
    "env_model_var": "OPENAI_TICKER_MODEL",
    "provider": "openai_responses",
}


def load_taxonomy_config(path: Path = UNIVERSE_PATH) -> dict[str, Any]:
    """Legacy-shaped taxonomy config (`classification` + `baskets`) read from the universe."""
    data = load_universe_data(path)
    classification = data.get("classification")
    if not isinstance(classification, dict):
        classification = dict(DEFAULT_CLASSIFICATION)
    return {
        "version": data.get("version", 1),
        "description": data.get("description", ""),
        "classification": classification,
        "baskets": {
            row["id"]: {
                "path": list(row.get("path", []) or []),
                "description": row.get("description", ""),
                "keywords": list(row.get("keywords", []) or []),
                "candidates": list(row.get("candidates", []) or []),
            }
            for row in data.get("baskets", [])
            if isinstance(row, dict) and row.get("id")
        },
    }


def save_taxonomy_config(data: dict[str, Any], path: Path = UNIVERSE_PATH) -> None:
    """Write back only the taxonomy-owned fields, leaving holdings untouched."""
    universe_data = load_universe_data(path)
    baskets = data.get("baskets", {}) or {}
    by_id = {row.get("id"): row for row in universe_data.get("baskets", [])}
    for basket_id, row in baskets.items():
        target = by_id.get(basket_id)
        if target is None or not isinstance(row, dict):
            continue
        for key in ("path", "description", "keywords", "candidates"):
            if key in row:
                target[key] = row[key]
    if isinstance(data.get("classification"), dict):
        universe_data["classification"] = data["classification"]
    save_universe_data(universe_data, path)


def load_effective_taxonomy(
    base_taxonomy: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Basket taxonomy keyed by id. Candidates come back as (ticker, name, note) tuples.

    `base_taxonomy` is accepted and ignored -- the universe is now the base.
    """
    universe = load_universe()
    return {
        basket.id: {
            "path": list(basket.path),
            "description": basket.description,
            "keywords": list(basket.keywords),
            "candidates": [candidate.as_tuple() for candidate in basket.candidates],
        }
        for basket in universe.baskets
    }


def taxonomy_options(
    base_taxonomy: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    universe = load_universe()
    return [
        {
            "id": basket.id,
            "path": list(basket.path),
            "description": basket.description,
            "keywords": list(basket.keywords),
        }
        for basket in universe.baskets
    ]


def add_taxonomy_candidate(
    basket_id: str,
    ticker: str,
    name: str,
    note: str,
    path: list[str] | None = None,
) -> None:
    data = load_universe_data()
    row = next((item for item in data.get("baskets", []) if item.get("id") == basket_id), None)
    if row is None:
        raise KeyError(f"Unknown basket: {basket_id}")
    if path and not row.get("path"):
        row["path"] = list(path)
    add_candidate_row(data, basket_id, ticker, name, note)
    save_universe_data(data)
