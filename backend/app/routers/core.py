"""인증 · 참조 데이터 · 기관 · 분류체계 · 사용자 · 원천(Asset)."""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import (Activity, Asset, MintRecord, Organization, ProcessDataset, Process, TaxonomyAxis, TaxonomyCode,
                      User, utcnow)
from ..security import (create_token, current_user, hash_password, require_admin, require_writer, verify_password)
from ..serializers import activity_out, asset_out, axis_out, mint_out, org_out, user_out
from ..services import activity, canonical, minting, profiling, serialize, storage, validation
from ..services.reference import vocab

router = APIRouter()


# ------------------------------------------------------------------ 인증
class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = db.scalar(select(User).where(User.username == body.username.strip()))
    if user is None or not user.active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "ID 또는 비밀번호가 올바르지 않습니다")
    return {"access_token": create_token(user), "token_type": "bearer", "user": user_out(user)}


@router.get("/auth/me")
def me(user: User = Depends(current_user)) -> dict[str, Any]:
    return user_out(user)


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


@router.post("/auth/password")
def change_password(body: PasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, bool]:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "현재 비밀번호가 올바르지 않습니다")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ 참조 데이터
@router.get("/reference")
def reference(_: User = Depends(current_user)) -> dict[str, Any]:
    s = get_settings()
    return {**vocab(), "meta_fields": canonical.META_FIELDS, "formats": serialize.FORMATS, "base_iri": s.base_iri,
            "def_ns": s.def_ns, "shapes_version": validation.shapes_version(), "max_upload_mb": s.max_upload_mb,
            "upload_exts": sorted(profiling.MEDIA_TYPES), "key_labels": {k: v for k, v in _key_labels().items()}}


def _key_labels() -> dict[str, str]:
    from ..services.suggest import KEY_LABEL

    return KEY_LABEL


@router.get("/shapes")
def shapes(mode: str = "draft", _: User = Depends(current_user)) -> dict[str, Any]:
    mode = "publish" if mode == "publish" else "draft"
    return {"version": validation.shapes_version(), "mode": mode, "turtle": validation.shapes_source(mode),
            "rules": validation.rule_catalog()}


# ------------------------------------------------------------------ 기관
class OrgIn(BaseModel):
    code: str | None = None
    label: str = Field(min_length=1, max_length=200)
    note: str | None = None
    active: bool = True


