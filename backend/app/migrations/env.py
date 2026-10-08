"""Alembic 실행 환경. 접속 주소는 앱 설정(FDE_DATABASE_URL)에서 읽는다."""
from __future__ import annotations

from alembic import context

from app import models  # noqa: F401 - 모든 테이블을 Base.metadata 에 등록
from app.db import Base, engine

target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):  # noqa: ANN001
    """UTC 보정 타입(UTCDateTime)은 DB 에서는 timezone 붙은 DateTime 이다. 이관 파일이 앱 코드에 기대지 않게 그렇게 적는다."""
    from app.models import UTCDateTime

    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def run_migrations_offline() -> None:
    context.configure(url=str(engine.url), target_metadata=target_metadata, literal_binds=True,
                      render_as_batch=engine.url.get_backend_name() == "sqlite")
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = context.config.attributes.get("connection")
    if connectable is None:
        with engine.connect() as conn:
            _run(conn)
    else:
        _run(connectable)


def _run(conn) -> None:  # noqa: ANN001
    context.configure(connection=conn, target_metadata=target_metadata, compare_type=True, render_item=render_item,
                      render_as_batch=conn.dialect.name == "sqlite")
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
