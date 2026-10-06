"""prov:Activity 기록."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import Activity, User, utcnow
from . import minting


def log(db: Session, type_: str, text: str, *, user: User | None = None, process_id: int | None = None,
        dataset_id: int | None = None, payload: dict[str, Any] | None = None, software: bool = False) -> Activity:
    now = utcnow()
    act = Activity(
        code=f"ACT-K-{minting.next_seq(db, 'ACT'):04d}",
        type=type_,
        text=text,
        agent_type="software" if software or user is None else "person",
        actor_id=user.id if user else None,
        actor_label=(user.name if user else "시스템"),
        process_id=process_id,
        dataset_id=dataset_id,
        payload=payload or {},
        started_at=now,
        ended_at=now,
    )
    db.add(act)
    db.flush()
    return act
