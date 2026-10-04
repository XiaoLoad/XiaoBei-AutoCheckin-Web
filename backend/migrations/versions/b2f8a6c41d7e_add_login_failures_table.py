"""add login_failures table

Revision ID: b2f8a6c41d7e
Revises: 65ff13936c2c
Create Date: 2026-10-04

登录失败计数表（防暴力破解持久化防线）：账号×IP / 账号全局 / IP 全局三维度，
见 app/models/login_failure.py 的 LoginFailure。key 单列主键，无外键——
不存在的用户名同样计数。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2f8a6c41d7e'
down_revision = '65ff13936c2c'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('login_failures',
    sa.Column('key', sa.String(length=160), nullable=False),
    sa.Column('fail_count', sa.Integer(), nullable=False),
    sa.Column('locked_until', sa.DateTime(), nullable=True),
    sa.Column('last_fail_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    with op.batch_alter_table('login_failures', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_login_failures_last_fail_at'), ['last_fail_at'], unique=False)


def downgrade():
    with op.batch_alter_table('login_failures', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_login_failures_last_fail_at'))

    op.drop_table('login_failures')
