#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from market_config import ROOT


TAXONOMY_CONFIG_PATH = ROOT / "config" / "taxonomy.yaml"


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_taxonomy_config(path: Path = TAXONOMY_CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text()) or {}
    return loaded if isinstance(loaded, dict) else {}


def save_taxonomy_config(data: dict[str, Any], path: Path = TAXONOMY_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=False))


def load_effective_taxonomy(base_taxonomy: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    effective = deepcopy(base_taxonomy)
    config = load_taxonomy_config()
    configured_baskets = config.get("baskets", {}) if isinstance(config.get("baskets"), dict) else {}
    for basket_id, row in configured_baskets.items():
        if not isinstance(row, dict):
            continue
        target = effective.setdefault(basket_id, {"description": "", "keywords": [], "candidates": []})
        if row.get("description"):
            target["description"] = str(row["description"])
        if row.get("path"):
            target["path"] = [str(part) for part in _as_list(row["path"])]
        if row.get("keywords"):
            seen = {str(item).lower() for item in target.get("keywords", [])}
            for keyword in _as_list(row["keywords"]):
                keyword_text = str(keyword)
                if keyword_text.lower() not in seen:
                    target.setdefault("keywords", []).append(keyword_text)
                    seen.add(keyword_text.lower())
        existing = {str(item[0]).upper() for item in target.get("candidates", []) if item}
        for candidate in _as_list(row.get("candidates")):
            if not isinstance(candidate, dict):
                continue
            ticker = str(candidate.get("ticker", "")).upper().strip()
            if not ticker or ticker in existing:
                continue
            target.setdefault("candidates", []).append(
                (
                    ticker,
                    str(candidate.get("name") or ticker),
                    str(candidate.get("note") or "LLM-classified candidate"),
                )
            )
            existing.add(ticker)
    return effective


def taxonomy_options(base_taxonomy: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    effective = load_effective_taxonomy(base_taxonomy)
    rows = []
    for basket_id, row in effective.items():
        rows.append(
            {
                "id": basket_id,
                "path": row.get("path", []),
                "description": row.get("description", ""),
                "keywords": row.get("keywords", []),
            }
        )
    return rows


def add_taxonomy_candidate(
    basket_id: str,
    ticker: str,
    name: str,
    note: str,
    path: list[str] | None = None,
) -> None:
    data = load_taxonomy_config()
    data.setdefault("version", 1)
    data.setdefault("description", "Layered basket taxonomy used for ticker intake and LLM classification.")
    baskets = data.setdefault("baskets", {})
    basket = baskets.setdefault(basket_id, {"path": path or [], "candidates": []})
    if path and not basket.get("path"):
        basket["path"] = path
    candidates = basket.setdefault("candidates", [])
    ticker = ticker.upper().strip()
    for candidate in candidates:
        if isinstance(candidate, dict) and str(candidate.get("ticker", "")).upper() == ticker:
            candidate["name"] = name
            candidate["note"] = note
            save_taxonomy_config(data)
            return
    candidates.append({"ticker": ticker, "name": name, "note": note})
    save_taxonomy_config(data)
