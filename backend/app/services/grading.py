"""N²SF 등급 판단 근거 · 표 41 공유 불가 점검 · 메타데이터 공개 수준 (가이드라인 v1.1 1.3.2 · 3.6.1 · 표 41).

등급(O · S1 · S2 · C)은 담당자가 정하되, 세 가지 판단 항목(개인정보 유형 · 재식별 위험도 · 보안·법적 제한)에서 **제안 등급**을
계산하고, 제안보다 낮게 정하면 사유를 요구한다. 값을 읽어 판정하지 않는다 (컬럼 이름 · 담당자 입력만 쓴다).
"""
from __future__ import annotations

import re
from datetime import UTC
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


def org_grade(pd: ProcessDataset) -> dict[str, Any] | None:
    """기관 등급표에서 이 자산에 매칭된 행 가운데 가장 높은 등급."""
    from sqlalchemy import select
    from sqlalchemy.orm import object_session

    from ..models import OrgGradeEntry

    db = object_session(pd)
    if db is None:
        return None
    rows = db.scalars(select(OrgGradeEntry).where(OrgGradeEntry.asset_id == pd.asset_id)).all()
    if not rows:
        return None
    top = max(rows, key=lambda r: rank(r.grade))
    return {"grade": normalize(top.grade), "label": GRADE_LABEL.get(normalize(top.grade) or "", None), "name": top.name, "system": top.system,
            "entries": len(rows), "legal_basis": top.legal_basis, "personal_data": top.personal_data}


def state(pd: ProcessDataset) -> dict[str, Any]:
    """화면·검수·정본이 함께 쓰는 등급 상태 요약."""
    b = basis(pd)
    sug, reasons = suggest(b)
    g = normalize(grade_of(pd))
    og = org_grade(pd)
    cols = column_summary(pd)
    # 제안 등급 = 판단 근거 · 기관 등급표 · 컬럼 민감 항목 가운데 가장 높은 것
    if og and (sug is None or rank(og["grade"]) > rank(sug)):
        sug = og["grade"]
        reasons = reasons + [f"기관 등급표: {og['name']} → {og['label']}"]
    if cols["dataset_personal_data"]:
        cg = PERSONAL_DATA[cols["dataset_personal_data"]][1]
        if sug is None or rank(cg) > rank(sug):
            sug = cg
            reasons = reasons + [f"컬럼 민감 항목: {cols['dataset_personal_label']} 컬럼 있음 → {GRADE_LABEL[cg]} 이상"]
    hints = [f"컬럼 이름 자동 탐지 {cols['suggested_count']}건 (데이터 사전에서 개인정보 여부를 확인하세요 — 등급에는 반영되지 않음)"] if cols["suggested_count"] else []
    below = sug is not None and g is not None and rank(g) < rank(sug)
    org_conflict = bool(og and ((g and rank(og["grade"]) > rank(g)) or (cols["dataset_personal_data"] and rank(PERSONAL_DATA[cols["dataset_personal_data"]][1]) > rank(og["grade"]))))
    return {
        "grade": g, "grade_label": GRADE_LABEL.get(g or "", None), "suggested": sug, "suggested_label": GRADE_LABEL.get(sug or "", None),
        "reasons": reasons, "hints": hints, "basis": b, "basis_complete": all(b.get(k) for k, _, _ in BASIS_FIELDS),
        "below_suggested": below, "below_reason": b.get("reason") if below else None,
        "org_grade": og, "org_conflict": org_conflict, "columns": cols,
        "prohibited": prohibited(pd), "visibility": visibility(pd), "visibility_explicit": (pd.classification or {}).get(VISIBILITY_KEY) in VISIBILITIES,
        "options": {"personal_data": {k: v[0] for k, v in PERSONAL_DATA.items()}, "reidentification": {k: v[0] for k, v in REIDENTIFICATION.items()},
                    "legal": {k: v[0] for k, v in LEGAL.items()}, "prohibited_types": PROHIBITED_TYPES, "visibilities": VISIBILITIES,
                    "min_reason": MIN_REASON},
    }


