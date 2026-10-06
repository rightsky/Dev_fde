"""업로드 원본 보관 (로컬 볼륨). 내용 해시(SHA-256)를 키로 쓴다."""
from __future__ import annotations

import hashlib
from pathlib import Path

from ..config import get_settings


def root() -> Path:
    p = get_settings().storage_dir
    p.mkdir(parents=True, exist_ok=True)
    return p


def save(data: bytes) -> tuple[str, str]:
    """(storage_key, sha256)"""
    digest = hashlib.sha256(data).hexdigest()
    key = f"{digest[:2]}/{digest}"
    path = root() / key
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return key, digest


def path_of(key: str) -> Path:
    p = (root() / key).resolve()
    if root().resolve() not in p.parents:
        raise ValueError("잘못된 저장 경로")
    return p
