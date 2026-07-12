from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from portfolio_review.llm_adapter import call_openai_json, load_llm_config
from portfolio_review.llm_context import build_llm_review_prompt, build_portfolio_review_llm_context


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "portfolio_review" / "llm_prompt_evals"


def base_features() -> list[dict[str, Any]]:
    return [
        {
            "portfolio_id": "app_metrics",
            "ticker": "AAA",
            "score": 83.0,
            "trend_score": 86.0,
            "risk_score": 72.0,
            "expected_5d_return_pct": 2.8,
            "ml_expected_5d_return_pct": 2.4,
            "prediction_source": "ml",
            "ml_model_kind": "extra_trees_depth_8_leaf_12_grid_winner",
            "momentum_20d_pct": 18.2,
            "relative_momentum_20d_pct": 12.1,
            "volatility_20d_pct": 34.0,
            "drawdown_20d_pct": 3.2,
            "beta_spy_20d": 1.1,
            "corr_spy_20d": 0.62,
        },
        {
            "portfolio_id": "app_metrics",
            "ticker": "BBB",
            "score": 76.0,
            "trend_score": 81.0,
            "risk_score": 38.0,
            "expected_5d_return_pct": 3.1,
            "ml_expected_5d_return_pct": 1.1,
            "prediction_source": "mechanical",
            "ml_model_kind": "mechanical_fallback",
            "momentum_20d_pct": 41.5,
            "relative_momentum_20d_pct": 35.4,
            "volatility_20d_pct": 119.0,
            "drawdown_20d_pct": 22.0,
            "beta_spy_20d": 6.4,
            "corr_spy_20d": 0.48,
        },
        {
            "portfolio_id": "web_metrics",
            "ticker": "CCC",
            "score": 45.0,
            "trend_score": 42.0,
            "risk_score": 65.0,
            "expected_5d_return_pct": -1.4,
            "ml_expected_5d_return_pct": -0.9,
            "prediction_source": "ml",
            "ml_model_kind": "extra_trees_depth_8_leaf_12_grid_winner",
            "momentum_20d_pct": -13.0,
            "relative_momentum_20d_pct": -17.0,
            "volatility_20d_pct": 47.0,
            "drawdown_20d_pct": 18.0,
            "beta_spy_20d": 1.7,
            "corr_spy_20d": 0.52,
        },
    ]


def base_recommendations() -> list[dict[str, Any]]:
    return [
        {
            "portfolio_id": "app_metrics",
            "ticker": "AAA",
            "action": "ADD",
            "decision_origin": "mechanical",
            "current_weight_pct": 3.0,
            "recommended_weight_pct": 6.0,
            "weight_change_pct": 3.0,
            "expected_5d_return_pct": 2.8,
            "expected_5d_risk_pct": 3.2,
            "goal_contribution_pct": 0.168,
            "confidence_score": 81.0,
            "evidence_summary": "score 83.0, trend 86.0, risk 72.0, ml expected 5d return 2.4%.",
            "intuition_summary": "No discretionary override.",
            "thesis": "Strong score and validated ML forecast.",
        },
        {
            "portfolio_id": "app_metrics",
            "ticker": "BBB",
            "action": "ADD",
            "decision_origin": "mechanical",
            "current_weight_pct": 0.0,
            "recommended_weight_pct": 3.5,
            "weight_change_pct": 3.5,
            "expected_5d_return_pct": 3.1,
            "expected_5d_risk_pct": 7.0,
            "goal_contribution_pct": 0.1085,
            "confidence_score": 67.0,
            "evidence_summary": "high momentum but high beta and high realized volatility.",
            "intuition_summary": "No discretionary override.",
            "thesis": "Momentum is strong but fragile.",
        },
        {
            "portfolio_id": "web_metrics",
            "ticker": "CCC",
            "action": "TRIM",
            "decision_origin": "mechanical",
            "current_weight_pct": 6.0,
            "recommended_weight_pct": 2.0,
            "weight_change_pct": -4.0,
            "expected_5d_return_pct": -1.4,
            "expected_5d_risk_pct": 4.1,
            "goal_contribution_pct": -0.028,
            "confidence_score": 62.0,
            "evidence_summary": "negative momentum and negative expected return.",
            "intuition_summary": "No discretionary override.",
            "thesis": "Thesis deterioration.",
        },
    ]


