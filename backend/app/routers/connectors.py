"""데이터 패브릭 외부 연계: 기관 DB 스키마 커넥터 + 연계 현황판.

- 커넥터는 관리자가 등록 · 삭제, 작성자(worker)가 접속 시험 · 동기화.
- 비밀번호는 암호화 저장하고 어떤 응답에도 넣지 않는다.
- 연계 현황판은 읽기 전용: Claude API · MCP · DB 커넥터 세 연결의 켜짐 여부와 최근 사용 시각.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Activity, AgentCall, AgentKey, Asset, DbConnector, Organization, User, utcnow
from ..security import current_user, require_admin, require_writer
from ..services import activity, connectors

router = APIRouter()


class ConnectorIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: str
    host: str = Field(min_length=1, max_length=200)
    port: int | None = None
    database: str = Field(min_length=1, max_length=100)
    schema_name: str | None = Field(default=None, max_length=100, alias="schema")
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(default="", max_length=500)
    org_id: int | None = None
    note: str | None = None

    model_config = {"populate_by_name": True}


def _get(db: Session, cid: int) -> DbConnector:
    c = db.get(DbConnector, cid)
    if c is None or c.deleted_at is not None:
        raise HTTPException(404, "커넥터가 없습니다")
    return c


@router.get("/connectors")
def list_connectors(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    rows = db.scalars(select(DbConnector).where(DbConnector.deleted_at.is_(None)).order_by(DbConnector.id)).all()
    counts = dict(db.execute(select(Asset.connector_id, func.count()).where(Asset.deleted_at.is_(None), Asset.connector_id.is_not(None))
                             .group_by(Asset.connector_id)).all())
    items = []
    for c in rows:
        o = connectors.out(c)
        o["asset_count"] = int(counts.get(c.id, 0))
        o["org"] = {"id": c.org.id, "code": c.org.code, "label": c.org.label} if c.org else None
        items.append(o)
    return {"items": items, "kinds": [{"kind": k, **v} for k, v in connectors.KINDS.items()]}


@router.post("/connectors", status_code=201)
def create_connector(body: ConnectorIn, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, Any]:
    if body.kind not in connectors.KINDS:
        raise HTTPException(422, "지원하는 종류는 postgresql · mysql 입니다")
    if body.org_id is not None and db.get(Organization, body.org_id) is None:
        raise HTTPException(422, "기관이 없습니다")
    try:
        enc = connectors.encrypt(body.password)
    except connectors.ConnectorError as exc:
        raise HTTPException(503, str(exc)) from exc
    c = DbConnector(name=body.name.strip(), kind=body.kind, host=body.host.strip(), port=body.port or connectors.KINDS[body.kind]["port"],
                    database=body.database.strip(), db_schema=(body.schema_name or "").strip() or None, username=body.username.strip(),
                    secret_enc=enc, org_id=body.org_id, note=(body.note or "").strip() or None, created_by=user.id)
    db.add(c)
    db.flush()
    activity.log(db, "connector_create", f"DB 커넥터 등록: {c.name} ({c.kind} {c.host}:{c.port}/{c.database})", user=user,
                 payload={"connector_id": c.id, "kind": c.kind, "host": c.host, "database": c.database, "username": c.username})
    db.commit()
    return connectors.out(c)


@router.post("/connectors/{cid}/test")
async def test_connector(cid: int, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    c = _get(db, cid)
    try:
        result = await run_in_threadpool(connectors.test_connection, c, connectors.decrypt(c.secret_enc))
        c.status, c.last_error = "ok", None
    except connectors.ConnectorError as exc:
        c.status, c.last_error = "error", str(exc)[:400]
        result = {"ok": False, "error": c.last_error}
    except Exception as exc:  # noqa: BLE001 - DB 드라이버 오류는 종류가 많다
        c.status, c.last_error = "error", f"{type(exc).__name__}: {exc}"[:400]
        result = {"ok": False, "error": c.last_error}
    c.last_tested_at = utcnow()
    activity.log(db, "connector_test", f"DB 커넥터 접속 시험: {c.name} → {'성공' if result['ok'] else '실패'}", user=user,
                 payload={"connector_id": c.id, **{k: v for k, v in result.items() if k != "sample"}})
    db.commit()
    return {**result, "connector": connectors.out(c)}


@router.post("/connectors/{cid}/sync")
async def sync_connector(cid: int, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    c = _get(db, cid)
    try:
        result = await run_in_threadpool(connectors.sync, db, c, connectors.decrypt(c.secret_enc), user.id)
    except connectors.ConnectorError as exc:
        c.status, c.last_error, c.last_tested_at = "error", str(exc)[:400], utcnow()
        activity.log(db, "connector_sync", f"DB 스키마 동기화 실패: {c.name}", user=user, payload={"connector_id": c.id, "error": c.last_error})
        db.commit()
        raise HTTPException(502, c.last_error) from exc
    except Exception as exc:  # noqa: BLE001
        c.status, c.last_error, c.last_tested_at = "error", f"{type(exc).__name__}: {exc}"[:400], utcnow()
        activity.log(db, "connector_sync", f"DB 스키마 동기화 실패: {c.name}", user=user, payload={"connector_id": c.id, "error": c.last_error})
        db.commit()
        raise HTTPException(502, c.last_error) from exc
    c.last_tested_at = utcnow()
    activity.log(db, "connector_sync",
                 f"DB 스키마 동기화: {c.name} · 표 {result['tables']}개 (새 자산 {len(result['created'])} · 갱신 {len(result['updated'])})",
                 user=user, payload={"connector_id": c.id, **result}, software=False)
    db.commit()
    return {**result, "connector": connectors.out(c)}


@router.delete("/connectors/{cid}")
def delete_connector(cid: int, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, Any]:
    c = _get(db, cid)
    c.deleted_at = utcnow()
    c.secret_enc = ""  # 비밀번호는 즉시 지운다. 가져온 자산은 남는다 (connector_id 는 유지, 화면에는 "연결 끊김")
    activity.log(db, "connector_delete", f"DB 커넥터 삭제: {c.name}", user=user, payload={"connector_id": c.id})
    db.commit()
    return {"ok": True}


@router.get("/integrations")
def integrations(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    """외부 연계 현황판 (읽기 전용). N²SF 통제표 3절의 외부 연결 목록과 같은 순서."""
    s = get_settings()
    now = utcnow()

    def last_activity(types: tuple[str, ...]):
        return db.scalar(select(func.max(Activity.started_at)).where(Activity.type.in_(types)))

    ai_last = last_activity(("ai_draft", "ai_simulate"))
    ai_today = db.scalar(select(func.count()).select_from(Activity).where(Activity.type.in_(("ai_draft", "ai_simulate")),
                                                                            Activity.started_at >= now.replace(hour=0, minute=0, second=0, microsecond=0))) or 0
    keys = db.scalars(select(AgentKey).where(AgentKey.revoked_at.is_(None))).all()
    active_keys = [k for k in keys if k.expires_at is None or k.expires_at > now]
    mcp_last = db.scalar(select(func.max(AgentCall.at)))
    mcp_denied_24h = db.scalar(select(func.count()).select_from(AgentCall).where(AgentCall.status == "denied",
                                                                                 AgentCall.at >= now.replace(hour=0, minute=0, second=0, microsecond=0))) or 0
    conns = db.scalars(select(DbConnector).where(DbConnector.deleted_at.is_(None))).all()
    conn_assets = db.scalar(select(func.count()).select_from(Asset).where(Asset.deleted_at.is_(None), Asset.source == "dbschema")) or 0
    items = [
        {"key": "anthropic", "name": "Claude API (초안 제안 · 시뮬레이션)", "direction": "outbound",
         "enabled": bool(s.anthropic_api_key), "status": "on" if s.anthropic_api_key else "off",
         "detail": f"모델 {s.ai_model} · 분당 {s.ai_rate_per_minute} · 일일 {s.ai_rate_per_day}" if s.anthropic_api_key else "API 키 없음 — 외부 송신 없음",
         "last_at": ai_last, "today": int(ai_today),
         "scope": "O · S1 · S2 데이터셋의 컬럼명 · 통계 · 담당자 설명문만. C 등급 · 전송 제외 · 원본 값 미송신"},
        {"key": "mcp", "name": "MCP 서버 /api/mcp (외부 에이전트)", "direction": "inbound",
         "enabled": len(active_keys) > 0, "status": "on" if active_keys else "off",
         "detail": f"유효 키 {len(active_keys)}개 · 오늘 거부 {mcp_denied_24h}건" if keys else "발급된 키 없음",
         "last_at": mcp_last, "today": None,
         "scope": "키 등급 안의 발행본. S2 는 건별 승인, C 는 비노출"},
        {"key": "connectors", "name": "기관 DB 스키마 커넥터", "direction": "outbound",
         "enabled": len(conns) > 0, "status": ("error" if any(c.status == "error" for c in conns) else "on") if conns else "off",
         "detail": f"커넥터 {len(conns)}개 · 가져온 표 {conn_assets}개" if conns else "등록된 커넥터 없음",
         "last_at": max((c.last_synced_at for c in conns if c.last_synced_at), default=None), "today": None,
         "scope": "테이블 · 컬럼 · 자료형만 읽기 전용으로. 행 데이터 · 예시값 미수집"},
    ]
    return {"items": items, "api_docs_exposed": s.expose_api_docs, "generated_at": now}
