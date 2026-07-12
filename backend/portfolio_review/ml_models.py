from __future__ import annotations

import math
from statistics import pstdev
from typing import Any

from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


FEATURE_COLUMNS = [
    "score",
    "trend_score",
    "risk_score",
    "price_score",
    "price_trend_score",
    "price_risk_score",
    "sentiment_or_catalyst_score",
    "options_score",
    "current_weight_pct",
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
]
LABEL_COLUMN = "forward_5d_return_pct"


class PositiveReturnClassifier(BaseEstimator, RegressorMixin):
    def __init__(self, estimator: Any, scale: float = 12.0) -> None:
        self.estimator = estimator
        self.scale = scale

    def fit(self, x: list[list[float]], y: list[float]) -> "PositiveReturnClassifier":
        self.estimator_ = clone(self.estimator)
        labels_binary = [1 if value > 0 else 0 for value in y]
        self.estimator_.fit(x, labels_binary)
        return self

    def predict(self, x: list[list[float]]) -> list[float]:
        if hasattr(self.estimator_, "predict_proba"):
            probabilities = self.estimator_.predict_proba(x)
            positive_index = list(self.estimator_.classes_).index(1) if 1 in self.estimator_.classes_ else -1
            if positive_index >= 0:
                return [round((float(row[positive_index]) - 0.5) * self.scale, 4) for row in probabilities]
        raw = self.estimator_.predict(x)
        return [round((float(value) - 0.5) * self.scale, 4) for value in raw]


def as_float(value: Any, default: float = 0.0) -> float:
    if value in {"", None}:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def has_label(row: dict[str, Any]) -> bool:
    value = row.get(LABEL_COLUMN)
    if value in {"", None}:
        return False
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def matrix(rows: list[dict[str, Any]]) -> list[list[float]]:
    return [[as_float(row.get(column)) for column in FEATURE_COLUMNS] for row in rows]


