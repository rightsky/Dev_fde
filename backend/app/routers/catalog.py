"""발행본(CatalogEntry) 조회 · 철회 · 복원과 HOME 대시보드. 화면은 ARD 관리(routers/ard.py)가 맡는다."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Activity, Asset, CatalogEntry, MintRecord, Process, ProcessDataset, User, utcnow
from ..security import current_user, require_admin
from ..serializers import activity_out, catalog_out, process_out
from ..services import activity, gates

router = APIRouter()


@router.get("/catalog")
def list_catalog(q: str | None = None, kind: str | None = None, status: str = "published", process_id: int | None = None,
                 db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    """발행본 목록 (간단 검색). 패싯 화면은 v0.18 에서 ARD 관리로 대체되었고, 이 목록은 STEP 7 · 검수 큐가 발행 ID 를 찾을 때 쓴다."""
    stmt = select(CatalogEntry).order_by(CatalogEntry.published_at.desc())
    if status in ("published", "withdrawn"):
        stmt = stmt.where(CatalogEntry.status == status)
    if kind in ("dataset", "stream"):
        stmt = stmt.where(CatalogEntry.kind == kind)
    if process_id is not None:
        stmt = stmt.where(CatalogEntry.process_id == process_id)
    for term in (q or "").lower().split():
        stmt = stmt.where(CatalogEntry.search_text.contains(term, autoescape=True))
    rows = db.scalars(stmt).all()
    return {"total": len(rows), "items": [catalog_out(e) for e in rows]}


def _entry(db: Session, resource_id: str) -> CatalogEntry:
    e = db.scalar(select(CatalogEntry).where(CatalogEntry.resource_id == resource_id))
    if e is None:
        raise HTTPException(404, "카탈로그 항목을 찾을 수 없습니다")
    return e


@router.get("/catalog/{resource_id}")
def get_entry(resource_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    from ..services import catalog as catalog_svc

    e = _entry(db, resource_id)
    pd_id = db.scalar(select(ProcessDataset.id).where(ProcessDataset.process_id == e.process_id, ProcessDataset.asset_id == e.asset_id)) if e.process_id else None
    return {**catalog_out(e, detail=True), "documents": catalog_svc.documents_for(db, e), "dataset_id": pd_id}


@router.get("/catalog/{resource_id}/raw")
def raw_entry(resource_id: str, format: str = "ttl", db: Session = Depends(get_db), _: User = Depends(current_user)) -> Response:
    e = _entry(db, resource_id)
    from ..services import catalog as catalog_svc

    if format in catalog_svc.DOC_FORMATS:
        body = catalog_svc.documents_for(db, e).get(format)
        if body is None:
            raise HTTPException(404, "이 발행본에는 해당 문서 산출물이 없습니다 (이전 판에서 발행됨)")
        mt, suffix = catalog_svc.DOC_FORMATS[format]
        return Response(body.encode("utf-8"), media_type=f"{mt}; charset=utf-8",
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(e.resource_id + '_' + suffix)}"})
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
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    from ..services import scope

    def count(model, *where) -> int:
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    mine = [] if scope.sees_all(user) else [Process.created_by == user.id]  # 작업자는 자기 프로세스만 센다
    procs = db.scalars(scope.restrict(select(Process).where(Process.status != "trashed"), user).order_by(Process.updated_at.desc()).limit(8)).all()
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
            "processes_active": count(Process, Process.status == "active", *mine),
            "processes_completed": count(Process, Process.status == "completed", *mine),
            "catalog_published": count(CatalogEntry, CatalogEntry.status == "published"),
            "minted": count(MintRecord),
            "activities": count(Activity),
        },
        "recent_processes": recent,
        "recent_activities": [activity_out(a) for a in db.scalars(select(Activity).order_by(Activity.id.desc()).limit(12))],
        "now": utcnow(),
    }
