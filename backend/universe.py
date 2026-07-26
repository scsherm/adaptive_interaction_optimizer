#!/usr/bin/env python3
"""Canonical semantic layer for baskets.

Everything the system knows about a basket -- its identity, presentation,
taxonomy placement, intake keywords, holdings, and candidate universe -- lives in
`config/universe.yaml` and is read through here. Other modules adapt this model
to their own shapes; none of them parse basket config themselves.
"""
from __future__ import annotations

import threading
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import yaml


ROOT = Path(__file__).resolve().parent
UNIVERSE_PATH = ROOT / "config" / "universe.yaml"

SCHEMA_VERSION = 1

METHODOLOGY_FIELDS = (
    "start_date",
    "end_date",
    "expected_constituents_per_basket",
    "source",
    "weighting",
    "price_field",
    "data_status",
)


class UniverseError(ValueError):
    """Raised when universe.yaml is structurally invalid."""


@dataclass(frozen=True)
class Holding:
    basket: str
    ticker: str
    name: str
    note: str


@dataclass(frozen=True)
class Candidate:
    basket: str
    ticker: str
    name: str
    note: str

    def as_tuple(self) -> tuple[str, str, str]:
        return (self.ticker, self.name, self.note)


@dataclass(frozen=True)
class IntakeRule:
    """Keyword rule used to guess a basket from scraped company context."""

    priority: int = 999
    confidence: float = 0.0
    keywords: tuple[str, ...] = ()

    def match(self, text: str) -> str:
        for keyword in self.keywords:
            if keyword and keyword in text:
                return keyword
        return ""


@dataclass(frozen=True)
class Basket:
    # Collections are lists, not tuples: downstream modules concatenate and index
    # them (e.g. `HOLDINGS + BENCHMARKS`), which is the contract MarketConfig had.
    id: str
    label: str
    short: str
    color: str
    accent: str
    path: list[str] = field(default_factory=list)
    description: str = ""
    keywords: list[str] = field(default_factory=list)
    intake: IntakeRule = field(default_factory=IntakeRule)
    holdings: list[Holding] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def holding_tickers(self) -> set[str]:
        return {holding.ticker.upper() for holding in self.holdings}

    @property
    def candidates_by_ticker(self) -> dict[str, Candidate]:
        return {candidate.ticker.upper(): candidate for candidate in self.candidates}


@dataclass(frozen=True)
class Methodology:
    start_date: date
    end_date: date
    expected_constituents_per_basket: int
    source: str
    weighting: str
    price_field: str
    data_status: str


@dataclass(frozen=True)
class Universe:
    version: int
    methodology: Methodology
    baskets: list[Basket]
    benchmarks: list[Holding]
    symbol_decisions: list[str]

    # Methodology proxies keep the historical MarketConfig attribute surface intact.
    @property
    def start_date(self) -> date:
        return self.methodology.start_date

    @property
    def end_date(self) -> date:
        return self.methodology.end_date

    @property
    def expected_constituents_per_basket(self) -> int:
        return self.methodology.expected_constituents_per_basket

    @property
    def source(self) -> str:
        return self.methodology.source

    @property
    def weighting(self) -> str:
        return self.methodology.weighting

    @property
    def price_field(self) -> str:
        return self.methodology.price_field

    @property
    def data_status(self) -> str:
        return self.methodology.data_status

    @property
    def holdings(self) -> list[Holding]:
        return [holding for basket in self.baskets for holding in basket.holdings]

    @property
    def basket_labels(self) -> dict[str, str]:
        return {basket.id: basket.label for basket in self.baskets}

    @property
    def basket_meta(self) -> dict[str, dict[str, str]]:
        return {
            basket.id: {
                "label": basket.label,
                "short": basket.short,
                "color": basket.color,
                "accent": basket.accent,
            }
            for basket in self.baskets
        }

    @property
    def basket_ids(self) -> list[str]:
        return [basket.id for basket in self.baskets]

    def basket(self, basket_id: str) -> Basket:
        for basket in self.baskets:
            if basket.id == basket_id:
                return basket
        raise KeyError(f"Unknown basket: {basket_id}")

    def get(self, basket_id: str) -> Basket | None:
        for basket in self.baskets:
            if basket.id == basket_id:
                return basket
        return None

    @property
    def intake_rules(self) -> list[tuple[str, IntakeRule]]:
        """Baskets carrying intake keywords, ordered by rule priority."""
        rules = [(basket.id, basket.intake) for basket in self.baskets if basket.intake.keywords]
        return sorted(rules, key=lambda item: (item[1].priority, item[0]))


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _text(value: Any, *, where: str, field_name: str, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, bool):
        # YAML 1.1 resolves bare ON/NO/YES/OFF to booleans, which silently eats
        # real tickers such as ON Semiconductor.
        raise UniverseError(
            f"{where}: {field_name} parsed as a YAML boolean. Quote the value (e.g. \"ON\")."
        )
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _str_list(value: Any, *, where: str, field_name: str) -> list[str]:
    if value is None or value == "":
        return []
    if not isinstance(value, list):
        value = [value]
    return [_text(item, where=where, field_name=field_name) for item in value if item is not None]


