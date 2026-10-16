"""8단계 전 과정을 API 로 수행하는 통합 테스트.

업로드 → 조합 → 메타데이터 승인 → 분류 → 관계 → 검증(초안·발행) → 민팅 → 직렬화 → 발행 → 진단.
"""
import io
import json
import zipfile

import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCAT, DCTERMS, RDF, RDFS

from .samples import accident_csv, road_xlsx

S: dict = {}


def gate(state: dict, n: int) -> dict:
    return next(g for g in state["gates"] if g["step"] == n)


def test_01_upload_and_profile(client):
    r = client.post("/api/assets/upload", files=[
        ("files", ("도로목록.xlsx", road_xlsx(), "application/octet-stream")),
        ("files", ("교통사고.csv", accident_csv(), "text/csv")),
        ("files", ("영상.mp4", b"x", "video/mp4")),
    ])
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["created"]) == 2 and body["rejected"][0]["filename"] == "영상.mp4"
    road, acc = body["created"]
    assert road["profile_summary"] == "스키마 7컬럼 · 200행 (실측)"
    assert "K5" in road["keys"] and "K5" in acc["keys"]
    assert acc["media_type"] == "text/csv"
    S["road"], S["acc"] = road["id"], acc["id"]

    r = client.post("/api/assets/streams", json={
        "name": "cctv.vehicle.det.v1", "temporal_resolution": "PT1S", "event_time_column": "event_time",
        "endpoint_url": "kafka://broker:9092/cctv.vehicle.det.v1",
        "fields": [{"name": "event_time", "type": "datetime"}, {"name": "link_id"}, {"name": "vehicle_no"}]})
    assert r.status_code == 200, r.text
    assert {"K5", "K6", "K7"} <= set(r.json()["keys"])
    S["stream"] = r.json()["id"]
    assert client.post("/api/assets/streams", json={"name": "bad", "temporal_resolution": "5분"}).status_code == 422


def test_02_process_selection_and_suggestion(client):
    r = client.post("/api/processes", json={})
    assert r.status_code == 200
    S["pid"] = pid = r.json()["process"]["id"]
    st = r.json()["state"]
    assert gate(st, 2)["can_enter"] is False

    # 잠긴 단계로는 이동할 수 없다
    assert client.patch(f"/api/processes/{pid}", json={"current_step": 3}).status_code == 409

    r = client.put(f"/api/processes/{pid}/selection", json={"asset_ids": [S["road"], S["acc"], S["stream"]]})
    assert r.status_code == 200, r.text
    ds = {d["asset"]["id"]: d["id"] for d in r.json()["datasets"]}
    S["d_road"], S["d_acc"], S["d_stream"] = ds[S["road"]], ds[S["acc"]], ds[S["stream"]]
    assert gate(r.json()["state"], 2)["can_enter"] is True

    sug = client.get(f"/api/processes/{pid}/suggestions").json()["suggestions"]
    assert sug, "연계키를 공유하는 후보가 있으므로 추천이 나와야 한다"
    top = sug[0]
    assert set(top["dataset_ids"]) >= {S["d_road"], S["d_acc"]}
    assert any("값 일치 108건" in x for x in top["reasons"]), top["reasons"]


def test_03_combo_and_confirm(client):
    pid = S["pid"]
    r = client.put(f"/api/processes/{pid}/combo", json={"dataset_ids": [S["d_road"], S["d_acc"], S["d_stream"]], "source": "suggestion"})
    assert r.status_code == 200, r.text
    road = next(d for d in r.json()["datasets"] if d["id"] == S["d_road"])
    assert road["meta"]["media_type"].endswith("spreadsheetml.sheet") and road["approved_fields"] == []
    assert road["readiness"]["missing"] == ["publisher", "distribution"], "승인 전에는 미입력으로 본다"
    assert road["resource_id"].startswith("DST-draft-")

    w = client.get(f"/api/processes/{pid}/combo/warnings").json()
    assert any(x["code"] == "PROFILE" and "시간 포맷" in x["message"] for x in w["warnings"])
    assert w["draft"]["title"]

    assert client.post(f"/api/processes/{pid}/combo/confirm", json={"title": " "}).status_code == 422
    r = client.post(f"/api/processes/{pid}/combo/confirm", json={"title": "도로 사고 원인 분석 조합", "description": "도로·사고·CCTV 결합"})
    assert r.status_code == 200, r.text
    assert r.json()["process"]["name"] == "도로 사고 원인 분석 조합"
    st = r.json()["state"]
    assert all(gate(st, n)["can_enter"] for n in (3, 4, 5, 6)) and not gate(st, 7)["can_enter"]


def test_04_validation_fails_before_approval(client):
    pid = S["pid"]
    # 관계가 없으면 검증을 시작할 수 없다 (리니지 미결)
    r = client.post(f"/api/processes/{pid}/validation-runs")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "LINEAGE_UNRESOLVED"
    r = client.post(f"/api/processes/{pid}/lineage-waiver", json={"reason": "관계 지정 전 사전 점검"})
    assert r.status_code == 200
    r = client.post(f"/api/processes/{pid}/validation-runs")
    assert r.status_code == 200, r.text
    run = r.json()["run"]
    assert run["pass_count"] == 0 and run["fail_count"] == 3
    road = next(d for d in run["datasets"] if d["dataset_id"] == S["d_road"])
    shapes = {(x["shape"], (x["route"] or {}).get("key")) for x in road["results"] if x["severity"] == "Violation"}
    assert ("PublisherShape", "publisher") in shapes and ("MediaTypePlacementShape", "mediaType") in shapes
    stream = next(d for d in run["datasets"] if d["dataset_id"] == S["d_stream"])
    assert any(x["shape"] == "StreamServiceShape" and x["route"]["step"] == 3 for x in stream["results"] if x["severity"] == "Violation")
    assert all(c["ok"] for c in road["gate0"]), "구조 검사(게이트 0)는 통과해야 한다"
    # 검증 결과가 있으면 STEP 7 에 들어가 볼 수는 있지만(열람), 통과가 없으니 변환은 할 수 없다
    assert gate(r.json()["state"], 7)["can_enter"] and not gate(r.json()["state"], 7)["can_run"]
    client.delete(f"/api/processes/{pid}/lineage-waiver")


def test_05_metadata_approval(client):
    org = client.get("/api/orgs").json()[0]["id"]
    S["org"] = org
    # 값 없는 필드는 승인할 수 없다
    r = client.patch(f"/api/datasets/{S['d_road']}/meta", json={"values": {"publisher_org_id": None}, "approve": ["publisher_org_id"]})
    assert r.status_code == 422
    assert client.post(f"/api/datasets/{S['d_road']}/meta/confirm").status_code == 409

    for did in (S["d_road"], S["d_acc"]):
        r = client.patch(f"/api/datasets/{did}/meta", json={
            "values": {"publisher_org_id": org, "description": "테스트용 데이터셋 설명입니다.", "keywords": ["도로", "사고"]},
            "approve": ["publisher_org_id", "media_type"]})
        assert r.status_code == 200, r.text
        assert r.json()["readiness"]["level"] == "ai-ready"
        assert client.post(f"/api/datasets/{did}/meta/confirm").status_code == 200
    r = client.patch(f"/api/datasets/{S['d_stream']}/meta", json={
        "values": {"publisher_org_id": org, "watermark": "PT2M"},
        "approve": ["publisher_org_id", "temporal_resolution", "event_time_column"]})
    assert r.status_code == 200, r.text
    assert client.post(f"/api/datasets/{S['d_stream']}/meta/confirm").status_code == 200

    # 승인된 값을 고치면 승인이 풀린다
    r = client.patch(f"/api/datasets/{S['d_acc']}/meta", json={"values": {"media_type": "application/json"}})
    assert "media_type" not in r.json()["approved_fields"] and r.json()["readiness"]["missing"] == ["distribution"]
    assert r.json()["meta_confirmed_at"] is None, "필수 필드가 다시 비면 확정도 풀린다"
    r = client.patch(f"/api/datasets/{S['d_acc']}/meta", json={"values": {"media_type": "text/csv"}, "approve": ["media_type"]})
    assert r.json()["readiness"]["level"] == "ai-ready"
    assert client.post(f"/api/datasets/{S['d_acc']}/meta/confirm").status_code == 200

    assert client.patch(f"/api/datasets/{S['d_road']}/meta", json={"values": {"issued": "2026/08/01"}}).status_code == 422
    assert client.patch(f"/api/datasets/{S['d_road']}/meta", json={"values": {"nope": 1}}).status_code == 422

    pv = client.get(f"/api/datasets/{S['d_road']}/preview").json()
    g = Graph().parse(data=pv["turtle"], format="turtle")
    ds = URIRef(pv["iri"])
    assert (ds, RDF.type, DCAT.Dataset) in g and g.value(ds, DCTERMS.publisher) is not None
    dist = g.value(ds, DCAT.distribution)
    assert str(g.value(dist, DCAT.mediaType)).startswith("https://www.iana.org/assignments/media-types/application/vnd.openxml")
    assert pv["validation"]["passed"] is True


