"""AI 에이전트(MCP) 접근 관리: 키 발급·검증, 접근 범위, 호출 이력.

가이드라인 3.4.5 「MCP 연계 관리 원칙」(표 39)을 이렇게 반영한다.
- 접근 범위 명확화 · 최소권한: 키마다 접근할 수 있는 N²SF 등급(O · S)과 쓸 수 있는 도구를 정한다. C 등급은 어떤 키로도 열지 않는다.
- 조회형 기능 우선: 도구는 모두 읽기 전용이다. 발행된 카탈로그 항목만 보인다.
- 이력 관리: 모든 호출(거부 포함)을 agent_call 에 남긴다.
- 고위험 행위 승인: 키 발급·폐기는 관리자만 하고 prov:Activity 로 기록한다.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AgentCall, AgentKey, CatalogEntry, utcnow

GRADES = ["O", "S"]  # 키에 줄 수 있는 등급. C(통제)는 에이전트 접근 대상이 아니다
TOOLS = ["search_datasets", "get_dataset", "get_metadata", "get_schema", "get_data_card", "get_usage_terms"]
KEY_PREFIX = "fde_"


class AccessDenied(Exception):
    """에이전트 요청 거부 (이력에는 denied 로 남는다)."""


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def bearer(headers: Any) -> str | None:
    if not headers:
        return None
    value = headers.get("authorization") or headers.get("Authorization") or ""
    return value[7:].strip() if value.lower().startswith("bearer ") else None


def find_key(db: Session, raw: str | None) -> AgentKey | None:
    """유효한 키(폐기·만료되지 않음)만 돌려준다."""
    if not raw or not raw.startswith(KEY_PREFIX):
        return None
    k = db.scalar(select(AgentKey).where(AgentKey.key_hash == hash_key(raw)))
    if k is None or k.revoked_at is not None:
        return None
    if k.expires_at is not None and k.expires_at <= utcnow():
        return None
    return k


def entry_grade(e: CatalogEntry) -> str:
    """등급 미지정은 보수적으로 S 로 본다 (STEP 4 N²SF 규칙과 같다)."""
    return str((e.facets or {}).get("n2sf") or "S").replace("N2SF-", "")


def visible(e: CatalogEntry, key: AgentKey) -> bool:
    g = entry_grade(e)
    return e.status == "published" and g != "C" and g in (key.grades or [])


def calls_today(db: Session, key: AgentKey) -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return db.scalar(select(func.count(AgentCall.id)).where(AgentCall.key_id == key.id, AgentCall.at >= start)) or 0


class CallRecord:
    def __init__(self) -> None:
        self.resource_ids: list[str] = []
        self.message: str | None = None


@contextmanager
def tool_call(db: Session, headers: Any, tool: str, arguments: dict[str, Any]) -> Iterator[tuple[AgentKey, CallRecord]]:
    """도구 호출 1건: 키 확인 → 도구·호출량 확인 → 실행 → 이력 기록. 거부·오류도 기록한다."""
    started = time.monotonic()
    key = find_key(db, bearer(headers))
    rec = CallRecord()
    status = "ok"
    try:
        if key is None:
            raise AccessDenied("유효한 에이전트 키가 아닙니다")
        if key.tools and tool not in key.tools:
            raise AccessDenied(f"이 키로는 {tool} 도구를 쓸 수 없습니다")
        if calls_today(db, key) >= key.daily_limit:
            raise AccessDenied(f"하루 호출 상한({key.daily_limit}건)을 넘었습니다")
        yield key, rec
    except AccessDenied as exc:
        status, rec.message = "denied", str(exc)
        raise
    except Exception as exc:  # noqa: BLE001 - 이력에 남기고 그대로 올린다
        status, rec.message = "error", str(exc)[:500]
        raise
    finally:
        args = {k: (v[:200] if isinstance(v, str) else v) for k, v in arguments.items()}
        db.add(AgentCall(key_id=key.id if key else None, key_label=(f"{key.name} ({key.prefix}…)" if key else "(키 없음)"),
                         tool=tool, arguments=args, resource_ids=rec.resource_ids[:50], status=status, message=rec.message,
                         duration_ms=int((time.monotonic() - started) * 1000)))
        if key is not None:
            key.last_used_at = utcnow()
        db.commit()


def usage_stats(db: Session, days: int = 30) -> dict[int, dict[str, int]]:
    since = utcnow() - timedelta(days=days)
    rows = db.execute(select(AgentCall.key_id, AgentCall.status, func.count(AgentCall.id))
                      .where(AgentCall.at >= since, AgentCall.key_id.is_not(None))
                      .group_by(AgentCall.key_id, AgentCall.status)).all()
    out: dict[int, dict[str, int]] = {}
    for key_id, status, n in rows:
        out.setdefault(key_id, {"ok": 0, "denied": 0, "error": 0})[status] = n
    return out


def exposure(db: Session, entry: CatalogEntry | None, days: int = 30) -> dict[str, Any] | None:
    """발행 항목 1건이 에이전트에게 열려 있는지와 최근 호출 수 (STEP 8 원칙 10 의 자동 증빙)."""
    if entry is None or entry.status != "published":
        return None
    keys = [k for k in db.scalars(select(AgentKey).where(AgentKey.revoked_at.is_(None)))
            if (k.expires_at is None or k.expires_at > utcnow()) and visible(entry, k)]
    if not keys:
        return None
    since = utcnow() - timedelta(days=days)
    calls = [c for c in db.scalars(select(AgentCall).where(AgentCall.at >= since)) if entry.resource_id in (c.resource_ids or [])]
    return {"keys": len(keys), "calls": len(calls), "denied": sum(1 for c in calls if c.status == "denied"), "grade": entry_grade(entry)}
