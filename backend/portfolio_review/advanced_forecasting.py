from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from portfolio_review.ml_models import as_float, grouped_price_series, holdout_metrics, pct_return, performance_gate
from portfolio_review.training_dataset import is_equity_training_symbol


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


@dataclass(frozen=True)
class AdvancedModelSpec:
    model_kind: str
    repo_id: str
    model_family: str
    runtime_package: str
    source_url: str
    paper_url: str
    license: str
    implementation_priority: str
    recommended_first_test: str
    best_practice_notes: list[str]


ForecastRunner = Callable[[AdvancedModelSpec, list[dict[str, Any]], int], Iterable[dict[str, Any]]]

RUNTIME_IMPORT_ALIASES = {
    "granite-tsfm": "tsfm_public",
    "timecopilot-uni2ts": "uni2ts",
    "lag-llama": "lag_llama",
}


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def runtime_import_name(package_name: str) -> str:
    return RUNTIME_IMPORT_ALIASES.get(package_name, package_name)


def build_advanced_model_specs() -> list[AdvancedModelSpec]:
    return [
        AdvancedModelSpec(
            model_kind="chronos_2",
            repo_id="amazon/chronos-2",
            model_family="Chronos",
            runtime_package="chronos",
            source_url="https://huggingface.co/amazon/chronos-2",
            paper_url="https://arxiv.org/abs/2510.15821",
            license="apache-2.0",
            implementation_priority="primary",
            recommended_first_test="zero_shot_cross_series_price_forecast",
            best_practice_notes=[
                "Prefer zero-shot backtesting before any fine-tuning.",
                "Use only price context available at the anchor date.",
                "Compare context lengths and promote only if recent holdouts pass the same gate as supervised ML.",
                "Chronos-2 supports cross-series and covariate-aware forecasting, so it is the first advanced candidate.",
            ],
        ),
        AdvancedModelSpec(
            model_kind="chronos_2_cross",
            repo_id="amazon/chronos-2",
            model_family="Chronos",
            runtime_package="chronos",
            source_url="https://huggingface.co/amazon/chronos-2",
            paper_url="https://arxiv.org/abs/2510.15821",
            license="apache-2.0",
            implementation_priority="primary_parameter_sweep",
            recommended_first_test="zero_shot_cross_learning_context_sweep",
            best_practice_notes=[
                "Chronos-2 predict_df exposes cross_learning; installed docs warn it does not always help.",
                "Use batch_size near 100 because the package docs cite that size in the technical-report guidance.",
                "Treat this as a parameter variant, not a separate model family.",
            ],
        ),
        AdvancedModelSpec(
            model_kind="chronos_t5_small",
            repo_id="amazon/chronos-t5-small",
            model_family="Chronos",
            runtime_package="chronos",
            source_url="https://huggingface.co/amazon/chronos-t5-small",
            paper_url="https://arxiv.org/abs/2403.07815",
            license="apache-2.0",
            implementation_priority="secondary",
            recommended_first_test="zero_shot_price_forecast",
            best_practice_notes=[
                "Use probabilistic forecasts and score the median 5-day horizon first.",
                "Test multiple context lengths because the model card examples emphasize context sensitivity.",
                "Treat this as a simpler baseline against Chronos-2 rather than the preferred candidate.",
            ],
        ),
        AdvancedModelSpec(
            model_kind="chronos_bolt_tiny",
            repo_id="autogluon/chronos-bolt-tiny",
            model_family="Chronos",
            runtime_package="chronos",
            source_url="https://huggingface.co/autogluon/chronos-bolt-tiny",
            paper_url="https://arxiv.org/abs/2403.07815",
            license="apache-2.0",
            implementation_priority="primary_fast_baseline",
            recommended_first_test="zero_shot_price_forecast_context_sweep",
            best_practice_notes=[
                "Chronos-Bolt is documented as faster and more memory-efficient than original Chronos.",
                "Use as a fast context-length sweep candidate before spending time on larger models.",
                "Keep the same anchored holdout gate as all other forecasters.",
            ],
        ),
        AdvancedModelSpec(
            model_kind="chronos_bolt_mini",
            repo_id="autogluon/chronos-bolt-mini",
            model_family="Chronos",
            runtime_package="chronos",
            source_url="https://huggingface.co/autogluon/chronos-bolt-mini",
            paper_url="https://arxiv.org/abs/2403.07815",
            license="apache-2.0",
            implementation_priority="primary_fast_baseline",
            recommended_first_test="zero_shot_price_forecast_context_sweep",
            best_practice_notes=[
                "Mini-sized Bolt tests whether a modest model improves over tiny without large CPU cost.",
                "Model-card guidance supports CPU-friendly zero-shot forecasting.",
                "Promote only if it beats simpler supervised baselines under rolling validation.",
            ],
        ),
        AdvancedModelSpec(
            model_kind="chronos_bolt_small",
            repo_id="autogluon/chronos-bolt-small",
            model_family="Chronos",
            runtime_package="chronos",
            source_url="https://huggingface.co/autogluon/chronos-bolt-small",
            paper_url="https://arxiv.org/abs/2403.07815",
            license="apache-2.0",
            implementation_priority="primary_fast_baseline",
            recommended_first_test="zero_shot_price_forecast_context_sweep",
            best_practice_notes=[
                "Small-sized Bolt is the closest size peer to Chronos T5-small.",
                "The model card reports Bolt improves speed and accuracy versus original Chronos families on broad benchmarks.",
                "Use context-length sensitivity checks because stock-history-only forecasting can be unstable.",
            ],
        ),
        AdvancedModelSpec(
            model_kind="moirai_small",
            repo_id="Salesforce/moirai-1.0-R-small",
            model_family="MOIRAI",
            runtime_package="uni2ts",
            source_url="https://huggingface.co/Salesforce/moirai-1.0-R-small",
            paper_url="https://arxiv.org/abs/2402.02592",
            license="cc-by-nc-4.0",
            implementation_priority="research_candidate",
            recommended_first_test="zero_shot_then_domain_validation",
            best_practice_notes=[
                "Use the Uni2TS/GluonTS path from the model card rather than raw AutoModel outputs.",
                "Respect the non-commercial license before any use beyond local research.",
                "Benchmark with rolling windows before considering fine-tuning.",
            ],
        ),
        AdvancedModelSpec(
            model_kind="moment_small",
            repo_id="AutonLab/MOMENT-1-small",
            model_family="MOMENT",
            runtime_package="momentfm",
            source_url="https://huggingface.co/AutonLab/MOMENT-1-small",
            paper_url="https://arxiv.org/abs/2402.03885",
            license="mit",
            implementation_priority="research_candidate",
            recommended_first_test="forecasting_pipeline_then_embedding_features",
            best_practice_notes=[
                "Use MOMENTPipeline with task_name='forecasting' for direct forecasts.",
                "Later test task-specific embeddings as features in the supervised tournament.",
                "Run out-of-sample validation before using any few-shot or fine-tuned variant.",
            ],
        ),
        AdvancedModelSpec(
            model_kind="lag_llama",
            repo_id="time-series-foundation-models/Lag-Llama",
            model_family="Lag-Llama",
            runtime_package="lag_llama",
            source_url="https://huggingface.co/time-series-foundation-models/Lag-Llama",
            paper_url="https://arxiv.org/abs/2310.08278",
            license="apache-2.0",
            implementation_priority="research_candidate",
            recommended_first_test="zero_shot_then_finetune_if_needed",
            best_practice_notes=[
                "The model card recommends benchmarking zero-shot first, then fine-tuning if needed.",
                "Tune context length before drawing conclusions.",
                "Use validation splits and early stopping for fine-tuning experiments.",
            ],
        ),
        AdvancedModelSpec(
            model_kind="granite_ttm_r2",
            repo_id="ibm-granite/granite-timeseries-ttm-r2",
            model_family="Granite TTM",
            runtime_package="granite-tsfm",
            source_url="https://huggingface.co/ibm-granite/granite-timeseries-ttm-r2",
            paper_url="https://research.ibm.com/publications/tiny-time-mixers-ttms-fast-pre-trained-models-for-enhanced-zerofew-shot-forecasting-of-multivariate-time-series--1",
            license="apache-2.0",
            implementation_priority="research_candidate",
            recommended_first_test="zero_shot_point_forecast_context_sweep",
            best_practice_notes=[
                "Use the granite-tsfm TinyTimeMixer prediction API rather than generic transformer loading.",
                "Benchmark zero-shot first because the model family is designed for fast zero/few-shot time-series forecasting.",
                "Keep it out of recommendation authority until the adapter passes the same rolling holdout gates.",
            ],
        ),
    ]


