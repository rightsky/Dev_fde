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
from . import ratelimit

GRADES = ["O", "S1", "S2"]  # 키에 줄 수 있는 등급 (S 는 S1 조건부 공유 · S2 제한 공유로 세분화). C(비공개)는 에이전트 접근 대상이 아니다
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
    """등급 미지정은 보수적으로 S2 로 본다 (STEP 4 N²SF 규칙과 같다). 세분화 전 'S' 도 S2."""
    g = str((e.facets or {}).get("n2sf") or "S2").replace("N2SF-", "")
    return "S2" if g == "S" else g


def key_grades(key: AgentKey) -> set[str]:
    g = set(key.grades or [])
    if "S" in g:  # 세분화 전 키
        g |= {"S1", "S2"}
    return g


def entry_visibility(e: CatalogEntry) -> str:
    """메타데이터 공개 수준: detail(상세) · listing(목록만) · internal(비노출). 발행 시점 facet, 없으면 C 는 internal."""
    v = (e.facets or {}).get("meta_visibility")
    if v in ("listing", "detail", "internal"):
        return str(v)
    return "internal" if entry_grade(e) == "C" else "detail"


def has_grant(e: CatalogEntry, key: AgentKey) -> bool:
    """S2(제한 공유) 발행본에 대한 이 키의 유효한 건별 승인이 있는지."""
    from sqlalchemy.orm import object_session

    from ..models import AgentGrant

    db = object_session(e) or object_session(key)
    if db is None or key.id is None:
        return False
    now = utcnow()
    for gr in db.scalars(select(AgentGrant).where(AgentGrant.key_id == key.id, AgentGrant.resource_id == e.resource_id)):
        if gr.revoked_at is None and (gr.expires_at is None or gr.expires_at > now):
            return True
    return False


def visible(e: CatalogEntry, key: AgentKey) -> bool:
    """에이전트에게 상세를 보여도 되는 발행 항목인지: 발행 중 · C 등급 아님 · 키의 등급 범위 안 · 공개 수준 detail · 전송 제외 아님.
    S2(제한 공유)는 키 등급에 더해 발행본 건별 승인(agent_grant)이 있어야 한다."""
    g = entry_grade(e)
    if (e.facets or {}).get("ai_excluded") or e.status != "published" or entry_visibility(e) != "detail":
        return False
    if g == "C" or g not in key_grades(key):
        return False
    if g == "S2" and not has_grant(e, key):
        return False
    return True


def listable(e: CatalogEntry, key: AgentKey) -> bool:
    """검색 결과에 넣어도 되는지: 상세가 보이는 항목, 또는 담당자가 '목록만 공개'로 정한 항목(등급과 무관하게 제목 · 기관 · 등급만).
    공개 수준 detail 인데 키 등급 밖이면 존재를 드러내지 않는다 (기존 원칙 유지)."""
    if (e.facets or {}).get("ai_excluded") or e.status != "published":
        return False
    return visible(e, key) or entry_visibility(e) == "listing"


def calls_today(db: Session, key: AgentKey) -> int:
    start = ratelimit.local_day_start()  # FDE_TIMEZONE 기준 자정 (기본 Asia/Seoul)
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
