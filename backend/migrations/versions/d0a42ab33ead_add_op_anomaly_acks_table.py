"""add op_anomaly_acks table

Revision ID: d0a42ab33ead
Revises: e6503f14835c
Create Date: 2026-09-16 17:55:43.294551

异常告警的「已处理」确认表：见 app/models/op_log.py 的 OpAnomalyAck。

⚠️ autogenerate 同时还捞到 jw_accounts 上两处与本改动无关的历史漂移
（删 uq_jw_accounts_b_account、把 ix_jw_accounts_b_account_id 改成 unique），
已从本迁移中剔除——功能提交不掺无关 schema 变更。
那份漂移仍在（下次 flask db migrate 还会再报），需单独处理。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd0a42ab33ead'
down_revision = 'e6503f14835c'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('op_anomaly_acks',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('ip', sa.String(length=64), nullable=False),
    sa.Column('count_at_ack', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'ip', name='uq_op_anomaly_ack_user_ip')
    )
    with op.batch_alter_table('op_anomaly_acks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_op_anomaly_acks_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_op_anomaly_acks_ip'), ['ip'], unique=False)
        batch_op.create_index(batch_op.f('ix_op_anomaly_acks_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('op_anomaly_acks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_op_anomaly_acks_user_id'))
        batch_op.drop_index(batch_op.f('ix_op_anomaly_acks_ip'))
        batch_op.drop_index(batch_op.f('ix_op_anomaly_acks_created_at'))

    op.drop_table('op_anomaly_acks')
