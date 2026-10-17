"""외부 정본 검사 (v0.20) — 스튜디오 밖에서 만든 Turtle · JSON-LD 를 올려 게이트 0 + SHACL 을 돌린다. 저장하지 않는다.

시연 2장면("정본 통과 · 오류본은 SHACL 도달 전 차단")과, 타 기관 · 타 도구 산출물의 사전 점검용.
게이트 0 은 스튜디오 자기 정본 검사(validation.gate0)와 같은 네 가지(파서 · prefix 완결 · UTF-8 · 임시 ID 잔존)를 외부 파일 기준으로 다시 구현했다.
⑤ 정체성 일치는 요청 데이터셋이 없으므로 "dcat:Dataset · dcterms:title · dcterms:identifier 존재" 검사로 대신한다.
"""
from __future__ import annotations

import re
from typing import Any

from rdflib import Graph, URIRef
from rdflib.namespace import DCAT, DCTERMS, RDF

from . import minting, validation

MAX_BYTES = 5 * 1024 * 1024
_PREFIX_DECL = re.compile(r"^\s*(?:@prefix|PREFIX)\s+([A-Za-z][\w-]*)?:\s*<", re.MULTILINE)
_TEMP_ID = re.compile(minting.DRAFT_PATTERN + r"|-신규\b|-초안\b|등록대기|TEMP-|TMP-", re.IGNORECASE)


def _format_of(filename: str) -> str | None:
    f = filename.lower()
    if f.endswith((".ttl", ".turtle")):
        return "turtle"
    if f.endswith((".jsonld", ".json")):
        return "json-ld"
    if f.endswith((".nt", ".ntriples")):
        return "nt"
    if f.endswith((".rdf", ".xml", ".owl")):
        return "xml"
    if f.endswith(".trig"):
        return "trig"
    return None