def package_available(package_name: str) -> bool:
    return importlib.util.find_spec(runtime_import_name(package_name)) is not None


def select_specs(model_kinds: list[str] | None = None) -> list[AdvancedModelSpec]:
    specs = build_advanced_model_specs()
    if not model_kinds:
        return specs
    selected = {item.strip() for item in model_kinds if item.strip()}
    return [spec for spec in specs if spec.model_kind in selected or spec.repo_id in selected]


def context_rows_for_anchor(
    raw_price_rows: list[dict[str, Any]],
    anchor_date: str,
    context_length: int,
    prediction_length: int,
    max_tickers: int,
) -> list[dict[str, Any]]:
    grouped = grouped_price_series(raw_price_rows)
    contexts: list[dict[str, Any]] = []
    for ticker in sorted(grouped):
        if ticker in {"SPY", "QQQ"} or not is_equity_training_symbol(ticker):
            continue
        series = grouped[ticker]
        eligible_indexes = [index for index, row in enumerate(series) if str(row.get("date", "")) <= anchor_date]
        if not eligible_indexes:
            continue
        anchor_index = eligible_indexes[-1]
        label_index = anchor_index + prediction_length
        if anchor_index + 1 < context_length or label_index >= len(series):
            continue
        context_slice = series[anchor_index - context_length + 1 : anchor_index + 1]
        current_price = as_float(series[anchor_index].get("price"))
        final_price = as_float(series[label_index].get("price"))
        if current_price <= 0 or final_price <= 0:
            continue
        contexts.append(
            {
                "context_id": f"{ticker}:{anchor_date}:{context_length}",
                "ticker": ticker,
                "anchor_date": anchor_date,
                "context_length": context_length,
                "prediction_length": prediction_length,
                "last_context_date": str(series[anchor_index].get("date", "")),
                "label_end_date": str(series[label_index].get("date", "")),
                "prices": [as_float(row.get("price")) for row in context_slice],
                "current_price": current_price,
                "actual_final_price": final_price,
                "actual_return_pct": pct_return(final_price, current_price),
            }
        )
        if len(contexts) >= max_tickers:
            break
    return contexts


