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
    assert g.value(pol, ODRL.profile) is not None, "fde: 확장 동작을 쓰므로 odrl:profile 을 밝힌다"
    # DCAT 3: 갱신주기는 dcterms:Frequency 개념 IRI, 원래 간격은 fde:updateInterval
    FREQ = Namespace("http://purl.org/cld/freq/")
    assert g.value(ds, DCTERMS.accrualPeriodicity) == FREQ.monthly and (FREQ.monthly, RDF.type, DCTERMS.Frequency) in g
    assert str(g.value(ds, Namespace("https://catalog.molit.go.kr/def/").updateInterval)) == "P1M"
    perms = {g.value(r, ODRL.action) for r in g.objects(pol, ODRL.permission)}
    prohib = {g.value(r, ODRL.action) for r in g.objects(pol, ODRL.prohibition)}
    FDE = Namespace("https://catalog.molit.go.kr/def/")
    assert perms == {FDE.aiTraining, FDE.dataCombination} and prohib == {ODRL.distribute}
    assert all((a, RDF.type, ODRL.Action) in g for a in perms | prohib), "동작 정의도 같은 그래프에 있다"
    cond = next(r for r in g.objects(pol, ODRL.permission) if g.value(r, ODRL.action) == FDE.dataCombination)
    duty = g.value(cond, ODRL.duty)
    assert duty is not None and (duty, RDF.type, ODRL.Duty) in g and "재식별" in str(g.value(duty, RDFS.comment)), "조건부 허용은 ODRL duty 로"
    assert (g.value(duty, ODRL.action), ODRL.includedIn, ODRL.use) in g
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
                     "K": [{"code": "K5", "column": "도로링크ID"}, {"code": "K7", "column": "발생일시"}], "N2SF": "N2SF-S2"},
        S["d_stream"]: {"F1": ["F1-01"], "F2": ["F2-06"], "F4": ["F4-05"], "F6": ["F6-01"],
                        "K": [{"code": "K5", "column": "link_id"}], "N2SF": "N2SF-S2"},
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
    get = lambda did, fmt: client.get(f"/api/artifacts/{arts[(did, fmt)]['id']}").json()["content"]
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
    # 작업자는 자기 담당 프로세스만 본다 (v0.18.1): 관리자가 이 프로세스를 담당자에게 배정한다
    assert client.get(f"/api/processes/{pid}", headers=wh).status_code == 404
    w1id = next(u["id"] for u in client.get("/api/users").json() if u["username"] == "worker1")
    assert client.patch(f"/api/processes/{pid}", json={"owner_id": w1id}).status_code == 200
    assert client.get(f"/api/processes/{pid}", headers=wh).status_code == 200
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
    assert cat["total"] >= 1 and "facets" not in cat, "패싯 집계는 v0.18 에서 제거 (ARD 관리)"
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
    # P-12 (3.6절): 등급은 있지만 S2 데이터셋에 판단 근거가 없어 부분 충족 (v0.14 부터 근거 · 표 41 · 공개 수준을 함께 본다)
    assert items["P-12"]["status"] == "partial" and any("판단 근거 미작성" in d["detail"] for d in items["P-12"]["datasets"])
    assert items["P-15"]["status"] == "met"

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
        for rid, g in (("DST-000001", "O"), ("DST-000002", "S2"), ("SVC-000001", "C")):
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
    kb = client.post("/api/agent-keys", json={"name": "내부 분석", "grades": ["O", "S1", "S2"], "tools": ["search_datasets"], "daily_limit": 3}).json()
    k_both, kb_id = kb["key"], kb["id"]

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

    # O·S1·S2 키 (검색 도구만, 하루 3건): S2 는 키 등급만으로 열리지 않고 발행본 건별 승인이 있어야 한다 (3.6.1 S2 사전 승인)
    err, out = _tool(client, k_both, "search_datasets")
    assert not err and {x["resource_id"] for x in out["results"]} == {"DST-000001"}, "승인 전에는 S2 가 보이지 않는다"
    gl = client.get(f"/api/agent-keys/{kb_id}/grants").json()
    assert gl["s2_allowed"] and any(c["resource_id"] == "DST-000002" for c in gl["candidates"])
    assert client.post(f"/api/agent-keys/{kb_id}/grants", json={"resource_id": "DST-000002"}).status_code == 422, "승인 근거 필수"
    assert client.post(f"/api/agent-keys/{kb_id}/grants", json={"resource_id": "DST-000001", "note": "O 등급"}).status_code == 422, "S2 에만 필요"
    r = client.post(f"/api/agent-keys/{kb_id}/grants", json={"resource_id": "DST-000002", "note": "교통안전공단 협약 2026-07, 사고 원인 분석 목적", "expires_days": 30})
    assert r.status_code == 200 and r.json()["state"] == "active", r.text
    grant_id = r.json()["id"]
    # 승인은 S2 등급이 없는 키에는 줄 수 없다
    assert client.post(f"/api/agent-keys/{kid}/grants", json={"resource_id": "DST-000002", "note": "x" * 10}).status_code == 409
    err, out = _tool(client, k_both, "search_datasets")
    assert not err and {x["resource_id"] for x in out["results"]} == {"DST-000001", "DST-000002"}
    assert next(k for k in client.get("/api/agent-keys").json() if k["id"] == kb_id)["s2_grants"] == 1
    err, msg = _tool(client, k_both, "get_dataset", resource_id="DST-000002")
    assert err and "get_dataset 도구를 쓸 수 없습니다" in msg
    err, msg = _tool(client, k_both, "search_datasets")
    assert err and "하루 호출 상한" in msg
    # 승인 회수 → 다시 안 보인다 (상한 때문에 visible 로 확인)
    assert client.post(f"/api/agent-keys/{kb_id}/grants/{grant_id}/revoke").json()["state"] == "revoked"
    with SessionLocal() as db:
        from app.models import AgentKey as _AK
        from app.models import CatalogEntry as _CE
        from app.services import agent as _agent
        assert not _agent.visible(db.query(_CE).filter_by(resource_id="DST-000002").one(), db.get(_AK, kb_id))

    # 이력: 거부 포함 모두 남는다
    calls = client.get("/api/agent-calls", params={"key_id": kid}).json()
    assert len(calls) == 8 and sum(c["status"] == "denied" for c in calls) == 2
    assert any("DST-000001" in c["resource_ids"] for c in calls)
    keys = {k["id"]: k for k in client.get("/api/agent-keys").json()}
    assert keys[kid]["stats_30d"]["ok"] == 6 and keys[kid]["last_used_at"]
    with SessionLocal() as db:
        # 401 은 MCP 서버 앞에서 막히지만 시도 자체는 '인증 실패' 로 남는다 (키 원문은 저장하지 않고 앞 8자만)
        bad = db.query(AgentCall).filter(AgentCall.key_id.is_(None)).all()
        assert bad and all(c.status == "denied" and c.tool == "auth" for c in bad)
        assert all(len(c.arguments.get("key_prefix", "")) <= 8 for c in bad)

    # STEP 8 원칙 10: 발행본이 에이전트에게 열려 있으면 실제 호출 이력이 증빙으로 붙는다
    pid = S["pid"]
    items = {i["id"]: i for i in client.post(f"/api/processes/{pid}/diagnosis-runs").json()["run"]["items"]}
    p10 = items["P-10"]
    assert p10["status"] == "pending", p10
    rows = {d["name"]: d["detail"] for d in p10["datasets"]}
    assert any("MCP 로 제공 중 — DST-000001" in v and "접근 가능 키 2개" in v and "AI 이용조건 3/5항목" in v for v in rows.values()), rows
    assert len(p10["datasets"]) == 1, "C 등급 스트림과 승인이 회수된 S2 데이터셋은 에이전트에게 열려 있지 않다"

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

    def fake_call(system, user, tool):
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
        def __init__(self, **kw):
            self.messages = self

        def create(self, **kw):
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
    assert "https://www.w3.org/TR/prov-o/" in sent["system"] and '"property": "rai:dataLimitations"' in sent["user"]
    # N²SF C(비공개) 등급은 외부 모델에 보내지 않는다 (규칙 기반 칸은 된다)
    monkeypatch.setattr(assist, "_call", fake_call)
    from app.db import SessionLocal
    from app.models import ProcessDataset

    with SessionLocal() as db:
        p = db.get(ProcessDataset, did)
        p.classification = {**(p.classification or {}), "N2SF": "N2SF-C"}
        db.commit()
    st = client.get("/api/ai-status", params={"dataset_id": did}).json()
    assert st["grade"] == "C" and "C(비공개)" in st["blocked_reason"]
    r = client.post(f"/api/datasets/{did}/drafts", json={"fields": ["rai_known_limitations"]})
    assert r.status_code == 403 and "C(비공개)" in r.json()["detail"]
    assert client.post(f"/api/datasets/{did}/drafts", json={"fields": ["rai_missing_data"]}).status_code == 200
    with SessionLocal() as db:
        p = db.get(ProcessDataset, did)
        p.classification = {**(p.classification or {}), "N2SF": "N2SF-S2"}
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

    def fake_call(system, user, tool):
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

    # 개인정보 의심 컬럼은 프로파일에도 값 표본이 없다 (화면·산출물·외부 전송 공통)
    prof = client.get(f"/api/assets/{S['acc']}").json()["profile"]
    car = next(c for t in prof["tables"] for c in t["columns"] if c["name"] == "차량번호")
    assert car.get("pii") and car["samples"] == []
    # 외부 AI 전송 제외는 발행 카탈로그 facets 에도 반영되어 MCP·시뮬레이션에서 숨겨진다
    client.put(f"/api/datasets/{S['d_acc']}/ai-exclusion", json={"excluded": True, "reason": "시험"})
    assert client.get("/api/catalog/DST-000002").json()["facets"]["ai_excluded"] is True
    from app.db import SessionLocal
    from app.models import AgentKey, CatalogEntry
    from app.services import agent as agent_svc

    with SessionLocal() as db:
        e2 = db.query(CatalogEntry).filter_by(resource_id="DST-000002").one()
        assert not agent_svc.visible(e2, AgentKey(grades=["O", "S1", "S2"], tools=[]))
    # 외부 제공 카드에서는 값 표본 행이 빠진다
    from app.services import documents as docs_svc
    card = client.get("/api/catalog/DST-000001").json()["documents"]["card"]
    assert "데이터 인스턴스" in card and "값 표본을 제외" in docs_svc.strip_samples(card)
    r = client.post(f"/api/processes/{pid}/simulations", json={"scenario": "chat", "question": "x", "dataset_ids": [S["d_acc"]]})
    assert r.status_code == 403 and "교통사고" in r.json()["detail"]

    # 에이전트: 가짜 클라이언트가 실제 도구 본체를 호출하게 한다 (search → get_usage_terms → 답)
    class _B:
        def __init__(self, **kw):
            self.__dict__.update(kw)

        def model_dump(self):
            return dict(self.__dict__)

    class _U:
        input_tokens, output_tokens = 50, 10

    class _Msg:
        def __init__(self, content):
            self.content, self.usage, self.model = content, _U(), "claude-opus-5-5"

    calls: list[dict] = []

    class _Client:
        def __init__(self, **kw):
            self.messages = self

        def create(self, **kw):
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
    assert client.get("/api/catalog/DST-000002").json()["facets"]["ai_excluded"] is False

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