def check(filename: str, data: bytes, mode: str = "draft") -> dict[str, Any]:
    fmt = _format_of(filename)
    checks: list[dict[str, Any]] = []
    g: Graph | None = None
    text = ""
    # ③ UTF-8 (가장 먼저 — 깨진 바이트면 나머지는 의미 없다)
    try:
        text = data.decode("utf-8-sig")
        bad = "�" in text
        checks.append({"key": "utf8", "name": "③ 인코딩 UTF-8", "ok": not bad, "detail": "치환 문자(U+FFFD) 포함 — 원본 인코딩 손상" if bad else f"UTF-8 정상 ({len(data):,} bytes)"})
    except UnicodeDecodeError as exc:
        checks.append({"key": "utf8", "name": "③ 인코딩 UTF-8", "ok": False, "detail": f"UTF-8 로 읽을 수 없음: {exc}"[:200]})
        text = data.decode("utf-8", errors="replace")
    # ① 파서
    if fmt is None:
        checks.insert(0, {"key": "parse", "name": "① 파서 통과", "ok": False, "detail": "지원하지 않는 확장자 (.ttl · .jsonld · .nt · .rdf · .trig)"})
    else:
        try:
            g = Graph().parse(data=text, format=fmt)
            checks.insert(0, {"key": "parse", "name": "① 파서 통과", "ok": True, "detail": f"{fmt} 파싱 {len(g):,}트리플"})
        except Exception as exc:  # noqa: BLE001
            g = None
            first = str(exc).strip().splitlines()
            msg = " ".join(x.strip() for x in first[:2]) if first else type(exc).__name__
            checks.insert(0, {"key": "parse", "name": "① 파서 통과", "ok": False, "detail": f"파싱 실패: {type(exc).__name__}: {msg}"[:240]})
    # ② prefix 완결 (Turtle · TriG 만 의미 있다). 선언 안 된 접두어는 파서가 이미 실패시키므로, 여기서는 파서가 실패했을 때 어떤 접두어가 빠졌는지 짚어 준다
    if fmt in ("turtle", "trig"):
        declared = set(_PREFIX_DECL.findall(text)) | {""}
        body = re.sub(r"^\s*(?:@prefix|PREFIX)[^\n]*$", "", text, flags=re.MULTILINE)
        body = re.sub(r'"""[\s\S]*?"""|"[^"\n]*"|<[^>\s]*>|#[^\n]*', "", body)
        used = {m for m in re.findall(r"(?<![\w:<])([A-Za-z][\w-]*):(?=[A-Za-z_])", body)} - {"http", "https", "urn", "mailto", "file", "tel"}
        missing = sorted(used - declared)
        checks.insert(1, {"key": "prefix", "name": "② prefix 완결", "ok": not missing, "detail": ("미선언: " + ", ".join(missing[:8])) if missing else f"선언 {len(declared) - 1}개 · 사용한 접두어 전부 선언됨"})
    else:
        checks.insert(1, {"key": "prefix", "name": "② prefix 완결", "ok": True, "skipped": True, "detail": "Turtle 이 아니라 해당 없음 (JSON-LD 는 @context 로 해석)"})
    # ④ 임시 ID 잔존 — 그래프의 IRI 와 원문 둘 다
    if g is not None:
        temp = sorted({str(t) for tr in g for t in tr if isinstance(t, URIRef) and _TEMP_ID.search(str(t))})
    else:
        temp = sorted({m.group(0) for m in _TEMP_ID.finditer(text)})[:8]
    if mode == "publish":
        checks.append({"key": "mint", "name": "④ ID 잔존 검사", "ok": not temp, "detail": "임시 ID 없음" if not temp else f"임시 ID {len(temp)}건 — " + ", ".join(str(t).rsplit("/", 1)[-1] for t in temp[:4])})
    else:
        checks.append({"key": "mint", "name": "④ ID 잔존 검사", "ok": True, "skipped": True, "detail": ("초안 모드 — 발행 모드에서 검사" + (f" (임시 ID {len(temp)}건 보임)" if temp else ""))})
    # ⑤ 정체성 (대체): dcat:Dataset 또는 DataService 가 있고 제목 · 식별자가 있는가
    if g is not None:
        subjects = list(g.subjects(RDF.type, DCAT.Dataset)) + list(g.subjects(RDF.type, DCAT.DataService))
        titled = [s for s in subjects if g.value(s, DCTERMS.title) is not None]
        ident = [s for s in subjects if g.value(s, DCTERMS.identifier) is not None]
        ok = bool(subjects) and len(titled) == len(subjects)
        checks.append({"key": "identity", "name": "⑤ 정체성 (데이터셋 · 제목 · 식별자)", "ok": ok,
                       "detail": (f"dcat:Dataset/DataService {len(subjects)}건 · 제목 {len(titled)} · 식별자 {len(ident)}" if subjects else "dcat:Dataset 이 없음 — 메타데이터 정본이 아님")})
    gate_ok = all(c["ok"] for c in checks if c["key"] in ("parse", "prefix", "utf8"))
    out: dict[str, Any] = {"filename": filename, "format": fmt, "mode": mode, "gate0": checks, "gate0_passed": gate_ok and all(c["ok"] for c in checks),
                           "blocked_before_shacl": not gate_ok, "triples": len(g) if g is not None else 0, "shacl": None,
                           "shapes_version": validation.shapes_version()}
    if gate_ok and g is not None:
        rows, _report = validation.run_shacl(g, mode)
        viol = [r for r in rows if r["severity"] == "Violation"]
        out["shacl"] = {"conforms": not viol, "violations": len(viol), "warnings": sum(1 for r in rows if r["severity"] == "Warning"),
                        "infos": sum(1 for r in rows if r["severity"] == "Info"), "rows": rows[:300], "truncated": len(rows) > 300}
    out["verdict"] = ("차단: 게이트 0 실패 — SHACL 도달 전 반려" if not gate_ok else
                      "통과: 게이트 0 + SHACL 적합" if out["shacl"] and out["shacl"]["conforms"] and out["gate0_passed"] else
                      "SHACL 위반 있음" if out["shacl"] and not out["shacl"]["conforms"] else "게이트 0 일부 미충족 (④ · ⑤)")
    return out
