"""규칙 기반 추천.

LLM 을 쓰지 않는다. 업로드 파일의 실제 프로파일(컬럼명·값 표본)에서 계산한 근거만으로
조합 추천, 조합 경고, 설명 초안, 분류 추천, 결합 후보를 만든다. 모든 추천에는 계산 근거를 문장으로 붙인다.
"""
from __future__ import annotations

import itertools
import re
from typing import Any

from ..models import Asset, Process, ProcessDataset

KEY_LABEL = {"K1": "행정구역", "K2": "주소", "K3": "좌표", "K4": "건축물ID", "K5": "도로링크", "K6": "차량ID",
             "K7": "시각", "K8": "사업ID", "K9": "문서ID"}


# ------------------------------------------------------------------ 공통
def asset_keys(asset: Asset, min_score: float = 0.5) -> dict[str, dict[str, Any]]:
    """원천이 가진 연계키 코드별 최고 후보."""
    best: dict[str, dict[str, Any]] = {}
    for c in asset.key_candidates or []:
        if c["score"] >= min_score and (c["code"] not in best or c["score"] > best[c["code"]]["score"]):
            best[c["code"]] = c
    return best


def overlap(a: Asset, ca: dict[str, Any], b: Asset, cb: dict[str, Any]) -> dict[str, Any] | None:
    """두 컬럼의 정규화 고유값 표본 교집합 통계 (실측)."""
    va = (a.key_samples or {}).get(f"{ca['table']}|{ca['column']}")
    vb = (b.key_samples or {}).get(f"{cb['table']}|{cb['column']}")
    if not va or not vb:
        return None
    sa, sb = set(va), set(vb)
    matched = len(sa & sb)
    return {
        "source_distinct": len(sa), "target_distinct": len(sb), "matched": matched,
        "source_match_rate": round(matched / len(sa), 4), "target_match_rate": round(matched / len(sb), 4),
        "sampled": bool(ca.get("sampled") or cb.get("sampled")),
    }


def pair_links(a: Asset, b: Asset) -> list[dict[str, Any]]:
    """두 원천 사이의 결합 후보 (같은 연계키 코드를 공유하는 컬럼 쌍)."""
    ka, kb = asset_keys(a, 0.4), asset_keys(b, 0.4)
    out = []
    for code in sorted(set(ka) & set(kb)):
        st = overlap(a, ka[code], b, kb[code]) if a.kind != "stream" and b.kind != "stream" else None
        base = min(ka[code]["score"], kb[code]["score"])
        # 값이 실제로 겹치면 가점, 전혀 안 겹치면 감점. 시각(K7)은 값 일치보다 축 공유가 의미이므로 감점하지 않는다.
        if st:
            rate = max(st["source_match_rate"], st["target_match_rate"])
            score = base * 0.5 + rate * 0.5 if code != "K7" else base * 0.5 + rate * 0.3
        else:
            score = base * 0.6
        out.append({"code": code, "label": KEY_LABEL.get(code, code),
                    "source": {"table": ka[code]["table"], "column": ka[code]["column"]},
                    "target": {"table": kb[code]["table"], "column": kb[code]["column"]},
                    "score": round(score, 2), "stats": st})
    return sorted(out, key=lambda x: -x["score"])


# ------------------------------------------------------------------ STEP 1 조합 추천
def combo_suggestions(assets: list[Asset]) -> list[dict[str, Any]]:
    """선택한 후보에서 연계키를 공유하는 연결 묶음을 찾아 점수와 근거를 붙인다."""
    if len(assets) < 2:
        return []
    links: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for a, b in itertools.combinations(assets, 2):
        pl = pair_links(a, b)
        if pl:
            links[(a.id, b.id)] = pl
    # 연결 요소
    parent = {a.id: a.id for a in assets}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (x, y), pl in links.items():
        if pl[0]["score"] >= 0.35:
            parent[find(x)] = find(y)
    groups: dict[int, list[Asset]] = {}
    for a in assets:
        groups.setdefault(find(a.id), []).append(a)
    by_id = {a.id: a for a in assets}
    out = []
    for members in groups.values():
        if len(members) < 2:
            continue
        ids = {m.id for m in members}
        edges = [(pair, pl[0]) for pair, pl in links.items() if pair[0] in ids and pair[1] in ids]
        if not edges:
            continue
        score = sum(e["score"] for _, e in edges) / len(edges)
        shared = sorted({e["code"] for _, e in edges})
        reasons = []
        for (x, y), e in sorted(edges, key=lambda t: -t[1]["score"])[:6]:
            st = e["stats"]
            detail = (f"값 일치 {st['matched']:,}건 ({max(st['source_match_rate'], st['target_match_rate']):.0%})"
                      if st else "값 표본 없음 — 컬럼 규칙 기준")
            reasons.append(f"{by_id[x].name} ↔ {by_id[y].name}: {e['code']} {e['label']} "
                           f"({e['source']['column']} = {e['target']['column']}) · {detail}")
        out.append({
            "asset_ids": sorted(ids),
            "names": [m.name for m in members],
            "shared_keys": [{"code": c, "label": KEY_LABEL.get(c, c)} for c in shared],
            "score": round(score, 2),
            "confidence": round(score * 100),
            "reasons": reasons,
            "method": "규칙 기반 — 연계키 후보 공유 + 값 표본 일치율",
        })
    return sorted(out, key=lambda s: (-len(s["asset_ids"]), -s["score"]))


