"""공유 링크 (share_link) — ARD 관리 v0.19

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-17 21:50:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('share_link',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('token_prefix', sa.String(length=8), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('dataset_id', sa.Integer(), nullable=True),
        sa.Column('process_id', sa.Integer(), nullable=True),
        sa.Column('filename', sa.String(length=300), nullable=False),
        sa.Column('grade', sa.String(length=4), nullable=True),
        sa.Column('recipient', sa.String(length=200), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('max_downloads', sa.Integer(), nullable=False),
        sa.Column('downloads', sa.Integer(), nullable=False),
        sa.Column('last_downloaded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_label', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['app_user.id'], ),
        sa.ForeignKeyConstraint(['process_id'], ['process.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'))
    op.create_index(op.f('ix_share_link_token_hash'), 'share_link', ['token_hash'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_share_link_token_hash'), table_name='share_link')
    op.drop_table('share_link')
