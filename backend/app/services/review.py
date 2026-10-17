"""발행 검수 (검수 큐 · 승인).

가이드라인 3.4.6 「AI 에이전트 활용 시 보안 고려사항」(표 40)은 제한공유 데이터 접근, 데이터 결합, 개인정보 포함 데이터 처리,
결과물 반출 같은 고위험 작업에 사람의 검토·승인(HITL)을 두고, 공개 데이터 같은 저위험 작업은 자동화할 수 있다고 한다.
이 모듈은 발행 대상의 위험 신호를 계산하고, 요청 → 승인·반려 → 발행의 흐름을 관리한다.

- 위험이 높음이면 관리자도 바로 발행할 수 없고 검수 요청과 승인을 거쳐야 한다.
- 승인자는 고위험 신호를 하나씩 확인(acknowledge)해야 한다.
- 요청자가 스스로 승인하면 사유를 남기고 '자기 승인'으로 표시한다.
- 요청 시점의 변환 결과와 정본 체크섬을 묶어 두고, 그 뒤 내용이 바뀌었으면 승인하지 않는다 (검토한 것 = 발행하는 것).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Attestation, CatalogEntry, Process, ReviewRequest, SerializationRun, User, utcnow
from . import grading, activity, canonical, catalog, diagnosis, gates, serialize, validation

SEVERITY_ORDER = {"high": 3, "medium": 2, "low": 1}
LEVEL_LABEL = {"high": "높음", "medium": "보통", "low": "낮음"}
STATUS_LABEL = {"pending": "검수 대기", "approved": "승인 · 발행", "rejected": "반려", "withdrawn": "요청 취소"}
DIAG_MIN_RATIO = 0.5  # STEP 8 점수가 이 비율 미만이면 '보통' 신호 (이 스튜디오의 기준)


class ReviewError(Exception):
    def __init__(self, status: int, message: str, code: str | None = None, extra: dict[str, Any] | None = None):
        super().__init__(message)
        self.status, self.message, self.code, self.extra = status, message, code, extra or {}


def _signal(code: str, severity: str, label: str, detail: str, datasets: list[str] | None = None) -> dict[str, Any]:
    return {"code": code, "severity": severity, "label": label, "detail": detail, "datasets": datasets or []}


def publish_state(db: Session, p: Process) -> tuple[list[str], Any, SerializationRun | None]:
    """발행 조건(catalog.check)과 최신 검증·변환."""
    st = gates.state(db, p)
    vr, sr = validation.latest_run(db, p.id), serialize.latest_run(db, p.id)
    return catalog.check(p, vr, st["validation"]["stale"], sr, st["serialization"]["stale"]), vr, sr


def assess(db: Session, p: Process, sr: SerializationRun | None) -> dict[str, Any]:
    """발행 대상(자가검증 통과 데이터셋)의 요약과 위험 신호. 위험 수준은 신호 가운데 가장 높은 것."""
    by_id = {d.id: d for d in p.combo}
    targets = [s for s in (sr.self_verify if sr else []) if s.get("passed") and s["dataset_id"] in by_id]
    c12 = db.scalar(select(Attestation).where(Attestation.process_id == p.id, Attestation.item_id == "C-12"))
    pii_checked = bool(c12 and c12.status == "met")
    datasets: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    grade_s, grade_c, grade_unset, pii_ds, pii_ai, unset_terms, republish = [], [], [], [], [], [], []
    grade_s1, basis_missing, below_basis, prohibited_block, prohibited_review = [], [], [], [], []
    for s in targets:
        pd = by_id[s["dataset_id"]]
        canon = canonical.build(db, pd, "publish")
        rec = canon.record
        grade = str(rec.get("n2sfGrade") or "")
        pii = [c["name"] for t in (pd.asset.profile or {}).get("tables", []) for c in t.get("columns", []) if c.get("pii")]
        terms = rec.get("aiUsageTerms") or {}
        entry = db.scalar(select(CatalogEntry).where(CatalogEntry.resource_id == s["resource_id"]))
        rid = s["resource_id"]
        datasets.append({"dataset_id": pd.id, "resource_id": rid, "title": s.get("name"), "checksum": s["checksum"],
                         "kind": pd.asset.kind, "n2sf": grade or None, "pii": pii, "ai_terms": terms,
                         "current_version": entry.version if entry else None,
                         "change": "new" if entry is None else ("same" if entry.checksum == s["checksum"] and entry.status == "published" else "update")})
        gst = grading.state(pd)
        grade = gst["grade"] or ""
        if grade == "C":
            grade_c.append(rid)
        elif grade == "S2":
            grade_s.append(rid)
        elif grade == "S1":
            grade_s1.append(rid)
        elif not grade:
            grade_unset.append(rid)
        if grade in ("S1", "S2", "C") and not gst["basis_complete"]:
            basis_missing.append(rid)
        if gst["below_suggested"]:
            below_basis.append(f"{rid} ({gst['suggested_label']} 제안 → {gst['grade_label']})")
        if gst["prohibited"]["types"]:
            (prohibited_block if gst["prohibited"]["blocked"] else prohibited_review).append(f"{rid} ({', '.join(gst['prohibited']['labels'])})")
        if pii:
            pii_ds.append(f"{rid}({', '.join(pii[:3])}{' 외' if len(pii) > 3 else ''})")
            if terms.get("ai_training") in ("permitted", "conditional") or terms.get("ai_redistribution") in ("permitted", "conditional"):
                pii_ai.append(rid)
        if len(terms) < len(canonical.AI_TERMS):
            unset_terms.append(rid)
        if entry is not None and entry.checksum != s["checksum"]:
            republish.append(f"{rid} v{entry.version}→v{entry.version + 1}")

    if grade_c:
        signals.append(_signal("grade_c", "high", "N²SF C(기밀) 등급", "통제 등급 데이터를 카탈로그에 올립니다. 공개 범위를 다시 확인하세요", grade_c))
    if grade_s:
        signals.append(_signal("grade_s2", "high", "N²SF S2(제한 공유) 등급",
                               "개별 기록·민감 정보가 포함된 제한 공유 데이터입니다. 기관 간 협약 · 사전 승인 · 에이전트 노출 범위를 확인하세요 (3.6.1 · 표 40)", grade_s))
    if grade_s1:
        signals.append(_signal("grade_s1", "medium", "N²SF S1(조건부 공유) 등급",
                               "비식별·집계 자료로 이용약정과 목적 확인을 전제로 제공하는 데이터입니다. 이용조건(표 39)이 그에 맞는지 확인하세요", grade_s1))
    if grade_unset:
        signals.append(_signal("grade_unset", "medium", "보안등급 미지정", "STEP 4 에서 N²SF 등급을 정하지 않았습니다. 미지정은 S2 로 취급합니다", grade_unset))
    if basis_missing:
        signals.append(_signal("grade_basis_missing", "medium", "등급 판단 근거 미작성",
                               "S1 이상 등급인데 개인정보 유형 · 재식별 위험도 · 보안·법적 제한을 적지 않았습니다 (3.6.1 판단 항목)", basis_missing))
    if below_basis:
        signals.append(_signal("grade_below_basis", "high", "판단 근거보다 낮은 등급",
                               "담당자가 제안 등급보다 낮게 정했습니다. STEP 4 에 적힌 사유가 타당한지 확인하세요", below_basis))
    if prohibited_block:
        signals.append(_signal("share_prohibited", "high", "표 41 공유 불가 유형 해당 — 발행에서 제외됨",
                               "고유식별정보 · 국가보안 · 제3자 제공 금지 · 재식별 위험 잔존 데이터는 외부 카탈로그에 올리지 않습니다. 승인해도 이 데이터셋은 빠집니다", prohibited_block))
    if prohibited_review:
        signals.append(_signal("share_prohibited", "high", "표 41 공유 불가 유형 해당",
                               "원칙적으로 공유가 제한되는 유형입니다 (FDE_SHARE_PROHIBITED=review 로 발행은 허용). 제한 사유가 해소되었는지 확인하세요", prohibited_review))
    if pii_ds:
        signals.append(_signal("pii", "medium" if pii_checked else "high", "개인정보 의심 컬럼",
                               ("담당자가 STEP 8 C-12(개인정보 보호)에서 확인했습니다" if pii_checked
                                else "자동 탐지 결과입니다. 비식별 처리 여부를 확인하세요 (STEP 8 C-12 확인 대기)"), pii_ds))
    if pii_ai:
        signals.append(_signal("pii_ai_use", "high", "개인정보 의심 데이터에 AI 학습·재배포 허용",
                               "AI 활용 이용조건에서 AI 학습이나 재배포를 허용했습니다. 재식별 위험을 검토하세요 (표 40 재식별 위험)", pii_ai))
    if len(targets) > 1 and p.relations:
        sev = "high" if pii_ds else "medium"
        signals.append(_signal("combination", sev, "데이터 결합 포함",
                               f"조합 안 관계 {len(p.relations)}건. 결합으로 개인·민감 속성이 추론될 수 있는지 검토하세요 (표 39 · 표 40)",
                               [d["resource_id"] for d in datasets]))
    dr = diagnosis.latest_run(db, p.id)
    st = gates.state(db, p)
    diag = None
    if dr is None:
        signals.append(_signal("diagnosis_missing", "medium", "STEP 8 진단 미실행", "가이드라인 준수 진단 없이 발행합니다"))
    else:
        stale = st["diagnosis"]["stale"]
        ratio = dr.score / dr.max_score if dr.max_score else 0
        diag = {"run_id": dr.id, "score": dr.score, "max_score": dr.max_score, "ratio": round(ratio, 3), "stale": stale}
        if stale:
            signals.append(_signal("diagnosis_stale", "medium", "STEP 8 진단이 최신 아님", stale))
        elif ratio < DIAG_MIN_RATIO:
            signals.append(_signal("diagnosis_low", "medium", "가이드라인 준수 점수 낮음",
                                   f"{dr.score:g}/{dr.max_score:g}점 ({round(ratio * 100)}%) — 기준 {round(DIAG_MIN_RATIO * 100)}%"))
    if unset_terms:
        signals.append(_signal("ai_terms_unset", "low", "AI 활용 이용조건 미정 항목 있음",
                               "에이전트에게는 미정 항목을 그 용도로 쓰지 말라고 안내합니다", unset_terms))
    if republish:
        signals.append(_signal("republish", "low", "기존 발행본 갱신", "새 버전으로 바뀝니다", republish))
    level = max((s["severity"] for s in signals), key=lambda x: SEVERITY_ORDER[x], default="low")
    return {"level": level, "level_label": LEVEL_LABEL[level], "signals": signals, "datasets": datasets, "diagnosis": diag,
            "pii_checked": pii_checked}


def pending(db: Session, process_id: int) -> ReviewRequest | None:
    return db.scalar(select(ReviewRequest).where(ReviewRequest.process_id == process_id, ReviewRequest.status == "pending"))


def latest(db: Session, process_id: int) -> ReviewRequest | None:
    return db.scalar(select(ReviewRequest).where(ReviewRequest.process_id == process_id).order_by(ReviewRequest.id.desc()).limit(1))


def submit(db: Session, p: Process, user: User, message: str | None) -> ReviewRequest:
    if p.status == "trashed":
        raise ReviewError(409, "휴지통에 있는 프로세스는 검수 요청할 수 없습니다")
    if pending(db, p.id):
        raise ReviewError(409, "이미 검수 대기 중인 요청이 있습니다", "REVIEW_PENDING")
    reasons, _vr, sr = publish_state(db, p)
    if reasons:
        raise ReviewError(409, reasons[0], "PUBLISH_BLOCKED", {"reasons": reasons})
    a = assess(db, p, sr)
    if not a["datasets"]:
        raise ReviewError(409, "발행할 수 있는 데이터셋이 없습니다")
    if all(d["change"] == "same" for d in a["datasets"]):
        raise ReviewError(409, "모든 데이터셋이 이미 같은 내용으로 발행되어 있습니다")
    rr = ReviewRequest(process_id=p.id, message=(message or "").strip() or None, serialization_run_id=sr.id if sr else None,
                       checksums={d["resource_id"]: d["checksum"] for d in a["datasets"]}, risk_level=a["level"],
                       signals=a["signals"], datasets=a["datasets"], diagnosis=a["diagnosis"], requested_by=user.id,
                       requested_label=user.name, requested_at=utcnow())
    db.add(rr)
    db.flush()
    activity.log(db, "review_request", f"발행 검수 요청 #{rr.id} — {p.name} (위험 {LEVEL_LABEL[a['level']]}, {len(a['datasets'])}건)",
                 user=user, process_id=p.id, payload={"review_id": rr.id, "risk": a["level"]})
    return rr


def changed_since(db: Session, rr: ReviewRequest) -> str | None:
    """요청 뒤에 발행 대상이 바뀌었으면 그 사유."""
    p = db.get(Process, rr.process_id)
    if p is None:
        return "프로세스가 없습니다"
    reasons, _vr, sr = publish_state(db, p)
    if reasons:
        return "지금은 발행 조건을 만족하지 않습니다 — " + reasons[0]
    if sr is None or sr.id != rr.serialization_run_id:
        return "요청 뒤에 변환(STEP 7)이 다시 실행되었습니다"
    now = {s["resource_id"]: s["checksum"] for s in sr.self_verify if s.get("passed")}
    if now != rr.checksums:
        return "요청 뒤에 정본 내용이 바뀌었습니다"
    return None


def approve(db: Session, rr: ReviewRequest, user: User, note: str | None, acknowledged: list[str]) -> list[CatalogEntry]:
    if rr.status != "pending":
        raise ReviewError(409, f"이미 처리된 요청입니다 ({STATUS_LABEL.get(rr.status, rr.status)})")
    why = changed_since(db, rr)
    if why:
        raise ReviewError(409, why + " — 반려하고 다시 요청하세요", "REVIEW_STALE")
    high = [s["code"] for s in rr.signals if s["severity"] == "high"]
    missing = [c for c in high if c not in set(acknowledged)]
    if missing:
        raise ReviewError(422, "고위험 신호를 모두 확인해야 승인할 수 있습니다", "ACK_REQUIRED", {"missing": missing})
    note = (note or "").strip()
    self_ok = rr.requested_by == user.id
    if self_ok and get_settings().review_self_approve == "deny":
        raise ReviewError(403, "본인이 요청한 발행은 승인할 수 없습니다 (FDE_REVIEW_SELF_APPROVE=deny) — 다른 관리자에게 넘기세요", "SELF_APPROVAL_DENIED")
    if self_ok and rr.risk_level == "high" and len(note) < 10:
        raise ReviewError(422, "본인이 요청한 고위험 발행을 직접 승인하려면 사유를 10자 이상 적으세요", "SELF_APPROVAL_NOTE")
    p = db.get(Process, rr.process_id)
    if p is None or p.status == "trashed":
        raise ReviewError(409, "휴지통에 있는 프로세스는 발행할 수 없습니다 — 복원한 뒤 다시 요청하세요")
    _reasons, vr, sr = publish_state(db, p)  # type: ignore[arg-type]
    entries = catalog.publish(db, p, user, vr, sr)  # type: ignore[arg-type]
    if not entries:
        raise ReviewError(409, "발행할 수 있는 데이터셋이 없습니다")
    rr.status, rr.reviewer_id, rr.reviewer_label, rr.decided_at = "approved", user.id, user.name, utcnow()
    rr.decision_note, rr.acknowledged, rr.self_approved = note or None, [c for c in acknowledged if c in high], self_ok
    rr.published = [e.resource_id for e in entries]
    activity.log(db, "review_approve",
                 f"발행 검수 승인 #{rr.id} — {p.name} {len(entries)}건 발행" + (" (자기 승인)" if self_ok else ""), user=user,
                 process_id=p.id, payload={"review_id": rr.id, "risk": rr.risk_level, "acknowledged": rr.acknowledged,
                                           "published": rr.published, "self_approved": self_ok})  # type: ignore[union-attr]
    return entries


def reject(db: Session, rr: ReviewRequest, user: User, note: str | None) -> None:
    if rr.status != "pending":
        raise ReviewError(409, f"이미 처리된 요청입니다 ({STATUS_LABEL.get(rr.status, rr.status)})")
    note = (note or "").strip()
    if len(note) < 2:
        raise ReviewError(422, "반려 사유를 적으세요")
    rr.status, rr.reviewer_id, rr.reviewer_label, rr.decided_at, rr.decision_note = "rejected", user.id, user.name, utcnow(), note
    activity.log(db, "review_reject", f"발행 검수 반려 #{rr.id} — {note[:80]}", user=user, process_id=rr.process_id,
                 payload={"review_id": rr.id})


def withdraw(db: Session, rr: ReviewRequest, user: User) -> None:
    if rr.status != "pending":
        raise ReviewError(409, "검수 대기 중인 요청만 취소할 수 있습니다")
    if rr.requested_by != user.id and user.role != "admin":
        raise ReviewError(403, "요청한 사람이나 관리자만 취소할 수 있습니다")
    rr.status, rr.decided_at, rr.reviewer_label = "withdrawn", utcnow(), user.name
    activity.log(db, "review_withdraw", f"발행 검수 요청 취소 #{rr.id}", user=user, process_id=rr.process_id,
                 payload={"review_id": rr.id})


def out(db: Session, rr: ReviewRequest, *, check: bool = False) -> dict[str, Any]:
    p = db.get(Process, rr.process_id)
    d = {"id": rr.id, "process_id": rr.process_id, "process_name": p.name if p else None, "status": rr.status,
         "status_label": STATUS_LABEL.get(rr.status, rr.status), "message": rr.message, "risk_level": rr.risk_level,
         "risk_label": LEVEL_LABEL.get(rr.risk_level, rr.risk_level), "signals": rr.signals, "datasets": rr.datasets,
         "diagnosis": rr.diagnosis, "requested_by": rr.requested_label, "requested_by_id": rr.requested_by,
         "requested_at": rr.requested_at.isoformat(), "reviewer": rr.reviewer_label,
         "decided_at": rr.decided_at.isoformat() if rr.decided_at else None, "decision_note": rr.decision_note,
         "acknowledged": rr.acknowledged, "self_approved": rr.self_approved, "published": rr.published,
         "serialization_run_id": rr.serialization_run_id}
    if check and rr.status == "pending":
        d["stale"] = changed_since(db, rr)
    return d