# ------------------------------------------------------------------ STEP 2
def combo_warnings(process: Process) -> list[dict[str, Any]]:
    """조합 보정 경고 (규칙엔진)."""
    combo = process.combo
    out: list[dict[str, Any]] = []
    assets = [d.asset for d in combo]
    for d in combo:
        a = d.asset
        prof = a.profile or {}
        if a.kind == "dataset" and prof.get("status") == "error":
            out.append({"level": "error", "dataset_id": d.id, "name": a.name, "code": "PROFILE_ERROR",
                        "message": f"프로파일 실패 — 파일을 읽을 수 없습니다 ({prof.get('error', '')[:120]})"})
        if a.kind == "dataset" and prof.get("status") in ("empty",):
            out.append({"level": "error", "dataset_id": d.id, "name": a.name, "code": "EMPTY",
                        "message": "데이터 행이 없습니다"})
        for w in prof.get("warnings", []):
            out.append({"level": "warn", "dataset_id": d.id, "name": a.name, "code": "PROFILE", "message": w})
        if not asset_keys(a, 0.4) and prof.get("status") == "ok":
            out.append({"level": "warn", "dataset_id": d.id, "name": a.name, "code": "NO_KEY",
                        "message": "연계키 후보를 찾지 못했습니다 — STEP 4 에서 수기 배정이 필요합니다"})
    if len(combo) >= 2:
        for d in combo:
            others = [o for o in assets if o.id != d.asset_id]
            if not any(pair_links(d.asset, o) for o in others):
                out.append({"level": "warn", "dataset_id": d.id, "name": d.asset.name, "code": "ISOLATED",
                            "message": "조합 내 다른 데이터셋과 공유하는 연계키가 없습니다 — 결합 근거를 확인하세요"})
    seen: dict[str, str] = {}
    for d in combo:
        if d.asset.sha256:
            if d.asset.sha256 in seen:
                out.append({"level": "warn", "dataset_id": d.id, "name": d.asset.name, "code": "DUPLICATE",
                            "message": f"「{seen[d.asset.sha256]}」와 내용이 같은 파일입니다 (SHA-256 일치)"})
            seen[d.asset.sha256] = d.asset.name
    return out


def description_draft(process: Process) -> dict[str, str]:
    """조합 제목·설명 초안 (템플릿). 사람이 확인하고 고치는 것을 전제로 한다."""
    combo = process.combo
    names = [d.asset.name for d in combo]
    if not names:
        return {"title": "", "description": ""}
    counts: dict[str, int] = {}
    for d in combo:
        for c in asset_keys(d.asset):
            counts[c] = counts.get(c, 0) + 1
    keys = sorted(c for c, n in counts.items() if n >= 2)  # 둘 이상이 함께 가진 키만 '공유'다
    streams = [d.asset.name for d in combo if d.asset.kind == "stream"]
    title = names[0] if len(names) == 1 else f"{_short(names[0])} 외 {len(names) - 1}건 조합"
    parts = [f"{', '.join(_short(n) for n in names[:4])}{' 등' if len(names) > 4 else ''} {len(names)}개 데이터셋의 조합."]
    if keys:
        parts.append("공유 연계키: " + ", ".join(f"{k} {KEY_LABEL.get(k, '')}".strip() for k in keys) + ".")
    if streams:
        parts.append(f"실시간 스트림 {len(streams)}건 포함.")
    rows = sum(t.get("rows", 0) for d in combo for t in (d.asset.profile or {}).get("tables", []))
    if rows:
        parts.append(f"파일형 데이터 합계 {rows:,}행 (프로파일 실측).")
    return {"title": title, "description": " ".join(parts)}


def _short(name: str) -> str:
    return re.sub(r"^sample_", "", name)[:30]


