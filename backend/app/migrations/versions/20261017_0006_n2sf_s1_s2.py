"""N²SF S 등급을 S1(조건부 공유) · S2(제한 공유) 로 세분화 (가이드라인 3.6.1)

기존 S 는 보수적으로 S2 로 옮긴다: 데이터셋 분류, 에이전트 키 허용 등급, 발행본 facet.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-17 13:30:00
"""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

NEW = [("N2SF-S2", "S2 — 제한 공유", "개별 기록·민감 정보 포함. 기관 간 협약 · 사전 승인 · 접근통제와 이력 관리가 전제", 1),
       ("N2SF-S1", "S1 — 조건부 공유", "비식별·집계 처리된 자료. 이용약정 · 목적 확인 · 비밀유지 의무를 전제로 제공", 2)]


def _load(v):
    if v is None:
        return None
    return json.loads(v) if isinstance(v, str) else v


# JSON 열은 방언마다 직렬화가 달라 SQLAlchemy 표 구성으로 갱신한다 (PostgreSQL json 열에 문자열을 바로 넣으면 형 오류)
T_CODE = sa.table("taxonomy_code", sa.column("axis_code", sa.String), sa.column("code", sa.String), sa.column("label", sa.String),
                  sa.column("definition", sa.String), sa.column("position", sa.Integer), sa.column("active", sa.Boolean), sa.column("extra", sa.JSON))
T_PD = sa.table("process_dataset", sa.column("id", sa.Integer), sa.column("classification", sa.JSON))
T_KEY = sa.table("agent_key", sa.column("id", sa.Integer), sa.column("grades", sa.JSON))
T_ENTRY = sa.table("catalog_entry", sa.column("id", sa.Integer), sa.column("facets", sa.JSON))


def upgrade() -> None:
    conn = op.get_bind()
    axis = conn.execute(sa.text("SELECT code FROM taxonomy_axis WHERE code = 'N2SF'")).first()
    if axis is None:
        return  # 분류체계가 아직 시딩되지 않은 새 DB: seed 가 새 코드를 넣는다
    have = {r[0] for r in conn.execute(sa.text("SELECT code FROM taxonomy_code WHERE axis_code = 'N2SF'"))}
    for code, label, definition, pos in NEW:
        if code not in have:
            conn.execute(T_CODE.insert().values(axis_code="N2SF", code=code, label=label, definition=definition, position=pos, active=True, extra={}))
    conn.execute(sa.text("UPDATE taxonomy_code SET active = :f, label = 'S — (세분화 전, S2 로 이관됨)' WHERE axis_code = 'N2SF' AND code = 'N2SF-S'"), {"f": False})
    conn.execute(sa.text("UPDATE taxonomy_code SET label = 'C — 비공개' WHERE axis_code = 'N2SF' AND code = 'N2SF-C'"))
    conn.execute(sa.text("UPDATE taxonomy_code SET label = 'O — 공개', position = 3 WHERE axis_code = 'N2SF' AND code = 'N2SF-O'"))
    conn.execute(sa.text("UPDATE taxonomy_axis SET description = '국가 망 보안체계 등급 (가이드라인 1.3.2 · 3.6.1, S 는 S1·S2 로 세분화). 미지정은 S2 로 간주한다' WHERE code = 'N2SF'"))

    # 데이터셋 분류 JSON: N2SF-S → N2SF-S2
    for pid, cls in conn.execute(sa.text("SELECT id, classification FROM process_dataset")).all():
        c = _load(cls)
        if isinstance(c, dict) and c.get("N2SF") == "N2SF-S":
            c["N2SF"] = "N2SF-S2"
            conn.execute(T_PD.update().where(T_PD.c.id == pid).values(classification=c))
    # 에이전트 키: S → S1 + S2
    for kid, grades in conn.execute(sa.text("SELECT id, grades FROM agent_key")).all():
        g = _load(grades) or []
        if "S" in g:
            g = sorted({x for x in g if x != "S"} | {"S1", "S2"})
            conn.execute(T_KEY.update().where(T_KEY.c.id == kid).values(grades=g))
    # 발행본 facet: S → S2
    for eid, facets in conn.execute(sa.text("SELECT id, facets FROM catalog_entry")).all():
        f = _load(facets) or {}
        if f.get("n2sf") == "S":
            f["n2sf"] = "S2"
            conn.execute(T_ENTRY.update().where(T_ENTRY.c.id == eid).values(facets=f))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE taxonomy_code SET active = :t, label = 'S — Sensitive' WHERE axis_code = 'N2SF' AND code = 'N2SF-S'"), {"t": True})
    for pid, cls in conn.execute(sa.text("SELECT id, classification FROM process_dataset")).all():
        c = _load(cls)
        if isinstance(c, dict) and c.get("N2SF") in ("N2SF-S1", "N2SF-S2"):
            c["N2SF"] = "N2SF-S"
            conn.execute(T_PD.update().where(T_PD.c.id == pid).values(classification=c))
    conn.execute(sa.text("DELETE FROM taxonomy_code WHERE axis_code = 'N2SF' AND code IN ('N2SF-S1', 'N2SF-S2')"))