def labels(rows: list[dict[str, Any]]) -> list[float]:
    return [as_float(row.get(LABEL_COLUMN)) for row in rows]


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def pct_return(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return (current / previous - 1.0) * 100.0


def score_from_return(value: float, scale: float) -> float:
    return clamp(50.0 + value * scale)


def moving_average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def annualized_vol_pct(values: list[float]) -> float:
    returns = []
    for index in range(1, len(values)):
        previous = values[index - 1]
        if previous:
            returns.append(values[index] / previous - 1.0)
    if len(returns) < 3:
        return 0.0
    return pstdev(returns) * math.sqrt(252) * 100.0


def max_drawdown_pct(values: list[float]) -> float:
    high = values[0] if values else 0.0
    worst = 0.0
    for value in values:
        high = max(high, value)
        if high:
            worst = min(worst, (value / high - 1.0) * 100.0)
    return worst


def grouped_price_series(raw_price_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in raw_price_rows:
        ticker = str(row.get("ticker", "")).upper()
        price = as_float(row.get("adj_close") or row.get("close"))
        date = str(row.get("date", ""))
        if not date or price <= 0:
            continue
        grouped.setdefault(ticker, []).append(
            {
                "date": date,
                "price": price,
                "volume": as_float(row.get("volume")),
            }
        )
    for ticker, series in grouped.items():
        grouped[ticker] = sorted(series, key=lambda item: str(item["date"]))
    return grouped


def series_price(series: list[dict[str, Any]], index: int) -> float:
    if index < 0 or index >= len(series):
        return 0.0
    return as_float(series[index].get("price"))


def return_over(series: list[dict[str, Any]], index: int, days: int) -> float:
    if index - days < 0:
        return 0.0
    return pct_return(series_price(series, index), series_price(series, index - days))


def average_volume(series: list[dict[str, Any]], start: int, end: int) -> float:
    values = [as_float(row.get("volume")) for row in series[max(0, start) : max(0, end)] if as_float(row.get("volume")) > 0]
    return moving_average(values)


def rolling_values(series: list[dict[str, Any]], index: int, days: int) -> list[float]:
    if index - days + 1 < 0:
        return []
    return [as_float(row.get("price")) for row in series[index - days + 1 : index + 1]]


def benchmark_return(benchmark_by_date: dict[str, dict[str, Any]], start_date: str, end_date: str) -> float:
    start = benchmark_by_date.get(start_date)
    end = benchmark_by_date.get(end_date)
    if not start or not end:
        return 0.0
    return pct_return(as_float(end.get("price")), as_float(start.get("price")))


def aligned_daily_returns(
    series: list[dict[str, Any]],
    benchmark_by_date: dict[str, dict[str, Any]],
    index: int,
    days: int,
) -> tuple[list[float], list[float]]:
    stock_returns: list[float] = []
    benchmark_returns: list[float] = []
    start = max(1, index - days + 1)
    for cursor in range(start, index + 1):
        current = series[cursor]
        previous = series[cursor - 1]
        current_benchmark = benchmark_by_date.get(str(current.get("date", "")))
        previous_benchmark = benchmark_by_date.get(str(previous.get("date", "")))
        if not current_benchmark or not previous_benchmark:
            continue
        stock_returns.append(pct_return(as_float(current.get("price")), as_float(previous.get("price"))))
        benchmark_returns.append(pct_return(as_float(current_benchmark.get("price")), as_float(previous_benchmark.get("price"))))
    return stock_returns, benchmark_returns


def covariance(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    return sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / len(xs)


def beta_to_benchmark(stock_returns: list[float], benchmark_returns: list[float]) -> float:
    variance = covariance(benchmark_returns, benchmark_returns)
    if not variance:
        return 0.0
    return covariance(stock_returns, benchmark_returns) / variance


def percentile_rank(values: list[float], value: float) -> float:
    if len(values) < 2:
        return 0.5
    less_or_equal = sum(1 for item in values if item <= value)
    return round((less_or_equal - 1) / (len(values) - 1), 4)


def add_cross_sectional_ranks(rows: list[dict[str, Any]]) -> None:
    by_date: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_date.setdefault(str(row.get("date", "")), []).append(row)
    rank_fields = [
        ("momentum_20d_pct", "cross_section_momentum_20d_rank"),
        ("relative_momentum_20d_pct", "cross_section_relative_momentum_20d_rank"),
        ("volatility_20d_pct", "cross_section_volatility_20d_rank"),
        ("drawdown_20d_pct", "cross_section_drawdown_20d_rank"),
        ("volume_ratio_5_20", "cross_section_volume_ratio_rank"),
    ]
    for date_rows in by_date.values():
        for source, target in rank_fields:
            values = [as_float(row.get(source)) for row in date_rows]
            for row in date_rows:
                row[target] = percentile_rank(values, as_float(row.get(source)))


def price_feature_row(
    ticker: str,
    series: list[dict[str, Any]],
    index: int,
    benchmark_series: list[dict[str, Any]],
    benchmark_by_date: dict[str, dict[str, Any]],
    forward_days: int = 5,
    include_label: bool = True,
) -> dict[str, Any] | None:
    if index < 1 or index >= len(series):
        return None
    date_value = str(series[index].get("date", ""))
    current = series_price(series, index)
    if current <= 0:
        return None
    ret_1 = return_over(series, index, 1)
    ret_5 = return_over(series, index, 5)
    ret_10 = return_over(series, index, 10)
    ret_20 = return_over(series, index, 20)
    ret_40 = return_over(series, index, 40)
    ret_60 = return_over(series, index, 60)
    ma_10 = moving_average(rolling_values(series, index, 10))
    ma_20 = moving_average(rolling_values(series, index, 20))
    ma_50 = moving_average(rolling_values(series, index, 50))
    vol_10 = annualized_vol_pct(rolling_values(series, index, 10))
    vol_20 = annualized_vol_pct(rolling_values(series, index, 20))
    vol_60 = annualized_vol_pct(rolling_values(series, index, 60))
    drawdown_20 = abs(max_drawdown_pct(rolling_values(series, index, 20)))
    drawdown_60 = abs(max_drawdown_pct(rolling_values(series, index, 60)))
    avg_volume_5 = average_volume(series, index - 4, index + 1)
    avg_volume_20 = average_volume(series, index - 19, index + 1)
    volume_ratio = avg_volume_5 / avg_volume_20 if avg_volume_20 else 1.0
    benchmark_index_by_date = {str(row.get("date", "")): cursor for cursor, row in enumerate(benchmark_series)}
    benchmark_index = benchmark_index_by_date.get(date_value, -1)
    benchmark_ret_5 = return_over(benchmark_series, benchmark_index, 5) if benchmark_index >= 0 else 0.0
    benchmark_ret_20 = return_over(benchmark_series, benchmark_index, 20) if benchmark_index >= 0 else 0.0
    benchmark_ret_60 = return_over(benchmark_series, benchmark_index, 60) if benchmark_index >= 0 else 0.0
    stock_20, bench_20 = aligned_daily_returns(series, benchmark_by_date, index, 20)
    stock_60, bench_60 = aligned_daily_returns(series, benchmark_by_date, index, 60)
    score = score_from_return(ret_5 * 0.25 + ret_20 * 0.45 + (ret_20 - benchmark_ret_20) * 0.30, 1.8)
    trend = score_from_return(ret_5 * 0.20 + ret_20 * 0.35 + ret_60 * 0.25 + (ret_20 - benchmark_ret_20) * 0.20, 2.0)
    risk = clamp(100.0 - vol_20 * 0.45 - drawdown_20 * 1.4)
    row: dict[str, Any] = {
        "date": date_value,
        "ticker": ticker,
        "score": round(score, 4),
        "trend_score": round(trend, 4),
        "risk_score": round(risk, 4),
        "price_score": round(score, 4),
        "price_trend_score": round(trend, 4),
        "price_risk_score": round(risk, 4),
        "sentiment_or_catalyst_score": 50.0,
        "options_score": 50.0,
        "current_weight_pct": 0.0,
        "momentum_1d_pct": round(ret_1, 4),
        "momentum_5d_pct": round(ret_5, 4),
        "momentum_10d_pct": round(ret_10, 4),
        "momentum_20d_pct": round(ret_20, 4),
        "momentum_40d_pct": round(ret_40, 4),
        "momentum_60d_pct": round(ret_60, 4),
        "relative_momentum_5d_pct": round(ret_5 - benchmark_ret_5, 4),
        "relative_momentum_20d_pct": round(ret_20 - benchmark_ret_20, 4),
        "relative_momentum_60d_pct": round(ret_60 - benchmark_ret_60, 4),
        "ma_gap_10d_pct": round(pct_return(current, ma_10) if ma_10 else 0.0, 4),
        "ma_gap_20d_pct": round(pct_return(current, ma_20) if ma_20 else 0.0, 4),
        "ma_gap_50d_pct": round(pct_return(current, ma_50) if ma_50 else 0.0, 4),
        "volatility_10d_pct": round(vol_10, 4),
        "volatility_20d_pct": round(vol_20, 4),
        "volatility_60d_pct": round(vol_60, 4),
        "drawdown_20d_pct": round(drawdown_20, 4),
        "drawdown_60d_pct": round(drawdown_60, 4),
        "volume_ratio_5_20": round(volume_ratio, 4),
        "beta_spy_20d": round(beta_to_benchmark(stock_20, bench_20), 4),
        "beta_spy_60d": round(beta_to_benchmark(stock_60, bench_60), 4),
        "corr_spy_20d": round(pearson(stock_20, bench_20), 4),
        "corr_spy_60d": round(pearson(stock_60, bench_60), 4),
        "spy_momentum_5d_pct": round(benchmark_ret_5, 4),
        "spy_momentum_20d_pct": round(benchmark_ret_20, 4),
        "spy_volatility_20d_pct": round(annualized_vol_pct(rolling_values(benchmark_series, benchmark_index, 20)) if benchmark_index >= 0 else 0.0, 4),
        "spy_ma_gap_50d_pct": round(
            pct_return(series_price(benchmark_series, benchmark_index), moving_average(rolling_values(benchmark_series, benchmark_index, 50)))
            if benchmark_index >= 0 and moving_average(rolling_values(benchmark_series, benchmark_index, 50))
            else 0.0,
            4,
        ),
        "training_source": "raw_price_history_bootstrap",
    }
    if include_label and index + forward_days < len(series):
        label_end_date = str(series[index + forward_days].get("date", ""))
        forward = series_price(series, index + forward_days)
        raw_forward = pct_return(forward, current)
        benchmark_forward = benchmark_return(benchmark_by_date, date_value, label_end_date)
        row["forward_5d_raw_return_pct"] = round(raw_forward, 4)
        row["forward_5d_benchmark_return_pct"] = round(benchmark_forward, 4)
        row["forward_5d_excess_return_pct"] = round(raw_forward - benchmark_forward, 4)
        row["forward_5d_return_pct"] = round(raw_forward, 4)
        row["label_end_date"] = label_end_date
        row["target_kind"] = "forward_5d_absolute_return"
    return row


def build_price_history_training_rows(
    raw_price_rows: list[dict[str, Any]],
    tickers: list[str],
    lookback: int = 60,
    forward_days: int = 5,
) -> list[dict[str, Any]]:
    ticker_set = {ticker.upper() for ticker in tickers}
    grouped = grouped_price_series(raw_price_rows)
    benchmark_series = grouped.get("SPY") or grouped.get("QQQ") or []
    benchmark_by_date = {str(row.get("date", "")): row for row in benchmark_series}

    training_rows: list[dict[str, Any]] = []
    for ticker, series in grouped.items():
        if ticker not in ticker_set or ticker in {"SPY", "QQQ"}:
            continue
        if len(series) < lookback + forward_days + 1:
            continue
        for index in range(lookback, len(series) - forward_days):
            row = price_feature_row(ticker, series, index, benchmark_series, benchmark_by_date, forward_days, True)
            if row:
                training_rows.append(row)
    add_cross_sectional_ranks(training_rows)
    training_rows.sort(key=lambda row: (row["date"], row["ticker"]))
    return training_rows


def build_latest_price_feature_rows(
    raw_price_rows: list[dict[str, Any]],
    tickers: list[str],
    as_of_date: str | None = None,
) -> dict[str, dict[str, Any]]:
    ticker_set = {ticker.upper() for ticker in tickers}
    grouped = grouped_price_series(raw_price_rows)
    benchmark_series = grouped.get("SPY") or grouped.get("QQQ") or []
    benchmark_by_date = {str(row.get("date", "")): row for row in benchmark_series}
    rows: list[dict[str, Any]] = []
    for ticker in ticker_set:
        series = grouped.get(ticker, [])
        if len(series) < 20:
            continue
        index = len(series) - 1
        if as_of_date:
            eligible = [cursor for cursor, row in enumerate(series) if str(row.get("date", "")) <= as_of_date]
            if not eligible:
                continue
            index = eligible[-1]
        row = price_feature_row(ticker, series, index, benchmark_series, benchmark_by_date, include_label=False)
        if row:
            rows.append(row)
    add_cross_sectional_ranks(rows)
    return {str(row["ticker"]): row for row in rows}


def directional_accuracy(actual: list[float], predicted: list[float]) -> float:
    if not actual:
        return 0.0
    hits = 0
    for real, pred in zip(actual, predicted):
        if (real >= 0 and pred >= 0) or (real < 0 and pred < 0):
            hits += 1
    return round(hits / len(actual), 4)


def ranks(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    out = [0.0] * len(values)
    for rank, (index, _value) in enumerate(ordered, start=1):
        out[index] = float(rank)
    return out


def pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    x_den = math.sqrt(sum((x - x_mean) ** 2 for x in xs))
    y_den = math.sqrt(sum((y - y_mean) ** 2 for y in ys))
    if not x_den or not y_den:
        return 0.0
    return numerator / (x_den * y_den)


def rank_ic(actual: list[float], predicted: list[float]) -> float:
    return round(pearson(ranks(actual), ranks(predicted)), 4)


def bucket_spread(actual: list[float], predicted: list[float], bucket_fraction: float = 0.20) -> dict[str, float]:
    if not actual:
        return {"top_bucket_actual_return": 0.0, "bottom_bucket_actual_return": 0.0, "long_short_spread": 0.0}
    pairs = sorted(zip(predicted, actual), key=lambda item: item[0])
    bucket_size = max(1, int(len(pairs) * bucket_fraction))
    bottom = [real for _pred, real in pairs[:bucket_size]]
    top = [real for _pred, real in pairs[-bucket_size:]]
    top_avg = sum(top) / len(top)
    bottom_avg = sum(bottom) / len(bottom)
    return {
        "top_bucket_actual_return": round(top_avg, 4),
        "bottom_bucket_actual_return": round(bottom_avg, 4),
        "long_short_spread": round(top_avg - bottom_avg, 4),
    }


def model_candidates() -> list[tuple[str, Any]]:
    return [
        (
            "ridge_standardized",
            make_pipeline(StandardScaler(), Ridge(alpha=10.0)),
        ),
        (
            "random_forest_regressor",
            RandomForestRegressor(n_estimators=120, random_state=17, min_samples_leaf=6, max_depth=7),
        ),
        (
            "extra_trees_regressor",
            ExtraTreesRegressor(n_estimators=160, random_state=31, min_samples_leaf=8, max_depth=8),
        ),
        (
            "extra_trees_depth_8_leaf_12_grid_winner",
            ExtraTreesRegressor(n_estimators=160, random_state=31, min_samples_leaf=12, max_depth=8, n_jobs=-1),
        ),
        (
            "hist_gradient_boosting_regressor_conservative",
            HistGradientBoostingRegressor(
                random_state=29,
                learning_rate=0.05,
                max_iter=120,
                max_leaf_nodes=12,
                l2_regularization=0.8,
            ),
        ),
        (
            "random_forest_positive_return_classifier",
            PositiveReturnClassifier(
                RandomForestClassifier(n_estimators=160, random_state=41, min_samples_leaf=8, max_depth=7),
                scale=12.0,
            ),
        ),
        (
            "extra_trees_positive_return_classifier",
            PositiveReturnClassifier(
                ExtraTreesClassifier(n_estimators=180, random_state=43, min_samples_leaf=8, max_depth=8),
                scale=12.0,
            ),
        ),
        (
            "hist_gradient_positive_return_classifier",
            PositiveReturnClassifier(
                HistGradientBoostingClassifier(
                    random_state=47,
                    learning_rate=0.05,
                    max_iter=120,
                    max_leaf_nodes=12,
                    l2_regularization=0.8,
                ),
                scale=12.0,
            ),
        ),
    ]


def score_model_result(result: dict[str, Any]) -> tuple[float, float, float, float, float]:
    wf = result["walk_forward"]
    directional = float(wf.get("directional_accuracy", 0.0))
    rank_value = float(wf.get("rank_ic", 0.0))
    spread = float(wf.get("long_short_spread", 0.0))
    passed = directional >= 0.5 and rank_value > 0.0 and spread > 0.0
    return (
        1.0 if passed else 0.0,
        spread,
        rank_value,
        directional,
        -float(wf.get("mae", 999.0)),
    )


def performance_gate(walk_forward: dict[str, Any]) -> dict[str, Any]:
    thresholds = {
        "min_directional_accuracy": 0.50,
        "min_rank_ic": 0.0,
        "min_long_short_spread": 0.0,
    }
    directional = float(walk_forward.get("directional_accuracy", 0.0))
    rank_value = float(walk_forward.get("rank_ic", 0.0))
    spread = float(walk_forward.get("long_short_spread", 0.0))
    passed = (
        directional >= thresholds["min_directional_accuracy"]
        and rank_value > thresholds["min_rank_ic"]
        and spread > thresholds["min_long_short_spread"]
    )
    if passed:
        reason = "walk_forward_validation_passed"
    else:
        reason = "walk_forward_validation_failed"
    return {
        "passed": passed,
        "reason": reason,
        "thresholds": thresholds,
        "observed": {
            "directional_accuracy": round(directional, 4),
            "rank_ic": round(rank_value, 4),
            "long_short_spread": round(spread, 4),
        },
    }


def combined_performance_gate(model_state: dict[str, Any]) -> dict[str, Any]:
    walk_gate = performance_gate(model_state.get("walk_forward", {}))
    recent = model_state.get("recent_holdout") or {}
    if recent.get("status") != "tested":
        return walk_gate
    recent_gate = performance_gate(recent)
    passed = bool(walk_gate["passed"] and recent_gate["passed"])
    return {
        "passed": passed,
        "reason": "walk_forward_and_recent_holdout_passed" if passed else "walk_forward_or_recent_holdout_failed",
        "walk_forward": walk_gate,
        "recent_holdout": recent_gate,
    }


def walk_forward_evaluate(model_name: str, base_model: Any, x: list[list[float]], y: list[float], splits: int) -> dict[str, Any]:
    splitter = TimeSeriesSplit(n_splits=splits)
    actual: list[float] = []
    predicted: list[float] = []
    for train_idx, test_idx in splitter.split(x):
        model = clone(base_model)
        train_x = [x[index] for index in train_idx]
        train_y = [y[index] for index in train_idx]
        test_x = [x[index] for index in test_idx]
        test_y = [y[index] for index in test_idx]
        model.fit(train_x, train_y)
        preds = list(model.predict(test_x))
        actual.extend(test_y)
        predicted.extend(preds)
    buckets = bucket_spread(actual, predicted)
    return {
        "model_kind": model_name,
        "walk_forward": {
            "splits": splits,
            "mae": round(mean_absolute_error(actual, predicted), 4),
            "directional_accuracy": directional_accuracy(actual, predicted),
            "rank_ic": rank_ic(actual, predicted),
            **buckets,
        },
    }


def holdout_metrics(actual: list[float], predicted: list[float]) -> dict[str, float]:
    return {
        "mae": round(mean_absolute_error(actual, predicted), 4),
        "directional_accuracy": directional_accuracy(actual, predicted),
        "rank_ic": rank_ic(actual, predicted),
        "mean_actual_return_pct": round(sum(actual) / len(actual), 4) if actual else 0.0,
        "mean_predicted_return_pct": round(sum(predicted) / len(predicted), 4) if predicted else 0.0,
        **bucket_spread(actual, predicted),
    }


def evaluate_model_on_anchor(
    model_name: str,
    base_model: Any,
    rows: list[dict[str, Any]],
    anchor_date: str,
    min_train_rows: int = 30,
    max_train_rows: int = 6000,
) -> dict[str, Any]:
    train_rows = [
        row for row in rows
        if str(row.get("date", "")) < anchor_date
        and str(row.get("label_end_date") or row.get("date", "")) <= anchor_date
        and has_label(row)
    ]
    holdout_rows = [
        row for row in rows
        if row.get("date") == anchor_date and has_label(row)
    ]
    if len(train_rows) > max_train_rows:
        train_rows = train_rows[-max_train_rows:]
    if len(train_rows) < min_train_rows or not holdout_rows:
        return {
            "model_kind": model_name,
            "anchor_date": anchor_date,
            "status": "insufficient_anchor_data",
            "train_rows": len(train_rows),
            "holdout_rows": len(holdout_rows),
        }
    model = clone(base_model)
    model.fit(matrix(train_rows), labels(train_rows))
    actual = labels(holdout_rows)
    predicted = [float(value) for value in model.predict(matrix(holdout_rows))]
    return {
        "model_kind": model_name,
        "anchor_date": anchor_date,
        "status": "tested",
        "train_rows": len(train_rows),
        "holdout_rows": len(holdout_rows),
        **holdout_metrics(actual, predicted),
    }


def recent_anchor_dates(
    rows: list[dict[str, Any]],
    count: int = 4,
    spacing: int = 5,
    min_holdout_rows: int = 50,
) -> list[str]:
    counts: dict[str, int] = {}
    for row in rows:
        date_value = str(row.get("date", ""))
        if date_value and has_label(row):
            counts[date_value] = counts.get(date_value, 0) + 1
    dates = sorted(date_value for date_value, row_count in counts.items() if row_count >= min_holdout_rows)
    selected: list[str] = []
    cursor = len(dates) - 1
    while cursor >= 0 and len(selected) < count:
        selected.append(dates[cursor])
        cursor -= spacing
    return list(reversed(selected))


def aggregate_anchor_results(model_kind: str, anchor_results: list[dict[str, Any]]) -> dict[str, Any]:
    tested = [row for row in anchor_results if row.get("status") == "tested"]
    if not tested:
        return {"model_kind": model_kind, "status": "insufficient_anchor_data", "anchors_tested": 0}
    return {
        "model_kind": model_kind,
        "status": "tested",
        "anchors_tested": len(tested),
        "mae": round(sum(as_float(row.get("mae")) for row in tested) / len(tested), 4),
        "directional_accuracy": round(sum(as_float(row.get("directional_accuracy")) for row in tested) / len(tested), 4),
        "rank_ic": round(sum(as_float(row.get("rank_ic")) for row in tested) / len(tested), 4),
        "top_bucket_actual_return": round(sum(as_float(row.get("top_bucket_actual_return")) for row in tested) / len(tested), 4),
        "bottom_bucket_actual_return": round(sum(as_float(row.get("bottom_bucket_actual_return")) for row in tested) / len(tested), 4),
        "long_short_spread": round(sum(as_float(row.get("long_short_spread")) for row in tested) / len(tested), 4),
        "anchor_results": tested,
    }


def recent_holdout_tournament(
    rows: list[dict[str, Any]],
    min_train_rows: int = 30,
    max_train_rows: int = 6000,
) -> list[dict[str, Any]]:
    anchors = recent_anchor_dates(rows)
    results = []
    for model_name, estimator in model_candidates():
        anchor_results = [
            evaluate_model_on_anchor(model_name, estimator, rows, anchor, min_train_rows, max_train_rows)
            for anchor in anchors
        ]
        results.append(aggregate_anchor_results(model_name, anchor_results))
    return results


def score_recent_holdout_result(result: dict[str, Any]) -> tuple[float, float, float, float, float]:
    if result.get("status") != "tested":
        return (-999.0, -999.0, -999.0, -999.0, -999.0)
    directional = float(result.get("directional_accuracy", 0.0))
    rank_value = float(result.get("rank_ic", 0.0))
    spread = float(result.get("long_short_spread", 0.0))
    passed = directional >= 0.5 and rank_value > 0.0 and spread > 0.0
    return (
        1.0 if passed else 0.0,
        spread,
        rank_value,
        directional,
        -float(result.get("mae", 999.0)),
    )


def run_anchor_backtest(
    rows: list[dict[str, Any]],
    anchor_date: str,
    min_train_rows: int = 30,
) -> dict[str, Any]:
    holdout_rows = [
        row for row in rows
        if row.get("date") == anchor_date and has_label(row)
    ]
    train_rows = [
        row for row in rows
        if str(row.get("date", "")) < anchor_date
        and str(row.get("label_end_date") or row.get("date", "")) <= anchor_date
        and has_label(row)
    ]
    result: dict[str, Any] = {
        "holdout_date": anchor_date,
        "train_rows": len(train_rows),
        "holdout_rows": len(holdout_rows),
        "max_train_label_end_date": max((str(row.get("label_end_date") or "") for row in train_rows), default=""),
        "min_holdout_label_end_date": min((str(row.get("label_end_date") or "") for row in holdout_rows), default=""),
    }
    if not holdout_rows:
        return {
            **result,
            "status": "missing_anchor_holdout",
            "model_kind": "mechanical_fallback",
            "holdout": {},
        }

    model_state = train_walk_forward(train_rows, min_train_rows=min_train_rows)
    estimator = model_state.pop("estimator")
    if estimator is None:
        return {
            **result,
            **model_state,
            "holdout": {},
        }

    actual = labels(holdout_rows)
    predicted = [float(value) for value in estimator.predict(matrix(holdout_rows))]
    holdout = holdout_metrics(actual, predicted)
    gate = combined_performance_gate(model_state)
    return {
        **result,
        **model_state,
        "status": "trained" if gate["passed"] else "trained_low_confidence",
        "performance_gate": gate,
        "holdout": holdout,
    }


def train_walk_forward(rows: list[dict[str, Any]], min_train_rows: int = 30, max_train_rows: int = 6000) -> dict[str, Any]:
    all_labeled = [row for row in rows if has_label(row)]
    all_labeled.sort(key=lambda row: str(row.get("date", "")))
    available_labeled_rows = len(all_labeled)
    labeled = all_labeled[-max_train_rows:] if len(all_labeled) > max_train_rows else all_labeled
    if len(labeled) < min_train_rows:
        return {
            "status": "insufficient_labeled_history",
            "model_kind": "mechanical_fallback",
            "labeled_rows": len(labeled),
            "available_labeled_rows": available_labeled_rows,
            "min_train_rows": min_train_rows,
            "estimator": None,
            "walk_forward": {},
        }
    x = matrix(labeled)
    y = labels(labeled)
    splits = min(5, max(2, len(labeled) // 2000 if len(labeled) > 2000 else len(labeled) // 6))
    tuning_results = [
        walk_forward_evaluate(name, estimator, x, y, splits)
        for name, estimator in model_candidates()
    ]
    recent_holdouts = recent_holdout_tournament(all_labeled, min_train_rows=min_train_rows, max_train_rows=max_train_rows)
    best_recent = max(recent_holdouts, key=score_recent_holdout_result) if recent_holdouts else {}
    if best_recent.get("status") == "tested":
        best_name = str(best_recent["model_kind"])
        selection_basis = "recent_anchor_holdout_tournament"
    else:
        best = max(tuning_results, key=score_model_result)
        best_name = str(best["model_kind"])
        selection_basis = "walk_forward_time_series_split"
    best = next(result for result in tuning_results if result["model_kind"] == best_name)
    best_template = next(estimator for name, estimator in model_candidates() if name == best_name)
    final_model = clone(best_template)
    final_model.fit(x, y)
    return {
        "status": "trained",
        "model_kind": best_name,
        "labeled_rows": len(labeled),
        "available_labeled_rows": available_labeled_rows,
        "max_train_rows": max_train_rows,
        "min_train_rows": min_train_rows,
        "estimator": final_model,
        "selection_basis": selection_basis,
        "walk_forward": best["walk_forward"],
        "recent_holdout": best_recent if best_recent.get("model_kind") == best_name else {},
        "recent_holdout_tournament": recent_holdouts,
        "tuning_results": [
            {"model_kind": result["model_kind"], **result["walk_forward"]}
            for result in tuning_results
        ],
    }


def build_ml_predictions(
    current_rows: list[dict[str, Any]],
    historical_rows: list[dict[str, Any]],
    min_train_rows: int = 30,
) -> dict[str, Any]:
    model_state = train_walk_forward(historical_rows, min_train_rows=min_train_rows)
    estimator = model_state.pop("estimator")
    predictions: list[dict[str, Any]] = []
    if estimator is None:
        for row in current_rows:
            updated = dict(row)
            updated["prediction_source"] = "mechanical"
            updated["ml_model_kind"] = model_state["model_kind"]
            updated["ml_expected_5d_return_pct"] = ""
            predictions.append(updated)
        model_state["predictions"] = predictions
        return model_state

    predicted_values = estimator.predict(matrix(current_rows))
    gate = combined_performance_gate(model_state)
    model_state["performance_gate"] = gate
    if not gate["passed"]:
        model_state["status"] = "trained_low_confidence"
        for row, prediction in zip(current_rows, predicted_values):
            updated = dict(row)
            updated["prediction_source"] = "mechanical"
            updated["ml_model_kind"] = model_state["model_kind"]
            updated["ml_expected_5d_return_pct"] = ""
            updated["rejected_ml_expected_5d_return_pct"] = round(float(prediction), 4)
            predictions.append(updated)
        model_state["predictions"] = predictions
        return model_state

    for row, prediction in zip(current_rows, predicted_values):
        updated = dict(row)
        ml_return = round(float(prediction), 4)
        updated["prediction_source"] = "ml"
        updated["ml_model_kind"] = model_state["model_kind"]
        updated["ml_expected_5d_return_pct"] = ml_return
        updated["expected_5d_return_pct"] = ml_return
        updated["goal_contribution_pct"] = round(as_float(updated.get("recommended_weight_pct")) / 100.0 * ml_return, 4)
        predictions.append(updated)
    model_state["predictions"] = predictions
    return model_state
