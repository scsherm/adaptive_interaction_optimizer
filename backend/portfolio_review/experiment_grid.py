from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sklearn.base import clone
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import ElasticNet, HuberRegressor, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler, StandardScaler

from portfolio_review.ml_models import (
    PositiveReturnClassifier,
    aggregate_anchor_results,
    as_float,
    build_price_history_training_rows,
    evaluate_model_on_anchor,
    performance_gate,
    recent_anchor_dates,
    score_recent_holdout_result,
)
from portfolio_review.training_dataset import select_training_universe_tickers


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = DATA_DIR / "portfolio_review"


@dataclass(frozen=True)
class SupervisedCandidate:
    model_kind: str
    family: str
    estimator: Any
    params: dict[str, Any]
    research_basis: str


def package_available(package_name: str) -> bool:
    return importlib.util.find_spec(package_name) is not None


def candidate_name(prefix: str, **params: Any) -> str:
    suffix = "_".join(f"{key}_{value}" for key, value in params.items())
    return f"{prefix}_{suffix}" if suffix else prefix


def supervised_model_grid(include_optional: bool = True, profile: str = "balanced") -> list[SupervisedCandidate]:
    candidates: list[SupervisedCandidate] = []
    ridge_alphas = [0.1, 1, 3, 10, 30, 100] if profile != "small" else [1, 10, 30]
    for alpha in ridge_alphas:
        candidates.append(
            SupervisedCandidate(
                model_kind=f"ridge_alpha_{alpha:g}",
                family="linear_regularized",
                estimator=make_pipeline(StandardScaler(), Ridge(alpha=alpha)),
                params={"alpha": alpha, "scaler": "standard"},
                research_basis="Regularized linear baseline for noisy cross-sectional return prediction.",
            )
        )

    if profile != "small":
        for alpha in [0.001, 0.01, 0.05]:
            for l1_ratio in [0.15, 0.5, 0.85]:
                candidates.append(
                    SupervisedCandidate(
                        model_kind=candidate_name("elastic_net", alpha=alpha, l1=l1_ratio),
                        family="linear_regularized",
                        estimator=make_pipeline(
                            StandardScaler(),
                            ElasticNet(alpha=alpha, l1_ratio=l1_ratio, max_iter=20000, random_state=19),
                        ),
                        params={"alpha": alpha, "l1_ratio": l1_ratio, "scaler": "standard"},
                        research_basis="Sparse/regularized linear model used as an interpretable return-prediction baseline.",
                    )
                )
        for epsilon in [1.35, 1.75]:
            for alpha in [0.0001, 0.001]:
                candidates.append(
                    SupervisedCandidate(
                        model_kind=candidate_name("huber", eps=epsilon, alpha=alpha),
                        family="linear_robust",
                        estimator=make_pipeline(RobustScaler(), HuberRegressor(epsilon=epsilon, alpha=alpha, max_iter=1000)),
                        params={"epsilon": epsilon, "alpha": alpha, "scaler": "robust"},
                        research_basis="Robust regression candidate to reduce impact of fat-tailed stock-return outliers.",
                    )
                )

    rf_depths = [5, 8] if profile == "small" else [4, 7, 10]
    rf_leafs = [6] if profile == "small" else [5, 10]
    for depth in rf_depths:
        for leaf in rf_leafs:
            candidates.append(
                SupervisedCandidate(
                    model_kind=candidate_name("random_forest", depth=depth, leaf=leaf),
                    family="tree_ensemble",
                    estimator=RandomForestRegressor(
                        n_estimators=120,
                        random_state=17,
                        min_samples_leaf=leaf,
                        max_depth=depth,
                        n_jobs=-1,
                    ),
                    params={"n_estimators": 120, "max_depth": depth, "min_samples_leaf": leaf},
                    research_basis="Nonlinear ensemble baseline common in empirical asset-pricing ML comparisons.",
                )
            )

    et_depths = [8] if profile == "small" else [5, 8, 12]
    et_leafs = [8] if profile == "small" else [4, 8, 12]
    for depth in et_depths:
        for leaf in et_leafs:
            candidates.append(
                SupervisedCandidate(
                    model_kind=candidate_name("extra_trees", depth=depth, leaf=leaf),
                    family="tree_ensemble",
                    estimator=ExtraTreesRegressor(
                        n_estimators=160,
                        random_state=31,
                        min_samples_leaf=leaf,
                        max_depth=depth,
                        n_jobs=-1,
                    ),
                    params={"n_estimators": 160, "max_depth": depth, "min_samples_leaf": leaf},
                    research_basis="Randomized tree ensemble candidate for nonlinear cross-sectional interactions.",
                )
            )

    hgb_params = [(0.05, 12, 0.8)] if profile == "small" else [
        (0.03, 8, 0.2),
        (0.03, 16, 0.8),
        (0.05, 12, 0.8),
        (0.06, 16, 0.2),
        (0.10, 8, 1.5),
        (0.10, 24, 1.0),
    ]
    for learning_rate, leaves, l2 in hgb_params:
        candidates.append(
            SupervisedCandidate(
                model_kind=candidate_name("hist_gradient", lr=learning_rate, leaf=leaves, l2=l2),
                family="gradient_boosting",
                estimator=HistGradientBoostingRegressor(
                    random_state=29,
                    learning_rate=learning_rate,
                    max_iter=160,
                    max_leaf_nodes=leaves,
                    l2_regularization=l2,
                ),
                params={"learning_rate": learning_rate, "max_leaf_nodes": leaves, "l2_regularization": l2, "max_iter": 160},
                research_basis="Gradient boosting is a strong tabular baseline; regularization is swept to control overfit.",
            )
        )

    classifier_params = [(0.05, 12, 12.0)] if profile == "small" else [(0.03, 8, 10.0), (0.05, 12, 12.0), (0.08, 16, 14.0)]
    for learning_rate, leaves, scale in classifier_params:
        candidates.append(
            SupervisedCandidate(
                model_kind=candidate_name("hgb_positive_classifier", lr=learning_rate, leaf=leaves, scale=scale),
                family="direction_classifier",
                estimator=PositiveReturnClassifier(
                    HistGradientBoostingClassifier(
                        random_state=47,
                        learning_rate=learning_rate,
                        max_iter=160,
                        max_leaf_nodes=leaves,
                        l2_regularization=0.8,
                    ),
                    scale=scale,
                ),
                params={"learning_rate": learning_rate, "max_leaf_nodes": leaves, "scale": scale},
                research_basis="Directional classifier tests sign prediction separately from return magnitude.",
            )
        )

    if include_optional:
        candidates.extend(optional_supervised_candidates(profile=profile))
    return candidates