def freshness(status: str = "ready", missing: list[str] | None = None) -> dict[str, Any]:
    missing = missing or []
    return {
        "status": status,
        "missing": missing,
        "files": [
            {"name": "raw_prices", "exists": "raw_prices" not in missing, "row_count": 5000, "latest_observed": "2026-05-25", "status": "ok"},
            {"name": "ticker_sentiment", "exists": "ticker_sentiment" not in missing, "row_count": 120, "latest_observed": "2026-05-18", "status": "stale" if status == "stale_inputs" else "ok"},
        ],
    }


def diagnostics(weekly_return: float, target_gap: float) -> list[dict[str, Any]]:
    return [
        {
            "run_id": "simulated",
            "date": "2026-05-25",
            "portfolio_id": "app_metrics",
            "portfolio_value": 101200.0,
            "gross_exposure_pct": 106.0,
            "cash_reserve": 7000.0,
            "weekly_return_pct": weekly_return,
            "target_weekly_return_pct": 1.0,
            "target_gap_pct": target_gap,
            "position_count": 18,
        }
    ]


def trained_ml_result() -> dict[str, Any]:
    return {
        "status": "trained",
        "model_kind": "extra_trees_depth_8_leaf_12_grid_winner",
        "training_source": "raw_price_history_bootstrap",
        "labeled_rows": 3200,
        "available_labeled_rows": 4800,
        "walk_forward": {"mae": 4.1, "directional_accuracy": 0.58, "rank_ic": 0.18, "long_short_spread": 2.4},
        "recent_holdout": {"status": "tested", "mae": 3.9, "directional_accuracy": 0.61, "rank_ic": 0.21, "long_short_spread": 3.1},
        "performance_gate": {"passed": True, "reason": "walk_forward_and_recent_holdout_passed"},
        "tuning_results": [
            {"model_kind": "extra_trees_depth_8_leaf_12_grid_winner", "mae": 4.1, "directional_accuracy": 0.58, "rank_ic": 0.18, "long_short_spread": 2.4},
            {"model_kind": "ridge_standardized", "mae": 5.3, "directional_accuracy": 0.51, "rank_ic": 0.03, "long_short_spread": 0.4},
        ],
        "advanced_model_backtest": {
            "status": "tested",
            "best_model": "chronos_bolt_tiny_ctx252",
            "authority": "eligible",
            "candidate_results": [
                {"model_kind": "chronos_bolt_tiny_ctx252", "mae": 4.0268, "directional_accuracy": 0.6222, "rank_ic": 0.2904, "long_short_spread": 8.2329},
                {"model_kind": "granite_ttm_r2_ctx64", "mae": 4.5425, "directional_accuracy": 0.5344, "rank_ic": 0.1172, "long_short_spread": 1.9409},
            ],
        },
    }


def disabled_ml_result() -> dict[str, Any]:
    return {
        "status": "disabled",
        "model_kind": "mechanical_fallback",
        "labeled_rows": 0,
        "available_labeled_rows": 0,
        "walk_forward": {},
        "performance_gate": {},
    }


def bad_ml_result() -> dict[str, Any]:
    return {
        "status": "trained_low_confidence",
        "model_kind": "bad_test_model",
        "training_source": "raw_price_history_bootstrap",
        "labeled_rows": 900,
        "available_labeled_rows": 1200,
        "walk_forward": {"mae": 6.2, "directional_accuracy": 0.46, "rank_ic": -0.08, "long_short_spread": -1.2},
        "recent_holdout": {"status": "tested", "mae": 6.8, "directional_accuracy": 0.44, "rank_ic": -0.12, "long_short_spread": -2.1},
        "performance_gate": {"passed": False, "reason": "walk_forward_or_recent_holdout_failed"},
        "tuning_results": [
            {"model_kind": "bad_test_model", "mae": 6.2, "directional_accuracy": 0.46, "rank_ic": -0.08, "long_short_spread": -1.2}
        ],
    }


