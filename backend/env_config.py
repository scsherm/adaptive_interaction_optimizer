#!/usr/bin/env python3
"""Load `.env.local` / `.env` from the project root into the process environment.

This is the one place that resolves env-file locations. Keeping it central avoids
the failure it was written to fix, where a module looked for `.env.local` under
`backend/` instead of the repo root and silently ran without the key. Import this
module early and call `load_dotenv()` once per entrypoint.

Real environment variables always win -- a shell export overrides the file.
"""
from __future__ import annotations

import os
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent

# Repo root first, then backend/, so either location works.
ENV_FILES = (
    PROJECT_ROOT / ".env.local",
    PROJECT_ROOT / ".env",
    BACKEND_ROOT / ".env.local",
    BACKEND_ROOT / ".env",
)


def _parse(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def dotenv_values(paths: tuple[Path, ...] = ENV_FILES) -> dict[str, str]:
    """Merged contents of the env files. Earlier files take precedence."""
    values: dict[str, str] = {}
    for path in paths:
        if not path.exists():
            continue
        try:
            parsed = _parse(path.read_text())
        except OSError:
            continue
        for key, value in parsed.items():
            values.setdefault(key, value)
    return values


def load_dotenv(*, override: bool = False, paths: tuple[Path, ...] = ENV_FILES) -> list[str]:
    """Copy env-file values into os.environ. Returns the names that were set."""
    loaded = []
    for key, value in dotenv_values(paths).items():
        if override or not os.environ.get(key):
            os.environ[key] = value
            loaded.append(key)
    return loaded


def env_value(name: str, default: str = "") -> str:
    """Environment first, then the env files."""
    found = os.environ.get(name)
    if found:
        return found
    return dotenv_values().get(name, default)


def env_flag(name: str, default: bool = False) -> bool:
    value = env_value(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def status() -> dict[str, object]:
    """Which files exist and which interesting keys resolved -- never the values."""
    values = dotenv_values()
    interesting = ("OPENAI_API_KEY", "USE_LLM", "SEC_USER_AGENT", "ALPHA_VANTAGE_API_KEY")
    return {
        "files": [str(path) for path in ENV_FILES if path.exists()],
        "keys": {
            name: bool(os.environ.get(name) or values.get(name)) for name in interesting
        },
    }


if __name__ == "__main__":
    import json

    load_dotenv()
    print(json.dumps(status(), indent=2))