def test_05b_guideline_metadata_fields(client):
    """가이드라인 표 9~12 항목을 도로목록 1건에만 채운다 (교통사고·스트림은 최소 입력으로 둔다)."""
    did = S["d_road"]
    assert client.patch(f"/api/datasets/{did}/meta", json={"values": {"contact_phone": "전화없음"}}).status_code == 422
    assert client.patch(f"/api/datasets/{did}/meta", json={"values": {"landing_page": "data.example.go.kr"}}).status_code == 422
    r = client.patch(f"/api/datasets/{did}/meta", json={"values": {
        "creator": "도로정책과", "references": ["도로법 제23조", "https://www.law.go.kr/법령/도로법 제23조"],
        "landing_page": "https://data.example.go.kr/dataset/{road}", "provenance": "국가교통DB 에서 월 1회 내려받아 중복 구간을 제거",
        "access_url": "https://data.example.go.kr/file/road.xlsx", "endpoint_url": "https://api.example.go.kr/road/v1",
        "accrual_periodicity": "P1M", "contact_name": "도로정책과 담당자", "contact_email": "road@example.go.kr",
        "contact_phone": "044-201-3114", "version": "2026.01.v1", "issued": "2026-01-15", "modified": "2026-08-01",
        "version_notes": "최초 공개", "rights": "출처를 표시하면 상업적 이용과 변경을 허용한다",
        "quality_annotation": "월 1회 수동 검수 완료", "rai_missing_data": "차로수 결측 2% — 조사 누락, 대체하지 않음",
        "spatial": "대한민국"}})
    assert r.status_code == 200, r.text
    assert r.json()["meta_confirmed_at"] is not None, "권장·선택 필드를 채워도 확정은 유지된다"
    pv = client.get(f"/api/datasets/{did}/preview").json()
    g = Graph().parse(data=pv["turtle"], format="turtle")
    ds = URIRef(pv["iri"])
    OWL = Namespace("http://www.w3.org/2002/07/owl#")
    ADMS = Namespace("http://www.w3.org/ns/adms#")
    DQV = Namespace("http://www.w3.org/ns/dqv#")
    VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")
    FOAF = Namespace("http://xmlns.com/foaf/0.1/")
    RAI = Namespace("http://mlcommons.org/croissant/RAI/")
    assert str(g.value(ds, OWL.versionInfo)) == "2026.01.v1" and str(g.value(ds, ADMS.versionNotes)) == "최초 공개"
    assert (g.value(ds, DCTERMS.creator), RDF.type, FOAF.Agent) in g
    # 주소에 Turtle 로 쓸 수 없는 문자가 있어도 정본을 만들 수 있다 (퍼센트 인코딩, 한글은 그대로)
    assert str(g.value(ds, DCAT.landingPage)) == "https://data.example.go.kr/dataset/%7Broad%7D"
    assert URIRef("https://www.law.go.kr/법령/도로법%20제23조") in set(g.objects(ds, DCTERMS.references))
    assert (g.value(ds, DCTERMS.provenance), RDF.type, DCTERMS.ProvenanceStatement) in g
    assert str(g.value(ds, DCTERMS.language)) == "http://id.loc.gov/vocabulary/iso639-1/ko"
    assert (g.value(ds, DCTERMS.rights), RDF.type, DCTERMS.RightsStatement) in g
    assert (g.value(ds, DQV.hasQualityAnnotation), RDF.type, DQV.QualityAnnotation) in g
    assert g.value(ds, RAI.dataCollectionMissingData) is not None
    assert str(g.value(g.value(ds, DCAT.contactPoint), VCARD.hasTelephone)) == "tel:044-201-3114"
    dist = g.value(ds, DCAT.distribution)
    svc = g.value(dist, DCAT.accessService)
    assert (svc, RDF.type, DCAT.DataService) in g and str(g.value(svc, DCAT.endpointURL)) == "https://api.example.go.kr/road/v1"
    # 데이터 사전: 컬럼 정의를 적으면 csvw:Table 을 고르지 않아도 컬럼 구조가 정본에 들어간다
    d = client.get(f"/api/datasets/{did}/dictionary").json()
    assert d["total"] == 7 and d["described"] == 0 and {r["column"] for r in d["rows"]} >= {"LINK_ID", "도로명"}
    assert client.put(f"/api/datasets/{did}/dictionary", json={"entries": [{"table": "도로목록", "column": "없는컬럼", "description": "x"}]}).status_code == 422
    entries = [{"table": r["table"], "column": r["column"], "description": f"{r['column']} 설명",
                **({"unit": "m"} if r["column"] == "연장(m)" else {})} for r in d["rows"]]
    d = client.put(f"/api/datasets/{did}/dictionary", json={"entries": entries}).json()
    assert d["described"] == d["total"] == 7
    r = client.patch(f"/api/datasets/{did}/meta", json={"values": {"card_background": "도로 안전 정책 수립", "card_use_cases": "사고 위험 구간 예측"}})
    assert r.status_code == 200, r.text
    pv = client.get(f"/api/datasets/{did}/preview").json()
    g = Graph().parse(data=pv["turtle"], format="turtle")
    CSVW = Namespace("http://www.w3.org/ns/csvw#")
    SDO = Namespace("https://schema.org/")
    descs = {str(o) for c in g.subjects(RDF.type, CSVW.Column) for o in g.objects(c, DCTERMS.description)}
    assert "LINK_ID 설명" in descs and len(descs) == 7
    assert any(str(o) == "m" for o in g.objects(None, SDO.unitText))
    assert str(g.value(ds, RAI.dataUseCases)) == "사고 위험 구간 예측" and g.value(ds, RAI.dataLimitations) is None
    # AI 활용 이용조건 (가이드라인 3.4.5 표 39) → ODRL 정책
    assert client.patch(f"/api/datasets/{did}/meta", json={"values": {"ai_training": "yes"}}).status_code == 422
    r = client.patch(f"/api/datasets/{did}/meta", json={"values": {
        "ai_training": "permitted", "ai_combination": "conditional", "ai_redistribution": "prohibited",
        "ai_terms_conditions": "결합 전 재식별 위험 검토를 받고 출처를 표시한다"}})
    assert r.status_code == 200, r.text
    pv = client.get(f"/api/datasets/{did}/preview").json()
    g = Graph().parse(data=pv["turtle"], format="turtle")
    ODRL = Namespace("http://www.w3.org/ns/odrl/2/")
    pol = g.value(ds, ODRL.hasPolicy)
    assert (pol, RDF.type, ODRL.Set) in g and "재식별" in str(g.value(pol, RDFS.comment))
    perms = {g.value(r, ODRL.action) for r in g.objects(pol, ODRL.permission)}
    prohib = {g.value(r, ODRL.action) for r in g.objects(pol, ODRL.prohibition)}
    FDE = Namespace("https://catalog.molit.go.kr/def/")
    assert perms == {FDE.aiTraining, FDE.dataCombination} and prohib == {ODRL.distribute}
    assert all((a, RDF.type, ODRL.Action) in g for a in perms | prohib), "동작 정의도 같은 그래프에 있다"
    cond = next(r for r in g.objects(pol, ODRL.permission) if g.value(r, ODRL.action) == FDE.dataCombination)
    assert g.value(cond, FDE.conditional).toPython() is True
    # 파일형 데이터셋의 API 접근 서비스는 스트림 셰이프(StreamServiceShape)의 대상이 아니다
    assert pv["validation"]["passed"] is True, [x for x in pv["validation"]["results"] if x["severity"] == "Violation"]
    assert not [x for x in pv["validation"]["results"] if x["shape"] == "StreamServiceShape"]