def _date(value: Any, *, where: str, field_name: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(_text(value, where=where, field_name=field_name))
    except ValueError as exc:
        raise UniverseError(f"{where}: {field_name} is not an ISO date: {value!r}") from exc


def _instrument_rows(rows: Any, basket_id: str, kind: str, cls) -> list:
    if not rows:
        return []
    if not isinstance(rows, list):
        raise UniverseError(f"basket {basket_id}: {kind} must be a list")
    out = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        where = f"basket {basket_id} {kind}[{index}]"
        if not isinstance(row, dict):
            raise UniverseError(f"{where}: expected a mapping, got {type(row).__name__}")
        ticker = _text(row.get("ticker"), where=where, field_name="ticker").upper()
        if not ticker:
            raise UniverseError(f"{where}: missing ticker")
        if ticker in seen:
            raise UniverseError(f"{where}: duplicate ticker {ticker}")
        seen.add(ticker)
        out.append(
            cls(
                basket=basket_id,
                ticker=ticker,
                name=_text(row.get("name"), where=where, field_name="name") or ticker,
                note=_text(row.get("note"), where=where, field_name="note"),
            )
        )
    return out


def _parse_intake(row: Any, basket_id: str) -> IntakeRule:
    if not row:
        return IntakeRule()
    if not isinstance(row, dict):
        raise UniverseError(f"basket {basket_id}: intake must be a mapping")
    where = f"basket {basket_id} intake"
    return IntakeRule(
        priority=int(row.get("priority", 999)),
        confidence=float(row.get("confidence", 0.0)),
        keywords=tuple(
            keyword.lower()
            for keyword in _str_list(row.get("keywords"), where=where, field_name="keywords")
        ),
    )


def parse_universe(data: dict[str, Any]) -> Universe:
    if not isinstance(data, dict):
        raise UniverseError("universe config must be a mapping")

    raw_methodology = data.get("methodology")
    if not isinstance(raw_methodology, dict):
        raise UniverseError("universe config is missing a `methodology` mapping")
    missing = [key for key in METHODOLOGY_FIELDS if key not in raw_methodology]
    if missing:
        raise UniverseError(f"methodology is missing: {', '.join(missing)}")

    methodology = Methodology(
        start_date=_date(raw_methodology["start_date"], where="methodology", field_name="start_date"),
        end_date=_date(raw_methodology["end_date"], where="methodology", field_name="end_date"),
        expected_constituents_per_basket=int(raw_methodology["expected_constituents_per_basket"]),
        source=_text(raw_methodology["source"], where="methodology", field_name="source"),
        weighting=_text(raw_methodology["weighting"], where="methodology", field_name="weighting"),
        price_field=_text(raw_methodology["price_field"], where="methodology", field_name="price_field"),
        data_status=_text(raw_methodology["data_status"], where="methodology", field_name="data_status"),
    )

    raw_baskets = data.get("baskets")
    if not isinstance(raw_baskets, list) or not raw_baskets:
        raise UniverseError("universe config needs a non-empty `baskets` list")

    baskets: list[Basket] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(raw_baskets):
        if not isinstance(row, dict):
            raise UniverseError(f"baskets[{index}]: expected a mapping")
        basket_id = _text(row.get("id"), where=f"baskets[{index}]", field_name="id")
        if not basket_id:
            raise UniverseError(f"baskets[{index}]: missing id")
        if basket_id in seen_ids:
            raise UniverseError(f"duplicate basket id: {basket_id}")
        seen_ids.add(basket_id)
        where = f"basket {basket_id}"
        label = _text(row.get("label"), where=where, field_name="label") or basket_id
        baskets.append(
            Basket(
                id=basket_id,
                label=label,
                short=_text(row.get("short"), where=where, field_name="short") or label,
                color=_text(row.get("color"), where=where, field_name="color"),
                accent=_text(row.get("accent"), where=where, field_name="accent"),
                path=_str_list(row.get("path"), where=where, field_name="path"),
                description=_text(row.get("description"), where=where, field_name="description"),
                keywords=_str_list(row.get("keywords"), where=where, field_name="keywords"),
                intake=_parse_intake(row.get("intake"), basket_id),
                holdings=_instrument_rows(row.get("holdings"), basket_id, "holdings", Holding),
                candidates=_instrument_rows(row.get("candidates"), basket_id, "candidates", Candidate),
            )
        )

    benchmarks = _instrument_rows(data.get("benchmarks"), "benchmark", "benchmarks", Holding)
    return Universe(
        version=int(data.get("version", SCHEMA_VERSION)),
        methodology=methodology,
        baskets=baskets,
        benchmarks=benchmarks,
        symbol_decisions=_str_list(
            data.get("symbol_decisions"), where="root", field_name="symbol_decisions"
        ),
    )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class _BlockDumper(yaml.SafeDumper):
    """SafeDumper that keeps nested lists indented under their key."""

    def increase_indent(self, flow: bool = False, indentless: bool = False):
        return super().increase_indent(flow, False)


def dump_universe_yaml(data: dict[str, Any]) -> str:
    return yaml.dump(
        data,
        Dumper=_BlockDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=100,
    )


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

_CACHE_LOCK = threading.Lock()
_CACHE: dict[Path, tuple[tuple[int, int], dict[str, Any]]] = {}


def _cache_key(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size)


def load_universe_data(path: Path = UNIVERSE_PATH) -> dict[str, Any]:
    """Raw round-trippable config. Returns a deep copy -- safe to mutate."""
    path = Path(path)
    if not path.exists():
        raise UniverseError(f"Universe config not found: {path}")
    key = _cache_key(path)
    with _CACHE_LOCK:
        cached = _CACHE.get(path)
        if cached and cached[0] == key:
            return deepcopy(cached[1])
    loaded = yaml.safe_load(path.read_text()) or {}
    if not isinstance(loaded, dict):
        raise UniverseError(f"Universe config must be a mapping: {path}")
    with _CACHE_LOCK:
        _CACHE[path] = (key, loaded)
    return deepcopy(loaded)


def save_universe_data(data: dict[str, Any], path: Path = UNIVERSE_PATH) -> None:
    """Validate, then write. Invalid config never reaches disk."""
    parse_universe(data)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_universe_yaml(data))
    with _CACHE_LOCK:
        _CACHE.pop(path, None)


