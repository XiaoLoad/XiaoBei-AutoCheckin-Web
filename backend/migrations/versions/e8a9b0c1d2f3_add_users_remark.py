"""add users remark

Revision ID: e8a9b0c1d2f3
Revises: b7c8d9e0f1a2
Create Date: 2026-10-07

users 表新增 remark 列：管理员创建/编辑用户时可填写备注（如真实姓名、寝室号），
便于区分用户名之外的身份信息。存量行由 server_default '' 回填为空串。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8a9b0c1d2f3'
down_revision = 'b7c8d9e0f1a2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('remark', sa.String(length=128), nullable=False,
                                      server_default=''))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('remark')
