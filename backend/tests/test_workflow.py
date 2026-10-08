"""8단계 전 과정을 API 로 수행하는 통합 테스트.

업로드 → 조합 → 메타데이터 승인 → 분류 → 관계 → 검증(초안·발행) → 민팅 → 직렬화 → 발행 → 진단.
"""
import io
import json
import zipfile

import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCAT, DCTERMS, RDF

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
    assert not gate(r.json()["state"], 7)["can_enter"]
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
    assert gate(st, 6)["done"] and gate(st, 7)["can_enter"]
    S["checksum_before"] = road["checksum"]

    # 상류(STEP 3)를 고치면 검증 결과가 무효화되고 STEP 7 이 다시 잠긴다
    client.patch(f"/api/datasets/{S['d_road']}/meta", json={"values": {"conforms_to": ["EPSG:5186"]}})
    st = client.get(f"/api/processes/{pid}").json()["state"]
    assert st["validation"]["stale"] and not gate(st, 6)["done"] and not gate(st, 7)["can_enter"]
    assert client.post(f"/api/processes/{pid}/serialization-runs", json={}).status_code == 409

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
    r = client.post(f"/api/processes/{pid}/publish")
    assert r.status_code == 200, r.text
    assert sorted(e["resource_id"] for e in r.json()["published"]) == ids

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
    assert run["max_score"] == max_before - 1 and run["score"] == before + 3
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
    assert "다시 확인 필요" in items["R-09"]["evidence"][0] and items["P-10"]["status"] == "pending"
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