def memory(with_bad_prior_outcomes: bool = False) -> dict[str, Any]:
    outcomes = []
    learnings = []
    if with_bad_prior_outcomes:
        outcomes = [
            {
                "ticker": "BBB",
                "horizon": "review_to_review",
                "realized_return_pct": -8.4,
                "benchmark_return_pct": 0.6,
                "target_hit": 0,
                "payload": {"action": "ADD", "start_date": "2026-05-17", "end_date": "2026-05-24"},
            }
        ]
        learnings = [
            {
                "learning_type": "evidence",
                "basis": "evidence",
                "summary": "High beta momentum adds underperformed during the prior review window.",
                "evidence": {"beta_spy_20d": 6.1, "realized_return_pct": -8.4},
                "confidence": 0.82,
                "status": "active",
            }
        ]
    return {
        "recent_learnings": learnings,
        "recent_journal_entries": [],
        "recent_decisions": [],
        "recent_outcomes": outcomes,
    }


def make_context(case_id: str, ml_result: dict[str, Any], weekly_return: float, target_gap: float, freshness_payload: dict[str, Any], memory_payload: dict[str, Any]) -> dict[str, Any]:
    return build_portfolio_review_llm_context(
        run_id=f"eval_{case_id}",
        run_date="2026-05-25",
        goal={"weekly_return_pct": 1.0, "weekly_return_dollars_on_100k": 1000.0},
        ml_result=ml_result,
        feature_rows=base_features(),
        recommendations=base_recommendations(),
        diagnostics=diagnostics(weekly_return, target_gap),
        freshness=freshness_payload,
        journal_memory=memory_payload,
    )


def with_focus(context: dict[str, Any], case_id: str, focus: list[str]) -> dict[str, Any]:
    updated = dict(context)
    updated["evaluation_focus"] = {
        "case_id": case_id,
        "must_address": focus,
        "note": "Prompt-eval only. Address these items using the supplied context; do not invent facts.",
    }
    return updated


def simulated_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "trained_model_with_mixed_recommendations",
            "description": "ML passes validation, recommendations include ADD and TRIM, and risk varies.",
            "context": with_focus(
                make_context("trained", trained_ml_result(), weekly_return=0.4, target_gap=0.6, freshness_payload=freshness(), memory_payload=memory()),
                "trained_model_with_mixed_recommendations",
                ["validated ML is available", "mixed ADD/TRIM recommendations", "risk dispersion"],
            ),
            "expect": [["validated", "validation"], ["add", "trim"], ["risk", "volatility", "drawdown"]],
        },
        {
            "case_id": "disabled_ml_but_active_rule_engine",
            "description": "ML is disabled, but deterministic recommendations still exist.",
            "context": with_focus(
                make_context("disabled", disabled_ml_result(), weekly_return=0.2, target_gap=0.8, freshness_payload=freshness(), memory_payload=memory()),
                "disabled_ml_but_active_rule_engine",
                ["ML forecast evidence unavailable", "deterministic rule engine active"],
            ),
            "expect": [["ml"], ["deterministic", "rule"], ["unavailable", "disabled"]],
        },
        {
            "case_id": "failed_model_validation",
            "description": "ML was trained but failed validation; context should label it non-authoritative.",
            "context": with_focus(
                make_context("bad_model", bad_ml_result(), weekly_return=-1.1, target_gap=2.1, freshness_payload=freshness(), memory_payload=memory()),
                "failed_model_validation",
                ["validation failed", "ML non-authoritative", "goal gap is negative"],
            ),
            "expect": [["failed", "low-confidence", "non-authoritative"], ["validation"], ["goal", "target"]],
        },
        {
            "case_id": "stale_and_missing_inputs",
            "description": "Important data files are stale or missing.",
            "context": with_focus(
                make_context("stale", trained_ml_result(), weekly_return=1.3, target_gap=-0.3, freshness_payload=freshness("stale_inputs", ["ticker_sentiment"]), memory_payload=memory()),
                "stale_and_missing_inputs",
                ["stale or missing ticker_sentiment", "confidence impact", "target is currently ahead"],
            ),
            "expect": [["stale", "missing"], ["confidence"], ["target", "weekly"]],
        },
        {
            "case_id": "prior_outcome_contradicts_current_signal",
            "description": "Current high-beta ADD conflicts with prior outcome memory.",
            "context": with_focus(
                make_context("memory_conflict", trained_ml_result(), weekly_return=0.9, target_gap=0.1, freshness_payload=freshness(), memory_payload=memory(with_bad_prior_outcomes=True)),
                "prior_outcome_contradicts_current_signal",
                ["prior outcome memory conflicts with current high-beta ADD", "BBB risk", "do not override recommendation"],
            ),
            "expect": [["prior", "outcome", "memory"], ["high beta", "beta", "volatility"], ["bbb"]],
        },
    ]


