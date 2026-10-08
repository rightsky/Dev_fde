"""STEP 8 가이드라인 준수 진단 — 규칙 엔진.

규칙 정의는 data/guideline_rules.json 에 있다 (가이드라인 v1.1 의 80항목). 항목 문구(text)는 원문이고,
판정 기준(criteria)은 이 스튜디오가 정한 것이다. 판정 방식은 네 가지다.
- AUTO-GRAPH   : 데이터셋 정본 그래프에 SPARQL ASK 를 던지거나 검증·직렬화 실행 결과를 본다.
- AUTO-PROFILE : 업로드 파일의 프로파일 통계를 본다.
- AUTO-DERIVED : 연결된 세부 항목의 판정을 종합한다 (15개 원칙 등, 원문에 판정 기준이 없는 항목).
- HUMAN-ATTEST : 담당자가 증빙과 함께 확인한다. 확인 기록이 없으면 '확인 대기'다.

데이터셋 단위 규칙은 조합 전체로 집계한다: 전부 충족 → 충족, 일부 → 부분, 없음 → 미흡. 적용 대상이 없으면 해당 없음(만점에서 제외).
"""
from __future__ import annotations

import re
from typing import Any

from rdflib import URIRef
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Activity, Attestation, DiagnosisRun, Process, ProcessDataset, Relation, User, utcnow
from . import activity, canonical, documents, minting, serialize, validation
from .reference import fix_route, guideline_rules

# 가이드라인 2.1.1 「데이터별 권장 오픈 포맷」 표 (이 스튜디오가 받는 형식 범위에서)
OPEN_EXT = {"csv", "tsv", "json", "xml", "parquet", "orc", "odt", "geojson", "gpkg"}
VENDOR_EXT = {"hwp", "hwpx", "doc", "docx", "xls", "xlsx", "ppt", "pptx"}
LARGE_BYTES = 100 * 1024 * 1024  # '대용량' 의 기준은 가이드라인에 없다 — 이 스튜디오의 기준
_UNNAMED = re.compile(r"^컬럼\d+$")
_STATUS_LABEL = {"met": "충족", "partial": "부분 충족", "unmet": "미흡", "na": "해당 없음", "pending": "확인 대기"}


class _Ctx:
    def __init__(self, db: Session, process: Process):
        self.db = db
        self.process = process
        self.mode = "publish" if process.pub_mode else "draft"
        self.combo = process.combo
        self.canon = {pd.id: canonical.build(db, pd, self.mode) for pd in self.combo}
        self.vr = validation.latest_run(db, process.id)
        self.v_stale = validation.stale_reason(db, process, self.vr)
        self.sr = serialize.latest_run(db, process.id)
        self.attest = {a.item_id: a for a in db.scalars(select(Attestation).where(Attestation.process_id == process.id))}
        # 담당자 확인은 그때의 조합을 보고 한 것이다. 그 뒤에 조합 구성이 바뀌었으면 다시 확인받는다.
        self.combo_changed_at = db.scalar(select(func.max(Activity.started_at)).where(
            Activity.process_id == process.id, Activity.type == "combo_change"))

    def outdated(self, att: Attestation | None) -> bool:
        return bool(att and self.combo_changed_at and att.attested_at < self.combo_changed_at)

    def title(self, pd: ProcessDataset) -> str:
        return (pd.meta or {}).get("title") or pd.asset.name


def _tables(pd: ProcessDataset) -> list[dict[str, Any]]:
    return (pd.asset.profile or {}).get("tables", [])


def _columns(pd: ProcessDataset) -> list[dict[str, Any]]:
    return [c for t in _tables(pd) for c in t["columns"]]


def _ask(ctx: _Ctx, pd: ProcessDataset, query: str) -> bool:
    c = ctx.canon[pd.id]
    return bool(c.graph.query(query, initBindings={"this": URIRef(c.iri)}).askAnswer)


