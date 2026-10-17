"""분류체계 세트 (v0.20).

- 세트 = F1~F6 코드 묶음 + 이름 · 기관/분야. K · N²SF 축은 공통(set_id NULL).
- 프로세스는 세트 하나를 쓴다 (process.taxonomy_set_id, 비우면 기본 세트). 분류를 확정한 데이터셋이 있으면 바꿀 수 없다.
- 복제: 원본 세트의 F1~F6 코드를 새 코드(F1-<SLUG>-01 …)로 복사하고 extra.source_code 에 원본 코드를 남긴다. 규칙 기반 추천은 이 매핑으로 새 세트에도 적용된다.
- CSV 가져오기 · 내보내기: axis,code,label,definition,active
"""
from __future__ import annotations

import csv
import io
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Process, TaxonomyAxis, TaxonomyCode, TaxonomySet, User, utcnow

SET_AXES = ("F1", "F2", "F3", "F4", "F5", "F6")
_SLUG = re.compile(r"[^a-z0-9]+")


class TaxError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def default_set(db: Session) -> TaxonomySet:
    s = db.scalar(select(TaxonomySet).where(TaxonomySet.is_default.is_(True), TaxonomySet.deleted_at.is_(None)))
    if s is None:
        s = db.scalar(select(TaxonomySet).where(TaxonomySet.slug == "base"))
    if s is None:
        raise TaxError(500, "기본 분류체계 세트가 없습니다")
    return s


def set_of(db: Session, process: Process | None) -> TaxonomySet:
    if process is not None and process.taxonomy_set_id:
        s = db.get(TaxonomySet, process.taxonomy_set_id)
        if s is not None:
            return s
    return default_set(db)


def get(db: Session, set_id: int) -> TaxonomySet:
    s = db.get(TaxonomySet, set_id)
    if s is None or s.deleted_at is not None:
        raise TaxError(404, "분류체계 세트를 찾을 수 없습니다")
    return s


def axes_for(db: Session, s: TaxonomySet) -> list[dict[str, Any]]:
    """세트 기준 축 목록: F1~F6 은 그 세트 코드만, K · N2SF 는 공통 코드."""
    from ..serializers import axis_out

    out = []
    for ax in db.scalars(select(TaxonomyAxis).order_by(TaxonomyAxis.position)):
        o = axis_out(ax)
        if ax.code in SET_AXES:
            o["codes"] = [c for c in o["codes"] if c.get("set_id") == s.id]
        o["in_set"] = ax.code in SET_AXES
        out.append(o)
    return out


def usage(db: Session, s: TaxonomySet) -> int:
    return db.scalar(select(func.count()).select_from(Process).where(Process.taxonomy_set_id == s.id, Process.status != "trashed")) or 0


def out(db: Session, s: TaxonomySet) -> dict[str, Any]:
    counts = dict(db.execute(select(TaxonomyCode.axis_code, func.count()).where(TaxonomyCode.set_id == s.id, TaxonomyCode.active.is_(True)).group_by(TaxonomyCode.axis_code)).all())
    base = db.get(TaxonomySet, s.base_set_id) if s.base_set_id else None
    return {"id": s.id, "slug": s.slug, "name": s.name, "scope": s.scope, "description": s.description, "base_set": {"id": base.id, "name": base.name} if base else None,
            "is_default": s.is_default, "locked": s.locked, "created_by": s.created_label, "created_by_id": s.created_by, "created_at": s.created_at, "updated_at": s.updated_at,
            "code_counts": {a: int(counts.get(a, 0)) for a in SET_AXES}, "code_total": int(sum(counts.values())), "process_count": usage(db, s)}


def make_slug(db: Session, name: str, wanted: str | None) -> str:
    base = _SLUG.sub("-", (wanted or "").lower()).strip("-")[:16]
    if not base:
        # 한글 이름이면 앞 글자 영문 약어가 없으니 set + 번호
        n = (db.scalar(select(func.count()).select_from(TaxonomySet)) or 0) + 1
        base = f"set{n}"
    slug = base
    i = 2
    while db.scalar(select(TaxonomySet).where(TaxonomySet.slug == slug)):
        slug = f"{base}{i}"
        i += 1
    return slug


def can_edit(user: User, s: TaxonomySet) -> bool:
    if user.role == "admin":
        return True
    return user.role == "worker" and not s.locked and s.created_by == user.id