def validate(grade: str | None, b: dict[str, Any], pd: ProcessDataset | None = None) -> str | None:
    """저장 전 검사. 제안(판단 근거 · 기관 등급표 · 컬럼 민감 항목)보다 낮은 등급에는 사유가 필요하다. 문제가 있으면 메시지."""
    sug, _ = suggest(b)
    why = "판단 근거"
    if pd is not None:
        og = org_grade(pd)
        if og and (sug is None or rank(og["grade"]) > rank(sug)):
            sug, why = og["grade"], f"기관 등급표({og['name']})"
        cols = column_summary(pd)
        if cols["dataset_personal_data"]:
            cg = PERSONAL_DATA[cols["dataset_personal_data"]][1]
            if sug is None or rank(cg) > rank(sug):
                sug, why = cg, f"컬럼 민감 항목({cols['dataset_personal_label']})"
    if sug is None or grade is None:
        return None
    if rank(grade) < rank(sug) and len(str(b.get("reason") or "").strip()) < MIN_REASON:
        return f"{why}로는 {GRADE_LABEL[sug]} 이상인데 {GRADE_LABEL[normalize(grade) or '']} 로 정했습니다 — 낮추는 사유를 {MIN_REASON}자 이상 적으세요"
    return None


# ---------------------------------------------------------------- 컬럼 민감 항목 (가이드라인 생애주기 표: 항목 단위 비식별 처리·기록)
COLUMN_PERSONAL = {"none": "비개인", "pseudonymized": "가명", "personal": "개인정보", "sensitive": "민감·고유식별"}
_COLUMN_RANK = {"none": 0, "pseudonymized": 1, "personal": 2, "sensitive": 3}
DEID_METHODS = {"delete": "삭제", "masking": "마스킹", "categorize": "범주화", "pseudonymize": "가명화", "aggregate": "집계", "other": "기타"}


