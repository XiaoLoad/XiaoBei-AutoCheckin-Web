"""sign_records.created_at 加索引（保留策略清理 job 按该列做范围 DELETE，无索引时全表扫描）

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-09-05
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_sign_records_created_at', 'sign_records', ['created_at'])


def downgrade():
    op.drop_index('ix_sign_records_created_at', table_name='sign_records')
