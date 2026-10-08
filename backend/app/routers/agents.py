"""AI 에이전트(MCP) 키 관리 · 호출 이력 (관리자 전용)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AgentCall, AgentKey, User, utcnow
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
            "last_used_at": _iso(k.last_used_at), "stats_30d": stats or {"ok": 0, "denied": 0, "error": 0}}


@router.get("/mcp-info")
def mcp_info(_: User = Depends(require_admin)) -> dict[str, Any]:
    from ..mcp_server import PATH, tool_list
    return {"path": PATH, "transport": "streamable-http", "tools": tool_list(), "grades": agent.GRADES}


@router.get("/agent-keys")
def list_keys(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[dict[str, Any]]:
    stats = agent.usage_stats(db)
    return [_key_out(k, stats.get(k.id)) for k in db.scalars(select(AgentKey).order_by(AgentKey.id.desc()))]


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
        raise HTTPException(400, "접근 등급은 O(공개) · S(민감) 중에서 하나 이상 고르세요. C(통제)는 에이전트에게 열 수 없습니다")
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
