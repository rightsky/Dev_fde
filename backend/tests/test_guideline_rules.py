"""진단 규칙 파일(guideline_rules.json)의 구조 검사 — 가이드라인 v1.1 의 80항목과 맞는지 본다."""
from rdflib.plugins.sparql import prepareQuery

from app.services import canonical, diagnosis
from app.services.reference import guideline_rules, vocab


def test_rule_file_matches_guideline_structure():
    doc = guideline_rules()
    rules = doc["rules"]
    assert doc["total_items_in_guideline"] == 80 and len(rules) == 80
    assert len({r["id"] for r in rules}) == 80
    # 표 9~11 필수 22 · 표 9·12 권장·선택 7 · 15개 원칙 · 부록 3 공통 필수 15 · 공통 권장 18 · 유형별 3
    assert {a["id"]: a["guideline_items"] for a in doc["areas"]} == {"A1": 22, "A2": 7, "A3": 15, "A4": 15, "A5": 18, "A6": 3}
    for a in doc["areas"]:
        assert len([r for r in rules if r["area"] == a["id"]]) == a["guideline_items"], a
    assert all(r["level"] == "필수" for r in rules if r["area"] in ("A1", "A4"))
    assert sorted(r["level"] for r in rules if r["area"] == "A2") == ["권장"] * 3 + ["선택"] * 4
    assert all(r["level"] == "권장" for r in rules if r["area"] == "A5")
    methods = {m["id"] for m in doc["methods"]}
    for r in rules:
        assert r["method"] in methods, r["id"]
        assert r["name"] and r["text"] and r["basis"] and r["criteria"] and r["remedy"], r["id"]
        assert r.get("difficulty") in (1, 2, 3), r["id"]


def test_resolvers_are_executable():
    rules = guideline_rules()["rules"]
    ids = {r["id"] for r in rules}
    ns = dict(canonical.new_graph().namespaces())
    fields = {f["name"] for f in canonical.META_FIELDS} | {"extra_classes", "dictionary"}
    routes = vocab()["fix_routes"]
    for r in rules:
        res = r["resolver"]
        assert (r["method"] == "AUTO-DERIVED") == (res["type"] == "derived"), r["id"]
        if res["type"] == "ask":
            prepareQuery(res["query"], initNs=ns)
            if r.get("partial"):
                prepareQuery(r["partial"]["query"], initNs=ns)
        elif res["type"] == "builtin":
            assert res["name"] in diagnosis._BUILTINS, r["id"]
        elif res["type"] == "derived":
            assert set(res["from"]) <= ids - {r["id"]}, r["id"]
        else:
            assert res["type"] == "attest" and r["method"] == "HUMAN-ATTEST", r["id"]
        if r.get("route"):
            assert r["route"] in routes, r["id"]
            if r["route"] == "meta3":
                assert r.get("focus") in fields, r["id"]
        if r.get("focus_stream"):
            assert r["focus_stream"] in fields, r["id"]


def test_guideline_metadata_fields_have_form_inputs():
    """표 9~12 항목 가운데 사람이 적어야 하는 것은 STEP 3 폼에 입력 필드가 있어야 한다."""
    by_prop = {f["property"].split(" ")[0] for f in canonical.META_FIELDS}
    for prop in ("dcterms:title", "dcterms:description", "dcterms:references", "dcterms:creator", "dcterms:publisher",
                 "dcat:landingPage", "dcterms:accrualPeriodicity", "dcat:keyword", "dcat:contactPoint", "dcterms:language",
                 "dcat:accessURL", "dcat:mediaType", "owl:versionInfo", "dcterms:issued", "dcterms:modified",
                 "adms:versionNotes", "dcterms:rights", "dcterms:temporal", "dcterms:spatial", "rai:dataBiases",
                 "dqv:hasQualityAnnotation", "rai:knownLimitations", "rai:dataCollectionMissingData"):
        assert prop in by_prop, prop