def load_universe(path: Path = UNIVERSE_PATH) -> Universe:
    return parse_universe(load_universe_data(path))


def invalidate_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


# ---------------------------------------------------------------------------
# Mutation primitives
#
# These operate on the raw dict so that comments-free round-tripping stays
# lossless, and they always validate before returning.
# ---------------------------------------------------------------------------


def find_basket_row(data: dict[str, Any], basket_id: str) -> dict[str, Any]:
    for row in data.get("baskets", []):
        if row.get("id") == basket_id:
            return row
    raise KeyError(f"Unknown basket: {basket_id}")


def basket_row_template(
    basket_id: str,
    label: str,
    *,
    short: str = "",
    color: str = "#8aa0c0",
    accent: str = "oklch(70% 0.10 250)",
    path: Iterable[str] = (),
    description: str = "",
    keywords: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "id": basket_id,
        "label": label,
        "short": short or label,
        "color": color,
        "accent": accent,
        "path": list(path),
        "description": description,
        "keywords": list(keywords),
        "holdings": [],
        "candidates": [],
    }


def upsert_basket(data: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    baskets = data.setdefault("baskets", [])
    for index, existing in enumerate(baskets):
        if existing.get("id") == row["id"]:
            baskets[index] = {**existing, **row}
            return data
    baskets.append(row)
    return data


def add_holding_row(
    data: dict[str, Any], basket_id: str, ticker: str, name: str, note: str
) -> dict[str, Any]:
    basket = find_basket_row(data, basket_id)
    holdings = basket.setdefault("holdings", [])
    ticker = ticker.upper().strip()
    for holding in holdings:
        if str(holding.get("ticker", "")).upper() == ticker:
            return data
    holdings.append({"ticker": ticker, "name": name, "note": note})
    return data


def remove_holding_row(data: dict[str, Any], basket_id: str, ticker: str) -> dict[str, Any]:
    basket = find_basket_row(data, basket_id)
    ticker = ticker.upper().strip()
    basket["holdings"] = [
        row for row in basket.get("holdings", []) if str(row.get("ticker", "")).upper() != ticker
    ]
    return data


def add_candidate_row(
    data: dict[str, Any], basket_id: str, ticker: str, name: str, note: str
) -> dict[str, Any]:
    basket = find_basket_row(data, basket_id)
    candidates = basket.setdefault("candidates", [])
    ticker = ticker.upper().strip()
    for candidate in candidates:
        if str(candidate.get("ticker", "")).upper() == ticker:
            candidate["name"] = name
            candidate["note"] = note
            return data
    candidates.append({"ticker": ticker, "name": name, "note": note})
    return data


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate(universe: Universe | None = None) -> list[str]:
    """Structural problems that should block a pipeline run, as human-readable strings."""
    universe = universe or load_universe()
    problems: list[str] = []

    if universe.methodology.start_date > universe.methodology.end_date:
        problems.append(
            f"start_date {universe.methodology.start_date.isoformat()} is after "
            f"end_date {universe.methodology.end_date.isoformat()}"
        )

    for basket in universe.baskets:
        if not basket.holdings:
            problems.append(f"{basket.id} has no holdings")
        if not basket.description:
            problems.append(f"{basket.id} has no description (needed for classification)")
        candidates = basket.candidates_by_ticker
        for holding in basket.holdings:
            if holding.ticker.upper() not in candidates:
                problems.append(
                    f"{holding.ticker} in {basket.id} is not represented in category taxonomy"
                )
    return problems


def main() -> int:
    import json

    universe = load_universe()
    problems = validate(universe)
    payload = {
        "status": "FAIL" if problems else "PASS",
        "baskets": len(universe.baskets),
        "holdings": len(universe.holdings),
        "candidates": sum(len(basket.candidates) for basket in universe.baskets),
        "problems": problems,
    }
    print(json.dumps(payload, indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