# ------------------------------------------------------------------ STEP 4 분류 추천
_F1_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("F1-02", re.compile(r"도로|링크|노선|ROAD|교차로|터널|교량", re.I)),
    ("F1-01", re.compile(r"교통|소통|운행|차량|OBU|텔레메|eTAS|사고|버스|택시|통행|TRAFFIC", re.I)),
    ("F1-03", re.compile(r"철도|열차|역사|지하철|RAIL", re.I)),
    ("F1-04", re.compile(r"항공|공항|비행|AIR", re.I)),
    ("F1-05", re.compile(r"물류|창고|화물|택배", re.I)),
    ("F1-06", re.compile(r"도시|용도지역|지구단위|도시계획", re.I)),
    ("F1-07", re.compile(r"주택|토지|부동산|아파트|필지|건축", re.I)),
    ("F1-08", re.compile(r"건설|안전점검|공사|시설물", re.I)),
    ("F1-09", re.compile(r"수자원|하천|댐|수위|강수|WATER", re.I)),
]


def classification_suggestions(pd: ProcessDataset) -> list[dict[str, Any]]:
    """축별 코드 추천. score 는 0~100, reason 은 계산 근거."""
    a = pd.asset
    prof = a.profile or {}
    tables = prof.get("tables", [])
    cols = [c for t in tables for c in t.get("columns", [])]
    col_names = " ".join(c["name"] for c in cols)
    title = (pd.meta or {}).get("title") or a.name
    text = f"{title} {a.name} {(pd.meta or {}).get('description', '')}"
    out: list[dict[str, Any]] = []

    # F1 — 이름·컬럼명 키워드
    hits = 0
    for code, pat in _F1_RULES:
        in_name = len(pat.findall(text))
        in_cols = len(pat.findall(col_names))
        if in_name or in_cols:
            hits += 1
            score = min(97, 55 + in_name * 20 + min(in_cols, 4) * 6)
            basis = []
            if in_name:
                basis.append(f"이름·설명 키워드 {in_name}회")
            if in_cols:
                basis.append(f"컬럼명 키워드 {in_cols}회")
            out.append({"axis": "F1", "code": code, "score": score, "reason": " · ".join(basis)})
    if not hits:
        out.append({"axis": "F1", "code": "F1-10", "score": 40, "reason": "주제 키워드 미검출 — 기타로 제안"})

    # F2 — 형태·컬럼 타입
    keys = asset_keys(a, 0.5)
    if a.kind == "stream":
        out.append({"axis": "F2", "code": "F2-06", "score": 99, "reason": "스트림으로 등록된 원천"})
        out.append({"axis": "F2", "code": "F2-04", "score": 85, "reason": "event-time 기반 관측 스트림"})
    else:
        form_map = {"정형": ("F2-01", 97), "반정형": ("F2-02", 95), "비정형": ("F2-03", 90)}
        if a.data_form in form_map:
            code, sc = form_map[a.data_form]
            out.append({"axis": "F2", "code": code, "score": sc, "reason": f"파일 형식 .{a.ext} → {a.data_form}"})
        dt_cols = [c for c in cols if c["type"] == "datetime"]
        num_cols = [c for c in cols if c["type"] in ("integer", "number")]
        # 시계열: 일정 간격의 시각 컬럼이 행을 구분할 만큼 촘촘해야 한다 (기준일자처럼 반복되는 날짜는 제외)
        series = [c for c in dt_cols if c.get("interval") and (c["count"] - c["missing"]) and c["distinct"] / (c["count"] - c["missing"]) >= 0.5]
        if series and num_cols:
            out.append({"axis": "F2", "code": "F2-04", "score": 82,
                        "reason": f"시각 컬럼 {series[0]['name']} + 수치 컬럼 {len(num_cols)}개 · 일정 관측 간격"})
        elif dt_cols and num_cols:
            out.append({"axis": "F2", "code": "F2-04", "score": 45,
                        "reason": f"시각 컬럼 {dt_cols[0]['name']} 존재 — 관측 시계열인지 확인 필요"})
        if "K3" in keys or "K5" in keys or "K1" in keys:
            k = "K3" if "K3" in keys else ("K5" if "K5" in keys else "K1")
            out.append({"axis": "F2", "code": "F2-05", "score": 88 if k == "K3" else 70,
                        "reason": f"{k} {KEY_LABEL[k]} 컬럼 {keys[k]['column']} 보유"})
        if a.ext in ("jpg", "jpeg", "png", "tif", "tiff", "mp4", "avi"):
            out.append({"axis": "F2", "code": "F2-07", "score": 95, "reason": f"파일 형식 .{a.ext}"})

    # F3 — 연계키와 관측 간격
    if "K5" in keys:
        out.append({"axis": "F3", "code": "F3-01", "score": 90, "reason": f"도로링크 컬럼 {keys['K5']['column']}"})
    if "K1" in keys:
        lens = {len(s) for s in (a.key_samples or {}).get(f"{keys['K1']['table']}|{keys['K1']['column']}", [])[:500]}
        code, why = ("F3-02", "행정동(8·10자리 코드)") if lens & {8, 10} else (("F3-03", "시군구(5자리 코드)") if 5 in lens else
                                                                       (("F3-04", "시도(2자리 코드)") if 2 in lens else ("F3-03", "행정구역 컬럼")))
        out.append({"axis": "F3", "code": code, "score": 80, "reason": f"{keys['K1']['column']} — {why}"})
    if "K3" in keys:
        out.append({"axis": "F3", "code": "F3-07", "score": 78, "reason": f"좌표 컬럼 {keys['K3']['column']}"})
    dur_code = {"PT5M": "F3-08", "PT15M": "F3-09", "PT1H": "F3-10", "P1D": "F3-11", "P1W": "F3-12", "P1M": "F3-13",
                "P3M": "F3-14", "P1Y": "F3-15"}
    if a.kind == "stream":
        tr = (pd.meta or {}).get("temporal_resolution") or (a.stream or {}).get("temporal_resolution")
        if tr in dur_code:
            out.append({"axis": "F3", "code": dur_code[tr], "score": 95, "reason": f"temporalResolution {tr} 선언과 동기화"})
        else:
            out.append({"axis": "F3", "code": "F3-16", "score": 85, "reason": "실시간 스트림"})
    else:
        for c in cols:
            iv = c.get("interval")
            if iv and iv.get("duration") in dur_code:
                present = c["count"] - c["missing"]
                dense = bool(present) and c["distinct"] / present >= 0.5
                out.append({"axis": "F3", "code": dur_code[iv["duration"]], "score": 84 if dense else 50,
                            "reason": f"{c['name']} 값 간격 중앙값 {iv['seconds']:.0f}초 → {iv['label']}"
                                      + ("" if dense else " (반복되는 날짜 — 관측 주기인지 확인 필요)")})
                break

    # K — 프로파일 후보 그대로
    for code, c in sorted(keys.items()):
        out.append({"axis": "K", "code": code, "score": round(c["score"] * 100), "reason": c["reason"],
                    "table": c["table"], "column": c["column"]})

    # N2SF — 개인정보 의심 컬럼 유무 (판단은 사람이 한다)
    pii = [c["name"] for c in cols if c.get("pii")]
    if pii:
        out.append({"axis": "N2SF", "code": "N2SF-S", "score": 80,
                    "reason": f"개인정보 의심 컬럼 {len(pii)}개 ({', '.join(pii[:4])}) — 필터링 투영 조건부 검토"})
    elif tables:
        out.append({"axis": "N2SF", "code": "N2SF-O", "score": 60, "reason": "개인정보 의심 컬럼 미검출 — 개방 가능 여부는 담당자 확인 필요"})
    return sorted(out, key=lambda s: (s["axis"], -s["score"]))


