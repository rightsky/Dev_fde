"""ARD 관리 — 산출물 보관함 · 발행본 · 배포 이력 · 제출 패키지 · 보존 정책 · 요약."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Process, ProcessDataset, ShareLink, User
from ..security import current_user, require_admin, require_writer
from ..services import activity, ard, ard_extra, scope

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
    allowed = scope.visible_process_ids(db, user)
    if allowed is not None:  # 작업자는 자기 프로세스의 산출물만
        items = [i for i in items if i["process"]["id"] in allowed]
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
    if not scope.visible(user, db.get(Process, meta["process_id"]) if meta.get("process_id") else None):
        raise HTTPException(404, "내려받을 산출물이 없습니다")
    if user.role == "viewer" and not ard.viewer_allowed(meta.get("grade")):
        raise HTTPException(403, "열람 전용 계정은 O(공개) 등급 산출물만 내려받을 수 있습니다")
    activity.log(db, "artifact_download", f"산출물 다운로드 — {filename}", user=user, process_id=meta.get("process_id"), dataset_id=meta.get("dataset_id"),
                 payload={"kind": kind, "id": id, "dataset_id": dataset_id, "filename": filename, "size": len(content), "sha256": ard.sha256(content), "grade": meta.get("grade"), "run_id": meta.get("run_id")})
    db.commit()
    return _download(content, filename, media_type)


@router.get("/ard/datasets/{did}/package")
def package(did: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Response:
    pd = db.get(ProcessDataset, did)
    if pd is None or not scope.visible(user, pd.process):
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
def package_manifest(did: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    pd = db.get(ProcessDataset, did)
    if pd is None or not scope.visible(user, pd.process):
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
            sort: str = "created", format: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    items = ard.history_items(db, type_=type, actor_id=actor_id, org=org, q=q, sort=sort)
    allowed = scope.visible_process_ids(db, user)
    if allowed is not None:  # 작업자는 자기 프로세스 · 자기 활동만
        items = [i for i in items if (i["process_id"] in allowed) or i["actor"].get("id") == user.id]
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


# ----------------------------------------------------------------- 버전 비교 (v0.19)
@router.get("/ard/datasets/{did}/versions")
def dataset_versions(did: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    pd = db.get(ProcessDataset, did)
    if pd is None or not scope.visible(user, pd.process):
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다")
    return {"dataset": {"id": pd.id, "title": (pd.meta or {}).get("title") or pd.asset.name}, "items": ard_extra.versions(db, pd)}


@router.get("/ard/datasets/{did}/diff")
def dataset_diff(did: int, from_ref: str, to_ref: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    pd = db.get(ProcessDataset, did)
    if pd is None or not scope.visible(user, pd.process):
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다")
    try:
        return ard_extra.diff(db, pd, from_ref, to_ref)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


# ----------------------------------------------------------------- 공유 링크 (v0.19)
class ShareIn(BaseModel):
    kind: str
    target_id: int
    dataset_id: int | None = None
    days: int = Field(default=7, ge=1, le=ard_extra.SHARE_MAX_DAYS)
    max_downloads: int = Field(default=10, ge=1, le=ard_extra.SHARE_MAX_DOWNLOADS)
    recipient: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=1000)


@router.get("/ard/share-links")
def share_links(state: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    from sqlalchemy import select

    rows = db.scalars(select(ShareLink).order_by(ShareLink.id.desc())).all()
    allowed = scope.visible_process_ids(db, user)
    if allowed is not None:
        rows = [r for r in rows if r.process_id in allowed or r.created_by == user.id]
    items = [ard_extra.out(r) for r in rows]
    if state in ("active", "expired", "revoked", "exhausted"):
        items = [i for i in items if i["state"] == state]
    return {"items": items, "max_days": ard_extra.SHARE_MAX_DAYS, "max_downloads": ard_extra.SHARE_MAX_DOWNLOADS, "grades": list(ard_extra.SHARE_GRADES)}


@router.post("/ard/share-links", status_code=201)
def share_create(body: ShareIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    if body.kind not in ard.KINDS:
        raise HTTPException(422, "알 수 없는 산출물 종류입니다")
    # 작업자는 자기 프로세스 산출물만
    if body.kind == "package":
        pd = db.get(ProcessDataset, body.target_id)
        if pd is None or not scope.visible(user, pd.process):
            raise HTTPException(404, "데이터셋을 찾을 수 없습니다")
    else:
        got = ard.fetch_file(db, body.kind, body.target_id, body.dataset_id)
        if got is None or not scope.visible(user, db.get(Process, got[3]["process_id"]) if got[3].get("process_id") else None):
            raise HTTPException(404, "산출물을 찾을 수 없습니다")
    try:
        link, token = ard_extra.create(db, user, kind=body.kind, target_id=body.target_id, dataset_id=body.dataset_id, days=body.days, max_downloads=body.max_downloads,
                                       recipient=body.recipient, note=body.note)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    activity.log(db, "share_create", f"공유 링크 생성 — {link.filename} ({link.grade} · {body.days}일 · {body.max_downloads}회" + (f" · {link.recipient}" if link.recipient else "") + ")",
                 user=user, process_id=link.process_id, dataset_id=link.dataset_id,
                 payload={"share_id": link.id, "kind": link.kind, "target_id": link.target_id, "filename": link.filename, "grade": link.grade, "expires_at": link.expires_at.isoformat(),
                          "max_downloads": link.max_downloads, "recipient": link.recipient, "token_prefix": link.token_prefix})
    db.commit()
    base = str(request.base_url).rstrip("/")
    # 토큰 원문은 이 응답에서 한 번만 준다. 화면 주소(/share/…)는 SPA 가 받아 /api/share/… 로 내려받는다
    return {**ard_extra.out(link), "url": f"{base}/share/{token}", "token": token}


@router.post("/ard/share-links/{sid}/revoke")
def share_revoke(sid: int, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    link = db.get(ShareLink, sid)
    if link is None:
        raise HTTPException(404, "공유 링크를 찾을 수 없습니다")
    if user.role != "admin" and link.created_by != user.id:
        raise HTTPException(403, "본인이 만든 링크만 회수할 수 있습니다")
    if link.revoked_at is None:
        link.revoked_at = ard.utcnow()
        activity.log(db, "share_revoke", f"공유 링크 회수 — {link.filename} ({link.token_prefix}…)", user=user, process_id=link.process_id, dataset_id=link.dataset_id,
                     payload={"share_id": link.id, "downloads": link.downloads})
        db.commit()
    return ard_extra.out(link)


# 공개 (로그인 없음): 링크 정보 · 내려받기. 토큰은 경로로만 받고 로그에는 앞 8자만 남긴다
@router.get("/share/{token}")
def share_info(token: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    link, why = ard_extra.resolve(db, token)
    if link is None:
        raise HTTPException(404, why)
    o = ard_extra.out(link)
    return {"filename": o["filename"], "kind_label": o["kind_label"], "grade": o["grade"], "expires_at": o["expires_at"], "remaining": max(0, link.max_downloads - link.downloads),
            "recipient": o["recipient"], "note": o["note"], "created_by": o["created_by"], "ok": why is None, "reason": why,
            "notice": "이 산출물은 FDE Data Studio 에서 발행한 메타데이터 산출물입니다. 내려받기는 기록됩니다."}


@router.get("/share/{token}/download")
def share_download(token: str, request: Request, db: Session = Depends(get_db)) -> Response:
    link, why = ard_extra.resolve(db, token)
    if link is None or why:
        raise HTTPException(410 if link else 404, why)
    got = ard_extra.fetch(db, link)
    if got is None:
        raise HTTPException(404, "산출물이 더 이상 없습니다 (보존 정리로 삭제되었을 수 있습니다)")
    content, filename, media_type = got
    link.downloads += 1
    link.last_downloaded_at = ard.utcnow()
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "") or "").split(",")[0].strip()
    activity.log(db, "share_download", f"공유 링크 다운로드 — {filename} ({link.token_prefix}… · {link.downloads}/{link.max_downloads})", user=None,
                 process_id=link.process_id, dataset_id=link.dataset_id,
                 payload={"share_id": link.id, "filename": filename, "size": len(content), "sha256": ard.sha256(content), "ip": ip, "recipient": link.recipient}, software=True)
    db.commit()
    return _download(content, filename, media_type)


# ----------------------------------------------------------------- 외부 정본 검사 (v0.20)
@router.post("/ard/check-external")
async def check_external(files: list[UploadFile] = File(...), mode: str = Form("draft"), db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """스튜디오 밖에서 만든 Turtle · JSON-LD 를 게이트 0 + SHACL 로 검사한다. 파일은 저장하지 않고 결과 요약만 활동 로그에 남긴다."""
    from ..services import extcheck

    mode = "publish" if mode == "publish" else "draft"
    results = []
    for f in files[:10]:
        name = (f.filename or "upload").replace("\\", "/").rsplit("/", 1)[-1]
        data = await f.read()
        if len(data) > extcheck.MAX_BYTES:
            results.append({"filename": name, "error": "5MB 를 초과합니다"})
            continue
        try:
            results.append(await run_in_threadpool(extcheck.check, name, data, mode))
        except Exception as exc:  # noqa: BLE001
            results.append({"filename": name, "error": f"{type(exc).__name__}: {exc}"[:300]})
    activity.log(db, "external_check", "외부 정본 검사 — " + ", ".join(f"{r['filename']}: {r.get('verdict') or r.get('error')}" for r in results)[:400], user=user,
                 payload={"mode": mode, "results": [{"filename": r["filename"], "verdict": r.get("verdict"), "error": r.get("error"), "triples": r.get("triples"),
                                                      "violations": (r.get("shacl") or {}).get("violations") if r.get("shacl") else None} for r in results]})
    db.commit()
    return {"mode": mode, "results": results}