@router.get("/orgs")
def list_orgs(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[dict[str, Any]]:
    return [org_out(o) for o in db.scalars(select(Organization).order_by(Organization.label))]


@router.post("/orgs")
def create_org(body: OrgIn, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    code = (body.code or "").strip()
    if code and not re.fullmatch(r"ORG-[A-Za-z0-9]{3,20}", code):
        raise HTTPException(422, "기관 코드는 ORG-영숫자 형식이어야 합니다 (예: ORG-1613000)")
    if not code:
        code = f"ORG-L{minting.next_seq(db, 'ORG'):05d}"  # 행정표준코드가 없는 기관의 로컬 채번
    if db.scalar(select(Organization).where(Organization.code == code)):
        raise HTTPException(409, f"이미 등록된 기관 코드입니다: {code}")
    org = Organization(code=code, label=body.label.strip(), note=body.note, active=body.active)
    db.add(org)
    activity.log(db, "org_register", f"기관 등록 — {org.label} ({code})", user=user)
    db.commit()
    return org_out(org)


@router.patch("/orgs/{org_id}")
def update_org(org_id: int, body: OrgIn, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> dict[str, Any]:
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(404, "기관을 찾을 수 없습니다")
    org.label, org.note, org.active = body.label.strip(), body.note, body.active
    db.commit()
    return org_out(org)


# ------------------------------------------------------------------ 분류체계
@router.get("/taxonomy")
def taxonomy(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[dict[str, Any]]:
    return [axis_out(a) for a in db.scalars(select(TaxonomyAxis).order_by(TaxonomyAxis.position))]


class CodeIn(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    definition: str | None = None
    active: bool = True


@router.post("/taxonomy/{axis_code}/codes")
def add_code(axis_code: str, body: CodeIn, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, Any]:
    axis = db.get(TaxonomyAxis, axis_code)
    if axis is None:
        raise HTTPException(404, "분류 축을 찾을 수 없습니다")
    if axis_code in ("K", "N2SF"):
        raise HTTPException(422, "연계키·보안등급 축은 코드 체계가 고정되어 있어 추가할 수 없습니다")
    if any(c.label == body.label.strip() for c in axis.codes):
        raise HTTPException(409, "같은 이름의 코드가 이미 있습니다")
    nums = [int(m.group(1)) for c in axis.codes if (m := re.search(r"-(\d+)$", c.code))]
    code = TaxonomyCode(code=f"{axis_code}-{(max(nums) if nums else 0) + 1:02d}", label=body.label.strip(),
                        definition=body.definition, position=len(axis.codes), active=body.active)
    axis.codes.append(code)
    activity.log(db, "taxonomy_change", f"분류체계 코드 추가 — {axis_code} {axis.name}: {code.label} ({code.code})", user=user)
    db.commit()
    return axis_out(axis)


@router.patch("/taxonomy/codes/{code_id}")
def update_code(code_id: int, body: CodeIn, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, Any]:
    code = db.get(TaxonomyCode, code_id)
    if code is None:
        raise HTTPException(404, "코드를 찾을 수 없습니다")
    was = code.active
    code.label, code.definition, code.active = body.label.strip(), body.definition, body.active
    if was != body.active:
        activity.log(db, "taxonomy_change", f"분류체계 코드 {'복원' if body.active else '폐기'} — {code.code} {code.label}", user=user)
    db.commit()
    return axis_out(code.axis)


# ------------------------------------------------------------------ 사용자
class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=60, pattern=r"^[A-Za-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8)
    role: str = "worker"
    org_label: str | None = None
    email: str | None = None


class UserPatch(BaseModel):
    name: str | None = None
    role: str | None = None
    org_label: str | None = None
    email: str | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=8)


@router.get("/users")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[dict[str, Any]]:
    return [user_out(u) for u in db.scalars(select(User).order_by(User.id))]


@router.post("/users")
def create_user(body: UserIn, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> dict[str, Any]:
    if body.role not in ("admin", "worker", "viewer"):
        raise HTTPException(422, "역할은 admin · worker · viewer 중 하나여야 합니다")
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(409, "이미 사용 중인 ID 입니다")
    u = User(username=body.username, name=body.name, password_hash=hash_password(body.password), role=body.role,
             org_label=body.org_label, email=body.email)
    db.add(u)
    db.commit()
    return user_out(u)


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserPatch, db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> dict[str, Any]:
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "사용자를 찾을 수 없습니다")
    if body.role is not None:
        if body.role not in ("admin", "worker", "viewer"):
            raise HTTPException(422, "역할은 admin · worker · viewer 중 하나여야 합니다")
        if u.id == admin.id and body.role != "admin":
            raise HTTPException(409, "자기 자신의 관리자 권한은 해제할 수 없습니다")
        u.role = body.role
    if body.active is not None:
        if u.id == admin.id and not body.active:
            raise HTTPException(409, "자기 자신의 계정은 비활성화할 수 없습니다")
        u.active = body.active
    for f in ("name", "org_label", "email"):
        v = getattr(body, f)
        if v is not None:
            setattr(u, f, v)
    if body.password:
        u.password_hash = hash_password(body.password)
    db.commit()
    return user_out(u)


# ------------------------------------------------------------------ 활동 로그 · 민팅 대장
@router.get("/activities")
def list_activities(process_id: int | None = None, limit: int = 50, db: Session = Depends(get_db),
                    _: User = Depends(current_user)) -> list[dict[str, Any]]:
    q = select(Activity).order_by(Activity.id.desc()).limit(min(max(limit, 1), 500))
    if process_id is not None:
        q = q.where(Activity.process_id == process_id)
    return [activity_out(a) for a in db.scalars(q)]


@router.get("/mint-registry")
def mint_registry(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    from ..models import Sequence

    recs = db.scalars(select(MintRecord).order_by(MintRecord.id.desc())).all()
    seqs = {s.kind: s.next_value for s in db.scalars(select(Sequence))}
    return {
        "records": [mint_out(m) for m in recs],
        "next": {k: f"{k}-{seqs.get(k, minting.SEQ_START[k]):06d}" for k in ("DST", "SVC")},
        "policy": {
            "draft_pattern": "{DST|SVC}-draft-{작업 번호 6자리}",
            "published_pattern": "{DST|SVC}-{일련번호 6자리}",
            "distribution_pattern": "DIST-{본체 번호}-{확장자}",
            "activity_pattern": "ACT-K-{일련번호 4자리}",
            "rule": "발행 ID 는 관리자가 민팅 대장에 등록한 것만 쓴다. 대장에 없으면 발행 모드 검증의 게이트 0 ④ 에서 실패한다 (fallback 발급 금지). 같은 원천은 재발행해도 같은 ID 를 유지한다.",
            "iri_base": get_settings().id_ns,
        },
    }


# ------------------------------------------------------------------ 원천(Asset)
def _asset_or_404(db: Session, asset_id: int) -> Asset:
    a = db.get(Asset, asset_id)
    if a is None or a.deleted_at is not None:
        raise HTTPException(404, "원천을 찾을 수 없습니다")
    return a


@router.get("/assets")
def list_assets(kind: str | None = None, q: str | None = None, db: Session = Depends(get_db),
                _: User = Depends(current_user)) -> list[dict[str, Any]]:
    stmt = select(Asset).where(Asset.deleted_at.is_(None)).order_by(Asset.id.desc())
    if kind in ("dataset", "stream"):
        stmt = stmt.where(Asset.kind == kind)
    if q:
        stmt = stmt.where(func.lower(Asset.name).contains(q.lower()))
    return [asset_out(a) for a in db.scalars(stmt)]


@router.post("/assets/upload")
async def upload_assets(files: list[UploadFile] = File(...), db: Session = Depends(get_db),
                        user: User = Depends(require_writer)) -> dict[str, Any]:
    s = get_settings()
    created: list[Asset] = []
    rejected: list[dict[str, str]] = []
    for f in files:
        filename = (f.filename or "upload").replace("\\", "/").rsplit("/", 1)[-1]
        ext = profiling.classify_ext(filename)
        if ext in profiling.BLOCKED_EXTS:
            rejected.append({"filename": filename, "reason": "대용량·실시간성 또는 실행 파일 형식은 업로드할 수 없습니다 — 스트림 등록을 이용하세요"})
            continue
        if ext not in profiling.MEDIA_TYPES:
            rejected.append({"filename": filename, "reason": f".{ext or '?'} 형식은 지원하지 않습니다"})
            continue
        data = await f.read()
        if len(data) > s.max_upload_mb * 1024 * 1024:
            rejected.append({"filename": filename, "reason": f"{s.max_upload_mb}MB 를 초과합니다 — 데이터레이크 연동 대상입니다"})
            continue
        if not data:
            rejected.append({"filename": filename, "reason": "빈 파일입니다"})
            continue
        key, digest = storage.save(data)
        res = profiling.profile_file(storage.path_of(key), filename, s.profile_max_rows)
        name = filename.rsplit(".", 1)[0] if "." in filename else filename
        asset = Asset(name=name, kind="dataset", source="upload", filename=filename, ext=ext, size=len(data),
                      sha256=digest, media_type=res.media_type, storage_key=key, data_form=res.data_form,
                      profile=res.profile, key_candidates=res.key_candidates, key_samples=res.key_samples,
                      created_by=user.id)
        db.add(asset)
        db.flush()
        created.append(asset)
    if created:
        activity.log(db, "upload", f"파일 업로드 {len(created)}건 — " + ", ".join(a.filename or a.name for a in created[:5]),
                     user=user, payload={"asset_ids": [a.id for a in created]})
    db.commit()
    return {"created": [asset_out(a) for a in created], "rejected": rejected}


class StreamField(BaseModel):
    name: str
    type: str = "string"


class StreamIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    org_id: int | None = None
    temporal_resolution: str | None = None
    event_time_column: str | None = None
    endpoint_url: str | None = None
    timezone: str | None = "Asia/Seoul"
    fields: list[StreamField] = []


@router.post("/assets/streams")
def register_stream(body: StreamIn, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    name = body.name.strip()
    if db.scalar(select(Asset).where(Asset.name == name, Asset.kind == "stream", Asset.deleted_at.is_(None))):
        raise HTTPException(409, "같은 이름의 스트림이 이미 등록되어 있습니다")
    if body.temporal_resolution and not canonical.is_duration(body.temporal_resolution.strip()):
        raise HTTPException(422, "시간 해상도는 ISO 8601 duration 이어야 합니다 (예: PT5M)")
    if body.org_id and db.get(Organization, body.org_id) is None:
        raise HTTPException(422, "제공기관을 찾을 수 없습니다")
    if body.endpoint_url and not re.match(r"^[a-z][a-z0-9+.-]*://\S+$", body.endpoint_url.strip(), re.I):
        raise HTTPException(422, "엔드포인트는 URL 형식이어야 합니다 (예: kafka://broker:9092/topic)")
    fields = [f.model_dump() for f in body.fields if f.name.strip()]
    res = profiling.profile_stream(fields)
    asset = Asset(name=name, kind="stream", source="stream", data_form="실시간 스트림", description=body.description,
                  org_id=body.org_id, profile=res.profile, key_candidates=res.key_candidates, key_samples={},
                  stream={"temporal_resolution": (body.temporal_resolution or "").strip() or None,
                          "event_time_column": (body.event_time_column or "").strip() or None,
                          "endpoint_url": (body.endpoint_url or "").strip() or None,
                          "timezone": body.timezone, "fields": fields},
                  created_by=user.id)
    db.add(asset)
    db.flush()
    activity.log(db, "stream_register", f"스트림 등록 — {name}", user=user, payload={"asset_id": asset.id})
    db.commit()
    return asset_out(asset, detail=True)


@router.get("/assets/{asset_id}")
def get_asset(asset_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    a = _asset_or_404(db, asset_id)
    out = asset_out(a, detail=True)
    rec = minting.minted_record(db, a.id)
    out["minted_id"] = rec.minted_id if rec else None
    used = db.execute(select(Process.id, Process.name, Process.status).join(ProcessDataset, ProcessDataset.process_id == Process.id)
                      .where(ProcessDataset.asset_id == a.id)).all()
    out["used_in"] = [{"id": i, "name": n, "status": st} for i, n, st in used]
    return out


class AssetPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    org_id: int | None = None


@router.patch("/assets/{asset_id}")
def update_asset(asset_id: int, body: AssetPatch, db: Session = Depends(get_db), _: User = Depends(require_writer)) -> dict[str, Any]:
    a = _asset_or_404(db, asset_id)
    if body.name is not None:
        a.name = body.name.strip()
    if body.description is not None:
        a.description = body.description
    if "org_id" in body.model_fields_set:
        if body.org_id is not None and db.get(Organization, body.org_id) is None:
            raise HTTPException(422, "제공기관을 찾을 수 없습니다")
        a.org_id = body.org_id
    db.commit()
    return asset_out(a, detail=True)


@router.delete("/assets/{asset_id}")
def delete_asset(asset_id: int, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    a = _asset_or_404(db, asset_id)
    if minting.minted_record(db, a.id):
        raise HTTPException(409, "발행 ID 가 발급된 원천은 삭제할 수 없습니다 (카탈로그 추적성 유지)")
    used = db.execute(select(Process.name).join(ProcessDataset, ProcessDataset.process_id == Process.id)
                      .where(ProcessDataset.asset_id == a.id, ProcessDataset.in_combo.is_(True),
                             Process.status != "trashed")).scalars().all()
    if used:
        raise HTTPException(409, "조합에 포함된 원천입니다 — 먼저 조합에서 제외하세요: " + ", ".join(sorted(set(used))[:5]))
    for pd in db.scalars(select(ProcessDataset).where(ProcessDataset.asset_id == a.id)).all():
        db.delete(pd)
    a.deleted_at = utcnow()
    activity.log(db, "asset_delete", f"원천 삭제 — {a.name}", user=user, payload={"asset_id": a.id})
    db.commit()
    return {"ok": True}
