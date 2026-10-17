"""발행 검수 큐 (요청 · 승인 · 반려). 가이드라인 3.4.6 표 40 HITL."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Process, ReviewRequest, User
from ..security import current_user, require_admin, require_writer
from ..services import review

router = APIRouter()


def _raise(exc: review.ReviewError) -> None:
    detail: Any = exc.message if not exc.code else {"code": exc.code, "message": exc.message, **exc.extra}
    raise HTTPException(exc.status, detail)


def _process(db: Session, pid: int) -> Process:
    p = db.get(Process, pid)
    if p is None:
        raise HTTPException(404, "프로세스를 찾을 수 없습니다")
    return p


def _request(db: Session, rid: int) -> ReviewRequest:
    rr = db.get(ReviewRequest, rid)
    if rr is None:
        raise HTTPException(404, "검수 요청을 찾을 수 없습니다")
    return rr


@router.get("/processes/{pid}/publish-review")
def publish_review(pid: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    """STEP 7 발행 카드용: 지금 발행하면 어떤 위험 신호가 있는지, 검수 요청 상태는 어떤지."""
    p = _process(db, pid)
    reasons, _vr, sr = review.publish_state(db, p)
    a = review.assess(db, p, sr) if not reasons else None
    pend = review.pending(db, pid)
    last = review.latest(db, pid)
    return {"blocked": reasons, "assessment": a, "pending": review.out(db, pend, check=True) if pend else None,
            "latest": review.out(db, last) if last else None,
            "direct_publish": bool(a) and a["level"] != "high" and pend is None,
            "direct_publish_reason": None if reasons else (
                "검수 대기 중인 요청이 있습니다" if pend else ("위험 수준이 높아 검수 승인이 필요합니다" if a and a["level"] == "high" else None))}


class SubmitIn(BaseModel):
    message: str | None = Field(default=None, max_length=2000)


@router.post("/processes/{pid}/review-requests")
def submit(pid: int, body: SubmitIn, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    p = _process(db, pid)
    try:
        rr = review.submit(db, p, user, body.message)
    except review.ReviewError as exc:
        _raise(exc)
    db.commit()
    return review.out(db, rr)


@router.get("/review-requests")
def list_requests(status: str = "pending", limit: int = 100, db: Session = Depends(get_db),
                  _: User = Depends(current_user)) -> dict[str, Any]:
    q = select(ReviewRequest).order_by(ReviewRequest.id.desc()).limit(max(1, min(limit, 500)))
    if status == "pending":
        q = q.where(ReviewRequest.status == "pending")
    elif status == "done":
        q = q.where(ReviewRequest.status != "pending")
    counts = dict(db.execute(select(ReviewRequest.status, func.count(ReviewRequest.id)).group_by(ReviewRequest.status)).all())
    return {"items": [review.out(db, r) for r in db.scalars(q)], "counts": counts}


@router.get("/review-requests/{rid}")
def get_request(rid: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, Any]:
    from ..config import get_settings

    return {**review.out(db, _request(db, rid), check=True), "self_approve_policy": get_settings().review_self_approve}


class ApproveIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)
    acknowledged: list[str] = Field(default_factory=list)


@router.post("/review-requests/{rid}/approve")
def approve(rid: int, body: ApproveIn, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, Any]:
    from ..serializers import catalog_out

    rr = _request(db, rid)
    try:
        entries = review.approve(db, rr, user, body.note, body.acknowledged)
    except review.ReviewError as exc:
        db.rollback()
        _raise(exc)
    db.commit()
    return {"request": review.out(db, rr), "published": [catalog_out(e) for e in entries]}


class RejectIn(BaseModel):
    note: str = Field(max_length=2000)


@router.post("/review-requests/{rid}/reject")
def reject(rid: int, body: RejectIn, db: Session = Depends(get_db), user: User = Depends(require_admin)) -> dict[str, Any]:
    rr = _request(db, rid)
    try:
        review.reject(db, rr, user, body.note)
    except review.ReviewError as exc:
        _raise(exc)
    db.commit()
    return review.out(db, rr)


@router.post("/review-requests/{rid}/withdraw")
def withdraw(rid: int, db: Session = Depends(get_db), user: User = Depends(require_writer)) -> dict[str, Any]:
    rr = _request(db, rid)
    try:
        review.withdraw(db, rr, user)
    except review.ReviewError as exc:
        _raise(exc)
    db.commit()
    return review.out(db, rr)
