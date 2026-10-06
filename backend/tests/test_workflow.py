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
    assert run["ok_count"] == 3 and len(run["artifacts"]) == 12
    for sv in run["self_verify"]:
        assert sv["passed"] and len(sv["checks"]) == 6, sv
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
    schema = json.loads(client.get(f"/api/artifacts/{arts[(S['d_stream'], 'schema')]['id']}").json()["content"])
    assert {"@id", "identifier", "title", "publisher", "temporalResolution", "eventTimeColumn"} <= set(schema["required"])

    z = client.get(f"/api/serialization-runs/{run['id']}/download")
    assert z.status_code == 200
    with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
        names = zf.namelist()
        assert "manifest.json" in names and len(names) == 13
        man = json.loads(zf.read("manifest.json"))
        assert all(f["sha256"] for f in man["files"])
    dl = client.get(f"/api/artifacts/{arts[(S['d_road'], 'ttl')]['id']}", params={"download": True})
    assert "attachment" in dl.headers["content-disposition"] and dl.headers["content-type"].startswith("text/turtle")
    st = r.json()["state"]
    assert gate(st, 7)["done"] and gate(st, 8)["can_enter"]


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
    sr = client.post(f"/api/processes/{pid}/serialization-runs", json={"formats": ["ttl", "jsonld", "txt", "schema"]}).json()["run"]
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


def test_11_diagnosis_and_attestation(client):
    pid = S["pid"]
    r = client.post(f"/api/processes/{pid}/diagnosis-runs")
    assert r.status_code == 200, r.text
    run = r.json()["run"]
    items = {i["id"]: i for i in run["items"]}
    assert items["M-03"]["status"] == "met" and items["M-04"]["status"] == "met"
    assert items["C-01"]["status"] == "met", items["C-01"]
    assert items["C-02"]["status"] == "partial", "사고 CSV 는 결측 표기가 혼재한다"
    assert items["P-06"]["status"] == "partial", "사고 CSV 의 발생일시가 ISO 8601 이 아니다"
    assert items["O-06"]["status"] == "unmet" and items["O-06"]["route"]["focus"] == "rai_data_biases"
    assert items["T-01"]["status"] == "pending", "개인정보 의심 컬럼(차량번호)이 있어 담당자 확인이 필요하다"
    assert items["C-04"]["status"] == "pending"
    assert items["R-04"]["status"] == "partial"
    assert run["max_score"] == len([i for i in run["items"] if i["status"] != "na"])
    assert run["summary"]["roadmap"][0]["difficulty"] == "낮음"
    before = run["score"]

    assert client.put(f"/api/processes/{pid}/attestations/M-01", json={"status": "met", "evidence": "x"}).status_code == 422
    assert client.put(f"/api/processes/{pid}/attestations/C-04", json={"status": "met"}).status_code == 422
    assert client.put(f"/api/processes/{pid}/attestations/C-04", json={"status": "met", "evidence": "공유폴더/데이터카드_v1.docx"}).status_code == 200
    run = client.post(f"/api/processes/{pid}/diagnosis-runs").json()["run"]
    assert run["score"] == before + 1 and {i["id"]: i for i in run["items"]}["C-04"]["status"] == "met"
    rep = client.get(f"/api/diagnosis-runs/{run['id']}/report")
    assert rep.status_code == 200 and "가이드라인 준수 진단 보고서" in rep.text

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
