"""STEP 7 문서 산출물: 데이터 카드(부록 4) · 데이터 사전 · Croissant.

세 산출물 모두 정본(canonical)과 원천 프로파일에서 만든다. 사람이 적어야 하는 내용(컬럼 정의, 카드 전용 항목)도
STEP 3 에서 정본에 들어간 값만 쓴다. 그래서 정본 체크섬이 같으면 산출물도 같다 (생성 시각 같은 바뀌는 값은 넣지 않는다).
"""
from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

from ..models import ProcessDataset, ValidationRun
from . import canonical

CR = Namespace("http://mlcommons.org/croissant/")
SDO = Namespace("https://schema.org/")

# Croissant 1.0 의 표준 JSON-LD 컨텍스트 (명세 부록 1) + RAI
CROISSANT_CONTEXT: dict[str, Any] = {
    "@language": "ko",
    "@vocab": "https://schema.org/",
    "citeAs": "cr:citeAs",
    "column": "cr:column",
    "conformsTo": "dct:conformsTo",
    "cr": "http://mlcommons.org/croissant/",
    "rai": "http://mlcommons.org/croissant/RAI/",
    "data": {"@id": "cr:data", "@type": "@json"},
    "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
    "dct": "http://purl.org/dc/terms/",
    "examples": {"@id": "cr:examples", "@type": "@json"},
    "extract": "cr:extract",
    "field": "cr:field",
    "fileProperty": "cr:fileProperty",
    "fileObject": "cr:fileObject",
    "fileSet": "cr:fileSet",
    "format": "cr:format",
    "includes": "cr:includes",
    "isLiveDataset": "cr:isLiveDataset",
    "jsonPath": "cr:jsonPath",
    "key": "cr:key",
    "md5": "cr:md5",
    "parentField": "cr:parentField",
    "path": "cr:path",
    "recordSet": "cr:recordSet",
    "references": "cr:references",
    "regex": "cr:regex",
    "repeated": "cr:repeated",
    "replace": "cr:replace",
    "sc": "https://schema.org/",
    "separator": "cr:separator",
    "source": "cr:source",
    "subField": "cr:subField",
    "transform": "cr:transform",
}
_CR_TYPE = {"integer": "sc:Integer", "number": "sc:Float", "datetime": "sc:Date", "boolean": "sc:Boolean"}
_TYPE_LABEL = {"integer": "정수", "number": "실수", "datetime": "날짜·시각", "boolean": "참/거짓", "string": "문자열"}
MASK = "(개인정보 의심 · 표시 안 함)"


# ------------------------------------------------------------------ 데이터 사전
def dictionary_rows(pd: ProcessDataset) -> list[dict[str, Any]]:
    """컬럼마다 프로파일 통계와 사람이 적은 정의·단위·코드값을 한 행으로 묶는다."""
    dic = canonical.dictionary(pd)
    keys = {(k.get("table"), k.get("column")): k.get("code") for k in (pd.classification or {}).get("K", []) if k.get("column")}
    keys_any = {k.get("column"): k.get("code") for k in (pd.classification or {}).get("K", []) if k.get("column")}
    stream = pd.asset.kind == "stream"
    rows = []
    for t in (pd.asset.profile or {}).get("tables", []):
        for c in t.get("columns", []):
            ent = dic.get(t["name"], {}).get(c["name"], {})
            rows.append({
                "table": t["name"], "column": c["name"], "type": c["type"], "type_label": _TYPE_LABEL.get(c["type"], c["type"]),
                "description": ent.get("description", ""), "unit": ent.get("unit", ""), "codes": ent.get("codes", ""),
                "required": None if stream or not t.get("rows") else c["null_rate"] == 0,
                "null_rate": None if stream else c["null_rate"], "distinct": None if stream else c.get("distinct"),
                "missing_markers": [m["marker"] for m in c.get("missing_markers", [])],
                "samples": [] if c.get("pii") else [str(v) for v in (c.get("samples") or [])[:3]],
                "pii": (c.get("pii") or {}).get("kind"),
                "key": keys.get((t["name"], c["name"])) or keys_any.get(c["name"]),
            })
    return rows


