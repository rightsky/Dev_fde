"""ARD 관리 — ARD 스튜디오가 만든 산출물의 보관 · 배포 · 이력.

- 산출물 보관함: STEP 7 산출물 파일 · ZIP, STEP 6 검증 보고서, STEP 8 진단 보고서를 한 목록으로 (DB 에 있는 것을 모아 보인다)
- 발행본: 외부(MCP · 포털)에 내준 정본 (CatalogEntry)
- 배포 이력: 다운로드 · 발행 · 철회 · 복원 활동 로그
- 제출 패키지: 데이터셋 하나를 JSON-LD + 데이터 카드 + 데이터 사전 + manifest.json 으로 묶는다
- 보존 정책: 프로세스당 최신 N회차 변환만 보관 (발행본이 참조하는 회차는 예외)
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (Activity, AgentCall, AgentGrant, Artifact, CatalogEntry, DiagnosisRun, Process, ProcessDataset,
                      SerializationRun, User, ValidationRun, utcnow)
from . import gates, grading, serialize

PAGE_SIZES = (10, 20, 50, 100)
KINDS = {"file": "산출물 파일", "zip": "산출물 묶음(ZIP)", "validation": "검증 보고서", "diagnosis": "진단 보고서", "package": "제출 패키지"}
FORMAT_LABEL = {f["key"]: f["tag"] for f in serialize.FORMATS}
HISTORY_TYPES = {"artifact_download": "다운로드", "package_download": "제출 패키지", "publish": "발행", "withdraw": "철회", "republish": "복원",
                 "retention_apply": "보존 정리"}


def page_args(page: int | None, size: int | None) -> tuple[int, int]:
    s = size if size in PAGE_SIZES else 20
    return max(1, page or 1), s


def paginate(items: list[Any], page: int, size: int) -> dict[str, Any]:
    total = len(items)
    pages = max(1, (total + size - 1) // size)
    page = min(page, pages)
    return {"items": items[(page - 1) * size: page * size], "total": total, "page": page, "size": size, "pages": pages}


# ----------------------------------------------------------------- 공통: 작업자 · 조직 · 등급
def _users(db: Session) -> dict[int, User]:
    return {u.id: u for u in db.scalars(select(User)).all()}


def actor_of(users: dict[int, User], uid: int | None) -> dict[str, Any] | None:
    u = users.get(uid) if uid else None
    return {"id": u.id, "name": u.name, "org": u.org_label or None} if u else None


def _process_grade(p: Process) -> str | None:
    """프로세스 산출물(ZIP · 보고서)의 등급 = 조합 최고 등급 (미지정은 S2 취급)."""
    gs = [grading.normalize(grading.grade_of(d)) or "S2" for d in p.combo]
    return grading.GRADES[max(grading.rank(g) for g in gs)] if gs else None


def _dataset_grade(pd: ProcessDataset | None) -> str | None:
    return (grading.normalize(grading.grade_of(pd)) or "S2") if pd else None


def viewer_allowed(grade: str | None) -> bool:
    """열람 전용 계정은 O 등급 산출물만 내려받는다 (ARD 관리 결정 (b))."""
    return grade == "O"


# ----------------------------------------------------------------- 산출물 보관함
def artifact_items(db: Session, *, process_id: int | None = None, kind: str | None = None, q: str | None = None,
                   latest_only: bool = False, actor_id: int | None = None, org: str | None = None, sort: str = "created") -> list[dict[str, Any]]:
    users = _users(db)
    procs = {p.id: p for p in db.scalars(select(Process).where(Process.status != "trashed")).all()}
    if process_id is not None:
        procs = {k: v for k, v in procs.items() if k == process_id}
    pds = {d.id: d for d in db.scalars(select(ProcessDataset)).all()}
    items: list[dict[str, Any]] = []

    def base(kind_: str, p: Process, uid: int | None, at, grade: str | None, **extra) -> dict[str, Any]:
        a = actor_of(users, uid)
        return {"kind": kind_, "kind_label": KINDS[kind_], "process": {"id": p.id, "name": p.name, "status": p.status},
                "actor": a, "org": (a or {}).get("org"), "created_at": at, "grade": grade, "viewer_allowed": viewer_allowed(grade), **extra}

    # STEP 7 변환 회차: ZIP 한 건 + 산출물 파일들
    srs = db.scalars(select(SerializationRun).where(SerializationRun.process_id.in_(list(procs)) if procs else False)
                     .order_by(SerializationRun.id.desc())).all()
    latest_sr: dict[int, int] = {}
    for sr in srs:
        latest_sr.setdefault(sr.process_id, sr.id)
    for sr in srs:
        p = procs[sr.process_id]
        is_latest = latest_sr[sr.process_id] == sr.id
        pg = _process_grade(p)
        if sr.artifacts:
            items.append(base("zip", p, sr.triggered_by, sr.started_at, pg, id=sr.id, key=f"zip:{sr.id}", run_id=sr.id, mode=sr.mode,
                              dataset=None, format="zip", format_label="ZIP", filename=f"{_slug(p.name)}_산출물_{sr.id}.zip",
                              size=sum(a.size for a in sr.artifacts), sha256=None, latest=is_latest,
                              detail=f"{len(sr.artifacts)}개 파일 · 자가검증 통과 {sr.ok_count} · 실패 {sr.fail_count}"))
        for a in sr.artifacts:
            pd = pds.get(a.dataset_id)
            items.append(base("file", p, sr.triggered_by, sr.started_at, _dataset_grade(pd) or pg, id=a.id, key=f"file:{a.id}", run_id=sr.id, mode=sr.mode,
                              dataset={"id": a.dataset_id, "title": a.dataset_name}, format=a.fmt, format_label=FORMAT_LABEL.get(a.fmt, a.fmt),
                              filename=a.filename, size=a.size, sha256=a.sha256, latest=is_latest, detail=a.media_type))
    # STEP 6 검증 보고서 (데이터셋별 SHACL 보고서가 있는 것만)
    vrs = db.scalars(select(ValidationRun).where(ValidationRun.process_id.in_(list(procs)) if procs else False)
                     .order_by(ValidationRun.id.desc())).all()
    latest_vr: dict[int, int] = {}
    for vr in vrs:
        latest_vr.setdefault(vr.process_id, vr.id)
    for vr in vrs:
        p = procs[vr.process_id]
        for r in vr.results:
            if not getattr(r, "report_ttl", None):
                continue
            pd = pds.get(r.dataset_id)
            title = ((pd.meta or {}).get("title") if pd else None) or (pd.asset.name if pd else f"데이터셋 {r.dataset_id}")
            items.append(base("validation", p, vr.triggered_by, vr.started_at, _dataset_grade(pd) or _process_grade(p), id=vr.id, key=f"validation:{vr.id}:{r.dataset_id}",
                              run_id=vr.id, mode=vr.mode, dataset={"id": r.dataset_id, "title": title}, format="ttl", format_label="SHACL 보고서",
                              filename=f"{_slug(title)}_검증보고서_{vr.id}.ttl", size=len(r.report_ttl.encode("utf-8")), sha256=None,
                              latest=latest_vr[vr.process_id] == vr.id, detail=("적합" if getattr(r, "conforms", None) else "위반 있음") + f" · 게이트 {vr.mode}"))
    # STEP 8 진단 보고서
    drs = db.scalars(select(DiagnosisRun).where(DiagnosisRun.process_id.in_(list(procs)) if procs else False)
                     .order_by(DiagnosisRun.id.desc())).all()
    latest_dr: dict[int, int] = {}
    for dr in drs:
        latest_dr.setdefault(dr.process_id, dr.id)
    for dr in drs:
        p = procs[dr.process_id]
        items.append(base("diagnosis", p, dr.triggered_by, dr.started_at, _process_grade(p), id=dr.id, key=f"diagnosis:{dr.id}", run_id=dr.id, mode=None,
                          dataset=None, format="html", format_label="진단 보고서", filename=f"진단보고서_{_slug(p.name)}_{dr.id}.html", size=None, sha256=None,
                          latest=latest_dr[dr.process_id] == dr.id, detail=f"{dr.score:g} / {dr.max_score:g}점 · 규칙 {dr.ruleset_version}"))

    # 필터
    if kind in KINDS:
        items = [i for i in items if i["kind"] == kind]
    if latest_only:
        items = [i for i in items if i["latest"]]
    if actor_id is not None:
        items = [i for i in items if (i["actor"] or {}).get("id") == actor_id]
    if org:
        items = [i for i in items if (i["org"] or "") == org]
    for term in (q or "").lower().split():
        items = [i for i in items if term in " ".join(str(x) for x in [i["process"]["name"], (i["dataset"] or {}).get("title"), i["filename"], i["format_label"],
                                                                      (i["actor"] or {}).get("name"), i["org"]] if x).lower()]
    # 정렬: 기본 최신순. 작업자 · 조직으로 묶어 볼 때는 그 키로 먼저 정렬한다
    key_created = lambda i: i["created_at"]  # noqa: E731
    if sort == "actor":
        items.sort(key=lambda i: (((i["actor"] or {}).get("name") or "힣"), -i["created_at"].timestamp()))
    elif sort == "org":
        items.sort(key=lambda i: ((i["org"] or "힣"), -i["created_at"].timestamp()))
    else:
        items.sort(key=key_created, reverse=True)
    return items


def _slug(name: str) -> str:
    return re.sub(r"[^가-힣a-zA-Z0-9]+", "_", name or "").strip("_")[:40] or "item"


def fetch_file(db: Session, kind: str, id_: int, dataset_id: int | None = None) -> tuple[bytes, str, str, dict[str, Any]] | None:
    """(내용, 파일명, 미디어타입, 메타). 없으면 None."""
    if kind == "file":
        a = db.get(Artifact, id_)
        if a is None:
            return None
        p = db.get(Process, a.run.process_id)
        pd = db.get(ProcessDataset, a.dataset_id)
        return a.content.encode("utf-8"), a.filename, a.media_type, {"process_id": p.id if p else None, "dataset_id": a.dataset_id, "grade": _dataset_grade(pd) or (_process_grade(p) if p else None), "run_id": a.run_id}
    if kind == "zip":
        sr = db.get(SerializationRun, id_)
        if sr is None or not sr.artifacts:
            return None
        p = db.get(Process, sr.process_id)
        return serialize.build_zip(sr, p), f"{_slug(p.name)}_산출물_{sr.id}.zip", "application/zip", {"process_id": p.id, "dataset_id": None, "grade": _process_grade(p), "run_id": sr.id}
    if kind == "validation":
        vr = db.get(ValidationRun, id_)
        r = next((x for x in (vr.results if vr else []) if x.dataset_id == dataset_id), None)
        if r is None or not r.report_ttl:
            return None
        p = db.get(Process, vr.process_id)
        pd = db.get(ProcessDataset, dataset_id)
        title = ((pd.meta or {}).get("title") if pd else None) or (pd.asset.name if pd else f"dataset_{dataset_id}")
        return r.report_ttl.encode("utf-8"), f"{_slug(title)}_검증보고서_{vr.id}.ttl", "text/turtle", {"process_id": p.id, "dataset_id": dataset_id, "grade": _dataset_grade(pd) or _process_grade(p), "run_id": vr.id}
    if kind == "diagnosis":
        from .report import render_report

        dr = db.get(DiagnosisRun, id_)
        if dr is None:
            return None
        p = db.get(Process, dr.process_id)
        return render_report(p, dr).encode("utf-8"), f"진단보고서_{_slug(p.name)}_{dr.id}.html", "text/html", {"process_id": p.id, "dataset_id": None, "grade": _process_grade(p), "run_id": dr.id}
    return None


# ----------------------------------------------------------------- 제출 패키지
def build_package(db: Session, pd: ProcessDataset) -> tuple[bytes, str, dict[str, Any]] | None:
    """데이터셋 하나의 제출 패키지: 최신 변환 회차의 JSON-LD · Croissant · 데이터 카드 · 데이터 사전 + manifest.json."""
    sr = serialize.latest_run(db, pd.process_id)
    if sr is None:
        return None
    arts = {a.fmt: a for a in sr.artifacts if a.dataset_id == pd.id}
    if "jsonld" not in arts:
        return None
    entry = db.scalar(select(CatalogEntry).where(CatalogEntry.asset_id == pd.asset_id, CatalogEntry.process_id == pd.process_id))
    gst = grading.state(pd)
    title = (pd.meta or {}).get("title") or pd.asset.name
    want = ["jsonld", "croissant", "card", "dict", "ttl", "schema", "txt"]
    files = []
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for key in want:
            a = arts.get(key)
            if a is None:
                continue
            z.writestr(a.filename, a.content)
            files.append({"file": a.filename, "format": key, "label": FORMAT_LABEL.get(key, key), "media_type": a.media_type, "size": a.size, "sha256": a.sha256})
        manifest = {
            "package": "FDE Data Studio 제출 패키지", "version": 1, "generated_at": utcnow().isoformat(), "title": title,
            "resource_id": entry.resource_id if entry else None, "iri": entry.iri if entry else None,
            "published": {"status": entry.status, "version": entry.version, "at": entry.published_at.isoformat()} if entry else None,
            "process": {"id": pd.process.id, "name": pd.process.name}, "serialization_run": sr.id, "set_checksum": next(iter(arts.values())).set_checksum,
            "n2sf": {"grade": gst["grade"], "label": gst["grade_label"], "visibility": gst["visibility"], "share_prohibited": gst["prohibited"].get("labels", []) if isinstance(gst["prohibited"], dict) else []},
            "ai_assisted_fields": sorted(((pd.meta or {}).get("_ai_assisted") or {}).keys()),
            "files": files,
            "note": "파일 체크섬은 SHA-256. JSON-LD 가 정본이며 나머지는 같은 정본에서 변환한 것입니다",
        }
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return buf.getvalue(), f"{_slug(title)}_제출패키지_{sr.id}.zip", manifest


# ----------------------------------------------------------------- 발행본
def published_items(db: Session, *, q: str | None = None, status: str | None = None, kind: str | None = None,
                    actor_id: int | None = None, org: str | None = None, sort: str = "created") -> list[dict[str, Any]]:
    from ..serializers import catalog_out

    users = _users(db)
    stmt = select(CatalogEntry).order_by(CatalogEntry.published_at.desc())
    if status in ("published", "withdrawn"):
        stmt = stmt.where(CatalogEntry.status == status)
    if kind in ("dataset", "stream"):
        stmt = stmt.where(CatalogEntry.kind == kind)
    for term in (q or "").lower().split():
        stmt = stmt.where(CatalogEntry.search_text.contains(term, autoescape=True))
    rows = db.scalars(stmt).all()
    grants = dict(db.execute(select(AgentGrant.resource_id, func.count()).where(AgentGrant.revoked_at.is_(None)).group_by(AgentGrant.resource_id)).all())
    # 최근 MCP 호출: resource_ids JSON 에 담긴 발행 ID 를 최근 500건에서 훑는다
    last_call: dict[str, Any] = {}
    for c in db.scalars(select(AgentCall).where(AgentCall.status == "ok").order_by(AgentCall.id.desc()).limit(500)).all():
        for rid in c.resource_ids or []:
            last_call.setdefault(rid, c.at)
    out = []
    for e in rows:
        a = actor_of(users, e.published_by)
        o = catalog_out(e)
        f = e.facets or {}
        o.update({"actor": a, "org": (a or {}).get("org"), "grade": f.get("n2sf"), "visibility": f.get("meta_visibility"), "readiness": f.get("readiness"),
                  "s2_grants": int(grants.get(e.resource_id, 0)), "last_mcp_call": last_call.get(e.resource_id),
                  "mcp_exposed": e.status == "published" and f.get("meta_visibility") != "internal" and not f.get("ai_excluded") and f.get("n2sf") != "C"})
        out.append(o)
    if actor_id is not None:
        out = [o for o in out if (o["actor"] or {}).get("id") == actor_id]
    if org:
        out = [o for o in out if (o["org"] or "") == org]
    if sort == "actor":
        out.sort(key=lambda o: (((o["actor"] or {}).get("name") or "힣"), -o["published_at"].timestamp()))
    elif sort == "org":
        out.sort(key=lambda o: ((o["org"] or "힣"), -o["published_at"].timestamp()))
    return out


# ----------------------------------------------------------------- 배포 이력
def history_items(db: Session, *, type_: str | None = None, actor_id: int | None = None, org: str | None = None, q: str | None = None,
                  sort: str = "created") -> list[dict[str, Any]]:
    users = _users(db)
    types = [type_] if type_ in HISTORY_TYPES else list(HISTORY_TYPES)
    rows = db.scalars(select(Activity).where(Activity.type.in_(types)).order_by(Activity.id.desc()).limit(5000)).all()
    out = []
    for a in rows:
        actor = actor_of(users, a.actor_id) or {"id": None, "name": a.actor_label, "org": None}
        out.append({"id": a.id, "code": a.code, "type": a.type, "type_label": HISTORY_TYPES.get(a.type, a.type), "text": a.text, "actor": actor,
                    "org": actor.get("org"), "process_id": a.process_id, "at": a.started_at, "payload": a.payload or {}})
    if actor_id is not None:
        out = [o for o in out if o["actor"].get("id") == actor_id]
    if org:
        out = [o for o in out if (o["org"] or "") == org]
    for term in (q or "").lower().split():
        out = [o for o in out if term in (o["text"] + " " + (o["actor"].get("name") or "") + " " + json.dumps(o["payload"], ensure_ascii=False)).lower()]
    if sort == "actor":
        out.sort(key=lambda o: ((o["actor"].get("name") or "힣"), -o["at"].timestamp()))
    elif sort == "org":
        out.sort(key=lambda o: ((o["org"] or "힣"), -o["at"].timestamp()))
    return out


def history_csv(items: list[dict[str, Any]]) -> str:
    import csv

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["시각", "구분", "내용", "작업자", "작업조직", "프로세스", "상세"])
    for o in items:
        w.writerow([o["at"].isoformat(), o["type_label"], o["text"], o["actor"].get("name") or "", o["org"] or "", o["process_id"] or "",
                    json.dumps(o["payload"], ensure_ascii=False)])
    return "﻿" + buf.getvalue()


# ----------------------------------------------------------------- 보존 정책
def retention_candidates(db: Session) -> list[dict[str, Any]]:
    """프로세스당 최신 N회차를 넘는 변환 회차 가운데, 발행본이 참조하지 않는 것."""
    keep = max(1, get_settings().artifact_keep_runs)
    published_sums = {e.checksum for e in db.scalars(select(CatalogEntry).where(CatalogEntry.status == "published")).all()}
    out = []
    for p in db.scalars(select(Process)).all():
        srs = db.scalars(select(SerializationRun).where(SerializationRun.process_id == p.id).order_by(SerializationRun.id.desc())).all()
        for sr in srs[keep:]:
            if any(a.set_checksum in published_sums for a in sr.artifacts):
                continue
            out.append({"run_id": sr.id, "process": {"id": p.id, "name": p.name}, "started_at": sr.started_at, "files": len(sr.artifacts),
                        "size": sum(a.size for a in sr.artifacts)})
    return out


def apply_retention(db: Session, user: User | None) -> dict[str, Any]:
    from . import activity

    from ..models import ReviewRequest

    cands = retention_candidates(db)
    for c in cands:
        sr = db.get(SerializationRun, c["run_id"])
        if sr is not None:
            # SQLite 는 FK 의 SET NULL 을 보장하지 않으므로 참조를 직접 끊는다 (해당 진단 · 검수 요청은 어차피 "변환이 다시 실행됨" 상태)
            for dr in db.scalars(select(DiagnosisRun).where(DiagnosisRun.serialization_run_id == sr.id)).all():
                dr.serialization_run_id = None
            for rr in db.scalars(select(ReviewRequest).where(ReviewRequest.serialization_run_id == sr.id)).all():
                rr.serialization_run_id = None
            for a in list(sr.artifacts):
                db.delete(a)
            db.delete(sr)
    if cands:
        activity.log(db, "retention_apply", f"보존 정리 — 변환 회차 {len(cands)}건 삭제 (프로세스당 최신 {get_settings().artifact_keep_runs}회차 보관)", user=user,
                     payload={"runs": [c["run_id"] for c in cands], "keep": get_settings().artifact_keep_runs}, software=user is None)
    db.flush()
    return {"deleted": len(cands), "runs": [c["run_id"] for c in cands], "keep": get_settings().artifact_keep_runs}


# ----------------------------------------------------------------- 요약 · 재변환 필요
def stale_processes(db: Session) -> list[dict[str, Any]]:
    out = []
    for p in db.scalars(select(Process).where(Process.status == "active")).all():
        st = gates.state(db, p)
        s = st.get("serialization") or {}
        d = st.get("diagnosis") or {}
        if s.get("run_id") and s.get("stale"):
            out.append({"process": {"id": p.id, "name": p.name}, "step": 7, "reason": s["stale"]})
        elif d.get("run_id") and d.get("stale"):
            out.append({"process": {"id": p.id, "name": p.name}, "step": 8, "reason": d["stale"]})
    return out


def summary(db: Session) -> dict[str, Any]:
    now = utcnow()
    week = now - timedelta(days=7)
    arts = db.scalar(select(func.count()).select_from(Artifact)) or 0
    zips = db.scalar(select(func.count()).select_from(SerializationRun)) or 0
    diags = db.scalar(select(func.count()).select_from(DiagnosisRun)) or 0
    pubs = db.scalars(select(CatalogEntry).where(CatalogEntry.status == "published")).all()
    ready = sum(1 for e in pubs if (e.facets or {}).get("readiness") == "ai-ready")
    downloads = db.scalar(select(func.count()).select_from(Activity).where(Activity.type.in_(("artifact_download", "package_download")), Activity.started_at >= week)) or 0
    mcp30 = db.scalar(select(func.count()).select_from(AgentCall).where(AgentCall.status == "ok", AgentCall.at >= now - timedelta(days=30))) or 0
    stale = stale_processes(db)
    cands = retention_candidates(db)
    return {"artifacts": arts + zips + diags, "files": arts, "published": len(pubs), "ai_ready": ready, "withdrawn": db.scalar(select(func.count()).select_from(CatalogEntry).where(CatalogEntry.status == "withdrawn")) or 0,
            "downloads_7d": downloads, "mcp_calls_30d": mcp30, "stale": stale, "retention": {"candidates": len(cands), "size": sum(c["size"] for c in cands), "keep": get_settings().artifact_keep_runs},
            "page_sizes": list(PAGE_SIZES), "generated_at": now}


def filters(db: Session) -> dict[str, Any]:
    """목록의 작업자 · 작업조직 선택지."""
    users = db.scalars(select(User).order_by(User.name)).all()
    return {"actors": [{"id": u.id, "name": u.name, "org": u.org_label} for u in users],
            "orgs": sorted({u.org_label for u in users if u.org_label}),
            "kinds": [{"kind": k, "label": v} for k, v in KINDS.items() if k != "package"],
            "history_types": [{"type": k, "label": v} for k, v in HISTORY_TYPES.items()]}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