def test_06_classification(client):
    sug = client.get(f"/api/datasets/{S['d_road']}/classification/suggestions").json()["suggestions"]
    by = {(s["axis"], s["code"]) for s in sug}
    assert ("F1", "F1-02") in by and ("F2", "F2-01") in by and ("K", "K5") in by and ("F3", "F3-01") in by
    assert client.post(f"/api/datasets/{S['d_road']}/classification/confirm").status_code == 409

    assert client.put(f"/api/datasets/{S['d_road']}/classification", json={"F4": ["F4-01", "F4-02"]}).status_code == 422
    assert client.put(f"/api/datasets/{S['d_road']}/classification", json={"F1": ["F2-01"]}).status_code == 422
    assert client.put(f"/api/datasets/{S['d_road']}/classification", json={"K": [{"code": "K5", "column": "없는컬럼"}]}).status_code == 422

    payloads = {
        S["d_road"]: {"F1": ["F1-02"], "F2": ["F2-01", "F2-05"], "F3": ["F3-01"], "F4": ["F4-01"], "F6": ["F6-03"],
                      "K": [{"code": "K5", "column": "LINK_ID"}, {"code": "K3", "column": "경도"}], "N2SF": "N2SF-O"},
        S["d_acc"]: {"F1": ["F1-01"], "F2": ["F2-01"], "F4": ["F4-06"], "F6": ["F6-02"],
                     "K": [{"code": "K5", "column": "도로링크ID"}, {"code": "K7", "column": "발생일시"}], "N2SF": "N2SF-S"},
        S["d_stream"]: {"F1": ["F1-01"], "F2": ["F2-06"], "F4": ["F4-05"], "F6": ["F6-01"],
                        "K": [{"code": "K5", "column": "link_id"}], "N2SF": "N2SF-S"},
    }
    for did, body in payloads.items():
        assert client.put(f"/api/datasets/{did}/classification", json=body).status_code == 200
        r = client.post(f"/api/datasets/{did}/classification/confirm")
        assert r.status_code == 200, r.text
    st = client.get(f"/api/processes/{S['pid']}").json()["state"]
    assert gate(st, 3)["done"] and gate(st, 4)["done"] and not gate(st, 5)["done"]


def test_07_relations_with_real_join_stats(client):
    pid = S["pid"]
    payload = client.get(f"/api/processes/{pid}/relations").json()
    cand = next(c for c in payload["candidates"] if c["key_code"] == "K5" and {c["source_id"], c["target_id"]} == {S["d_road"], S["d_acc"]})
    assert cand["stats"]["matched"] == 108
    r = client.post(f"/api/processes/{pid}/relations", json={
        "type": "JOINED_ON", "source_id": S["d_acc"], "target_id": S["d_road"], "key_code": "K5",
        "source_table": "교통사고", "source_column": "도로링크ID", "target_table": "도로목록", "target_column": "LINK_ID"})
    assert r.status_code == 200, r.text
    rel = r.json()["relations"][0]
    # 사고 123종 링크 중 108종이 도로 목록에 있다 (10건마다 넣은 X 링크 15종은 불일치)
    assert rel["stats"]["computed"] and rel["stats"]["matched"] == 108 and rel["stats"]["source_distinct"] == 123
    assert rel["stats"]["unmatched_samples"][0].startswith("X")
    assert rel["status"] == "draft" and r.json()["lineage_resolved"] is False
    assert client.post(f"/api/processes/{pid}/relations", json={
        "type": "JOINED_ON", "source_id": S["d_road"], "target_id": S["d_acc"], "key_code": "K5"}).status_code == 409
    r = client.post(f"/api/relations/{rel['id']}/confirm")
    assert r.status_code == 200 and r.json()["lineage_resolved"] is True
    r = client.post(f"/api/processes/{pid}/relations", json={"type": "GROUPED_WITH", "source_id": S["d_stream"],
                                                             "target_id": S["d_acc"], "confirm": True})
    assert r.status_code == 200, r.text

    for level, must in ((1, {"Collection", "Dataset", "Service"}), (2, {"Agent", "Activity"}), (3, {"Distribution", "Table"}),
                        (4, {"Column", "JoinKey"})):
        gr = client.get(f"/api/processes/{pid}/graph", params={"level": level}).json()
        assert must <= set(gr["node_counts"]), (level, gr["node_counts"])
        ids = {n["id"] for n in gr["nodes"]}
        assert all(e["source"] in ids and e["target"] in ids for e in gr["edges"])
    assert gr["edge_counts"]["JOINED_ON"] == 2, "데이터셋 간 1건 + 컬럼 간 1건"


def test_08_validation_passes_and_goes_stale(client):
    pid = S["pid"]
    r = client.post(f"/api/processes/{pid}/validation-runs")
    assert r.status_code == 200, r.text
    run = r.json()["run"]
    assert run["pass_count"] == 3, [(d["name"], [x["message"] for x in d["results"] if x["severity"] == "Violation"]) for d in run["datasets"]]
    assert "재검증 — 직전 위반" in client.get(f"/api/processes/{pid}/activities").json()[0]["text"]
    road = next(d for d in run["datasets"] if d["dataset_id"] == S["d_road"])
    # 좌표 연계키(K3)가 있는데 좌표계를 선언하지 않았으므로 Warning 이 남는다
    crs = [x for x in road["results"] if "좌표계" in x["message"]]
    assert crs and crs[0]["severity"] == "Warning" and crs[0]["route"]["focus"] == "conforms_to"
    st = r.json()["state"]
    assert gate(st, 6)["done"] and gate(st, 7)["can_enter"] and gate(st, 7)["can_run"]
    S["checksum_before"] = road["checksum"]

    # 상류(STEP 3)를 고치면 검증 결과가 무효화된다. STEP 7 은 지난 결과를 볼 수는 있지만(열람) 새로 변환할 수는 없다
    client.patch(f"/api/datasets/{S['d_road']}/meta", json={"values": {"conforms_to": ["EPSG:5186"]}})
    st = client.get(f"/api/processes/{pid}").json()["state"]
    assert st["validation"]["stale"] and not gate(st, 6)["done"]
    assert gate(st, 7)["can_enter"] and not gate(st, 7)["can_run"] and "최신" in gate(st, 7)["run_reason"] or gate(st, 7)["run_reason"]
    r = client.post(f"/api/processes/{pid}/serialization-runs", json={})
    assert r.status_code == 409 and "변환 불가" in r.json()["detail"]

    run = client.post(f"/api/processes/{pid}/validation-runs").json()["run"]
    road = next(d for d in run["datasets"] if d["dataset_id"] == S["d_road"])
    assert road["checksum"] != S["checksum_before"] and not [x for x in road["results"] if "좌표계" in x["message"]]
    rep = client.get(f"/api/validation-runs/{run['id']}/report", params={"dataset_id": S["d_road"]})
    assert rep.status_code == 200 and "ValidationReport" in rep.text


def test_09_serialization_and_self_verify(client):
    pid = S["pid"]
    r = client.post(f"/api/processes/{pid}/serialization-runs", json={})
    assert r.status_code == 200, r.text
    run = r.json()["run"]
    assert run["ok_count"] == 3 and len(run["artifacts"]) == 21, "3건 × 7포맷"
    for sv in run["self_verify"]:
        assert sv["passed"] and len(sv["checks"]) == 7, sv
    arts = {(a["dataset_id"], a["fmt"]): a for a in run["artifacts"]}
    ttl = client.get(f"/api/artifacts/{arts[(S['d_acc'], 'ttl')]['id']}").json()["content"]
    jld = client.get(f"/api/artifacts/{arts[(S['d_acc'], 'jsonld')]['id']}").json()["content"]
    g1, g2 = Graph().parse(data=ttl, format="turtle"), Graph().parse(data=jld, format="json-ld")
    assert isomorphic(g1, g2) and len(g1) > 40
    # 분류·관계가 실제 산출물에 들어 있다
    FDE = Namespace("https://catalog.molit.go.kr/def/")
    ds = next(g1.subjects(RDF.type, DCAT.Dataset))
    assert g1.value(ds, DCAT.theme) is not None and g1.value(ds, FDE.n2sfGrade) is not None
    rel = g1.value(ds, DCAT.qualifiedRelation)
    assert rel is not None and str(g1.value(rel, FDE.sourceColumn)) == "도로링크ID" and float(g1.value(rel, FDE.matchRate)) == pytest.approx(108 / 123, abs=1e-3)
    assert "draft" in str(ds)
    txt = client.get(f"/api/artifacts/{arts[(S['d_acc'], 'txt')]['id']}").json()["content"]
    assert "「교통사고」는 " in txt and "「도로목록」과 K5 기준으로 결합된다 (도로링크ID = LINK_ID)" in txt and "ai-ready" in txt
    # 문서 산출물: Croissant · 데이터 카드 · 데이터 사전
    get = lambda did, fmt: client.get(f"/api/artifacts/{arts[(did, fmt)]['id']}").json()["content"]  # noqa: E731
    cr = json.loads(get(S["d_road"], "croissant"))
    assert "http://mlcommons.org/croissant/1.0" in cr["conformsTo"] and cr["distribution"][0]["sha256"]
    fields = cr["recordSet"][0]["field"]
    assert len(fields) == 7 and fields[0]["source"]["extract"]["column"] and any(f.get("description") == "LINK_ID 설명" for f in fields)
    assert cr["rai:dataUseCases"] == "사고 위험 구간 예측"
    card = get(S["d_road"], "card")
    assert card.startswith("# 데이터 카드: 도로목록") and "## 6. 기술적 사양" in card and "도로 안전 정책 수립" in card
    assert "(작성 필요)" in card, "채우지 않은 칸은 작성 필요로 표시한다"
    dic = get(S["d_road"], "dict")
    assert dic.startswith("\ufeff표,컬럼,자료형,정의") and len(dic.strip().splitlines()) == 8
    acc_dic = get(S["d_acc"], "dict")
    assert "(개인정보 의심 · 표시 안 함)" in acc_dic, "개인정보 의심 컬럼의 예시값은 내보내지 않는다"
    assert "차량번호" in get(S["d_acc"], "card") and "(개인정보 의심 · 표시 안 함)" in get(S["d_acc"], "card")
    schema = json.loads(client.get(f"/api/artifacts/{arts[(S['d_stream'], 'schema')]['id']}").json()["content"])
    assert {"@id", "identifier", "title", "publisher", "temporalResolution", "eventTimeColumn"} <= set(schema["required"])

    z = client.get(f"/api/serialization-runs/{run['id']}/download")
    assert z.status_code == 200
    with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
        names = zf.namelist()
        assert "manifest.json" in names and len(names) == 22
        man = json.loads(zf.read("manifest.json"))
        assert all(f["sha256"] for f in man["files"])
    dl = client.get(f"/api/artifacts/{arts[(S['d_road'], 'ttl')]['id']}", params={"download": True})
    assert "attachment" in dl.headers["content-disposition"] and dl.headers["content-type"].startswith("text/turtle")
    st = r.json()["state"]
    assert gate(st, 7)["done"] and gate(st, 8)["can_enter"]


