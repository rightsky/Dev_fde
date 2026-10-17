"""기관 N²SF 등급표 가져오기 (N²SF 기획안 3절).

기관이 N²SF 1단계(준비)에서 만든 업무정보 · 정보시스템 등급표(CSV)를 올리면 자산과 매칭해 데이터셋 등급의 기본값과 충돌 신호에 쓴다.
열 이름은 한국어 · 영어 몇 가지를 자동으로 알아보고, 등급은 C/S/S1/S2/O 또는 1/2/3 을 받는다.
"""
from __future__ import annotations

import csv
import hashlib
import io
from difflib import SequenceMatcher
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Asset, OrgGradeEntry, ProcessDataset, User
from ..security import current_user, require_admin, require_writer
from ..services import activity, grading

router = APIRouter()

COLUMNS = {
    "name": ("업무정보명", "업무정보", "정보명", "데이터명", "데이터셋명", "자산명", "name", "dataset", "title"),
    "system": ("정보시스템", "정보시스템명", "시스템", "시스템명", "시스템코드", "system", "system_code"),
    "department": ("소관부서", "부서", "담당부서", "department", "dept"),
    "grade": ("등급", "보안등급", "n2sf", "n²sf", "grade", "c/s/o", "cso"),
    "personal_data": ("개인정보", "개인정보포함", "개인정보 포함", "personal", "pii"),
    "legal_basis": ("법령근거", "법령 근거", "근거법령", "관련법령", "legal", "law"),
    "note": ("비고", "note", "remark", "memo"),
}
GRADE_ALIASES = {"C": "C", "S": "S2", "S1": "S1", "S2": "S2", "O": "O", "3": "C", "2": "S2", "1": "O",
                 "비공개": "C", "기밀": "C", "제한공유": "S2", "제한 공유": "S2", "조건부공유": "S1", "조건부 공유": "S1", "민감": "S2", "공개": "O", "공개공유": "O"}


def _norm(s: str) -> str:
    return "".join(ch for ch in str(s or "").lower() if ch.isalnum())