def _chronos_predictions_from_tensor_output(output: Any) -> list[float]:
    try:
        import numpy as np
    except Exception as exc:  # pragma: no cover - dependency reported by caller
        raise RuntimeError(f"numpy unavailable for Chronos output conversion: {exc}") from exc
    data = output.detach().cpu().numpy() if hasattr(output, "detach") else np.asarray(output)
    if data.ndim == 3:
        return [float(np.median(data[index, :, -1])) for index in range(data.shape[0])]
    if data.ndim == 2:
        return [float(data[index, -1]) for index in range(data.shape[0])]
    raise RuntimeError(f"Unexpected Chronos forecast shape: {data.shape}")


def _chronos_predict_df(
    spec: AdvancedModelSpec,
    pipeline: Any,
    contexts: list[dict[str, Any]],
    prediction_length: int,
) -> list[dict[str, Any]]:
    import pandas as pd

    rows: list[dict[str, Any]] = []
    for context in contexts:
        for index, value in enumerate(context["prices"]):
            rows.append(
                {
                    "item_id": context["context_id"],
                    "timestamp": pd.Timestamp("2000-01-01") + pd.Timedelta(days=index),
                    "target": value,
                }
            )
    predict_kwargs: dict[str, Any] = {}
    if spec.model_kind == "chronos_2_cross":
        predict_kwargs = {
            "cross_learning": True,
            "batch_size": min(100, max(1, len(contexts))),
            "context_length": max((len(context["prices"]) for context in contexts), default=None),
        }
    pred_df = pipeline.predict_df(
        pd.DataFrame(rows),
        prediction_length=prediction_length,
        quantile_levels=[0.5],
        id_column="item_id",
        timestamp_column="timestamp",
        target="target",
        **predict_kwargs,
    )
    outputs: list[dict[str, Any]] = []
    for context in contexts:
        forecast_rows = pred_df[pred_df["item_id"] == context["context_id"]]
        value_column = "0.5" if "0.5" in forecast_rows.columns else "mean" if "mean" in forecast_rows.columns else ""
        if not value_column:
            numeric_columns = [column for column in forecast_rows.columns if column not in {"item_id", "timestamp"}]
            value_column = numeric_columns[-1] if numeric_columns else ""
        if not value_column or forecast_rows.empty:
            raise RuntimeError("Chronos predict_df did not return a usable median/mean forecast column.")
        outputs.append(
            {
                "ticker": context["ticker"],
                "context_id": context["context_id"],
                "predicted_final_price": float(forecast_rows[value_column].iloc[-1]),
                "prediction_length": prediction_length,
                "status": "ok",
            }
        )
    return outputs


