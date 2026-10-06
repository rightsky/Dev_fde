"""STEP 6 검증: 게이트 0 (코드 검사) + SHACL (pySHACL).

판정은 데이터셋 단위다. 게이트 0 실패가 없고 sh:Violation 이 0건이면 통과. Warning·Info 는 통과에 영향을 주지 않는다.
게이트 0 ①~③ (파서·prefix·인코딩) 이 실패하면 SHACL 은 실행하지 않는다.
"""
from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from typing import Any

from pyshacl import validate as shacl_validate
from rdflib import Graph, Namespace, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Process, ProcessDataset, Relation, User, ValidationDatasetResult, ValidationRun, utcnow
from . import activity, canonical, minting
from .reference import SHAPES_DIR, fix_route

SH = Namespace("http://www.w3.org/ns/shacl#")
_SEVERITY = {str(SH.Violation): "Violation", str(SH.Warning): "Warning", str(SH.Info): "Info"}
_AUTO_PREFIX = re.compile(r"@prefix ns\d+:")


class LineageUnresolved(Exception):
    """조합이 2건 이상인데 확정된 관계도, 미결 사유도 없다."""


@lru_cache
def _shapes_text(name: str) -> str:
    s = get_settings()
    text = (SHAPES_DIR / name).read_text(encoding="utf-8")
    return text.replace("__DEF_NS__", s.def_ns).replace("__SHAPES_NS__", s.shapes_ns)


@lru_cache
def shapes_graph(mode: str) -> Graph:
    g = Graph()
    g.parse(data=_shapes_text("fde-shapes.ttl"), format="turtle")
    if mode == "publish":
        g.parse(data=_shapes_text("fde-shapes-publish.ttl"), format="turtle")
    return g


def shapes_version() -> str:
    g = shapes_graph("draft")
    v = g.value(URIRef(get_settings().shapes_ns), OWL.versionInfo)
    return str(v) if v else "unknown"


def shapes_source(mode: str) -> str:
    text = _shapes_text("fde-shapes.ttl")
    if mode == "publish":
        text += "\n\n" + _shapes_text("fde-shapes-publish.ttl")
    return text


def rule_catalog() -> list[dict[str, Any]]:
    """화면에 보여 줄 등재 규칙 목록 (셰이프 그래프에서 추출)."""
    FDE = canonical.fde()
    out: list[dict[str, Any]] = []
    for mode in ("draft", "publish"):
        g = shapes_graph(mode)
        seen = {r["iri"] for r in out}
        for s in set(g.subjects(SH.message, None)) | set(g.subjects(SH.sparql, None)):
            if not isinstance(s, URIRef) or str(s) in seen:
                continue
            msg = g.value(s, SH.message) or next((g.value(b, SH.message) for b in g.objects(s, SH.sparql)), None)
            path = g.value(s, SH.path)
            sev = g.value(s, SH.severity)
            route = g.value(s, FDE.fixRoute)
            out.append({
                "iri": str(s),
                "name": str(g.value(s, RDFS.label) or str(s).rsplit("/", 1)[-1]),
                "local": str(s).rsplit("/", 1)[-1],
                "message": str(msg) if msg else "",
                "path": g.namespace_manager.normalizeUri(path) if isinstance(path, URIRef) else None,
                "severity": _SEVERITY.get(str(sev), "Violation"),
                "route": fix_route(str(route)) if route else None,
                "profile": "publish" if mode == "publish" else "common",
                "evaluator": "SHACL-SPARQL" if (s, SH.sparql, None) in g else "SHACL Core",
            })
    out.sort(key=lambda r: (r["profile"] != "common", {"Violation": 0, "Warning": 1, "Info": 2}[r["severity"]], r["name"]))
    return out