def dictionary_coverage(pd: ProcessDataset) -> tuple[int, int]:
    rows = dictionary_rows(pd)
    return sum(1 for r in rows if r["description"]), len(rows)


def render_dictionary(canon: canonical.Canonical, pd: ProcessDataset) -> str:
    """데이터 사전 CSV. 엑셀에서 한글이 깨지지 않게 BOM 을 붙인다."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["표", "컬럼", "자료형", "정의", "단위", "코드값 의미", "필수(결측 없음)", "결측률(%)", "고유값 수",
                "결측 표기", "예시값", "연계키", "개인정보 의심"])
    for r in dictionary_rows(pd):
        w.writerow([r["table"], r["column"], r["type_label"], r["description"], r["unit"], r["codes"],
                    "" if r["required"] is None else ("예" if r["required"] else "아니오"),
                    "" if r["null_rate"] is None else f"{r['null_rate'] * 100:.1f}",
                    "" if r["distinct"] is None else r["distinct"],
                    " / ".join(r["missing_markers"]), MASK if r["pii"] else " / ".join(r["samples"]),
                    r["key"] or "", r["pii"] or ""])
    return "\ufeff" + buf.getvalue()


# ------------------------------------------------------------------ 데이터 카드 (부록 4)
def _join(*parts: Any, sep: str = " · ") -> str:
    return sep.join(str(p) for p in parts if p not in (None, "", [], {}))


def _sample_rows(pd: ProcessDataset) -> list[dict[str, str]]:
    tables = (pd.asset.profile or {}).get("tables", [])
    if not tables or not tables[0].get("sample_rows"):
        return []
    t = tables[0]
    cols = t["columns"]
    out = []
    for row in t["sample_rows"][:3]:
        out.append({c["name"]: (MASK if c.get("pii") else (row[i] if i < len(row) else "")) for i, c in enumerate(cols)})
    return out


def card_items(canon: canonical.Canonical, pd: ProcessDataset, vr: ValidationRun | None = None,
               files: list[str] | None = None) -> list[dict[str, Any]]:
    """부록 4 의 6개 분류 · 38항목을 채운다. source: 자동 | 입력 | 작성 필요 | 해당 시."""
    r = canon.record
    stream = pd.asset.kind == "stream"
    prof = pd.asset.profile or {}
    cols = [c for t in prof.get("tables", []) for c in t.get("columns", [])]
    contact = r.get("contactPoint") or {}
    dist = r.get("distribution") or {}
    described, total_cols = dictionary_coverage(pd)
    pii = [c["name"] for c in cols if c.get("pii")]
    rows_n = sum(t.get("rows", 0) for t in prof.get("tables", []))
    sections: list[dict[str, Any]] = []

    def section(name: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        sections.append({"section": name, "items": items})
        return items

    def add(items: list[dict[str, Any]], item: str, content: str, source: str, optional: bool = False) -> None:
        if not content:
            source = "해당 시" if optional else "작성 필요"
        items.append({"item": item, "content": content, "source": source, "optional": optional,
                      "filled": bool(content)})

    s = section("데이터셋 개요")
    add(s, "데이터셋명/ID", _join(r.get("title"), canon.resource_id, sep=" / "), "자동")
    add(s, "발행기관/담당부서/연락처", _join((r.get("publisher") or {}).get("label"), r.get("creator"), contact.get("name"),
                                         contact.get("email"), contact.get("phone")), "입력")
    add(s, "데이터셋 요약", r.get("description", ""), "입력")
    add(s, "지원 태스크(활용 목적)", _join(*(r.get("aiPurpose") or [])), "입력", optional=True)
    add(s, "언어 정보", r.get("language", ""), "입력")
    tp = r.get("temporal") or {}
    add(s, "대상 범위", _join(f"기간 {tp.get('start', '')} ~ {tp.get('end', '')}" if tp else "",
                            f"공간 {r['spatial']}" if r.get("spatial") else "",
                            f"대상 조합 「{r['isPartOf']['title']}」" if r.get("isPartOf") else "") if (tp or r.get("spatial")) else "", "입력")
    add(s, "갱신 정책", _join(f"갱신주기 {r['accrualPeriodicity']}" if r.get("accrualPeriodicity") else "",
                            f"시간 해상도 {r['temporalResolution']}" if r.get("temporalResolution") else "",
                            f"지연 허용 {r['watermarkDelay']}" if r.get("watermarkDelay") else ""), "입력")
    api = r.get("endpointURL") or (dist.get("accessService") or {}).get("endpointURL")
    add(s, "제공 형태", _join(f"파일 다운로드 ({dist.get('format') or dist.get('mediaType')}{', ' + dist['accessURL'] if dist.get('accessURL') else ''})"
                            if dist else "", f"API ({api})" if api else "", "실시간 스트림" if stream else ""), "자동")

    s = section("데이터셋 구조")
    samples = _sample_rows(pd)
    add(s, "데이터 인스턴스(샘플)", "\n".join(json.dumps(x, ensure_ascii=False) for x in samples), "자동", optional=stream)
    if samples:
        s[-1]["note"] = "개인정보 의심 컬럼은 자동 탐지 기준으로 가렸습니다. 주소·이름처럼 탐지되지 않은 민감 정보가 없는지 배포 전에 확인하세요"
    add(s, "데이터 필드 정의", f"컬럼 {total_cols}개 전부 정의됨 (데이터 사전 파일 참조)" if total_cols and described == total_cols else "",
        "입력")
    if total_cols and described < total_cols:
        s[-1]["note"] = f"정의 작성 {described}/{total_cols}개 — STEP 3 데이터 사전 탭에서 채웁니다"
    uniq = [c["name"] for c in cols if c.get("unique") and not stream]
    keys_txt = ", ".join(f"{k['key']} {k['label']}({k.get('column', '-')})" for k in r.get("joinKeys", []))
    add(s, "키/식별자 규칙", _join(f"연계키 {keys_txt}" if keys_txt else "",
                                f"중복 없는 컬럼 {', '.join(uniq[:5])}" if uniq else ""), "자동")
    marks = sorted({m["marker"] for c in cols for m in c.get("missing_markers", [])})
    add(s, "결측·특수값 규칙", _join(f"결측 표기 {', '.join(marks)}" if marks else ("결측 없음" if cols and not stream else ""),
                                  r.get("missingData", "")), "자동")
    add(s, "분할 정보(Splits)", r.get("cardSplits", ""), "입력", optional=True)
    enc = next((w for w in prof.get("warnings", []) if "인코딩" in w), None)
    add(s, "포맷·인코딩·표준", _join(dist.get("format") or dist.get("mediaType") or ("스트림 메시지" if stream else ""),
                                   enc or ("UTF-8" if not stream else ""),
                                   f"준수 표준 {', '.join(map(str, r.get('conformsTo', [])))}" if r.get("conformsTo") else ""), "자동")
    add(s, "기계 이해 스키마 제공", ", ".join(f for f in (files or []) if f.endswith((".json", ".jsonld", ".ttl"))), "자동")

    s = section("데이터셋 생성")
    add(s, "구축 배경", r.get("cardBackground", ""), "입력")
    add(s, "데이터 소스(출처)", _join(r.get("provenance", ""),
                                  f"원천 파일 {pd.asset.filename}" if pd.asset.filename and r.get("provenance") else ""), "입력")
    add(s, "정제·전처리 과정", r.get("cardPreprocessing", ""), "입력")
    add(s, "어노테이션 과정(해당 시)", r.get("cardAnnotation", ""), "입력", optional=True)
    add(s, "비식별·보호 조치", r.get("cardProtection", ""), "입력")
    if pii:
        s[-1]["note"] = f"자동 탐지된 개인정보 의심 컬럼: {', '.join(pii)}" + ("" if r.get("cardProtection") else " — 적용한 보호조치를 적어야 합니다")
    elif not r.get("cardProtection") and cols:
        s[-1].update(content="개인정보 의심 컬럼 없음 (컬럼 이름·값 패턴 자동 탐지 결과)", source="자동", filled=True)
    vtext = (f"STEP 6 SHACL 검증 통과 (셰이프 {vr.shapes_version}, {vr.mode} 모드)" if vr else "")
    add(s, "품질관리 절차", _join(r.get("qualityAnnotation", ""), vtext), "자동")

    s = section("사용 시 고려사항")
    add(s, "권장 사용 범위", _join(r.get("cardUseCases", ""), f"AI 활용 목적 {', '.join(r['aiPurpose'])}" if r.get("aiPurpose") else ""), "입력")
    add(s, "비권장/금지 사용", r.get("cardProhibitedUses", ""), "입력")
    add(s, "사회적 영향", r.get("cardSocialImpact", ""), "입력")
    add(s, "편향성 및 한계", _join(f"편향: {r['dataBiases']}" if r.get("dataBiases") else "",
                                 f"한계: {r['knownLimitations']}" if r.get("knownLimitations") else "", sep="\n"), "입력")
    add(s, "기술적 제약", _join(f"행 {rows_n:,}건" if rows_n else "", f"해상도 {', '.join(r['granularity'])}" if r.get("granularity") else "",
                              f"시간 해상도 {r['temporalResolution']}" if r.get("temporalResolution") else "",
                              f"버전 {r['version']}" if r.get("version") else ""), "자동")
    add(s, "리스크 완화 권고", r.get("cardRiskMitigation", ""), "입력")

    s = section("추가 정보 및 라이선스")
    add(s, "라이선스", _join(r.get("license") or r.get("accessRights") or "", r.get("rights", "")), "입력")
    who = r.get("creator") or (r.get("publisher") or {}).get("label")
    add(s, "인용", _join(who, f"「{r.get('title')}」", f"버전 {r['version']}" if r.get("version") else "",
                        f"발행일 {r['issued']}" if r.get("issued") else "", canon.iri, sep=", ") + ", 접속일 (인용 시 기입)" if who else "", "자동")
    add(s, "작성자/관리자 정보", _join(r.get("creator"), contact.get("name"), contact.get("email"), contact.get("phone")), "입력")
    add(s, "버전/변경 이력", _join(f"버전 {r['version']}" if r.get("version") else "", f"수정일 {r['modified']}" if r.get("modified") else "",
                                 r.get("versionNotes", "")), "입력")
    add(s, "관련 문서", _join(r.get("landingPage", ""), *(r.get("references") or []), *(files or [])), "자동")

    s = section("기술적 사양")
    add(s, "재현성", r.get("cardReproducibility", ""), "입력")
    add(s, "환경 설정", r.get("cardEnvironment", ""), "입력")
    add(s, "매개변수/규칙", r.get("cardParameters", ""), "입력")
    add(s, "코드 및 라이브러리 버전", r.get("cardCode", ""), "입력")
    add(s, "무결성 검증 정보", _join(f"SHA-256 {pd.asset.sha256}" if pd.asset.sha256 else "",
                                  f"파일 크기 {pd.asset.size:,} B" if pd.asset.size else "", f"레코드 {rows_n:,}건" if rows_n else ""),
        "자동", optional=stream)
    add(s, "접근 사양(해당 시)", f"API 엔드포인트 {api}" if api else "", "입력", optional=True)
    return sections


def card_coverage(sections: list[dict[str, Any]]) -> tuple[int, int]:
    req = [i for s in sections for i in s["items"] if not i["optional"]]
    return sum(1 for i in req if i["filled"]), len(req)


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


def render_card(canon: canonical.Canonical, pd: ProcessDataset, vr: ValidationRun | None, files: list[str]) -> str:
    sections = card_items(canon, pd, vr, files)
    filled, total = card_coverage(sections)
    title = canon.record.get("title") or canon.resource_id
    lines = [f"# 데이터 카드: {title}", "",
             f"> 「공공데이터의 인공지능 친화적 관리 가이드라인 v1.1」 부록 4 양식 · 식별자 {canon.resource_id} · 정본 체크섬 {canon.checksum[:16]}",
             f"> 필수 칸 {filled}/{total}개 작성 ({round(filled / total * 100) if total else 0}%). "
             "'작성 필요'는 FDE Data Studio STEP 3 에서 채울 칸, '해당 시'는 해당할 때만 쓰는 칸입니다.", ""]
    for n, sec in enumerate(sections, start=1):
        lines += [f"## {n}. {sec['section']}", "", "| 항목 | 작성 내용 | 근거 |", "|---|---|---|"]
        for it in sec["items"]:
            content = it["content"] or ("(작성 필요)" if it["source"] == "작성 필요" else "(해당 시 작성)")
            if it.get("note"):
                content += f" ({it['note']})"
            lines.append(f"| {_cell(it['item'])} | {_cell(content)} | {it['source']} |")
        lines.append("")
    rows = dictionary_rows(pd)
    if rows:
        lines += ["## 부록. 데이터 필드 정의", "", "| 표 | 컬럼 | 자료형 | 정의 | 단위 |", "|---|---|---|---|---|"]
        for r in rows:
            lines.append(f"| {_cell(r['table'])} | {_cell(r['column'])} | {r['type_label']} | {_cell(r['description'] or '(작성 필요)')} | {_cell(r['unit'])} |")
        lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------ Croissant 1.0
def _cid(text: str) -> str:
    """Croissant @id 로 쓸 짧은 상대 IRI (공백·구분자를 밑줄로)."""
    return re.sub(r"[\s/#?%\"<>\\^`{|}]+", "_", str(text)).strip("_") or "x"


def render_croissant(canon: canonical.Canonical, pd: ProcessDataset) -> str:
    r = canon.record
    dist = r.get("distribution") or {}
    rai_used = False
    doc: dict[str, Any] = {
        "@context": CROISSANT_CONTEXT,
        "@type": "sc:Dataset",
        "@id": canon.iri,
        "name": r.get("title") or canon.resource_id,
        "description": r.get("description") or r.get("title") or canon.resource_id,
        "url": r.get("landingPage") or canon.iri,
        "identifier": canon.resource_id,
    }
    if r.get("license") or r.get("accessRights"):
        doc["license"] = r.get("license") or r.get("accessRights")
    who = r.get("creator") or (r.get("publisher") or {}).get("label")
    if who:
        doc["creator"] = {"@type": "sc:Organization", "name": who}
    if r.get("publisher"):
        doc["publisher"] = {"@type": "sc:Organization", "name": r["publisher"]["label"], "sameAs": r["publisher"]["@id"]}
    for key, prop in (("issued", "datePublished"), ("modified", "dateModified"), ("version", "version")):
        if r.get(key):
            doc[prop] = str(r[key])
    if r.get("keywords"):
        doc["keywords"] = r["keywords"]
    if r.get("language"):
        doc["inLanguage"] = r["language"]
    if r.get("temporalResolution"):
        doc["isLiveDataset"] = True
    if who:
        doc["citeAs"] = ", ".join(x for x in (who, f"「{doc['name']}」", r.get("version"), canon.iri) if x)

    files: list[dict[str, Any]] = []
    fid = _cid(pd.asset.filename or canon.resource_id)
    if dist and pd.asset.filename:
        fo: dict[str, Any] = {"@type": "cr:FileObject", "@id": fid, "name": pd.asset.filename,
                              "contentUrl": dist.get("accessURL") or pd.asset.filename,
                              "encodingFormat": dist.get("mediaType")}
        if pd.asset.sha256:
            fo["sha256"] = pd.asset.sha256
        if pd.asset.size:
            fo["contentSize"] = f"{pd.asset.size} B"
        files.append(fo)
    elif pd.asset.kind == "stream":
        # 스트림은 메시지 하나를 JSON 레코드로 보고, 브로커 주소를 파일 객체의 위치로 적는다 (isLiveDataset)
        ep = r.get("endpointURL") or (pd.asset.stream or {}).get("endpoint_url")
        files.append({"@type": "cr:FileObject", "@id": fid, "name": pd.asset.name, "contentUrl": ep or pd.asset.name,
                      "encodingFormat": "application/jsonlines",
                      "description": "실시간 스트림 — 메시지 1건이 레코드 1건 (JSON)"})
    doc["distribution"] = files

    dic = canonical.dictionary(pd)
    record_sets = []
    for t in (pd.asset.profile or {}).get("tables", []):
        rs_id = _cid(t["name"])
        fields = []
        for c in t.get("columns", []):
            f: dict[str, Any] = {"@type": "cr:Field", "@id": f"{rs_id}/{_cid(c['name'])}", "name": c["name"],
                                 "dataType": _CR_TYPE.get(c["type"], "sc:Text")}
            ent = dic.get(t["name"], {}).get(c["name"], {})
            if ent.get("description"):
                f["description"] = ent["description"] + (f" (단위: {ent['unit']})" if ent.get("unit") else "")
            if files:
                extract = {"jsonPath": f"$.{c['name']}"} if pd.asset.kind == "stream" else {"column": c["name"]}
                f["source"] = {"fileObject": {"@id": fid}, "extract": extract}
            fields.append(f)
        rs: dict[str, Any] = {"@type": "cr:RecordSet", "@id": rs_id, "name": t["name"], "field": fields}
        keys = [k for k in r.get("joinKeys", []) if k.get("column") and any(c["name"] == k["column"] for c in t.get("columns", []))]
        if keys:
            rs["description"] = "연계키: " + ", ".join(f"{k['key']} {k['label']}({k['column']})" for k in keys)
        record_sets.append(rs)
    doc["recordSet"] = record_sets

    rai = {"rai:dataBiases": r.get("dataBiases"), "rai:dataLimitations": r.get("knownLimitations"),
           "rai:dataCollectionMissingData": r.get("missingData"), "rai:dataCollection": r.get("provenance"),
           "rai:dataPreprocessingProtocol": r.get("cardPreprocessing"), "rai:dataAnnotationProtocol": r.get("cardAnnotation"),
           "rai:personalSensitiveInformation": r.get("cardProtection"), "rai:dataUseCases": r.get("cardUseCases"),
           "rai:dataSocialImpact": r.get("cardSocialImpact"),
           "rai:dataReleaseMaintenancePlan": " · ".join(x for x in (
               f"갱신주기 {r['accrualPeriodicity']}" if r.get("accrualPeriodicity") else "", r.get("versionNotes", "")) if x) or None}
    for k, v in rai.items():
        if v:
            doc[k] = v
            rai_used = True
    doc["conformsTo"] = ["http://mlcommons.org/croissant/1.0"] + (["http://mlcommons.org/croissant/RAI/1.0"] if rai_used else [])
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


# ------------------------------------------------------------------ 자가검증
def verify(canon: canonical.Canonical, pd: ProcessDataset, contents: dict[str, str]) -> dict[str, Any]:
    """문서 산출물이 정본·프로파일과 맞는지 다시 읽어 확인한다."""
    problems: list[str] = []
    rows = dictionary_rows(pd)
    title = canon.record.get("title") or canon.resource_id
    if "croissant" in contents:
        try:
            g = Graph().parse(data=contents["croissant"], format="json-ld")
            ds = URIRef(canon.iri)
            if (ds, RDF.type, SDO.Dataset) not in g:
                problems.append("Croissant 에 sc:Dataset 없음")
            elif str(g.value(ds, SDO.name)) != title:
                problems.append("Croissant 이름이 정본 제목과 다름")
            n_fields = len(set(g.subjects(RDF.type, CR.Field)))
            if n_fields != len(rows):
                problems.append(f"Croissant 필드 {n_fields}개 ≠ 컬럼 {len(rows)}개")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"Croissant JSON-LD 해석 실패: {str(exc)[:120]}")
    if "dict" in contents:
        body = contents["dict"].lstrip("\ufeff")
        n = max(len(list(csv.reader(io.StringIO(body)))) - 1, 0)
        if n != len(rows):
            problems.append(f"데이터 사전 {n}행 ≠ 컬럼 {len(rows)}개")
    if "card" in contents:
        if title not in contents["card"] or canon.resource_id not in contents["card"]:
            problems.append("데이터 카드에 제목 또는 식별자 없음")
    detail = (f"Croissant 필드·데이터 사전 {len(rows)}행·데이터 카드가 정본과 일치" if not problems else "; ".join(problems))
    return {"name": "⑦ 문서 산출물 정합", "ok": not problems, "detail": detail}