# 각 내장 판정기는 (판정, 근거 문장) 또는 None(해당 없음) 을 돌려준다.
# 판정: True 충족 / False 미흡 / "partial" 부분 / "attest" 담당자 확인 필요(근거 문장은 자동으로 모은 증빙)
def _b_minted(ctx: _Ctx, pd: ProcessDataset):
    rec = minting.minted_record(ctx.db, pd.asset_id)
    return (True, f"{rec.minted_id} 발급됨") if rec else (False, "민팅 대장 미등록 (초안 ID)")


def _b_periodicity(ctx: _Ctx, pd: ProcessDataset):
    if pd.asset.kind == "stream":
        tr = canonical.effective_meta(pd).get("temporal_resolution")
        if not tr:
            return False, "temporalResolution 미승인"
        return (True, f"temporalResolution {tr}") if canonical.is_duration(str(tr)) else ("partial", f"비표준 표기 「{tr}」")
    v = (pd.meta or {}).get("accrual_periodicity")
    if not v:
        return False, "갱신주기 미입력"
    if canonical.is_duration(str(v)) or v == "irregular":
        return True, f"갱신주기 {v}"
    return "partial", f"비표준 표기 「{v}」"


def _relations(ctx: _Ctx, pd: ProcessDataset) -> list[Relation]:
    rels = ctx.db.scalars(select(Relation).where(Relation.process_id == ctx.process.id, Relation.status == "confirmed",
                                                 (Relation.source_id == pd.id) | (Relation.target_id == pd.id))).all()
    return [r for r in rels if r.source.in_combo and r.target.in_combo]


def _b_related(ctx: _Ctx, pd: ProcessDataset):
    if len(ctx.combo) < 2:
        return None
    rels = _relations(ctx, pd)
    return (True, f"확정 관계 {len(rels)}건") if rels else (False, "조합 내 관계 미지정")


def _b_provenance(ctx: _Ctx, pd: ProcessDataset):
    """원천·수집경로·가공 이력: 사람이 적은 출처·가공 이력(dcterms:provenance)이나 파생 관계가 있어야 충족이다."""
    if _ask(ctx, pd, "ASK { ?this dcterms:provenance ?p }"):
        return True, "출처·가공 이력(dcterms:provenance) 기재됨"
    derived = [r for r in _relations(ctx, pd) if r.type == "DERIVED_FROM"]
    if derived:
        return True, f"파생 관계 {len(derived)}건 기록됨"
    if _ask(ctx, pd, "ASK { ?this prov:wasGeneratedBy ?a }"):
        return "partial", "카탈로그 작성 이력만 있음 — 원천·수집경로·가공 이력 없음"
    return False, "이력 정보 없음"


def _b_open_format(ctx: _Ctx, pd: ProcessDataset):
    ext = (pd.asset.ext or "").lower()
    if not ext:
        return False, "파일 형식을 알 수 없음"
    if ext in OPEN_EXT:
        return True, f".{ext} — 권장 오픈 포맷"
    if ext in VENDOR_EXT:
        return False, f".{ext} — 비권장 포맷(벤더 종속)"
    return "partial", f".{ext} — 가이드라인 권장·비권장 목록에 없는 형식"


def _b_structured(ctx: _Ctx, pd: ProcessDataset):
    prof = pd.asset.profile or {}
    tables = [t for t in prof.get("tables", []) if t.get("columns")]
    if pd.asset.kind == "stream":
        n = len(_columns(pd))
        return (True, f"스트림 스키마 {n}필드 등록") if n else (False, "스트림 스키마 필드 미등록")
    if not tables:
        return False, "표 형태로 읽지 못함" + (f" — {prof['error'][:80]}" if prof.get("error") else "")
    issues = []
    for t in tables:
        if t.get("preamble"):
            issues.append(f"[{t['name']}] 헤더 앞에 {len(t['preamble'])}줄")
        unnamed = [c["name"] for c in t["columns"] if _UNNAMED.match(c["name"])]
        if unnamed:
            issues.append(f"[{t['name']}] 이름 없는 컬럼 {len(unnamed)}개")
    cols = sum(len(t["columns"]) for t in tables)
    if issues:
        return "partial", f"표 {len(tables)}개 · 컬럼 {cols}개를 읽었으나 " + ", ".join(issues[:3])
    return True, f"표 {len(tables)}개 · 컬럼 {cols}개 — 첫 줄이 컬럼 이름인 표 구조"


