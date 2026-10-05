"""add digest pending attempts

Revision ID: e2a7b4c9d8f1
Revises: c5e8f9a3b7d2
Create Date: 2026-10-05

T7 修复配套：push_group_digest_pending 增加 attempts 列。
发送改为「删除 pending 行」原子认领后，发送失败需按 attempts 重排队，
超过 MAX_FLUSH_ATTEMPTS 记 fail 终态，防止永久性故障（如凭证失效）导致 30s 对账无限重试。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e2a7b4c9d8f1'
down_revision = 'c5e8f9a3b7d2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'push_group_digest_pending',
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade():
    op.drop_column('push_group_digest_pending', 'attempts')
