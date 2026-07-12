from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def _point_forecast(forecast: Any) -> float:
    import numpy as np

    if hasattr(forecast, "samples"):
        samples = np.asarray(forecast.samples)
        if samples.ndim >= 2:
            return float(np.median(samples[:, -1]))
    if hasattr(forecast, "mean"):
        return float(forecast.mean[-1])
    return float(forecast.quantile(0.5)[-1])


def run(payload: dict[str, Any]) -> list[dict[str, Any]]:
    import pandas as pd
    import torch
    from gluonts.dataset.common import ListDataset
    from huggingface_hub import hf_hub_download
    from lag_llama.gluon.estimator import LagLlamaEstimator

    contexts = payload["contexts"]
    prediction_length = int(payload["prediction_length"])
    freq = str(payload.get("freq") or "D")
    device_name = str(payload.get("device") or "cpu")
    num_samples = int(payload.get("num_samples") or 100)
    context_length = max((len(context["prices"]) for context in contexts), default=0)
    if context_length <= 0:
        return []

    spec = payload.get("spec") or {}
    repo_id = spec.get("repo_id") or "time-series-foundation-models/Lag-Llama"
    checkpoint_path = os.environ.get("LAG_LLAMA_CKPT_PATH") or hf_hub_download(repo_id, "lag-llama.ckpt")
    device = torch.device(device_name)

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    hyper_parameters = checkpoint.get("hyper_parameters", {})
    model_kwargs = hyper_parameters.get("model_kwargs", {})
    trained_context_length = int(model_kwargs.get("context_length") or hyper_parameters.get("context_length") or 32)
    rope_scaling = None
    if context_length > trained_context_length and os.environ.get("LAG_LLAMA_ROPE_SCALING", "1") != "0":
        rope_scaling = {
            "type": "linear",
            "factor": max(1.0, context_length / trained_context_length),
        }

    estimator = LagLlamaEstimator(
        ckpt_path=checkpoint_path,
        prediction_length=prediction_length,
        context_length=context_length,
        input_size=int(model_kwargs.get("input_size") or 1),
        n_layer=int(model_kwargs.get("n_layer") or 8),
        n_embd_per_head=int(model_kwargs.get("n_embd_per_head") or 16),
        n_head=int(model_kwargs.get("n_head") or 9),
        scaling=model_kwargs.get("scaling") or "robust",
        time_feat=bool(model_kwargs.get("time_feat", True)),
        dropout=float(model_kwargs.get("dropout") or 0.0),
        num_parallel_samples=num_samples,
        batch_size=min(32, max(1, len(contexts))),
        rope_scaling=rope_scaling,
        device=device,
    )
    dataset = ListDataset(
        [
            {
                "start": pd.Period("2000-01-01", freq=freq),
                "target": [float(value) for value in context["prices"]],
            }
            for context in contexts
        ],
        freq=freq,
    )
    transformation = estimator.create_transformation()
    original_torch_load = torch.load

    def trusted_checkpoint_load(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("weights_only", False)
        return original_torch_load(*args, **kwargs)

    torch.load = trusted_checkpoint_load
    try:
        module = estimator.create_lightning_module(use_kv_cache=False)
    finally:
        torch.load = original_torch_load
    module.eval()
    predictor = estimator.create_predictor(transformation, module)
    forecasts = list(predictor.predict(dataset))
    final_prices = [_point_forecast(forecast) for forecast in forecasts]
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


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: lag_llama_isolated_runner.py INPUT_JSON OUTPUT_JSON", file=sys.stderr)
        return 2
    input_path = Path(argv[1])
    output_path = Path(argv[2])
    os.environ.setdefault("MPLCONFIGDIR", str(input_path.parent / "matplotlib"))
    Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
    rows = run(json.loads(input_path.read_text()))
    output_path.write_text(json.dumps(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