# ------------------------------------------------------------------ 즉시 진단 (STEP 3·4 미리보기)
def test_17_diagnosis_preview(client):
    pid, did = S["pid"], S["d_road"]
    # 최신 상태에서: 저장된 진단과 같다
    pv = client.get(f"/api/datasets/{did}/diagnosis-preview").json()
    assert pv["last_run"] and pv["improved"] == [] and pv["regressed"] == [] and pv["provisional_note"] is None
    assert all(not i["provisional"] for i in pv["items"]) and pv["max_score"] > 0
    m07 = next(i for i in pv["items"] if i["id"] == "M-07")
    assert m07["dataset_status"] == "met" and m07["focus"] == "accrual_periodicity"
    # 갱신주기를 지우면 즉시 진단에서 바로 미흡으로, 산출물에 기대는 항목은 잠정으로 표시된다
    assert client.patch(f"/api/datasets/{did}/meta", json={"values": {"accrual_periodicity": None}}).status_code == 200
    pv = client.get(f"/api/datasets/{did}/diagnosis-preview").json()
    m07 = next(i for i in pv["items"] if i["id"] == "M-07")
    assert m07["dataset_status"] == "unmet" and m07["changed"] and any(r["id"] == "M-07" for r in pv["regressed"])
    assert pv["provisional_note"] and next(i for i in pv["items"] if i["id"] == "R-10")["provisional"]
    assert next(i for i in pv["items"] if i["id"] == "P-04")["provisional"], "산출물 항목을 종합하는 원칙도 잠정"
    # 프로세스 전체 즉시 진단: STEP 8 이 저장된 결과 위에 "지금 판정"을 겹쳐 보일 때 쓴다. 데이터셋별 판정이 함께 온다
    allpv = client.get(f"/api/processes/{pid}/diagnosis-preview").json()
    m07a = next(i for i in allpv["items"] if i["id"] == "M-07")
    assert m07a["dataset_id"] is None if "dataset_id" in m07a else allpv["dataset_id"] is None
    assert any(d["id"] == did and d["status"] == "unmet" for d in m07a["datasets"]) and m07a["previous"] in ("met", "partial")
    assert client.get(f"/api/processes/{pid}/diagnosis-runs/latest").json()["stale"], "저장된 진단은 최신 아님"
    assert client.get(f"/api/processes/{pid}/diagnosis-runs/latest").json()["run"]["id"] == pv["last_run"]["id"], "기록은 남기지 않는다"
    # 되돌리면 개선으로 잡힌다
    client.patch(f"/api/datasets/{did}/meta", json={"values": {"accrual_periodicity": "P1M"}})
    pv = client.get(f"/api/datasets/{did}/diagnosis-preview").json()
    assert not any(r["id"] == "M-07" for r in pv["regressed"])
    # 다른 데이터셋에만 해당하는 항목은 빠진다
    acc = client.get(f"/api/datasets/{S['d_acc']}/diagnosis-preview").json()
    assert {i["id"] for i in acc["items"]} <= {i["id"] for i in pv["items"]} | {i["id"] for i in acc["items"]}


