"""분류체계 세트 (taxonomy_set) · taxonomy_code.set_id · process.taxonomy_set_id — v0.20

기존 F1~F6 코드는 모두 기본 세트(slug 'base', 국토교통부 ARD 분류체계)로 이관한다. K · N2SF 코드는 공통(NULL).

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-17 22:10:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None

SET_AXES = ("F1", "F2", "F3", "F4", "F5", "F6")


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'taxonomy_set' not in insp.get_table_names():
        op.create_table('taxonomy_set',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('slug', sa.String(length=24), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('scope', sa.String(length=120), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('base_set_id', sa.Integer(), nullable=True),
            sa.Column('is_default', sa.Boolean(), nullable=False),
            sa.Column('locked', sa.Boolean(), nullable=False),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('created_label', sa.String(length=100), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['base_set_id'], ['taxonomy_set.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['created_by'], ['app_user.id'], ),
            sa.PrimaryKeyConstraint('id'), sa.UniqueConstraint('slug'))
    code_cols = {c['name'] for c in insp.get_columns('taxonomy_code')}
    if 'set_id' not in code_cols:
        with op.batch_alter_table('taxonomy_code') as b:
            b.add_column(sa.Column('set_id', sa.Integer(), nullable=True))
            b.create_index(op.f('ix_taxonomy_code_set_id'), ['set_id'], unique=False)
            b.create_foreign_key('fk_taxonomy_code_set', 'taxonomy_set', ['set_id'], ['id'], ondelete='CASCADE')
    proc_cols = {c['name'] for c in insp.get_columns('process')}
    if 'taxonomy_set_id' not in proc_cols:
        with op.batch_alter_table('process') as b:
            b.add_column(sa.Column('taxonomy_set_id', sa.Integer(), nullable=True))
            b.create_foreign_key('fk_process_taxonomy_set', 'taxonomy_set', ['taxonomy_set_id'], ['id'])
    # 데이터 이관: 기본 세트 1개 + 기존 F1~F6 코드 귀속
    now = sa.func.now()
    existing = bind.execute(sa.text("SELECT id FROM taxonomy_set WHERE slug = 'base'")).scalar()
    if existing is None:
        bind.execute(sa.text(
            "INSERT INTO taxonomy_set (slug, name, scope, description, base_set_id, is_default, locked, created_by, created_label, created_at, updated_at) "
            "VALUES ('base', '국토교통부 ARD 분류체계 (기본)', '국토교통부', '공공데이터 AI 친화적 관리 가이드라인 표 기반 기본 세트 (F1 주제영역 · F2 데이터유형 · F3 해상도 · F4 이용조건 · F5 AI활용목적 · F6 거버넌스)', "
            "NULL, :t, :t, NULL, '시스템', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"t": True})
        existing = bind.execute(sa.text("SELECT id FROM taxonomy_set WHERE slug = 'base'")).scalar()
    bind.execute(sa.text("UPDATE taxonomy_code SET set_id = :sid WHERE set_id IS NULL AND axis_code IN ('F1','F2','F3','F4','F5','F6')"), {"sid": existing})


def downgrade() -> None:
    with op.batch_alter_table('process') as b:
        b.drop_constraint('fk_process_taxonomy_set', type_='foreignkey')
        b.drop_column('taxonomy_set_id')
    with op.batch_alter_table('taxonomy_code') as b:
        b.drop_constraint('fk_taxonomy_code_set', type_='foreignkey')
        b.drop_index(op.f('ix_taxonomy_code_set_id'))
        b.drop_column('set_id')
    op.drop_table('taxonomy_set')