def test_09b_croissant_is_valid_for_reference_library(client, tmp_path):
    """MLCommons 의 Croissant 참조 라이브러리(mlcroissant)로 산출물을 읽어 본다. 라이브러리가 없으면 건너뛴다."""
    mlc = pytest.importorskip("mlcroissant")
    run = client.get(f"/api/processes/{S['pid']}/serialization-runs/latest").json()["run"]
    for a in [a for a in run["artifacts"] if a["fmt"] == "croissant"]:
        path = tmp_path / a["filename"]
        path.write_text(client.get(f"/api/artifacts/{a['id']}").json()["content"], encoding="utf-8")
        ds = mlc.Dataset(jsonld=str(path))  # 명세 위반이면 ValidationError
        assert ds.metadata.name and ds.metadata.record_sets, a["filename"]


def test_10_publish_requires_mint(client):
    pid = S["pid"]
    r = client.post(f"/api/processes/{pid}/publish")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "PUBLISH_BLOCKED"

    client.patch(f"/api/processes/{pid}", json={"pub_mode": True})
    st = client.get(f"/api/processes/{pid}").json()["state"]
    assert "발행 모드" in st["validation"]["stale"]
    run = client.post(f"/api/processes/{pid}/validation-runs").json()["run"]
    assert run["mode"] == "publish" and run["pass_count"] == 0
    road = next(d for d in run["datasets"] if d["dataset_id"] == S["d_road"])
    g0 = next(c for c in road["gate0"] if c["key"] == "mint")
    assert not g0["ok"] and "미민팅" in g0["detail"]
    assert any((x["route"] or {}).get("key") == "mint" for x in road["results"])

    r = client.post(f"/api/processes/{pid}/mint")
    assert r.status_code == 200, r.text
    ids = sorted(m["minted_id"] for m in r.json()["created"])
    assert ids == ["DST-000001", "DST-000002", "SVC-000001"]
    assert client.post(f"/api/processes/{pid}/mint").json()["created"] == [], "같은 원천은 다시 발급하지 않는다"

    run = client.post(f"/api/processes/{pid}/validation-runs").json()["run"]
    assert run["pass_count"] == 3, [(d["name"], [x["message"] for x in d["results"] if x["severity"] == "Violation"]) for d in run["datasets"]]
    assert client.post(f"/api/processes/{pid}/publish").status_code == 409, "발행 모드 직렬화가 아직 없다"
    sr = client.post(f"/api/processes/{pid}/serialization-runs", json={}).json()["run"]
    assert sr["ok_count"] == 3

    # 검수 큐 (표 40 HITL): 개인정보 의심 컬럼·결합이 있어 위험 '높음' → 관리자도 바로 발행할 수 없다
    pr = client.get(f"/api/processes/{pid}/publish-review").json()
    S["review_probe"] = pr
    a = pr["assessment"]
    codes = {x["code"]: x["severity"] for x in a["signals"]}
    assert a["level"] == "high" and codes.get("pii") == "high" and codes.get("combination") == "high", codes
    assert pr["direct_publish"] is False and {d["change"] for d in a["datasets"]} == {"new"}
    r = client.post(f"/api/processes/{pid}/publish")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "REVIEW_REQUIRED"

    # 담당자(작업자) 계정이 검수를 요청한다
    assert client.post("/api/users", json={"username": "worker1", "name": "담당자", "password": "worker-pass-1",
                                           "role": "worker"}).status_code == 200
    wtok = client.post("/api/auth/login", json={"username": "worker1", "password": "worker-pass-1"}).json()["access_token"]
    wh = {"Authorization": f"Bearer {wtok}"}
    assert client.post(f"/api/processes/{pid}/publish", headers=wh).status_code == 403, "발행은 관리자만"
    rq = client.post(f"/api/processes/{pid}/review-requests", json={"message": "도로·사고 결합 데이터 발행 요청"}, headers=wh)
    assert rq.status_code == 200, rq.text
    rq = rq.json()
    assert rq["status"] == "pending" and rq["risk_level"] == "high" and len(rq["datasets"]) == 3
    assert client.post(f"/api/processes/{pid}/review-requests", json={}, headers=wh).json()["detail"]["code"] == "REVIEW_PENDING"
    assert client.post(f"/api/processes/{pid}/publish").json()["detail"]["code"] == "REVIEW_PENDING"
    q = client.get("/api/review-requests", params={"status": "pending"}).json()
    assert [x["id"] for x in q["items"]] == [rq["id"]] and q["counts"]["pending"] == 1
    assert client.post(f"/api/review-requests/{rq['id']}/approve", json={}, headers=wh).status_code == 403, "승인은 관리자만"

    # 반려 → 다시 요청 → 고위험 신호를 모두 확인해야 승인된다
    assert client.post(f"/api/review-requests/{rq['id']}/reject", json={"note": ""}).status_code == 422
    rj = client.post(f"/api/review-requests/{rq['id']}/reject", json={"note": "차량번호 비식별 여부를 C-12 에 적어 주세요"}).json()
    assert rj["status"] == "rejected" and rj["reviewer"] == "관리자"
    rq = client.post(f"/api/processes/{pid}/review-requests", json={"message": "재요청"}, headers=wh).json()
    # 요청 뒤에 변환을 다시 돌리면 검토한 내용과 발행할 내용이 달라질 수 있으므로 승인하지 않는다
    assert client.post(f"/api/processes/{pid}/serialization-runs", json={}).status_code == 200
    assert client.get(f"/api/review-requests/{rq['id']}").json()["stale"]
    high = [x["code"] for x in rq["signals"] if x["severity"] == "high"]
    r = client.post(f"/api/review-requests/{rq['id']}/approve", json={"acknowledged": high})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "REVIEW_STALE"
    assert client.post(f"/api/review-requests/{rq['id']}/withdraw", headers=wh).json()["status"] == "withdrawn"
    # 관리자 본인이 요청한 고위험 발행을 직접 승인하려면 사유가 필요하다
    mine = client.post(f"/api/processes/{pid}/review-requests", json={}).json()
    r = client.post(f"/api/review-requests/{mine['id']}/approve", json={"acknowledged": high, "note": "확인"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "SELF_APPROVAL_NOTE"
    assert client.post(f"/api/review-requests/{mine['id']}/withdraw").status_code == 200
    rq = client.post(f"/api/processes/{pid}/review-requests", json={"message": "재요청"}, headers=wh).json()
    r = client.post(f"/api/review-requests/{rq['id']}/approve", json={"acknowledged": high[:1]})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "ACK_REQUIRED"
    r = client.post(f"/api/review-requests/{rq['id']}/approve", json={"acknowledged": high, "note": "결합 키는 도로링크뿐, 개인 식별 불가 확인"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["request"]["status"] == "approved" and body["request"]["self_approved"] is False
    assert sorted(e["resource_id"] for e in body["published"]) == ids == sorted(body["request"]["published"])
    assert client.post(f"/api/review-requests/{rq['id']}/approve", json={"acknowledged": high}).status_code == 409
    acts = [a["type"] for a in client.get("/api/activities").json()]
    assert {"review_request", "review_reject", "review_approve"} <= set(acts)
    # 같은 내용으로는 다시 요청할 필요가 없다
    assert client.post(f"/api/processes/{pid}/review-requests", json={}, headers=wh).status_code == 409

    cat = client.get("/api/catalog", params={"q": "사고"}).json()
    assert cat["total"] >= 1 and ("교통물류", 2) in [tuple(x) for x in cat["facets"]["theme"]] or cat["total"] >= 1
    entry = client.get("/api/catalog/DST-000001").json()
    g = Graph().parse(data=entry["turtle"], format="turtle")
    assert not any("draft" in str(t) for triple in g for t in triple), "발행물에 초안 ID 가 남으면 안 된다"
    assert entry["version"] == 1 and entry["facets"]["readiness"] == "ai-ready"
    raw = client.get("/api/catalog/DST-000001/raw", params={"format": "jsonld"})
    assert raw.status_code == 200 and Graph().parse(data=raw.text, format="json-ld")
    # 발행본과 같은 정본에서 만든 문서 산출물도 카탈로그에서 받는다
    assert set(entry["documents"]) == {"croissant", "card", "dict"}
    assert "DST-000001" in entry["documents"]["card"] and "draft" not in entry["documents"]["croissant"]
    assert "AI 활용 이용조건" in entry["documents"]["card"] and "| 재배포 | 불허 |" in entry["documents"]["card"]
    assert entry["facets"]["ai_terms"] == {"ai_training": "permitted", "ai_combination": "conditional", "ai_redistribution": "prohibited"}
    raw = client.get("/api/catalog/DST-000001/raw", params={"format": "croissant"})
    assert raw.status_code == 200 and json.loads(raw.text)["identifier"] == "DST-000001"


def test_11_diagnosis_and_attestation(client):
    pid = S["pid"]
    r = client.post(f"/api/processes/{pid}/diagnosis-runs")
    assert r.status_code == 200, r.text
    run = r.json()["run"]
    items = {i["id"]: i for i in run["items"]}
    sm = run["summary"]
    # 가이드라인 80항목 전체를 판정한다
    assert len(items) == 80 and sm["guideline_total"] == sm["implemented_total"] == 80
    assert [a["implemented"] for a in sm["areas"]] == [a["guideline_items"] for a in sm["areas"]] == [22, 7, 15, 15, 18, 3]
    assert all(i["text"] and i["criteria"] and i["level"] for i in items.values())
    assert items["M-01"]["text"] == "데이터셋의 공식 명칭" and items["M-01"]["property"] == "dct:title"
    assert items["P-01"]["text"].startswith("데이터는 개방형 방식으로 제공되어야 하며")

    # 메타데이터 (표 9~12): 도로목록만 채웠으므로 대부분 부분 충족이다
    assert items["M-01"]["status"] == "met" and items["M-05"]["status"] == "met" and items["M-10"]["status"] == "met"
    assert items["M-04"]["status"] == "partial" and items["M-04"]["route"]["focus"] == "creator"
    assert {d["status"] for d in items["M-13"]["datasets"]} == {"met"} and len(items["M-13"]["datasets"]) == 2, "스트림은 배포본 항목에서 빠진다"
    m14 = {d["id"]: d for d in items["M-14"]["datasets"]}
    assert m14[S["d_road"]]["status"] == "met" and m14[S["d_acc"]]["status"] == "unmet"
    assert m14[S["d_stream"]]["status"] == "met" and m14[S["d_stream"]]["focus"] == "endpoint_url"
    assert items["M-21"]["status"] == "partial", "공공누리(license)는 도로목록뿐이고 나머지는 제공 조건(accessRights)만 있다"
    assert items["O-04"]["status"] == "unmet" and items["O-04"]["route"]["focus"] == "rai_data_biases"
    assert items["O-03"]["status"] == "met" and items["O-05"]["status"] == "partial"

    # 체크리스트 (부록 3)
    c01 = {d["id"]: d["status"] for d in items["C-01"]["datasets"]}
    assert c01 == {S["d_road"]: "unmet", S["d_acc"]: "met"}, "XLSX 는 비권장 포맷, CSV 는 권장 오픈 포맷"
    assert items["C-04"]["status"] == "met"
    assert items["C-07"]["status"] in ("partial", "unmet"), "사고 CSV 의 발생일시가 ISO 8601 이 아니다"
    assert items["C-09"]["status"] == "partial", "사고 CSV 는 결측 표기가 혼재한다"
    assert items["C-12"]["status"] == "pending", "개인정보 의심 컬럼(차량번호)이 있어 담당자 확인이 필요하다"
    assert items["R-10"]["method"] == "AUTO-GRAPH" and not items["R-10"]["attestable"]
    r10 = {d["id"]: d["status"] for d in items["R-10"]["datasets"]}
    assert set(r10) == {S["d_road"], S["d_acc"], S["d_stream"]} and items["R-10"]["status"] in ("partial", "unmet")
    c06 = {d["id"]: d["status"] for d in items["C-06"]["datasets"]}
    assert c06 == {S["d_road"]: "met", S["d_acc"]: "unmet", S["d_stream"]: "unmet"}, items["C-06"]["datasets"]
    assert items["R-09"]["status"] == "pending" and items["R-09"]["attestable"]
    assert items["R-12"]["status"] == "met" and items["R-18"]["status"] == "met"
    r06 = {d["id"]: d["status"] for d in items["R-06"]["datasets"]}
    assert r06 == {S["d_road"]: "met", S["d_acc"]: "partial", S["d_stream"]: "partial"}, "출처·가공 이력은 도로목록에만 적었다"
    assert items["R-13"]["status"] == "partial" and items["R-14"]["status"] == "met"
    r13 = {d["id"]: d["status"] for d in items["R-13"]["datasets"]}
    assert r13 == {S["d_road"]: "met", S["d_acc"]: "unmet", S["d_stream"]: "partial"}, "kafka:// 는 웹 기반 API 가 아니다"
    assert len(items["R-14"]["datasets"]) == 1, "API 엔드포인트가 없는 데이터셋은 해당 없음"
    assert items["R-02"]["status"] == "na" and items["R-02"]["score"] is None
    assert items["R-15"]["status"] == "pending" and items["U-01"]["status"] == "pending"
    assert items["P-10"]["status"] == "na" and "AI 에이전트(MCP)로 제공하지 않음" in items["P-10"]["evidence"][0], "에이전트 키가 없다"

    # 종합 항목: 연결 항목의 판정을 종합한다
    assert items["C-05"]["method"] == "AUTO-DERIVED" and len(items["C-05"]["related"]) == 22
    assert items["C-05"]["status"] == "partial"
    assert [c["id"] for c in items["P-03"]["related"]] == ["C-04", "C-05"] and items["P-03"]["status"] == "partial"
    assert items["P-11"]["status"] == "pending", "연결 항목이 전부 확인 대기면 확인 대기"
    assert items["P-12"]["status"] == "met" and items["P-15"]["status"] == "met"

    assert run["max_score"] == len([i for i in run["items"] if i["status"] != "na"])
    assert sum(m["total"] for m in sm["methods"]) == 80
    road = sm["roadmap"]
    assert road[0]["difficulty"] == "낮음" and all(x["method"] != "AUTO-DERIVED" for x in road)
    before, max_before = run["score"], run["max_score"]

    att = f"/api/processes/{pid}/attestations"
    assert client.put(f"{att}/M-01", json={"status": "met", "evidence": "x"}).status_code == 422, "자동 판정 항목"
    assert client.put(f"{att}/P-01", json={"status": "met", "evidence": "x"}).status_code == 422, "종합 항목"
    assert client.put(f"{att}/R-09", json={"status": "met"}).status_code == 422, "증빙 필수"
    assert client.put(f"{att}/P-10", json={"status": "na"}).status_code == 422, "해당 없음에도 사유가 필요하다"
    assert client.put(f"{att}/R-09", json={"status": "met", "evidence": "공유폴더/데이터카드_v1.docx"}).status_code == 200
    assert client.put(f"{att}/P-10", json={"status": "na", "evidence": "AI 에이전트·MCP 로 제공하지 않는 데이터"}).status_code == 200
    assert client.put(f"{att}/C-15", json={"status": "met", "evidence": "기관 누리집 오류 신고 게시판"}).status_code == 200
    run = client.post(f"/api/processes/{pid}/diagnosis-runs").json()["run"]
    items = {i["id"]: i for i in run["items"]}
    assert items["R-09"]["status"] == "met" and items["P-10"]["status"] == "na" and items["P-10"]["score"] is None
    assert items["C-15"]["status"] == "met" and items["P-11"]["status"] == "met", "연결 항목이 충족되면 원칙도 충족된다"
    assert run["max_score"] == max_before and run["score"] == before + 3
    rep = client.get(f"/api/diagnosis-runs/{run['id']}/report")
    assert rep.status_code == 200 and "가이드라인 준수 진단 보고서" in rep.text and "데이터셋의 공식 명칭" in rep.text
    latest = client.get(f"/api/processes/{pid}/diagnosis-runs/latest").json()
    assert latest["ruleset"]["implemented_total"] == 80 and latest["ruleset"]["method_counts"]["HUMAN-ATTEST"] == 16

    # 담당자 확인은 그때의 조합을 보고 한 것이므로, 그 뒤에 조합 구성이 바뀌면 다시 확인받는다
    from app.db import SessionLocal
    from app.services import activity

    with SessionLocal() as db:
        activity.log(db, "combo_change", "조합 변경 — (테스트)", process_id=pid)
        db.commit()
    items = {i["id"]: i for i in client.post(f"/api/processes/{pid}/diagnosis-runs").json()["run"]["items"]}
    assert items["R-09"]["status"] == "pending" and items["R-09"]["attestation"]["outdated"] is True
    assert "다시 확인 필요" in items["R-09"]["evidence"][0] and items["P-10"]["status"] == "na"
    assert client.put(f"{att}/R-09", json={"status": "met", "evidence": "공유폴더/데이터카드_v2.docx"}).status_code == 200
    assert client.delete(f"{att}/C-15").status_code == 200 and client.delete(f"{att}/C-15").status_code == 404
    items = {i["id"]: i for i in client.post(f"/api/processes/{pid}/diagnosis-runs").json()["run"]["items"]}
    assert items["R-09"]["status"] == "met" and items["C-15"]["status"] == "pending" and items["C-15"]["attestation"] is None

    r = client.post(f"/api/processes/{pid}/complete")
    assert r.status_code == 200 and r.json()["process"]["status"] == "completed"
    assert client.patch(f"/api/datasets/{S['d_road']}/meta", json={"values": {"version": "2"}}).status_code == 409


def test_12_lifecycle_and_permissions(client):
    pid = S["pid"]
    assert client.delete(f"/api/processes/{pid}").status_code == 409
    assert client.post(f"/api/processes/{pid}/trash").status_code == 200
    assert all(p["id"] != pid for p in client.get("/api/processes").json())
    assert client.post(f"/api/processes/{pid}/restore").json()["status"] == "completed"
    assert client.delete(f"/api/assets/{S['road']}").status_code == 409, "민팅된 원천은 삭제할 수 없다"

    r = client.post("/api/users", json={"username": "viewer1", "name": "열람자", "password": "viewer-pass-1", "role": "viewer"})
    assert r.status_code == 200, r.text
    tok = client.post("/api/auth/login", json={"username": "viewer1", "password": "viewer-pass-1"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/processes", headers=h).status_code == 200
    assert client.post("/api/processes", json={}, headers=h).status_code == 403
    assert client.post(f"/api/processes/{pid}/mint", headers=h).status_code == 403
    assert client.get("/api/processes", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401

    d = client.get("/api/dashboard").json()
    assert d["counts"]["catalog_published"] == 3 and d["counts"]["minted"] == 3
    reg = client.get("/api/mint-registry").json()
    assert reg["next"] == {"DST": "DST-000003", "SVC": "SVC-000002"}
    shapes = client.get("/api/shapes", params={"mode": "publish"}).json()
    assert any(r["local"] == "MintedIdShape" for r in shapes["rules"]) and "fdesh:PublisherShape" in shapes["turtle"]


# ------------------------------------------------------------------ MCP (AI 에이전트)
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json",
               "MCP-Protocol-Version": "2025-06-18"}


def _rpc(client, key, method, params=None, id_=1):
    h = {**MCP_HEADERS, "Authorization": f"Bearer {key}"}
    body = {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}
    return client.post("/api/mcp", json=body, headers=h)


def _tool(client, key, name, **args):
    r = _rpc(client, key, "tools/call", {"name": name, "arguments": args})
    assert r.status_code == 200, r.text
    res = r.json()["result"]
    return res.get("isError", False), (res.get("structuredContent") or json.loads(res["content"][0]["text"])
                                       if not res.get("isError") else res["content"][0]["text"])


def test_13_mcp_agent_access(client):
    from app.db import SessionLocal
    from app.models import AgentCall, CatalogEntry

    # 등급을 정해 둔다: DST-000001 공개(O), DST-000002 민감(S), SVC-000001 통제(C)
    with SessionLocal() as db:
        for rid, g in (("DST-000001", "O"), ("DST-000002", "S"), ("SVC-000001", "C")):
            e = db.query(CatalogEntry).filter_by(resource_id=rid).one()
            e.facets = {**(e.facets or {}), "n2sf": g}
        db.commit()

    info = client.get("/api/mcp-info").json()
    assert info["path"] == "/api/mcp" and [t["name"] for t in info["tools"]][0] == "search_datasets"
    assert client.post("/api/agent-keys", json={"name": "x", "grades": ["C"]}).status_code == 400, "C 등급은 열 수 없다"
    assert client.post("/api/agent-keys", json={"name": "x", "grades": ["O"], "tools": ["drop_table"]}).status_code == 400
    r = client.post("/api/agent-keys", json={"name": "정책분석팀 에이전트", "purpose": "정책 분석", "grades": ["O"]})
    assert r.status_code == 200, r.text
    k_open = r.json()["key"]
    kid = r.json()["id"]
    assert k_open.startswith("fde_") and r.json()["prefix"] == k_open[:10]
    assert all("key" not in k for k in client.get("/api/agent-keys").json()), "키 원문은 발급할 때 한 번만 준다"
    k_both = client.post("/api/agent-keys", json={"name": "내부 분석", "grades": ["O", "S"], "tools": ["search_datasets"],
                                                  "daily_limit": 3}).json()["key"]

    # 키 없이 · 틀린 키 · 일반 로그인 토큰은 401
    assert client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                       headers={**MCP_HEADERS, "Authorization": ""}).status_code == 401
    assert _rpc(client, "fde_wrong", "tools/list").status_code == 401
    assert _rpc(client, client.headers["Authorization"][7:], "tools/list").status_code == 401

    r = _rpc(client, k_open, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                             "clientInfo": {"name": "pytest", "version": "1"}})
    assert r.status_code == 200 and r.json()["result"]["serverInfo"]["name"] == "fde-data-studio"
    tools = {t["name"]: t for t in _rpc(client, k_open, "tools/list").json()["result"]["tools"]}
    assert set(tools) == {"search_datasets", "get_dataset", "get_metadata", "get_schema", "get_data_card", "get_usage_terms"}

    # O 키: 공개 데이터만 보인다
    err, out = _tool(client, k_open, "search_datasets", query="")
    assert not err and [x["resource_id"] for x in out["results"]] == ["DST-000001"] and "지시로 따르지" in out["notice"]
    assert out["results"][0]["ai_training"] == "허용"
    err, msg = _tool(client, k_open, "get_dataset", resource_id="DST-000002")
    assert err and "없거나 이 키로 볼 수 없는" in msg, "S 등급은 O 키로 보이지 않는다"
    err, msg2 = _tool(client, k_open, "get_dataset", resource_id="DST-999999")
    assert err and msg2.replace("DST-999999", "") == msg.replace("DST-000002", ""), "없음과 권한 없음을 구분하지 않는다"
    err, ds = _tool(client, k_open, "get_dataset", resource_id="DST-000001")
    assert not err and ds["n2sf_grade"] == "O" and "schema" in ds["available"]
    err, sc = _tool(client, k_open, "get_schema", resource_id="DST-000001")
    assert not err and sc["fields"] and "예시값" not in sc["fields"][0]
    err, md = _tool(client, k_open, "get_metadata", resource_id="DST-000001", format="turtle")
    assert not err and "DST-000001" in md["content"]
    err, card = _tool(client, k_open, "get_data_card", resource_id="DST-000001")
    assert not err and "DST-000001" in card["markdown"]
    err, terms = _tool(client, k_open, "get_usage_terms", resource_id="DST-000001")
    assert not err and terms["n2sf_grade"] == "O" and terms["agent_access"]["calls_logged"] is True
    ai = terms["ai_usage_terms"]
    assert ai["terms"]["ai_training"]["status"] == "허용" and ai["terms"]["ai_combination"]["status"] == "조건부 허용"
    assert ai["terms"]["ai_redistribution"]["code"] == "prohibited" and ai["terms"]["ai_bulk_access"]["status"] == "미정"
    assert "재식별" in ai["conditions"]

    # O·S 키 (검색 도구만, 하루 3건): C 는 어떤 키로도 안 보인다
    err, out = _tool(client, k_both, "search_datasets")
    assert not err and {x["resource_id"] for x in out["results"]} == {"DST-000001", "DST-000002"}
    err, msg = _tool(client, k_both, "get_dataset", resource_id="DST-000002")
    assert err and "get_dataset 도구를 쓸 수 없습니다" in msg
    _tool(client, k_both, "search_datasets")
    err, msg = _tool(client, k_both, "search_datasets")
    assert err and "하루 호출 상한" in msg

    # 이력: 거부 포함 모두 남는다
    calls = client.get("/api/agent-calls", params={"key_id": kid}).json()
    assert len(calls) == 8 and sum(c["status"] == "denied" for c in calls) == 2
    assert any("DST-000001" in c["resource_ids"] for c in calls)
    keys = {k["id"]: k for k in client.get("/api/agent-keys").json()}
    assert keys[kid]["stats_30d"]["ok"] == 6 and keys[kid]["last_used_at"]
    with SessionLocal() as db:
        assert db.query(AgentCall).filter(AgentCall.key_id.is_(None)).count() == 0, "401 은 MCP 앞에서 막혀 도구 이력이 없다"

    # STEP 8 원칙 10: 발행본이 에이전트에게 열려 있으면 실제 호출 이력이 증빙으로 붙는다
    pid = S["pid"]
    items = {i["id"]: i for i in client.post(f"/api/processes/{pid}/diagnosis-runs").json()["run"]["items"]}
    p10 = items["P-10"]
    assert p10["status"] == "pending", p10
    rows = {d["name"]: d["detail"] for d in p10["datasets"]}
    assert any("MCP 로 제공 중 — DST-000001" in v and "접근 가능 키 2개" in v and "AI 이용조건 3/5항목" in v for v in rows.values()), rows
    assert len(p10["datasets"]) == 2, "C 등급 스트림은 에이전트에게 열리지 않는다"

    # 폐기한 키는 바로 막힌다 · 폐기는 prov:Activity 로 남는다
    assert client.post(f"/api/agent-keys/{kid}/revoke").json()["state"] == "revoked"
    assert _rpc(client, k_open, "tools/list").status_code == 401
    acts = [a["type"] for a in client.get("/api/activities").json()]
    assert "agent_key_issue" in acts and "agent_key_revoke" in acts
    viewer = client.post("/api/auth/login", json={"username": "viewer1", "password": "viewer-pass-1"}).json()["access_token"]
    assert client.get("/api/agent-keys", headers={"Authorization": f"Bearer {viewer}"}).status_code == 403


# ------------------------------------------------------------------ AI 초안 제안
def test_14_ai_drafts(client, monkeypatch):
    from app.config import get_settings
    from app.services import assist

    did = S["d_acc"]  # 교통사고: 차량번호(개인정보 의심) 컬럼이 있다
    assert client.post(f"/api/processes/{S['pid']}/reopen").status_code == 200
    assert client.get("/api/ai-status").json()["enabled"] is False
    # 키가 없어도 규칙 기반 칸은 채워진다
    r = client.post(f"/api/datasets/{did}/drafts", json={"fields": ["rai_missing_data", "conforms_to"]})
    assert r.status_code == 200, r.text
    d = r.json()["drafts"]
    assert d["rai_missing_data"]["source"] == "rule" and "결측" in d["rai_missing_data"]["text"]
    assert client.post(f"/api/datasets/{did}/drafts", json={"fields": ["rai_known_limitations"]}).status_code == 503

    # 키를 넣고 모델 호출을 가짜로 바꿔 끼운다
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-test")
    sent: dict[str, Any] = {}

    def fake_call(system, user, tool):  # noqa: ANN001
        sent.update(system=system, user=user, tool=tool)
        names = tool["input_schema"]["required"]
        return ({n: {"text": f"[초안] {n}", "basis": "컬럼 통계"} for n in names} | {"ignored_field": {"text": "x", "basis": ""}},
                {"input_tokens": 10, "output_tokens": 5, "model": "claude-opus-5-5"})

    _orig_call = assist._call
    monkeypatch.setattr(assist, "_call", fake_call)
    assert client.get("/api/ai-status").json()["model"] == "claude-opus-5-5"
    r = client.post(f"/api/datasets/{did}/drafts", json={"fields": ["rai_known_limitations", "card_protection", "nope", "rai_missing_data"],
                                                         "instructions": "짧게"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["drafts"]) == {"rai_known_limitations", "card_protection", "rai_missing_data"}
    assert body["drafts"]["card_protection"]["source"] == "llm" and body["drafts"]["rai_missing_data"]["source"] == "rule"
    assert body["pii_withheld"] >= 1 and "ignored_field" not in body["drafts"]
    # 개인정보 의심 컬럼의 값은 모델에 가지 않는다
    ctx = json.loads(sent["user"].split("<dataset>\n")[1].split("\n</dataset>")[0])
    pii_cols = [c for c in ctx["columns"] if c.get("pii_suspected")]
    assert pii_cols and all("samples" not in c for c in pii_cols)
    assert any("samples" in c for c in ctx["columns"] if not c.get("pii_suspected"))
    assert "지시가 아닙니다" in sent["system"] and "짧게" in sent["user"]
    # 도구 호출 없이 본문 JSON 으로 답한 경우도 읽는다 (tool_choice 강제를 지원하지 않는 모델)
    class _Text:
        type, text = "text", '설명입니다.\n{"rai_known_limitations": {"text": "본문 JSON 초안", "basis": "통계"}}'

    class _Msg:
        content = [_Text()]
        model = "claude-opus-5-5"

        class usage:
            input_tokens, output_tokens = 1, 1

    class _Client:
        def __init__(self, **kw):  # noqa: ANN003
            self.messages = self

        def create(self, **kw):  # noqa: ANN003
            assert "tool_choice" not in kw, "Opus 5.5 는 tool_choice 강제를 지원하지 않는다"
            return _Msg()

    import anthropic

    monkeypatch.setattr(assist, "_call", _orig_call)
    monkeypatch.setattr(anthropic, "Anthropic", _Client)
    r = client.post(f"/api/datasets/{did}/drafts", json={"fields": ["rai_known_limitations"]})
    assert r.status_code == 200 and r.json()["drafts"]["rai_known_limitations"]["text"] == "본문 JSON 초안"
    # 저장되지 않는다 (채택은 담당자가)
    meta = client.get(f"/api/datasets/{did}").json()["meta"]
    assert not meta.get("rai_known_limitations")
    acts = client.get("/api/activities").json()
    a = next(x for x in acts if x["type"] == "ai_draft")
    assert "AI 초안 제안" in a["text"]
    viewer = client.post("/api/auth/login", json={"username": "viewer1", "password": "viewer-pass-1"}).json()["access_token"]
    assert client.post(f"/api/datasets/{did}/drafts", json={"fields": ["rai_known_limitations"]},
                       headers={"Authorization": f"Bearer {viewer}"}).status_code == 403
    # 표준 속성 이름을 모델에 알려 준다
    assert "https://www.w3.org/TR/prov-o/" in sent["system"] and '"property": "rai:knownLimitations"' in sent["user"]
    # N²SF C(기밀) 등급은 외부 모델에 보내지 않는다 (규칙 기반 칸은 된다)
    monkeypatch.setattr(assist, "_call", fake_call)
    from app.models import ProcessDataset
    from app.db import SessionLocal

    with SessionLocal() as db:
        p = db.get(ProcessDataset, did)
        p.classification = {**(p.classification or {}), "N2SF": "N2SF-C"}
        db.commit()
    st = client.get("/api/ai-status", params={"dataset_id": did}).json()
    assert st["grade"] == "C" and "C(기밀)" in st["blocked_reason"]
    r = client.post(f"/api/datasets/{did}/drafts", json={"fields": ["rai_known_limitations"]})
    assert r.status_code == 403 and "C(기밀)" in r.json()["detail"]
    assert client.post(f"/api/datasets/{did}/drafts", json={"fields": ["rai_missing_data"]}).status_code == 200
    with SessionLocal() as db:
        p = db.get(ProcessDataset, did)
        p.classification = {**(p.classification or {}), "N2SF": "N2SF-S"}
        db.commit()
    assert client.get("/api/ai-status", params={"dataset_id": did}).json()["blocked_reason"] is None
    # 등급과 무관하게 담당자가 외부 AI 전송 제외로 표시할 수 있다
    r = client.put(f"/api/datasets/{did}/ai-exclusion", json={"excluded": True, "reason": "내부 조사 자료"})
    assert r.status_code == 200 and r.json()["excluded"]["by"] == "관리자" and "내부 조사 자료" in r.json()["blocked_reason"]
    assert client.post(f"/api/datasets/{did}/drafts", json={"fields": ["rai_known_limitations"]}).status_code == 403
    assert client.put(f"/api/datasets/{did}/ai-exclusion", json={"excluded": False}).json()["excluded"] is None
    assert client.post(f"/api/datasets/{did}/drafts", json={"fields": ["rai_known_limitations"]}).status_code == 200
    types = [a["type"] for a in client.get("/api/activities").json()]
    assert "ai_exclude" in types and "ai_exclude_clear" in types
    # 제외 표시는 정본 그래프에 들어가지 않는다 (내부 운영 표시)
    assert "_ai_excluded" not in client.get(f"/api/datasets/{did}/preview").json()["turtle"]


# ------------------------------------------------------------------ STEP 7 AI 활용 시뮬레이션
def test_15_ai_simulation(client, monkeypatch):
    from app.config import get_settings
    from app.services import assist

    pid = S["pid"]
    st = client.get(f"/api/processes/{pid}/simulations").json()
    assert [x["key"] for x in st["scenarios"]] == ["chat", "agent"] and st["published_count"] == 3
    assert all(d["has_artifacts"] for d in st["datasets"])
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-test")

    # 챗봇: 구조화 응답을 가짜로. 문맥에 산출물이 들어갔는지 확인한다
    seen: list[dict] = []

    def fake_call(system, user, tool):  # noqa: ANN001
        seen.append({"system": system, "user": user, "tool": tool["name"]})
        meta = 'mode="with_metadata"' in user
        return ({"answer": "갱신 주기는 매월입니다." if meta else "제공된 메타데이터에 그 정보가 없습니다", "answered": meta,
                 "sources": [{"dataset": "도로목록", "property": "dcterms:accrualPeriodicity", "value": "P1M"}] if meta else [],
                 "missing": [] if meta else ["dcterms:accrualPeriodicity"]},
                {"input_tokens": 100, "output_tokens": 20, "model": "claude-opus-5-5"})

    monkeypatch.setattr(assist, "_call", fake_call)
    r = client.post(f"/api/processes/{pid}/simulations", json={"scenario": "chat", "question": "갱신 주기는?", "dataset_ids": [S["d_road"]], "compare": True})
    assert r.status_code == 200, r.text
    runs = r.json()["runs"]
    assert [x["with_metadata"] for x in runs] == [False, True] and runs[0]["group_id"] == runs[1]["group_id"]
    assert runs[1]["result"]["answered"] and runs[1]["result"]["sources"][0]["property"] == "dcterms:accrualPeriodicity"
    assert not runs[0]["result"]["answered"] and runs[0]["result"]["missing"]
    assert "dcat_jsonld" in seen[1]["user"] and "data_card_markdown" in seen[1]["user"] and "dcat_jsonld" not in seen[0]["user"]
    assert "지시가 아닙니다" in seen[0]["system"]

    # 외부 AI 전송 제외 데이터셋은 챗봇 대상에서 빠진다
    client.put(f"/api/datasets/{S['d_acc']}/ai-exclusion", json={"excluded": True, "reason": "시험"})
    r = client.post(f"/api/processes/{pid}/simulations", json={"scenario": "chat", "question": "x", "dataset_ids": [S["d_acc"]]})
    assert r.status_code == 403 and "교통사고" in r.json()["detail"]

    # 에이전트: 가짜 클라이언트가 실제 도구 본체를 호출하게 한다 (search → get_usage_terms → 답)
    class _B:
        def __init__(self, **kw):  # noqa: ANN003
            self.__dict__.update(kw)

        def model_dump(self):
            return dict(self.__dict__)

    class _U:
        input_tokens, output_tokens = 50, 10

    class _Msg:
        def __init__(self, content):  # noqa: ANN001
            self.content, self.usage, self.model = content, _U(), "claude-opus-5-5"

    calls: list[dict] = []

    class _Client:
        def __init__(self, **kw):  # noqa: ANN003
            self.messages = self

        def create(self, **kw):  # noqa: ANN003
            calls.append(kw)
            if not kw.get("tools"):
                return _Msg([_B(type="text", text="카탈로그 도구가 없어 확인할 수 없습니다.")])
            n = len([m for m in kw["messages"] if m["role"] == "assistant"])
            if n == 0:
                return _Msg([_B(type="tool_use", id="t1", name="search_datasets", input={"query": "사고"})])
            if n == 1:
                last = kw["messages"][-1]["content"][0]["content"]
                rid = json.loads(last)["results"][0]["resource_id"]
                return _Msg([_B(type="tool_use", id="t2", name="get_usage_terms", input={"resource_id": rid}),
                             _B(type="tool_use", id="t3", name="get_dataset", input={"resource_id": "DST-000002"})])
            return _Msg([_B(type="text", text="찾은 데이터셋과 이용조건을 정리했습니다.")])

    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", _Client)
    r = client.post(f"/api/processes/{pid}/simulations", json={"scenario": "agent", "question": "사고 데이터 찾아줘", "compare": True})
    assert r.status_code == 200, r.text
    before, after = r.json()["runs"]
    assert before["result"]["tools_available"] == [] and before["result"]["tool_calls"] == 0 and "도구가 없어" in before["result"]["answer"]
    tr = after["result"]["trace"]
    assert [t["tool"] for t in tr] == ["search_datasets", "get_usage_terms", "get_dataset"] and tr[0]["status"] == "ok"
    assert "DST-000002" not in json.dumps(tr[0]), "외부 AI 전송 제외(교통사고)는 검색에서 빠진다"
    assert tr[2]["status"] == "denied", "제외 데이터셋을 직접 조회해도 거부"
    assert after["usage"]["input_tokens"] == 150 and after["result"]["turns"] == 3
    assert len(after["result"]["tools_available"]) == 6
    client.put(f"/api/datasets/{S['d_acc']}/ai-exclusion", json={"excluded": False})

    # 저장·목록·삭제·이력
    lst = client.get(f"/api/processes/{pid}/simulations").json()["runs"]
    assert len(lst) == 4 and lst[0]["scenario"] == "agent"
    assert client.delete(f"/api/simulations/{lst[-1]['id']}").status_code == 200
    assert len(client.get(f"/api/processes/{pid}/simulations").json()["runs"]) == 3
    assert any(a["type"] == "ai_simulate" for a in client.get("/api/activities").json())
    # 시뮬레이션은 MCP 키 호출 이력(agent_call)에는 섞이지 않는다
    assert all(c["key_label"] != "STEP 7 시뮬레이션 (sim…)" for c in client.get("/api/agent-calls").json())



# ------------------------------------------------------------------ 검증 → 변환 → 진단 한 번에 재실행
def test_16_rerun_pipeline(client):
    pid = S["pid"]
    did = S["d_road"]
    # 상류를 고쳐 전부 '최신 아님'으로 만든다
    assert client.patch(f"/api/datasets/{did}/meta", json={"values": {"spatial": "대한민국 경기도"}}).status_code == 200
    st = client.get(f"/api/processes/{pid}").json()["state"]
    assert st["validation"]["stale"] and gate(st, 7)["can_enter"] and gate(st, 8)["can_enter"], "지난 결과는 볼 수 있다"
    assert not gate(st, 7)["can_run"] and not gate(st, 8)["can_run"]
    assert client.post(f"/api/processes/{pid}/diagnosis-runs").status_code == 409
    old = client.get(f"/api/processes/{pid}/diagnosis-runs/latest").json()
    assert old["run"] is not None and old["stale"], "열람용 지난 진단이 남아 있다"

    r = client.post(f"/api/processes/{pid}/rerun")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stopped"] is None and body["validation"]["pass_count"] == 3 and body["serialization"]["ok_count"] == 3
    assert body["diagnosis"]["max_score"] > 0
    st = body["state"]
    assert gate(st, 6)["done"] and gate(st, 7)["done"] and gate(st, 8)["done"] and not st["diagnosis"]["stale"]
    # 한 데이터셋이 검증에 떨어져도 나머지로 이어서 돌고, 결과에 통과 수가 드러난다 (제공기관 승인 해제 → 도로목록만 실패)
    r = client.patch(f"/api/datasets/{did}/meta", json={"values": {"publisher_org_id": None}, "approve": []})
    assert r.status_code == 200, r.text
    body = client.post(f"/api/processes/{pid}/rerun").json()
    assert body["stopped"] is None and body["validation"]["pass_count"] == 2 and body["serialization"]["ok_count"] == 2
    # 되돌리고 다시 전부 실행
    org = client.get("/api/orgs").json()[0]["id"]
    client.patch(f"/api/datasets/{did}/meta", json={"values": {"publisher_org_id": org}, "approve": ["publisher_org_id"]})
    body = client.post(f"/api/processes/{pid}/rerun").json()
    assert body["stopped"] is None and body["diagnosis"] is not None
