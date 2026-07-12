#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "backend"


def main() -> int:
    checked = 0
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        if ".venv" in path.parts:
            continue
        ast.parse(path.read_text(), filename=str(path))
        checked += 1
    print(f"Python syntax OK ({checked} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