def flatten_text(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, default=str).lower()


def evaluate_result(case: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    text = flatten_text(result)
    journal_entries = result.get("journal_entries", []) if isinstance(result, dict) else []
    learning_records = result.get("learning_records", []) if isinstance(result, dict) else []
    risk_flags = result.get("risk_flags", []) if isinstance(result, dict) else []
    useful_learning_records = [
        row
        for row in learning_records
        if isinstance(row, dict) and str(row.get("summary", "")).strip().lower() not in {"", "none", "n/a", "na", "null"}
    ]
    expected_groups = case.get("expect", [])
    expected_passed = True
    for group in expected_groups:
        if isinstance(group, str):
            group = [group]
        if not any(str(term).lower() in text for term in group):
            expected_passed = False
            break
    checks = {
        "api_used": bool(response.get("used")),
        "no_error": not bool(response.get("error")),
        "has_journal_entries": isinstance(journal_entries, list) and len(journal_entries) >= 3,
        "has_useful_learning_records": isinstance(learning_records, list) and len(useful_learning_records) >= 1,
        "has_risk_flags": isinstance(risk_flags, list) and len(risk_flags) >= 1,
        "does_not_claim_stock_picking_authority": "i recommend buying" not in text and "you should buy" not in text,
        "mentions_expected_case_terms": expected_passed,
    }
    return {
        "case_id": case["case_id"],
        "description": case["description"],
        "passed": all(checks.values()),
        "checks": checks,
        "response": response,
    }


def run_eval(output_dir: Path = OUTPUT_DIR, live: bool = True) -> dict[str, Any]:
    run_id = datetime.now(UTC).strftime("llm_prompt_eval_%Y%m%dT%H%M%SZ")
    cases = simulated_cases()
    results = []
    for case in cases:
        prompt = build_llm_review_prompt(case["context"])
        response = call_openai_json(prompt, schema_name=f"portfolio_review_prompt_eval_{case['case_id']}") if live else {"used": False, "result": {}, "error": "live disabled"}
        results.append(evaluate_result(case, response))
    summary = {
        "run_id": run_id,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": load_llm_config()["model"],
        "case_count": len(results),
        "passed_count": sum(1 for row in results if row["passed"]),
        "failed_cases": [row["case_id"] for row in results if not row["passed"]],
        "results": results,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{run_id}.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str))
    (output_dir / "latest.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=str))
    summary["path"] = str(path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run simulated LLM prompt evals for portfolio review.")
    parser.add_argument("--dry-run", action="store_true", help="Build cases without calling the LLM.")
    args = parser.parse_args()
    summary = run_eval(live=not args.dry_run)
    print(json.dumps({key: summary[key] for key in ["run_id", "model", "case_count", "passed_count", "failed_cases", "path"]}, indent=2))


if __name__ == "__main__":
    main()