def _b_schema_defined(ctx: _Ctx, pd: ProcessDataset):
    if pd.asset.kind == "stream":
        n = len(_columns(pd))
        return (True, f"스트림 스키마 {n}필드 등록 (이름·자료형)") if n else (False, "스트림 스키마 필드 미등록")
    if _ask(ctx, pd, "ASK { ?this dcat:distribution ?d . ?d csvw:table ?t . ?t csvw:tableSchema ?s . ?s csvw:column ?c }"):
        return True, f"CSVW 스키마 — 컬럼 {len(_columns(pd))}개의 이름·자료형·필수 여부"
    return False, "정본 그래프에 데이터 스키마(csvw:tableSchema) 없음"


def _b_schema_hint(ctx: _Ctx, pd: ProcessDataset):
    n = len(_columns(pd))
    if pd.asset.kind == "stream":
        return "attest", f"스트림 스키마 {n}필드 (이름·자료형만 등록됨)"
    has = _ask(ctx, pd, "ASK { ?this dcat:distribution ?d . ?d csvw:table ?t }")
    return "attest", f"컬럼 {n}개 — 이름·자료형·필수 여부가 CSVW 스키마로 정본에 " + ("있음" if has else "없음")


def _artifact(ctx: _Ctx, pd: ProcessDataset, fmt: str):
    return next((a for a in ctx.sr.artifacts if a.dataset_id == pd.id and a.fmt == fmt), None) if ctx.sr else None


def _grade(done: int, total: int, threshold: float) -> Any:
    ratio = done / total if total else 0
    return True if ratio >= threshold else ("partial" if ratio >= 0.5 else False)


def _b_data_dictionary(ctx: _Ctx, pd: ProcessDataset):
    done, total = documents.dictionary_coverage(pd)
    if not total:
        return None
    if not _artifact(ctx, pd, "dict"):
        return False, f"STEP 7 데이터 사전 미산출 (정의 작성 {done}/{total}개)"
    return _grade(done, total, 1.0), f"데이터 사전 산출 · 정의 작성 {done}/{total}개"


def _b_data_card(ctx: _Ctx, pd: ProcessDataset):
    art = _artifact(ctx, pd, "card")
    done, total = documents.card_coverage(documents.card_items(ctx.canon[pd.id], pd, ctx.vr))
    if not art:
        return False, f"STEP 7 데이터 카드 미산출 (필수 칸 {done}/{total}개 작성 가능)"
    return _grade(done, total, 0.9), f"데이터 카드 {art.filename} · 필수 칸 {done}/{total}개 작성 ({round(done / total * 100)}%)"


def _b_machine_readable(ctx: _Ctx, pd: ProcessDataset):
    if not ctx.sr:
        return False, "STEP 7 변환 미실행"
    sv = next((s for s in ctx.sr.self_verify if s["dataset_id"] == pd.id), None)
    fmts = {a.fmt for a in ctx.sr.artifacts if a.dataset_id == pd.id}
    if sv and sv["passed"] and {"ttl", "jsonld"} <= fmts:
        return True, "Turtle·JSON-LD 산출 · 파생 자가검증 통과"
    if sv and sv["passed"]:
        return "partial", f"산출 포맷 {', '.join(sorted(fmts))} — JSON-LD 미포함"
    return False, "산출물 없음 (검증 미통과 또는 자가검증 실패)"


