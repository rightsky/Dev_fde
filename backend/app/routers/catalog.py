"""데이터 카탈로그(발행분) · 대시보드."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Activity, Asset, CatalogEntry, MintRecord, Process, User, utcnow
from ..security import current_user, require_admin
from ..serializers import activity_out, catalog_out, process_out
from ..services import activity, gates

router = APIRouter()


@router.get("/catalog")
def list_catalog(q: str | None = None, kind: str | None = None, theme: str | None = None, data_type: str | None = None,
                 status: str = "published", db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    stmt = select(CatalogEntry).order_by(CatalogEntry.published_at.desc())
    if status in ("published", "withdrawn"):
        stmt = stmt.where(CatalogEntry.status == status)
    if kind in ("dataset", "stream"):
        stmt = stmt.where(CatalogEntry.kind == kind)
    for term in (q or "").lower().split():
        stmt = stmt.where(CatalogEntry.search_text.contains(term))
    rows = db.scalars(stmt).all()
    # 패싯 집계는 필터 적용 전 결과 기준으로 한다 (선택지를 좁히지 않기 위함)
    themes: dict[str, int] = {}
    types: dict[str, int] = {}
    for e in rows:
        cls = (e.facets or {}).get("classification", {})
        for t in cls.get("theme", []):
            themes[t] = themes.get(t, 0) + 1
        for t in cls.get("dataType", []):
            types[t] = types.get(t, 0) + 1
    if theme:
        rows = [e for e in rows if theme in (e.facets or {}).get("classification", {}).get("theme", [])]
    if data_type:
        rows = [e for e in rows if data_type in (e.facets or {}).get("classification", {}).get("dataType", [])]
    return {"total": len(rows), "items": [catalog_out(e) for e in rows],
            "facets": {"theme": sorted(themes.items(), key=lambda x: -x[1]), "data_type": sorted(types.items(), key=lambda x: -x[1])}}


def _entry(db: Session, resource_id: str) -> CatalogEntry:
    e = db.scalar(select(CatalogEntry).where(CatalogEntry.resource_id == resource_id))
    if e is None:
        raise HTTPException(404, "카탈로그 항목을 찾을 수 없습니다")
    return e


@router.get("/catalog/{resource_id}")
def get_entry(resource_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    return catalog_out(_entry(db, resource_id), detail=True)


@router.get("/catalog/{resource_id}/raw")
def raw_entry(resource_id: str, format: str = "ttl", db: Session = Depends(get_db), _: User = Depends(current_user)) -> Response:
    e = _entry(db, resource_id)
    body, mt, ext = {"ttl": (e.turtle, "text/turtle", "ttl"), "jsonld": (e.jsonld, "application/ld+json", "jsonld"),
                     "txt": (e.text_summary or "", "text/plain", "txt"),
                     "schema": (e.schema_json or "", "application/json", "json")}.get(format, (e.turtle, "text/turtle", "ttl"))
    return Response(body.encode("utf-8"), media_type=f"{mt}; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{e.resource_id}.{ext}"'})


@router.post("/catalog/{resource_id}/withdraw")
def withdraw(resource_id: str, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, Any]:
    """발행 철회. 항목은 삭제하지 않고 상태만 바꾼다 (리니지 추적성 유지)."""
    e = _entry(db, resource_id)
    e.status = "withdrawn"
    activity.log(db, "withdraw", f"카탈로그 발행 철회 — {e.resource_id} {e.title}", user=user, process_id=e.process_id)
    db.commit()
    return catalog_out(e)


@router.post("/catalog/{resource_id}/restore")
def restore(resource_id: str, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, Any]:
    e = _entry(db, resource_id)
    e.status = "published"
    activity.log(db, "republish", f"카탈로그 발행 복원 — {e.resource_id} {e.title}", user=user, process_id=e.process_id)
    db.commit()
    return catalog_out(e)


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    def count(model, *where) -> int:  # noqa: ANN001
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    procs = db.scalars(select(Process).where(Process.status != "trashed").order_by(Process.updated_at.desc()).limit(8)).all()
    recent = []
    for p in procs:
        st = gates.state(db, p)
        o = process_out(p)
        o["steps_done"] = [g["step"] for g in st["gates"] if g["done"]]
        o["validation"] = st["validation"]
        recent.append(o)
    return {
        "counts": {
            "assets": count(Asset, Asset.deleted_at.is_(None)),
            "streams": count(Asset, Asset.deleted_at.is_(None), Asset.kind == "stream"),
            "processes_active": count(Process, Process.status == "active"),
            "processes_completed": count(Process, Process.status == "completed"),
            "catalog_published": count(CatalogEntry, CatalogEntry.status == "published"),
            "minted": count(MintRecord),
            "activities": count(Activity),
        },
        "recent_processes": recent,
        "recent_activities": [activity_out(a) for a in db.scalars(select(Activity).order_by(Activity.id.desc()).limit(12))],
        "now": utcnow(),
    }
