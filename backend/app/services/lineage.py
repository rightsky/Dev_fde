"""STEP 5: 관계 후보·결합 통계·LPG 투영.

정본은 RDF 이고 LPG(노드·엣지)는 화면 표시용 파생 표현이다. 그래프는 저장된 데이터(조합·배포본·프로파일·관계·활동)에서
매번 다시 만든다.
"""
from __future__ import annotations

import itertools
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Activity, Asset, Organization, Process, ProcessDataset, Relation
from . import minting, storage, suggest
from .profiling import read_column


def _values(asset: Asset, table: str | None, column: str | None) -> list[str] | None:
    if not table or not column or asset.kind == "stream":
        return None
    cached = (asset.key_samples or {}).get(f"{table}|{column}")
    cand = next((c for c in asset.key_candidates or [] if c["table"] == table and c["column"] == column), None)
    if cached is not None and cand is not None and not cand.get("sampled"):
        return cached
    if asset.storage_key and asset.filename:
        vals = read_column(storage.path_of(asset.storage_key), asset.filename, table, column)
        if vals is not None:
            return vals
    return cached


def join_stats(rel: Relation) -> dict[str, Any]:
    """두 컬럼의 실제 값으로 결합 통계를 계산한다 (정규화: 공백 제거·대문자)."""
    a = _values(rel.source.asset, rel.source_table, rel.source_column)
    b = _values(rel.target.asset, rel.target_table, rel.target_column)
    if a is None or b is None:
        return {"computed": False,
                "reason": "스트림 또는 값을 읽을 수 없는 컬럼 — 결합 통계를 계산하지 않았습니다"}
    sa, sb = set(a), set(b)
    matched = len(sa & sb)
    return {
        "computed": True,
        "source_distinct": len(sa), "target_distinct": len(sb), "matched": matched,
        "source_match_rate": round(matched / len(sa), 4) if sa else 0.0,
        "target_match_rate": round(matched / len(sb), 4) if sb else 0.0,
        "unmatched_samples": sorted(sa - sb)[:5],
    }


def candidates(process: Process) -> list[dict[str, Any]]:
    """조합 데이터셋 쌍마다 결합 후보를 계산한다."""
    out = []
    existing = {(r.source_id, r.target_id, r.key_code) for r in process.relations if r.type == "JOINED_ON"}
    for a, b in itertools.combinations(process.combo, 2):
        for link in suggest.pair_links(a.asset, b.asset):
            used = (a.id, b.id, link["code"]) in existing or (b.id, a.id, link["code"]) in existing
            out.append({"source_id": a.id, "source_name": _title(a), "target_id": b.id, "target_name": _title(b),
                        "key_code": link["code"], "key_label": link["label"],
                        "source_table": link["source"]["table"], "source_column": link["source"]["column"],
                        "target_table": link["target"]["table"], "target_column": link["target"]["column"],
                        "score": link["score"], "stats": link["stats"], "already": used})
    return sorted(out, key=lambda c: (c["already"], -c["score"]))


def _title(pd: ProcessDataset) -> str:
    return (pd.meta or {}).get("title") or pd.asset.name


def relation_out(rel: Relation) -> dict[str, Any]:
    return {
        "id": rel.id, "type": rel.type, "status": rel.status, "priority": rel.priority,
        "source_id": rel.source_id, "source_name": _title(rel.source),
        "target_id": rel.target_id, "target_name": _title(rel.target),
        "key_code": rel.key_code, "key_label": suggest.KEY_LABEL.get(rel.key_code or "", None),
        "source_table": rel.source_table, "source_column": rel.source_column,
        "target_table": rel.target_table, "target_column": rel.target_column,
        "note": rel.note, "stats": rel.stats or {},
        "iri": minting.relation_iri(rel.id),
        "created_at": rel.created_at, "confirmed_at": rel.confirmed_at,
    }