def optional_supervised_candidates(profile: str = "balanced") -> list[SupervisedCandidate]:
    candidates: list[SupervisedCandidate] = []
    if package_available("xgboost"):
        from xgboost import XGBClassifier, XGBRegressor

        xgb_params = [(0.03, 2, 0.8), (0.05, 3, 0.9)] if profile != "small" else [(0.05, 3, 0.9)]
        for learning_rate, depth, subsample in xgb_params:
            candidates.append(
                SupervisedCandidate(
                    model_kind=candidate_name("xgboost", lr=learning_rate, depth=depth, subsample=subsample),
                    family="gradient_boosting_optional",
                    estimator=XGBRegressor(
                        n_estimators=220,
                        learning_rate=learning_rate,
                        max_depth=depth,
                        subsample=subsample,
                        colsample_bytree=0.85,
                        reg_lambda=5.0,
                        objective="reg:squarederror",
                        random_state=53,
                        n_jobs=2,
                    ),
                    params={"n_estimators": 220, "learning_rate": learning_rate, "max_depth": depth, "subsample": subsample},
                    research_basis="XGBoost is a widely used tuned GBDT baseline for high-dimensional tabular prediction.",
                )
            )
            candidates.append(
                SupervisedCandidate(
                    model_kind=candidate_name("xgboost_positive_classifier", lr=learning_rate, depth=depth),
                    family="direction_classifier_optional",
                    estimator=PositiveReturnClassifier(
                        XGBClassifier(
                            n_estimators=220,
                            learning_rate=learning_rate,
                            max_depth=depth,
                            subsample=subsample,
                            colsample_bytree=0.85,
                            reg_lambda=5.0,
                            objective="binary:logistic",
                            eval_metric="logloss",
                            random_state=59,
                            n_jobs=2,
                        ),
                        scale=12.0,
                    ),
                    params={"n_estimators": 220, "learning_rate": learning_rate, "max_depth": depth, "subsample": subsample},
                    research_basis="XGBoost classifier checks whether directional edge is stronger than magnitude regression.",
                )
            )
    if package_available("lightgbm"):
        from lightgbm import LGBMClassifier, LGBMRegressor

        lgbm_params = [(0.03, 15, 10), (0.06, 31, 20)] if profile != "small" else [(0.06, 31, 20)]
        for learning_rate, leaves, min_child in lgbm_params:
            candidates.append(
                SupervisedCandidate(
                    model_kind=candidate_name("lightgbm", lr=learning_rate, leaves=leaves, child=min_child),
                    family="gradient_boosting_optional",
                    estimator=LGBMRegressor(
                        n_estimators=240,
                        learning_rate=learning_rate,
                        num_leaves=leaves,
                        min_child_samples=min_child,
                        subsample=0.85,
                        colsample_bytree=0.85,
                        reg_lambda=5.0,
                        random_state=61,
                        n_jobs=2,
                        verbosity=-1,
                    ),
                    params={"n_estimators": 240, "learning_rate": learning_rate, "num_leaves": leaves, "min_child_samples": min_child},
                    research_basis="LightGBM is a fast GBDT baseline often competitive on tabular forecasting features.",
                )
            )
            candidates.append(
                SupervisedCandidate(
                    model_kind=candidate_name("lightgbm_positive_classifier", lr=learning_rate, leaves=leaves),
                    family="direction_classifier_optional",
                    estimator=PositiveReturnClassifier(
                        LGBMClassifier(
                            n_estimators=240,
                            learning_rate=learning_rate,
                            num_leaves=leaves,
                            min_child_samples=min_child,
                            subsample=0.85,
                            colsample_bytree=0.85,
                            reg_lambda=5.0,
                            random_state=67,
                            n_jobs=2,
                            verbosity=-1,
                        ),
                        scale=12.0,
                    ),
                    params={"n_estimators": 240, "learning_rate": learning_rate, "num_leaves": leaves},
                    research_basis="LightGBM classifier tests pure directional classification with tree boosting.",
                )
            )
    if package_available("catboost"):
        from catboost import CatBoostRegressor

        cb_params = [(0.03, 4), (0.06, 6)] if profile != "small" else [(0.06, 4)]
        for learning_rate, depth in cb_params:
            candidates.append(
                SupervisedCandidate(
                    model_kind=candidate_name("catboost", lr=learning_rate, depth=depth),
                    family="gradient_boosting_optional",
                    estimator=CatBoostRegressor(
                        iterations=220,
                        learning_rate=learning_rate,
                        depth=depth,
                        l2_leaf_reg=8.0,
                        loss_function="RMSE",
                        random_seed=71,
                        verbose=False,
                        allow_writing_files=False,
                    ),
                    params={"iterations": 220, "learning_rate": learning_rate, "depth": depth, "l2_leaf_reg": 8.0},
                    research_basis="CatBoost is included as another robust GBDT implementation with different tree construction.",
                )
            )
    if package_available("tabpfn") and profile == "exhaustive":
        from tabpfn import TabPFNRegressor

        candidates.append(
            SupervisedCandidate(
                model_kind="tabpfn_regressor_cpu_estimators_4",
                family="foundation_tabular_optional",
                estimator=TabPFNRegressor(n_estimators=4, device="cpu", random_state=73, show_progress_bar=False),
                params={"n_estimators": 4, "device": "cpu"},
                research_basis="TabPFN is tested only in exhaustive mode because it is heavier and has training-size limits.",
            )
        )
    return candidates


