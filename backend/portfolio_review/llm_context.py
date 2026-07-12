from __future__ import annotations

import json
from typing import Any


SCHEMA_VERSION = "portfolio_review_llm_context_v1"


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def limited_dict(row: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: row.get(key) for key in keys if key in row}


def compact_metric_rows(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    compact = []
    for row in rows[:limit]:
        compact.append(
            {
                "model_kind": row.get("model_kind"),
                "status": row.get("status", "tested"),
                "mae": row.get("mae"),
                "directional_accuracy": row.get("directional_accuracy"),
                "rank_ic": row.get("rank_ic"),
                "long_short_spread": row.get("long_short_spread"),
                "authority": row.get("authority"),
            }
        )
    return compact


def model_authority(ml_result: dict[str, Any]) -> dict[str, Any]:
    gate = ml_result.get("performance_gate") if isinstance(ml_result.get("performance_gate"), dict) else {}
    gate_passed = bool(gate.get("passed"))
    trained = ml_result.get("status") == "trained"
    return {
        "usable_for_mechanical_scoring": bool(trained and gate_passed),
        "provisional": not bool(trained and gate_passed),
        "reason": gate.get("reason") or ml_result.get("status", "unknown"),
    }


def build_model_decision_context(ml_result: dict[str, Any]) -> dict[str, Any]:
    recent_tournament = ml_result.get("recent_holdout_tournament")
    if not isinstance(recent_tournament, list):
        recent_tournament = []
    tuning_results = ml_result.get("tuning_results")
    if not isinstance(tuning_results, list):
        tuning_results = []
    advanced = ml_result.get("advanced_model_backtest")
    if not isinstance(advanced, dict):
        advanced = {}
    return {
        "recommendation_engine": {
            "kind": "deterministic_mechanical_rule_engine",
            "active": True,
            "authority": "produces the mechanical recommendation rows from portfolio scores, risk, expected return, and sizing rules",
            "note": "This engine can be active even when the optional ML forecast model is disabled.",
        },
        "champion_model": {
            "model_kind": ml_result.get("model_kind", "mechanical_fallback"),
            "status": ml_result.get("status", "unknown"),
            "training_source": ml_result.get("training_source", ""),
            **model_authority(ml_result),
            "selection_note": "This describes optional ML forecast authority, not whether deterministic mechanical recommendations exist.",
        },
        "validation": {
            "walk_forward": ml_result.get("walk_forward", {}),
            "recent_holdout": ml_result.get("recent_holdout", {}),
            "anchor_backtest": ml_result.get("anchor_backtest", {}),
            "performance_gate": ml_result.get("performance_gate", {}),
            "labeled_rows": ml_result.get("labeled_rows", 0),
            "available_labeled_rows": ml_result.get("available_labeled_rows", 0),
        },
        "models_compared_on_same_dataset": bool(tuning_results or recent_tournament),
        "compared_models": compact_metric_rows(tuning_results or recent_tournament, limit=10),
        "advanced_models": {
            "status": advanced.get("status", "not_present"),
            "best_model": advanced.get("best_model", ""),
            "authority": advanced.get("authority", ""),
            "candidate_results": compact_metric_rows(advanced.get("candidate_results", []) if isinstance(advanced.get("candidate_results"), list) else [], limit=10),
        },
        "caveats": [
            "Model evidence is context for review and journaling; the LLM cannot override recommendations.",
            "When ML is disabled, describe ML forecast evidence as unavailable; do not call deterministic mechanical recommendations invalid solely for that reason.",
            "If models_compared_on_same_dataset is false, treat model comparisons as provisional.",
            "A positive validation metric does not imply the 1% weekly goal is achievable.",
        ],
    }


def compact_forecast(row: dict[str, Any]) -> dict[str, Any]:
    return limited_dict(
        row,
        [
            "portfolio_id",
            "ticker",
            "score",
            "trend_score",
            "risk_score",
            "expected_5d_return_pct",
            "ml_expected_5d_return_pct",
            "rejected_ml_expected_5d_return_pct",
            "prediction_source",
            "ml_model_kind",
            "momentum_5d_pct",
            "momentum_20d_pct",
            "relative_momentum_20d_pct",
            "volatility_20d_pct",
            "drawdown_20d_pct",
            "beta_spy_20d",
            "corr_spy_20d",
        ],
    )


def compact_recommendation(row: dict[str, Any]) -> dict[str, Any]:
    return limited_dict(
        row,
        [
            "portfolio_id",
            "ticker",
            "action",
            "decision_origin",
            "current_weight_pct",
            "recommended_weight_pct",
            "weight_change_pct",
            "expected_5d_return_pct",
            "expected_5d_risk_pct",
            "goal_contribution_pct",
            "confidence_score",
            "evidence_summary",
            "intuition_summary",
            "thesis",
        ],
    )


def build_portfolio_review_llm_context(
    run_id: str,
    run_date: str,
    goal: dict[str, Any],
    ml_result: dict[str, Any],
    feature_rows: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    freshness: dict[str, Any],
    journal_memory: dict[str, Any],
) -> dict[str, Any]:
    forecasts = sorted(
        [compact_forecast(row) for row in feature_rows],
        key=lambda row: (str(row.get("portfolio_id", "")), -as_float(row.get("expected_5d_return_pct"))),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "run": {
            "run_id": run_id,
            "date": run_date,
        },
        "goal": goal,
        "llm_role": {
            "authority": "review_context_math_data_and_journal_only",
            "may": [
                "summarize evidence",
                "identify stale or weak assumptions",
                "separate evidence from intuition",
                "propose journal lessons for future evaluation",
            ],
            "may_not": ["pick_tickers", "override_recommendations", "invent_metrics"],
        },
        "model_decision_context": build_model_decision_context(ml_result),
        "current_forecasts": forecasts[:30],
        "mechanical_recommendations": [compact_recommendation(row) for row in recommendations[:30]],
        "portfolio_diagnostics": diagnostics,
        "freshness": {
            "status": freshness.get("status"),
            "missing": freshness.get("missing", []),
            "files": [
                limited_dict(row, ["name", "exists", "row_count", "latest_observed", "status"])
                for row in freshness.get("files", [])
            ],
        },
        "journal_memory": journal_memory,
        "requested_output": {
            "journal_entries": "Evidence-based and intuition-labeled notes for this run only. Do not replay prior memory rows.",
            "learning_records": "Durable hypotheses or lessons to evaluate in future review runs.",
            "risk_flags": "Data/model caveats that should be visible in the next review.",
        },
    }


def build_llm_review_prompt(context: dict[str, Any]) -> str:
    return (
        "Review this paper-trading portfolio context for the current run only. "
        "Current-run facts come only from `model_decision_context`, `current_forecasts`, "
        "`mechanical_recommendations`, `portfolio_diagnostics`, and `freshness`. "
        "`journal_memory` is historical memory: use it only to identify recurring lessons, "
        "prior outcomes, or stale assumptions. Do not copy, replay, or restate prior-memory "
        "recommendation entries as current-run journal entries. "
        "Do not choose stocks, do not override mechanical recommendations, and do not invent metrics. "
        "Distinguish the deterministic recommendation engine from the optional ML forecast model. "
        "If ML is disabled, say ML forecast evidence is unavailable; do not say the deterministic "
        "recommendation rows are invalid solely because ML is disabled. "
        "If the model is disabled, provisional, or not compared on the same dataset, say that directly. "
        "If `evaluation_focus` is present, explicitly address each focus item; this field is for prompt testing only. "
        "Do not return placeholder learning records such as `None`, `N/A`, or empty lessons; use an empty list instead. "
        "Return JSON with keys `journal_entries`, `learning_records`, and `risk_flags`. "
        "Each journal entry must include `entry_type`, `basis` (`evidence` or `intuition`), "
        "`category`, `summary`, `details`, `linked_tickers`, and `confidence`. "
        "Each learning record must include `learning_type`, `basis`, `summary`, `evidence`, "
        "`confidence`, and `status`; put any hypothesis text in `summary`, not only in `title` or `hypothesis`. "
        "Each risk flag must include `flag_type`, `severity`, `summary`, `details`, and `linked_tickers`. "
        "`details` must be a string, not an object. Prefer 4-8 journal entries and 2-5 learning records.\n\n"
        + json.dumps(context, indent=2, sort_keys=True, default=str)
    )
