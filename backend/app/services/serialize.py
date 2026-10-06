"""STEP 7 직렬화·포맷 변환 + 파생 자가검증.

검증을 통과한 데이터셋만 대상이다. 정본 그래프 1개에서 4개 포맷을 만들고, 만든 직후 실제 파서로 다시 읽어
정본과 같은지 확인한다. 자가검증에 실패한 데이터셋의 산출물은 저장하지 않는다.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from typing import Any

import jsonschema
from rdflib import Graph
from rdflib.compare import isomorphic
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Artifact, Process, ProcessDataset, SerializationRun, User, ValidationRun, utcnow
from . import activity, canonical, validation

FORMATS: list[dict[str, str]] = [
    {"key": "ttl", "label": "Turtle (RDF 정본)", "tag": "TTL", "suffix": ".ttl", "media_type": "text/turtle",
     "use": "카탈로그 트리플스토어 정본 저장 · SHACL 검증 대상"},
    {"key": "jsonld", "label": "JSON-LD (RDF 직렬화)", "tag": "JSON-LD", "suffix": ".jsonld", "media_type": "application/ld+json",
     "use": "시스템 간 API 계층 · 카탈로그 API 전송"},
    {"key": "txt", "label": "자연어 문장화", "tag": "문장화", "suffix": "_문장화.txt", "media_type": "text/plain",
     "use": "sLLM RAG 입력 · 벡터DB 적재용 코퍼스"},
    {"key": "schema", "label": "순수 JSON + 스키마", "tag": "스키마", "suffix": "_schema.json", "media_type": "application/json",
     "use": "제약 디코딩용 스키마 · 스키마 레지스트리"},
]
FORMAT_KEYS = [f["key"] for f in FORMATS]
_AUTO_PREFIX = re.compile(r"@prefix ns\d+:")


def file_base(rid: str, name: str) -> str:
    base = re.sub(r"[^가-힣a-zA-Z0-9]+", "_", name or "dataset").strip("_")[:40] or "dataset"
    return f"{rid}_{base}"


def jsonld_context(g: Graph) -> dict[str, str]:
    used = set()
    for s, p, o in g:
        for t in (s, p, o):
            try:
                prefix, _, _ = g.namespace_manager.compute_qname(str(t), generate=False)
                used.add(prefix)
            except (KeyError, ValueError, TypeError):
                continue
    return {prefix: str(ns) for prefix, ns in g.namespaces() if prefix in used}


def render_ttl(canon: canonical.Canonical, mode: str) -> str:
    head = [
        f"# FDE Data Studio 정본 — {canon.resource_id}",
        f"# fde:setChecksum \"{canon.checksum}\"",
        f"# mode: {mode} · readiness: {canon.readiness['level']}",
        "",
    ]
    return "\n".join(head) + canon.graph.serialize(format="turtle")


def render_jsonld(canon: canonical.Canonical) -> str:
    raw = canon.graph.serialize(format="json-ld", context=jsonld_context(canon.graph), auto_compact=True, indent=2)
    return json.dumps(json.loads(raw), ensure_ascii=False, indent=2) + "\n"


def _josa(word: str, with_final: str, without_final: str) -> str:
    """받침 유무에 따라 조사를 고른다 (한글이 아니면 받침 없는 쪽)."""
    ch = (word or " ").rstrip(" 」)\"'")[-1:] or " "
    if "가" <= ch <= "힣":
        return with_final if (ord(ch) - 0xAC00) % 28 else without_final
    if ch.isdigit():
        return with_final if ch in "013678" else without_final
    return without_final


def render_txt(canon: canonical.Canonical) -> str:
    """정본 레코드를 문장으로 푼다. 결측 필드는 문장을 만들지 않는다 ('미상'·'미선언' 금지)."""
    r = canon.record
    title = r.get("title") or canon.resource_id
    form = (r.get("distribution") or {}).get("format") or ("실시간 스트림" if canon.is_stream else "데이터셋")
    s: list[str] = []
    quoted = f"「{title}」"
    if r.get("publisher"):
        s.append(f"{quoted}{_josa(title, '은', '는')} {r['publisher']['label']} 소관의 {form}이다.")
    else:
        s.append(f"{quoted} {form}이다.")
    if r.get("description"):
        s.append(str(r["description"]).rstrip(" .。") + ".")
    if r.get("roleNote"):
        s.append(str(r["roleNote"]).rstrip(" .。") + ".")
    if r.get("theme"):
        s.append(f"주제영역은 {', '.join(r['theme'])}이며" + (f" 데이터유형은 {', '.join(r['dataType'])}이다." if r.get("dataType") else " 분류되어 있다."))
    elif r.get("dataType"):
        s.append(f"데이터유형은 {', '.join(r['dataType'])}이다.")
    if r.get("granularity"):
        s.append(f"해상도는 {', '.join(r['granularity'])} 단위이다.")
    if r.get("temporalResolution"):
        t = f"시간 해상도는 {r['temporalResolution']}"
        if r.get("eventTimeColumn"):
            t += f", event-time 컬럼은 {r['eventTimeColumn']}"
        s.append(t + "이다.")
    if r.get("temporal"):
        tp = r["temporal"]
        s.append(f"수록 기간은 {tp.get('start', '')} ~ {tp.get('end', '')}이다.".replace("  ", " "))
    if r.get("accrualPeriodicity"):
        s.append(f"갱신 주기는 {r['accrualPeriodicity']}이다.")
    if r.get("joinKeys"):
        parts = [f"{k['key']} {k['label']}" + (f"({k['column']})" if k.get("column") else "") for k in r["joinKeys"]]
        s.append(f"연계키는 {', '.join(parts)}이다.")
    for rel in r.get("relations", []):
        if rel["type"] == "JOINED_ON" and rel.get("direction") == "out":
            cols = f" ({rel.get('sourceColumn')} = {rel.get('targetColumn')})" if rel.get("sourceColumn") and rel.get("targetColumn") else ""
            key = f" {rel['key']} 기준으로" if rel.get("key") else ""
            s.append(f"「{rel['target']}」{_josa(rel['target'], '과', '와')}{key} 결합된다{cols}.")
        elif rel["type"] == "GROUPED_WITH":
            s.append(f"「{rel['target']}」{_josa(rel['target'], '과', '와')} 연관 데이터셋으로 묶인다.")
        elif rel["type"] == "WAS_DERIVED_FROM" and rel.get("direction") == "out":
            s.append(f"「{rel['target']}」에서 파생되었다.")
    if r.get("license"):
        s.append(f"이용허락은 {r['license']}이다.")
    elif r.get("accessRights"):
        s.append(f"이용 조건은 {r['accessRights']}이다.")
    if r.get("n2sfGrade"):
        s.append(f"보안등급(N²SF)은 {r['n2sfGrade']}이다.")
    if r.get("aiPurpose"):
        s.append(f"AI 활용 목적은 {', '.join(r['aiPurpose'])}이다.")
    if r.get("dataBiases"):
        s.append("알려진 편향: " + str(r["dataBiases"]).rstrip(" .") + ".")
    if r.get("knownLimitations"):
        s.append("알려진 한계: " + str(r["knownLimitations"]).rstrip(" .") + ".")
    if r.get("isPartOf"):
        s.append(f"조합 「{r['isPartOf']['title']}」의 구성원이다.")
    tail = (f"이 서술은 ai-ready 등급 정본에서 생성되었다 (식별자: {canon.resource_id}, 세트 체크섬: {canon.checksum[:16]})."
            if canon.readiness["level"] == "ai-ready"
            else f"※ 필수 필드 결측 상태의 초안 서술 — 학습 코퍼스 수집 전 보강 권장 (식별자: {canon.resource_id}, 세트 체크섬: {canon.checksum[:16]}).")
    return " ".join(s) + "\n" + tail + "\n"


def _schema_of(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, list):
        return {"type": "array", "items": _schema_of(value[0]) if value else {}, "minItems": 0}
    if isinstance(value, dict):
        return {"type": "object", "properties": {k: _schema_of(v) for k, v in value.items()},
                "required": [k for k in value if k == "@id"]}
    return {"type": "string"}


def render_schema(canon: canonical.Canonical) -> str:
    """정본 레코드(순수 JSON)와 그 구조를 기술하는 JSON Schema 를 한 파일에 담는다.

    properties 는 정본에 실제 존재하는 필드만, required 는 준비도 필수 필드 중 존재하는 것만 낸다.
    """
    rec = canon.record
    props = {k: _schema_of(v) for k, v in rec.items()}
    props["@id"] = {"type": "string", "format": "iri"}
    props["identifier"] = {"type": "string", "pattern": "^(DST|SVC)-.+$"}
    if isinstance(rec.get("publisher"), dict):
        props["publisher"]["properties"]["@id"] = {"type": "string", "format": "iri"}
    required = ["@id", "identifier"] + [k for k in canon.readiness["required"] if k in rec]
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{get_settings().base_iri.rstrip('/')}/schema/{canon.resource_id}.json",
        "$comment": f"generated from canonical {canon.resource_id} · readiness: {canon.readiness['level']} · setChecksum: {canon.checksum}",
        "title": rec.get("title") or canon.resource_id,
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
        "examples": [rec],
    }
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"


def render_all(canon: canonical.Canonical, mode: str) -> dict[str, str]:
    return {"ttl": render_ttl(canon, mode), "jsonld": render_jsonld(canon), "txt": render_txt(canon),
            "schema": render_schema(canon)}


def self_verify(canon: canonical.Canonical, contents: dict[str, str], validated_checksum: str | None) -> dict[str, Any]:
    """산출물을 실제 파서로 다시 읽어 정본과 대조한다."""
    checks: list[dict[str, Any]] = []
    g_ttl: Graph | None = None
    g_jsonld: Graph | None = None
    try:
        g_ttl = Graph().parse(data=contents["ttl"], format="turtle")
        checks.append({"name": "① TTL 재파싱", "ok": True, "detail": f"{len(g_ttl)}트리플"})
    except Exception as exc:  # noqa: BLE001
        checks.append({"name": "① TTL 재파싱", "ok": False, "detail": str(exc)[:200]})
    auto = _AUTO_PREFIX.findall(contents["ttl"])
    checks.append({"name": "② prefix 완결", "ok": not auto, "detail": "전부 선언됨" if not auto else "자동 생성 prefix: " + ", ".join(auto)})
    bad = any("�" in c for c in contents.values())
    try:
        for c in contents.values():
            c.encode("utf-8").decode("utf-8")
        checks.append({"name": "③ UTF-8 정상", "ok": not bad, "detail": "왕복 정상" if not bad else "치환 문자(U+FFFD) 포함"})
    except UnicodeError as exc:
        checks.append({"name": "③ UTF-8 정상", "ok": False, "detail": str(exc)[:200]})
    try:
        g_jsonld = Graph().parse(data=contents["jsonld"], format="json-ld")
        same = g_ttl is not None and isomorphic(g_ttl, g_jsonld) and isomorphic(g_ttl, canon.graph)
        checks.append({"name": "④ TTL↔JSON-LD 그래프 동형", "ok": same,
                       "detail": f"TTL {len(g_ttl) if g_ttl is not None else 0} · JSON-LD {len(g_jsonld)} · 정본 {len(canon.graph)}트리플"})
    except Exception as exc:  # noqa: BLE001
        checks.append({"name": "④ TTL↔JSON-LD 그래프 동형", "ok": False, "detail": str(exc)[:200]})
    out_cs = canonical.graph_checksum(g_ttl) if g_ttl is not None else ""
    cs_ok = bool(out_cs) and out_cs == canon.checksum and (validated_checksum is None or out_cs == validated_checksum)
    checks.append({"name": "⑤ 검증 대상 = 산출 대상", "ok": cs_ok,
                   "detail": f"체크섬 {out_cs[:16]} 일치" if cs_ok else "검증 시점 정본과 산출물 체크섬 불일치"})
    try:
        schema = json.loads(contents["schema"])
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(canon.record, schema)
        checks.append({"name": "⑥ JSON 인스턴스 스키마 적합", "ok": True, "detail": f"필수 {len(schema['required'])}필드"})
    except Exception as exc:  # noqa: BLE001
        checks.append({"name": "⑥ JSON 인스턴스 스키마 적합", "ok": False, "detail": str(exc)[:200]})
    return {"passed": all(c["ok"] for c in checks), "checks": checks}


def run(db: Session, process: Process, user: User, vr: ValidationRun, formats: list[str] | None = None) -> SerializationRun:
    formats = [f for f in FORMAT_KEYS if not formats or f in formats]
    if "ttl" not in formats:
        formats.insert(0, "ttl")  # Turtle 정본은 항상 생성
    sr = SerializationRun(process_id=process.id, validation_run_id=vr.id, mode=vr.mode, formats=formats,
                          triggered_by=user.id, started_at=utcnow())
    db.add(sr)
    db.flush()
    by_id = {d.id: d for d in process.combo}
    summary: list[dict[str, Any]] = []
    for res in vr.results:
        pd: ProcessDataset | None = by_id.get(res.dataset_id)
        if pd is None or not res.passed:
            continue
        canon = canonical.build(db, pd, vr.mode)
        try:
            contents = render_all(canon, vr.mode)
            sv = self_verify(canon, contents, res.checksum)
        except Exception as exc:  # noqa: BLE001 - 렌더러 결함은 산출물 폐기로 처리
            contents, sv = {}, {"passed": False, "checks": [{"name": "렌더러 예외", "ok": False, "detail": str(exc)[:300]}]}
        name = (pd.meta or {}).get("title") or pd.asset.name
        summary.append({"dataset_id": pd.id, "name": name, "resource_id": canon.resource_id, "checksum": canon.checksum,
                        "readiness": canon.readiness["level"], "triple_count": len(canon.graph), **sv})
        if not sv["passed"]:
            continue
        base = file_base(canon.resource_id, name)
        for f in FORMATS:
            if f["key"] not in formats:
                continue
            body = contents[f["key"]]
            raw = body.encode("utf-8")
            sr.artifacts.append(Artifact(dataset_id=pd.id, dataset_name=name, fmt=f["key"], filename=base + f["suffix"],
                                         media_type=f["media_type"], content=body, size=len(raw),
                                         sha256=hashlib.sha256(raw).hexdigest(), set_checksum=canon.checksum))
    sr.self_verify = summary
    sr.ok_count = sum(1 for s in summary if s["passed"])
    sr.fail_count = len(summary) - sr.ok_count
    sr.ended_at = utcnow()
    act = activity.log(
        db, "serialization_run",
        f"직렬화·포맷 변환 실행 — 통과 {len(summary)}건 × {len(formats)}포맷 · 파생 자가검증 {sr.ok_count}/{len(summary)}",
        user=user, process_id=process.id, payload={"run_id": sr.id, "validation_run_id": vr.id, "formats": formats})
    sr.activity_id = act.id
    db.flush()
    return sr


def latest_run(db: Session, process_id: int) -> SerializationRun | None:
    return db.scalar(select(SerializationRun).where(SerializationRun.process_id == process_id)
                     .order_by(SerializationRun.id.desc()).limit(1))


def stale_reason(db: Session, process: Process, sr: SerializationRun | None, vr: ValidationRun | None,
                 v_stale: str | None) -> str | None:
    if sr is None:
        return None
    if vr is None or sr.validation_run_id != vr.id:
        return "검증이 다시 실행되었습니다 — 변환을 다시 실행하세요"
    return v_stale


def build_zip(sr: SerializationRun, process: Process) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        manifest = {
            "process": {"id": process.id, "name": process.name, "collection": process.combo_title},
            "serialization_run": sr.id,
            "validation_run": sr.validation_run_id,
            "mode": sr.mode,
            "generated_at": (sr.ended_at or sr.started_at).isoformat(),
            "base_iri": get_settings().base_iri,
            "self_verify": sr.self_verify,
            "files": [{"name": a.filename, "dataset": a.dataset_name, "format": a.fmt, "media_type": a.media_type,
                       "size": a.size, "sha256": a.sha256, "set_checksum": a.set_checksum} for a in sr.artifacts],
        }
        for a in sr.artifacts:
            z.writestr(a.filename, a.content)
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return buf.getvalue()


def shapes_stale(vr: ValidationRun) -> bool:
    return vr.shapes_version != validation.shapes_version()