def run_chronos_forecast(
    spec: AdvancedModelSpec,
    contexts: list[dict[str, Any]],
    prediction_length: int,
) -> list[dict[str, Any]]:
    try:
        import torch
        from chronos import BaseChronosPipeline
    except Exception as exc:
        raise RuntimeError(f"Chronos runtime is not available: {exc}") from exc

    try:
        seed = int(os.environ.get("ADVANCED_MODEL_SEED", "17"))
    except ValueError:
        seed = 17
    torch.manual_seed(seed)
    device_map = os.environ.get("ADVANCED_MODEL_DEVICE", "cpu")
    dtype_name = os.environ.get("ADVANCED_MODEL_TORCH_DTYPE", "float32")
    dtype = getattr(torch, dtype_name, torch.float32)
    try:
        pipeline = BaseChronosPipeline.from_pretrained(spec.repo_id, device_map=device_map, dtype=dtype)
    except TypeError:
        pipeline = BaseChronosPipeline.from_pretrained(spec.repo_id, device_map=device_map, torch_dtype=dtype)
    if hasattr(pipeline, "predict_df"):
        return _chronos_predict_df(spec, pipeline, contexts, prediction_length)
    tensors = [torch.tensor(context["prices"], dtype=torch.float32) for context in contexts]
    forecast = pipeline.predict(tensors, prediction_length=prediction_length)
    final_prices = _chronos_predictions_from_tensor_output(forecast)
    return [
        {
            "ticker": context["ticker"],
            "context_id": context["context_id"],
            "predicted_final_price": final_price,
            "prediction_length": prediction_length,
            "status": "ok",
        }
        for context, final_price in zip(contexts, final_prices)
    ]


def _left_padded_price_tensors(
    contexts: list[dict[str, Any]],
    target_length: int | None = None,
    channels_first: bool = True,
) -> tuple[Any, Any]:
    import torch

    sequence_length = target_length or max((len(context["prices"]) for context in contexts), default=0)
    values = torch.zeros((len(contexts), sequence_length), dtype=torch.float32)
    masks = torch.zeros((len(contexts), sequence_length), dtype=torch.float32)
    for row_index, context in enumerate(contexts):
        prices = [float(value) for value in context["prices"]][-sequence_length:]
        if not prices:
            continue
        values[row_index, -len(prices) :] = torch.tensor(prices, dtype=torch.float32)
        masks[row_index, -len(prices) :] = 1.0
    if channels_first:
        return values.unsqueeze(1), masks
    return values.unsqueeze(-1), masks.unsqueeze(-1)


