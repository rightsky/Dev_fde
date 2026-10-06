"""업로드 파일 프로파일링.

파일을 실제로 읽어 표(시트) 단위로 컬럼 타입·결측·고유값·시간 포맷·개인정보 의심 여부를 산출하고,
컬럼명과 값 패턴으로 연계키(K1~K9) 후보를 계산한다. 결과는 Asset.profile / key_candidates / key_samples 에 저장된다.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

MEDIA_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "csv": "text/csv",
    "tsv": "text/tab-separated-values",
    "txt": "text/plain",
    "json": "application/json",
    "parquet": "application/vnd.apache.parquet",
    "xml": "application/xml",
    "pdf": "application/pdf",
    "hwp": "application/x-hwp",
    "hwpx": "application/hwp+zip",
}
DATA_FORMS = {
    "xlsx": "정형", "xls": "정형", "csv": "정형", "tsv": "정형", "parquet": "정형",
    "json": "반정형", "xml": "반정형", "txt": "비정형", "pdf": "비정형", "hwp": "비정형", "hwpx": "비정형",
}
TABULAR_EXTS = {"xlsx", "xls", "csv", "tsv", "json", "parquet"}
BLOCKED_EXTS = {"mp4", "avi", "ts", "pcap", "bag", "exe", "dll", "sh", "bat"}

MISSING_MARKERS = {"-", "--", "null", "NULL", "Null", "N/A", "n/a", "NA", "nan", "NaN", "없음", "미상", "해당없음",
                   "-999", "-9999", "9999", ".", "?"}
KEY_SAMPLE_CAP = 5000
SAMPLE_ROWS = 20

_DATE_PATTERNS: list[tuple[str, re.Pattern[str], bool]] = [
    # (라벨, 패턴, ISO 8601 여부)
    ("YYYY-MM-DDTHH:MM:SS", re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$"), True),
    ("YYYY-MM-DD HH:MM:SS", re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2}(\.\d+)?)?$"), False),
    ("YYYY-MM-DD", re.compile(r"^\d{4}-\d{2}-\d{2}$"), True),
    ("YYYY.MM.DD", re.compile(r"^\d{4}\.\s?\d{1,2}\.\s?\d{1,2}\.?( \d{1,2}:\d{2}(:\d{2})?)?$"), False),
    ("YYYY/MM/DD", re.compile(r"^\d{4}/\d{1,2}/\d{1,2}( \d{1,2}:\d{2}(:\d{2})?)?$"), False),
    ("YYYY년 MM월 DD일", re.compile(r"^\d{4}년\s?\d{1,2}월(\s?\d{1,2}일)?"), False),
    ("YYYYMMDDHHMMSS", re.compile(r"^(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])([01]\d|2[0-3])[0-5]\d[0-5]\d$"), False),
    ("YYYYMMDDHHMM", re.compile(r"^(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])([01]\d|2[0-3])[0-5]\d$"), False),
    ("YYYYMMDD", re.compile(r"^(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])$"), False),
]
_DATE_NAME = re.compile(r"일시|일자|날짜|시각|시간|연도|년도|년월|기준일|등록일|수정일|발생일|DATE|DT$|_DT_|_DT|TIME|TM$|YMD|YYYYMM|YEAR", re.I)
_YM = re.compile(r"^(19|20)\d{2}(0[1-9]|1[0-2])$")
_Y = re.compile(r"^(19|20)\d{2}$")

_PII_NAME = re.compile(r"주민|성명|이름|전화|휴대|핸드폰|연락처|생년|이메일|email|e-mail|계좌|여권|운전면허|차량번호|차대번호|VIN", re.I)
_PII_VALUE: list[tuple[str, re.Pattern[str]]] = [
    ("주민등록번호", re.compile(r"^\d{6}-?[1-4]\d{6}$")),
    ("휴대전화", re.compile(r"^01[016789]-?\d{3,4}-?\d{4}$")),
    ("이메일", re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")),
    ("차량번호", re.compile(r"^(\d{2,3}[가-힣]\d{4}|[가-힣]{2}\d{1,2}[가-힣]\d{4})$")),
]

# 연계키 규칙: (코드, 컬럼명 패턴, 값 검사 함수 이름, 설명)
KEY_RULES: list[dict[str, Any]] = [
    {"code": "K1", "name": re.compile(r"행정구역|시도|시군구|읍면동|행정동|법정동|SIDO|SGG|SIGUNGU|EMD|ADM_?CD|ADM_?DR|BJD|지역코드|관할", re.I),
     "value": "admin_code", "label": "행정구역"},
    {"code": "K2", "name": re.compile(r"주소|소재지|도로명|지번|ADDR|ADRES", re.I), "value": "address", "label": "주소"},
    {"code": "K3", "name": re.compile(r"위도|경도|좌표|LAT|LON|LNG|X좌표|Y좌표|X_?CRD|Y_?CRD|GEOM|WKT|XCOORD|YCOORD", re.I),
     "value": "coordinate", "label": "좌표"},
    {"code": "K4", "name": re.compile(r"건축물|건물(ID|번호|관리)|BLDG|BULD|PNU|필지", re.I), "value": None, "label": "건축물ID"},
    {"code": "K5", "name": re.compile(r"링크|LINK|노드|NODE|도로(ID|번호|코드)|ROAD_?(ID|NO|CD)|노선(ID|번호|코드)", re.I),
     "value": None, "label": "도로링크"},
    {"code": "K6", "name": re.compile(r"차량|차대|자동차등록|VHCL|VEHICLE|CAR_?(NO|ID)|VIN|운행기록장치|OBU", re.I),
     "value": "vehicle", "label": "차량ID"},
    {"code": "K7", "name": _DATE_NAME, "value": "datetime", "label": "시각"},
    {"code": "K8", "name": re.compile(r"사업(ID|번호|코드|명)|과제|공사(ID|번호|코드)|PROJECT|PRJCT|BIZ_?(ID|NO)", re.I),
     "value": None, "label": "사업ID"},
    {"code": "K9", "name": re.compile(r"문서|DOC|관리번호|일련번호|접수번호|순번|^ID$|_ID$|^NO$|번호$", re.I),
     "value": None, "label": "문서ID"},
]
_ADMIN_CODE = re.compile(r"^\d{2}(\d{3})?(\d{3})?(\d{2})?$")  # 2/5/8/10자리
_ADDRESS = re.compile(r"(특별시|광역시|특별자치|[가-힣]+도\s|[가-힣]+시\s|[가-힣]+군\s|[가-힣]+구\s).*(로|길|동|리|읍|면)")


@dataclass
class ProfileResult:
    profile: dict[str, Any]
    key_candidates: list[dict[str, Any]] = field(default_factory=list)
    key_samples: dict[str, list[str]] = field(default_factory=dict)
    data_form: str = "정형"
    media_type: str | None = None


# ----------------------------------------------------------------- 파일 읽기
def _decode(raw: bytes) -> tuple[str, str]:
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-16"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8 (손상 문자 치환)"


def _read_delimited(path: Path, ext: str, max_rows: int, stem: str) -> tuple[list[tuple[str, pd.DataFrame]], list[str]]:
    raw = path.read_bytes()
    text, enc = _decode(raw)
    warnings: list[str] = []
    if enc not in ("utf-8-sig",):
        warnings.append(f"문자 인코딩 {enc} — UTF-8 이 아님")
    delim = "\t" if ext == "tsv" else ","
    if ext != "tsv":
        try:
            delim = csv.Sniffer().sniff(text[:65536], delimiters=",;\t|").delimiter
        except csv.Error:
            delim = ","
    df = pd.read_csv(io.StringIO(text), sep=delim, header=None, dtype=object, nrows=max_rows + 50,
                     keep_default_na=False, na_values=[""], engine="python", on_bad_lines="skip")
    return [(stem, df)], warnings


def _read_excel(path: Path, ext: str, max_rows: int) -> tuple[list[tuple[str, pd.DataFrame]], list[str]]:
    engine = "openpyxl" if ext == "xlsx" else "xlrd"
    sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object, nrows=max_rows + 50, engine=engine)
    return [(str(name), df) for name, df in sheets.items()], []


def _read_json(path: Path, max_rows: int, stem: str) -> tuple[list[tuple[str, pd.DataFrame]], list[str]]:
    text, _ = _decode(path.read_bytes())
    data = json.loads(text)
    tables: list[tuple[str, pd.DataFrame]] = []
    warnings: list[str] = []

    def to_frame(name: str, rows: list[Any]) -> None:
        recs = [r for r in rows[:max_rows] if isinstance(r, dict)]
        if recs:
            df = pd.json_normalize(recs).astype(object)
            tables.append((name, _with_header_row(df)))

    if isinstance(data, list):
        to_frame(stem, data)
    elif isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                to_frame(str(k), v)
        if not tables:
            tables.append((stem, _with_header_row(pd.json_normalize(data).astype(object))))
            warnings.append("단일 객체 JSON — 레코드 배열이 아니어서 1행으로 해석")
    if not tables:
        warnings.append("표 형태로 해석할 수 있는 레코드 배열을 찾지 못함")
    return tables, warnings


def _with_header_row(df: pd.DataFrame) -> pd.DataFrame:
    """컬럼명이 이미 있는 프레임을 header=None 형태(첫 행이 머리글)로 맞춘다."""
    head = pd.DataFrame([list(map(str, df.columns))], columns=range(len(df.columns)))
    body = df.copy()
    body.columns = range(len(df.columns))
    return pd.concat([head, body], ignore_index=True)


def _read_parquet(path: Path, max_rows: int, stem: str) -> tuple[list[tuple[str, pd.DataFrame]], list[str]]:
    df = pd.read_parquet(path).head(max_rows).astype(object)
    return [(stem, _with_header_row(df))], []


def _stem(filename: str) -> str:
    return filename.rsplit(".", 1)[0] if "." in filename else filename


def _read_tables(path: Path, ext: str, max_rows: int, stem: str) -> tuple[list[tuple[str, pd.DataFrame]], list[str]]:
    """(표 이름, 머리글 미지정 프레임) 목록. 표 이름은 엑셀은 시트명, 그 외는 원본 파일명이다."""
    if ext in ("xlsx", "xls"):
        return _read_excel(path, ext, max_rows)
    if ext in ("csv", "tsv"):
        return _read_delimited(path, ext, max_rows, stem)
    if ext == "json":
        return _read_json(path, max_rows, stem)
    return _read_parquet(path, max_rows, stem)


# ----------------------------------------------------------------- 머리글 탐지
def _is_blank(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    if v is pd.NaT:
        return True
    return isinstance(v, str) and v.strip() == ""


def _detect_header(df: pd.DataFrame) -> int:
    """앞쪽 15행 중 머리글 행을 고른다. 제목·설명 행이 위에 붙은 공공 엑셀 양식을 처리하기 위함."""
    limit = min(15, len(df))
    if limit == 0:
        return 0
    counts = [int(sum(not _is_blank(v) for v in df.iloc[i].tolist())) for i in range(limit)]
    width = max(counts) if counts else 0
    if width == 0:
        return 0
    for i in range(limit):
        row = [v for v in df.iloc[i].tolist() if not _is_blank(v)]
        if len(row) < max(2, math.ceil(width * 0.6)) and width > 1:
            continue
        if not all(isinstance(v, str) for v in row):
            continue
        if len(set(str(v).strip() for v in row)) < len(row) * 0.8:
            continue
        return i
    return 0


def _column_names(header: list[Any]) -> list[str]:
    """머리글 행에서 컬럼명을 만든다. 빈 칸은 '컬럼N', 중복은 '_2' 접미로 구분한다."""
    names: list[str] = []
    seen: Counter[str] = Counter()
    for i, h in enumerate(header):
        nm = re.sub(r"\s+", " ", _to_text(h)) if not _is_blank(h) else f"컬럼{i + 1}"
        seen[nm] += 1
        names.append(nm if seen[nm] == 1 else f"{nm}_{seen[nm]}")
    return names


# ----------------------------------------------------------------- 값 해석
def _to_text(v: Any) -> str:
    if isinstance(v, datetime):
        return v.isoformat(sep="T", timespec="seconds") if (v.hour or v.minute or v.second) else v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _num(text: str) -> float | None:
    t = text.replace(",", "")
    if not re.fullmatch(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?", t):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _date_format(text: str, name_hint: bool) -> tuple[str, bool] | None:
    for label, pat, iso in _DATE_PATTERNS:
        if pat.match(text):
            return label, iso
    if name_hint:
        if _YM.match(text):
            return "YYYYMM", False
        if _Y.match(text):
            return "YYYY", True
    return None


def _profile_column(name: str, values: list[Any]) -> dict[str, Any]:
    total = len(values)
    name_is_date = bool(_DATE_NAME.search(name))
    texts: list[str] = []
    markers: Counter[str] = Counter()
    native_dt = 0
    for v in values:
        if _is_blank(v):
            continue
        if isinstance(v, (datetime, date)):
            native_dt += 1
        t = _to_text(v)
        if t in MISSING_MARKERS:
            markers[t] += 1
            continue
        texts.append(t)
    blanks = total - len(texts) - sum(markers.values())
    present = len(texts)
    missing = total - present
    counter = Counter(texts)
    distinct = len(counter)

    nums = [n for n in (_num(t) for t in texts) if n is not None]
    fmt_counter: Counter[str] = Counter()
    iso_hits = 0
    for t in texts:
        f = _date_format(t, name_is_date)
        if f:
            fmt_counter[f[0]] += 1
            iso_hits += 1 if f[1] else 0
    date_hits = sum(fmt_counter.values())

    col_type = "string"
    if present:
        if date_hits / present >= 0.9 and (name_is_date or native_dt or not all(t.isdigit() for t in texts[:50])):
            col_type = "datetime"
        elif len(nums) / present >= 0.95:
            col_type = "integer" if all(float(n).is_integer() for n in nums) and not any("." in t for t in texts[:200]) else "number"
        elif distinct <= 2 and set(t.upper() for t in counter) <= {"Y", "N", "TRUE", "FALSE", "예", "아니오", "O", "X", "0", "1"}:
            col_type = "boolean"
    # 식별자성 숫자(자릿수 고정·앞자리 0)는 문자열로 본다
    if col_type == "integer" and any(len(t) > 1 and t.startswith("0") for t in texts[:200]):
        col_type = "string"

    out: dict[str, Any] = {
        "name": name,
        "type": col_type,
        "count": total,
        "missing": missing,
        "null_rate": round(missing / total, 4) if total else 0.0,
        "distinct": distinct,
        "unique": bool(present and distinct == present),
        "samples": [v for v, _ in counter.most_common(5)],
        "max_len": max((len(t) for t in texts), default=0),
        "missing_markers": [{"marker": m if m else "(공백)", "count": c} for m, c in markers.most_common()]
        + ([{"marker": "(빈 셀)", "count": blanks}] if blanks else []),
    }
    if col_type in ("integer", "number") and nums:
        out["min"], out["max"] = min(nums), max(nums)
    if col_type == "datetime":
        out["date_formats"] = [{"format": f, "count": c} for f, c in fmt_counter.most_common()]
        out["iso8601"] = bool(date_hits and iso_hits == date_hits)
        out["min"], out["max"] = min(texts), max(texts)
        interval = _infer_interval(texts)
        if interval:
            out["interval"] = interval
    pii = _detect_pii(name, texts)
    if pii:
        out["pii"] = pii
    return out


def _infer_interval(texts: list[str]) -> dict[str, Any] | None:
    """시각 컬럼의 관측 간격(중앙값)을 구해 해상도 라벨로 바꾼다."""
    try:
        ser = pd.to_datetime(pd.Series(sorted(set(texts))[:20000]), errors="coerce", format="mixed")
    except (ValueError, TypeError):
        return None
    ser = ser.dropna().sort_values()
    if len(ser) < 3:
        return None
    deltas = ser.diff().dropna().dt.total_seconds()
    deltas = deltas[deltas > 0]
    if deltas.empty:
        return None
    med = float(deltas.median())
    table = [(300, "5분", "PT5M"), (900, "15분", "PT15M"), (3600, "1시간", "PT1H"), (86400, "일", "P1D"),
             (604800, "주", "P1W"), (2629800, "월", "P1M"), (7889400, "분기", "P3M"), (31557600, "연", "P1Y")]
    best = min(table, key=lambda x: abs(math.log(med / x[0])))
    if abs(math.log(med / best[0])) > math.log(1.6):
        return {"seconds": med, "label": None, "duration": None}
    return {"seconds": med, "label": best[1], "duration": best[2]}


def _detect_pii(name: str, texts: list[str]) -> dict[str, Any] | None:
    sample = texts[:500]
    for label, pat in _PII_VALUE:
        if sample and sum(1 for t in sample if pat.match(t)) / len(sample) >= 0.5:
            return {"kind": label, "basis": "값 패턴"}
    m = _PII_NAME.search(name)
    if m:
        return {"kind": m.group(0), "basis": "컬럼명"}
    return None


# ----------------------------------------------------------------- 연계키 후보
def _value_score(kind: str | None, col: dict[str, Any], texts: list[str]) -> tuple[float, str]:
    if not kind or not texts:
        return 0.0, ""
    sample = texts[:1000]
    n = len(sample)
    if kind == "datetime":
        return (0.4, "시각 형식 값") if col["type"] == "datetime" else (0.0, "")
    if kind == "admin_code":
        hit = sum(1 for t in sample if _ADMIN_CODE.match(t)) / n
        return (0.35, "행정구역 코드 자릿수(2·5·8·10) 일치") if hit >= 0.9 else (0.0, "")
    if kind == "address":
        hit = sum(1 for t in sample if _ADDRESS.search(t)) / n
        return (0.35, "주소 문자열 패턴") if hit >= 0.6 else (0.0, "")
    if kind == "coordinate":
        nums = [x for x in (_num(t) for t in sample) if x is not None]
        if len(nums) / n >= 0.95 and nums:
            lo, hi = min(nums), max(nums)
            if (33 <= lo and hi <= 39.5) or (124 <= lo and hi <= 132):
                return 0.4, "한반도 경위도 범위"
            if 100000 <= lo and hi <= 2200000:
                return 0.3, "평면직각좌표 범위"
        if sum(1 for t in sample if t.upper().startswith(("POINT", "LINESTRING", "POLYGON", "MULTI"))) / n >= 0.9:
            return 0.4, "WKT 도형"
        return 0.0, ""
    if kind == "vehicle":
        hit = sum(1 for t in sample if _PII_VALUE[3][1].match(t.replace(" ", ""))) / n
        return (0.35, "차량번호 형식") if hit >= 0.6 else (0.0, "")
    return 0.0, ""


def _key_candidates(table: str, cols: list[dict[str, Any]], col_texts: dict[str, list[str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for col in cols:
        texts = col_texts.get(col["name"], [])
        for rule in KEY_RULES:
            name_hit = bool(rule["name"].search(col["name"]))
            v_score, v_reason = _value_score(rule["value"], col, texts)
            if rule["code"] == "K7" and col["type"] == "datetime":
                score, reasons = 0.55 + (0.3 if name_hit else 0.0), ["시각 형식 값"] + (["컬럼명 일치"] if name_hit else [])
            elif name_hit:
                score, reasons = 0.55 + v_score, ["컬럼명 일치"] + ([v_reason] if v_reason else [])
                # 값 패턴 규칙이 없는 식별자형 키(도로링크·건축물·사업·문서)는 값의 식별력으로 보강한다
                present = col["count"] - col["missing"]
                if rule["value"] is None and present and col["distinct"] / present >= 0.5:
                    score += 0.25
                    reasons.append(f"고유값 비율 {col['distinct'] / present:.0%}")
            elif v_score >= 0.35:
                score, reasons = 0.2 + v_score, [v_reason]
            else:
                continue
            # 결합 축으로 쓰려면 값이 있어야 한다
            if col["null_rate"] > 0.5:
                score -= 0.2
                reasons.append(f"결측률 {col['null_rate']:.0%}")
            if rule["code"] == "K9" and not col["unique"]:
                score -= 0.15
            score = round(max(0.05, min(0.99, score)), 2)
            out.append({"code": rule["code"], "label": rule["label"], "table": table, "column": col["name"],
                        "score": score, "reason": " · ".join(reasons)})
    # 같은 컬럼이 여러 키에 걸리면 점수 높은 것만, K9 는 다른 키가 없을 때만
    best: dict[str, dict[str, Any]] = {}
    for c in sorted(out, key=lambda x: -x["score"]):
        if c["column"] not in best:
            best[c["column"]] = c
    return list(best.values())


def normalize_key_value(text: str) -> str:
    return re.sub(r"\s+", "", str(text)).upper()


# ----------------------------------------------------------------- 진입점
def classify_ext(filename: str) -> str:
    return (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()


def profile_file(path: Path, filename: str, max_rows: int = 50_000) -> ProfileResult:
    ext = classify_ext(filename)
    media_type = MEDIA_TYPES.get(ext)
    data_form = DATA_FORMS.get(ext, "비정형")
    if ext not in TABULAR_EXTS:
        return ProfileResult(
            profile={"status": "unsupported", "tables": [],
                     "warnings": [f".{ext or '?'} 형식은 표 구조 프로파일 대상이 아닙니다 — 메타데이터는 수기로 작성하세요"]},
            data_form=data_form, media_type=media_type)
    try:
        frames, warnings = _read_tables(path, ext, max_rows, _stem(filename))
    except Exception as exc:  # noqa: BLE001 - 사용자 파일은 어떤 형태로든 깨져 있을 수 있다
        return ProfileResult(
            profile={"status": "error", "tables": [], "warnings": [], "error": f"{type(exc).__name__}: {exc}"[:400]},
            data_form=data_form, media_type=media_type)

    tables: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    samples: dict[str, list[str]] = {}
    for tname, df in frames:
        df = df.dropna(how="all").dropna(axis=1, how="all")
        if df.empty:
            continue
        orig_rows = [int(i) for i in df.index]  # 빈 행을 지우기 전의 원본 행 번호
        df = df.reset_index(drop=True)
        hrow = _detect_header(df)
        names = _column_names(df.iloc[hrow].tolist())
        body = df.iloc[hrow + 1:].reset_index(drop=True)
        truncated = len(body) > max_rows
        body = body.head(max_rows)
        cols: list[dict[str, Any]] = []
        col_texts: dict[str, list[str]] = {}
        for i, nm in enumerate(names):
            vals = body.iloc[:, i].tolist()
            cols.append(_profile_column(nm, vals))
            col_texts[nm] = [_to_text(v) for v in vals if not _is_blank(v) and _to_text(v) not in MISSING_MARKERS]
        kc = _key_candidates(tname, cols, col_texts)
        for c in kc:
            vals = Counter(normalize_key_value(t) for t in col_texts.get(c["column"], []))
            keep = [v for v, _ in vals.most_common(KEY_SAMPLE_CAP)]
            samples[f"{tname}|{c['column']}"] = keep
            c["distinct"] = len(vals)
            c["sampled"] = len(vals) > KEY_SAMPLE_CAP
        candidates.extend(kc)
        preamble = [" ".join(_to_text(v) for v in df.iloc[i].tolist() if not _is_blank(v))[:200] for i in range(hrow)]
        tables.append({
            "name": tname,
            "rows": int(len(body)),
            "truncated": truncated,
            "header_row": orig_rows[hrow] + 1,
            "preamble": [p for p in preamble if p],
            "columns": cols,
            "sample_rows": [[("" if _is_blank(v) else _to_text(v))[:120] for v in row]
                            for row in body.head(SAMPLE_ROWS).values.tolist()],
        })

    for t in tables:
        fmts = {f["format"] for c in t["columns"] if c["type"] == "datetime" for f in c.get("date_formats", [])}
        if len(fmts) > 1:
            warnings.append(f"[{t['name']}] 시간 포맷 {len(fmts)}종 혼재: {', '.join(sorted(fmts))}")
        marks = {m["marker"] for c in t["columns"] for m in c["missing_markers"]}
        if len(marks) > 1:
            warnings.append(f"[{t['name']}] 결측 표기 {len(marks)}종 혼재: {', '.join(sorted(marks))}")
        pii = [c["name"] for c in t["columns"] if c.get("pii")]
        if pii:
            warnings.append(f"[{t['name']}] 개인정보 의심 컬럼: {', '.join(pii[:8])}")
    status = "ok" if tables else "empty"
    return ProfileResult(
        profile={"status": status, "tables": tables, "warnings": warnings},
        key_candidates=sorted(candidates, key=lambda c: (-c["score"], c["code"])),
        key_samples=samples, data_form=data_form, media_type=media_type)


def human_size(n: int | None) -> str:
    if not n:
        return "0 KB"
    if n > 1048576:
        return f"{n / 1048576:.1f} MB"
    return f"{max(1, round(n / 1024))} KB"


def profile_summary(profile: dict[str, Any]) -> str:
    st = profile.get("status")
    if st == "ok":
        tables = profile.get("tables", [])
        cols = sum(len(t["columns"]) for t in tables)
        rows = sum(t["rows"] for t in tables)
        head = f"표 {len(tables)}개 · " if len(tables) > 1 else ""
        return f"{head}스키마 {cols}컬럼 · {rows:,}행 (실측)"
    if st == "error":
        return "프로파일 실패 — 파일을 읽을 수 없음"
    if st == "empty":
        return "데이터 행 없음"
    if st == "stream":
        return f"스트림 스키마 {len(profile.get('tables', [{}])[0].get('columns', []))}필드 (등록값)"
    return "표 구조 프로파일 대상 아님"


def profile_stream(fields: list[dict[str, Any]]) -> ProfileResult:
    """스트림은 값을 읽을 수 없으므로 등록된 스키마(필드명·타입)만으로 구조와 연계키 후보를 만든다."""
    cols = [{"name": str(f.get("name", "")).strip(), "type": str(f.get("type") or "string"), "count": 0, "missing": 0,
             "null_rate": 0.0, "distinct": 0, "unique": False, "samples": [], "max_len": 0, "missing_markers": []}
            for f in fields if str(f.get("name", "")).strip()]
    for c in cols:
        pii = _detect_pii(c["name"], [])
        if pii:
            c["pii"] = pii
    cands = _key_candidates("stream", cols, {})
    for c in cands:
        c["distinct"], c["sampled"] = 0, False
    return ProfileResult(
        profile={"status": "stream", "tables": [{"name": "stream", "rows": 0, "truncated": False, "header_row": 0,
                                                 "preamble": [], "columns": cols, "sample_rows": []}],
                 "warnings": [] if cols else ["스키마 필드가 등록되지 않았습니다"]},
        key_candidates=sorted(cands, key=lambda c: (-c["score"], c["code"])), data_form="실시간 스트림")


def read_column(path: Path, filename: str, table: str, column: str, max_rows: int = 200_000) -> list[str] | None:
    """결합 통계 계산용: 파일에서 특정 표·컬럼의 정규화 고유값을 읽는다."""
    ext = classify_ext(filename)
    if ext not in TABULAR_EXTS:
        return None
    try:
        frames, _ = _read_tables(path, ext, max_rows, _stem(filename))
    except Exception:  # noqa: BLE001
        return None
    for tname, df in frames:
        if tname != table:
            continue
        df = df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
        if df.empty:
            return []
        hrow = _detect_header(df)
        names = _column_names(df.iloc[hrow].tolist())
        if column not in names:
            return None
        vals = df.iloc[hrow + 1:, names.index(column)].tolist()
        return sorted({normalize_key_value(_to_text(v)) for v in vals if not _is_blank(v) and _to_text(v) not in MISSING_MARKERS})
    return None