def _b_iso8601(ctx: _Ctx, pd: ProcessDataset):
    cols = [c for c in _columns(pd) if c["type"] == "datetime"]
    if not cols:
        return None
    bad = [c for c in cols if not c.get("iso8601")]
    if not bad:
        return True, f"날짜·시각 컬럼 {len(cols)}개 전부 ISO 8601"
    fmts = sorted({f["format"] for c in bad for f in c.get("date_formats", [])})
    verdict: Any = "partial" if len(bad) < len(cols) else False
    return verdict, f"비표준 날짜·시각 컬럼 {len(bad)}/{len(cols)}개 ({', '.join(c['name'] for c in bad[:3])}) — 형식 {', '.join(fmts[:4])}"


def _b_missing_markers(ctx: _Ctx, pd: ProcessDataset):
    if not _tables(pd):
        return None
    marks = sorted({m["marker"] for c in _columns(pd) for m in c["missing_markers"]})
    if len(marks) <= 1:
        return True, f"결측 표기 {len(marks)}종" + (f" ({marks[0]})" if marks else " (결측 없음)")
    return False, f"결측 표기 {len(marks)}종 혼재: {', '.join(marks[:6])}"


def _b_large_format(ctx: _Ctx, pd: ProcessDataset):
    size = pd.asset.size or 0
    if size < LARGE_BYTES:
        return None
    ext = (pd.asset.ext or "").lower()
    label = f"{size / 1024 / 1024:.0f}MB"
    return (True, f"{label} · Parquet") if ext == "parquet" else (False, f"{label} · .{ext} — Parquet 또는 압축 제공 권장")


def _endpoint(ctx: _Ctx, pd: ProcessDataset) -> str | None:
    rows = ctx.canon[pd.id].graph.query(
        "SELECT ?u WHERE { { ?this dcat:endpointURL ?u } UNION { ?this dcat:distribution ?d . ?d dcat:accessService ?s . ?s dcat:endpointURL ?u } } LIMIT 1",
        initBindings={"this": URIRef(ctx.canon[pd.id].iri)})
    return next((str(r[0]) for r in rows), None)


def _b_web_api(ctx: _Ctx, pd: ProcessDataset):
    ep = _endpoint(ctx, pd)
    if not ep:
        return False, "API 엔드포인트 미선언"
    if re.match(r"^https?://", ep, re.I):
        return True, f"API 엔드포인트 {ep}"
    return "partial", f"엔드포인트 {ep} — 웹(http) 기반 API 가 아님"


def _b_api_alt(ctx: _Ctx, pd: ProcessDataset):
    ep = _endpoint(ctx, pd)
    if not ep:
        return None
    if _ask(ctx, pd, "ASK { ?this dcat:distribution ?d . ?d dcat:accessURL ?u }"):
        return True, "API 엔드포인트와 파일 접속 URL 이 함께 있음"
    return False, "API 엔드포인트만 있고 파일 접속 URL 없음"


def _b_api_hint(ctx: _Ctx, pd: ProcessDataset):
    ep = _endpoint(ctx, pd)
    return ("attest", f"API 엔드포인트 {ep}") if ep else None


def _b_numeric_hint(ctx: _Ctx, pd: ProcessDataset):
    cols = [c["name"] for c in _columns(pd) if c["type"] in ("integer", "number")]
    return ("attest", f"수치 컬럼 {len(cols)}개: {', '.join(cols[:6])}" + (" 외" if len(cols) > 6 else "")) if cols else None


def _b_pii(ctx: _Ctx, pd: ProcessDataset):
    cols = [c for c in _columns(pd) if c.get("pii")]
    if not cols:
        return None
    return "attest", "개인정보 의심 컬럼: " + ", ".join(f"{c['name']}({c['pii']['kind']})" for c in cols[:6])


_BUILTINS = {"minted": _b_minted, "periodicity": _b_periodicity, "related": _b_related, "provenance": _b_provenance,
             "open_format": _b_open_format, "structured": _b_structured, "schema_defined": _b_schema_defined,
             "schema_hint": _b_schema_hint, "machine_readable": _b_machine_readable, "iso8601": _b_iso8601,
             "missing_markers": _b_missing_markers, "large_format": _b_large_format, "web_api": _b_web_api, "api_alt": _b_api_alt,
             "api_hint": _b_api_hint, "numeric_hint": _b_numeric_hint, "pii": _b_pii,
             "data_dictionary": _b_data_dictionary, "data_card": _b_data_card}
