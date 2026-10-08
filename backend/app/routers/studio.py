"""스튜디오 8단계 API: 프로세스 · 조합 · 메타데이터 · 분류 · 관계 · 검증 · 직렬화 · 진단."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (Artifact, Asset, Attestation, DiagnosisRun, Organization, Process, ProcessDataset, Relation,
                      SerializationRun, TaxonomyAxis, TaxonomyCode, User, ValidationRun, utcnow)
from ..security import current_user, require_admin, require_writer
from ..serializers import (activity_out, dataset_out, diagnosis_out, mint_out, process_out, serialization_out,
                           validation_out)
from ..services import (activity, canonical, catalog, diagnosis, gates, lineage, minting, serialize, suggest,
                        validation)
from ..services.reference import guideline_rules, vocab

router = APIRouter()


# ------------------------------------------------------------------ 공통 조회
def _process(db: Session, pid: int) -> Process:
    p = db.get(Process, pid)
    if p is None:
        raise HTTPException(404, "프로세스를 찾을 수 없습니다")
    return p


def _editable(db: Session, pid: int) -> Process:
    p = _process(db, pid)
    if p.status == "trashed":
        raise HTTPException(409, "휴지통에 있는 프로세스입니다 — 복원 후 수정하세요")
    if p.status == "completed":
        raise HTTPException(409, "종료된 프로세스입니다 — 다시 열기 후 수정하세요")
    return p


def _dataset(db: Session, did: int, editable: bool = True) -> ProcessDataset:
    pd = db.get(ProcessDataset, did)
    if pd is None:
        raise HTTPException(404, "데이터셋을 찾을 수 없습니다")
    if editable:
        _editable(db, pd.process_id)
    return pd


def _mode(p: Process) -> str:
    return "publish" if p.pub_mode else "draft"


def _detail(db: Session, p: Process) -> dict[str, Any]:
    mode = _mode(p)
    return {"process": process_out(p), "datasets": [dataset_out(db, d, mode) for d in p.datasets],
            "state": gates.state(db, p)}


# ------------------------------------------------------------------ 프로세스
class ProcessIn(BaseModel):
    name: str | None = Field(default=None, max_length=200)


@router.get("/processes")
def list_processes(status: str | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[dict[str, Any]]:
    stmt = select(Process).order_by(Process.updated_at.desc())
    if status == "trashed":
        stmt = stmt.where(Process.status == "trashed")
    elif status in ("active", "completed"):
        stmt = stmt.where(Process.status == status)
    else:
        stmt = stmt.where(Process.status != "trashed")
    out = []
    for p in db.scalars(stmt):
        o = process_out(p)
        st = gates.state(db, p)
        o["steps_done"] = [g["step"] for g in st["gates"] if g["done"]]
        o["dataset_names"] = [(d.meta or {}).get("title") or d.asset.name for d in p.combo][:8]
        out.append(o)
    return out


@router.post("/processes")
def create_process(body: ProcessIn, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    name = (body.name or "").strip()
    if not name:
        n = db.scalar(select(func.count()).select_from(Process)) or 0
        name = f"{n + 1}차 프로세스"
    p = Process(name=name, created_by=user.id)
    db.add(p)
    db.flush()
    activity.log(db, "process_create", f"프로세스 시작 — {name}", user=user, process_id=p.id)
    db.commit()
    return _detail(db, p)


@router.get("/processes/{pid}")
def get_process(pid: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    return _detail(db, _process(db, pid))


class ProcessPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    current_step: int | None = Field(default=None, ge=1, le=8)
    pub_mode: bool | None = None


@router.patch("/processes/{pid}")
def update_process(pid: int, body: ProcessPatch, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    p = _editable(db, pid)
    if body.name is not None:
        p.name = body.name.strip()
    if body.current_step is not None and body.current_step != p.current_step:
        ok, reason = gates.can_enter(db, p, body.current_step)
        if not ok:
            raise HTTPException(409, f"STEP {body.current_step} 잠김 — {reason}")
        p.current_step = body.current_step
    if body.pub_mode is not None and body.pub_mode != p.pub_mode:
        p.pub_mode = body.pub_mode
        activity.log(db, "pub_mode", f"발행 모드 {'전환' if p.pub_mode else '해제'} — {p.name}", user=user, process_id=p.id)
    p.updated_at = utcnow()
    db.commit()
    return _detail(db, p)


@router.post("/processes/{pid}/complete")
def complete_process(pid: int, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    p = _editable(db, pid)
    st = gates.state(db, p)
    if not st["serialization"]["done"]:
        raise HTTPException(409, "STEP 7 변환을 완료해야 프로세스를 종료할 수 있습니다")
    p.status, p.completed_at = "completed", utcnow()
    last = max((g["step"] for g in st["gates"] if g["done"]), default=7)
    activity.log(db, "process_complete", f"프로세스 종료 확정 — {p.name} (STEP {last} 완료)", user=user, process_id=p.id)
    db.commit()
    return _detail(db, p)


@router.post("/processes/{pid}/reopen")
def reopen_process(pid: int, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    p = _process(db, pid)
    if p.status != "completed":
        raise HTTPException(409, "종료된 프로세스만 다시 열 수 있습니다")
    p.status, p.completed_at = "active", None
    activity.log(db, "process_reopen", f"프로세스 다시 열기 — {p.name}", user=user, process_id=p.id)
    db.commit()
    return _detail(db, p)


@router.post("/processes/{pid}/trash")
def trash_process(pid: int, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    p = _process(db, pid)
    if p.status == "trashed":
        raise HTTPException(409, "이미 휴지통에 있습니다")
    p.status, p.trashed_at = "trashed", utcnow()
    activity.log(db, "process_trash", f"프로세스 휴지통 이동 — {p.name}", user=user, process_id=p.id)
    db.commit()
    return process_out(p)


@router.post("/processes/{pid}/restore")
def restore_process(pid: int, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    p = _process(db, pid)
    if p.status != "trashed":
        raise HTTPException(409, "휴지통에 있는 프로세스가 아닙니다")
    p.status, p.trashed_at = ("completed" if p.completed_at else "active"), None
    activity.log(db, "process_restore", f"프로세스 복원 — {p.name}", user=user, process_id=p.id)
    db.commit()
    return process_out(p)


@router.delete("/processes/{pid}")
def purge_process(pid: int, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, bool]:
    p = _process(db, pid)
    if p.status != "trashed":
        raise HTTPException(409, "휴지통으로 옮긴 프로세스만 영구 삭제할 수 있습니다")
    name = p.name
    for model in (DiagnosisRun, SerializationRun, ValidationRun, Attestation):
        for row in db.scalars(select(model).where(model.process_id == pid)).all():
            db.delete(row)
    db.flush()
    db.delete(p)
    activity.log(db, "process_purge", f"프로세스 영구 삭제 — {name} (카탈로그 발행분은 유지)", user=user)
    db.commit()
    return {"ok": True}


@router.get("/processes/{pid}/activities")
def process_activities(pid: int, limit: int = 30, db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[dict[str, Any]]:
    from ..models import Activity

    rows = db.scalars(select(Activity).where(Activity.process_id == pid).order_by(Activity.id.desc()).limit(min(limit, 200)))
    return [activity_out(a) for a in rows]


# ------------------------------------------------------------------ STEP 1 후보 선택 · 조합 추천
class SelectionIn(BaseModel):
    asset_ids: list[int]


@router.put("/processes/{pid}/selection")
def set_selection(pid: int, body: SelectionIn, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    p = _editable(db, pid)
    want = list(dict.fromkeys(body.asset_ids))
    assets = {a.id: a for a in db.scalars(select(Asset).where(Asset.id.in_(want), Asset.deleted_at.is_(None)))} if want else {}
    missing = [i for i in want if i not in assets]
    if missing:
        raise HTTPException(422, f"존재하지 않는 원천입니다: {missing}")
    have = {d.asset_id: d for d in p.datasets}
    removed_combo = []
    for aid, d in list(have.items()):
        if aid not in assets:
            if d.in_combo:
                removed_combo.append((d.meta or {}).get("title") or d.asset.name)
            for r in [r for r in p.relations if d.id in (r.source_id, r.target_id)]:
                p.relations.remove(r)
            p.datasets.remove(d)
    for pos, aid in enumerate(want):
        if aid in have:
            have[aid].selected = True
        else:
            p.datasets.append(ProcessDataset(asset_id=aid, selected=True, position=len(have) + pos))
    if removed_combo:
        activity.log(db, "combo_change", "후보 해제로 조합에서 제외 — " + ", ".join(removed_combo), user=user, process_id=p.id)
    p.updated_at = utcnow()
    db.commit()
    db.refresh(p)
    out = _detail(db, p)
    out["removed_from_combo"] = removed_combo
    return out


@router.get("/processes/{pid}/suggestions")
def combo_suggestions(pid: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    p = _process(db, pid)
    by_asset = {d.asset_id: d for d in p.datasets if d.selected}
    sugg = suggest.combo_suggestions([d.asset for d in by_asset.values()])
    for s in sugg:
        s["dataset_ids"] = [by_asset[a].id for a in s["asset_ids"]]
    return {"suggestions": sugg, "selected": len(by_asset),
            "method": "규칙 기반 (LLM 미사용) — 컬럼 프로파일의 연계키 후보와 값 표본 일치율로 계산"}


# ------------------------------------------------------------------ STEP 2 조합
class ComboIn(BaseModel):
    dataset_ids: list[int]
    source: str = "manual"


def _enter_combo(db: Session, p: Process, d: ProcessDataset, user: User) -> None:
    d.in_combo = True
    if not d.meta:
        d.meta = suggest.meta_proposals(d.asset)
    if d.authoring_activity_id is None:
        act = activity.log(db, "catalog_authoring", f"카탈로그 작성 — {d.asset.name}", user=user, process_id=p.id, dataset_id=d.id)
        d.authoring_activity_id = act.id


@router.put("/processes/{pid}/combo")
def set_combo(pid: int, body: ComboIn, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    p = _editable(db, pid)
    by_id = {d.id: d for d in p.datasets}
    want = list(dict.fromkeys(body.dataset_ids))
    bad = [i for i in want if i not in by_id]
    if bad:
        raise HTTPException(422, f"이 프로세스의 후보가 아닙니다: {bad}")
    before = {d.id for d in p.combo}
    for d in p.datasets:
        if d.id in want:
            if not d.in_combo:
                _enter_combo(db, p, d, user)
            d.position = want.index(d.id)
        elif d.in_combo:
            d.in_combo = False
            for r in [r for r in p.relations if d.id in (r.source_id, r.target_id)]:
                p.relations.remove(r)
    p.combo_source = body.source if body.source in ("manual", "suggestion") else "manual"
    after = set(want)
    if before != after:
        names = [(by_id[i].meta or {}).get("title") or by_id[i].asset.name for i in want]
        activity.log(db, "combo_change", f"조합 변경 — {len(want)}건: " + ", ".join(names[:6]), user=user, process_id=p.id)
    p.updated_at = utcnow()
    db.commit()
    db.refresh(p)
    return _detail(db, p)


@router.get("/processes/{pid}/combo/warnings")
def combo_warnings(pid: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    p = _process(db, pid)
    return {"warnings": suggest.combo_warnings(p), "draft": suggest.description_draft(p)}


class ComboConfirmIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None


@router.post("/processes/{pid}/combo/confirm")
def confirm_combo(pid: int, body: ComboConfirmIn, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    p = _editable(db, pid)
    if not p.combo:
        raise HTTPException(409, "조합에 데이터셋이 없습니다")
    title = body.title.strip()
    if not title:
        raise HTTPException(422, "제목은 필수입니다")
    errors = [w for w in suggest.combo_warnings(p) if w["level"] == "error"]
    if errors:
        raise HTTPException(409, "읽을 수 없는 파일이 조합에 있습니다 — " + ", ".join(sorted({e["name"] for e in errors})))
    renamed = re.fullmatch(r"\d+차 프로세스", p.name) is not None or p.name == (p.combo_title or "")
    p.combo_title, p.combo_description = title, (body.description or "").strip() or None
    p.combo_confirmed_at = utcnow()
    if renamed:
        p.name = title
    activity.log(db, "combo_confirm", f"조합 확정 — 「{title}」 {len(p.combo)}건", user=user, process_id=p.id)
    db.commit()
    return _detail(db, p)


@router.post("/processes/{pid}/combo/unconfirm")
def unconfirm_combo(pid: int, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    p = _editable(db, pid)
    if p.combo_confirmed_at:
        p.combo_confirmed_at = None
        activity.log(db, "combo_unconfirm", f"조합 확정 해제 — {p.name}", user=user, process_id=p.id)
        db.commit()
    return _detail(db, p)


# ------------------------------------------------------------------ STEP 3 메타데이터
@router.get("/datasets/{did}")
def get_dataset(did: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    pd = _dataset(db, did, editable=False)
    out = dataset_out(db, pd, _mode(pd.process))
    out["asset"]["profile"] = pd.asset.profile or {}
    return out


class MetaIn(BaseModel):
    values: dict[str, Any] = {}
    approve: list[str] = []
    unapprove: list[str] = []
    extra_classes: list[str] | None = None


def _clean_meta(pd: ProcessDataset, db: Session, values: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    scope = "stream" if pd.asset.kind == "stream" else "dataset"
    fields = {f["name"]: f for f in canonical.META_FIELDS}
    for k, v in values.items():
        f = fields.get(k)
        if f is None:
            raise HTTPException(422, f"알 수 없는 메타데이터 필드입니다: {k}")
        if f["scope"] not in ("all", scope):
            raise HTTPException(422, f"{k} 필드는 {'스트림' if f['scope'] == 'stream' else '파일형 데이터셋'} 전용입니다")
        if f["type"] == "tags":
            v = [str(x).strip() for x in (v or []) if str(x).strip()] if isinstance(v, list) else \
                [x.strip() for x in str(v or "").split(",") if x.strip()]
        elif isinstance(v, str):
            v = v.strip()
        if v in ("", None, []):
            out[k] = None
            continue
        if f["type"] == "org":
            if db.get(Organization, int(v)) is None:
                raise HTTPException(422, "제공기관을 찾을 수 없습니다")
            v = int(v)
        if f["type"] == "duration" and not canonical.is_duration(str(v)):
            raise HTTPException(422, f"{f['label']}은(는) ISO 8601 duration 이어야 합니다 (예: PT5M, P1D)")
        if f["type"] == "date" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v)):
            raise HTTPException(422, f"{f['label']}은(는) YYYY-MM-DD 형식이어야 합니다")
        if f["type"] == "url" and not re.match(r"^[a-z][a-z0-9+.-]*://\S+$", str(v), re.I):
            raise HTTPException(422, f"{f['label']}은(는) URL 형식이어야 합니다")
        if f["type"] == "media_type" and not re.fullmatch(r"[a-z]+/[A-Za-z0-9.+-]+", str(v)):
            raise HTTPException(422, "미디어타입 형식이 올바르지 않습니다 (예: text/csv)")
        if k == "contact_email" and not re.fullmatch(r"[\w.+-]+@[\w-]+\.[\w.-]+", str(v)):
            raise HTTPException(422, "담당 이메일 형식이 올바르지 않습니다")
        if k == "contact_phone" and not re.fullmatch(r"\+?[0-9][0-9 ()-]{5,22}[0-9]", str(v)):
            raise HTTPException(422, "담당 전화번호 형식이 올바르지 않습니다 (예: 044-201-3114)")
        out[k] = v
    return out


@router.patch("/datasets/{did}/meta")
def patch_meta(did: int, body: MetaIn, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    pd = _dataset(db, did)
    needs = canonical.APPROVAL_FIELDS_STREAM if pd.asset.kind == "stream" else canonical.APPROVAL_FIELDS_DATASET
    meta = dict(pd.meta or {})
    auto = [a for a in meta.get("_auto", [])]
    approved = set(pd.approved_fields or [])
    changes = _clean_meta(pd, db, body.values)
    for k, v in changes.items():
        if meta.get(k) != v:
            if k in approved:
                approved.discard(k)  # 승인된 값을 고치면 승인이 풀린다
            if k in auto:
                auto.remove(k)
        if v is None:
            meta.pop(k, None)
        else:
            meta[k] = v
    for k in body.unapprove:
        approved.discard(k)
    newly = []
    for k in body.approve:
        if k not in needs:
            raise HTTPException(422, f"승인 대상 필드가 아닙니다: {k}")
        if not meta.get(k):
            raise HTTPException(422, f"값이 없는 필드는 승인할 수 없습니다: {k}")
        if k not in approved:
            approved.add(k)
            newly.append(k)
    meta["_auto"] = auto
    pd.meta = meta
    pd.approved_fields = [k for k in needs if k in approved]
    if body.extra_classes is not None:
        allowed = {c["iri"] for c in vocab()["extra_classes"]}
        bad = [c for c in body.extra_classes if c not in allowed]
        if bad:
            raise HTTPException(422, f"선택할 수 없는 클래스입니다: {bad}")
        pd.extra_classes = list(dict.fromkeys(body.extra_classes))
    if newly:
        labels = {f["name"]: f["property"] for f in canonical.META_FIELDS}
        activity.log(db, "meta_approve", f"ARD 필수 필드 승인 — {meta.get('title') or pd.asset.name} ({' · '.join(labels[k] for k in newly)})",
                     user=user, process_id=pd.process_id, dataset_id=pd.id)
    pd.process.updated_at = utcnow()
    db.flush()
    if pd.meta_confirmed_at and canonical.build(db, pd, _mode(pd.process)).readiness["missing"]:
        # 확정한 뒤 필수 필드가 다시 비거나 승인이 풀리면 확정도 풀린다
        pd.meta_confirmed_at = None
        activity.log(db, "meta_unconfirm", f"메타데이터 확정 자동 해제 — {meta.get('title') or pd.asset.name} (필수 필드 결측)",
                     user=user, process_id=pd.process_id, dataset_id=pd.id, software=True)
    db.commit()
    return dataset_out(db, pd, _mode(pd.process))


@router.post("/datasets/{did}/meta/confirm")
def confirm_meta(did: int, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    pd = _dataset(db, did)
    c = canonical.build(db, pd, _mode(pd.process))
    if c.readiness["missing"]:
        label = {"title": "제목", "publisher": "제공기관(승인)", "distribution": "미디어타입(승인)",
                 "temporalResolution": "시간 해상도(승인)", "eventTimeColumn": "event-time 컬럼(승인)"}
        raise HTTPException(409, "필수 필드가 비어 있거나 승인되지 않았습니다: " + ", ".join(label.get(m, m) for m in c.readiness["missing"]))
    pd.meta_confirmed_at = utcnow()
    activity.log(db, "meta_confirm", f"카탈로그 메타데이터 확정 — {c.record.get('title')} ({len(c.graph)}트리플)",
                 user=user, process_id=pd.process_id, dataset_id=pd.id)
    db.commit()
    return dataset_out(db, pd, _mode(pd.process))


@router.post("/datasets/{did}/meta/unconfirm")
def unconfirm_meta(did: int, db: Session = Depends(get_db), _: User = Depends(require_writer)) -> dict[str, Any]:
    pd = _dataset(db, did)
    pd.meta_confirmed_at = None
    db.commit()
    return dataset_out(db, pd, _mode(pd.process))


@router.get("/datasets/{did}/preview")
def preview(did: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    """정본 미리보기 + 즉시 검증. STEP 6 과 같은 엔진을 쓰되 실행 기록은 남기지 않는다."""
    pd = _dataset(db, did, editable=False)
    mode = _mode(pd.process)
    c = canonical.build(db, pd, mode)
    res = validation.validate_dataset(db, pd, mode)
    return {"resource_id": c.resource_id, "iri": c.iri, "checksum": c.checksum, "triple_count": len(c.graph),
            "readiness": c.readiness, "turtle": serialize.render_ttl(c, mode), "jsonld": serialize.render_jsonld(c),
            "text": serialize.render_txt(c), "record": c.record,
            "validation": {"passed": res["passed"], "violation_count": res["violation_count"],
                           "warning_count": res["warning_count"], "info_count": res["info_count"],
                           "results": res["results"], "gate0": res["gate0"]}}


# ------------------------------------------------------------------ STEP 4 분류
@router.get("/datasets/{did}/classification/suggestions")
def classification_suggestions(did: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    pd = _dataset(db, did, editable=False)
    return {"suggestions": suggest.classification_suggestions(pd),
            "method": "규칙 기반 (LLM 미사용) — 이름·컬럼명 키워드, 컬럼 타입, 관측 간격, 연계키 후보로 계산",
            "thresholds": {"strong": 80, "review": 40, "low": 15}}


class KeyIn(BaseModel):
    code: str
    table: str | None = None
    column: str | None = None


class ClassificationIn(BaseModel):
    F1: list[str] = []
    F2: list[str] = []
    F3: list[str] = []
    F4: list[str] = []
    F5: list[str] = []
    F6: list[str] = []
    K: list[KeyIn] = []
    N2SF: str | None = None


@router.put("/datasets/{did}/classification")
def put_classification(did: int, body: ClassificationIn, db: Session = Depends(get_db), _: User = Depends(require_writer)) -> dict[str, Any]:
    pd = _dataset(db, did)
    axes = {a.code: a for a in db.scalars(select(TaxonomyAxis))}
    valid = {c.code: c for c in db.scalars(select(TaxonomyCode).where(TaxonomyCode.active.is_(True)))}
    out: dict[str, Any] = {}
    for axis in ("F1", "F2", "F3", "F4", "F5", "F6"):
        codes = list(dict.fromkeys(getattr(body, axis)))
        bad = [c for c in codes if c not in valid or valid[c].axis_code != axis]
        if bad:
            raise HTTPException(422, f"{axis} 축에 없는 코드입니다: {bad}")
        if not axes[axis].multi and len(codes) > 1:
            raise HTTPException(422, f"{axis} {axes[axis].name} 축은 1개만 선택할 수 있습니다")
        if codes:
            out[axis] = codes
    keys, seen = [], set()
    cols = {(t["name"], c["name"]) for t in (pd.asset.profile or {}).get("tables", []) for c in t["columns"]}
    for k in body.K:
        if k.code not in valid or valid[k.code].axis_code != "K":
            raise HTTPException(422, f"연계키 코드가 아닙니다: {k.code}")
        if k.code in seen:
            raise HTTPException(422, f"연계키 {k.code} 가 중복 배정되었습니다")
        seen.add(k.code)
        item: dict[str, Any] = {"code": k.code}
        if k.column:
            if cols and not any(c == k.column and (not k.table or t == k.table) for t, c in cols):
                raise HTTPException(422, f"프로파일에 없는 컬럼입니다: {k.column}")
            item["column"] = k.column
            item["table"] = k.table or next((t for t, c in cols if c == k.column), None)
        keys.append(item)
    if keys:
        out["K"] = keys
    if body.N2SF:
        if body.N2SF not in valid or valid[body.N2SF].axis_code != "N2SF":
            raise HTTPException(422, f"보안등급 코드가 아닙니다: {body.N2SF}")
        out["N2SF"] = body.N2SF
    pd.classification = out
    pd.process.updated_at = utcnow()
    if pd.class_confirmed_at and not (out.get("F1") and out.get("F2")):
        pd.class_confirmed_at = None  # 필수 축이 비면 확정이 풀린다
    db.commit()
    return dataset_out(db, pd, _mode(pd.process))


def _class_gaps(db: Session, pd: ProcessDataset) -> tuple[list[str], list[str]]:
    """(확정을 막는 필수 축 결측, 경고로만 알리는 결측)"""
    cls = pd.classification or {}
    axes = {a.code: a for a in db.scalars(select(TaxonomyAxis))}
    blocking = [f"{a} {axes[a].name}" for a in ("F1", "F2") if not cls.get(a)]
    warn = [f"{a} {axes[a].name}" for a in ("F4", "F6", "K", "N2SF") if not cls.get(a)]
    return blocking, warn


@router.post("/datasets/{did}/classification/confirm")
def confirm_classification(did: int, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    pd = _dataset(db, did)
    blocking, warn = _class_gaps(db, pd)
    if blocking:
        raise HTTPException(409, "필수 축이 비어 있습니다: " + ", ".join(blocking))
    pd.class_confirmed_at = utcnow()
    cls = pd.classification or {}
    n = sum(len(v) if isinstance(v, list) else 1 for v in cls.values())
    activity.log(db, "class_confirm", f"다중분류 확정 — {(pd.meta or {}).get('title') or pd.asset.name} ({n}코드)",
                 user=user, process_id=pd.process_id, dataset_id=pd.id)
    db.commit()
    out = dataset_out(db, pd, _mode(pd.process))
    out["warnings"] = warn
    return out


@router.post("/datasets/{did}/classification/unconfirm")
def unconfirm_classification(did: int, db: Session = Depends(get_db), _: User = Depends(require_writer)) -> dict[str, Any]:
    pd = _dataset(db, did)
    pd.class_confirmed_at = None
    db.commit()
    return dataset_out(db, pd, _mode(pd.process))


# ------------------------------------------------------------------ STEP 5 관계 · 리니지
class RelationIn(BaseModel):
    type: str
    source_id: int
    target_id: int
    key_code: str | None = None
    source_table: str | None = None
    source_column: str | None = None
    target_table: str | None = None
    target_column: str | None = None
    note: str | None = None
    confirm: bool = False


class RelationPatch(BaseModel):
    key_code: str | None = None
    source_table: str | None = None
    source_column: str | None = None
    target_table: str | None = None
    target_column: str | None = None
    note: str | None = None
    priority: int | None = None


def _relation(db: Session, rid: int) -> Relation:
    r = db.get(Relation, rid)
    if r is None:
        raise HTTPException(404, "관계를 찾을 수 없습니다")
    _editable(db, r.process_id)
    return r


def _relations_payload(db: Session, p: Process) -> dict[str, Any]:
    ids = {d.id for d in p.combo}
    rels = [r for r in p.relations if r.source_id in ids and r.target_id in ids]
    return {"relations": [lineage.relation_out(r) for r in rels], "candidates": lineage.candidates(p),
            "lineage_resolved": validation.lineage_resolved(db, p),
            "waiver": {"reason": p.lineage_waiver_reason, "at": p.lineage_waived_at} if p.lineage_waived_at else None,
            "types": vocab()["relation_types"]}


@router.get("/processes/{pid}/relations")
def list_relations(pid: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    return _relations_payload(db, _process(db, pid))


@router.post("/processes/{pid}/relations")
def create_relation(pid: int, body: RelationIn, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    p = _editable(db, pid)
    ids = {d.id for d in p.combo}
    if body.type not in ("JOINED_ON", "GROUPED_WITH", "DERIVED_FROM"):
        raise HTTPException(422, "관계 유형은 JOINED_ON · GROUPED_WITH · DERIVED_FROM 중 하나여야 합니다")
    if body.source_id not in ids or body.target_id not in ids:
        raise HTTPException(422, "조합에 포함된 데이터셋끼리만 관계를 만들 수 있습니다")
    if body.source_id == body.target_id:
        raise HTTPException(422, "같은 데이터셋끼리는 관계를 만들 수 없습니다")
    if body.type == "JOINED_ON" and not body.key_code:
        raise HTTPException(422, "JOINED_ON 관계에는 연계키가 필요합니다")
    if body.key_code and not re.fullmatch(r"K[1-9]", body.key_code):
        raise HTTPException(422, "연계키는 K1~K9 중 하나여야 합니다")
    for r in p.relations:
        same_dir = (r.source_id, r.target_id) == (body.source_id, body.target_id)
        rev = (r.source_id, r.target_id) == (body.target_id, body.source_id)
        same_pair = same_dir or (rev and body.type != "DERIVED_FROM")
        same_key = body.type != "JOINED_ON" or r.key_code == body.key_code
        if r.type == body.type and same_pair and same_key:
            raise HTTPException(409, "같은 관계가 이미 있습니다")
    prio = max((r.priority for r in p.relations if r.type == "JOINED_ON"), default=0) + 1 if body.type == "JOINED_ON" else 0
    rel = Relation(process_id=p.id, type=body.type, source_id=body.source_id, target_id=body.target_id,
                   key_code=body.key_code if body.type == "JOINED_ON" else None,
                   source_table=body.source_table, source_column=body.source_column, target_table=body.target_table,
                   target_column=body.target_column, note=body.note, priority=prio, created_by=user.id)
    p.relations.append(rel)
    db.flush()
    db.refresh(rel)
    if rel.type == "JOINED_ON":
        rel.stats = lineage.join_stats(rel)
    if body.confirm:
        _confirm_relation(db, rel, user)
    db.commit()
    return _relations_payload(db, p)


def _confirm_relation(db: Session, rel: Relation, user: User) -> None:
    if rel.type == "JOINED_ON" and not (rel.source_column and rel.target_column) and \
            rel.source.asset.kind != "stream" and rel.target.asset.kind != "stream":
        raise HTTPException(409, "JOINED_ON 관계는 양쪽 매핑 컬럼을 지정해야 확정할 수 있습니다")
    rel.status, rel.confirmed_at = "confirmed", utcnow()
    a = (rel.source.meta or {}).get("title") or rel.source.asset.name
    b = (rel.target.meta or {}).get("title") or rel.target.asset.name
    detail = f" · {rel.key_code} {rel.source_column or ''} = {rel.target_column or ''}" if rel.type == "JOINED_ON" else ""
    activity.log(db, "relation_confirm", f"관계 확정 — {a} {rel.type} {b}{detail}", user=user, process_id=rel.process_id,
                 payload={"relation_id": rel.id})


@router.patch("/relations/{rid}")
def update_relation(rid: int, body: RelationPatch, db: Session = Depends(get_db), _: User = Depends(require_writer)) -> dict[str, Any]:
    rel = _relation(db, rid)
    changed = False
    for f in ("key_code", "source_table", "source_column", "target_table", "target_column", "note", "priority"):
        if f in body.model_fields_set:
            v = getattr(body, f)
            if f == "key_code" and v and not re.fullmatch(r"K[1-9]", v):
                raise HTTPException(422, "연계키는 K1~K9 중 하나여야 합니다")
            if getattr(rel, f) != v:
                setattr(rel, f, v)
                changed = changed or f not in ("note", "priority")
    if changed:
        if rel.type == "JOINED_ON":
            rel.stats = lineage.join_stats(rel)
        rel.status, rel.confirmed_at = "draft", None  # 내용이 바뀌면 다시 확정해야 한다
    db.commit()
    return _relations_payload(db, rel.process)


@router.post("/relations/{rid}/confirm")
def confirm_relation(rid: int, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    rel = _relation(db, rid)
    if rel.type == "JOINED_ON":
        rel.stats = lineage.join_stats(rel)
    _confirm_relation(db, rel, user)
    db.commit()
    return _relations_payload(db, rel.process)


@router.post("/relations/{rid}/unconfirm")
def unconfirm_relation(rid: int, db: Session = Depends(get_db), _: User = Depends(require_writer)) -> dict[str, Any]:
    rel = _relation(db, rid)
    rel.status, rel.confirmed_at = "draft", None
    db.commit()
    return _relations_payload(db, rel.process)


@router.delete("/relations/{rid}")
def delete_relation(rid: int, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    rel = _relation(db, rid)
    p = rel.process
    if rel.status == "confirmed":
        activity.log(db, "relation_delete", f"확정 관계 삭제 — {rel.type} (REL-{rel.id:06d})", user=user, process_id=p.id)
    p.relations.remove(rel)
    db.commit()
    return _relations_payload(db, p)


class OrderIn(BaseModel):
    relation_ids: list[int]


@router.put("/processes/{pid}/relations/order")
def order_relations(pid: int, body: OrderIn, db: Session = Depends(get_db), _: User = Depends(require_writer)) -> dict[str, Any]:
    """JOINED_ON 의 SSOT 우선순위 재정렬 (맨 위 = 판단 기준 1순위)."""
    p = _editable(db, pid)
    ids = {d.id for d in p.combo}
    joined = {r.id: r for r in p.relations if r.type == "JOINED_ON" and r.source_id in ids and r.target_id in ids}
    if set(body.relation_ids) != set(joined):
        raise HTTPException(422, "JOINED_ON 관계 전체의 순서를 보내야 합니다")
    for n, rid in enumerate(body.relation_ids, start=1):
        joined[rid].priority = n
    db.commit()
    db.refresh(p)
    return _relations_payload(db, p)


@router.get("/processes/{pid}/graph")
def process_graph(pid: int, level: int = 2, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    return lineage.graph(db, _process(db, pid), max(1, min(4, level)))


class WaiverIn(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


@router.post("/processes/{pid}/lineage-waiver")
def set_waiver(pid: int, body: WaiverIn, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    p = _editable(db, pid)
    p.lineage_waiver_reason, p.lineage_waived_at = body.reason.strip(), utcnow()
    activity.log(db, "lineage_waiver", f"리니지 미결 사유 기록 — {p.name}: {body.reason.strip()[:120]}", user=user, process_id=p.id)
    db.commit()
    return _detail(db, p)


@router.delete("/processes/{pid}/lineage-waiver")
def clear_waiver(pid: int, db: Session = Depends(get_db), _: User = Depends(require_writer)) -> dict[str, Any]:
    p = _editable(db, pid)
    p.lineage_waiver_reason, p.lineage_waived_at = None, None
    db.commit()
    return _detail(db, p)


# ------------------------------------------------------------------ STEP 6 검증
@router.post("/processes/{pid}/validation-runs")
def run_validation(pid: int, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    p = _editable(db, pid)
    ok, reason = gates.can_enter(db, p, 6)
    if not ok:
        raise HTTPException(409, f"STEP 6 잠김 — {reason}")
    try:
        vr = validation.run(db, p, user)
    except validation.LineageUnresolved:
        raise HTTPException(409, detail={"code": "LINEAGE_UNRESOLVED",
                                         "message": "조합이 2건 이상인데 확정된 관계가 없습니다 — STEP 5 에서 관계를 확정하거나 미결 사유를 기록하세요"}) from None
    db.commit()
    return {"run": validation_out(vr), "state": gates.state(db, p)}


@router.get("/processes/{pid}/validation-runs/latest")
def latest_validation(pid: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    p = _process(db, pid)
    vr = validation.latest_run(db, pid)
    return {"run": validation_out(vr), "stale": validation.stale_reason(db, p, vr) if vr else None,
            "lineage_resolved": validation.lineage_resolved(db, p),
            "mint": [{"dataset_id": d.id, "name": (d.meta or {}).get("title") or d.asset.name,
                      "minted_id": (rec.minted_id if (rec := minting.minted_record(db, d.asset_id)) else None),
                      "draft_id": minting.draft_id(d)} for d in p.combo]}


@router.get("/validation-runs/{run_id}/report")
def validation_report(run_id: int, dataset_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> Response:
    vr = db.get(ValidationRun, run_id)
    r = next((x for x in (vr.results if vr else []) if x.dataset_id == dataset_id), None)
    if r is None or not r.report_ttl:
        raise HTTPException(404, "검증 보고서를 찾을 수 없습니다")
    return Response(r.report_ttl, media_type="text/turtle; charset=utf-8")


@router.post("/processes/{pid}/mint")
def mint(pid: int, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, Any]:
    p = _editable(db, pid)
    if not p.combo or not p.combo_confirmed_at:
        raise HTTPException(409, "조합을 확정한 뒤에 ID 를 발급할 수 있습니다")
    created = minting.mint_for_process(db, p, user)
    if created:
        activity.log(db, "mint", f"발행 ID 발급 {len(created)}건 — " + ", ".join(m.minted_id for m in created),
                     user=user, process_id=p.id)
    db.commit()
    return {"created": [mint_out(m) for m in created], "detail": _detail(db, p)}


# ------------------------------------------------------------------ STEP 7 직렬화
class SerializeIn(BaseModel):
    formats: list[str] = []


@router.post("/processes/{pid}/serialization-runs")
def run_serialization(pid: int, body: SerializeIn, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    p = _editable(db, pid)
    ok, reason = gates.can_enter(db, p, 7)
    if not ok:
        raise HTTPException(409, f"STEP 7 잠김 — {reason}")
    bad = [f for f in body.formats if f not in serialize.FORMAT_KEYS]
    if bad:
        raise HTTPException(422, f"지원하지 않는 포맷입니다: {bad}")
    vr = validation.latest_run(db, pid)
    sr = serialize.run(db, p, user, vr, body.formats)  # type: ignore[arg-type]
    db.commit()
    return {"run": serialization_out(sr), "state": gates.state(db, p)}


@router.get("/processes/{pid}/serialization-runs/latest")
def latest_serialization(pid: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    p = _process(db, pid)
    st = gates.state(db, p)
    sr = serialize.latest_run(db, pid)
    vr = validation.latest_run(db, pid)
    blocked = catalog.check(p, vr, st["validation"]["stale"], sr, st["serialization"]["stale"])
    return {"run": serialization_out(sr), "stale": st["serialization"]["stale"], "formats": serialize.FORMATS,
            "publish_blocked": blocked}


def _download(content: str | bytes, filename: str, media_type: str) -> Response:
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename) or "download"
    disp = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    if isinstance(content, str):
        return Response(content.encode("utf-8"), media_type=f"{media_type}; charset=utf-8", headers={"Content-Disposition": disp})
    return Response(content, media_type=media_type, headers={"Content-Disposition": disp})


@router.get("/artifacts/{aid}")
def get_artifact(aid: int, download: bool = False, db: Session = Depends(get_db), _: User = Depends(current_user)) -> Any:
    a = db.get(Artifact, aid)
    if a is None:
        raise HTTPException(404, "산출물을 찾을 수 없습니다")
    if download:
        return _download(a.content, a.filename, a.media_type)
    return {"id": a.id, "filename": a.filename, "fmt": a.fmt, "media_type": a.media_type, "content": a.content,
            "sha256": a.sha256, "set_checksum": a.set_checksum, "size": a.size}


@router.get("/serialization-runs/{run_id}/download")
def download_zip(run_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> Response:
    sr = db.get(SerializationRun, run_id)
    if sr is None or not sr.artifacts:
        raise HTTPException(404, "내려받을 산출물이 없습니다")
    p = _process(db, sr.process_id)
    name = re.sub(r"[^가-힣a-zA-Z0-9]+", "_", p.name).strip("_")[:40] or "process"
    return _download(serialize.build_zip(sr, p), f"{name}_산출물_{sr.id}.zip", "application/zip")


@router.post("/processes/{pid}/publish")
def publish(pid: int, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, Any]:
    from ..serializers import catalog_out

    p = _process(db, pid)
    if p.status == "trashed":
        raise HTTPException(409, "휴지통에 있는 프로세스는 발행할 수 없습니다")
    st = gates.state(db, p)
    vr, sr = validation.latest_run(db, pid), serialize.latest_run(db, pid)
    reasons = catalog.check(p, vr, st["validation"]["stale"], sr, st["serialization"]["stale"])
    if reasons:
        raise HTTPException(409, detail={"code": "PUBLISH_BLOCKED", "message": reasons[0], "reasons": reasons})
    entries = catalog.publish(db, p, user, vr, sr)  # type: ignore[arg-type]
    if not entries:
        raise HTTPException(409, "발행할 수 있는 데이터셋이 없습니다 (검증 통과 + 자가검증 통과 + 민팅 필요)")
    db.commit()
    return {"published": [catalog_out(e) for e in entries]}


# ------------------------------------------------------------------ STEP 8 진단
@router.post("/processes/{pid}/diagnosis-runs")
def run_diagnosis(pid: int, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    p = _process(db, pid)
    if p.status == "trashed":
        raise HTTPException(409, "휴지통에 있는 프로세스입니다")
    ok, reason = gates.can_enter(db, p, 8)
    if not ok:
        raise HTTPException(409, f"STEP 8 잠김 — {reason}")
    dr = diagnosis.run(db, p, user)
    db.commit()
    return {"run": diagnosis_out(dr), "state": gates.state(db, p)}


@router.get("/processes/{pid}/diagnosis-runs/latest")
def latest_diagnosis(pid: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    p = _process(db, pid)
    st = gates.state(db, p)
    rules = guideline_rules()
    dr = diagnosis.latest_run(db, pid)
    atts = db.scalars(select(Attestation).where(Attestation.process_id == pid)).all()
    return {"run": diagnosis_out(dr), "stale": st["diagnosis"]["stale"],
            "attestations": {a.item_id: {"status": a.status, "note": a.note, "evidence": a.evidence, "by": a.attested_label,
                                         "at": a.attested_at} for a in atts},
            "pending_attestations": [a.item_id for a in atts if dr is not None and a.attested_at > dr.started_at],
            "ruleset": {"version": rules["version"], "guideline": rules["guideline"], "note": rules["note"],
                        "guideline_total": rules["total_items_in_guideline"], "implemented_total": len(rules["rules"]),
                        "methods": rules["methods"], "areas": rules["areas"],
                        "method_counts": {m["id"]: len([r for r in rules["rules"] if r["method"] == m["id"]])
                                          for m in rules["methods"]}}}


class AttestIn(BaseModel):
    status: str
    note: str | None = None
    evidence: str | None = None


@router.put("/processes/{pid}/attestations/{item_id}")
def attest(pid: int, item_id: str, body: AttestIn, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    p = _process(db, pid)
    rule = next((r for r in guideline_rules()["rules"] if r["id"] == item_id), None)
    if rule is None:
        raise HTTPException(404, "진단 항목을 찾을 수 없습니다")
    if rule["method"] != "HUMAN-ATTEST":
        raise HTTPException(422, "담당자 확인 대상 항목이 아닙니다 (자동 판정 항목)")
    if body.status not in ("met", "partial", "unmet", "na"):
        raise HTTPException(422, "판정은 met · partial · unmet · na 중 하나여야 합니다")
    if body.status == "na" and not rule.get("allow_na"):
        raise HTTPException(422, "이 항목은 해당 없음으로 판정할 수 없습니다")
    if body.status != "unmet" and not (body.evidence or "").strip():
        raise HTTPException(422, "해당 없음 판정에는 그 사유가 필요합니다" if body.status == "na"
                            else "충족·부분 충족 판정에는 증빙(문서 위치·링크·설명)이 필요합니다")
    att = db.scalar(select(Attestation).where(Attestation.process_id == pid, Attestation.item_id == item_id))
    if att is None:
        att = Attestation(process_id=pid, item_id=item_id, status=body.status)
        db.add(att)
    att.status, att.note, att.evidence = body.status, body.note, body.evidence
    att.attested_by, att.attested_label, att.attested_at = user.id, user.name, utcnow()
    label = {"met": "충족", "partial": "부분 충족", "unmet": "미흡", "na": "해당 없음"}[body.status]
    act = activity.log(db, "attestation", f"담당자 확인 — {item_id} {rule['name']}: {label}", user=user, process_id=p.id)
    att.activity_id = act.id
    db.commit()
    return {"ok": True, "item_id": item_id, "status": att.status}


@router.delete("/processes/{pid}/attestations/{item_id}")
def delete_attestation(pid: int, item_id: str, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    """담당자 확인을 지운다. 재진단하면 그 항목은 확인 대기(또는 자동 증빙의 해당 없음)로 돌아간다."""
    p = _process(db, pid)
    att = db.scalar(select(Attestation).where(Attestation.process_id == pid, Attestation.item_id == item_id))
    if att is None:
        raise HTTPException(404, "담당자 확인 기록이 없습니다")
    db.delete(att)
    activity.log(db, "attestation", f"담당자 확인 삭제 — {item_id}", user=user, process_id=p.id)
    db.commit()
    return {"ok": True, "item_id": item_id}


@router.get("/diagnosis-runs/{run_id}/report")
def diagnosis_report(run_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> Response:
    """진단 보고서 (인쇄용 HTML — 브라우저 인쇄로 PDF 저장)."""
    from ..services.report import render_report

    dr = db.get(DiagnosisRun, run_id)
    if dr is None:
        raise HTTPException(404, "진단 결과를 찾을 수 없습니다")
    p = _process(db, dr.process_id)
    return _download(render_report(p, dr), f"진단보고서_{re.sub(r'[^가-힣a-zA-Z0-9]+', '_', p.name)[:40]}_{dr.id}.html", "text/html")