def _header_map(header: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for i, h in enumerate(header):
        key = _norm(h)
        for field, names in COLUMNS.items():
            if field not in out and any(key == _norm(n) or _norm(n) in key for n in names):
                out[field] = i
                break
    return out


def _grade(v: str) -> str | None:
    key = str(v or "").strip().upper().replace("N2SF-", "")
    return GRADE_ALIASES.get(key) or GRADE_ALIASES.get(str(v or "").strip())


def _score(entry_name: str, entry_system: str | None, asset: Asset, titles: list[str]) -> int:
    """이름 유사도 0~100. 완전 일치 100, 포함 관계 90, 그 외 SequenceMatcher."""
    cands = [asset.name, asset.filename or "", *titles]
    a = _norm(entry_name)
    best = 0
    for c in cands:
        b = _norm(c)
        if not a or not b:
            continue
        if a == b:
            return 100
        if a in b or b in a:
            best = max(best, 90)
        best = max(best, int(SequenceMatcher(None, a, b).ratio() * 100))
    return best


def _titles(db: Session) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for pd in db.scalars(select(ProcessDataset)):
        t = (pd.meta or {}).get("title")
        if t:
            out.setdefault(pd.asset_id, []).append(str(t))
    return out


def _out(e: OrgGradeEntry, candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"id": e.id, "kind": e.kind, "name": e.name, "system": e.system, "department": e.department, "grade": e.grade,
            "grade_label": grading.GRADE_LABEL.get(e.grade), "personal_data": e.personal_data, "legal_basis": e.legal_basis, "note": e.note,
            "asset_id": e.asset_id, "match_score": e.match_score, "source_file": e.source_file, "imported_at": e.imported_at,
            "candidates": candidates or []}


@router.get("/org-grades")
def list_entries(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    assets = db.scalars(select(Asset).where(Asset.deleted_at.is_(None))).all()
    titles = _titles(db)
    items = []
    for e in db.scalars(select(OrgGradeEntry).order_by(OrgGradeEntry.id)):
        scored = sorted(((_score(e.name, e.system, a, titles.get(a.id, [])), a) for a in assets), key=lambda x: -x[0])
        cands = [{"asset_id": a.id, "name": a.name, "filename": a.filename, "score": sc} for sc, a in scored[:3] if sc >= 40]
        items.append(_out(e, cands))
    matched = sum(1 for i in items if i["asset_id"])
    return {"items": items, "total": len(items), "matched": matched, "unmatched": len(items) - matched}


@router.post("/org-grades/import")
async def import_csv(file: UploadFile = File(...), replace: bool = True, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, Any]:
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "5MB 를 넘는 등급표는 올릴 수 없습니다")
    text = raw.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise HTTPException(422, "빈 파일입니다")
    hm = _header_map(rows[0])
    if "name" not in hm or "grade" not in hm:
        raise HTTPException(422, f"열 이름을 알아보지 못했습니다 — 최소한 '업무정보명'과 '등급' 열이 필요합니다. 읽은 머리글: {rows[0][:8]}")
    assets = db.scalars(select(Asset).where(Asset.deleted_at.is_(None))).all()
    titles = _titles(db)
    digest = hashlib.sha256(raw).hexdigest()
    if replace:
        for old in db.scalars(select(OrgGradeEntry)):
            db.delete(old)
        db.flush()
    created, skipped = [], []
    for n, r in enumerate(rows[1:], start=2):
        def col(k: str) -> str | None:
            i = hm.get(k)
            return (r[i].strip() if i is not None and i < len(r) else None) or None
        name, g = col("name"), _grade(col("grade") or "")
        if not name or not g:
            skipped.append(f"{n}행: {'이름 없음' if not name else '등급 값을 알 수 없음 (' + str(col('grade')) + ')'}")
            continue
        e = OrgGradeEntry(kind="info", name=name, system=col("system"), department=col("department"), grade=g,
                          personal_data=col("personal_data"), legal_basis=col("legal_basis"), note=col("note"),
                          source_file=file.filename, source_sha256=digest, imported_by=user.id)
        scored = sorted(((_score(name, e.system, a, titles.get(a.id, [])), a) for a in assets), key=lambda x: -x[0])
        if scored and scored[0][0] >= 90:  # 이름이 같거나 포함 관계면 자동 매칭, 나머지는 담당자가 고른다
            e.asset_id, e.match_score = scored[0][1].id, scored[0][0]
        db.add(e)
        created.append(e)
    db.flush()
    activity.log(db, "org_grades_import", f"N²SF 기관 등급표 가져오기 — {file.filename} {len(created)}행 (자동 매칭 {sum(1 for e in created if e.asset_id)}건)",
                 user=user, payload={"file": file.filename, "sha256": digest, "rows": len(created), "skipped": skipped[:20], "columns": hm})
    db.commit()
    return {"imported": len(created), "auto_matched": sum(1 for e in created if e.asset_id), "skipped": skipped, "columns": hm}


class MatchIn(BaseModel):
    asset_id: int | None = None


@router.patch("/org-grades/{eid}")
def set_match(eid: int, body: MatchIn, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    e = db.get(OrgGradeEntry, eid)
    if e is None:
        raise HTTPException(404, "등급표 행이 없습니다")
    if body.asset_id is not None and db.get(Asset, body.asset_id) is None:
        raise HTTPException(404, "자산이 없습니다")
    e.asset_id, e.match_score = body.asset_id, (100 if body.asset_id else 0)
    activity.log(db, "org_grades_match", f"기관 등급표 매칭 — {e.name} → 자산 {body.asset_id or '해제'}", user=user, payload={"entry": e.id, "asset_id": body.asset_id})
    db.commit()
    return _out(e)


@router.delete("/org-grades")
def clear(db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, int]:
    n = 0
    for e in db.scalars(select(OrgGradeEntry)):
        db.delete(e)
        n += 1
    activity.log(db, "org_grades_clear", f"N²SF 기관 등급표 비움 ({n}행)", user=user)
    db.commit()
    return {"deleted": n}
