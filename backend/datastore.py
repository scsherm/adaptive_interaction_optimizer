#!/usr/bin/env python3
"""Queryable view over the pipeline's outputs.

The pipeline writes flat CSVs and the builders bake one JSON blob per page, so
every question the workstation can answer has to be decided at build time. This
module registers those CSVs -- plus the basket universe itself -- as DuckDB
views, so a question can instead be asked as SQL at read time.

    from datastore import query
    query("SELECT ticker, basket FROM holdings WHERE basket = 'metals'")

CLI:
    python datastore.py catalog
    python datastore.py schema basket_metrics
    python datastore.py query "SELECT * FROM basket_metrics LIMIT 5"
    python datastore.py export-parquet
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

from universe import ROOT, load_universe


DATA_DIR = ROOT / "data"
PARQUET_DIR = DATA_DIR / "parquet"

# Sub-directories whose CSVs are worth exposing, mapped to a table-name prefix.
NESTED_SOURCES = {"sentiment": "sentiment"}

# Artifacts from a removed rotation stage. They are frozen months behind the
# rest of the pipeline, so they are excluded rather than silently joined against.
STALE_TABLES = {
    "basket_rotation_scores",
    "basket_rotation_daily",
    "rotation_changes",
}

_SELECT_RE = re.compile(r"^\s*(?:with|select|describe|summarize|explain|pragma|show)\b", re.IGNORECASE)


class DatastoreError(RuntimeError):
    pass


def _duckdb():
    try:
        import duckdb  # noqa: PLC0415
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise DatastoreError(
            "duckdb is not installed. Run `npm run setup` (or "
            "`backend/.venv/bin/python -m pip install -r backend/requirements.txt`)."
        ) from exc
    return duckdb


def csv_sources(data_dir: Path = DATA_DIR) -> dict[str, Path]:
    """Table name -> CSV path, for every CSV the pipeline emits."""
    sources: dict[str, Path] = {}
    for path in sorted(data_dir.glob("*.csv")):
        if path.stem in STALE_TABLES:
            continue
        sources[path.stem] = path
    for folder, prefix in NESTED_SOURCES.items():
        for path in sorted((data_dir / folder).glob("*.csv")):
            name = path.stem if path.stem.startswith(prefix) else f"{prefix}_{path.stem}"
            sources[name] = path
    return sources


# ---------------------------------------------------------------------------
# Universe tables
# ---------------------------------------------------------------------------

UNIVERSE_TABLES = {
    "baskets": (
        ["id", "label", "short", "color", "description", "taxonomy_path", "keywords", "holding_count"],
        ["VARCHAR", "VARCHAR", "VARCHAR", "VARCHAR", "VARCHAR", "VARCHAR", "VARCHAR", "INTEGER"],
    ),
    "holdings": (
        ["basket", "ticker", "name", "note"],
        ["VARCHAR", "VARCHAR", "VARCHAR", "VARCHAR"],
    ),
    "candidates": (
        ["basket", "ticker", "name", "note", "is_holding"],
        ["VARCHAR", "VARCHAR", "VARCHAR", "VARCHAR", "BOOLEAN"],
    ),
    "benchmarks": (
        ["ticker", "name", "note"],
        ["VARCHAR", "VARCHAR", "VARCHAR"],
    ),
}


def universe_rows() -> dict[str, list[tuple]]:
    universe = load_universe()
    baskets, holdings, candidates = [], [], []
    for basket in universe.baskets:
        held = basket.holding_tickers
        baskets.append(
            (
                basket.id,
                basket.label,
                basket.short,
                basket.color,
                basket.description,
                " / ".join(basket.path),
                ", ".join(basket.keywords),
                len(basket.holdings),
            )
        )
        for holding in basket.holdings:
            holdings.append((basket.id, holding.ticker, holding.name, holding.note))
        for candidate in basket.candidates:
            candidates.append(
                (basket.id, candidate.ticker, candidate.name, candidate.note, candidate.ticker in held)
            )
    benchmarks = [(row.ticker, row.name, row.note) for row in universe.benchmarks]
    return {
        "baskets": baskets,
        "holdings": holdings,
        "candidates": candidates,
        "benchmarks": benchmarks,
    }


def connect(data_dir: Path = DATA_DIR):
    """An in-memory DuckDB connection with every artifact registered.

    CSV views are lazy -- DuckDB only reads a file when a query touches it.
    """
    duckdb = _duckdb()
    connection = duckdb.connect(":memory:")
    for name, path in csv_sources(data_dir).items():
        # DDL cannot take bound parameters in DuckDB, so the path is inlined.
        literal = str(path).replace("'", "''")
        connection.execute(
            f'CREATE OR REPLACE VIEW "{name}" AS '
            f"SELECT * FROM read_csv_auto('{literal}', header=true, sample_size=-1)"
        )
    rows_by_table = universe_rows()
    for name, (columns, types) in UNIVERSE_TABLES.items():
        spec = ", ".join(f'"{column}" {kind}' for column, kind in zip(columns, types))
        connection.execute(f'CREATE OR REPLACE TABLE "{name}" ({spec})')
        rows = rows_by_table[name]
        if rows:
            placeholders = ", ".join("?" for _ in columns)
            connection.executemany(f'INSERT INTO "{name}" VALUES ({placeholders})', rows)
    return connection


def query(
    sql: str,
    params: Iterable[Any] | None = None,
    *,
    data_dir: Path = DATA_DIR,
    read_only: bool = True,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Run SQL and return rows as dicts.

    `read_only` (the default) rejects anything that is not a read statement, so
    an agent driving this cannot mutate or drop the registered artifacts.
    """
    if read_only and not _SELECT_RE.match(sql):
        raise DatastoreError(
            "Only read statements are allowed here. Pass read_only=False if a write is intended."
        )
    connection = connect(data_dir)
    try:
        cursor = connection.execute(sql, list(params) if params else None)
        columns = [column[0] for column in cursor.description or []]
        rows = cursor.fetchmany(limit) if limit else cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        connection.close()