# 판정기가 '해당 없음'을 돌려줄 때 화면에 적을 사유
_NA_REASON = {"related": "조합에 데이터셋이 1건뿐임", "iso8601": "날짜·시각 컬럼 없음", "large_format": "100MB 미만이라 대용량이 아님",
              "api_alt": "API 엔드포인트 미선언", "api_hint": "API 엔드포인트 미선언", "numeric_hint": "수치 컬럼 없음",
              "pii": "개인정보 의심 컬럼 미검출 (컬럼 이름·값 패턴 기준의 자동 탐지 결과)"}


def _route(rule: dict[str, Any]) -> dict[str, Any] | None:
    r = fix_route(rule.get("route"))
    if r:
        return {**r, **({"focus": rule["focus"]} if rule.get("focus") else {})}
    if rule.get("step"):
        return {"key": None, "step": rule["step"], "label": f"STEP {rule['step']}", "focus": None}
    return None


def _base(ctx: _Ctx, rule: dict[str, Any]) -> dict[str, Any]:
    att = ctx.attest.get(rule["id"])
    return {
        "id": rule["id"], "area": rule["area"], "name": rule["name"], "method": rule["method"], "basis": rule["basis"],
        "level": rule.get("level"), "text": rule.get("text"), "property": rule.get("property"), "group": rule.get("group"),
        "criteria": rule.get("criteria"), "remedy": rule.get("remedy"), "difficulty": rule.get("difficulty", 2),
        "datasets": [], "evidence": [], "related": [], "route": _route(rule),
        "attestable": rule["method"] == "HUMAN-ATTEST", "allow_na": bool(rule.get("allow_na")),
        "attestation": ({"status": att.status, "note": att.note, "evidence": att.evidence, "by": att.attested_label,
                         "at": att.attested_at.isoformat(), "outdated": ctx.outdated(att)} if att else None),
    }


def _evaluate(ctx: _Ctx, rule: dict[str, Any]) -> dict[str, Any]:
    """종합(derived) 이외의 항목 1건을 판정한다."""
    res = rule["resolver"]
    old = ctx.attest.get(rule["id"])
    att = None if ctx.outdated(old) else old
    item = _base(ctx, rule)
    human = rule["method"] == "HUMAN-ATTEST"
    verdicts: list[Any] = []
    na_reasons: list[str] = []
    if res["type"] != "attest":
        for pd in ctx.combo:
            stream = pd.asset.kind == "stream"
            if (rule.get("applies") == "dataset" and stream) or (rule.get("applies") == "stream" and not stream):
                continue
            if res["type"] == "ask":
                ok = _ask(ctx, pd, res["query"])
                v: Any = True if ok else ("partial" if rule.get("partial") and _ask(ctx, pd, rule["partial"]["query"]) else False)
                why = "정본 그래프에 있음" if v is True else ("일부만 있음" if v == "partial" else "정본 그래프에 없음")
            else:
                out = _BUILTINS[res["name"]](ctx, pd)
                if out is None:
                    na_reasons.append(_NA_REASON.get(res["name"], "적용 대상 아님"))
                    continue
                v, why = out
            verdicts.append(v)
            if v == "attest":
                status = att.status if att else "pending"
            else:
                status = "met" if v is True else ("partial" if v == "partial" else "unmet")
            row = {"id": pd.id, "name": ctx.title(pd), "status": status, "detail": why}
            if stream and rule.get("focus_stream"):
                row["focus"] = rule["focus_stream"]
            item["datasets"].append(row)
    if human and att:
        # 담당자 확인이 있으면 자동 증빙(해당 없음 포함)보다 우선한다
        item["status"] = att.status
        item["evidence"].append(f"담당자 확인: {_STATUS_LABEL.get(att.status, att.status)} · {att.attested_label} · "
                                f"{att.attested_at:%Y-%m-%d %H:%M}" + (f" — {att.note}" if att.note else ""))
    elif human and (res["type"] == "attest" or verdicts):
        item["status"] = "pending"
        if old:
            item["evidence"].append(f"다시 확인 필요 — 담당자 확인({_STATUS_LABEL.get(old.status, old.status)} · {old.attested_label} · "
                                    f"{old.attested_at:%Y-%m-%d %H:%M}) 뒤에 조합 구성이 바뀌었습니다")
        else:
            item["evidence"].append("담당자 확인 대기 — 증빙을 첨부하고 확인하세요")
    elif not verdicts:
        item["status"] = "na"
        item["evidence"].append("해당 없음: " + (sorted(set(na_reasons))[0] if na_reasons else "적용 대상 데이터셋 없음"))
    else:
        met = sum(1 for v in verdicts if v is True)
        part = sum(1 for v in verdicts if v == "partial")
        item["status"] = "met" if met == len(verdicts) else ("unmet" if met == 0 and part == 0 else "partial")
        item["evidence"].append(f"데이터셋 {len(verdicts)}건 중 충족 {met} · 부분 {part} · 미흡 {len(verdicts) - met - part}")
    return item


