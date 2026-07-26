from __future__ import annotations

import json
import sys
from pathlib import Path
import urllib.error
import urllib.request
from typing import Any


# gpt-5.1-mini does not exist; this path would have 404'd the moment USE_LLM
# was turned on.
DEFAULT_MODEL = "gpt-5.4-mini"
ROOT = Path(__file__).resolve().parents[1]

# Env files live at the project root, not under backend/. This module used to
# look one directory too low, so USE_LLM and the API key never resolved.
sys.path.insert(0, str(ROOT))
from env_config import dotenv_values, env_flag, env_value  # noqa: E402


def read_local_env() -> dict[str, str]:
    return dotenv_values()


def load_llm_config() -> dict[str, Any]:
    api_key = env_value("OPENAI_API_KEY", "").strip()
    enabled = env_flag("USE_LLM", False) and bool(api_key)
    return {
        "enabled": enabled,
        "use_llm_env": env_value("USE_LLM", "false"),
        "model": env_value("OPENAI_MODEL", env_value("MODEL", DEFAULT_MODEL)).strip() or DEFAULT_MODEL,
        "has_api_key": bool(api_key),
        "provider": "openai",
        "authority": "csv_extraction_and_journal_context_only",
        "redacted_api_key": "present" if api_key else "missing",
    }


def extract_output_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    chunks: list[str] = []
    for item in response.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    chunks.append(content.get("text", ""))
    return "\n".join(chunk for chunk in chunks if chunk)


def call_openai_json(prompt: str, schema_name: str = "portfolio_review_context") -> dict[str, Any]:
    config = load_llm_config()
    api_key = env_value("OPENAI_API_KEY", "").strip()
    if not config["enabled"]:
        return {
            "enabled": False,
            "used": False,
            "model": config["model"],
            "result": {},
            "error": "LLM disabled. Set USE_LLM=true and OPENAI_API_KEY to enable testing.",
        }
    payload = {
        "model": config["model"],
        "instructions": (
            "You are assisting a paper-trading portfolio review system. "
            "Do not pick stocks or issue investment advice. Extract structured data, "
            "summarize evidence, and label intuition separately from evidence."
        ),
        "input": prompt,
        "text": {"format": {"type": "json_object"}},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"enabled": True, "used": False, "model": config["model"], "result": {}, "error": str(exc)}
    text = extract_output_text(data)
    try:
        parsed = json.loads(text) if text else {}
    except json.JSONDecodeError:
        parsed = {"raw_text": text}
    return {"enabled": True, "used": True, "model": config["model"], "result": parsed, "error": ""}
