"""N²SF 등급 판단 근거 · 표 41 공유 불가 점검 · 메타데이터 공개 수준 (가이드라인 v1.1 1.3.2 · 3.6.1 · 표 41).

등급(O · S1 · S2 · C)은 담당자가 정하되, 세 가지 판단 항목(개인정보 유형 · 재식별 위험도 · 보안·법적 제한)에서 **제안 등급**을
계산하고, 제안보다 낮게 정하면 사유를 요구한다. 값을 읽어 판정하지 않는다 (컬럼 이름 · 담당자 입력만 쓴다).
"""
from __future__ import annotations

import re
from typing import Any

from ..config import get_settings
from ..models import ProcessDataset

GRADES = ["O", "S1", "S2", "C"]  # 낮은 순. 등급 비교는 이 순서로 한다
GRADE_LABEL = {"O": "O · 공개", "S1": "S1 · 조건부 공유", "S2": "S2 · 제한 공유", "C": "C · 비공개"}
BASIS_KEY, PROHIBITED_KEY, VISIBILITY_KEY = "N2SF_BASIS", "SHARE_PROHIBITED", "META_VISIBILITY"

# 판단 항목 → 요구하는 최저 등급 (3.6.1 "공공데이터 공개 가능 수준 판단 항목" 예시표를 등급으로 옮긴 것)
PERSONAL_DATA = {  # 개인정보 유형
    "none": ("비개인정보", "O"), "anonymized": ("익명정보", "O"), "pseudonymized": ("가명정보", "S1"),
    "personal": ("개인정보", "S2"), "sensitive": ("민감정보·고유식별정보", "C"),
}
REIDENTIFICATION = {  # 재식별 위험도
    "low": ("낮음 (단독·결합 모두 식별 곤란)", "O"), "medium": ("중간 (결합 시 식별 가능)", "S1"), "high": ("높음 (단독 식별 가능)", "S2"),
}
LEGAL = {  # 보안·법적 제한
    "none": ("일반공개", "O"), "trade-secret": ("영업비밀·제3자 권리 포함", "S1"),
    "statutory": ("법령상 비공개", "C"), "national-security": ("국가안전 관련", "C"),
}
BASIS_FIELDS = (("personal_data", "개인정보 유형", PERSONAL_DATA), ("reidentification", "재식별 위험도", REIDENTIFICATION), ("legal", "보안·법적 제한", LEGAL))

# 표 41 공유 불가한 데이터 5가지 유형
PROHIBITED_TYPES = {
    "unique-identifier": "고유식별정보 포함 (주민등록번호 · 여권번호 등)",
    "national-security": "국가보안사항 (비밀 · 비공개 분류)",
    "third-party-ban": "개별 법률의 제3자 제공 금지 (의료법 · 신용정보법 등)",
    "reidentification-risk": "비식별 처리 뒤에도 재식별 위험 잔존",
    "org-designated": "기관이 공유 제한으로 지정",
}
AUTO_TYPES = ("unique-identifier", "national-security", "reidentification-risk")  # 자동 신호가 있는 유형
_UNIQUE_ID = re.compile(r"주민|여권|운전면허|외국인등록|passport|resident_?no|rrn|jumin|ssn|driver_?licen", re.IGNORECASE)

VISIBILITIES = {"detail": "상세 공개 (설명 · 스키마 · 카드까지, 등급 범위 안의 이용자에게)", "listing": "목록만 공개 (제목 · 기관 · 등급만, 등급과 무관하게 모든 이용자에게)",
                "internal": "기관 내부 한정 (외부 · 에이전트에는 존재도 알리지 않음)"}
MIN_REASON = 20


def grade_of(pd: ProcessDataset) -> str | None:
    g = (pd.classification or {}).get("N2SF")
    return str(g).replace("N2SF-", "") if g else None


def normalize(grade: str | None) -> str | None:
    """세분화 전 'S' 는 보수적으로 S2 로 본다."""
    if grade is None:
        return None
    g = str(grade).replace("N2SF-", "")
    return "S2" if g == "S" else g


def rank(grade: str | None) -> int:
    g = normalize(grade)
    return GRADES.index(g) if g in GRADES else -1


def basis(pd: ProcessDataset) -> dict[str, Any]:
    b = (pd.classification or {}).get(BASIS_KEY)
    return b if isinstance(b, dict) else {}


