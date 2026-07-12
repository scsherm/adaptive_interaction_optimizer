#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import os
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from portfolio_review.advanced_forecasting import run_advanced_price_backtest, select_specs
from portfolio_review.foundation_models import foundation_model_candidates
from portfolio_review.journal_store import JournalStore, SCHEMA_VERSION as JOURNAL_SCHEMA_VERSION
from portfolio_review.llm_adapter import call_openai_json, env_flag, load_llm_config
from portfolio_review.llm_context import build_llm_review_prompt, build_portfolio_review_llm_context
from portfolio_review.ml_models import (
    build_latest_price_feature_rows,
    build_ml_predictions,
    build_price_history_training_rows,
    run_anchor_backtest,
)
from portfolio_review.model_lab import summarize_tournament
from portfolio_review.training_dataset import select_training_universe_tickers


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = DATA_DIR / "portfolio_review"
MODEL_VERSION = "portfolio_review_mechanical_v1"

PORTFOLIO_CONFIG = {
    "app_metrics": {
        "label": "App Metrics Portfolio",
        "dir": "paper_portfolio",
        "candidate_score_field": "paper_score",
        "name_field": "name",
        "group_field": "basket",
        "price_field": "end_adj_close",
        "risk_field": "risk_adjustment_score",
        "options_field": "options_setup_score",
    },
    "web_metrics": {
        "label": "Web Metrics Portfolio",
        "dir": "web_portfolio",
        "candidate_score_field": "web_score",
        "name_field": "company",
        "group_field": "sector",
        "price_field": "reference_price",
        "risk_field": "risk_score",
        "options_field": "options_score",
    },
}

FEATURE_FIELDS = [
    "run_id",
    "date",
    "portfolio_id",
    "ticker",
    "name",
    "group",
    "asset_type",
    "current_weight_pct",
    "recommended_weight_pct",
    "score",
    "trend_score",
    "risk_score",
    "sentiment_or_catalyst_score",
    "options_score",
    "expected_5d_return_pct",
    "ml_expected_5d_return_pct",
    "rejected_ml_expected_5d_return_pct",
    "prediction_source",
    "ml_model_kind",
    "price_score",
    "price_trend_score",
    "price_risk_score",
    "momentum_1d_pct",
    "momentum_5d_pct",
    "momentum_10d_pct",
    "momentum_20d_pct",
    "momentum_40d_pct",
    "momentum_60d_pct",
    "relative_momentum_5d_pct",
    "relative_momentum_20d_pct",
    "relative_momentum_60d_pct",
    "ma_gap_10d_pct",
    "ma_gap_20d_pct",
    "ma_gap_50d_pct",
    "volatility_10d_pct",
    "volatility_20d_pct",
    "volatility_60d_pct",
    "drawdown_20d_pct",
    "drawdown_60d_pct",
    "volume_ratio_5_20",
    "beta_spy_20d",
    "beta_spy_60d",
    "corr_spy_20d",
    "corr_spy_60d",
    "spy_momentum_5d_pct",
    "spy_momentum_20d_pct",
    "spy_volatility_20d_pct",
    "spy_ma_gap_50d_pct",
    "cross_section_momentum_20d_rank",
    "cross_section_relative_momentum_20d_rank",
    "cross_section_volatility_20d_rank",
    "cross_section_drawdown_20d_rank",
    "cross_section_volume_ratio_rank",
    "expected_5d_risk_pct",
    "goal_contribution_pct",
    "source_notes",
    "source_urls",
    "thesis",
    "forward_5d_return_pct",
]

RECOMMENDATION_FIELDS = [
    "run_id",
    "date",
    "portfolio_id",
    "ticker",
    "name",
    "group",
    "asset_type",
    "action",
    "decision_origin",
    "current_weight_pct",
    "recommended_weight_pct",
    "weight_change_pct",
    "expected_5d_return_pct",
    "expected_5d_risk_pct",
    "goal_contribution_pct",
    "confidence_score",
    "model_version",
    "evidence_summary",
    "intuition_summary",
    "thesis",
]

DIAGNOSTIC_FIELDS = [
    "run_id",
    "date",
    "portfolio_id",
    "portfolio_value",
    "gross_exposure_pct",
    "cash_reserve",
    "weekly_return_pct",
    "target_weekly_return_pct",
    "target_gap_pct",
    "position_count",
]