def catalog(data_dir: Path = DATA_DIR) -> list[dict[str, Any]]:
    """Every queryable table with its columns and row count."""
    connection = connect(data_dir)
    try:
        names = sorted({*csv_sources(data_dir), *UNIVERSE_TABLES})
        entries = []
        for name in names:
            try:
                columns = [
                    {"name": row[0], "type": row[1]}
                    for row in connection.execute(f'DESCRIBE "{name}"').fetchall()
                ]
                count = connection.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
            except Exception as exc:  # a malformed CSV should not blank the catalog
                entries.append({"table": name, "error": str(exc)[:200]})
                continue
            entries.append(
                {
                    "table": name,
                    "source": "universe" if name in UNIVERSE_TABLES else "csv",
                    "rows": count,
                    "columns": columns,
                }
            )
        return entries
    finally:
        connection.close()


def export_parquet(data_dir: Path = DATA_DIR, target: Path = PARQUET_DIR) -> list[str]:
    """Materialize every table to Parquet -- faster repeat reads, stable types."""
    target.mkdir(parents=True, exist_ok=True)
    connection = connect(data_dir)
    written = []
    try:
        for name in sorted({*csv_sources(data_dir), *UNIVERSE_TABLES}):
            out = target / f"{name}.parquet"
            connection.execute(
                f"COPY (SELECT * FROM \"{name}\") TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            written.append(str(out.relative_to(ROOT)))
    finally:
        connection.close()
    return written


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "catalog"
    if command == "catalog":
        entries = catalog()
        for entry in entries:
            if "error" in entry:
                print(f"{entry['table']:<36} ERROR {entry['error']}")
                continue
            print(f"{entry['table']:<36} {entry['rows']:>8} rows  {len(entry['columns'])} cols")
        print(f"\n{len(entries)} tables")
        return 0
    if command == "schema":
        if len(argv) < 3:
            print("usage: datastore.py schema <table>", file=sys.stderr)
            return 2
        entry = next((row for row in catalog() if row["table"] == argv[2]), None)
        if entry is None:
            print(f"unknown table: {argv[2]}", file=sys.stderr)
            return 1
        print(json.dumps(entry, indent=2, default=str))
        return 0
    if command == "query":
        if len(argv) < 3:
            print('usage: datastore.py query "SELECT ..."', file=sys.stderr)
            return 2
        rows = query(argv[2])
        print(json.dumps(rows, indent=2, default=str))
        return 0
    if command == "export-parquet":
        written = export_parquet()
        print(json.dumps({"written": written, "count": len(written)}, indent=2))
        return 0
    print(f"unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
