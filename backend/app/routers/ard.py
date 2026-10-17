"""ARD 관리 — 산출물 보관함 · 발행본 · 배포 이력 · 제출 패키지 · 보존 정책 · 요약."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ProcessDataset, User
from ..security import current_user, require_admin
from ..services import activity, ard

router = APIRouter()


def _download(content: bytes, filename: str, media_type: str) -> Response:
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename) or "download"
    disp = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    mt = media_type if media_type.startswith("application/zip") else f"{media_type}; charset=utf-8"
    return Response(content, media_type=mt, headers={"Content-Disposition": disp})


@router.get("/ard/summary")
def summary(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    return ard.summary(db)


@router.get("/ard/filters")
def filters(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    return ard.filters(db)


@router.get("/ard/artifacts")
def artifacts(page: int = 1, size: int = 20, q: str | None = None, process_id: int | None = None, kind: str | None = None, latest_only: bool = False,
              actor_id: int | None = None, org: str | None = None, sort: str = "created", db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    page, size = ard.page_args(page, size)
    items = ard.artifact_items(db, process_id=process_id, kind=kind, q=q, latest_only=latest_only, actor_id=actor_id, org=org, sort=sort)
    if user.role == "viewer":
        for i in items:
            i["can_download"] = i["viewer_allowed"]
    else:
        for i in items:
            i["can_download"] = True
    return ard.paginate(items, page, size)


@router.get("/ard/download")
def download(kind: str, id: int, dataset_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Response:
    got = ard.fetch_file(db, kind, id, dataset_id)
    if got is None:
        raise HTTPException(404, "내려받을 산출물이 없습니다")
    content, filename, media_type, meta = got
    if user.role == "viewer" and not ard.viewer_allowed(meta.get("grade")):
        raise HTTPException(403, "열람 전용 계정은 O(공개) 등급 산출물만 내려받을 수 있습니다")
    activity.log(db, "artifact_download", f"산출물 다운로드 — {filename}", user=user, process_id=meta.get("process_id"), dataset_id=meta.get("dataset_id"),
                 payload={"kind": kind, "id": id, "dataset_id": dataset_id, "filename": filename, "size": len(content), "sha256": ard.sha256(content), "grade": meta.get("grade"), "run_id": meta.get("run_id")})
    db.commit()
    return _download(content, filename, media_type)


@router.get("/ard/datasets/{did}/package")
def package(did: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Response:
    pd = db.get(ProcessDataset, did)
    if pd is None:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다")
    got = ard.build_package(db, pd)
    if got is None:
        raise HTTPException(409, "이 데이터셋의 변환 산출물(JSON-LD)이 없습니다 — STEP 7 변환을 먼저 실행하세요")
    content, filename, manifest = got
    if user.role == "viewer" and not ard.viewer_allowed(manifest["n2sf"]["grade"]):
        raise HTTPException(403, "열람 전용 계정은 O(공개) 등급 산출물만 내려받을 수 있습니다")
    activity.log(db, "package_download", f"제출 패키지 다운로드 — {manifest['title']}", user=user, process_id=pd.process_id, dataset_id=pd.id,
                 payload={"filename": filename, "files": [f["file"] for f in manifest["files"]], "resource_id": manifest["resource_id"], "sha256": ard.sha256(content), "size": len(content)})
    db.commit()
    return _download(content, filename, "application/zip")


@router.get("/ard/datasets/{did}/package/manifest")
def package_manifest(did: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    pd = db.get(ProcessDataset, did)
    if pd is None:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다")
    got = ard.build_package(db, pd)
    if got is None:
        raise HTTPException(409, "이 데이터셋의 변환 산출물(JSON-LD)이 없습니다 — STEP 7 변환을 먼저 실행하세요")
    return got[2]


@router.get("/ard/published")
def published(page: int = 1, size: int = 20, q: str | None = None, status: str | None = None, kind: str | None = None, actor_id: int | None = None,
              org: str | None = None, sort: str = "created", db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    page, size = ard.page_args(page, size)
    return ard.paginate(ard.published_items(db, q=q, status=status, kind=kind, actor_id=actor_id, org=org, sort=sort), page, size)


@router.get("/ard/history")
def history(page: int = 1, size: int = 20, type: str | None = None, actor_id: int | None = None, org: str | None = None, q: str | None = None,
            sort: str = "created", format: str | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    items = ard.history_items(db, type_=type, actor_id=actor_id, org=org, q=q, sort=sort)
    if format == "csv":
        return _download(ard.history_csv(items).encode("utf-8"), "ARD_배포이력.csv", "text/csv")
    page, size = ard.page_args(page, size)
    return ard.paginate(items, page, size)


@router.get("/ard/retention")
def retention(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    c = ard.retention_candidates(db)
    return {"candidates": c, "keep": ard.get_settings().artifact_keep_runs, "size": sum(x["size"] for x in c)}


@router.post("/ard/retention/apply")
def retention_apply(db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, Any]:
    r = ard.apply_retention(db, user)
    db.commit()
    return r
