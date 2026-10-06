"""정적 참조 데이터 (어휘·단계·수정 경로) 로더."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SHAPES_DIR = Path(__file__).resolve().parent.parent / "shapes"


@lru_cache
def vocab() -> dict[str, Any]:
    return json.loads((DATA_DIR / "vocab.json").read_text(encoding="utf-8"))


@lru_cache
def taxonomy_seed() -> dict[str, Any]:
    return json.loads((DATA_DIR / "taxonomy.json").read_text(encoding="utf-8"))


@lru_cache
def guideline_rules() -> dict[str, Any]:
    return json.loads((DATA_DIR / "guideline_rules.json").read_text(encoding="utf-8"))


def fix_route(key: str | None) -> dict[str, Any] | None:
    if not key:
        return None
    r = vocab()["fix_routes"].get(key)
    return {"key": key, **r} if r else None


def step_label(n: int) -> str:
    for s in vocab()["steps"]:
        if s["n"] == n:
            return s["label"]
    return f"STEP {n}"
