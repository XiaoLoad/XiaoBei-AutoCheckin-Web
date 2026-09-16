"""add op_logs table

Revision ID: e6503f14835c
Revises: d1e2f3a4b5c6
Create Date: 2026-09-16 13:18:35.160847

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6503f14835c'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('op_logs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('action', sa.String(length=48), nullable=False),
    sa.Column('category', sa.String(length=24), nullable=False),
    sa.Column('result', sa.String(length=16), nullable=False),
    sa.Column('summary', sa.String(length=255), nullable=False),
    sa.Column('detail', sa.Text(), nullable=True),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('op_logs', schema=None) as batch_op:
        batch_op.create_index('ix_op_logs_category_time', ['category', 'created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_op_logs_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_op_logs_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_op_logs_user_time', ['user_id', 'created_at'], unique=False)


def downgrade():
    with op.batch_alter_table('op_logs', schema=None) as batch_op:
        batch_op.drop_index('ix_op_logs_user_time')
        batch_op.drop_index(batch_op.f('ix_op_logs_user_id'))
        batch_op.drop_index(batch_op.f('ix_op_logs_created_at'))
        batch_op.drop_index('ix_op_logs_category_time')

    op.drop_table('op_logs')
