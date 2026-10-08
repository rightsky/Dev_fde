"""카탈로그 발행.

발행 조건
1. 최신 검증이 발행 모드로 실행되었고 현재 정본과 일치한다 (stale 아님).
2. 그 검증에 대한 직렬화가 있고 파생 자가검증을 통과했다.
3. 대상 데이터셋의 발행 ID 가 민팅 대장에 있다 (발행 모드 검증의 게이트 0 ④ 가 이미 보증).
조건을 만족한 데이터셋만 카탈로그 항목으로 등재(또는 새 버전으로 갱신)한다.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CatalogEntry, Process, SerializationRun, User, ValidationRun, utcnow
from . import activity, canonical, minting


class PublishBlocked(Exception):
    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


def check(process: Process, vr: ValidationRun | None, v_stale: str | None, sr: SerializationRun | None,
          s_stale: str | None) -> list[str]:
    reasons: list[str] = []
    if not process.pub_mode:
        reasons.append("발행 모드가 아닙니다 — STEP 6 에서 발행 모드로 전환해 검증하세요")
    if vr is None or vr.mode != "publish":
        reasons.append("발행 모드 검증 결과가 없습니다")
    elif v_stale:
        reasons.append(v_stale)
    elif vr.pass_count == 0:
        reasons.append("검증을 통과한 데이터셋이 없습니다")
    if sr is None or (vr is not None and sr.validation_run_id != vr.id):
        reasons.append("최신 검증에 대한 직렬화 결과가 없습니다 — STEP 7 변환을 실행하세요")
    elif s_stale:
        reasons.append(s_stale)
    elif sr.ok_count == 0:
        reasons.append("파생 자가검증을 통과한 산출물이 없습니다")
    return reasons


def publish(db: Session, process: Process, user: User, vr: ValidationRun, sr: SerializationRun) -> list[CatalogEntry]:
    by_pd = {d.id: d for d in process.combo}
    ok_ids = {s["dataset_id"] for s in sr.self_verify if s["passed"]}
    files: dict[int, dict[str, str]] = {}
    for a in sr.artifacts:
        files.setdefault(a.dataset_id, {})[a.fmt] = a.content
    out: list[CatalogEntry] = []
    act = activity.log(db, "publish", f"카탈로그 발행 — {process.name} {len(ok_ids)}건", user=user, process_id=process.id,
                       payload={"validation_run_id": vr.id, "serialization_run_id": sr.id})
    for res in vr.results:
        pd = by_pd.get(res.dataset_id)
        if pd is None or not res.passed or pd.id not in ok_ids:
            continue
        canon = canonical.build(db, pd, "publish")
        if not canon.minted or canon.checksum != res.checksum:
            continue
        f = files.get(pd.id, {})
        rec = canon.record
        facets: dict[str, Any] = {
            "classification": {k: rec[k] for k in ("theme", "dataType", "granularity", "aiPurpose", "governance") if k in rec},
            "license": rec.get("license") or rec.get("accessRights"),
            "n2sf": rec.get("n2sfGrade"),
            "keys": rec.get("joinKeys", []),
            "keywords": rec.get("keywords", []),
            "media_type": (rec.get("distribution") or {}).get("mediaType"),
            "form": (rec.get("distribution") or {}).get("format") or ("실시간 스트림" if canon.is_stream else None),
            "triple_count": len(canon.graph),
            "readiness": canon.readiness["level"],
            "relations": rec.get("relations", []),
            "distribution_id": minting.distribution_id(canon.resource_id, pd.asset.ext) if rec.get("distribution") else None,
        }
        search = " ".join(str(x) for x in [
            canon.resource_id, rec.get("title"), rec.get("description"), (rec.get("publisher") or {}).get("label"),
            *rec.get("keywords", []), *rec.get("theme", []), *rec.get("dataType", []), process.combo_title] if x)
        entry = db.scalar(select(CatalogEntry).where(CatalogEntry.resource_id == canon.resource_id))
        fields = dict(
            iri=canon.iri, kind=pd.asset.kind, title=rec.get("title") or pd.asset.name, description=rec.get("description"),
            publisher_label=(rec.get("publisher") or {}).get("label"), asset_id=pd.asset_id, process_id=process.id,
            process_name=process.name, collection_title=process.combo_title, status="published", checksum=canon.checksum,
            turtle=f.get("ttl", ""), jsonld=f.get("jsonld", ""), text_summary=f.get("txt"), schema_json=f.get("schema"),
            facets=facets, search_text=search.lower(), published_by=user.id, published_label=user.name,
            published_at=utcnow(), activity_id=act.id)
        if entry is None:
            entry = CatalogEntry(resource_id=canon.resource_id, version=1, **fields)
            db.add(entry)
        else:
            changed = entry.checksum != canon.checksum
            for k, v in fields.items():
                setattr(entry, k, v)
            if changed:
                entry.version += 1
        out.append(entry)
    db.flush()
    act.text = f"카탈로그 발행 — {process.name} {len(out)}건 ({', '.join(e.resource_id for e in out[:5])})"
    return out


DOC_FORMATS = {"croissant": ("application/ld+json", "croissant.json"), "card": ("text/markdown", "데이터카드.md"),
               "dict": ("text/csv", "데이터사전.csv")}


def documents_for(db: Session, entry: CatalogEntry) -> dict[str, str]:
    """발행본과 같은 정본(체크섬)에서 만든 STEP 7 문서 산출물(Croissant·데이터 카드·데이터 사전)."""
    from ..models import Artifact, ProcessDataset

    rows = db.execute(select(Artifact.fmt, Artifact.content).join(ProcessDataset, ProcessDataset.id == Artifact.dataset_id)
                      .where(ProcessDataset.asset_id == entry.asset_id, Artifact.set_checksum == entry.checksum,
                             Artifact.fmt.in_(list(DOC_FORMATS))).order_by(Artifact.id.desc())).all()
    out: dict[str, str] = {}
    for fmt, content in rows:
        out.setdefault(fmt, content)
    return out
