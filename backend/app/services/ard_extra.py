"""ARD 관리 v0.19 — 버전 비교 · 공유 링크.

버전 비교: 같은 데이터셋의 두 변환 회차(또는 발행본)의 JSON-LD 를 rdflib 로 읽어 트리플 단위로 비교한다 (빈 노드는 rdflib.compare 가 정렬).
            결과는 속성(predicate)별로 추가 · 삭제 · 변경을 묶어 사람이 읽는 표로 준다.
공유 링크: 수요처가 로그인 없이 내려받는 만료형 링크. O · S1 등급 산출물만, 토큰은 해시만 저장, 횟수 · 만료 · 회수.
"""
from __future__ import annotations

import hashlib
import secrets
from collections import defaultdict
from datetime import timedelta
from typing import Any

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.compare import graph_diff, to_isomorphic
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Artifact, CatalogEntry, Process, ProcessDataset, SerializationRun, ShareLink, User, utcnow
from . import ard, grading

SHARE_GRADES = ("O", "S1")
SHARE_MAX_DAYS = 90
SHARE_MAX_DOWNLOADS = 100


# ----------------------------------------------------------------- 버전 비교
def versions(db: Session, pd: ProcessDataset) -> list[dict[str, Any]]:
    """이 데이터셋의 JSON-LD 가 있는 변환 회차 + 발행본."""
    users = ard._users(db)  # noqa: SLF001
    out = []
    runs = db.scalars(select(SerializationRun).where(SerializationRun.process_id == pd.process_id).order_by(SerializationRun.id.desc())).all()
    for sr in runs:
        a = next((x for x in sr.artifacts if x.dataset_id == pd.id and x.fmt == "jsonld"), None)
        if a is None:
            continue
        out.append({"ref": f"run:{sr.id}", "label": f"변환 #{sr.id}", "kind": "run", "run_id": sr.id, "mode": sr.mode, "at": sr.started_at,
                    "actor": ard.actor_of(users, sr.triggered_by), "checksum": a.set_checksum, "size": a.size, "latest": sr.id == runs[0].id})
    entry = db.scalar(select(CatalogEntry).where(CatalogEntry.asset_id == pd.asset_id, CatalogEntry.process_id == pd.process_id))
    if entry is not None:
        out.insert(0, {"ref": f"published:{entry.id}", "label": f"발행본 {entry.resource_id} v{entry.version}", "kind": "published", "run_id": None, "mode": "publish",
                       "at": entry.published_at, "actor": ard.actor_of(users, entry.published_by), "checksum": entry.checksum, "size": len(entry.jsonld.encode("utf-8")),
                       "latest": False, "status": entry.status})
    return out


def _jsonld_of(db: Session, pd: ProcessDataset, ref: str) -> tuple[str, str] | None:
    kind, _, id_ = ref.partition(":")
    if kind == "run" and id_.isdigit():
        a = db.scalar(select(Artifact).where(Artifact.run_id == int(id_), Artifact.dataset_id == pd.id, Artifact.fmt == "jsonld"))
        return (a.content, f"변환 #{id_}") if a else None
    if kind == "published" and id_.isdigit():
        e = db.get(CatalogEntry, int(id_))
        return (e.jsonld, f"발행본 {e.resource_id} v{e.version}") if e and e.asset_id == pd.asset_id else None
    return None


def _short(g: Graph, term: Any) -> str:
    if isinstance(term, URIRef):
        try:
            q = g.namespace_manager.normalizeUri(term)
            return q if not q.startswith("<") else str(term)
        except Exception:  # noqa: BLE001
            return str(term)
    if isinstance(term, BNode):
        return "(빈 노드)"
    if isinstance(term, Literal):
        s = str(term)
        return (s[:200] + "…") if len(s) > 200 else s
    return str(term)


def diff(db: Session, pd: ProcessDataset, ref_from: str, ref_to: str) -> dict[str, Any]:
    a = _jsonld_of(db, pd, ref_from)
    b = _jsonld_of(db, pd, ref_to)
    if a is None or b is None:
        raise ValueError("비교할 JSON-LD 가 없습니다")
    ga, gb = Graph(), Graph()
    ga.parse(data=a[0], format="json-ld")
    gb.parse(data=b[0], format="json-ld")
    both, only_a, only_b = graph_diff(to_isomorphic(ga), to_isomorphic(gb))
    # 같은 (주어, 술어) 에서 값만 바뀐 것은 '변경' 으로 묶는다
    rm = defaultdict(list)
    add = defaultdict(list)
    for s, p, o in only_a:
        rm[(s, p)].append(o)
    for s, p, o in only_b:
        add[(s, p)].append(o)
    rows = []
    for key in sorted(set(rm) | set(add), key=lambda k: (str(k[1]), str(k[0]))):
        s, p = key
        old, new = rm.get(key, []), add.get(key, [])
        rows.append({"subject": _short(gb if key in add else ga, s), "predicate": _short(gb if key in add else ga, p), "predicate_iri": str(p),
                     "old": [_short(ga, o) for o in old], "new": [_short(gb, o) for o in new],
                     "change": "changed" if old and new else ("added" if new else "removed")})
    by_pred = defaultdict(lambda: {"added": 0, "removed": 0, "changed": 0})
    for r in rows:
        by_pred[r["predicate"]][r["change"]] += 1
    return {"from": {"ref": ref_from, "label": a[1], "triples": len(ga)}, "to": {"ref": ref_to, "label": b[1], "triples": len(gb)},
            "unchanged": len(both), "added": len(only_b), "removed": len(only_a),
            "rows": rows[:500], "truncated": len(rows) > 500,
            "by_predicate": [{"predicate": k, **v} for k, v in sorted(by_pred.items(), key=lambda kv: -(kv[1]["added"] + kv[1]["removed"] + kv[1]["changed"]))],
            "identical": not only_a and not only_b}


