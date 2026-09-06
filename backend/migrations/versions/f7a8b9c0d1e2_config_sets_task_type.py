"""配置套类型化：config_sets.task_type（dorm 寝室 / activity 活动）

按适用签到类型拆分配置套语义：寝室套不含活动调度块的可视化编辑，活动套承载课表
驱动参数；绑定/批量应用按类型过滤。存量归类规则：被活动任务绑定（follow/来源标签）
的套归为 activity，其余归为 dorm——保证存量活动任务的 follow 链路不断。

Revision ID: f7a8b9c0d1e2
Revises: d5e6f7a8b9c0
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f7a8b9c0d1e2'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('config_sets',
                  sa.Column('task_type', sa.String(length=16), nullable=False,
                            server_default='dorm'))
    # 存量归类：被活动任务引用过的套 → activity（不限启用状态，follow/来源标签都算）
    op.execute("""
        UPDATE config_sets cs
        SET task_type = 'activity'
        WHERE EXISTS (
            SELECT 1 FROM schedules s
            WHERE s.config_set_id = cs.id AND s.task_type = 'activity'
        )
    """)
    # 同一类型内的 is_default 唯一性由应用层保证（enforce_single_default 按类型隔离）


def downgrade():
    op.drop_column('config_sets', 'task_type')