def meta_proposals(asset: Asset) -> dict[str, Any]:
    """조합 편입 시 메타데이터 초기 제안값 (승인 대상 필드는 승인 전까지 정본에 들어가지 않는다)."""
    meta: dict[str, Any] = {"title": asset.name, "language": "ko"}
    auto = ["title", "language"]
    if asset.description:
        meta["description"] = asset.description
        auto.append("description")
    if asset.org_id:
        meta["publisher_org_id"] = asset.org_id
        auto.append("publisher_org_id")
    if asset.kind == "stream":
        st = asset.stream or {}
        for src, dst in (("temporal_resolution", "temporal_resolution"), ("event_time_column", "event_time_column"),
                         ("endpoint_url", "endpoint_url"), ("timezone", "timezone")):
            if st.get(src):
                meta[dst] = st[src]
                auto.append(dst)
    else:
        if asset.media_type:
            meta["media_type"] = asset.media_type
            auto.append("media_type")
        dts = [c for t in (asset.profile or {}).get("tables", []) for c in t["columns"] if c["type"] == "datetime" and c.get("min")]
        if dts:
            c = max(dts, key=lambda c: c["count"] - c["missing"])
            lo, hi = _to_date(c["min"]), _to_date(c["max"])
            if lo and hi:
                meta["temporal_start"], meta["temporal_end"] = lo, hi
                auto += ["temporal_start", "temporal_end"]
    meta["_auto"] = auto
    return meta


def _to_date(v: str) -> str | None:
    m = re.match(r"^(\d{4})[-./]?(\d{2})[-./]?(\d{2})", str(v))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None
