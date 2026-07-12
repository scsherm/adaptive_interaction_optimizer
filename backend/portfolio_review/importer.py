from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any


IMPORT_FIELDS = [
    "date",
    "portfolio_id",
    "ticker",
    "buy_date",
    "asset_type",
    "quantity",
    "reference_price",
    "target_value",
    "target_weight_pct",
    "notes",
]


def normalized_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def find_column(fieldnames: list[str], aliases: set[str]) -> str | None:
    by_normalized = {normalized_key(name): name for name in fieldnames}
    for alias in aliases:
        found = by_normalized.get(normalized_key(alias))
        if found:
            return found
    return None


def as_float(value: Any, default: float = 0.0) -> float:
    if value in {"", None}:
        return default
    try:
        return float(str(value).replace("$", "").replace(",", "").replace("%", "").strip())
    except ValueError:
        return default


def round_money(value: float) -> float:
    return round(value + 1e-9, 2)


def parse_portfolio_csv(csv_text: str, capital: float) -> list[dict[str, Any]]:
    reader = csv.DictReader(StringIO(csv_text.strip()))
    fieldnames = reader.fieldnames or []
    ticker_col = find_column(fieldnames, {"ticker", "symbol", "stock", "underlying"})
    if not ticker_col:
        raise ValueError("CSV must include a ticker or symbol column")
    buy_date_col = find_column(fieldnames, {"buy_date", "buy date", "date", "purchase_date", "purchase date"})
    quantity_col = find_column(fieldnames, {"quantity", "qty", "shares", "contracts"})
    price_col = find_column(fieldnames, {"buy_price", "buy price", "price", "reference_price", "avg cost", "average cost"})
    value_col = find_column(fieldnames, {"target_value", "value", "market_value", "cost_basis", "amount"})
    weight_col = find_column(fieldnames, {"target_weight_pct", "weight", "weight_pct", "allocation", "allocation_pct"})
    notes_col = find_column(fieldnames, {"notes", "note", "thesis", "memo"})
    asset_col = find_column(fieldnames, {"asset_type", "asset type", "type", "instrument"})

    positions = []
    for row in reader:
        ticker = str(row.get(ticker_col, "")).strip().upper()
        if not ticker:
            continue
        quantity = as_float(row.get(quantity_col)) if quantity_col else 0.0
        price = as_float(row.get(price_col)) if price_col else 0.0
        target_value = as_float(row.get(value_col)) if value_col else 0.0
        weight = as_float(row.get(weight_col)) if weight_col else 0.0
        if not target_value and quantity and price:
            target_value = quantity * price
        if not target_value and weight:
            target_value = capital * weight / 100.0
        if not weight and target_value:
            weight = target_value / capital * 100.0
        positions.append(
            {
                "ticker": ticker,
                "buy_date": str(row.get(buy_date_col, "")).strip() if buy_date_col else "",
                "asset_type": str(row.get(asset_col, "stock")).strip() if asset_col else "stock",
                "quantity": round(quantity, 4),
                "reference_price": round(price, 4),
                "target_value": round_money(target_value),
                "target_weight_pct": round(weight, 4),
                "notes": str(row.get(notes_col, "")).strip() if notes_col else "",
            }
        )
    return positions


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=IMPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def import_portfolio_csv(
    csv_text: str,
    portfolio_id: str,
    data_dir: Path,
    run_date: str,
    capital: float = 100000.0,
) -> dict[str, Any]:
    positions = parse_portfolio_csv(csv_text, capital)
    for position in positions:
        position["date"] = run_date
        position["portfolio_id"] = portfolio_id
    gross = sum(float(row["target_value"]) for row in positions)
    output_dir = data_dir / "imported_portfolios" / portfolio_id
    snapshot_path = output_dir / f"portfolio_snapshot_{run_date}.csv"
    write_csv(snapshot_path, positions)
    write_csv(output_dir / "portfolio_history.csv", positions)
    state = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "date": run_date,
        "portfolio_id": portfolio_id,
        "source": "csv_import",
        "summary": {
            "capital": round_money(capital),
            "gross_exposure": round_money(gross),
            "gross_exposure_pct": round(gross / capital * 100.0, 4) if capital else 0.0,
            "cash_reserve": round_money(capital - gross),
            "cash_reserve_pct": round((capital - gross) / capital * 100.0, 4) if capital else 0.0,
            "position_count": len(positions),
        },
        "positions": positions,
        "files": {
            "snapshot": str(snapshot_path),
            "portfolio_history": str(output_dir / "portfolio_history.csv"),
            "current_state": str(output_dir / "current_state.json"),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "current_state.json").write_text(json.dumps(state, indent=2))
    return state


def import_portfolio_csv_api(payload: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    csv_text = str(payload.get("csvText", ""))
    if not csv_text.strip():
        raise ValueError("csvText is required")
    portfolio_id = str(payload.get("portfolioId") or "uploaded_portfolio").strip()
    run_date = str(payload.get("runDate") or datetime.now(UTC).date().isoformat())
    capital = as_float(payload.get("capital"), 100000.0)
    return import_portfolio_csv(
        csv_text,
        portfolio_id=portfolio_id,
        data_dir=data_dir,
        run_date=run_date,
        capital=capital,
    )
