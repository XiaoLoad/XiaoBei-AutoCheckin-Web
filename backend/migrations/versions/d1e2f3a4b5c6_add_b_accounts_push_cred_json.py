"""add b_accounts push_cred_json

Revision ID: d1e2f3a4b5c6
Revises: f7a8b9c0d1e2
Create Date: 2026-09-15 15:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1e2f3a4b5c6'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    # 账号级推送凭证绑定（JSON {channel: credential_id}），可空——存量账号默认未绑定
    with op.batch_alter_table('b_accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('push_cred_json', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('b_accounts', schema=None) as batch_op:
        batch_op.drop_column('push_cred_json')