# ------------------------------------------------------------------ LPG 투영
def graph(db: Session, process: Process, level: int) -> dict[str, Any]:
    """granularity 1 조합·데이터셋 / 2 프로버넌스 / 3 배포본·표 / 4 컬럼."""
    mode = "publish" if process.pub_mode else "draft"
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def node(nid: str, type_: str, label: str, sub: str = "", **extra: Any) -> str:
        nodes.setdefault(nid, {"id": nid, "type": type_, "label": label, "sub": sub, **extra})
        return nid

    seen_edges: set[tuple[str, str, str, Any]] = set()

    def edge(src: str, dst: str, type_: str, label: str = "", **extra: Any) -> None:
        key = (src, dst, type_, extra.get("relation_id"))
        if key in seen_edges:  # 같은 컬럼이 키 배정과 결합에 함께 쓰이면 구조 엣지가 두 번 요청된다
            return
        seen_edges.add(key)
        edges.append({"id": f"e{len(edges) + 1}", "source": src, "target": dst, "type": type_, "label": label, **extra})

    combo = process.combo
    ds_node: dict[int, str] = {}
    if process.combo_title:
        col = node("collection", "Collection", process.combo_title, minting.collection_id(process, mode),
                   detail={"설명": process.combo_description or ""})
    else:
        col = None
    for pd in combo:
        rid, minted = minting.resource_id(db, pd, mode)
        a = pd.asset
        keys = [k.get("code") for k in (pd.classification or {}).get("K", [])]
        nid = node(f"ds{pd.id}", "Service" if a.kind == "stream" else "Dataset", _title(pd), rid, dataset_id=pd.id,
                   detail={"식별자": rid, "민팅": "발급됨" if minted else "초안", "형태": a.data_form or "",
                           "연계키": ", ".join(keys) or "미배정",
                           "메타 확정": "예" if pd.meta_confirmed_at else "아니오",
                           "분류 확정": "예" if pd.class_confirmed_at else "아니오"})
        ds_node[pd.id] = nid
        if col:
            edge(col, nid, "HAD_MEMBER")

    rels = [r for r in process.relations if r.source_id in ds_node and r.target_id in ds_node]
    for r in rels:
        label = r.key_code or ""
        if r.type == "JOINED_ON" and r.source_column and r.target_column and level <= 3:
            label = f"{r.key_code or ''} {r.source_column} = {r.target_column}".strip()
        edge(ds_node[r.source_id], ds_node[r.target_id], "WAS_DERIVED_FROM" if r.type == "DERIVED_FROM" else r.type, label,
             status=r.status, relation_id=r.id, priority=r.priority,
             detail={"상태": "확정" if r.status == "confirmed" else "초안", **_stat_detail(r.stats)})

    if level >= 2:
        agent = node("agent-fde", "Agent", "FDE Data Studio", "prov:SoftwareAgent")
        for pd in combo:
            org_id = (pd.meta or {}).get("publisher_org_id") if "publisher_org_id" in (pd.approved_fields or []) else None
            if org_id:
                org = db.get(Organization, int(org_id))
                if org:
                    o = node(f"org{org.id}", "Agent", org.label, org.code)
                    edge(ds_node[pd.id], o, "WAS_ATTRIBUTED_TO")
            act = pd.authoring_activity
            if act:
                an = node(f"act{act.id}", "Activity", "카탈로그 작성", act.code,
                          detail={"기록": act.text, "수행": act.actor_label, "시각": act.started_at.isoformat()})
                edge(ds_node[pd.id], an, "WAS_GENERATED_BY")
                edge(an, agent, "WAS_ASSOCIATED_WITH")
        runs = db.scalars(select(Activity).where(Activity.process_id == process.id,
                                                 Activity.type.in_(["validation_run", "serialization_run", "publish"]))
                          .order_by(Activity.id.desc()).limit(3))
        for act in runs:
            label = {"validation_run": "검증 실행", "serialization_run": "직렬화 실행", "publish": "카탈로그 발행"}[act.type]
            an = node(f"act{act.id}", "Activity", label, act.code,
                      detail={"기록": act.text, "수행": act.actor_label, "시각": act.started_at.isoformat()})
            for pd in combo:
                edge(an, ds_node[pd.id], "USED")
            edge(an, agent, "WAS_ASSOCIATED_WITH")

    table_node: dict[tuple[int, str], str] = {}
    if level >= 3:
        for pd in combo:
            a = pd.asset
            if a.kind == "stream":
                continue
            rid, _ = minting.resource_id(db, pd, mode)
            approved = "media_type" in (pd.approved_fields or []) and (pd.meta or {}).get("media_type")
            dn = node(f"dist{pd.id}", "Distribution", a.filename or a.name, minting.distribution_id(rid, a.ext),
                      detail={"mediaType": (pd.meta or {}).get("media_type") or "", "승인": "예" if approved else "아니오",
                              "크기": f"{a.size or 0:,} bytes", "SHA-256": (a.sha256 or "")[:16]})
            edge(ds_node[pd.id], dn, "HAS_DISTRIBUTION")
            for t in (a.profile or {}).get("tables", []):
                tn = node(f"tbl{pd.id}:{t['name']}", "Table", t["name"], f"{len(t['columns'])}컬럼 · {t['rows']:,}행",
                          detail={"머리글 행": str(t.get("header_row", "")), "컬럼": ", ".join(c["name"] for c in t["columns"][:12])})
                table_node[(pd.id, t["name"])] = tn
                edge(dn, tn, "HAS_TABLE")

    if level >= 4:
        def col_node(pd: ProcessDataset, table: str | None, column: str | None) -> str | None:
            if not table or not column:
                return None
            parent = table_node.get((pd.id, table))
            prof = next((c for t in (pd.asset.profile or {}).get("tables", []) if t["name"] == table
                         for c in t["columns"] if c["name"] == column), None)
            sub = f"{prof['type']} · 결측 {prof['null_rate']:.1%}" if prof else "컬럼"
            cn = node(f"col{pd.id}:{table}:{column}", "Column", column, sub,
                      detail={"표": table, "고유값": str(prof["distinct"]) if prof else "", "예시": ", ".join((prof or {}).get("samples", [])[:3])})
            if parent:
                edge(parent, cn, "HAS_COLUMN")
            else:
                edge(ds_node[pd.id], cn, "HAS_COLUMN")
            return cn

        for pd in combo:
            for k in (pd.classification or {}).get("K", []):
                cn = col_node(pd, k.get("table") or ("stream" if pd.asset.kind == "stream" else None), k.get("column"))
                if cn and k.get("code"):
                    kn = node(f"key{k['code']}", "JoinKey", k["code"], suggest.KEY_LABEL.get(k["code"], ""))
                    edge(cn, kn, "MAPPED_TO_KEY")
        for r in rels:
            if r.type != "JOINED_ON":
                continue
            s = col_node(r.source, r.source_table, r.source_column)
            t = col_node(r.target, r.target_table, r.target_column)
            if s and t:
                edge(s, t, "JOINED_ON", r.key_code or "", status=r.status, relation_id=r.id,
                     detail={"상태": "확정" if r.status == "confirmed" else "초안", **_stat_detail(r.stats)})

    counts: dict[str, int] = {}
    for n in nodes.values():
        counts[n["type"]] = counts.get(n["type"], 0) + 1
    etypes: dict[str, int] = {}
    for e in edges:
        etypes[e["type"]] = etypes.get(e["type"], 0) + 1
    return {"level": level, "nodes": list(nodes.values()), "edges": edges, "node_counts": counts, "edge_counts": etypes}


def _stat_detail(stats: dict[str, Any] | None) -> dict[str, str]:
    if not stats or not stats.get("computed"):
        return {}
    return {"값 일치": f"{stats['matched']:,}건",
            "출발 일치율": f"{stats['source_match_rate']:.1%}", "도착 일치율": f"{stats['target_match_rate']:.1%}"}