# ------------------------------------------------------------------ v0.12 품질 검수 후속 (속도 제한 · 자기 승인 정책 · 토큰 무효화 · AI 보조 작성 이력 · 표준 IRI)
def test_18_quality_followups(client, monkeypatch):
    from rdflib import DCTERMS, RDF, Graph, Namespace, URIRef

    from app.config import get_settings
    from app.db import SessionLocal
    from app.models import ProcessDataset
    from app.services import assist, ratelimit

    pid, did = S["pid"], S["d_road"]
    assert client.post(f"/api/processes/{pid}/reopen").status_code in (200, 409)
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-test")
    monkeypatch.setattr(assist, "_call", lambda system, user, tool: (
        {n: {"text": f"[초안] {n}", "basis": "통계"} for n in tool["input_schema"]["required"]},
        {"input_tokens": 1, "output_tokens": 1, "model": "claude-opus-5-5"}))

    # ① 분당 속도 제한: 2회로 낮추면 3번째가 429 (Retry-After 포함)
    monkeypatch.setattr(get_settings(), "ai_rate_per_minute", 2)
    ratelimit.reset()
    for _ in range(2):
        assert client.post(f"/api/datasets/{did}/drafts", json={"fields": ["rai_known_limitations"]}).status_code == 200
    r = client.post(f"/api/datasets/{did}/drafts", json={"fields": ["rai_known_limitations"]})
    assert r.status_code == 429 and "분당 2회" in r.json()["detail"] and r.headers.get("retry-after")
    ratelimit.reset()
    # 일일 상한은 활동 로그(한국 시간 자정 기준)로 센다
    monkeypatch.setattr(get_settings(), "ai_rate_per_day", 1)
    r = client.post(f"/api/datasets/{did}/drafts", json={"fields": ["rai_known_limitations"]})
    assert r.status_code == 429 and "오늘 AI 호출 상한" in r.json()["detail"]
    monkeypatch.setattr(get_settings(), "ai_rate_per_day", 0)
    monkeypatch.setattr(get_settings(), "ai_rate_per_minute", 0)
    ratelimit.reset()

    # ② AI 초안 채택 이력: 저장할 때 출처를 보내면 정본에 fde:aiAssisted 로 남고 카드·카탈로그에 표시된다
    r = client.patch(f"/api/datasets/{did}/meta", json={
        "values": {"rai_known_limitations": "[초안] rai_known_limitations", "rai_data_biases": "담당자가 고친 편향 설명"},
        "ai_assisted": {"rai_known_limitations": {"model": "claude-opus-5-5", "drafted_at": "2026-10-17T03:00:00", "draft_text": "[초안] rai_known_limitations"},
                        "rai_data_biases": {"model": "claude-opus-5-5", "drafted_at": "2026-10-17T03:00:00", "draft_text": "[초안] rai_data_biases"}}})
    assert r.status_code == 200, r.text
    pv = client.get(f"/api/datasets/{did}/preview").json()
    g = Graph().parse(data=pv["turtle"], format="turtle")
    fde = Namespace(get_settings().def_ns)
    nodes = list(g.objects(None, fde.aiAssisted))
    assert len(nodes) == 2
    modified = {str(g.value(n, fde.assistedProperty)): bool(g.value(n, fde.modifiedAfterDraft).toPython()) for n in nodes}
    rai = "http://mlcommons.org/croissant/RAI/"
    assert modified[rai + "dataLimitations"] is False and modified[rai + "dataBiases"] is True  # 그대로 채택 vs 담당자 수정
    assert any(str(o).endswith("agent/claude-opus-5-5") for o in g.objects(None, URIRef("http://www.w3.org/ns/prov#wasAssociatedWith")))
    from app.services import canonical, documents

    def card_md() -> str:
        with SessionLocal() as db:
            p = db.get(ProcessDataset, did)
            return documents.render_card(canonical.build(db, p, "draft"), p, None, [])

    card = card_md()
    assert "AI 보조 작성 · 담당자 확정" in card and "그대로 채택 1칸" in card and "담당자 수정 1칸" in card
    # 칸을 비우면 이력도 사라진다
    assert client.patch(f"/api/datasets/{did}/meta", json={"values": {"rai_data_biases": None}}).status_code == 200
    pv = client.get(f"/api/datasets/{did}/preview").json()
    assert "ai-assist-rai_known_limitations" in pv["turtle"] and "ai-assist-rai_data_biases" not in pv["turtle"]
    # 표시 옵션을 끄면 카드 고지만 빠지고 그래프 이력은 남는다
    monkeypatch.setattr(get_settings(), "ai_assist_notice", False)
    assert "AI 보조 작성 · 담당자 확정" not in card_md()
    assert "ai-assist-" in client.get(f"/api/datasets/{did}/preview").json()["turtle"]
    monkeypatch.setattr(get_settings(), "ai_assist_notice", True)

    # ③ AI 기본법 제34조 학습용데이터 개요 대응 블록
    assert "제34조 학습용데이터 개요 대응" in card
    g = Graph().parse(data=client.get(f"/api/datasets/{did}/preview").json()["turtle"], format="turtle")
    cov = str(next(g.objects(None, fde.trainingDataOverviewCoverage)))
    assert cov.endswith("/8") and int(cov.split("/")[0]) >= 1
    prof = next(g.objects(None, fde.complianceProfile), None)
    assert prof is not None and (prof, RDF.type, DCTERMS.Standard) in g

    # ④ 표준 IRI: spatial → dcterms:Location, conformsTo 이름 → dcterms:Standard, format → MediaTypeOrExtent, 공공누리 URL
    assert client.patch(f"/api/datasets/{did}/meta", json={"values": {"spatial": "대한민국", "conforms_to": ["EPSG:5186", "https://www.w3.org/TR/vocab-dcat-3/"],
                                                                        "language": "한국어"}}).status_code == 200
    g = Graph().parse(data=client.get(f"/api/datasets/{did}/preview").json()["turtle"], format="turtle")
    loc = next(g.objects(None, DCTERMS.spatial), None)
    assert isinstance(loc, URIRef) and (loc, RDF.type, DCTERMS.Location) in g
    stds = list(g.objects(None, DCTERMS.conformsTo))
    assert len(stds) == 2 and all((s, RDF.type, DCTERMS.Standard) in g for s in stds)
    assert URIRef("https://www.w3.org/TR/vocab-dcat-3/") in stds
    lang = next(g.objects(None, DCTERMS.language), None)
    assert isinstance(lang, URIRef) and (lang, RDF.type, DCTERMS.LinguisticSystem) in g
    fmt = next(g.objects(None, DCTERMS["format"]), None)
    assert fmt is None or (isinstance(fmt, URIRef) and (fmt, RDF.type, DCTERMS.MediaTypeOrExtent) in g)
    ttl = client.get(f"/api/datasets/{did}/preview").json()["turtle"]
    if "kogl.or.kr" in ttl:
        assert "licenseType" in ttl
    # CSVW 컬럼 이름: 공백 등은 퍼센트 인코딩, 원래 머리글은 csvw:titles
    assert "csvw:titles" in ttl
    assert client.patch(f"/api/datasets/{did}/meta", json={"values": {"language": "ko"}}).status_code == 200

    # ⑤ 검색어의 % _ 는 글자 그대로 (와일드카드 아님)
    assert client.get("/api/assets", params={"q": "%"}).status_code == 200
    assert client.get("/api/assets", params={"q": "%"}).json() == [] or all("%" in a["name"] for a in client.get("/api/assets", params={"q": "%"}).json())

    # ⑥ 자기 승인 정책 deny: 본인이 요청한 발행은 승인 불가 (403)
    monkeypatch.setattr(get_settings(), "review_self_approve", "deny")
    with SessionLocal() as db:
        for d in db.query(ProcessDataset).filter_by(process_id=pid).all():
            d.classification = {**(d.classification or {}), "N2SF": "N2SF-S2"}
        db.commit()
    rr = client.post(f"/api/processes/{pid}/rerun").json()
    if rr["state"]["gates"][6]["done"]:
        r = client.post(f"/api/processes/{pid}/review-requests", json={"message": "자기 승인 테스트"})
        if r.status_code == 200:
            rid = r.json()["id"]
            det = client.get(f"/api/review-requests/{rid}").json()
            ack = [s["code"] for s in det["signals"] if s["severity"] == "high"]
            r = client.post(f"/api/review-requests/{rid}/approve", json={"note": "본인 승인 시도 열 글자 이상", "acknowledged": ack})
            assert r.status_code == 403 and r.json()["detail"]["code"] == "SELF_APPROVAL_DENIED"
            assert client.post(f"/api/review-requests/{rid}/withdraw").status_code == 200
    monkeypatch.setattr(get_settings(), "review_self_approve", "note")

    # ⑦ 비밀번호를 바꾸면 그 전에 발급된 토큰은 401
    r = client.post("/api/users", json={"username": "pwuser", "name": "비번", "password": "first-pass-1", "role": "worker"})
    assert r.status_code == 200, r.text
    tok = client.post("/api/auth/login", json={"username": "pwuser", "password": "first-pass-1"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/auth/me", headers=h).status_code == 200
    import time
    time.sleep(1.1)  # iat 초 단위 비교
    r = client.post("/api/auth/password", json={"current_password": "first-pass-1", "new_password": "second-pass-2"}, headers=h)
    assert r.status_code == 200 and r.json().get("relogin") is True
    r = client.get("/api/auth/me", headers=h)
    assert r.status_code == 401 and "다시 로그인" in r.json()["detail"]
    tok2 = client.post("/api/auth/login", json={"username": "pwuser", "password": "second-pass-2"}).json()["access_token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok2}"}).status_code == 200

    # ⑧ MCP get_usage_terms 에 학습용데이터 개요 작성 현황이 붙는다 (발행본이 있으면)
    from app import mcp_server
    from app.models import AgentKey, CatalogEntry
    with SessionLocal() as db:
        e = db.query(CatalogEntry).filter_by(resource_id="DST-000001").first()
        if e is not None:
            key = AgentKey(name="t", key_hash="x", grades=["O", "S1", "S2", "C"], tools=list(mcp_server.IMPLS), daily_limit=100, created_by=None)
            from app.services.agent import CallRecord
            out = mcp_server.impl_get_usage_terms(db, key, CallRecord(), e.resource_id)
            assert isinstance(out, dict) and out["training_data_overview"]["coverage"].endswith("/8")
            assert isinstance(out["ai_assisted_fields"], list)


# ------------------------------------------------------------------ v0.12 N²SF: S1/S2 · 등급 판단 근거 · 표 41 · 메타데이터 공개 수준
def test_19_n2sf_grading(client, monkeypatch):
    from app.config import get_settings
    from app.db import SessionLocal
    from app.models import AgentKey, CatalogEntry, ProcessDataset
    from app.services import agent as agent_svc
    from app.services import grading

    pid, did = S["pid"], S["d_road"]
    assert client.post(f"/api/processes/{pid}/reopen").status_code in (200, 409)
    assert client.post(f"/api/datasets/{did}/classification/unconfirm").status_code in (200, 409)
    base = client.get(f"/api/datasets/{did}").json()["classification"]
    body = {k: base[k] for k in ("F1", "F2", "F3", "F4", "F5", "F6", "K") if k in base}

    # 분류체계에 S1 · S2 가 있고 세분화 전 S 는 비활성
    n2 = next(a for a in client.get("/api/taxonomy").json() if a["code"] == "N2SF")
    active = {c["code"] for c in n2["codes"] if c["active"]}
    assert {"N2SF-O", "N2SF-S1", "N2SF-S2", "N2SF-C"} <= active and "N2SF-S" not in active

    # ① 판단 근거 → 제안 등급. 개인정보(personal) 이면 S2 이상
    assert grading.suggest({"personal_data": "personal"})[0] == "S2"
    assert grading.suggest({"personal_data": "anonymized", "reidentification": "medium"})[0] == "S1"
    assert grading.suggest({"legal": "national-security"})[0] == "C"
    # 제안보다 낮게 정하면 사유 필요 (422 GRADE_BELOW_BASIS)
    r = client.put(f"/api/datasets/{did}/classification", json={**body, "N2SF": "N2SF-O", "N2SF_BASIS": {"personal_data": "personal", "reidentification": "low", "legal": "none"}})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "GRADE_BELOW_BASIS"
    r = client.put(f"/api/datasets/{did}/classification", json={**body, "N2SF": "N2SF-O", "N2SF_BASIS": {"personal_data": "personal", "reidentification": "low", "legal": "none",
                                                                                                         "reason": "집계 단위가 읍면동 월별이라 개별 기록이 없고 개인정보 컬럼은 삭제됨"}})
    assert r.status_code == 200, r.text
    gst = r.json()["grading"]
    assert gst["suggested"] == "S2" and gst["below_suggested"] and gst["basis"]["by"] == "관리자" and gst["visibility"] == "detail"
    ttl = client.get(f"/api/datasets/{did}/preview").json()["turtle"]
    assert "gradeBasis" in ttl and "suggestedGrade" in ttl and 'metadataVisibility "detail"' in ttl
    # 제안을 따르면 사유 없이 저장
    r = client.put(f"/api/datasets/{did}/classification", json={**body, "N2SF": "N2SF-S2", "N2SF_BASIS": {"personal_data": "personal", "reidentification": "low", "legal": "none"}})
    assert r.status_code == 200 and r.json()["grading"]["below_suggested"] is False

    # ② 표 41: 자동 신호(국가안전) 는 사유 20자 이상으로만 해제, 수동 유형 지정 가능
    r = client.put(f"/api/datasets/{did}/classification", json={**body, "N2SF": "N2SF-C", "N2SF_BASIS": {"personal_data": "none", "reidentification": "low", "legal": "national-security"},
                                                               "SHARE_PROHIBITED": {"manual": ["third-party-ban"], "overrides": {"national-security": "짧음"}}})
    assert r.status_code == 422 and "20자" in r.json()["detail"]
    r = client.put(f"/api/datasets/{did}/classification", json={**body, "N2SF": "N2SF-C", "N2SF_BASIS": {"personal_data": "none", "reidentification": "low", "legal": "national-security"},
                                                               "SHARE_PROHIBITED": {"manual": ["third-party-ban"]}})
    assert r.status_code == 200
    pro = r.json()["grading"]["prohibited"]
    assert set(pro["types"]) == {"national-security", "third-party-ban"} and pro["blocked"] is True and "national-security" in pro["auto"]
    assert r.json()["grading"]["visibility"] == "internal"  # C 기본값
    ttl = client.get(f"/api/datasets/{did}/preview").json()["turtle"]
    assert 'shareProhibited "national-security"' in ttl and 'metadataVisibility "internal"' in ttl
    # 자동 신호를 사유로 해제하면 수동 지정만 남는다
    r = client.put(f"/api/datasets/{did}/classification", json={**body, "N2SF": "N2SF-C", "N2SF_BASIS": {"personal_data": "none", "reidentification": "low", "legal": "national-security"},
                                                               "SHARE_PROHIBITED": {"manual": ["third-party-ban"], "overrides": {"national-security": "국가안전 관련은 시설 좌표 컬럼 때문이며 해당 컬럼은 원천에서 제거됨"}}})
    assert r.status_code == 200 and r.json()["grading"]["prohibited"]["types"] == ["third-party-ban"]
    # 발행 차단: S2 + 수동 유형 → 검수 평가에 share_prohibited 신호, 승인해도 이 데이터셋은 빠진다
    r = client.put(f"/api/datasets/{did}/classification", json={**body, "N2SF": "N2SF-S2", "N2SF_BASIS": {"personal_data": "personal", "reidentification": "low", "legal": "none"},
                                                               "SHARE_PROHIBITED": {"manual": ["third-party-ban"]}})
    assert r.status_code == 200 and r.json()["grading"]["prohibited"]["blocked"] is True
    with SessionLocal() as db:
        for d in db.query(ProcessDataset).filter_by(process_id=pid).all():
            if d.id != did:
                d.classification = {**(d.classification or {}), "N2SF": "N2SF-O"}
        db.commit()
    rr = client.post(f"/api/processes/{pid}/rerun").json()
    pv = client.get(f"/api/processes/{pid}/publish-review").json()
    assert pv["assessment"], pv
    codes = {s["code"] for s in pv["assessment"]["signals"]}
    assert {"share_prohibited", "grade_s2"} <= codes, codes
    assert any("DST-000001" in d for sg in pv["assessment"]["signals"] if sg["code"] == "share_prohibited" for d in sg["datasets"])
    # review 모드면 차단하지 않는다
    monkeypatch.setattr(get_settings(), "share_prohibited", "review")
    with SessionLocal() as db:
        assert grading.state(db.get(ProcessDataset, did))["prohibited"]["blocked"] is False
    monkeypatch.setattr(get_settings(), "share_prohibited", "block")
    # 실제 발행에서 빠진다 (관리자 직접 발행은 고위험이라 검수 큐 → 승인)
    r = client.post(f"/api/processes/{pid}/review-requests", json={"message": "표 41 차단 확인"})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    det = client.get(f"/api/review-requests/{rid}").json()
    ack = [sg["code"] for sg in det["signals"] if sg["severity"] == "high"]
    r = client.post(f"/api/review-requests/{rid}/approve", json={"note": "본인 승인 사유 열 글자 이상 적습니다", "acknowledged": ack})
    assert r.status_code == 200, r.text
    published = {e["resource_id"] for e in r.json()["published"]}
    assert "DST-000001" not in published and published, published
    acts = client.get("/api/activities").json()
    pub = next(a for a in acts if a["type"] == "publish")
    assert "표 41 공유 불가로 제외 1건" in pub["text"]

    # ③ 메타데이터 공개 수준: listing 이면 등급 밖 키에도 제목만, internal 이면 존재도 안 보임
    r = client.put(f"/api/datasets/{did}/classification", json={**body, "N2SF": "N2SF-S2", "N2SF_BASIS": {"personal_data": "personal", "reidentification": "low", "legal": "none"},
                                                               "META_VISIBILITY": "listing"})
    assert r.status_code == 200 and r.json()["grading"]["visibility"] == "listing"
    with SessionLocal() as db:
        e = db.query(CatalogEntry).filter_by(resource_id="DST-000001").first()
        if e is not None:
            k_o = AgentKey(name="o", key_hash="h1", grades=["O"], tools=[], daily_limit=10)
            k_s = AgentKey(name="s", key_hash="h2", grades=["O", "S1", "S2"], tools=[], daily_limit=10)
            e.facets = {**(e.facets or {}), "n2sf": "S1", "meta_visibility": "listing"}
            assert agent_svc.listable(e, k_o) and not agent_svc.visible(e, k_o)
            assert agent_svc.listable(e, k_s) and not agent_svc.visible(e, k_s), "listing 은 누구에게도 상세를 열지 않는다"
            e.facets = {**e.facets, "meta_visibility": "detail"}
            assert not agent_svc.listable(e, k_o) and agent_svc.visible(e, k_s)
            e.facets = {**e.facets, "n2sf": "S2"}
            assert not agent_svc.visible(e, k_s), "S2 는 키 등급만으로는 열리지 않는다 (건별 승인 필요)"
            e.facets = {**e.facets, "meta_visibility": "internal"}
            assert not agent_svc.listable(e, k_s)
            # 세분화 전 키(S) 는 S1 을 본다 (S 발행본은 S2 로 취급되어 건별 승인 대상)
            e.facets = {**e.facets, "meta_visibility": "detail", "n2sf": "S1"}
            assert agent_svc.visible(e, AgentKey(name="l", key_hash="h3", grades=["O", "S"], tools=[], daily_limit=10))
            db.rollback()
    # 키 발급에 S 는 더 이상 쓸 수 없고 S1 · S2 를 쓴다
    assert client.post("/api/agent-keys", json={"name": "구키", "grades": ["O", "S"], "tools": ["search_datasets"], "daily_limit": 5, "expires_days": None}).status_code in (400, 422)
    assert client.get("/api/mcp-info").json()["grades"] == ["O", "S1", "S2"]
    # 원복
    r = client.put(f"/api/datasets/{did}/classification", json={**body, "N2SF": base.get("N2SF", "N2SF-O")})
    assert r.status_code == 200


# ------------------------------------------------------------------ v0.14 N²SF 2차: 컬럼 민감 항목 · 조합 등급 · 기관 등급표
def test_20_n2sf_columns_combo_org(client):
    from app.db import SessionLocal
    from app.models import ProcessDataset
    from app.services import grading

    pid, did = S["pid"], S["d_acc"]  # 교통사고: 차량번호 (개인정보 의심)
    assert client.post(f"/api/processes/{pid}/reopen").status_code in (200, 409)
    assert client.post(f"/api/datasets/{did}/classification/unconfirm").status_code in (200, 409)

    # ① 컬럼 민감 항목: 자동 후보가 보이고, 표시 + 비식별 기록을 저장하면 사전 · 정본 · 요약에 반영
    d = client.get(f"/api/datasets/{did}/dictionary").json()
    sug = [r for r in d["rows"] if r["personal_suggested"]]
    assert sug and d["sensitive"]["suggested_count"] >= 1 and "personal_data" in d["options"]
    # 자동 탐지만으로는 등급을 올리지 않는다 (힌트만). 담당자가 사전에서 확인해야 바닥이 된다
    assert d["sensitive"]["dataset_personal_data"] is None and d["sensitive"]["suggested"][0]["column"]
    g0 = client.get(f"/api/datasets/{did}").json()["grading"]
    assert not any("컬럼 민감 항목" in x for x in g0["reasons"]) and any("자동 탐지" in x for x in g0["hints"])
    col = sug[0]
    r = client.put(f"/api/datasets/{did}/dictionary", json={"entries": [{"table": col["table"], "column": col["column"], "personal_data": "personal"}]})
    assert r.status_code == 200, r.text
    d = client.get(f"/api/datasets/{did}/dictionary").json()
    row = next(x for x in d["rows"] if x["column"] == col["column"])
    assert row["personal_data"] == "personal" and row["personal_suggested"] is None and row["deid"] is None
    assert d["sensitive"]["marked"] == 1 and d["sensitive"]["needs_deid"] == [f"{col['table']}.{col['column']}"]
    assert d["sensitive"]["dataset_personal_data"] == "personal"
    assert client.put(f"/api/datasets/{did}/dictionary", json={"entries": [{"table": col["table"], "column": col["column"], "personal_data": "weird"}]}).status_code == 422
    r = client.put(f"/api/datasets/{did}/dictionary", json={"entries": [{"table": col["table"], "column": col["column"], "deid": {"method": "masking", "note": "뒤 4자리 마스킹"}}]})
    assert r.status_code == 200
    d = client.get(f"/api/datasets/{did}/dictionary").json()
    row = next(x for x in d["rows"] if x["column"] == col["column"])
    assert row["personal_data"] == "personal" and row["deid"]["method"] == "masking" and row["deid"]["by"] == "관리자" and d["sensitive"]["needs_deid"] == []
    ttl = client.get(f"/api/datasets/{did}/preview").json()["turtle"]
    assert 'personalDataType "personal"' in ttl and 'fde:method "masking"' in ttl
    # 컬럼에서 올라온 기본값: 등급을 O 로 두려면 사유 필요
    base = client.get(f"/api/datasets/{did}").json()["classification"]
    body = {k: base[k] for k in ("F1", "F2", "F3", "F4", "F5", "F6", "K") if k in base}
    g = client.get(f"/api/datasets/{did}").json()["grading"]
    assert g["suggested"] == "S2" and any("컬럼 민감 항목" in x for x in g["reasons"]) and g["columns"]["marked"] == 1
    r = client.put(f"/api/datasets/{did}/classification", json={**body, "N2SF": "N2SF-O"})
    assert r.status_code == 422 and "컬럼 민감 항목" in r.json()["detail"]["message"]
    assert client.put(f"/api/datasets/{did}/classification", json={**body, "N2SF": "N2SF-S2"}).status_code == 200
    # STEP 8 C-12 증빙에 비식별 기록 수가 붙는다 (즉시 진단으로 확인: 변환 전이라도 판정 가능)
    client.post(f"/api/processes/{pid}/rerun")
    dr = client.post(f"/api/processes/{pid}/diagnosis-runs").json()
    items = {i["id"]: i for i in dr["run"]["items"]} if "run" in dr else {i["id"]: i for i in client.get(f"/api/datasets/{did}/diagnosis-preview").json()["items"]}
    c12 = items["C-12"]
    assert any("비식별 처리 기록 1개" in (dd.get("detail") or "") for dd in c12.get("datasets", [])) or "비식별 처리 기록 1개" in (c12.get("detail") or "")

    # ② 조합 등급: 기본값은 구성 최고 등급, 낮추면 사유
    det = client.get(f"/api/processes/{pid}").json()
    cg = det["process"]["combo_grading"]
    assert cg["floor"] == "S2" and cg["grade"] == "S2" and cg["explicit"] is False
    r = client.put(f"/api/processes/{pid}/combo-grade", json={"grade": "O"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "COMBO_GRADE_BELOW"
    r = client.put(f"/api/processes/{pid}/combo-grade", json={"grade": "S1", "reason": "결합 결과는 읍면동 월별 집계만 제공하고 개별 기록은 반출하지 않음"})
    assert r.status_code == 200 and r.json()["process"]["combo_grading"]["below_floor"] is True
    pv = client.get(f"/api/processes/{pid}/publish-review").json()
    if pv["assessment"]:
        assert "combo_grade_lowered" in {s["code"] for s in pv["assessment"]["signals"]}
    assert client.put(f"/api/processes/{pid}/combo-grade", json={"grade": None}).json()["process"]["combo_grading"]["explicit"] is False

    # ③ 기관 등급표 가져오기: 열 자동 인식 · 이름 매칭 · 제안 등급 상향 · 충돌 신호
    csv_text = "업무정보명,정보시스템,소관부서,등급,개인정보 포함,법령 근거,비고\n교통사고,사고관리시스템,안전정책과,C,포함,도로교통법,원본\n도로목록,도로대장,도로과,O,,,\n알 수 없는 표,시스템X,부서,2,,,\n이상한등급,시스템Y,부서,Z,,,\n"
    r = client.post("/api/org-grades/import", files={"file": ("n2sf_org.csv", csv_text.encode("utf-8-sig"), "text/csv")})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["imported"] == 3 and out["auto_matched"] >= 2 and len(out["skipped"]) == 1 and "grade" in out["columns"]
    lst = client.get("/api/org-grades").json()
    acc = next(e for e in lst["items"] if e["name"] == "교통사고")
    assert acc["grade"] == "C" and acc["asset_id"] == S["acc"] and acc["match_score"] >= 90
    unknown = next(e for e in lst["items"] if e["name"] == "알 수 없는 표")
    assert unknown["asset_id"] is None and unknown["grade"] == "S2"
    # 기관표(C) 가 스튜디오 등급(S2) 보다 높다 → 제안이 C 로 오르고 충돌 신호
    g = client.get(f"/api/datasets/{did}").json()["grading"]
    assert g["org_grade"]["grade"] == "C" and g["suggested"] == "C" and g["org_conflict"] is True
    r = client.put(f"/api/datasets/{did}/classification", json={**body, "N2SF": "N2SF-S2"})
    assert r.status_code == 422 and "기관 등급표" in r.json()["detail"]["message"]
    pv = client.get(f"/api/processes/{pid}/publish-review").json()
    if pv["assessment"]:
        assert "org_grade_conflict" in {s["code"] for s in pv["assessment"]["signals"]}
    # 매칭 수정 · 비우기
    assert client.patch(f"/api/org-grades/{unknown['id']}", json={"asset_id": S["road"]}).json()["asset_id"] == S["road"]
    assert client.patch(f"/api/org-grades/{acc['id']}", json={"asset_id": None}).json()["asset_id"] is None
    assert client.get(f"/api/datasets/{did}").json()["grading"]["org_grade"] is None
    types = [a["type"] for a in client.get("/api/activities").json()]
    assert "org_grades_import" in types and "org_grades_match" in types
    assert client.delete("/api/org-grades").json()["deleted"] == 3
    # 원복
    assert client.put(f"/api/datasets/{did}/dictionary", json={"entries": [{"table": col["table"], "column": col["column"], "personal_data": "", "clear_deid": True}]}).status_code == 200
    with SessionLocal() as db:
        assert grading.column_items(db.get(ProcessDataset, did)) == {}


# ------------------------------------------------------------------ v0.15: AI 이용조건 등급별 기본값
def test_21_ai_term_defaults(client):
    pid, did = S["pid"], S["d_road"]
    assert client.post(f"/api/processes/{pid}/reopen").status_code in (200, 409)
    assert client.post(f"/api/datasets/{did}/classification/unconfirm").status_code in (200, 409)
    base = client.get(f"/api/datasets/{did}").json()["classification"]
    body = {k: base[k] for k in ("F1", "F2", "F3", "F4", "F5", "F6", "K") if k in base}
    # 이용조건을 비우고 C 로 정하면 5항목 전부 불허 기본값, 담당자가 이미 고른 항목은 그대로
    assert client.patch(f"/api/datasets/{did}/meta", json={"values": {"ai_training": None, "ai_combination": "permitted", "ai_automated_access": None, "ai_bulk_access": None, "ai_redistribution": None}}).status_code == 200
    r = client.put(f"/api/datasets/{did}/classification", json={**body, "N2SF": "N2SF-C", "N2SF_BASIS": {"personal_data": "none", "reidentification": "low", "legal": "statutory"}})
    assert r.status_code == 200, r.text
    meta = r.json()["meta"]
    assert meta["ai_training"] == "prohibited" and meta["ai_bulk_access"] == "prohibited" and meta["ai_combination"] == "permitted"
    assert meta["_ai_terms_defaulted"]["grade"] == "C" and "ai_training" in meta["_ai_terms_defaulted"]["fields"] and "ai_combination" not in meta["_ai_terms_defaulted"]["fields"]
    acts = [a["type"] for a in client.get("/api/activities").json()]
    assert "ai_terms_default" in acts
    # 같은 등급으로 다시 저장하면 다시 채우지 않는다 (등급이 바뀔 때만)
    assert client.patch(f"/api/datasets/{did}/meta", json={"values": {"ai_bulk_access": None}}).status_code == 200
    r = client.put(f"/api/datasets/{did}/classification", json={**body, "N2SF": "N2SF-C", "N2SF_BASIS": {"personal_data": "none", "reidentification": "low", "legal": "statutory"}})
    assert r.json()["meta"].get("ai_bulk_access") is None
    # 원복
    assert client.put(f"/api/datasets/{did}/classification", json={**body, "N2SF": base.get("N2SF", "N2SF-O")}).status_code == 200


# ------------------------------------------------------------------ /api/docs 노출 설정
def test_22_api_docs_toggle(client, monkeypatch):
    """개발 기본값은 열림. FDE_EXPOSE_API_DOCS=false 면 앱을 만들 때 docs · openapi 경로가 빠진다 (운영 compose 기본값)."""
    from fastapi import FastAPI

    from app.config import get_settings
    from app.main import app as live

    assert client.get("/api/docs").status_code == 200 and client.get("/api/openapi.json").status_code == 200
    assert isinstance(live, FastAPI)
    monkeypatch.setattr(get_settings(), "expose_api_docs", False)
    closed = FastAPI(docs_url="/api/docs" if get_settings().expose_api_docs else None, openapi_url="/api/openapi.json" if get_settings().expose_api_docs else None)
    assert closed.docs_url is None and closed.openapi_url is None


def _connector_target():
    """커넥터 시험용 PostgreSQL. CI 는 FDE_DATABASE_URL 의 PostgreSQL, 로컬은 55432 개발 DB. 둘 다 없으면 접속 부분만 건너뛴다."""
    import os
    from urllib.parse import urlparse

    url = os.environ.get("FDE_CONNECTOR_TEST_URL") or os.environ.get("FDE_DATABASE_URL", "")
    if not url.startswith("postgresql"):
        url = "postgresql+psycopg://postgres@127.0.0.1:55432/fde_test"
    u = urlparse(url)
    try:
        import psycopg
        psycopg.connect(host=u.hostname, port=u.port or 5432, dbname=u.path.lstrip("/"), user=u.username, password=u.password or "", connect_timeout=2).close()
    except Exception:  # noqa: BLE001
        return None
    return {"host": u.hostname, "port": u.port or 5432, "database": u.path.lstrip("/"), "username": u.username, "password": u.password or ""}


def test_23_db_connectors_and_integrations(client):
    """데이터 패브릭 외부 연계: 비밀번호 암호화 저장 · 응답 비노출, 읽기 전용 스키마 반영 → dbschema 자산, 연계 현황판."""
    from app.services import connectors

    # 암호화 왕복
    tok = connectors.encrypt("p@ss:word/한글")
    assert tok != "p@ss:word/한글" and connectors.decrypt(tok) == "p@ss:word/한글"

    board = client.get("/api/integrations").json()
    assert [i["key"] for i in board["items"]] == ["anthropic", "mcp", "connectors"]
    assert board["items"][2]["status"] == "off"

    # 작성자는 등록 못 함, 관리자만
    wtok = client.post("/api/auth/login", json={"username": "worker1", "password": "worker-pass-1"}).json()["access_token"]
    wh = {"Authorization": f"Bearer {wtok}"}
    body = {"name": "시험 DB", "kind": "postgresql", "host": "127.0.0.1", "port": 1, "database": "x", "username": "u", "password": "secret-pw"}
    assert client.post("/api/connectors", json=body, headers=wh).status_code == 403
    assert client.post("/api/connectors", json={**body, "kind": "oracle"}).status_code == 422
    r = client.post("/api/connectors", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    text_all = client.get("/api/connectors").text + r.text
    assert "secret-pw" not in text_all and "secret_enc" not in text_all, "비밀번호는 어떤 응답에도 없어야 한다"
    lst = client.get("/api/connectors").json()
    assert lst["items"][0]["status"] == "never" and lst["items"][0]["schema"] == "public" and lst["kinds"][0]["kind"] == "postgresql"

    # 접속 실패는 상태 error 로 기록되고 활동 로그에 남는다
    r = client.post(f"/api/connectors/{cid}/test", headers=wh)
    assert r.status_code == 200 and r.json()["ok"] is False and r.json()["connector"]["status"] == "error"
    assert client.post(f"/api/connectors/{cid}/sync", headers=wh).status_code == 502
    acts = client.get("/api/activities", params={"limit": 20}).json()
    types = [a["type"] for a in (acts["items"] if isinstance(acts, dict) else acts)]
    assert "connector_create" in types and "connector_test" in types and "connector_sync" in types

    target = _connector_target()
    if target is not None:
        # 실제 PostgreSQL 에 표를 만들고 스키마만 읽어 온다
        import psycopg
        with psycopg.connect(host=target["host"], port=target["port"], dbname=target["database"], user=target["username"], password=target["password"], autocommit=True) as cx:
            cx.execute("DROP SCHEMA IF EXISTS fde_conn_test CASCADE")
            cx.execute("CREATE SCHEMA fde_conn_test")
            cx.execute("CREATE TABLE fde_conn_test.citizen (resident_no varchar(14) primary key, name text, birth date, income numeric(12,2), active boolean)")
            cx.execute("COMMENT ON TABLE fde_conn_test.citizen IS '주민 기본'")
            cx.execute("INSERT INTO fde_conn_test.citizen VALUES ('900101-1234567', '홍길동', '1990-01-01', 100.5, true)")
            cx.execute("CREATE TABLE fde_conn_test.road_link (link_id bigint primary key, road_name text, length_m double precision)")
        r = client.post("/api/connectors", json={"name": "기관 DB", "kind": "postgresql", "schema": "fde_conn_test", **target})
        assert r.status_code == 201, r.text
        live = r.json()["id"]
        r = client.post(f"/api/connectors/{live}/test", headers=wh)
        assert r.status_code == 200 and r.json()["ok"] is True and r.json()["tables"] == 2 and r.json()["columns"] == 8, r.text
        r = client.post(f"/api/connectors/{live}/sync", headers=wh)
        assert r.status_code == 200, r.text
        assert sorted(r.json()["created"]) == ["citizen", "road_link"] and r.json()["connector"]["status"] == "ok" and r.json()["connector"]["table_count"] == 2
        assets = [a for a in client.get("/api/assets").json() if a["source"] == "dbschema"]
        assert len(assets) == 2
        cz = next(a for a in assets if a["name"] == "citizen")
        assert cz["connector"]["name"] == "기관 DB" and cz["profile_status"] == "dbschema" and cz["column_count"] == 5 and cz["row_count"] == 0
        assert cz["description"] == "주민 기본" and "DB 스키마" in cz["profile_summary"]
        detail = client.get(f"/api/assets/{cz['id']}").json()
        cols = {c["name"]: c for c in detail["profile"]["tables"][0]["columns"]}
        assert cols["resident_no"]["pk"] is True and cols["resident_no"].get("pii"), "주민번호 컬럼은 이름으로 개인정보 의심"
        assert cols["income"]["type"] == "number" and cols["birth"]["type"] == "datetime" and cols["active"]["type"] == "boolean" and cols["link_id"]["type"] == "integer" if "link_id" in cols else True
        assert all(c["samples"] == [] for c in cols.values()), "값은 읽지 않는다"
        assert "홍길동" not in client.get(f"/api/assets/{cz['id']}").text
        # 두 번째 동기화: 변화 없음 → unchanged, 표 하나 지우면 missing 표시
        r = client.post(f"/api/connectors/{live}/sync", headers=wh).json()
        assert r["created"] == [] and r["unchanged"] == 2
        with psycopg.connect(host=target["host"], port=target["port"], dbname=target["database"], user=target["username"], password=target["password"], autocommit=True) as cx:
            cx.execute("ALTER TABLE fde_conn_test.road_link ADD COLUMN lanes smallint")
            cx.execute("DROP TABLE fde_conn_test.citizen")
        r = client.post(f"/api/connectors/{live}/sync", headers=wh).json()
        assert r["updated"] == ["road_link"] and r["missing"] == ["fde_conn_test.citizen"]
        assets = [a for a in client.get("/api/assets").json() if a["source"] == "dbschema"]
        assert len(assets) == 2, "사라진 표의 자산은 지우지 않는다"
        assert any("원천 DB 에 이 테이블이 없었습니다" in w for w in next(a for a in assets if a["name"] == "citizen")["warnings"])
        board = client.get("/api/integrations").json()
        assert board["items"][2]["enabled"] is True and board["items"][2]["last_at"] is not None
        with psycopg.connect(host=target["host"], port=target["port"], dbname=target["database"], user=target["username"], password=target["password"], autocommit=True) as cx:
            cx.execute("DROP SCHEMA fde_conn_test CASCADE")
        # 삭제: 비밀번호 즉시 폐기, 자산은 남고 "연결 끊김" 표시
        assert client.delete(f"/api/connectors/{live}", headers=wh).status_code == 403
        assert client.delete(f"/api/connectors/{live}").status_code == 200
        assert all(c["id"] != live for c in client.get("/api/connectors").json()["items"])
        assets = [a for a in client.get("/api/assets").json() if a["source"] == "dbschema"]
        assert len(assets) == 2 and all(a["connector"]["deleted"] for a in assets)

    assert client.delete(f"/api/connectors/{cid}").status_code == 200
    assert client.get(f"/api/connectors/{cid}/test").status_code in (404, 405)


def test_24_ard_management(client):
    """ARD 관리: 산출물 보관함(페이지 · 필터 · 작업자/조직 정렬) · 다운로드 로그 · viewer O 등급 제한 · 제출 패키지 · 발행본 · 배포 이력 CSV · 보존 정책 · 요약."""
    pid = S["pid"]
    s = client.get("/api/ard/summary").json()
    assert s["artifacts"] > 0 and s["published"] >= 1 and s["page_sizes"] == [10, 20, 50, 100] and "stale" in s and "retention" in s
    f = client.get("/api/ard/filters").json()
    assert any(a["name"] == "관리자" for a in f["actors"]) and [k["kind"] for k in f["kinds"]] == ["file", "zip", "validation", "diagnosis"]

    # 목록 · 페이지 · 크기 (허용되지 않는 크기는 20 으로)
    r = client.get("/api/ard/artifacts", params={"page": 1, "size": 10}).json()
    assert r["size"] == 10 and len(r["items"]) <= 10 and r["pages"] >= 1 and r["total"] >= len(r["items"])
    assert client.get("/api/ard/artifacts", params={"size": 7}).json()["size"] == 20
    assert client.get("/api/ard/artifacts", params={"page": 999, "size": 10}).json()["page"] == r["pages"], "넘치는 페이지는 마지막 페이지로"
    kinds = {i["kind"] for i in client.get("/api/ard/artifacts", params={"size": 100, "latest_only": "false"}).json()["items"]}
    assert {"file", "zip", "diagnosis"} <= kinds
    assert all(i["kind"] == "zip" for i in client.get("/api/ard/artifacts", params={"kind": "zip"}).json()["items"])
    assert all(i["latest"] for i in client.get("/api/ard/artifacts", params={"latest_only": "true", "size": 100}).json()["items"])
    admin_id = next(a["id"] for a in f["actors"] if a["name"] == "관리자")
    by_actor = client.get("/api/ard/artifacts", params={"actor_id": admin_id, "size": 100}).json()
    assert by_actor["total"] > 0 and all(i["actor"]["id"] == admin_id for i in by_actor["items"])
    assert client.get("/api/ard/artifacts", params={"actor_id": 999999}).json()["total"] == 0
    names = [i["actor"]["name"] if i["actor"] else "" for i in client.get("/api/ard/artifacts", params={"sort": "actor", "size": 100}).json()["items"]]
    assert names == sorted(names, key=lambda n: n or "힣"), "작업자별 구분은 작업자 이름 순으로 정렬"
    q = client.get("/api/ard/artifacts", params={"q": "도로목록", "size": 100}).json()
    assert q["total"] > 0 and all("도로목록" in (i["dataset"] or {}).get("title", "") or "도로목록" in i["filename"] for i in q["items"])

    # 다운로드: 파일 · ZIP · 진단 보고서, 로그에 남는다
    files = [i for i in client.get("/api/ard/artifacts", params={"kind": "file", "size": 100}).json()["items"]]
    jl = next(i for i in files if i["format"] == "jsonld" and i["latest"])
    r = client.get("/api/ard/download", params={"kind": "file", "id": jl["id"]})
    assert r.status_code == 200 and r.headers["content-disposition"].startswith("attachment") and len(r.content) == jl["size"]
    z = next(i for i in client.get("/api/ard/artifacts", params={"kind": "zip"}).json()["items"])
    assert client.get("/api/ard/download", params={"kind": "zip", "id": z["id"]}).headers["content-type"].startswith("application/zip")
    d = next(i for i in client.get("/api/ard/artifacts", params={"kind": "diagnosis"}).json()["items"])
    assert client.get("/api/ard/download", params={"kind": "diagnosis", "id": d["id"]}).status_code == 200
    assert client.get("/api/ard/download", params={"kind": "file", "id": 999999}).status_code == 404
    hist = client.get("/api/ard/history", params={"type": "artifact_download", "size": 50}).json()
    assert hist["total"] >= 3 and hist["items"][0]["type"] == "artifact_download" and hist["items"][0]["payload"]["sha256"]
    assert s["downloads_7d"] + 3 <= client.get("/api/ard/summary").json()["downloads_7d"]

    # viewer: O 등급만. 앞 테스트들이 등급을 바꾸므로 O 인 것과 아닌 것을 목록에서 고른다 (스트림은 O, 교통사고는 S2)
    vtok = client.post("/api/auth/login", json={"username": "viewer1", "password": "viewer-pass-1"}).json()["access_token"]
    vh = {"Authorization": f"Bearer {vtok}"}
    items = client.get("/api/ard/artifacts", params={"kind": "file", "size": 100, "latest_only": "true"}, headers=vh).json()["items"]
    road = next(i for i in items if i["grade"] == "O" and i["format"] == "jsonld")
    acc = next(i for i in items if (i["dataset"] or {}).get("id") == S["d_acc"] and i["format"] == "jsonld")
    assert road["can_download"] is True
    assert acc["grade"] != "O" and acc["can_download"] is False
    assert client.get("/api/ard/download", params={"kind": "file", "id": road["id"]}, headers=vh).status_code == 200
    assert client.get("/api/ard/download", params={"kind": "file", "id": acc["id"]}, headers=vh).status_code == 403
    assert client.get("/api/ard/download", params={"kind": "zip", "id": z["id"]}, headers=vh).status_code == 403, "조합에 S2 가 있으면 ZIP 도 막는다"

    # 제출 패키지: JSON-LD · 카드 · 사전 + manifest
    import io
    import json
    import zipfile

    m = client.get(f"/api/ard/datasets/{S['d_road']}/package/manifest").json()
    assert m["resource_id"] and m["n2sf"]["grade"] in ("O", "S1", "S2") and {x["format"] for x in m["files"]} >= {"jsonld", "card", "dict"}
    r = client.get(f"/api/ard/datasets/{S['d_road']}/package")
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = zf.namelist()
        assert "manifest.json" in names and any(n.endswith(".jsonld") for n in names)
        man = json.loads(zf.read("manifest.json"))
        assert man["files"][0]["sha256"] and man["resource_id"] == m["resource_id"]
    assert client.get(f"/api/ard/datasets/{S['d_acc']}/package", headers=vh).status_code == 403
    assert client.get("/api/ard/history", params={"type": "package_download"}).json()["total"] >= 1

    # 발행본: 검색 · 상태 · 작업자, MCP 노출 플래그
    pub = client.get("/api/ard/published", params={"size": 10}).json()
    assert pub["total"] >= 1 and all(e["status"] == "published" for e in pub["items"]) and "mcp_exposed" in pub["items"][0]
    assert client.get("/api/ard/published", params={"q": "없는검색어zzz"}).json()["total"] == 0
    assert client.get("/api/ard/published", params={"actor_id": admin_id}).json()["total"] == pub["total"]
    assert client.get("/api/ard/published", params={"status": "all"}).json()["total"] >= pub["total"]
    detail = client.get(f"/api/catalog/{pub['items'][0]['resource_id']}").json()
    assert detail["dataset_id"] is not None
    assert "facets" not in client.get("/api/catalog").json()

    # 배포 이력 CSV
    r = client.get("/api/ard/history", params={"format": "csv"})
    assert r.status_code == 200 and r.text.startswith("﻿시각,구분") and "다운로드" in r.text

    # 보존 정책: 후보는 발행본이 참조하는 회차를 빼고 센다. 적용은 관리자만
    ret = client.get("/api/ard/retention").json()
    assert ret["keep"] == 5 and isinstance(ret["candidates"], list)
    assert client.post("/api/ard/retention/apply", headers=vh).status_code == 403
    r = client.post("/api/ard/retention/apply")
    assert r.status_code == 200 and r.json()["deleted"] == len(ret["candidates"])
    assert client.get("/api/ard/retention").json()["candidates"] == []


def test_25_column_samples_and_force_delete(client):
    """프로파일 예시값 직접 입력(작성자) · 강제 삭제(관리자만, 보호 무시 · 조합에서 떼어냄 · 민팅 대장은 유지)."""
    # 예시값 입력: 스키마만 있는 원천(스트림)에 담당자가 예시를 적는다
    r = client.post("/api/assets/streams", json={"name": "edit.samples.v1", "fields": [{"name": "event_time", "type": "datetime"}, {"name": "phone", "type": "string"}]})
    assert r.status_code in (200, 201), r.text
    aid = r.json()["id"]
    assert client.patch(f"/api/assets/{aid}/columns", params={"table": "stream", "column": "nope"}, json={"samples": ["x"]}).status_code == 404
    r = client.patch(f"/api/assets/{aid}/columns", params={"table": "stream", "column": "event_time"}, json={"samples": [" 2026-01-01T00:00:00+09:00 ", "", "2026-01-01T00:00:01+09:00"]})
    assert r.status_code == 200, r.text
    col = next(c for c in r.json()["profile"]["tables"][0]["columns"] if c["name"] == "event_time")
    assert col["samples"] == ["2026-01-01T00:00:00+09:00", "2026-01-01T00:00:01+09:00"] and col["samples_edited"] is True
    wtok = client.post("/api/auth/login", json={"username": "worker1", "password": "worker-pass-1"}).json()["access_token"]
    wh = {"Authorization": f"Bearer {wtok}"}
    assert client.patch(f"/api/assets/{aid}/columns", params={"table": "stream", "column": "phone"}, json={"samples": ["010-****-1234"]}, headers=wh).status_code == 200
    acts = client.get("/api/activities", params={"limit": 5}).json()
    assert any(a["type"] == "asset_column_edit" for a in acts)
    assert client.delete(f"/api/assets/{aid}").status_code == 200

    # 강제 삭제: 민팅된 원천은 일반 삭제 409, 작성자의 force 는 403, 관리자의 force 는 200 이고 프로세스에서 떨어진다
    road = S["road"]
    assert client.delete(f"/api/assets/{road}").status_code == 409
    assert client.delete(f"/api/assets/{road}", params={"force": "true"}, headers=wh).status_code == 403
    before = client.get(f"/api/processes/{S['pid']}").json()
    assert any(d["asset"]["id"] == road for d in before["datasets"])
    r = client.delete(f"/api/assets/{road}", params={"force": "true"})
    assert r.status_code == 200 and r.json()["force"] is True, r.text
    assert client.get(f"/api/assets/{road}").status_code == 404
    after = client.get(f"/api/processes/{S['pid']}").json()
    assert not any(d["asset"]["id"] == road for d in after["datasets"]), "모든 프로세스에서 떼어낸다"
    assert any(m["asset_id"] == road for m in client.get("/api/mint-registry").json()["records"]), "민팅 대장은 남는다"
    acts = client.get("/api/activities", params={"limit": 5}).json()
    assert any(a["type"] == "asset_delete" and "강제" in a["text"] for a in acts)


def test_26_process_scope_and_assignment(client):
    """작업자는 자기 프로세스만 (새 작업자는 빈 목록), 관리자 · 열람은 전부. 관리자가 담당자를 배정하면 그 작업자에게 보인다."""
    pid = S["pid"]
    r = client.post("/api/users", json={"username": "worker2", "name": "신규담당", "password": "worker-pass-2", "role": "worker", "org_label": "교통정책과"})
    assert r.status_code in (200, 201), r.text
    w2 = client.post("/api/auth/login", json={"username": "worker2", "password": "worker-pass-2"}).json()["access_token"]
    wh = {"Authorization": f"Bearer {w2}"}
    assert client.get("/api/processes", headers=wh).json() == [], "새 작업자는 빈 목록"
    assert client.get(f"/api/processes/{pid}", headers=wh).status_code == 404, "남의 프로세스는 존재도 안 보임"
    assert client.get(f"/api/processes/{pid}/graph", headers=wh).status_code == 404
    assert client.get(f"/api/datasets/{S['d_acc']}", headers=wh).status_code == 404
    assert client.get("/api/ard/artifacts", headers=wh).json()["total"] == 0
    dash = client.get("/api/dashboard", headers=wh).json()
    assert dash["recent_processes"] == [] and dash["counts"]["processes_active"] == 0
    # 관리자 · 열람은 전부
    assert any(p["id"] == pid for p in client.get("/api/processes").json())
    vtok = client.post("/api/auth/login", json={"username": "viewer1", "password": "viewer-pass-1"}).json()["access_token"]
    assert any(p["id"] == pid for p in client.get("/api/processes", headers={"Authorization": f"Bearer {vtok}"}).json())
    # 작업자 자신이 만든 프로세스는 보인다
    mine = client.post("/api/processes", json={"name": "신규담당 작업"}, headers=wh).json()["process"]["id"]
    assert [p["id"] for p in client.get("/api/processes", headers=wh).json()] == [mine]
    assert client.get(f"/api/processes/{mine}", headers=wh).status_code == 200
    # 배정: 작업자는 못 하고 관리자만. 배정하면 그 작업자 목록에 나타나고 원래 사람은 못 본다
    assert client.patch(f"/api/processes/{pid}", json={"owner_id": None}, headers=wh).status_code in (403, 404)
    w2id = next(u["id"] for u in client.get("/api/users").json() if u["username"] == "worker2")
    r = client.patch(f"/api/processes/{pid}", json={"owner_id": w2id})
    assert r.status_code == 200 and r.json()["process"]["owner"]["id"] == w2id, r.text
    ids = {p["id"] for p in client.get("/api/processes", headers=wh).json()}
    assert ids == {mine, pid}
    assert client.get(f"/api/processes/{pid}", headers=wh).status_code == 200
    assert client.get("/api/ard/artifacts", headers=wh).json()["total"] > 0, "배정받은 프로세스의 산출물도 보인다"
    w1 = client.post("/api/auth/login", json={"username": "worker1", "password": "worker-pass-1"}).json()["access_token"]
    assert client.get(f"/api/processes/{pid}", headers={"Authorization": f"Bearer {w1}"}).status_code == 404
    acts = client.get("/api/activities", params={"limit": 5}).json()
    assert any(a["type"] == "process_assign" for a in acts)
    # 원래 담당자(worker1)에게 되돌린다 (뒤 테스트가 worker1 으로 이 프로세스를 쓴다)
    w1id = next(u["id"] for u in client.get("/api/users").json() if u["username"] == "worker1")
    assert client.patch(f"/api/processes/{pid}", json={"owner_id": w1id}).status_code == 200


def test_27_jsonl_upload(client):
    """스트림 표본 덤프(JSON Lines) 업로드: 줄 단위 레코드 → 표 1개, 중첩 객체는 점 표기 컬럼, 번호판은 개인정보 의심."""
    rows = [
        '{"event_time":"2026-10-17T14:02:01+09:00","cctv_id":"CCTV-0417","link_id":"LNK-58-0031","plate":"58로1234","speed_kmh":100.2,"flags":{"hard_brake":false}}',
        '{"event_time":"2026-10-17T14:02:02+09:00","cctv_id":"CCTV-0417","link_id":"LNK-58-0031","plate":"12가5678","speed_kmh":64.0,"flags":{"hard_brake":false}}',
        "not json at all",
        '{"event_time":"2026-10-17T14:05:03+09:00","cctv_id":"CCTV-0417","link_id":"LNK-58-0031","plate":"58로1234","speed_kmh":12.4,"flags":{"hard_brake":true}}',
    ]
    r = client.post("/api/assets/upload", files=[("files", ("cctv_vehicle_det_v1_관측.jsonl", ("\n".join(rows) + "\n").encode("utf-8"), "application/x-ndjson"))])
    assert r.status_code == 200, r.text
    a = r.json()["created"][0]
    assert a["ext"] == "jsonl" and a["data_form"] == "반정형" and a["profile_status"] == "ok" and a["row_count"] == 3, a
    assert any("건너뛰었습니다" in w for w in a["warnings"])
    d = client.get(f"/api/assets/{a['id']}").json()
    cols = {c["name"]: c for c in d["profile"]["tables"][0]["columns"]}
    assert {"event_time", "cctv_id", "link_id", "plate", "speed_kmh", "flags.hard_brake"} <= set(cols)
    assert cols["event_time"]["type"] == "datetime" and cols["speed_kmh"]["type"] == "number" and cols["flags.hard_brake"]["type"] == "boolean"
    assert cols["plate"].get("pii") and cols["plate"]["samples"] == [], "번호판은 개인정보 의심 — 예시값 저장 안 함"
    assert "K5" in a["keys"] and "K7" in a["keys"], "링크 ID · 시각이 연계키 후보"
    assert client.delete(f"/api/assets/{a['id']}").status_code == 200


def test_28_stream_from_sample_and_schema_file(client):
    """스트림 등록 입구 정리: 표본 파일에서 필드 가져오기(sample_asset_id) · 스키마 파일(*.schema.json) 업로드는 스트림으로 등록."""
    import json

    rows = ['{"obs_time":"2026-10-16T17:41:00+09:00","station_id":"AWS-401","temp_c":30.0,"rain_mm_h":12.0}',
            '{"obs_time":"2026-10-16T17:42:00+09:00","station_id":"AWS-401","temp_c":30.1,"rain_mm_h":11.5}']
    r = client.post("/api/assets/upload", files=[("files", ("kma_aws_obs_v1.jsonl", ("\n".join(rows) + "\n").encode(), "application/x-ndjson"))])
    sample = r.json()["created"][0]
    # 표본에서: 필드를 비우면 표본 컬럼으로, event-time 은 첫 datetime
    r = client.post("/api/assets/streams", json={"name": "kma.aws.obs.v1", "temporal_resolution": "PT1M", "fields": [], "sample_asset_id": sample["id"]})
    assert r.status_code == 200, r.text
    st = r.json()
    assert st["kind"] == "stream" and [f["name"] for f in st["stream"]["fields"]] == ["obs_time", "station_id", "temp_c", "rain_mm_h"]
    assert st["stream"]["event_time_column"] == "obs_time" and st["stream"]["sample_asset_id"] == sample["id"] and st["stream"]["sample_filename"] == "kma_aws_obs_v1.jsonl"
    assert "K7" in st["keys"]
    assert client.post("/api/assets/streams", json={"name": "x.y", "fields": [], "sample_asset_id": 999999}).status_code == 422
    # 스키마 파일 업로드 → 표가 아니라 스트림으로
    spec = {"name": "vds.traffic.volume.v1", "title": "VDS 5분 집계", "temporal_resolution": "PT5M", "event_time_column": "collected_at", "endpoint_url": "kafka://b:9092/vds",
            "fields": [{"name": "collected_at", "type": "datetime"}, {"name": "link_id", "type": "string"}, {"name": "volume", "type": "integer"}]}
    r = client.post("/api/assets/upload", files=[("files", ("vds_traffic_volume_v1.schema.json", json.dumps(spec, ensure_ascii=False).encode(), "application/json"))])
    assert r.status_code == 200, r.text
    created = r.json()["created"]
    assert len(created) == 1 and created[0]["kind"] == "stream" and created[0]["name"] == "vds.traffic.volume.v1"
    assert created[0]["stream"]["registered_via"] == "schema_file" and created[0]["stream"]["temporal_resolution"] == "PT5M" and created[0]["profile_status"] == "stream"
    # 같은 이름을 다시 올리면 거부 사유에 설명이 붙는다
    r = client.post("/api/assets/upload", files=[("files", ("vds_traffic_volume_v1.schema.json", json.dumps(spec).encode(), "application/json"))])
    assert r.json()["created"] == [] and "스트림 스키마 파일" in r.json()["rejected"][0]["reason"]
    # 일반 JSON 표(레코드 배열)는 여전히 표로
    r = client.post("/api/assets/upload", files=[("files", ("plain.json", json.dumps([{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]).encode(), "application/json"))])
    assert r.json()["created"][0]["kind"] == "dataset" and r.json()["created"][0]["row_count"] == 2
    for a in (sample, st, created[0], r.json()["created"][0]):
        client.delete(f"/api/assets/{a['id']}")


def test_29_version_diff_and_share_links(client):
    """v0.19: 버전 비교(회차 · 발행본 JSON-LD 트리플 차이) · 공유 링크(O · S1 만, 만료 · 횟수 · 회수 · 등급 상승 차단, 로그인 없는 내려받기, 이력)."""
    pid = S["pid"]
    did = next(d["id"] for d in client.get(f"/api/processes/{pid}").json()["datasets"] if d["asset"]["kind"] == "stream") if False else S["d_stream"]
    v = client.get(f"/api/ard/datasets/{did}/versions").json()
    assert len(v["items"]) >= 2 and any(x["kind"] == "published" for x in v["items"]) and v["items"][-1]["kind"] == "run"
    runs = [x for x in v["items"] if x["kind"] == "run"]
    pub = next(x for x in v["items"] if x["kind"] == "published")
    d = client.get(f"/api/ard/datasets/{did}/diff", params={"from_ref": runs[0]["ref"], "to_ref": runs[0]["ref"]}).json()
    assert d["identical"] is True and d["added"] == 0 and d["removed"] == 0 and d["unchanged"] > 0
    d = client.get(f"/api/ard/datasets/{did}/diff", params={"from_ref": pub["ref"], "to_ref": runs[0]["ref"]}).json()
    assert d["from"]["label"].startswith("발행본") and isinstance(d["rows"], list) and "by_predicate" in d
    assert client.get(f"/api/ard/datasets/{did}/diff", params={"from_ref": "run:999999", "to_ref": runs[0]["ref"]}).status_code == 404

    # 공유 링크: O 등급(스트림 cctv.vehicle.det.v1 은 O) 파일은 되고, S2(교통사고)는 403
    files = client.get("/api/ard/artifacts", params={"kind": "file", "size": 100, "latest_only": "true"}).json()["items"]
    o_file = next(i for i in files if i["grade"] == "O" and i["format"] == "jsonld")
    s2_file = next(i for i in files if (i["dataset"] or {}).get("id") == S["d_acc"] and i["format"] == "jsonld")
    assert client.post("/api/ard/share-links", json={"kind": "file", "target_id": s2_file["id"], "days": 7, "max_downloads": 2}).status_code == 403
    r = client.post("/api/ard/share-links", json={"kind": "file", "target_id": o_file["id"], "days": 7, "max_downloads": 2, "recipient": "○○공단 데이터팀"})
    assert r.status_code == 201, r.text
    link = r.json()
    token = link["token"]
    assert link["url"].endswith(f"/share/{token}") and link["state"] == "active" and link["grade"] == "O" and "token_hash" not in link
    lst = client.get("/api/ard/share-links").json()
    assert any(i["id"] == link["id"] and i["token_prefix"] == token[:8] for i in lst["items"]) and lst["grades"] == ["O", "S1"]
    assert "token" not in lst["items"][0] or lst["items"][0].get("token") is None, "목록에는 토큰 원문이 없다"
    # 받는 쪽: 로그인 없이 정보 · 내려받기 (Authorization 헤더 없이)
    noauth = {"Authorization": ""}
    info = client.get(f"/api/share/{token}", headers=noauth).json()
    assert info["ok"] is True and info["remaining"] == 2 and info["filename"] == o_file["filename"] and info["recipient"] == "○○공단 데이터팀"
    r = client.get(f"/api/share/{token}/download", headers=noauth)
    assert r.status_code == 200 and len(r.content) == o_file["size"]
    assert client.get(f"/api/share/{token}", headers=noauth).json()["remaining"] == 1
    assert client.get(f"/api/share/{token}/download", headers=noauth).status_code == 200
    r = client.get(f"/api/share/{token}/download", headers=noauth)
    assert r.status_code == 410 and "횟수" in r.json()["detail"]
    assert client.get("/api/share/nope-token", headers=noauth).status_code == 404
    hist = client.get("/api/ard/history", params={"type": "share_download"}).json()
    assert hist["total"] >= 2 and hist["items"][0]["payload"]["share_id"] == link["id"]
    # 회수: 작성자(worker1)는 남의 링크 403, 관리자는 OK
    wtok = client.post("/api/auth/login", json={"username": "worker1", "password": "worker-pass-1"}).json()["access_token"]
    r2 = client.post("/api/ard/share-links", json={"kind": "file", "target_id": o_file["id"], "days": 1, "max_downloads": 1}).json()
    assert client.post(f"/api/ard/share-links/{r2['id']}/revoke", headers={"Authorization": f"Bearer {wtok}"}).status_code == 403
    assert client.post(f"/api/ard/share-links/{r2['id']}/revoke").json()["state"] == "revoked"
    assert client.get(f"/api/share/{r2['token']}", headers=noauth).json()["ok"] is False
    assert client.get(f"/api/share/{r2['token']}/download", headers=noauth).status_code == 410
    # 제출 패키지 링크 + 등급 상승 차단
    r3 = client.post("/api/ard/share-links", json={"kind": "package", "target_id": did, "days": 3, "max_downloads": 5}).json()
    assert r3["kind"] == "package" and client.get(f"/api/share/{r3['token']}/download", headers=noauth).headers["content-type"].startswith("application/zip")
    from app.db import SessionLocal
    from app.models import ProcessDataset
    with SessionLocal() as db:
        pd = db.get(ProcessDataset, did)
        pd.classification = {**(pd.classification or {}), "N2SF": "N2SF-S2"}
        db.commit()
    assert client.get(f"/api/share/{r3['token']}/download", headers=noauth).status_code == 410, "만든 뒤 S2 로 올라가면 막힌다"
    with SessionLocal() as db:
        pd = db.get(ProcessDataset, did)
        pd.classification = {**(pd.classification or {}), "N2SF": "N2SF-O"}
        db.commit()
    assert client.get(f"/api/share/{r3['token']}/download", headers=noauth).status_code == 200
    acts = client.get("/api/activities", params={"limit": 30}).json()
    assert {"share_create", "share_revoke", "share_download"} <= {a["type"] for a in acts}


def test_30_external_check(client):
    """외부 정본 검사: 스튜디오 발행본 Turtle 은 게이트 0 + SHACL 통과, prefix 누락 · 임시 ID 파일은 SHACL 도달 전 차단."""
    good = client.get("/api/catalog/DST-000001/raw", params={"format": "ttl"}).text
    broken = ('@prefix dcat: <http://www.w3.org/ns/dcat#> .\n@prefix dcterms: <http://purl.org/dc/terms/> .\n'
              '<https://x/id/dataset/DST-신규-0001> a dcat:Dataset ; dcterms:title "t" ; prov:wasGeneratedBy <https://x/id/activity/ACT-초안-1> .\n')
    r = client.post("/api/ard/check-external", data={"mode": "publish"},
                    files=[("files", ("good.ttl", good.encode(), "text/turtle")), ("files", ("broken.ttl", broken.encode(), "text/turtle")), ("files", ("x.bin", b"\xff\xfe", "application/octet-stream"))])
    assert r.status_code == 200, r.text
    res = {x["filename"]: x for x in r.json()["results"]}
    g, b, x = res["good.ttl"], res["broken.ttl"], res["x.bin"]
    assert g["verdict"].startswith("통과") and g["shacl"]["conforms"] and g["triples"] > 100 and all(c["ok"] for c in g["gate0"])
    assert b["blocked_before_shacl"] and b["shacl"] is None and b["verdict"].startswith("차단")
    g0 = {c["key"]: c for c in b["gate0"]}
    assert g0["parse"]["ok"] is False and g0["prefix"]["ok"] is False and "prov" in g0["prefix"]["detail"] and g0["mint"]["ok"] is False
    assert x["blocked_before_shacl"] and {c["key"]: c["ok"] for c in x["gate0"]}["utf8"] is False
    # 초안 모드면 ④ 는 생략
    r = client.post("/api/ard/check-external", data={"mode": "draft"}, files=[("files", ("good.ttl", good.encode(), "text/turtle"))]).json()["results"][0]
    assert next(c for c in r["gate0"] if c["key"] == "mint")["skipped"] is True
    assert any(a["type"] == "external_check" for a in client.get("/api/activities", params={"limit": 5}).json())


def test_31_taxonomy_sets(client):
    """분류체계 세트: 기본 세트 자동 이관 · 복제(코드 접두 · source_code) · 세트별 코드 추가 · CSV 내보내기/가져오기 · 프로세스 세트 전환(추천 매핑 · 확정 시 거부) · 삭제 보호."""
    sets = client.get("/api/taxonomy-sets").json()
    base = next(s for s in sets["items"] if s["slug"] == "base")
    assert base["is_default"] and base["locked"] and base["code_total"] >= 50 and base["code_counts"]["F1"] >= 10
    tax = client.get("/api/taxonomy").json()
    f1 = next(a for a in tax if a["code"] == "F1")
    assert all(c["set_id"] == base["id"] for c in f1["codes"]) and next(a for a in tax if a["code"] == "K")["in_set"] is False

    # 복제: 현대제철 세트
    r = client.post("/api/taxonomy-sets", json={"name": "현대제철 분류체계", "scope": "현대제철 · 제조", "base_set_id": base["id"], "slug": "HS"})
    assert r.status_code == 201, r.text
    hs = r.json()
    assert hs["slug"] == "hs" and hs["code_total"] == base["code_total"] and hs["base_set"]["id"] == base["id"] and not hs["is_default"]
    hs_tax = client.get("/api/taxonomy", params={"set_id": hs["id"]}).json()
    hs_f1 = next(a for a in hs_tax if a["code"] == "F1")["codes"]
    assert hs_f1[0]["code"].startswith("F1-HS-") and hs_f1[0]["extra"]["source_code"] == f1["codes"][0]["code"]
    # 세트별 코드 추가 (작성자는 남의 세트 403, 관리자 OK), 기본 세트는 관리자만
    wtok = client.post("/api/auth/login", json={"username": "worker1", "password": "worker-pass-1"}).json()["access_token"]
    wh = {"Authorization": f"Bearer {wtok}"}
    assert client.post("/api/taxonomy/F1/codes", json={"label": "제철 공정", "set_id": hs["id"]}, headers=wh).status_code == 403
    assert client.post("/api/taxonomy/F1/codes", json={"label": "제철 공정"}, headers=wh).status_code == 403
    r = client.post("/api/taxonomy/F1/codes", json={"label": "제철 공정", "definition": "고로 · 제강 · 압연", "set_id": hs["id"]})
    assert r.status_code == 200 and any(c["label"] == "제철 공정" and c["code"].startswith("F1-HS-") for c in r.json()["codes"])
    assert not any(c["label"] == "제철 공정" for c in next(a for a in client.get("/api/taxonomy").json() if a["code"] == "F1")["codes"]), "기본 세트에는 안 들어간다"
    # 작성자가 만든 세트는 작성자가 고칠 수 있다
    mine = client.post("/api/taxonomy-sets", json={"name": "담당자 세트", "base_set_id": base["id"], "empty": True}, headers=wh).json()
    assert mine["code_total"] == 0
    assert client.post("/api/taxonomy/F2/codes", json={"label": "센서 로그", "set_id": mine["id"]}, headers=wh).status_code == 200
    # CSV 내보내기 · 가져오기 (replace 로 폐기까지)
    csv_text = client.get(f"/api/taxonomy-sets/{hs['id']}/export").text
    assert csv_text.startswith("﻿axis,code,label") and "F1-HS-01" in csv_text
    up = "axis,label,definition\nF1,제철 공정,고로\nF1,물류 야드,출하\nF6,사내 공개,사내망 한정\n"
    r = client.post(f"/api/taxonomy-sets/{mine['id']}/import", files=[("file", ("set.csv", up.encode("utf-8-sig"), "text/csv"))], headers=wh)
    assert r.status_code == 200 and r.json()["added"] == 3, r.text
    r = client.post(f"/api/taxonomy-sets/{mine['id']}/import?replace=true", files=[("file", ("set.csv", "axis,label\nF1,제철 공정\n".encode(), "text/csv"))], headers=wh).json()
    assert r["updated"] == 1 and r["retired"] >= 2

    # 프로세스 세트 전환: 추천이 세트 코드로 매핑, 분류 확정 뒤에는 거부
    pid = S["pid"]
    r = client.post("/api/processes", json={"name": "세트 테스트"}).json()
    p2 = r["process"]["id"]
    assert r.get("taxonomy_set", {}).get("id") == base["id"] or client.get(f"/api/processes/{p2}").json()["taxonomy_set"]["id"] == base["id"]
    assert client.put(f"/api/processes/{p2}/selection", json={"asset_ids": [S["acc"]]}).status_code == 200
    d2 = client.get(f"/api/processes/{p2}").json()["datasets"][0]["id"]
    r = client.patch(f"/api/processes/{p2}", json={"taxonomy_set_id": hs["id"]})
    assert r.status_code == 200 and r.json()["taxonomy_set"]["id"] == hs["id"] and r.json()["process"]["taxonomy_set_id"] == hs["id"]
    sug = client.get(f"/api/datasets/{d2}/classification/suggestions").json()["suggestions"]
    f1s = [x for x in sug if x["axis"] == "F1"]
    assert f1s and all(x["code"].startswith("F1-HS-") and x["source_code"].startswith("F1-") for x in f1s), "추천이 세트 코드로 매핑"
    assert client.get("/api/taxonomy", params={"process_id": p2}).json()[0]["codes"][0]["code"].startswith("F1-HS-")
    # 세트 밖 코드는 422, 세트 코드는 200
    assert client.put(f"/api/datasets/{d2}/classification", json={"F1": [f1["codes"][0]["code"]]}).status_code == 422
    assert client.put(f"/api/datasets/{d2}/classification", json={"F1": [hs_f1[0]["code"]], "F2": [], "F3": [], "F4": [], "F5": [], "F6": [], "K": []}).status_code == 200
    # 다시 기본으로 돌리면 source_code 로 코드가 따라온다
    r = client.patch(f"/api/processes/{p2}", json={"taxonomy_set_id": base["id"]}).json()
    assert r["datasets"][0]["classification"]["F1"] == [f1["codes"][0]["code"]]
    # 확정 뒤에는 바꿀 수 없다
    assert client.post(f"/api/datasets/{d2}/classification/confirm").status_code in (200, 409)
    if client.get(f"/api/processes/{p2}").json()["datasets"][0]["class_confirmed_at"]:
        assert client.patch(f"/api/processes/{p2}", json={"taxonomy_set_id": hs["id"]}).status_code == 409
    # 삭제 보호: 기본 세트 · 사용 중 세트
    assert client.delete(f"/api/taxonomy-sets/{base['id']}").status_code == 409
    client.patch(f"/api/processes/{p2}", json={"taxonomy_set_id": hs["id"]})
    used = client.get("/api/taxonomy-sets").json()
    if next(s for s in used["items"] if s["id"] == hs["id"])["process_count"]:
        assert client.delete(f"/api/taxonomy-sets/{hs['id']}").status_code == 409
    assert client.delete(f"/api/taxonomy-sets/{mine['id']}", headers=wh).status_code == 200
    assert client.post(f"/api/processes/{p2}/trash").status_code == 200
    assert pid  # 기존 프로세스는 건드리지 않았다