def column_items(pd: ProcessDataset) -> dict[tuple[str, str], dict[str, Any]]:
    """데이터 사전에 적힌 컬럼 민감 항목: {(표, 컬럼): {personal_data, deid:{method, note, at, by}}}."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for table, cols in ((pd.meta or {}).get("_dictionary") or {}).items():
        for col, ent in (cols or {}).items():
            item: dict[str, Any] = {}
            if (ent or {}).get("personal_data") in COLUMN_PERSONAL:
                item["personal_data"] = ent["personal_data"]
            if isinstance((ent or {}).get("deid"), dict) and ent["deid"].get("method") in DEID_METHODS:
                item["deid"] = ent["deid"]
            if item:
                out[(table, col)] = item
    return out


def column_suggestions(pd: ProcessDataset) -> dict[tuple[str, str], tuple[str, str]]:
    """컬럼 이름 · 프로파일 PII 탐지에서 나온 개인정보 유형 후보: {(표, 컬럼): (유형, 근거)}. 값은 읽지 않는다."""
    out: dict[tuple[str, str], tuple[str, str]] = {}
    for t in (pd.asset.profile or {}).get("tables", []):
        for c in t.get("columns", []):
            if _UNIQUE_ID.search(c["name"]):
                out[(t["name"], c["name"])] = ("sensitive", "컬럼 이름이 고유식별정보 패턴")
            elif c.get("pii"):
                out[(t["name"], c["name"])] = ("personal", f"개인정보 의심 ({c['pii'].get('kind', '')})")
    return out


def column_summary(pd: ProcessDataset) -> dict[str, Any]:
    """컬럼 민감 항목 요약과, 거기서 올라오는 데이터셋 '개인정보 유형' 기본값."""
    items = column_items(pd)
    sugs = column_suggestions(pd)
    # 등급을 끌어올리는 것은 담당자가 데이터 사전에 '확인'한 항목뿐이다. 컬럼 이름 자동 탐지는 힌트로만 보이고
    # (아래 suggested), 담당자가 사전에서 '비개인'으로 표시하면 힌트도 사라진다
    best = ""
    for v in [i.get("personal_data") for i in items.values()]:
        if v and _COLUMN_RANK.get(v, 0) > _COLUMN_RANK.get(best, -1):
            best = v
    pending = [(k, s) for (k, s) in sugs.items() if k not in items]
    marked = sum(1 for i in items.values() if i.get("personal_data"))
    deid = sum(1 for i in items.values() if i.get("deid"))
    needs = [k for k, i in items.items() if i.get("personal_data") in ("personal", "sensitive") and not i.get("deid")]
    return {"marked": marked, "deid": deid, "suggested_count": len(pending),
            "suggested": [{"column": f"{t}.{c}", "personal_data": s[0], "label": COLUMN_PERSONAL.get(s[0], s[0]), "reason": s[1]} for (t, c), s in pending[:20]],
            "needs_deid": [f"{t}.{c}" for t, c in needs], "dataset_personal_data": best or None,
            "dataset_personal_label": PERSONAL_DATA.get(best, ("",))[0] if best else None}


# ---------------------------------------------------------------- 조합 등급 (3.6.1 결합 후 재검토)
def combo_grade(process: Any) -> dict[str, Any]:
    """조합의 등급: 구성 데이터셋 최고 등급이 기본값. 담당자가 낮추면 사유가 필요하다."""
    members = [(d, normalize(grade_of(d))) for d in process.combo]
    graded = [g for _, g in members if g]
    floor = GRADES[max(rank(g) for g in graded)] if graded else None
    chosen = normalize(getattr(process, "combo_grade", None))
    reason = getattr(process, "combo_grade_reason", None)
    below = floor is not None and chosen is not None and rank(chosen) < rank(floor)
    return {"floor": floor, "floor_label": GRADE_LABEL.get(floor or "", None), "grade": chosen or floor,
            "grade_label": GRADE_LABEL.get((chosen or floor) or "", None), "explicit": chosen is not None,
            "below_floor": below, "reason": reason, "unset": [((d.meta or {}).get("title") or d.asset.name) for d, g in members if not g],
            "mixed": len(set(graded)) > 1}


# ---------------------------------------------------------------- AI 이용조건(표 39) 등급별 기본값 (N²SF 기획안 4절)
AI_TERM_DEFAULTS: dict[str, dict[str, str]] = {
    "O": {},
    "S1": {"ai_training": "conditional", "ai_combination": "conditional", "ai_redistribution": "prohibited"},
    "S2": {"ai_training": "prohibited", "ai_combination": "conditional", "ai_automated_access": "conditional", "ai_bulk_access": "prohibited", "ai_redistribution": "prohibited"},
    "C": {"ai_training": "prohibited", "ai_combination": "prohibited", "ai_automated_access": "prohibited", "ai_bulk_access": "prohibited", "ai_redistribution": "prohibited"},
}
AI_TERM_DEFAULT_KEY = "_ai_terms_defaulted"


def apply_term_defaults(pd: ProcessDataset, grade: str | None, by: str) -> list[str]:
    """등급을 정하면 아직 고르지 않은 이용조건 항목을 등급 기본값으로 채운다. 담당자가 이미 고른 항목은 건드리지 않는다. 채운 항목 이름을 돌려준다."""
    g = normalize(grade)
    if not g or g not in AI_TERM_DEFAULTS:
        return []
    meta = dict(pd.meta or {})
    filled = []
    for name, status in AI_TERM_DEFAULTS[g].items():
        if not meta.get(name):
            meta[name] = status
            filled.append(name)
    if filled:
        from datetime import datetime

        meta[AI_TERM_DEFAULT_KEY] = {"grade": g, "fields": sorted(set(filled) | set((meta.get(AI_TERM_DEFAULT_KEY) or {}).get("fields", []))),
                                     "by": by, "at": datetime.now(UTC).replace(microsecond=0).isoformat()}
        pd.meta = meta
    return filled