def suggest(b: dict[str, Any]) -> tuple[str | None, list[str]]:
    """판단 항목에서 제안 등급과 그 이유. 항목이 하나도 없으면 (None, [])."""
    best, reasons = -1, []
    for key, label, table in BASIS_FIELDS:
        v = b.get(key)
        if v in table:
            name, g = table[v]
            reasons.append(f"{label}: {name} → {GRADE_LABEL[g]} 이상")
            best = max(best, GRADES.index(g))
    return (GRADES[best] if best >= 0 else None), reasons


def auto_prohibited(pd: ProcessDataset, b: dict[str, Any] | None = None) -> dict[str, str]:
    """표 41 유형 가운데 자동 신호가 있는 것: {유형: 근거}."""
    b = basis(pd) if b is None else b
    out: dict[str, str] = {}
    cols = [c["name"] for t in (pd.asset.profile or {}).get("tables", []) for c in t.get("columns", [])]
    hit = [c for c in cols if _UNIQUE_ID.search(c)]
    if hit:
        out["unique-identifier"] = f"컬럼 이름 패턴: {', '.join(hit[:4])}"
    elif b.get("personal_data") == "sensitive":
        out["unique-identifier"] = "개인정보 유형을 민감정보·고유식별정보로 판단"
    if b.get("legal") == "national-security":
        out["national-security"] = "보안·법적 제한을 국가안전 관련으로 판단"
    if b.get("reidentification") == "high" and not (pd.meta or {}).get("card_protection"):
        out["reidentification-risk"] = "재식별 위험 높음인데 비식별·보호 조치(데이터 카드) 기록이 없음"
    return out


def prohibited(pd: ProcessDataset) -> dict[str, Any]:
    """표 41 판정 종합. types = 지금 유효한 유형 (자동 신호 가운데 담당자가 사유를 적어 해제한 것은 뺀다 + 수동 지정)."""
    raw = (pd.classification or {}).get(PROHIBITED_KEY) or {}
    manual = [t for t in (raw.get("manual") or []) if t in PROHIBITED_TYPES]
    overrides = {k: v for k, v in (raw.get("overrides") or {}).items() if k in AUTO_TYPES and str(v or "").strip()}
    auto = auto_prohibited(pd)
    active = sorted({*(t for t in auto if t not in overrides), *manual})
    mode = get_settings().share_prohibited
    return {"types": active, "labels": [PROHIBITED_TYPES[t] for t in active], "auto": auto, "overrides": overrides, "manual": manual,
            "blocked": bool(active) and mode == "block", "mode": mode}


def visibility(pd: ProcessDataset) -> str:
    v = (pd.classification or {}).get(VISIBILITY_KEY)
    if v in VISIBILITIES:
        return str(v)
    # 기본값: C 는 존재도 드러내지 않는다(internal). 목록만 공개(listing)는 담당자가 명시적으로 고를 때만
    return "internal" if normalize(grade_of(pd)) == "C" else "detail"


def state(pd: ProcessDataset) -> dict[str, Any]:
    """화면·검수·정본이 함께 쓰는 등급 상태 요약."""
    b = basis(pd)
    sug, reasons = suggest(b)
    g = normalize(grade_of(pd))
    below = sug is not None and g is not None and rank(g) < rank(sug)
    return {
        "grade": g, "grade_label": GRADE_LABEL.get(g or "", None), "suggested": sug, "suggested_label": GRADE_LABEL.get(sug or "", None),
        "reasons": reasons, "basis": b, "basis_complete": all(b.get(k) for k, _, _ in BASIS_FIELDS),
        "below_suggested": below, "below_reason": b.get("reason") if below else None,
        "prohibited": prohibited(pd), "visibility": visibility(pd), "visibility_explicit": (pd.classification or {}).get(VISIBILITY_KEY) in VISIBILITIES,
        "options": {"personal_data": {k: v[0] for k, v in PERSONAL_DATA.items()}, "reidentification": {k: v[0] for k, v in REIDENTIFICATION.items()},
                    "legal": {k: v[0] for k, v in LEGAL.items()}, "prohibited_types": PROHIBITED_TYPES, "visibilities": VISIBILITIES,
                    "min_reason": MIN_REASON},
    }


def validate(grade: str | None, b: dict[str, Any]) -> str | None:
    """저장 전 검사. 제안보다 낮은 등급에는 사유가 필요하다. 문제가 있으면 메시지."""
    sug, _ = suggest(b)
    if sug is None or grade is None:
        return None
    if rank(grade) < rank(sug) and len(str(b.get("reason") or "").strip()) < MIN_REASON:
        return f"판단 근거로는 {GRADE_LABEL[sug]} 이상인데 {GRADE_LABEL[normalize(grade) or '']} 로 정했습니다 — 낮추는 사유를 {MIN_REASON}자 이상 적으세요"
    return None