def clone(db: Session, user: User, *, name: str, scope: str | None, description: str | None, base_set_id: int | None, slug: str | None, empty: bool = False) -> TaxonomySet:
    base = get(db, base_set_id) if base_set_id else None
    new = TaxonomySet(slug=make_slug(db, name, slug), name=name.strip(), scope=(scope or "").strip() or None, description=(description or "").strip() or None,
                      base_set_id=base.id if base else None, is_default=False, locked=False, created_by=user.id, created_label=user.name)
    db.add(new)
    db.flush()
    if base is not None and not empty:
        prefix = new.slug.upper().replace("-", "")[:6]
        for ax in SET_AXES:
            src = db.scalars(select(TaxonomyCode).where(TaxonomyCode.set_id == base.id, TaxonomyCode.axis_code == ax).order_by(TaxonomyCode.position)).all()
            for i, c in enumerate(src, start=1):
                db.add(TaxonomyCode(axis_code=ax, set_id=new.id, code=f"{ax}-{prefix}-{i:02d}", label=c.label, definition=c.definition, position=i - 1, active=c.active,
                                    extra={**(c.extra or {}), "source_code": (c.extra or {}).get("source_code") or c.code}))
    db.flush()
    return new


def add_code(db: Session, s: TaxonomySet, axis_code: str, label: str, definition: str | None, *, source_code: str | None = None, extra: dict[str, Any] | None = None) -> TaxonomyCode:
    if axis_code not in SET_AXES:
        raise TaxError(422, "연계키 · 보안등급 축은 코드 체계가 고정되어 있어 추가할 수 없습니다")
    axis = db.get(TaxonomyAxis, axis_code)
    if axis is None:
        raise TaxError(404, "분류 축을 찾을 수 없습니다")
    existing = db.scalars(select(TaxonomyCode).where(TaxonomyCode.set_id == s.id, TaxonomyCode.axis_code == axis_code)).all()
    if any(c.label == label.strip() for c in existing):
        raise TaxError(409, "같은 이름의 코드가 이미 있습니다")
    prefix = "" if s.slug == "base" else s.slug.upper().replace("-", "")[:6] + "-"
    nums = [int(m.group(1)) for c in existing if (m := re.search(r"-(\d+)$", c.code))]
    code = TaxonomyCode(axis_code=axis_code, set_id=s.id, code=f"{axis_code}-{prefix}{(max(nums) if nums else 0) + 1:02d}", label=label.strip(), definition=definition,
                        position=len(existing), active=True, extra={**(extra or {}), **({"source_code": source_code} if source_code else {})})
    db.add(code)
    db.flush()
    return code


def export_csv(db: Session, s: TaxonomySet) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["axis", "code", "label", "definition", "active", "source_code"])
    for ax in SET_AXES:
        for c in db.scalars(select(TaxonomyCode).where(TaxonomyCode.set_id == s.id, TaxonomyCode.axis_code == ax).order_by(TaxonomyCode.position)):
            w.writerow([ax, c.code, c.label, c.definition or "", "1" if c.active else "0", (c.extra or {}).get("source_code", "")])
    return "﻿" + buf.getvalue()


def import_csv(db: Session, s: TaxonomySet, text: str, *, replace: bool = False) -> dict[str, int]:
    """axis,label[,definition][,code][,active][,source_code]. code 가 있고 세트 안에 같은 코드가 있으면 갱신, 없으면 추가. replace 면 파일에 없는 코드는 폐기."""
    rows = list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
    if not rows:
        raise TaxError(422, "비어 있는 CSV 입니다")
    cols = {k.strip().lower(): k for k in rows[0].keys() if k}
    def col(r: dict, *names: str) -> str:
        for n in names:
            if n in cols and r.get(cols[n]) is not None:
                return str(r[cols[n]]).strip()
        return ""
    if not any(n in cols for n in ("axis", "축")) or not any(n in cols for n in ("label", "이름", "명칭")):
        raise TaxError(422, "열 이름에 axis(축) 와 label(이름) 이 있어야 합니다")
    existing = {(c.axis_code, c.code): c for c in db.scalars(select(TaxonomyCode).where(TaxonomyCode.set_id == s.id))}
    by_label = {(c.axis_code, c.label): c for c in existing.values()}
    seen: set[tuple[str, str]] = set()
    added = updated = 0
    for r in rows:
        ax = col(r, "axis", "축").upper()
        ax = {"주제영역": "F1", "데이터유형": "F2", "해상도": "F3", "유통·이용조건": "F4", "이용조건": "F4", "AI활용목적": "F5", "거버넌스": "F6"}.get(ax, ax)
        label = col(r, "label", "이름", "명칭")
        if ax not in SET_AXES or not label:
            continue
        code = col(r, "code", "코드")
        definition = col(r, "definition", "정의", "설명") or None
        active = col(r, "active", "사용") not in ("0", "false", "False", "N", "n", "아니오")
        hit = existing.get((ax, code)) if code else by_label.get((ax, label))
        if hit is not None:
            hit.label, hit.definition, hit.active = label, definition, active
            if col(r, "source_code"):
                hit.extra = {**(hit.extra or {}), "source_code": col(r, "source_code")}
            updated += 1
            seen.add((ax, hit.code))
        else:
            c = add_code(db, s, ax, label, definition, source_code=col(r, "source_code") or None)
            # 파일이 코드를 지정했으면 그대로 쓴다. 단 코드는 전역(축 안)에서 고유해야 하므로 다른 세트와 겹치면 생성한 코드를 유지한다
            if code and (ax, code) not in existing and db.scalar(select(TaxonomyCode).where(TaxonomyCode.axis_code == ax, TaxonomyCode.code == code)) is None:
                c.code = code
            c.active = active
            added += 1
            seen.add((ax, c.code))
    retired = 0
    if replace:
        for (ax, code), c in existing.items():
            if (ax, code) not in seen and c.active:
                c.active = False
                retired += 1
    s.updated_at = utcnow()
    db.flush()
    return {"added": added, "updated": updated, "retired": retired}


