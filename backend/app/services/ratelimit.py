"""외부 AI 호출 속도 제한 (사용자별). 분당은 프로세스 안 슬라이딩 윈도, 일일은 활동 로그 집계.

워커가 여럿이면 분당 제한은 워커마다 따로 센다 (일일 제한은 DB 기준이라 공유된다)."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Activity

AI_ACTIONS = ("ai_draft", "ai_simulate")
_lock = threading.Lock()
_recent: dict[int, deque[float]] = defaultdict(deque)


def local_day_start(now: datetime | None = None) -> datetime:
    tz = ZoneInfo(get_settings().timezone)
    now = (now or datetime.now(tz)).astimezone(tz)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def calls_today(db: Session, user_id: int) -> int:
    return db.scalar(select(func.count(Activity.id)).where(Activity.actor_id == user_id, Activity.type.in_(AI_ACTIONS),
                                                           Activity.started_at >= local_day_start())) or 0


def check(db: Session, user_id: int) -> None:
    """상한을 넘으면 429. 호출이 실제로 일어난 뒤에는 record() 로 분당 창에 적는다."""
    s = get_settings()
    if s.ai_rate_per_minute > 0:
        now = time.monotonic()
        with _lock:
            dq = _recent[user_id]
            while dq and now - dq[0] > 60:
                dq.popleft()
            if len(dq) >= s.ai_rate_per_minute:
                wait = int(60 - (now - dq[0])) + 1
                raise HTTPException(429, f"AI 호출이 너무 잦습니다 — 분당 {s.ai_rate_per_minute}회까지입니다. {wait}초 뒤 다시 시도하세요",
                                    headers={"Retry-After": str(wait)})
    if s.ai_rate_per_day > 0 and calls_today(db, user_id) >= s.ai_rate_per_day:
        tomorrow = local_day_start() + timedelta(days=1)
        raise HTTPException(429, f"오늘 AI 호출 상한({s.ai_rate_per_day}회)에 닿았습니다 — {tomorrow.strftime('%m/%d %H:%M')} 이후 다시 시도하세요")


def record(user_id: int) -> None:
    with _lock:
        _recent[user_id].append(time.monotonic())


def reset() -> None:
    with _lock:
        _recent.clear()
