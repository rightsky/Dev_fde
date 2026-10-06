"""STEP 8 가이드라인 준수 진단 — 규칙 엔진.

규칙 정의는 data/guideline_rules.json 에 있다. 판정 방식은 세 가지다.
- AUTO-GRAPH   : 데이터셋 정본 그래프에 SPARQL ASK 를 던지거나 검증·직렬화 실행 결과를 본다.
- AUTO-PROFILE : 업로드 파일의 프로파일 통계를 본다.
- HUMAN-ATTEST : 담당자가 증빙과 함께 확인한다. 확인 기록이 없으면 '확인 대기'다.

데이터셋 단위 규칙은 조합 전체로 집계한다: 전부 충족 → 충족, 일부 → 부분, 없음 → 미흡. 적용 대상이 없으면 해당 없음(만점에서 제외).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Attestation, DiagnosisRun, Process, ProcessDataset, Relation, User, utcnow
from . import activity, canonical, minting, serialize, validation
from .reference import fix_route, guideline_rules

OPEN_MEDIA = {"text/csv", "text/tab-separated-values", "application/json", "application/vnd.apache.parquet", "application/xml"}


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

    def title(self, pd: ProcessDataset) -> str:
        return (pd.meta or {}).get("title") or pd.asset.name


# 각 내장 판정기는 (판정, 근거 문장) 또는 None(해당 없음) 을 돌려준다. 판정: True 충족 / False 미흡 / "partial" 부분
def _ask(ctx: _Ctx, pd: ProcessDataset, query: str) -> bool:
    c = ctx.canon[pd.id]
    from rdflib import URIRef

    res = c.graph.query(query, initBindings={"this": URIRef(c.iri)})
    return bool(res.askAnswer)


def _b_minted(ctx: _Ctx, pd: ProcessDataset):
    rec = minting.minted_record(ctx.db, pd.asset_id)
    return (True, f"{rec.minted_id} 발급됨") if rec else (False, "민팅 대장 미등록 (초안 ID)")


def _b_iso8601(ctx: _Ctx, pd: ProcessDataset):
    cols = [c for t in (pd.asset.profile or {}).get("tables", []) for c in t["columns"] if c["type"] == "datetime"]
    if not cols:
        return None
    bad = [c for c in cols if not c.get("iso8601")]
    if not bad:
        return True, f"시각 컬럼 {len(cols)}개 전부 ISO 8601"
    fmts = sorted({f["format"] for c in bad for f in c.get("date_formats", [])})
    verdict: Any = "partial" if len(bad) < len(cols) else False
    return verdict, f"비표준 시각 컬럼 {len(bad)}/{len(cols)}개 ({', '.join(c['name'] for c in bad[:3])}) — 형식 {', '.join(fmts[:4])}"


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


def _b_shacl_pass(ctx: _Ctx, pd: ProcessDataset):
    if not ctx.vr:
        return False, "STEP 6 검증 미실행"
    r = next((x for x in ctx.vr.results if x.dataset_id == pd.id), None)
    if r is None:
        return False, "검증 결과 없음"
    stale = " (정본 변경됨 — 재검증 필요)" if ctx.v_stale else ""
    if r.passed and not ctx.v_stale:
        return True, f"Violation 0건 · Warning {r.warning_count}건"
    if r.passed:
        return "partial", f"직전 검증 통과{stale}"
    return False, f"Violation {r.violation_count}건{stale}"


def _b_missing_markers(ctx: _Ctx, pd: ProcessDataset):
    tables = (pd.asset.profile or {}).get("tables", [])
    if pd.asset.kind == "stream" or not tables:
        return None
    marks = sorted({m["marker"] for t in tables for c in t["columns"] for m in c["missing_markers"]})
    if len(marks) <= 1:
        return True, f"결측 표기 {len(marks)}종" + (f" ({marks[0]})" if marks else " (결측 없음)")
    return False, f"결측 표기 {len(marks)}종 혼재: {', '.join(marks[:6])}"


def _b_crs(ctx: _Ctx, pd: ProcessDataset):
    keys = {k.get("code") for k in (pd.classification or {}).get("K", [])}
    if "K3" not in keys:
        return None
    std = (pd.meta or {}).get("conforms_to") or []
    return (True, f"준수 표준 {', '.join(map(str, std))}") if std else (False, "좌표 연계키(K3)가 있으나 좌표계 미선언")


def _b_periodicity(ctx: _Ctx, pd: ProcessDataset):
    if pd.asset.kind == "stream":
        tr = canonical.effective_meta(pd).get("temporal_resolution")
        if not tr:
            return False, "temporalResolution 미승인"
        return (True, f"temporalResolution {tr}") if canonical.is_duration(str(tr)) else (False, f"비표준 표기 「{tr}」")
    v = (pd.meta or {}).get("accrual_periodicity")
    if not v:
        return False, "갱신 주기 미입력"
    if canonical.is_duration(str(v)) or v == "irregular":
        return True, f"갱신 주기 {v}"
    return "partial", f"비표준 표기 「{v}」"


def _b_lineage(ctx: _Ctx, pd: ProcessDataset):
    if len(ctx.combo) < 2:
        return None
    rels = ctx.db.scalars(select(Relation).where(Relation.process_id == ctx.process.id, Relation.status == "confirmed",
                                                 (Relation.source_id == pd.id) | (Relation.target_id == pd.id))).all()
    if rels:
        return True, f"확정 관계 {len(rels)}건"
    if ctx.process.lineage_waived_at:
        return "partial", "관계 미지정 — 미결 사유 기록으로 진행"
    return False, "조합 내 관계 미지정"


def _b_open_format(ctx: _Ctx, pd: ProcessDataset):
    if pd.asset.kind == "stream":
        return None
    mt = canonical.effective_meta(pd).get("media_type")
    if not mt:
        return False, "미디어타입 미승인"
    if mt in OPEN_MEDIA:
        return True, f"개방형 형식 {mt}"
    return "partial", f"{mt} — 개방형 배포본(CSV·Parquet) 병행 권장"


def _b_key_null_rate(ctx: _Ctx, pd: ProcessDataset):
    ks = [k for k in (pd.classification or {}).get("K", []) if k.get("column")]
    if pd.asset.kind == "stream" or not ks:
        return None
    cols = {(t["name"], c["name"]): c for t in (pd.asset.profile or {}).get("tables", []) for c in t["columns"]}
    bad, seen = [], 0
    for k in ks:
        c = cols.get((k.get("table"), k["column"])) or next((v for (t, n), v in cols.items() if n == k["column"]), None)
        if c:
            seen += 1
            if c["null_rate"] > 0.05:
                bad.append(f"{c['name']} {c['null_rate']:.1%}")
    if not seen:
        return None
    return (True, f"연계키 컬럼 {seen}개 결측률 5% 이하") if not bad else (False, "결측률 초과: " + ", ".join(bad[:4]))


def _b_pii(ctx: _Ctx, pd: ProcessDataset):
    cols = [c for t in (pd.asset.profile or {}).get("tables", []) for c in t["columns"] if c.get("pii")]
    if not cols:
        return True, "개인정보 의심 컬럼 미검출 (자동 증빙)"
    return "attest", "개인정보 의심 컬럼: " + ", ".join(f"{c['name']}({c['pii']['kind']})" for c in cols[:6])


_BUILTINS = {"minted": _b_minted, "iso8601": _b_iso8601, "machine_readable": _b_machine_readable,
             "shacl_pass": _b_shacl_pass, "missing_markers": _b_missing_markers, "crs_declared": _b_crs,
             "periodicity": _b_periodicity, "lineage": _b_lineage, "open_format": _b_open_format,
             "key_null_rate": _b_key_null_rate, "pii": _b_pii}


def _evaluate(ctx: _Ctx, rule: dict[str, Any]) -> dict[str, Any]:
    res = rule["resolver"]
    att = ctx.attest.get(rule["id"])
    item: dict[str, Any] = {
        "id": rule["id"], "area": rule["area"], "name": rule["name"], "method": rule["method"], "basis": rule["basis"],
        "remedy": rule.get("remedy"), "difficulty": rule.get("difficulty", 2), "datasets": [], "evidence": [],
        "route": ({**fix_route(rule["route"]), **({"focus": rule["focus"]} if rule.get("focus") else {})}
                  if rule.get("route") and fix_route(rule["route"]) else
                  ({"key": None, "step": rule["step"], "label": f"STEP {rule['step']}", "focus": None} if rule.get("step") else None)),
        "attestation": ({"status": att.status, "note": att.note, "evidence": att.evidence, "by": att.attested_label,
                         "at": att.attested_at.isoformat()} if att else None),
    }
    needs_attest = res["type"] == "attest"
    verdicts: list[Any] = []
    if not needs_attest:
        for pd in ctx.combo:
            if rule.get("applies") == "dataset" and pd.asset.kind == "stream":
                continue
            if rule.get("applies") == "stream" and pd.asset.kind != "stream":
                continue
            if res["type"] == "ask":
                ok = _ask(ctx, pd, res["query"])
                v: Any = True if ok else ("partial" if rule.get("partial") and _ask(ctx, pd, rule["partial"]["query"]) else False)
                why = "그래프 질의 충족" if v is True else ("부분 충족" if v == "partial" else "그래프에 해당 트리플 없음")
            else:
                out = _BUILTINS[res["name"]](ctx, pd)
                if out is None:
                    continue
                v, why = out
            if v == "attest":
                needs_attest = True
            verdicts.append(v)
            item["datasets"].append({"id": pd.id, "name": ctx.title(pd),
                                     "status": "met" if v is True else ("partial" if v == "partial" else ("pending" if v == "attest" else "unmet")),
                                     "detail": why})
    if needs_attest and (res["type"] == "attest" or "attest" in verdicts):
        if att:
            item["status"] = att.status
            item["evidence"].append(f"담당자 확인: {att.attested_label} · {att.attested_at:%Y-%m-%d %H:%M}"
                                    + (f" — {att.note}" if att.note else ""))
        else:
            item["status"] = "pending"
            item["evidence"].append("담당자 확인 대기 — 증빙을 첨부하고 확인하세요")
    elif not verdicts:
        item["status"] = "na"
        item["evidence"].append("적용 대상 데이터셋 없음")
    else:
        met = sum(1 for v in verdicts if v is True)
        part = sum(1 for v in verdicts if v == "partial")
        item["status"] = "met" if met == len(verdicts) else ("unmet" if met == 0 and part == 0 else "partial")
        item["evidence"].append(f"데이터셋 {len(verdicts)}건 중 충족 {met} · 부분 {part} · 미흡 {len(verdicts) - met - part}")
    return item


def run(db: Session, process: Process, user: User) -> DiagnosisRun:
    rules = guideline_rules()
    ctx = _Ctx(db, process)
    started = utcnow()
    scoring = rules["scoring"]
    items = [_evaluate(ctx, r) for r in rules["rules"]]
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
                        "met": len([i for i in its if i["status"] == "met"]),
                        "partial": len([i for i in its if i["status"] == "partial"]),
                        "unmet": len([i for i in its if i["status"] == "unmet"]),
                        "pending": len([i for i in its if i["status"] == "pending"])})
    todo = [i for i in scored if i["status"] in ("unmet", "partial", "pending")]
    todo.sort(key=lambda i: (i["difficulty"], -(1 - i["score"]), i["id"]))
    diff_label = {1: "낮음", 2: "중간", 3: "높음"}
    roadmap = [{"rank": n, "item_id": i["id"], "action": i["remedy"] or i["name"], "name": i["name"],
                "gain": round(1 - i["score"], 1), "difficulty": diff_label.get(i["difficulty"], "중간"),
                "basis": i["basis"], "route": i["route"]} for n, i in enumerate(todo, start=1)]
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
