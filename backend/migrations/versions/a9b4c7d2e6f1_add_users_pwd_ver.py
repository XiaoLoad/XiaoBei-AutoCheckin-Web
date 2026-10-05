"""add users pwd_ver

Revision ID: a9b4c7d2e6f1
Revises: b2f8a6c41d7e
Create Date: 2026-10-05

密码版本号（S7 修复）：users 表新增 pwd_ver 列，密码每次变更自增。
JWT 携带签发时的 pwd_ver，鉴权时与库值比对——不等即吊销，
使修改密码后该用户所有存量 token 立即失效（含其他设备/标签页的会话）。
存量行由 server_default '1' 回填，历史 token 无 pwd_ver 声明视为版本 1，
与库值一致，升级后不掉线。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a9b4c7d2e6f1'
down_revision = 'b2f8a6c41d7e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pwd_ver', sa.Integer(), nullable=False,
                                      server_default='1'))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('pwd_ver')
