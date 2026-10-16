"""단계 게이트 상태기계.

모든 단계 잠금·완료 판정은 이 모듈 한 곳에서만 한다. 하류 결과의 무효화(stale)는 플래그를 따로 저장하지 않고
'실행 시점 정본 체크섬 ≠ 현재 정본 체크섬' 으로 매번 계산한다 — 상류를 어떤 경로로 바꾸든 빠짐없이 감지된다.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import Process
from . import diagnosis, serialize, validation


def state(db: Session, process: Process) -> dict[str, Any]:
    datasets = process.datasets
    combo = process.combo
    sel_n = sum(1 for d in datasets if d.selected)
    combo_ok = bool(combo) and process.combo_confirmed_at is not None

    vr = validation.latest_run(db, process.id)
    v_stale = validation.stale_reason(db, process, vr) if combo else None
    v_done = vr is not None and v_stale is None
    v_pass = vr.pass_count if vr else 0

    sr = serialize.latest_run(db, process.id)
    s_stale = serialize.stale_reason(db, process, sr, vr, v_stale)
    s_done = sr is not None and s_stale is None and sr.ok_count > 0

    dr = diagnosis.latest_run(db, process.id)
    d_stale = diagnosis.stale_reason(dr, sr.id if sr else None, s_stale)
    d_done = dr is not None and d_stale is None

    meta_n = sum(1 for d in combo if d.meta_confirmed_at)
    class_n = sum(1 for d in combo if d.class_confirmed_at)
    lineage_ok = validation.lineage_resolved(db, process)
    rel_n = sum(1 for r in process.relations if r.status == "confirmed")

    need_combo = "STEP 2 조합 확정을 먼저 완료하세요"
    g = {
        1: {"done": sel_n > 0 or bool(combo), "can_enter": True, "reason": ""},
        2: {"done": combo_ok, "can_enter": sel_n > 0 or bool(combo), "reason": "STEP 1에서 후보를 1건 이상 선택하세요"},
        3: {"done": combo_ok and meta_n == len(combo), "can_enter": combo_ok, "reason": need_combo,
            "progress": f"{meta_n}/{len(combo)}"},
        4: {"done": combo_ok and class_n == len(combo), "can_enter": combo_ok, "reason": need_combo,
            "progress": f"{class_n}/{len(combo)}"},
        5: {"done": combo_ok and lineage_ok and (len(combo) < 2 or rel_n > 0 or process.lineage_waived_at is not None),
            "can_enter": combo_ok, "reason": need_combo, "progress": f"관계 {rel_n}건"},
        6: {"done": v_done, "can_enter": combo_ok, "reason": need_combo,
            "progress": f"통과 {v_pass}/{len(vr.results)}" if vr else ""},
        # 7·8 은 '들어가기'(지난 결과 열람)와 '실행하기'를 나눈다. 상류가 바뀌어도 지난 결과는 "최신 아님" 표시와 함께 볼 수 있고,
        # 새로 실행하는 것만 최신 상류 결과를 요구한다 — 미흡 항목을 여러 개 고칠 때 단계마다 왕복하지 않기 위함.
        7: {"done": s_done, "can_enter": vr is not None, "reason": "STEP 6 검증을 먼저 실행하세요",
            "can_run": v_done and v_pass >= 1, "run_reason": v_stale or "STEP 6 검증을 먼저 실행하세요 (통과 1건 이상 필요)",
            "progress": f"{sr.ok_count}건 변환" if sr else ""},
        8: {"done": d_done, "can_enter": sr is not None, "reason": "STEP 7 변환을 먼저 실행하세요",
            "can_run": s_done, "run_reason": s_stale or "STEP 7 변환을 먼저 실행하세요",
            "progress": f"{dr.score:g}/{dr.max_score:g}점" if dr else ""},
    }
    for n in (1, 2, 3, 4, 5, 6):
        g[n]["can_run"], g[n]["run_reason"] = g[n]["can_enter"], g[n]["reason"]
    return {
        "gates": [{"step": n, **v} for n, v in g.items()],
        "combo_ok": combo_ok,
        "lineage_resolved": lineage_ok,
        "validation": {"run_id": vr.id if vr else None, "stale": v_stale, "done": v_done, "mode": vr.mode if vr else None,
                       "pass_count": v_pass, "total": len(vr.results) if vr else 0},
        "serialization": {"run_id": sr.id if sr else None, "stale": s_stale, "done": s_done,
                          "ok_count": sr.ok_count if sr else 0},
        "diagnosis": {"run_id": dr.id if dr else None, "stale": d_stale, "done": d_done,
                      "score": dr.score if dr else None, "max_score": dr.max_score if dr else None},
    }


def can_enter(db: Session, process: Process, step: int) -> tuple[bool, str]:
    st = state(db, process)
    gate = next(g for g in st["gates"] if g["step"] == step)
    return gate["can_enter"], gate["reason"]


def can_run(db: Session, process: Process, step: int) -> tuple[bool, str]:
    """그 단계의 실행(검증·변환·진단)을 지금 할 수 있는지. 열람(can_enter)보다 엄격하다."""
    st = state(db, process)
    gate = next(g for g in st["gates"] if g["step"] == step)
    return gate["can_run"], gate["run_reason"]