def candidate_to_metadata(candidate: SupervisedCandidate) -> dict[str, Any]:
    data = asdict(candidate)
    data.pop("estimator", None)
    return data


def evaluate_candidate(
    rows: list[dict[str, Any]],
    candidate: SupervisedCandidate,
    anchor_dates: list[str],
    min_train_rows: int,
    max_train_rows: int,
) -> dict[str, Any]:
    anchor_results: list[dict[str, Any]] = []
    for anchor_date in anchor_dates:
        try:
            result = evaluate_model_on_anchor(
                candidate.model_kind,
                clone(candidate.estimator),
                rows,
                anchor_date,
                min_train_rows=min_train_rows,
                max_train_rows=max_train_rows,
            )
        except Exception as exc:
            return {
                **candidate_to_metadata(candidate),
                "status": "runtime_error",
                "authority": "none",
                "reason": str(exc),
                "anchors_tested": 0,
            }
        anchor_results.append(result)
    aggregate = aggregate_anchor_results(candidate.model_kind, anchor_results)
    if aggregate.get("status") != "tested":
        return {
            **candidate_to_metadata(candidate),
            **aggregate,
            "authority": "none",
        }
    gate = performance_gate(aggregate)
    return {
        **candidate_to_metadata(candidate),
        **aggregate,
        "authority": "eligible" if gate["passed"] else "rejected_by_validation",
        "performance_gate": gate,
        "score": score_result(aggregate),
    }


def score_result(result: dict[str, Any]) -> float:
    score_tuple = score_recent_holdout_result(result)
    return round(
        score_tuple[0] * 1000
        + score_tuple[1] * 20
        + score_tuple[2] * 100
        + score_tuple[3] * 10
        + score_tuple[4] * 0.1,
        6,
    )