def _forecast_rows_from_final_prices(
    contexts: list[dict[str, Any]],
    final_prices: list[float],
    prediction_length: int,
) -> list[dict[str, Any]]:
    return [
        {
            "ticker": context["ticker"],
            "context_id": context["context_id"],
            "predicted_final_price": float(final_price),
            "prediction_length": prediction_length,
            "status": "ok",
        }
        for context, final_price in zip(contexts, final_prices)
    ]


def _final_prices_from_output_tensor(output: Any, channels_first: bool = True) -> list[float]:
    import numpy as np

    data = output.detach().cpu().numpy() if hasattr(output, "detach") else np.asarray(output)
    if data.ndim == 3 and channels_first:
        return [float(data[index, 0, -1]) for index in range(data.shape[0])]
    if data.ndim == 3:
        return [float(data[index, -1, 0]) for index in range(data.shape[0])]
    if data.ndim == 2:
        return [float(data[index, -1]) for index in range(data.shape[0])]
    raise RuntimeError(f"Unexpected forecast tensor shape: {data.shape}")


def prediction_output_tensor(output: Any) -> Any:
    forecast = getattr(output, "prediction_outputs", None)
    if forecast is not None:
        return forecast
    forecast = getattr(output, "prediction_logits", None)
    if forecast is not None:
        return forecast
    raise RuntimeError("Granite TTM did not return prediction outputs.")


def granite_frequency_token_tensor(batch_size: int, freq: str, device: str) -> Any:
    import torch
    from tsfm_public.toolkit.time_series_preprocessor import DEFAULT_FREQUENCY_MAPPING

    token = DEFAULT_FREQUENCY_MAPPING.get(freq, DEFAULT_FREQUENCY_MAPPING["oov"])
    return torch.full((batch_size,), int(token), dtype=torch.int, device=device)


def run_moment_forecast(
    spec: AdvancedModelSpec,
    contexts: list[dict[str, Any]],
    prediction_length: int,
) -> list[dict[str, Any]]:
    try:
        import torch
        from momentfm import MOMENTPipeline
    except Exception as exc:
        raise RuntimeError(f"MOMENT runtime is not available: {exc}") from exc

    torch.manual_seed(int(os.environ.get("ADVANCED_MODEL_SEED", "17")))
    device = os.environ.get("ADVANCED_MODEL_DEVICE", "cpu")
    model = MOMENTPipeline.from_pretrained(
        spec.repo_id,
        model_kwargs={
            "task_name": "forecasting",
            "forecast_horizon": prediction_length,
        },
    )
    model.init()
    model.to(device)
    model.eval()
    values, masks = _left_padded_price_tensors(contexts, channels_first=True)
    values = values.to(device)
    masks = masks.to(device)
    with torch.no_grad():
        outputs = model(x_enc=values, input_mask=masks)
    forecast = getattr(outputs, "forecast", None)
    if forecast is None:
        raise RuntimeError("MOMENT did not return a forecast tensor.")
    return _forecast_rows_from_final_prices(
        contexts,
        _final_prices_from_output_tensor(forecast, channels_first=True),
        prediction_length,
    )


def run_granite_ttm_forecast(
    spec: AdvancedModelSpec,
    contexts: list[dict[str, Any]],
    prediction_length: int,
) -> list[dict[str, Any]]:
    try:
        import torch
        from tsfm_public.toolkit.get_model import get_model
    except Exception as exc:
        raise RuntimeError(f"Granite TTM runtime is not available: {exc}") from exc

    torch.manual_seed(int(os.environ.get("ADVANCED_MODEL_SEED", "17")))
    device = os.environ.get("ADVANCED_MODEL_DEVICE", "cpu")
    requested_context_length = max((len(context["prices"]) for context in contexts), default=0)
    model = get_model(
        spec.repo_id,
        context_length=requested_context_length,
        prediction_length=prediction_length,
        freq=os.environ.get("ADVANCED_MODEL_FREQ", "D"),
        force_return=os.environ.get("ADVANCED_MODEL_TTM_FORCE_RETURN", "zeropad"),
        prefer_l1_loss=env_flag("ADVANCED_MODEL_TTM_PREFER_L1", False),
    )
    model.to(device)
    model.eval()
    model_context_length = int(getattr(model.config, "context_length", requested_context_length))
    past_values, observed_mask = _left_padded_price_tensors(contexts, target_length=model_context_length, channels_first=False)
    past_values = past_values.to(device)
    observed_mask = observed_mask.to(device)
    freq_token = None
    if getattr(model.config, "resolution_prefix_tuning", False):
        freq_token = granite_frequency_token_tensor(
            batch_size=len(contexts),
            freq=os.environ.get("ADVANCED_MODEL_FREQ", "D"),
            device=device,
        )
    with torch.no_grad():
        outputs = model(
            past_values=past_values,
            past_observed_mask=observed_mask,
            return_loss=False,
            freq_token=freq_token,
        )
    forecast = prediction_output_tensor(outputs)
    return _forecast_rows_from_final_prices(
        contexts,
        _final_prices_from_output_tensor(forecast, channels_first=False),
        prediction_length,
    )


