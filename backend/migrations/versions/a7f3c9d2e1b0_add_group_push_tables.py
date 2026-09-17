"""add group push tables (push_groups / push_group_members / push_group_digest_log / push_group_digest_pending)

Revision ID: a7f3c9d2e1b0
Revises: d0a42ab33ead
Create Date: 2026-09-17 13:10:00.000000

群推送分组模型：班级/寝室两类分组 + 合并推送审计 + 待触发护栏。
见 docs/dorm-group-digest-design.md v3。班级分组成员派生自 account.profile.className（无需成员表）；
寝室分组成员存于 push_group_members。qq_code 为空表示未绑定 QQ 群、不参与推送。
幂等护栏：push_group_digest_log 与 push_group_digest_pending 均对 (group_id, date) 唯一。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7f3c9d2e1b0'
down_revision = 'd0a42ab33ead'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('push_groups',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=16), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('qq_code', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'type', 'name', name='uq_push_groups_user_type_name')
    )
    with op.batch_alter_table('push_groups', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_push_groups_user_id'), ['user_id'], unique=False)

    op.create_table('push_group_members',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['b_accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['push_groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('group_id', 'account_id', name='uq_push_group_members_group_account')
    )
    with op.batch_alter_table('push_group_members', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_push_group_members_group_id'), ['group_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_push_group_members_account_id'), ['account_id'], unique=False)

    op.create_table('push_group_digest_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('member_total', sa.Integer(), nullable=False),
        sa.Column('member_done', sa.Integer(), nullable=False),
        sa.Column('message', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['push_groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('group_id', 'date', name='uq_push_group_digest_log_group_date')
    )
    with op.batch_alter_table('push_group_digest_log', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_push_group_digest_log_group_id'), ['group_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_push_group_digest_log_date'), ['date'], unique=False)

    op.create_table('push_group_digest_pending',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('flush_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['push_groups.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('group_id', 'date', name='uq_push_group_digest_pending_group_date')
    )
    with op.batch_alter_table('push_group_digest_pending', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_push_group_digest_pending_group_id'), ['group_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_push_group_digest_pending_date'), ['date'], unique=False)


def downgrade():
    with op.batch_alter_table('push_group_digest_pending', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_push_group_digest_pending_date'))
        batch_op.drop_index(batch_op.f('ix_push_group_digest_pending_group_id'))
    op.drop_table('push_group_digest_pending')

    with op.batch_alter_table('push_group_digest_log', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_push_group_digest_log_date'))
        batch_op.drop_index(batch_op.f('ix_push_group_digest_log_group_id'))
    op.drop_table('push_group_digest_log')

    with op.batch_alter_table('push_group_members', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_push_group_members_account_id'))
        batch_op.drop_index(batch_op.f('ix_push_group_members_group_id'))
    op.drop_table('push_group_members')

    with op.batch_alter_table('push_groups', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_push_groups_user_id'))
    op.drop_table('push_groups')
