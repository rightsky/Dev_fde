"""기관 DB 스키마 읽기 커넥터 (db_connector) · asset.connector_id

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-17 17:40:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('db_connector',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('host', sa.String(length=200), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('database', sa.String(length=100), nullable=False),
        sa.Column('db_schema', sa.String(length=100), nullable=True),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('secret_enc', sa.Text(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_tested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('table_count', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['app_user.id'], ),
        sa.ForeignKeyConstraint(['org_id'], ['organization.id'], ),
        sa.PrimaryKeyConstraint('id'))
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('asset')}
    if 'connector_id' in cols:
        return  # create_all 로 이미 만들어진 DB (개발용)
    with op.batch_alter_table('asset') as b:
        b.add_column(sa.Column('connector_id', sa.Integer(), nullable=True))
        b.create_index(op.f('ix_asset_connector_id'), ['connector_id'], unique=False)
        b.create_foreign_key('fk_asset_connector', 'db_connector', ['connector_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('asset') as b:
        b.drop_constraint('fk_asset_connector', type_='foreignkey')
        b.drop_index(op.f('ix_asset_connector_id'))
        b.drop_column('connector_id')
    op.drop_table('db_connector')
