"""조합 등급 (process.combo_grade) · 기관 등급표 (org_grade_entry)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-17 15:10:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('process', sa.Column('combo_grade', sa.String(length=10), nullable=True))
    op.add_column('process', sa.Column('combo_grade_reason', sa.Text(), nullable=True))
    op.create_table('org_grade_entry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.Column('system', sa.String(length=200), nullable=True),
        sa.Column('department', sa.String(length=200), nullable=True),
        sa.Column('grade', sa.String(length=10), nullable=False),
        sa.Column('personal_data', sa.String(length=20), nullable=True),
        sa.Column('legal_basis', sa.String(length=500), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('asset_id', sa.Integer(), nullable=True),
        sa.Column('match_score', sa.Integer(), nullable=False),
        sa.Column('source_file', sa.String(length=300), nullable=True),
        sa.Column('source_sha256', sa.String(length=64), nullable=True),
        sa.Column('imported_by', sa.Integer(), nullable=True),
        sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['asset_id'], ['asset.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['imported_by'], ['app_user.id'], ),
        sa.PrimaryKeyConstraint('id'))
    op.create_index(op.f('ix_org_grade_entry_asset_id'), 'org_grade_entry', ['asset_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_org_grade_entry_asset_id'), table_name='org_grade_entry')
    op.drop_table('org_grade_entry')
    op.drop_column('process', 'combo_grade_reason')
    op.drop_column('process', 'combo_grade')
