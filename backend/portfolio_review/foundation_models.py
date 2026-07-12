from __future__ import annotations

import os
from typing import Any


FOUNDATION_MODEL_REPOS = [
    "amazon/chronos-2",
    "autogluon/chronos-bolt-tiny",
    "autogluon/chronos-bolt-mini",
    "autogluon/chronos-bolt-small",
    "amazon/chronos-t5-small",
    "Salesforce/moirai-1.0-R-small",
    "time-series-foundation-models/Lag-Llama",
    "AutonLab/MOMENT-1-small",
    "ibm-granite/granite-timeseries-ttm-r2",
]

FOUNDATION_MODEL_NOTES = {
    "amazon/chronos-2": {
        "model_kind": "chronos_2",
        "runtime_package": "chronos",
        "research_status": "primary_candidate",
        "reason": "Newer Chronos family model with cross-series and covariate-aware forecasting support.",
    },
    "amazon/chronos-t5-small": {
        "model_kind": "chronos_t5_small",
        "runtime_package": "chronos",
        "research_status": "baseline_candidate",
        "reason": "Older Chronos zero-shot probabilistic forecaster; useful as a simpler foundation-model baseline.",
    },
    "autogluon/chronos-bolt-tiny": {
        "model_kind": "chronos_bolt_tiny",
        "runtime_package": "chronos",
        "research_status": "fast_candidate",
        "reason": "Chronos-Bolt is documented as faster and more memory-efficient than original Chronos.",
    },
    "autogluon/chronos-bolt-mini": {
        "model_kind": "chronos_bolt_mini",
        "runtime_package": "chronos",
        "research_status": "fast_candidate",
        "reason": "Mini Bolt provides a small CPU-friendly step up from tiny for zero-shot checks.",
    },
    "autogluon/chronos-bolt-small": {
        "model_kind": "chronos_bolt_small",
        "runtime_package": "chronos",
        "research_status": "fast_candidate",
        "reason": "Small Bolt is a size peer to Chronos T5-small and should be benchmarked directly.",
    },
    "Salesforce/moirai-1.0-R-small": {
        "model_kind": "moirai_small",
        "runtime_package": "uni2ts",
        "research_status": "tested_eligible_ctx64",
        "reason": "Uni2TS/GluonTS adapter is wired and ctx64 passed the anchored gate; non-commercial model license still limits use beyond local research.",
    },
    "time-series-foundation-models/Lag-Llama": {
        "model_kind": "lag_llama",
        "runtime_package": "lag_llama",
        "research_status": "tested_eligible_ctx32_isolated",
        "reason": "Zero-shot adapter is wired through an isolated GluonTS runner; ctx32 passed the anchored gate but is slower than interactive candidates.",
    },
    "AutonLab/MOMENT-1-small": {
        "model_kind": "moment_small",
        "runtime_package": "momentfm",
        "research_status": "tested_rejected_ctx512",
        "reason": "MOMENTPipeline runs at seq_len 512, but the anchored gate rejected it; package warns only the reconstruction head is pre-trained.",
    },
    "ibm-granite/granite-timeseries-ttm-r2": {
        "model_kind": "granite_ttm_r2",
        "runtime_package": "granite-tsfm",
        "research_status": "tested_eligible_ctx64",
        "reason": "Granite TinyTimeMixer adapter is wired with frequency tokens and ctx64 passed the anchored gate.",
    },
}


def env_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def foundation_model_candidates() -> list[dict[str, Any]]:
    if not env_enabled("USE_FOUNDATION_MODELS"):
        return []
    return [
        {
            "model_kind": FOUNDATION_MODEL_NOTES.get(repo, {}).get("model_kind", repo.split("/")[-1]),
            "repo_id": repo,
            "status": "configured_not_loaded",
            "authority": "tournament_candidate_only",
            **FOUNDATION_MODEL_NOTES.get(repo, {}),
        }
        for repo in FOUNDATION_MODEL_REPOS
    ]