# ------------------------------------------------------------------ 게이트 0
def gate0(canon: canonical.Canonical, pd: ProcessDataset, mode: str) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    ttl = ""
    parsed: Graph | None = None
    try:
        ttl = canon.graph.serialize(format="turtle")
        parsed = Graph().parse(data=ttl, format="turtle")
        ok = isomorphic(parsed, canon.graph)
        checks.append({"key": "parse", "name": "① 파서 통과", "ok": ok,
                       "detail": f"Turtle 재파싱 {len(parsed)}트리플" + ("" if ok else " — 정본과 불일치")})
    except Exception as exc:  # noqa: BLE001
        checks.append({"key": "parse", "name": "① 파서 통과", "ok": False, "detail": f"재파싱 실패: {exc}"[:300]})
    auto = _AUTO_PREFIX.findall(ttl)
    checks.append({"key": "prefix", "name": "② prefix 완결", "ok": bool(ttl) and not auto,
                   "detail": "미등록 네임스페이스 " + ", ".join(auto) if auto else "사용한 prefix 전부 선언됨"})
    try:
        ttl.encode("utf-8").decode("utf-8")
        bad = "�" in ttl
        checks.append({"key": "utf8", "name": "③ 인코딩 UTF-8", "ok": not bad,
                       "detail": "치환 문자(U+FFFD) 포함 — 원본 인코딩 손상" if bad else "UTF-8 왕복 정상"})
    except UnicodeError as exc:
        checks.append({"key": "utf8", "name": "③ 인코딩 UTF-8", "ok": False, "detail": str(exc)[:200]})

    if mode == "publish":
        pat = re.compile(minting.DRAFT_PATTERN)
        leftovers = sorted({str(t) for triple in canon.graph for t in triple if isinstance(t, URIRef) and pat.search(str(t))})
        checks.append({"key": "mint", "name": "④ ID 잔존 검사", "ok": not leftovers, "route": None if not leftovers else "mint",
                       "detail": "임시 ID 없음" if not leftovers else "민팅 미등록 — " + ", ".join(i.rsplit("/", 1)[-1] for i in leftovers[:4])})
    else:
        checks.append({"key": "mint", "name": "④ ID 잔존 검사", "ok": True, "skipped": True,
                       "detail": "초안 모드 — 발행 모드에서 검사"})

    want = ((pd.meta or {}).get("title") or pd.asset.name or "").strip()
    got = canon.graph.value(URIRef(canon.iri), DCTERMS.title)
    ident = canon.graph.value(URIRef(canon.iri), DCTERMS.identifier)
    same = got is not None and str(got).strip() == want and str(ident) == canon.resource_id
    checks.append({"key": "identity", "name": "⑤ 정체성 일치", "ok": same, "route": None if same else "title",
                   "detail": f"요청 「{want}」 = 산출물 제목 일치" if same else f"요청 「{want}」 ≠ 산출물 「{got or '(없음)'}」"})
    return checks


# ------------------------------------------------------------------ SHACL
def _shape_info(shapes: Graph, shape: Any) -> tuple[str, str | None, str | None]:
    FDE = canonical.fde()
    name = shapes.value(shape, RDFS.label)
    route = shapes.value(shape, FDE.fixRoute)
    focus = shapes.value(shape, FDE.fixFocus)
    if name is None and isinstance(shape, URIRef):
        name = str(shape).rsplit("/", 1)[-1]
    return str(name or "Shape"), (str(route) if route else None), (str(focus) if focus else None)


def run_shacl(data: Graph, mode: str) -> tuple[list[dict[str, Any]], str]:
    shapes = shapes_graph(mode)
    _, report, _ = shacl_validate(data, shacl_graph=shapes, inference="none", advanced=True, abort_on_first=False,
                                  meta_shacl=False, debug=False)
    nm = data.namespace_manager
    rows: list[dict[str, Any]] = []
    for res in report.subjects(RDF.type, SH.ValidationResult):
        shape = report.value(res, SH.sourceShape)
        name, route, focus_field = _shape_info(shapes, shape)
        path = report.value(res, SH.resultPath)
        value = report.value(res, SH.value)
        focus = report.value(res, SH.focusNode)
        if value == focus:  # SPARQL 제약은 값 자리에 초점 노드를 그대로 돌려준다 — 화면에 중복 표시하지 않는다
            value = None
        msgs = [str(m) for m in report.objects(res, SH.resultMessage)]
        r = fix_route(route)
        if r and focus_field:
            r = {**r, "focus": focus_field}
        rows.append({
            "source": "shacl",
            "severity": _SEVERITY.get(str(report.value(res, SH.resultSeverity)), "Violation"),
            "shape": name,
            "shape_iri": str(shape) if isinstance(shape, URIRef) else None,
            "message": msgs[0] if msgs else name,
            "focus": str(focus).rsplit("/", 1)[-1] if focus is not None else None,
            "focus_iri": str(focus) if focus is not None else None,
            "path": nm.normalizeUri(path) if isinstance(path, URIRef) else None,
            "value": (str(value)[:200] if value is not None else None),
            "route": r,
        })
    # 같은 (shape, focus, path, message) 중복 제거
    uniq: dict[tuple, dict[str, Any]] = {}
    for r in rows:
        uniq.setdefault((r["shape_iri"], r["focus_iri"], r["path"], r["message"], r["value"]), r)
    order = {"Violation": 0, "Warning": 1, "Info": 2}
    out = sorted(uniq.values(), key=lambda r: (order[r["severity"]], r["shape"], r["message"]))
    return out, report.serialize(format="turtle")


