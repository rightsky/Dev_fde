"""프로세스 접근 범위 (v0.18.1).

- 관리자(admin): 모든 프로세스를 보고 다룬다
- 열람(viewer): 모든 프로세스를 읽기 전용으로 본다 (작성 권한은 원래 없다)
- 작업자(worker): **자기가 만든 프로세스만** 본다. 다른 작업자의 프로세스는 목록 · 상세 · 산출물 어디에도 나오지 않는다 (존재도 알리지 않음, 404)

새 작업자 계정은 처음에 빈 목록으로 시작한다. 레거시 프로세스(created_by 없음)는 관리자 · 열람 계정에만 보인다.
"""
from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (Artifact, DiagnosisRun, Process, ProcessDataset, Relation, SerializationRun, SimulationRun, User, ValidationRun)


def sees_all(user: User) -> bool:
    return user.role in ("admin", "viewer")


def visible(user: User, process: Process | None) -> bool:
    if process is None:
        return False
    return sees_all(user) or process.created_by == user.id


def visible_process_ids(db: Session, user: User) -> list[int] | None:
    """None 이면 제한 없음."""
    if sees_all(user):
        return None
    return list(db.scalars(select(Process.id).where(Process.created_by == user.id)).all())


def restrict(stmt, user: User):
    """select(Process) 문에 작업자 범위를 건다."""
    return stmt if sees_all(user) else stmt.where(Process.created_by == user.id)


def _process_of(db: Session, request: Request) -> Process | None:
    """경로 변수에서 대상 프로세스를 찾는다. 찾지 못하면 None (이 의존성은 범위만 보고, 404 는 각 라우트가 낸다)."""
    pp = request.path_params
    path = request.url.path
    try:
        if "pid" in pp:
            return db.get(Process, int(pp["pid"]))
        if "did" in pp:
            pd = db.get(ProcessDataset, int(pp["did"]))
            return pd.process if pd else None
        if "rid" in pp and "/relations/" in path:
            r = db.get(Relation, int(pp["rid"]))
            return db.get(Process, r.process_id) if r else None
        if "run_id" in pp:
            rid = int(pp["run_id"])
            model = SerializationRun if "/serialization-runs/" in path else ValidationRun if "/validation-runs/" in path else DiagnosisRun if "/diagnosis-runs/" in path else None
            run = db.get(model, rid) if model else None
            return db.get(Process, run.process_id) if run else None
        if "sid" in pp and "/simulations/" in path:
            s = db.get(SimulationRun, int(pp["sid"]))
            return db.get(Process, s.process_id) if s else None
        if "aid" in pp and "/artifacts/" in path:
            a = db.get(Artifact, int(pp["aid"]))
            return db.get(Process, a.run.process_id) if a else None
    except (TypeError, ValueError):
        return None
    return None


def enforce(request: Request, db: Session, user: User) -> None:
    """라우터 의존성: 작업자가 남의 프로세스에 닿으면 404 (존재를 드러내지 않는다)."""
    if sees_all(user):
        return
    p = _process_of(db, request)
    if p is not None and not visible(user, p):
        raise HTTPException(404, "프로세스를 찾을 수 없습니다")