def sort_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        results,
        key=lambda row: (
            1 if row.get("status") == "tested" else 0,
            1 if row.get("authority") == "eligible" else 0,
            as_float(row.get("score"), -99999.0),
            as_float(row.get("long_short_spread"), -99999.0),
        ),
        reverse=True,
    )


def compact_leaderboard(rows: list[dict[str, Any]], limit: int = 25) -> list[dict[str, Any]]:
    return sort_results(rows)[:limit]


def run_supervised_grid(
    rows: list[dict[str, Any]],
    candidates: list[SupervisedCandidate] | None = None,
    anchor_dates: list[str] | None = None,
    max_train_rows: int = 6000,
    min_train_rows: int = 30,
    profile: str = "balanced",
    include_optional: bool = True,
) -> dict[str, Any]:
    candidates = candidates or supervised_model_grid(include_optional=include_optional, profile=profile)
    anchor_dates = anchor_dates or recent_anchor_dates(rows, count=4, spacing=5, min_holdout_rows=50)
    results = [
        evaluate_candidate(rows, candidate, anchor_dates, min_train_rows=min_train_rows, max_train_rows=max_train_rows)
        for candidate in candidates
    ]
    tested = [row for row in results if row.get("status") == "tested"]
    eligible = [row for row in tested if row.get("authority") == "eligible"]
    sorted_results = sort_results(results)
    best = sorted_results[0] if sorted_results and sorted_results[0].get("status") == "tested" else {}
    return {
        "status": "tested" if tested else "not_tested",
        "candidate_count": len(candidates),
        "tested_count": len(tested),
        "eligible_count": len(eligible),
        "anchor_dates": anchor_dates,
        "max_train_rows": max_train_rows,
        "min_train_rows": min_train_rows,
        "best_model": best.get("model_kind", ""),
        "best_authority": best.get("authority", "none") if best else "none",
        "leaderboard": compact_leaderboard(results, limit=len(results)),
        "candidate_results": results,
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = [
        "rank",
        "model_kind",
        "family",
        "status",
        "authority",
        "anchors_tested",
        "mae",
        "directional_accuracy",
        "rank_ic",
        "top_bucket_actual_return",
        "bottom_bucket_actual_return",
        "long_short_spread",
        "score",
        "params",
        "research_basis",
        "reason",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for rank, row in enumerate(sort_results(rows), start=1):
            out = dict(row)
            out["rank"] = rank
            out["params"] = json.dumps(out.get("params", {}), sort_keys=True)
            writer.writerow(out)


def build_training_rows_from_data_dir(data_dir: Path, max_tickers: int = 800) -> list[dict[str, Any]]:
    tickers = select_training_universe_tickers(data_dir, seed_tickers=[], min_price_rows=180, max_tickers=max_tickers)
    raw_rows = read_csv(data_dir / "raw_prices.csv")
    return build_price_history_training_rows(raw_rows, tickers)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run model-selection grids for portfolio review ML.")
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument("--output", default=str(OUTPUT_DIR / "supervised_model_grid.json"))
    parser.add_argument("--csv-output", default=str(OUTPUT_DIR / "supervised_model_grid.csv"))
    parser.add_argument("--profile", choices=["small", "balanced", "exhaustive"], default="balanced")
    parser.add_argument("--no-optional", action="store_true")
    parser.add_argument("--max-train-rows", type=int, default=6000)
    parser.add_argument("--min-train-rows", type=int, default=30)
    parser.add_argument("--max-tickers", type=int, default=800)
    parser.add_argument("--anchors", default="")
    parser.add_argument("--limit-candidates", type=int, default=0)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    rows = build_training_rows_from_data_dir(data_dir, max_tickers=args.max_tickers)
    candidates = supervised_model_grid(include_optional=not args.no_optional, profile=args.profile)
    if args.limit_candidates > 0:
        candidates = candidates[: args.limit_candidates]
    anchor_dates = [item.strip() for item in args.anchors.split(",") if item.strip()] or None
    result = run_supervised_grid(
        rows,
        candidates=candidates,
        anchor_dates=anchor_dates,
        max_train_rows=args.max_train_rows,
        min_train_rows=args.min_train_rows,
        profile=args.profile,
        include_optional=not args.no_optional,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2))
    write_csv(Path(args.csv_output), result["candidate_results"])
    print(json.dumps({key: result[key] for key in ["status", "candidate_count", "tested_count", "eligible_count", "best_model", "best_authority"]}, indent=2))
    print(f"Wrote {output}")
    print(f"Wrote {args.csv_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