def validate_dataset(db: Session, pd: ProcessDataset, mode: str) -> dict[str, Any]:
    canon = canonical.build(db, pd, mode)
    g0 = gate0(canon, pd, mode)
    results: list[dict[str, Any]] = []
    for c in g0:
        if not c["ok"]:
            results.append({"source": "gate0", "severity": "Violation", "shape": "게이트 0", "shape_iri": None,
                            "message": f"{c['name']} — {c['detail']}", "focus": canon.resource_id, "focus_iri": canon.iri,
                            "path": None, "value": None, "route": fix_route(c.get("route"))})
    structural_ok = all(c["ok"] for c in g0 if c["key"] in ("parse", "prefix", "utf8"))
    report_ttl = None
    if structural_ok:
        shacl_rows, report_ttl = run_shacl(canon.graph, mode)
        # 게이트 0 ④ 와 MintedIdShape 는 같은 원인이므로 SHACL 쪽 행은 본체 1건으로 줄인다
        results.extend(shacl_rows)
    violations = [r for r in results if r["severity"] == "Violation"]
    warnings = [r for r in results if r["severity"] == "Warning"]
    infos = [r for r in results if r["severity"] == "Info"]
    return {
        "dataset_id": pd.id,
        "dataset_name": (pd.meta or {}).get("title") or pd.asset.name,
        "resource_id": canon.resource_id,
        "checksum": canon.checksum,
        "gate0": g0,
        "conforms": structural_ok and not any(r["source"] == "shacl" for r in violations),
        "passed": not violations,
        "violation_count": len(violations),
        "warning_count": len(warnings),
        "info_count": len(infos),
        "results": results,
        "report_ttl": report_ttl,
        "triple_count": len(canon.graph),
        "readiness": canon.readiness,
    }


# ------------------------------------------------------------------ 실행 단위
def combo_signature(process: Process, mode: str) -> str:
    ids = ",".join(str(d.id) for d in sorted(process.combo, key=lambda d: d.id))
    return hashlib.sha256(f"{mode}|{ids}".encode()).hexdigest()


def lineage_resolved(db: Session, process: Process) -> bool:
    if len(process.combo) < 2 or process.lineage_waived_at:
        return True
    ids = {d.id for d in process.combo}
    rels = db.scalars(select(Relation).where(Relation.process_id == process.id, Relation.status == "confirmed"))
    return any(r.source_id in ids and r.target_id in ids for r in rels)


def run(db: Session, process: Process, user: User, mode: str | None = None) -> ValidationRun:
    mode = mode or ("publish" if process.pub_mode else "draft")
    if not lineage_resolved(db, process):
        raise LineageUnresolved
    prev = latest_run(db, process.id)
    started = utcnow()
    vr = ValidationRun(process_id=process.id, mode=mode, shapes_version=shapes_version(), status="done",
                       combo_signature=combo_signature(process, mode), triggered_by=user.id, started_at=started)
    db.add(vr)
    db.flush()
    for pd in process.combo:
        r = validate_dataset(db, pd, mode)
        r.pop("readiness", None)
        vr.results.append(ValidationDatasetResult(**r))
    vr.pass_count = sum(1 for r in vr.results if r.passed)
    vr.fail_count = len(vr.results) - vr.pass_count
    vr.warning_count = sum(r.warning_count for r in vr.results)
    vr.ended_at = utcnow()
    text = f"STEP 6 검증 실행 — {process.name} · 통과 {vr.pass_count}/{len(vr.results)}"
    if prev:
        prev_fail = {(d.dataset_id, x["shape"]) for d in prev.results for x in d.results if x["severity"] == "Violation"}
        now_fail = {(d.dataset_id, x["shape"]) for d in vr.results for x in d.results if x["severity"] == "Violation"}
        fixed = sorted({s for _, s in prev_fail - now_fail})
        if fixed:
            text = f"재검증 — 직전 위반 {', '.join(fixed[:3])} 보강 · 통과 {vr.pass_count}/{len(vr.results)}"
    act = activity.log(db, "validation_run", text + (" (발행 모드)" if mode == "publish" else ""), user=user,
                       process_id=process.id, payload={"run_id": vr.id, "mode": mode, "shapes": vr.shapes_version})
    vr.activity_id = act.id
    db.flush()
    return vr


def latest_run(db: Session, process_id: int) -> ValidationRun | None:
    return db.scalar(select(ValidationRun).where(ValidationRun.process_id == process_id)
                     .order_by(ValidationRun.id.desc()).limit(1))


def stale_reason(db: Session, process: Process, vr: ValidationRun | None) -> str | None:
    """최신 검증 결과가 현재 정본과 어긋나면 사유를 돌려준다."""
    if vr is None:
        return None
    mode = "publish" if process.pub_mode else "draft"
    if vr.mode != mode:
        return "발행 모드 전환 — 해당 모드로 다시 검증해야 합니다"
    if vr.combo_signature != combo_signature(process, mode):
        return "조합 변경 — 검증 결과가 현재 조합과 다릅니다"
    by_id = {r.dataset_id: r for r in vr.results}
    for pd in process.combo:
        r = by_id.get(pd.id)
        if r is None or canonical.build(db, pd, mode).checksum != r.checksum:
            return "재검증 필요 — 정본이 변경되었습니다. STEP 6 검증을 다시 실행하세요"
    return None
