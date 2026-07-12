from __future__ import annotations

from typing import Any


def passes(row: dict[str, Any]) -> bool:
    return (
        float(row.get("directional_accuracy", 0.0)) >= 0.50
        and float(row.get("rank_ic", 0.0)) > 0.0
        and float(row.get("long_short_spread", 0.0)) > 0.0
    )


def summarize_tournament(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if passes(row)]
    if not eligible:
        return {"winner": "", "authority": "not_eligible", "reason": "no_model_passed_validation"}
    winner = max(
        eligible,
        key=lambda row: (
            float(row.get("long_short_spread", 0.0)),
            float(row.get("rank_ic", 0.0)),
            float(row.get("directional_accuracy", 0.0)),
            -float(row.get("mae", 999.0)),
        ),
    )
    return {"winner": winner["model_kind"], "authority": "eligible", "winner_metrics": winner}
