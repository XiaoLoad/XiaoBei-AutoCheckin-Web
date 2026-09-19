"""op_logs 加 (action, category) 覆盖索引（/op-logs/meta 的 GROUP BY 聚合原先全表扫 + 临时表）

Revision ID: 65ff13936c2c
Revises: c9d0e1f2a3b5
Create Date: 2026-09-19
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '65ff13936c2c'
down_revision = 'c9d0e1f2a3b5'
branch_labels = None
depends_on = None

# ⚠️ autogenerate 本次还报了三处差异，均为误报，已剔除，勿再加回：
#   - jw_accounts：uq_jw_accounts_b_account 与 ix_jw_accounts_b_account_id 的唯一性口径对不上；
#   - push_groups / push_group_members：外键「删了再建」，两边名字不同源。


def upgrade():
    op.create_index('ix_op_logs_action_category', 'op_logs', ['action', 'category'])


def downgrade():
    op.drop_index('ix_op_logs_action_category', table_name='op_logs')
