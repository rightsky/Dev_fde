"""기동할 때 DB 스키마를 최신 이관 판(head)으로 맞춘다.

v0.3 까지는 create_all 로 테이블을 만들었으므로 이관 기록(alembic_version)이 없다. 그런 DB 는 기준 판(0001)과
구조가 같으므로 기준 판으로 표시한 뒤 이어서 올린다.
"""
from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

BASELINE = "0001"
log = logging.getLogger("fde.migrate")


def alembic_config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parent / "migrations"))
    return cfg


def upgrade(engine: Engine) -> None:
    cfg = alembic_config()
    with engine.begin() as conn:
        tables = set(inspect(conn).get_table_names())
        cfg.attributes["connection"] = conn
        if "alembic_version" not in tables and "process" in tables:
            log.info("이관 기록이 없는 기존 DB — 기준 판 %s 로 표시합니다", BASELINE)
            command.stamp(cfg, BASELINE)
        command.upgrade(cfg, "head")
