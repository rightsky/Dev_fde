from pathlib import Path

from app.services import profiling

from .samples import accident_csv, road_xlsx


def _profile(tmp_path: Path, name: str, data: bytes):
    p = tmp_path / name
    p.write_bytes(data)
    return profiling.profile_file(p, name)


def test_xlsx_header_detection_and_keys(tmp_path):
    res = _profile(tmp_path, "도로목록.xlsx", road_xlsx())
    t = res.profile["tables"][0]
    assert res.profile["status"] == "ok"
    assert t["header_row"] == 3, "제목 행·빈 행 아래의 실제 머리글(엑셀 3행)을 찾아야 한다"
    assert t["preamble"] == ["도로 공간정보 목록 (2026년 8월 기준)"]
    assert [c["name"] for c in t["columns"]][:3] == ["LINK_ID", "도로명", "시군구코드"]
    assert t["rows"] == 200
    by = {c["name"]: c for c in t["columns"]}
    assert by["LINK_ID"]["unique"] and by["LINK_ID"]["type"] == "string"
    assert by["경도"]["type"] == "number" and by["연장(m)"]["type"] == "integer"
    assert by["기준일자"]["type"] == "datetime" and by["기준일자"]["iso8601"]
    codes = {c["code"]: c["column"] for c in res.key_candidates}
    assert codes["K5"] == "LINK_ID" and codes["K1"] == "시군구코드" and codes["K7"] == "기준일자"
    assert "K3" in codes
    assert len(res.key_samples["도로목록|LINK_ID"]) == 200


def test_csv_cp949_mixed_formats_and_pii(tmp_path):
    res = _profile(tmp_path, "사고.csv", accident_csv())
    t = res.profile["tables"][0]
    by = {c["name"]: c for c in t["columns"]}
    assert t["rows"] == 150
    assert by["발생일시"]["type"] == "datetime" and not by["발생일시"]["iso8601"]
    assert len(by["발생일시"]["date_formats"]) == 2
    assert by["차량번호"]["pii"]["kind"] == "차량번호"
    assert {m["marker"] for m in by["비고"]["missing_markers"]} >= {"-", "null"}
    w = " ".join(res.profile["warnings"])
    assert "시간 포맷" in w and "결측 표기" in w and "개인정보" in w and "cp949" in w
    codes = {c["code"] for c in res.key_candidates}
    assert {"K5", "K7", "K2", "K6"} <= codes


def test_unsupported_and_broken(tmp_path):
    res = _profile(tmp_path, "보고서.pdf", b"%PDF-1.4 ...")
    assert res.profile["status"] == "unsupported" and res.data_form == "비정형"
    res = _profile(tmp_path, "깨진.xlsx", b"not a zip")
    assert res.profile["status"] == "error"