def run_moirai_forecast(
    spec: AdvancedModelSpec,
    contexts: list[dict[str, Any]],
    prediction_length: int,
) -> list[dict[str, Any]]:
    try:
        import pandas as pd
        from gluonts.dataset.pandas import PandasDataset
        from uni2ts.model.moirai import MoiraiForecast, MoiraiModule
    except Exception as exc:
        raise RuntimeError(f"MOIRAI runtime is not available: {exc}") from exc

    wide_rows: dict[str, list[float]] = {context["context_id"]: [float(value) for value in context["prices"]] for context in contexts}
    df = pd.DataFrame(wide_rows)
    df.index = pd.date_range("2000-01-01", periods=len(df), freq=os.environ.get("ADVANCED_MODEL_FREQ", "D"))
    dataset = PandasDataset(dict(df))
    model = MoiraiForecast(
        module=MoiraiModule.from_pretrained(spec.repo_id),
        prediction_length=prediction_length,
        context_length=max((len(context["prices"]) for context in contexts), default=0),
        patch_size=os.environ.get("ADVANCED_MODEL_MOIRAI_PATCH_SIZE", "auto"),
        num_samples=int(os.environ.get("ADVANCED_MODEL_NUM_SAMPLES", "100")),
        target_dim=1,
        feat_dynamic_real_dim=dataset.num_feat_dynamic_real,
        past_feat_dynamic_real_dim=dataset.num_past_feat_dynamic_real,
    )
    predictor = model.create_predictor(batch_size=min(32, max(1, len(contexts))))
    forecasts = list(predictor.predict(dataset))
    final_prices = []
    for forecast in forecasts:
        if hasattr(forecast, "mean"):
            final_prices.append(float(forecast.mean[-1]))
        else:
            final_prices.append(float(forecast.quantile(0.5)[-1]))
    return _forecast_rows_from_final_prices(contexts, final_prices, prediction_length)