def switch_process_set(db: Session, p: Process, new: TaxonomySet) -> dict[str, Any]:
    """프로세스 세트 변경. 확정된 분류가 있으면 거부, 아니면 F1~F6 배정 가운데 새 세트에 없는 코드를 지운다 (source_code 가 같으면 바꿔 준다)."""
    confirmed = [d for d in p.datasets if d.class_confirmed_at]
    if confirmed:
        raise TaxError(409, "분류를 확정한 데이터셋이 있어 세트를 바꿀 수 없습니다 — STEP 4 에서 확정을 해제한 뒤 바꾸세요")
    new_codes = {c.code: c for c in db.scalars(select(TaxonomyCode).where(TaxonomyCode.set_id == new.id, TaxonomyCode.active.is_(True)))}
    all_codes = {c.code: c for c in db.scalars(select(TaxonomyCode).where(TaxonomyCode.axis_code.in_(SET_AXES)))}
    # 뿌리 코드(복제 원본까지 거슬러 올라간 코드)가 같으면 같은 개념으로 본다: 기본 ↔ 복제 세트 양방향 이동
    def root(code: str) -> str:
        seen = set()
        while code in all_codes and code not in seen:
            seen.add(code)
            src = (all_codes[code].extra or {}).get("source_code")
            if not src or src == code:
                break
            code = src
        return code
    by_root: dict[str, str] = {}
    for c in new_codes.values():
        by_root.setdefault(root(c.code), c.code)
    moved = dropped = 0
    for d in p.datasets:
        cls = dict(d.classification or {})
        changed = False
        for ax in SET_AXES:
            vals = cls.get(ax) or []
            kept = []
            for v in vals:
                if v in new_codes:
                    kept.append(v)
                elif root(v) in by_root:
                    kept.append(by_root[root(v)])
                    moved += 1
                else:
                    dropped += 1
            if kept != vals:
                changed = True
                if kept:
                    cls[ax] = kept
                else:
                    cls.pop(ax, None)
        if changed:
            d.classification = cls
    p.taxonomy_set_id = new.id
    p.updated_at = utcnow()
    db.flush()
    return {"moved": moved, "dropped": dropped}


def map_suggestions(db: Session, s: TaxonomySet, suggestions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """규칙 기반 추천(기본 세트 코드 기준)을 이 세트의 코드로 바꾼다. 세트에 대응 코드가 없으면 뺀다."""
    if s.slug == "base":
        return suggestions
    codes = db.scalars(select(TaxonomyCode).where(TaxonomyCode.set_id == s.id, TaxonomyCode.active.is_(True))).all()
    by_source: dict[str, str] = {}
    for c in codes:
        by_source.setdefault(c.code, c.code)
        src = (c.extra or {}).get("source_code")
        if src:
            by_source.setdefault(src, c.code)
    out = []
    for sug in suggestions:
        if sug["axis"] not in SET_AXES:
            out.append(sug)
            continue
        mapped = by_source.get(sug["code"])
        if mapped:
            out.append({**sug, "code": mapped, "source_code": sug["code"]})
    return out