FRESHNESS_FILES = [
    ("raw_prices", "raw_prices.csv", ["date"]),
    ("app_candidates", "paper_portfolio/candidate_scores.csv", ["data_as_of_date"]),
    ("web_candidates", "web_portfolio/candidate_scores.csv", []),
    ("app_state", "paper_portfolio/current_state.json", []),
    ("web_state", "web_portfolio/current_state.json", []),
    ("ticker_sentiment", "ticker_news_sentiment.csv", ["run_date"]),
    ("options_positioning", "options_positioning_metrics.csv", ["as_of_timestamp"]),
    ("fundamentals", "fundamentals_metrics.csv", ["as_of_date"]),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def as_float(value: Any, default: float = 0.0) -> float:
    if value in {"", None}:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def round_money(value: float) -> float:
    return round(value + 1e-9, 2)


def round_pct(value: float) -> float:
    return round(value + 1e-9, 4)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def latest_value(rows: list[dict[str, str]], fields: list[str]) -> str:
    values: list[str] = []
    for row in rows:
        for field in fields:
            value = row.get(field, "")
            if value:
                values.append(value)
    return max(values) if values else ""


def build_freshness_report(data_dir: Path, refresh_requested: bool) -> dict[str, Any]:
    files = []
    for label, relative, date_fields in FRESHNESS_FILES:
        path = data_dir / relative
        row_count = 0
        latest = ""
        if path.suffix == ".csv":
            rows = read_csv(path)
            row_count = len(rows)
            latest = latest_value(rows, date_fields)
        elif path.exists():
            payload = read_json(path)
            row_count = 1
            latest = str(payload.get("data_as_of_date") or payload.get("date") or "")
        files.append(
            {
                "name": label,
                "path": str(path),
                "exists": path.exists(),
                "row_count": row_count,
                "latest_observed": latest,
                "status": "ok" if path.exists() else "missing",
            }
        )
    missing = [row["name"] for row in files if not row["exists"]]
    return {
        "requested": refresh_requested,
        "performed": False,
        "status": "missing_inputs" if missing else "ready",
        "missing": missing,
        "files": files,
    }


def refresh_data_if_requested(refresh_requested: bool, run_id: str) -> dict[str, Any]:
    if not refresh_requested:
        return {
            "requested": False,
            "performed": False,
            "return_code": None,
            "command": [],
            "log_tail": [],
            "error": "",
        }
    refresh_run_id = f"{run_id}_data_refresh"
    command = [
        sys.executable,
        "run_pipeline.py",
        "--run-id",
        refresh_run_id,
        "--refresh-prices",
        "--refresh-fundamentals",
        "--refresh-positioning",
        "--refresh-ownership",
        "--refresh-sentiment",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        log_lines = completed.stdout.splitlines()[-80:]
        return {
            "requested": True,
            "performed": completed.returncode == 0,
            "return_code": completed.returncode,
            "command": command,
            "log_tail": log_lines,
            "error": "" if completed.returncode == 0 else "Data refresh command returned a non-zero exit code.",
        }
    except Exception as exc:  # pragma: no cover - surfaced in review payload
        return {
            "requested": True,
            "performed": False,
            "return_code": 1,
            "command": command,
            "log_tail": [],
            "error": str(exc),
        }


def current_position_weights(state: dict[str, Any]) -> dict[str, float]:
    weights: dict[str, float] = {}
    for position in state.get("positions", []):
        ticker = str(position.get("ticker", ""))
        if not ticker:
            continue
        weights[ticker] = weights.get(ticker, 0.0) + as_float(position.get("target_weight_pct"))
    return weights


def current_position_names(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(position.get("ticker", "")): position for position in state.get("positions", []) if position.get("ticker")}


def load_portfolio_state(data_dir: Path, portfolio_id: str) -> dict[str, Any]:
    config = PORTFOLIO_CONFIG[portfolio_id]
    state = read_json(data_dir / str(config["dir"]) / "current_state.json")
    return {
        "id": portfolio_id,
        "label": config["label"],
        "state": state,
        "summary": state.get("summary", {}),
        "positions": state.get("positions", []),
    }


def normalize_candidate(row: dict[str, str], portfolio_id: str) -> dict[str, Any]:
    config = PORTFOLIO_CONFIG[portfolio_id]
    score = as_float(row.get(str(config["candidate_score_field"])), 50.0)
    trend = as_float(row.get("trend_score"), 50.0)
    risk = as_float(row.get(str(config["risk_field"])), 50.0)
    options = as_float(row.get(str(config["options_field"])), 50.0)
    sentiment = as_float(row.get("sentiment_score") or row.get("catalyst_score"), 50.0)
    return {
        "portfolio_id": portfolio_id,
        "ticker": row.get("ticker", ""),
        "name": row.get(str(config["name_field"]), row.get("ticker", "")),
        "group": row.get(str(config["group_field"]), ""),
        "asset_type": row.get("asset_type", "stock") or "stock",
        "score": score,
        "trend_score": trend,
        "risk_score": risk,
        "sentiment_or_catalyst_score": sentiment,
        "options_score": options,
        "reference_price": as_float(row.get(str(config["price_field"]))),
        "source_notes": row.get("source_notes", ""),
        "source_urls": row.get("source_urls", ""),
        "thesis": row.get("thesis", ""),
    }


def load_candidates(data_dir: Path, portfolio_id: str) -> list[dict[str, Any]]:
    config = PORTFOLIO_CONFIG[portfolio_id]
    rows = read_csv(data_dir / str(config["dir"]) / "candidate_scores.csv")
    candidates = [normalize_candidate(row, portfolio_id) for row in rows if row.get("ticker")]
    candidates.sort(key=lambda row: float(row["score"]), reverse=True)
    return candidates


def expected_return(score: float, trend: float, sentiment: float) -> float:
    raw = (score - 50.0) * 0.055 + (trend - 50.0) * 0.025 + (sentiment - 50.0) * 0.015
    return round_pct(clamp(raw, -2.5, 4.5))


def expected_risk(risk_score: float, options_score: float, current_weight: float) -> float:
    base = 5.0 - risk_score * 0.035
    options_modifier = 0.45 if options_score >= 75 else 0.0
    size_modifier = current_weight * 0.05
    return round_pct(clamp(base + options_modifier + size_modifier, 1.0, 7.5))


def target_weight(score: float, risk_score: float, current_weight: float) -> float:
    if score < 58:
        return 0.0 if current_weight > 0 else 0.0
    score_weight = (score - 55.0) / 45.0 * 10.0
    risk_scale = clamp(risk_score / 70.0, 0.55, 1.2)
    target = score_weight * risk_scale
    if current_weight > 0 and score >= 70:
        target = max(target, min(current_weight, 10.0))
    return round_pct(clamp(target, 0.0, 10.0))


def recommendation_action(current_weight: float, recommended_weight: float, score: float) -> str:
    change = recommended_weight - current_weight
    if current_weight > 0 and score < 58:
        return "REMOVE"
    if current_weight == 0 and recommended_weight >= 2.0:
        return "ADD"
    if change >= 1.0:
        return "ADD"
    if change <= -1.0:
        return "TRIM"
    if recommended_weight > 0:
        return "HOLD"
    return "WATCH"


def build_feature_rows(
    data_dir: Path,
    portfolio_ids: list[str],
    run_id: str,
    run_date: str,
    goal_weekly_return_pct: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for portfolio_id in portfolio_ids:
        state = load_portfolio_state(data_dir, portfolio_id)["state"]
        current_weights = current_position_weights(state)
        positions = current_position_names(state)
        candidates_by_ticker = {row["ticker"]: row for row in load_candidates(data_dir, portfolio_id)}
        tickers = list(dict.fromkeys([*candidates_by_ticker.keys(), *current_weights.keys()]))
        for ticker in tickers[:40]:
            candidate = candidates_by_ticker.get(ticker)
            position = positions.get(ticker, {})
            if not candidate:
                candidate = {
                    "portfolio_id": portfolio_id,
                    "ticker": ticker,
                    "name": position.get("name") or position.get("company") or ticker,
                    "group": position.get("basket") or position.get("sector") or "",
                    "asset_type": position.get("asset_type", "stock"),
                    "score": as_float(position.get("paper_score") or position.get("web_score"), 50.0),
                    "trend_score": 50.0,
                    "risk_score": 50.0,
                    "sentiment_or_catalyst_score": 50.0,
                    "options_score": 50.0,
                    "source_notes": "",
                    "source_urls": "",
                    "thesis": position.get("thesis", ""),
                }
            current_weight = as_float(current_weights.get(ticker))
            score = as_float(candidate.get("score"), 50.0)
            trend = as_float(candidate.get("trend_score"), 50.0)
            risk = as_float(candidate.get("risk_score"), 50.0)
            sentiment = as_float(candidate.get("sentiment_or_catalyst_score"), 50.0)
            options = as_float(candidate.get("options_score"), 50.0)
            recommended_weight = target_weight(score, risk, current_weight)
            exp_return = expected_return(score, trend, sentiment)
            exp_risk = expected_risk(risk, options, current_weight)
            goal_contribution = round_pct(recommended_weight / 100.0 * exp_return)
            rows.append(
                {
                    "run_id": run_id,
                    "date": run_date,
                    "portfolio_id": portfolio_id,
                    "ticker": ticker,
                    "name": candidate.get("name", ticker),
                    "group": candidate.get("group", ""),
                    "asset_type": candidate.get("asset_type", "stock"),
                    "current_weight_pct": round_pct(current_weight),
                    "recommended_weight_pct": recommended_weight,
                    "score": round_pct(score),
                    "trend_score": round_pct(trend),
                    "risk_score": round_pct(risk),
                    "sentiment_or_catalyst_score": round_pct(sentiment),
                    "options_score": round_pct(options),
                    "expected_5d_return_pct": exp_return,
                    "ml_expected_5d_return_pct": "",
                    "prediction_source": "mechanical",
                    "ml_model_kind": "mechanical_fallback",
                    "expected_5d_risk_pct": exp_risk,
                    "goal_contribution_pct": goal_contribution,
                    "source_notes": candidate.get("source_notes", ""),
                    "source_urls": candidate.get("source_urls", ""),
                    "thesis": candidate.get("thesis", ""),
                    "forward_5d_return_pct": "",
                }
            )
    rows.sort(key=lambda row: (row["portfolio_id"], -float(row["score"])))
    return rows


def read_feature_history(output_dir: Path) -> list[dict[str, str]]:
    return read_csv(output_dir / "feature_history.csv")


def append_feature_history(output_dir: Path, feature_rows: list[dict[str, Any]], run_id: str) -> None:
    history_path = output_dir / "feature_history.csv"
    existing = [row for row in read_csv(history_path) if row.get("run_id") != run_id]
    write_csv(history_path, FEATURE_FIELDS, existing + feature_rows)


def bootstrap_anchor_date(run_date: str, calendar_days_back: int = 14) -> str:
    try:
        parsed = datetime.strptime(run_date, "%Y-%m-%d").date()
    except ValueError:
        return ""
    return (parsed - timedelta(days=calendar_days_back)).isoformat()


def bootstrap_ml_training_rows(data_dir: Path, feature_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seed_tickers = sorted({str(row.get("ticker", "")) for row in feature_rows if row.get("ticker")})
    tickers = select_training_universe_tickers(data_dir, seed_tickers=seed_tickers, min_price_rows=180, max_tickers=800)
    if not tickers:
        return []
    return build_price_history_training_rows(read_csv(data_dir / "raw_prices.csv"), tickers)


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def env_int_list(name: str, default: list[int]) -> list[int]:
    raw = os.environ.get(name, "")
    if not raw.strip():
        return default
    values: list[int] = []
    for item in raw.split(","):
        try:
            values.append(int(item.strip()))
        except ValueError:
            continue
    return values or default


def env_str_list(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def advanced_model_backtest_if_requested(data_dir: Path) -> dict[str, Any]:
    if not env_flag("USE_FOUNDATION_MODELS", False):
        return {
            "status": "disabled",
            "reason": "Set USE_FOUNDATION_MODELS=true to expose researched foundation-model candidates.",
        }
    if not env_flag("RUN_ADVANCED_MODEL_BACKTEST", False):
        return {
            "status": "configured_not_run",
            "reason": "Set RUN_ADVANCED_MODEL_BACKTEST=true to run optional local advanced-model inference.",
        }
    raw_price_rows = read_csv(data_dir / "raw_prices.csv")
    if not raw_price_rows:
        return {
            "status": "missing_price_history",
            "reason": "Advanced model backtests need data/raw_prices.csv.",
        }
    return run_advanced_price_backtest(
        raw_price_rows,
        specs=select_specs(env_str_list("ADVANCED_MODEL_KINDS") or ["chronos_2"]),
        context_lengths=env_int_list("ADVANCED_MODEL_CONTEXT_LENGTHS", [64, 128]),
        prediction_length=env_int("ADVANCED_MODEL_PREDICTION_LENGTH", 5),
        max_tickers=env_int("ADVANCED_MODEL_MAX_TICKERS", 30),
    )


def enrich_feature_rows_with_price_features(
    data_dir: Path,
    feature_rows: list[dict[str, Any]],
    as_of_date: str,
) -> list[dict[str, Any]]:
    tickers = sorted({str(row.get("ticker", "")) for row in feature_rows if row.get("ticker")})
    price_features = build_latest_price_feature_rows(read_csv(data_dir / "raw_prices.csv"), tickers, as_of_date)
    if not price_features:
        return feature_rows
    enriched = []
    for row in feature_rows:
        ticker = str(row.get("ticker", "")).upper()
        merged = dict(row)
        for key, value in price_features.get(ticker, {}).items():
            if key in {"date", "ticker", "score", "trend_score", "risk_score", "sentiment_or_catalyst_score", "options_score", "current_weight_pct"}:
                continue
            merged[key] = value
        enriched.append(merged)
    return enriched


def grouped_review_prices(raw_price_rows: list[dict[str, str]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in raw_price_rows:
        ticker = str(row.get("ticker", "")).upper()
        row_date = str(row.get("date", ""))
        price = as_float(row.get("adj_close") or row.get("close"))
        if ticker and row_date and price > 0:
            grouped.setdefault(ticker, []).append({"date": row_date, "price": price})
    for ticker, rows in grouped.items():
        grouped[ticker] = sorted(rows, key=lambda item: str(item["date"]))
    return grouped


def price_on_or_before(series: list[dict[str, Any]], target_date: str) -> dict[str, Any]:
    eligible = [row for row in series if str(row.get("date", "")) <= target_date]
    return eligible[-1] if eligible else {}


def pct_change(current: float, previous: float) -> float:
    if previous <= 0:
        return 0.0
    return round_pct((current / previous - 1.0) * 100.0)


def record_prior_decision_outcomes(data_dir: Path, journal_store: JournalStore, outcome_date: str) -> int:
    grouped = grouped_review_prices(read_csv(data_dir / "raw_prices.csv"))
    if not grouped:
        return 0
    benchmark_series = grouped.get("SPY") or grouped.get("QQQ") or []
    recorded = 0
    for decision in journal_store.decisions_missing_outcomes(outcome_date):
        ticker = str(decision.get("ticker", "")).upper()
        start = price_on_or_before(grouped.get(ticker, []), str(decision.get("run_date", "")))
        end = price_on_or_before(grouped.get(ticker, []), outcome_date)
        if not start or not end or start.get("date") == end.get("date"):
            continue
        realized = pct_change(as_float(end.get("price")), as_float(start.get("price")))
        benchmark_start = price_on_or_before(benchmark_series, str(decision.get("run_date", "")))
        benchmark_end = price_on_or_before(benchmark_series, outcome_date)
        benchmark = pct_change(as_float(benchmark_end.get("price")), as_float(benchmark_start.get("price"))) if benchmark_start and benchmark_end else 0.0
        action = str(decision.get("action", "")).upper()
        if action in {"TRIM", "REMOVE"}:
            target_hit = realized <= benchmark
        else:
            target_hit = realized >= benchmark
        journal_store.record_outcome(
            decision,
            outcome_date=outcome_date,
            horizon="review_to_review",
            realized_return_pct=realized,
            benchmark_return_pct=benchmark,
            target_hit=target_hit,
            payload={
                "start_date": start.get("date"),
                "start_price": start.get("price"),
                "end_date": end.get("date"),
                "end_price": end.get("price"),
                "benchmark_return_pct": benchmark,
                "action": action,
            },
        )
        recorded += 1
    return recorded


def build_recommendations(feature_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recommendations = []
    for row in feature_rows:
        current = as_float(row["current_weight_pct"])
        recommended = as_float(row["recommended_weight_pct"])
        score = as_float(row["score"], 50.0)
        action = recommendation_action(current, recommended, score)
        if action == "WATCH" and current == 0:
            continue
        weight_change = round_pct(recommended - current)
        confidence = round_pct(
            clamp(
                score * 0.45
                + as_float(row["trend_score"], 50.0) * 0.25
                + as_float(row["risk_score"], 50.0) * 0.20
                + as_float(row["options_score"], 50.0) * 0.10,
                0.0,
                100.0,
            )
        )
        prediction_source = str(row.get("prediction_source") or "mechanical")
        evidence = (
            f"score {score:.1f}, trend {as_float(row['trend_score'], 50.0):.1f}, "
            f"risk {as_float(row['risk_score'], 50.0):.1f}, "
            f"{prediction_source} expected 5d return {as_float(row['expected_5d_return_pct']):.2f}%."
        )
        intuition = (
            "Placeholder LLM/human intuition slot; no discretionary override applied. "
            "Use this field later for catalyst quality, narrative decay, and thesis drift."
        )
        recommendations.append(
            {
                "run_id": row["run_id"],
                "date": row["date"],
                "portfolio_id": row["portfolio_id"],
                "ticker": row["ticker"],
                "name": row["name"],
                "group": row["group"],
                "asset_type": row["asset_type"],
                "action": action,
                "decision_origin": "mechanical",
                "current_weight_pct": current,
                "recommended_weight_pct": recommended,
                "weight_change_pct": weight_change,
                "expected_5d_return_pct": row["expected_5d_return_pct"],
                "expected_5d_risk_pct": row["expected_5d_risk_pct"],
                "goal_contribution_pct": row["goal_contribution_pct"],
                "confidence_score": confidence,
                "model_version": MODEL_VERSION,
                "evidence_summary": evidence,
                "intuition_summary": intuition,
                "thesis": row["thesis"],
            }
        )
    recommendations.sort(key=lambda row: (row["portfolio_id"], row["action"] == "HOLD", -abs(float(row["weight_change_pct"]))))
    return recommendations


def portfolio_diagnostics(
    data_dir: Path,
    portfolio_ids: list[str],
    run_id: str,
    run_date: str,
    goal_weekly_return_pct: float,
) -> list[dict[str, Any]]:
    diagnostics = []
    for portfolio_id in portfolio_ids:
        loaded = load_portfolio_state(data_dir, portfolio_id)
        summary = loaded["summary"]
        weekly = as_float(summary.get("weekly_return_pct"))
        diagnostics.append(
            {
                "run_id": run_id,
                "date": run_date,
                "portfolio_id": portfolio_id,
                "portfolio_value": round_money(as_float(summary.get("capital"), 100000.0)),
                "gross_exposure_pct": round_pct(as_float(summary.get("gross_exposure_pct"))),
                "cash_reserve": round_money(as_float(summary.get("cash_reserve"))),
                "weekly_return_pct": round_pct(weekly),
                "target_weekly_return_pct": goal_weekly_return_pct,
                "target_gap_pct": round_pct(goal_weekly_return_pct - weekly),
                "position_count": len(loaded["positions"]),
            }
        )
    return diagnostics


def build_journal(
    run_id: str,
    run_date: str,
    recommendations: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    freshness: dict[str, Any],
    goal_weekly_return_pct: float,
) -> str:
    adds = [row for row in recommendations if row["action"] == "ADD"]
    trims = [row for row in recommendations if row["action"] in {"TRIM", "REMOVE"}]
    holds = [row for row in recommendations if row["action"] == "HOLD"]
    freshness_status = freshness.get("status", "unknown")
    lines = [
        f"# Portfolio Review Journal - {run_date}",
        "",
        f"- Run id: `{run_id}`",
        f"- Goal: `{goal_weekly_return_pct:.2f}%` weekly return",
        f"- Freshness status: `{freshness_status}`",
        f"- Mechanical model: `{MODEL_VERSION}`",
        "- LLM mode: `placeholder`",
        "",
        "## What Went Right - Evidence Based",
        "",
        f"- The engine found `{len(adds)}` add/increase candidates and `{len(holds)}` hold candidates based on score, trend, risk, and goal contribution.",
        "- Portfolio diagnostics and recommendation rows were written with model version and feature snapshot linkage.",
        "",
        "## What Went Wrong - Evidence Based",
        "",
        f"- `{len(trims)}` trim/remove candidates were flagged where current weights exceeded the mechanical target or score quality deteriorated.",
        f"- Freshness check status is `{freshness_status}`; missing or stale inputs should reduce confidence until refreshed.",
        "",
        "## What Went Right - Intuition",
        "",
        "- Placeholder only. No LLM or human discretionary view was allowed to change recommendations in this run.",
        "",
        "## What Went Wrong - Intuition",
        "",
        "- Placeholder only. Future LLM notes must distinguish narrative intuition from measured evidence.",
        "",
        "## Mechanical Recommendations",
        "",
    ]
    for row in recommendations[:12]:
        lines.append(
            f"- `{row['portfolio_id']}` `{row['ticker']}` {row['action']}: "
            f"{row['current_weight_pct']:.2f}% -> {row['recommended_weight_pct']:.2f}% "
            f"({row['evidence_summary']})"
        )
    lines.extend(
        [
            "",
            "## Goal Progress",
            "",
        ]
    )
    for row in diagnostics:
        lines.append(
            f"- `{row['portfolio_id']}` weekly return `{row['weekly_return_pct']:.2f}%`; "
            f"target gap `{row['target_gap_pct']:.2f}%`."
        )
    lines.extend(
        [
            "",
            "## Next Review Watchlist",
            "",
            "- Add historical feature labels as soon as enough future-return observations exist.",
            "- Promote only walk-forward validated models into mechanical recommendation authority.",
            "- Keep intuition-only recommendations separate until explicitly accepted by the user.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_review_outputs(
    output_dir: Path,
    run_id: str,
    payload: dict[str, Any],
    feature_rows: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    journal: str,
) -> dict[str, str]:
    run_dir = output_dir / "runs" / run_id
    files = {
        "run_manifest": str(run_dir / "run_manifest.json"),
        "freshness_report": str(run_dir / "freshness_report.json"),
        "feature_snapshot": str(run_dir / "feature_snapshot.csv"),
        "model_predictions": str(run_dir / "model_predictions.csv"),
        "portfolio_diagnostics": str(run_dir / "portfolio_diagnostics.csv"),
        "recommendations": str(run_dir / "recommendations.csv"),
        "decision_audit": str(run_dir / "decision_audit.csv"),
        "journal": str(run_dir / "journal.md"),
        "llm_context": str(run_dir / "llm_context.json"),
        "current_review": str(output_dir / "current_review.json"),
    }
    write_json(Path(files["run_manifest"]), payload)
    write_json(Path(files["freshness_report"]), payload["freshness"])
    write_csv(Path(files["feature_snapshot"]), FEATURE_FIELDS, feature_rows)
    write_csv(Path(files["model_predictions"]), FEATURE_FIELDS, feature_rows)
    write_csv(Path(files["portfolio_diagnostics"]), DIAGNOSTIC_FIELDS, diagnostics)
    write_csv(Path(files["recommendations"]), RECOMMENDATION_FIELDS, recommendations)
    write_csv(Path(files["decision_audit"]), RECOMMENDATION_FIELDS, recommendations)
    Path(files["journal"]).parent.mkdir(parents=True, exist_ok=True)
    Path(files["journal"]).write_text(journal)
    write_json(Path(files["llm_context"]), payload.get("llm_context", {}))
    write_json(Path(files["current_review"]), payload)
    return files


def run_portfolio_review(
    data_dir: Path = DATA_DIR,
    output_dir: Path = OUTPUT_DIR,
    run_id: str | None = None,
    run_date: str | None = None,
    goal_weekly_return_pct: float = 1.0,
    refresh_data: bool = False,
    portfolio_ids: list[str] | None = None,
) -> dict[str, Any]:
    run_date = run_date or date.today().isoformat()
    run_id = run_id or datetime.now(UTC).strftime("review_%Y%m%dT%H%M%SZ")
    portfolio_ids = portfolio_ids or ["app_metrics", "web_metrics"]
    portfolio_ids = [portfolio_id for portfolio_id in portfolio_ids if portfolio_id in PORTFOLIO_CONFIG]
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")

    refresh_result = refresh_data_if_requested(refresh_data, run_id)
    freshness = build_freshness_report(data_dir, refresh_data)
    freshness["performed"] = refresh_result["performed"]
    freshness["refresh_return_code"] = refresh_result["return_code"]
    freshness["refresh_error"] = refresh_result["error"]
    freshness["refresh_log_tail"] = refresh_result["log_tail"]
    feature_rows = build_feature_rows(data_dir, portfolio_ids, run_id, run_date, goal_weekly_return_pct)
    feature_rows = enrich_feature_rows_with_price_features(data_dir, feature_rows, run_date)
    use_ml = env_flag("USE_ML", True)
    if use_ml:
        historical_training_rows = read_feature_history(output_dir)
        price_training_rows = bootstrap_ml_training_rows(data_dir, feature_rows)
        ml_training_rows = historical_training_rows + price_training_rows
        ml_result = build_ml_predictions(feature_rows, ml_training_rows)
        feature_rows = ml_result.pop("predictions")
        ml_result["foundation_model_candidates"] = foundation_model_candidates()
        ml_result["advanced_model_backtest"] = advanced_model_backtest_if_requested(data_dir)
        ml_result["model_lab_summary"] = summarize_tournament(ml_result.get("recent_holdout_tournament", []))
        ml_result["model_lab_note"] = (
            "Models are tournament candidates only. Recommendation authority requires positive broad "
            "walk-forward and recent anchored holdout validation."
        )
        if price_training_rows and ml_result["status"] == "trained":
            ml_result["training_source"] = "raw_price_history_bootstrap"
            ml_result["bootstrap_training_rows"] = len(price_training_rows)
            ml_result["bootstrap_anchor_date"] = bootstrap_anchor_date(run_date)
            ml_result["bootstrap_anchor_rows"] = sum(
                1 for row in price_training_rows if row.get("date") == ml_result["bootstrap_anchor_date"]
            )
            ml_result["anchor_backtest"] = run_anchor_backtest(price_training_rows, ml_result["bootstrap_anchor_date"])
        elif price_training_rows:
            ml_result["training_source"] = "raw_price_history_bootstrap"
            ml_result["bootstrap_training_rows"] = len(price_training_rows)
            ml_result["bootstrap_anchor_date"] = bootstrap_anchor_date(run_date)
            ml_result["bootstrap_anchor_rows"] = sum(
                1 for row in price_training_rows if row.get("date") == ml_result["bootstrap_anchor_date"]
            )
            ml_result["anchor_backtest"] = run_anchor_backtest(price_training_rows, ml_result["bootstrap_anchor_date"])
        else:
            ml_result["training_source"] = "review_feature_history"
    else:
        ml_result = {
            "status": "disabled",
            "model_kind": "mechanical_fallback",
            "labeled_rows": 0,
            "min_train_rows": 0,
            "walk_forward": {},
        }
    llm_config = load_llm_config()
    recommendations = build_recommendations(feature_rows)
    diagnostics = portfolio_diagnostics(data_dir, portfolio_ids, run_id, run_date, goal_weekly_return_pct)
    journal_store = JournalStore(output_dir / "journal.db")
    journal_store.initialize()
    outcomes_recorded = record_prior_decision_outcomes(data_dir, journal_store, run_date)
    journal_memory = journal_store.build_memory()
    goal_payload = {
        "weekly_return_pct": goal_weekly_return_pct,
        "weekly_return_dollars_on_100k": round_money(100000.0 * goal_weekly_return_pct / 100.0),
    }
    llm_context = build_portfolio_review_llm_context(
        run_id=run_id,
        run_date=run_date,
        goal=goal_payload,
        ml_result=ml_result,
        feature_rows=feature_rows,
        recommendations=recommendations,
        diagnostics=diagnostics,
        freshness=freshness,
        journal_memory=journal_memory,
    )
    if llm_config["enabled"]:
        llm_review = call_openai_json(build_llm_review_prompt(llm_context), schema_name="portfolio_review_journal_v1")
    else:
        llm_review = {
            "enabled": False,
            "used": False,
            "model": llm_config["model"],
            "result": {},
            "error": "LLM disabled. Set USE_LLM=true and OPENAI_API_KEY to enable testing.",
        }
    journal = build_journal(run_id, run_date, recommendations, diagnostics, freshness, goal_weekly_return_pct)
    append_feature_history(output_dir, feature_rows, run_id)

    payload: dict[str, Any] = {
        "run_id": run_id,
        "generated_at": generated_at,
        "date": run_date,
        "model_version": MODEL_VERSION,
        "goal": goal_payload,
        "refresh": {
            "requested": refresh_data,
            "performed": refresh_result["performed"],
            "return_code": refresh_result["return_code"],
            "command": refresh_result["command"],
            "error": refresh_result["error"],
            "note": "When requested, the workflow runs run_pipeline.py before scoring; if refresh fails, recommendations still record the stale/freshness evidence.",
        },
        "llm": {
            **llm_config,
            "mode": "enabled" if llm_config["enabled"] else "disabled",
            "note": "LLM is constrained to CSV extraction, evidence summaries, and intuition-labeled journal context; it does not independently pick stocks.",
            "review": llm_review,
        },
        "ml": {"enabled": use_ml, **ml_result},
        "llm_context": llm_context,
        "portfolios": portfolio_ids,
        "freshness": freshness,
        "diagnostics": diagnostics,
        "recommendations": recommendations,
        "top_recommendations": recommendations[:10],
        "journal_preview": journal.splitlines()[:40],
    }
    files = write_review_outputs(output_dir, run_id, payload, feature_rows, recommendations, diagnostics, journal)
    payload["files"] = files
    journal_store.record_review(payload, recommendations, diagnostics, llm_context, llm_review)
    payload["journal_ledger"] = {
        "db_path": str(journal_store.path),
        "schema_version": JOURNAL_SCHEMA_VERSION,
        "recorded": True,
        "outcomes_recorded": outcomes_recorded,
        "memory_counts": {
            "recent_learnings": len(journal_store.recent_learnings(limit=100)),
            "recent_entries": len(journal_store.recent_journal_entries(limit=100)),
            "recent_decisions": len(journal_store.decision_history(limit=100)),
            "recent_outcomes": len(journal_store.recent_outcomes(limit=100)),
        },
    }
    write_json(Path(files["run_manifest"]), payload)
    write_json(Path(files["current_review"]), payload)
    write_json(output_dir / "current_review.json", payload)
    return payload


def load_current_review(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    return read_json(output_dir / "current_review.json")


def run_portfolio_review_api(
    payload: dict[str, Any],
    data_dir: Path = DATA_DIR,
    output_dir: Path = OUTPUT_DIR,
) -> dict[str, Any]:
    goal = as_float(payload.get("goalWeeklyReturnPct"), 1.0)
    portfolio_ids = payload.get("portfolioIds") or ["app_metrics", "web_metrics"]
    if not isinstance(portfolio_ids, list):
        portfolio_ids = ["app_metrics", "web_metrics"]
    run_id = payload.get("runId")
    run_date = payload.get("runDate")
    return run_portfolio_review(
        data_dir=data_dir,
        output_dir=output_dir,
        run_id=str(run_id) if run_id else None,
        run_date=str(run_date) if run_date else None,
        goal_weekly_return_pct=goal,
        refresh_data=bool(payload.get("refreshData")),
        portfolio_ids=[str(item) for item in portfolio_ids],
    )


def main() -> int:
    result = run_portfolio_review()
    print(f"Wrote portfolio review {result['run_id']} for {result['date']}")
    for label, path in result["files"].items():
        print(f"- {label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
