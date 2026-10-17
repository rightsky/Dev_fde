"""DB 스키마 이관(Alembic) 검사."""
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from app import models  # noqa: F401
from app.db import Base, _make_engine
from app.migrate import BASELINE, upgrade


LATER_TABLES = {"agent_key", "agent_call", "review_request", "simulation_run", "org_grade_entry", "agent_grant"}  # 0002 (v0.5) · 0003 (v0.7) · 0004 (v0.9)


def _engine(tmp_path: Path, name: str):
    return _make_engine(f"sqlite:///{tmp_path / name}")


def test_fresh_database_matches_models(tmp_path):
    """빈 DB 를 이관 파일로 만든 결과가 모델 정의와 같아야 한다 (모델만 고치고 이관 파일을 빠뜨리면 실패)."""
    eng = _engine(tmp_path, "fresh.db")
    upgrade(eng)
    with eng.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diff == [], f"모델과 이관 파일이 다릅니다 — alembic revision --autogenerate 로 이관 파일을 만드세요: {diff}"


def test_legacy_database_is_stamped_then_upgraded(tmp_path):
    """v0.3 까지 create_all 로 만든 DB 는 기준 판으로 표시되고 데이터가 그대로 남는다."""
    eng = _engine(tmp_path, "legacy.db")
    # v0.3 시점의 표만 만든다 (0002 이후에 생긴 표는 빼고)
    Base.metadata.create_all(eng, tables=[t for t in Base.metadata.sorted_tables if t.name not in LATER_TABLES])
    with eng.begin() as c:
        c.execute(text("ALTER TABLE app_user DROP COLUMN password_changed_at"))  # 0005 (v0.12) 에서 생긴 열
        c.execute(text("ALTER TABLE process DROP COLUMN combo_grade"))  # 0007
        c.execute(text("ALTER TABLE process DROP COLUMN combo_grade_reason"))
        c.execute(text("INSERT INTO organization (code, label, kind, active, created_at) VALUES ('X', '기관', 'gov', 1, '2026-01-01 00:00:00')"))
    upgrade(eng)
    upgrade(eng)  # 두 번 기동해도 그대로
    with eng.connect() as c:
        assert "alembic_version" in inspect(c).get_table_names()
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() >= BASELINE
        assert c.execute(text("SELECT count(*) FROM organization")).scalar() == 1


def test_utc_datetime_normalizes_offsets(tmp_path):
    """UTCDateTime: 시간대가 붙은 값은 UTC 로 바꿔 저장하고, 읽을 때 항상 UTC aware 로 돌려준다 (SQLite 는 오프셋을 저장하지 않는다)."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.models import Organization

    eng = _engine(tmp_path, "tz.db")
    Base.metadata.create_all(eng)
    kst = timezone(timedelta(hours=9))
    at = datetime(2026, 10, 17, 9, 0, tzinfo=kst)  # = 2026-10-17T00:00Z
    with Session(eng) as s:
        s.add(Organization(code="TZ", label="시간대", kind="gov", created_at=at))
        s.commit()
    with Session(eng) as s:
        got = s.scalar(select(Organization).where(Organization.code == "TZ")).created_at
        assert got.tzinfo is not None and got.utcoffset() == timedelta(0)
        assert got == datetime(2026, 10, 17, 0, 0, tzinfo=timezone.utc)