def _derive(ctx: _Ctx, rule: dict[str, Any], done: dict[str, dict[str, Any]], scoring: dict[str, float]) -> dict[str, Any]:
    """연결 항목의 판정을 종합한다: 점수 평균 100% → 충족, 50% 이상 → 부분, 그 미만 → 미흡."""
    item = _base(ctx, rule)
    children = [done[c] for c in rule["resolver"]["from"]]
    item["related"] = [{"id": c["id"], "name": c["name"], "status": c["status"]} for c in children]
    scored = [c for c in children if c["status"] != "na"]
    if not scored:
        item["status"] = "na"
        item["evidence"].append("해당 없음: 연결 항목이 모두 해당 없음")
        return item
    ratio = sum(scoring.get(c["status"], 0.0) for c in scored) / len(scored)
    count = {s: len([c for c in scored if c["status"] == s]) for s in ("met", "partial", "unmet", "pending")}
    if count["pending"] == len(scored):
        item["status"] = "pending"
    else:
        item["status"] = "met" if ratio >= 1 else ("partial" if ratio >= 0.5 else "unmet")
    item["evidence"].append(f"연결 항목 {len(scored)}개 중 충족 {count['met']} · 부분 {count['partial']} · 미흡 {count['unmet']} · "
                            f"확인 대기 {count['pending']} (점수 평균 {ratio:.0%})"
                            + (f" · 해당 없음 {len(children) - len(scored)}개 제외" if len(children) > len(scored) else ""))
    return item