# ----------------------------------------------------------------- 공유 링크
def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def create(db: Session, user: User, *, kind: str, target_id: int, dataset_id: int | None, days: int, max_downloads: int, recipient: str | None, note: str | None) -> tuple[ShareLink, str]:
    """링크를 만든다. 대상 산출물의 등급이 O · S1 이어야 한다. 반환: (링크, 원문 토큰 — 이때 한 번만)."""
    if kind == "package":
        pd = db.get(ProcessDataset, target_id)
        if pd is None:
            raise ValueError("데이터셋을 찾을 수 없습니다")
        got = ard.build_package(db, pd)
        if got is None:
            raise ValueError("이 데이터셋의 변환 산출물이 없습니다")
        filename, meta = got[1], {"process_id": pd.process_id, "dataset_id": pd.id, "grade": got[2]["n2sf"]["grade"]}
    else:
        got = ard.fetch_file(db, kind, target_id, dataset_id)
        if got is None:
            raise ValueError("산출물을 찾을 수 없습니다")
        filename, meta = got[1], got[3]
    grade = grading.normalize(meta.get("grade")) or "S2"
    if grade not in SHARE_GRADES:
        raise PermissionError(f"공유 링크는 O · S1 등급 산출물만 만들 수 있습니다 (이 산출물: {grade}). S2 는 MCP 건별 승인이나 직접 전달을 쓰세요")
    days = max(1, min(SHARE_MAX_DAYS, days))
    max_downloads = max(1, min(SHARE_MAX_DOWNLOADS, max_downloads))
    token = secrets.token_urlsafe(24)
    link = ShareLink(token_hash=_hash(token), token_prefix=token[:8], kind=kind, target_id=target_id, dataset_id=meta.get("dataset_id") if kind != "package" else target_id,
                     process_id=meta.get("process_id"), filename=filename, grade=grade, recipient=(recipient or "").strip() or None, note=(note or "").strip() or None,
                     expires_at=utcnow() + timedelta(days=days), max_downloads=max_downloads, created_by=user.id, created_label=user.name)
    db.add(link)
    db.flush()
    return link, token


def resolve(db: Session, token: str) -> tuple[ShareLink | None, str | None]:
    """(링크, 거부 사유). 만료 · 회수 · 횟수 초과 · 등급 상승을 매번 다시 본다."""
    link = db.scalar(select(ShareLink).where(ShareLink.token_hash == _hash(token)))
    if link is None:
        return None, "링크가 없거나 잘못되었습니다"
    if link.revoked_at is not None:
        return link, "회수된 링크입니다"
    if link.expires_at <= utcnow():
        return link, "만료된 링크입니다"
    if link.downloads >= link.max_downloads:
        return link, "내려받기 횟수를 모두 썼습니다"
    # 만든 뒤 등급이 올라갔으면 막는다 (N²SF 재분류 반영)
    pd = db.get(ProcessDataset, link.dataset_id) if link.dataset_id else None
    p = db.get(Process, link.process_id) if link.process_id else None
    grade = ard._dataset_grade(pd) if pd else (ard._process_grade(p) if p else None)  # noqa: SLF001
    if grade and grade not in SHARE_GRADES:
        return link, f"산출물 등급이 {grade} 로 바뀌어 이 링크로는 내려받을 수 없습니다"
    if p is not None and p.status == "trashed":
        return link, "원본 프로세스가 삭제되었습니다"
    return link, None


def fetch(db: Session, link: ShareLink) -> tuple[bytes, str, str] | None:
    if link.kind == "package":
        pd = db.get(ProcessDataset, link.target_id)
        got = ard.build_package(db, pd) if pd else None
        return (got[0], got[1], "application/zip") if got else None
    got = ard.fetch_file(db, link.kind, link.target_id, link.dataset_id)
    return (got[0], got[1], got[2]) if got else None


def out(link: ShareLink, *, base_url: str | None = None) -> dict[str, Any]:
    now = utcnow()
    state = "revoked" if link.revoked_at else "expired" if link.expires_at <= now else "exhausted" if link.downloads >= link.max_downloads else "active"
    return {"id": link.id, "token_prefix": link.token_prefix, "kind": link.kind, "kind_label": ard.KINDS.get(link.kind, link.kind), "target_id": link.target_id,
            "dataset_id": link.dataset_id, "process_id": link.process_id, "filename": link.filename, "grade": link.grade, "recipient": link.recipient, "note": link.note,
            "expires_at": link.expires_at, "max_downloads": link.max_downloads, "downloads": link.downloads, "last_downloaded_at": link.last_downloaded_at,
            "created_by": link.created_label, "created_at": link.created_at, "revoked_at": link.revoked_at, "state": state,
            "path": f"/share/{link.token_prefix}…" if base_url is None else None}
