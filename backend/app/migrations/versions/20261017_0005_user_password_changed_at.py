"""user.password_changed_at (비밀번호 변경 뒤 기존 토큰 무효화)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-17 12:20:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('app_user', sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('app_user', 'password_changed_at')