def run(db: Session, process: Process, user: User) -> DiagnosisRun:
    rules = guideline_rules()
    ctx = _Ctx(db, process)
    started = utcnow()
    scoring = rules["scoring"]
    done: dict[str, dict[str, Any]] = {}
    for r in rules["rules"]:
        if r["resolver"]["type"] != "derived":
            done[r["id"]] = _evaluate(ctx, r)
    pending = [r for r in rules["rules"] if r["resolver"]["type"] == "derived"]
    while pending:  # 종합 항목이 종합 항목을 참조할 수 있으므로(P-03 → C-05) 준비된 것부터 푼다
        ready = [r for r in pending if all(c in done for c in r["resolver"]["from"])]
        if not ready:
            raise RuntimeError("진단 규칙의 연결 항목이 순환합니다: " + ", ".join(r["id"] for r in pending))
        for r in ready:
            done[r["id"]] = _derive(ctx, r, done, scoring)
        pending = [r for r in pending if r["id"] not in done]
    items = [done[r["id"]] for r in rules["rules"]]
    for it in items:
        it["score"] = scoring.get(it["status"], 0.0) if it["status"] != "na" else None
    scored = [i for i in items if i["status"] != "na"]
    total = sum(i["score"] for i in scored)
    areas = []
    for a in rules["areas"]:
        its = [i for i in scored if i["area"] == a["id"]]
        sc = sum(i["score"] for i in its)
        areas.append({"id": a["id"], "name": a["name"], "guideline_items": a["guideline_items"],
                      "implemented": len([i for i in items if i["area"] == a["id"]]), "items": len(its),
                      "score": sc, "pct": round(sc / len(its) * 100) if its else None,
                      "auto": len([i for i in its if i["method"] != "HUMAN-ATTEST"]),
                      "manual": len([i for i in its if i["method"] == "HUMAN-ATTEST"])})
    methods = []
    for m in rules["methods"]:
        its = [i for i in scored if i["method"] == m["id"]]
        methods.append({"id": m["id"], "name": m["name"], "items": len(its),
                        "total": len([i for i in items if i["method"] == m["id"]]),
                        "met": len([i for i in its if i["status"] == "met"]),
                        "partial": len([i for i in its if i["status"] == "partial"]),
                        "unmet": len([i for i in its if i["status"] == "unmet"]),
                        "pending": len([i for i in its if i["status"] == "pending"])})
    # 종합 항목은 연결 항목을 조치하면 함께 오르므로 조치 목록에는 넣지 않는다
    todo = [i for i in scored if i["status"] in ("unmet", "partial", "pending") and i["method"] != "AUTO-DERIVED"]
    todo.sort(key=lambda i: (i["difficulty"], -(1 - i["score"]), i["id"]))
    diff_label = {1: "낮음", 2: "중간", 3: "높음"}
    roadmap = [{"rank": n, "item_id": i["id"], "action": i["remedy"] or i["name"], "name": i["name"],
                "gain": round(1 - i["score"], 1), "difficulty": diff_label.get(i["difficulty"], "중간"),
                "basis": i["basis"], "level": i["level"], "method": i["method"], "route": i["route"]}
               for n, i in enumerate(todo, start=1)]
    summary = {
        "areas": areas, "methods": methods, "roadmap": roadmap,
        "dataset_count": len(ctx.combo), "mode": ctx.mode,
        "guideline": rules["guideline"], "guideline_total": rules["total_items_in_guideline"],
        "implemented_total": len(items), "scored_total": len(scored),
        "note": rules["note"],
        "validation_run_id": ctx.vr.id if ctx.vr else None, "validation_stale": ctx.v_stale,
        "counts": {s: len([i for i in items if i["status"] == s]) for s in ("met", "partial", "unmet", "pending", "na")},
        "potential_score": round(total + sum(r["gain"] for r in roadmap if r["difficulty"] == "낮음"), 1),
    }
    dr = DiagnosisRun(process_id=process.id, serialization_run_id=ctx.sr.id if ctx.sr else None,
                      ruleset_version=rules["version"], score=round(total, 1), max_score=float(len(scored)),
                      summary=summary, items=items, triggered_by=user.id, started_at=started, ended_at=utcnow())
    db.add(dr)
    db.flush()
    act = activity.log(db, "diagnosis_run",
                       f"가이드라인 준수 진단 실행 — {process.name} {len(ctx.combo)}건 · {dr.score:g}/{dr.max_score:g}점",
                       user=user, process_id=process.id, payload={"run_id": dr.id, "ruleset": rules["version"]})
    dr.activity_id = act.id
    db.flush()
    return dr


def latest_run(db: Session, process_id: int) -> DiagnosisRun | None:
    return db.scalar(select(DiagnosisRun).where(DiagnosisRun.process_id == process_id)
                     .order_by(DiagnosisRun.id.desc()).limit(1))


def stale_reason(dr: DiagnosisRun | None, sr_id: int | None, s_stale: str | None) -> str | None:
    if dr is None:
        return None
    if dr.serialization_run_id != sr_id:
        return "변환이 다시 실행되었습니다 — 진단을 다시 실행하세요"
    return s_stale