def run_lag_llama_forecast(
    spec: AdvancedModelSpec,
    contexts: list[dict[str, Any]],
    prediction_length: int,
) -> list[dict[str, Any]]:
    isolated_python = os.environ.get("LAG_LLAMA_PYTHON")
    if isolated_python:
        runner_script = Path(
            os.environ.get("LAG_LLAMA_RUNNER_SCRIPT", str(Path(__file__).with_name("lag_llama_isolated_runner.py")))
        )
        payload = {
            "spec": asdict(spec),
            "contexts": contexts,
            "prediction_length": prediction_length,
            "freq": os.environ.get("ADVANCED_MODEL_FREQ", "D"),
            "num_samples": int(os.environ.get("ADVANCED_MODEL_NUM_SAMPLES", "100")),
            "device": os.environ.get("ADVANCED_MODEL_DEVICE", "cpu"),
        }
        with tempfile.TemporaryDirectory(prefix="lag_llama_runner_") as tmp:
            input_path = Path(tmp) / "input.json"
            output_path = Path(tmp) / "output.json"
            input_path.write_text(json.dumps(payload))
            completed = subprocess.run(
                [isolated_python, str(runner_script), str(input_path), str(output_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "").strip()
                raise RuntimeError(f"Lag-Llama isolated runner failed: {detail[-1000:]}")
            return json.loads(output_path.read_text())
    raise RuntimeError(
        "Lag-Llama requires installation from https://github.com/time-series-foundation-models/lag-llama.git "
        "and an isolated `LAG_LLAMA_PYTHON` environment because its GluonTS dependency conflicts with MOIRAI."
    )


def default_runner(spec: AdvancedModelSpec, contexts: list[dict[str, Any]], prediction_length: int) -> list[dict[str, Any]]:
    if spec.model_family == "Chronos":
        return run_chronos_forecast(spec, contexts, prediction_length)
    if spec.model_kind == "moment_small":
        return run_moment_forecast(spec, contexts, prediction_length)
    if spec.model_kind == "granite_ttm_r2":
        return run_granite_ttm_forecast(spec, contexts, prediction_length)
    if spec.model_kind == "moirai_small":
        return run_moirai_forecast(spec, contexts, prediction_length)
    if spec.model_kind == "lag_llama":
        return run_lag_llama_forecast(spec, contexts, prediction_length)
    raise RuntimeError(
        f"{spec.model_kind} requires the {spec.runtime_package} adapter; no adapter is wired for this model kind."
    )


def evaluate_spec_context(
    raw_price_rows: list[dict[str, Any]],
    spec: AdvancedModelSpec,
    anchor_dates: list[str],
    context_length: int,
    prediction_length: int,
    max_tickers: int,
    runner: ForecastRunner | None,
) -> dict[str, Any]:
    result_base = {
        "model_kind": f"{spec.model_kind}_ctx{context_length}",
        "base_model_kind": spec.model_kind,
        "repo_id": spec.repo_id,
        "model_family": spec.model_family,
        "runtime_package": spec.runtime_package,
        "context_length": context_length,
        "prediction_length": prediction_length,
        "authority": "none",
        "research": asdict(spec),
    }
    if runner is None and not package_available(spec.runtime_package):
        return {
            **result_base,
            "status": "unavailable_runtime",
            "reason": f"Install optional package `{spec.runtime_package}` to run this candidate.",
            "anchor_count": 0,
            "holdout_rows": 0,
        }

    actual: list[float] = []
    predicted: list[float] = []
    prediction_rows: list[dict[str, Any]] = []
    tested_anchors = 0
    active_runner = runner or default_runner
    for anchor_date in anchor_dates:
        contexts = context_rows_for_anchor(raw_price_rows, anchor_date, context_length, prediction_length, max_tickers)
        if not contexts:
            continue
        tested_anchors += 1
        try:
            forecasts = list(active_runner(spec, contexts, prediction_length))
        except Exception as exc:
            return {
                **result_base,
                "status": "runtime_error",
                "reason": str(exc),
                "anchor_count": tested_anchors,
                "holdout_rows": len(actual),
            }
        for context, forecast in zip(contexts, forecasts):
            forecast_price = as_float(forecast.get("predicted_final_price"))
            if forecast_price <= 0:
                continue
            predicted_return = pct_return(forecast_price, as_float(context.get("current_price")))
            actual_return = as_float(context.get("actual_return_pct"))
            actual.append(actual_return)
            predicted.append(predicted_return)
            prediction_rows.append(
                {
                    "ticker": context["ticker"],
                    "anchor_date": anchor_date,
                    "last_context_date": context["last_context_date"],
                    "label_end_date": context["label_end_date"],
                    "actual_return_pct": round(actual_return, 4),
                    "predicted_return_pct": round(predicted_return, 4),
                }
            )
    if not actual:
        return {
            **result_base,
            "status": "insufficient_holdout_data",
            "reason": "No usable price contexts and labels were available for the requested anchors.",
            "anchor_count": tested_anchors,
            "holdout_rows": 0,
        }
    metrics = holdout_metrics(actual, predicted)
    gate = performance_gate(metrics)
    return {
        **result_base,
        "status": "tested",
        "authority": "eligible" if gate["passed"] else "rejected_by_validation",
        "anchor_count": tested_anchors,
        "holdout_rows": len(actual),
        **metrics,
        "performance_gate": gate,
        "predictions": prediction_rows,
    }


def score_candidate(result: dict[str, Any]) -> tuple[float, float, float, float, float]:
    if result.get("status") != "tested":
        return (-999.0, -999.0, -999.0, -999.0, -999.0)
    passed = 1.0 if result.get("performance_gate", {}).get("passed") else 0.0
    return (
        passed,
        as_float(result.get("long_short_spread")),
        as_float(result.get("rank_ic")),
        as_float(result.get("directional_accuracy")),
        -as_float(result.get("mae"), 999.0),
    )


def run_advanced_price_backtest(
    raw_price_rows: list[dict[str, Any]],
    specs: list[AdvancedModelSpec] | None = None,
    anchor_dates: list[str] | None = None,
    context_lengths: list[int] | None = None,
    prediction_length: int = 5,
    max_tickers: int = 60,
    runner: ForecastRunner | None = None,
) -> dict[str, Any]:
    specs = specs or select_specs(["chronos_2"])
    anchor_dates = anchor_dates or recent_price_anchor_dates(raw_price_rows)
    context_lengths = context_lengths or [64, 128, 252]
    candidate_results = [
        evaluate_spec_context(
            raw_price_rows=raw_price_rows,
            spec=spec,
            anchor_dates=anchor_dates,
            context_length=context_length,
            prediction_length=prediction_length,
            max_tickers=max_tickers,
            runner=runner,
        )
        for spec in specs
        for context_length in context_lengths
    ]
    tested = [row for row in candidate_results if row.get("status") == "tested"]
    unavailable = [row for row in candidate_results if row.get("status") == "unavailable_runtime"]
    if tested:
        best = max(tested, key=score_candidate)
        status = "tested"
    elif unavailable and len(unavailable) == len(candidate_results):
        best = {}
        status = "unavailable"
    else:
        best = {}
        status = "not_tested"
    return {
        "status": status,
        "best_model": best.get("model_kind", ""),
        "authority": best.get("authority", "none") if best else "none",
        "anchor_dates": anchor_dates,
        "context_lengths": context_lengths,
        "prediction_length": prediction_length,
        "candidate_results": candidate_results,
    }


def recent_price_anchor_dates(raw_price_rows: list[dict[str, Any]], count: int = 3, min_tickers: int = 50) -> list[str]:
    by_date: dict[str, set[str]] = {}
    grouped = grouped_price_series(raw_price_rows)
    for ticker, series in grouped.items():
        if ticker in {"SPY", "QQQ"} or not is_equity_training_symbol(ticker):
            continue
        for index, row in enumerate(series[:-5]):
            if index < 64:
                continue
            by_date.setdefault(str(row.get("date", "")), set()).add(ticker)
    dates = sorted(date_value for date_value, tickers in by_date.items() if len(tickers) >= min_tickers)
    return dates[-count:]


def read_csv(path: Path) -> list[dict[str, str]]:
    import csv

    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run leakage-safe advanced time-series model backtests.")
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument("--models", default="chronos_2", help="Comma-separated model kinds or repo ids.")
    parser.add_argument("--anchors", default="", help="Comma-separated anchor dates; defaults to recent price anchors.")
    parser.add_argument("--context-lengths", default="64,128", help="Comma-separated context lengths.")
    parser.add_argument("--prediction-length", type=int, default=5)
    parser.add_argument("--max-tickers", type=int, default=30)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    model_kinds = [item.strip() for item in args.models.split(",") if item.strip()]
    anchors = [item.strip() for item in args.anchors.split(",") if item.strip()] or None
    context_lengths = [int(item.strip()) for item in args.context_lengths.split(",") if item.strip()]
    result = run_advanced_price_backtest(
        read_csv(data_dir / "raw_prices.csv"),
        specs=select_specs(model_kinds),
        anchor_dates=anchors,
        context_lengths=context_lengths,
        prediction_length=args.prediction_length,
        max_tickers=args.max_tickers,
    )
    text = json.dumps(result, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
