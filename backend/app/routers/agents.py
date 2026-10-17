"""AI 에이전트(MCP) 키 관리 · 호출 이력 (관리자 전용)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AgentCall, AgentGrant, AgentKey, CatalogEntry, User, utcnow
from ..security import require_admin
from ..services import activity, agent

router = APIRouter()


def _iso(v: datetime | None) -> str | None:
    return v.isoformat() if v else None


def _key_out(k: AgentKey, stats: dict[str, int] | None = None) -> dict[str, Any]:
    now = utcnow()
    state = "revoked" if k.revoked_at else ("expired" if k.expires_at and k.expires_at <= now else "active")
    return {"id": k.id, "name": k.name, "purpose": k.purpose, "prefix": k.prefix, "grades": k.grades,
            "tools": k.tools or agent.TOOLS, "daily_limit": k.daily_limit, "state": state,
            "created_at": _iso(k.created_at), "expires_at": _iso(k.expires_at), "revoked_at": _iso(k.revoked_at),
            "last_used_at": _iso(k.last_used_at), "stats_30d": stats or {"ok": 0, "denied": 0, "error": 0},
            "s2_grants": sum(1 for g in getattr(k, "_grants", []) if g.revoked_at is None and (g.expires_at is None or g.expires_at > now))}


@router.get("/mcp-info")
def mcp_info(_: User = Depends(require_admin)) -> dict[str, Any]:
    from ..mcp_server import PATH, tool_list
    return {"path": PATH, "transport": "streamable-http", "tools": tool_list(), "grades": agent.GRADES}


@router.get("/agent-keys")
def list_keys(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[dict[str, Any]]:
    stats = agent.usage_stats(db)
    grants: dict[int, list[AgentGrant]] = {}
    for g in db.scalars(select(AgentGrant)):
        grants.setdefault(g.key_id, []).append(g)
    out = []
    for k in db.scalars(select(AgentKey).order_by(AgentKey.id.desc())):
        k._grants = grants.get(k.id, [])  # type: ignore[attr-defined]
        out.append(_key_out(k, stats.get(k.id)))
    return out


class KeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    purpose: str | None = Field(default=None, max_length=1000)
    grades: list[str] = Field(default_factory=lambda: ["O"])
    tools: list[str] = Field(default_factory=list)
    daily_limit: int = Field(default=1000, ge=1, le=100000)
    expires_days: int | None = Field(default=90, ge=1, le=3650)


@router.post("/agent-keys")
def create_key(body: KeyIn, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, Any]:
    grades = sorted(set(body.grades))
    if not grades or any(g not in agent.GRADES for g in grades):
        raise HTTPException(400, "접근 등급은 O(공개) · S1(조건부 공유) · S2(제한 공유) 중에서 하나 이상 고르세요. C(비공개)는 에이전트에게 열 수 없습니다. S2 는 발행본마다 건별 승인이 더 필요합니다")
    tools = [t for t in agent.TOOLS if t in set(body.tools)]
    if len(tools) != len(set(body.tools)):
        raise HTTPException(400, "알 수 없는 도구가 있습니다")
    raw = agent.new_key()
    k = AgentKey(name=body.name.strip(), purpose=(body.purpose or "").strip() or None, prefix=raw[:10],
                 key_hash=agent.hash_key(raw), grades=grades, tools=tools if len(tools) < len(agent.TOOLS) else [],
                 daily_limit=body.daily_limit, created_by=user.id,
                 expires_at=utcnow() + timedelta(days=body.expires_days) if body.expires_days else None)
    db.add(k)
    db.flush()
    activity.log(db, "agent_key_issue", f"AI 에이전트 키 발급 — {k.name} (등급 {'·'.join(grades)})", user=user,
                 payload={"agent_key_id": k.id, "grades": grades, "tools": k.tools or "all"})
    db.commit()
    return {**_key_out(k), "key": raw}


@router.post("/agent-keys/{key_id}/revoke")
def revoke_key(key_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, Any]:
    k = db.get(AgentKey, key_id)
    if k is None:
        raise HTTPException(404, "키가 없습니다")
    if k.revoked_at is None:
        k.revoked_at = utcnow()
        activity.log(db, "agent_key_revoke", f"AI 에이전트 키 폐기 — {k.name} ({k.prefix}…)", user=user,
                     payload={"agent_key_id": k.id})
        db.commit()
    return _key_out(k)


@router.get("/agent-calls")
def list_calls(key_id: int | None = None, status: str | None = None, limit: int = 100,
               db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[dict[str, Any]]:
    q = select(AgentCall).order_by(AgentCall.id.desc()).limit(max(1, min(limit, 500)))
    if key_id is not None:
        q = q.where(AgentCall.key_id == key_id)
    if status:
        q = q.where(AgentCall.status == status)
    return [{"id": c.id, "key_id": c.key_id, "key_label": c.key_label, "tool": c.tool, "arguments": c.arguments,
             "resource_ids": c.resource_ids, "status": c.status, "message": c.message, "duration_ms": c.duration_ms,
             "at": _iso(c.at)} for c in db.scalars(q)]


# ---------------------------------------------------------------- S2 건별 승인
def _grant_out(g: AgentGrant, titles: dict[str, str] | None = None) -> dict[str, Any]:
    now = utcnow()
    state = "revoked" if g.revoked_at else ("expired" if g.expires_at and g.expires_at <= now else "active")
    return {"id": g.id, "key_id": g.key_id, "resource_id": g.resource_id, "title": (titles or {}).get(g.resource_id), "note": g.note,
            "granted_by": g.granted_label, "granted_at": _iso(g.granted_at), "expires_at": _iso(g.expires_at), "revoked_at": _iso(g.revoked_at), "state": state}


def _key(db: Session, key_id: int) -> AgentKey:
    k = db.get(AgentKey, key_id)
    if k is None:
        raise HTTPException(404, "키가 없습니다")
    return k


@router.get("/agent-keys/{key_id}/grants")
def list_grants(key_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> dict[str, Any]:
    k = _key(db, key_id)
    grants = db.scalars(select(AgentGrant).where(AgentGrant.key_id == k.id).order_by(AgentGrant.id.desc())).all()
    titles = {e.resource_id: e.title for e in db.scalars(select(CatalogEntry))}
    # 승인 대상 후보: 발행 중인 S2 데이터셋 가운데 아직 유효한 승인이 없는 것
    active = {g.resource_id for g in grants if g.revoked_at is None and (g.expires_at is None or g.expires_at > utcnow())}
    candidates = [{"resource_id": e.resource_id, "title": e.title, "publisher": e.publisher_label}
                  for e in db.scalars(select(CatalogEntry).where(CatalogEntry.status == "published").order_by(CatalogEntry.resource_id))
                  if agent.entry_grade(e) == "S2" and agent.entry_visibility(e) == "detail" and e.resource_id not in active]
    return {"items": [_grant_out(g, titles) for g in grants], "candidates": candidates, "s2_allowed": "S2" in agent.key_grades(k)}


class GrantIn(BaseModel):
    resource_id: str = Field(min_length=3, max_length=40)
    note: str | None = Field(default=None, max_length=1000)
    expires_days: int | None = Field(default=180, ge=1, le=3650)


@router.post("/agent-keys/{key_id}/grants")
def create_grant(key_id: int, body: GrantIn, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, Any]:
    k = _key(db, key_id)
    if k.revoked_at:
        raise HTTPException(409, "폐기된 키에는 승인을 줄 수 없습니다")
    if "S2" not in agent.key_grades(k):
        raise HTTPException(409, "이 키는 S2 등급 접근이 없습니다 — 키 등급에 S2 가 있어야 건별 승인을 줄 수 있습니다")
    e = db.scalar(select(CatalogEntry).where(CatalogEntry.resource_id == body.resource_id.strip()))
    if e is None or e.status != "published":
        raise HTTPException(404, "발행 중인 데이터셋이 아닙니다")
    if agent.entry_grade(e) != "S2":
        raise HTTPException(422, f"{e.resource_id} 는 S2(제한 공유) 등급이 아닙니다 ({agent.entry_grade(e)}) — 건별 승인은 S2 에만 필요합니다")
    if not (body.note or "").strip():
        raise HTTPException(422, "승인 근거(협약 · 목적 · 승인 문서 번호 등)를 적으세요")
    g = AgentGrant(key_id=k.id, resource_id=e.resource_id, note=body.note.strip(), granted_by=user.id, granted_label=user.name,
                   expires_at=utcnow() + timedelta(days=body.expires_days) if body.expires_days else None)
    db.add(g)
    db.flush()
    activity.log(db, "agent_grant", f"S2 건별 승인 — 키 {k.name} → {e.resource_id} ({body.note.strip()[:60]})", user=user,
                 payload={"agent_key_id": k.id, "resource_id": e.resource_id, "grant_id": g.id, "expires_at": _iso(g.expires_at)})
    db.commit()
    return _grant_out(g, {e.resource_id: e.title})


@router.post("/agent-keys/{key_id}/grants/{gid}/revoke")
def revoke_grant(key_id: int, gid: int, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, Any]:
    g = db.get(AgentGrant, gid)
    if g is None or g.key_id != key_id:
        raise HTTPException(404, "승인이 없습니다")
    if g.revoked_at is None:
        g.revoked_at = utcnow()
        activity.log(db, "agent_grant_revoke", f"S2 건별 승인 회수 — 키 #{key_id} → {g.resource_id}", user=user,
                     payload={"agent_key_id": key_id, "resource_id": g.resource_id, "grant_id": g.id})
        db.commit()
    return _grant_out(g)
