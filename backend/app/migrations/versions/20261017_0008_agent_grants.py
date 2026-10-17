"""에이전트 키 S2 건별 승인 (agent_grant)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-17 15:30:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('agent_grant',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.String(length=40), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('granted_by', sa.Integer(), nullable=True),
        sa.Column('granted_label', sa.String(length=100), nullable=False),
        sa.Column('granted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['granted_by'], ['app_user.id'], ),
        sa.ForeignKeyConstraint(['key_id'], ['agent_key.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'))
    op.create_index(op.f('ix_agent_grant_key_id'), 'agent_grant', ['key_id'], unique=False)
    op.create_index(op.f('ix_agent_grant_resource_id'), 'agent_grant', ['resource_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_agent_grant_resource_id'), table_name='agent_grant')
    op.drop_index(op.f('ix_agent_grant_key_id'), table_name='agent_grant')
    op.drop_table('agent_grant')
