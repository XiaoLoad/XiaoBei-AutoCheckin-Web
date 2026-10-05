"""add activity_windows unique key

Revision ID: c5e8f9a3b7d2
Revises: a9b4c7d2e6f1
Create Date: 2026-10-05

活动窗口唯一约束（T6 兜底）：同一任务同一天同一时段标签 + 小节段只允许一行。
窗口展开是「读现有 → 删除 → 插入 → commit」的删插事务，进程内已由全局锁串行化；
唯一约束兜住锁外路径（历史数据残留、未来新增入口漏锁）与跨进程部署的极端情况。
建唯一索引前先清重：历史并发竞态可能已留下重复行，按 (schedule_id, date,
course_name, sections) 分组保留 id 最大的一行（最新状态），其余删除。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5e8f9a3b7d2'
down_revision = 'a9b4c7d2e6f1'
branch_labels = None
depends_on = None


def _dedupe_duplicates(conn):
    """删除历史重复窗口行：每组 (schedule_id, date, course_name, sections) 保留 id 最大者。
    MySQL 限制 DELETE 目标不能出现在子查询 FROM 里（1093），故 MAX(id) 一并在
    派生表中算完，DELETE 走派生表联接。"""
    conn.execute(sa.text("""
        DELETE w FROM activity_windows w
        JOIN (
            SELECT schedule_id, date, course_name, sections, MAX(id) AS max_id
            FROM activity_windows
            GROUP BY schedule_id, date, course_name, sections
            HAVING COUNT(*) > 1
        ) d ON w.schedule_id = d.schedule_id
             AND w.date = d.date
             AND w.course_name = d.course_name
             AND w.sections = d.sections
        WHERE w.id < d.max_id
    """))


def upgrade():
    conn = op.get_bind()
    _dedupe_duplicates(conn)
    op.create_unique_constraint(
        'uq_activity_windows_schedule_date_course_sections',
        'activity_windows',
        ['schedule_id', 'date', 'course_name', 'sections'],
    )


def downgrade():
    op.drop_constraint(
        'uq_activity_windows_schedule_date_course_sections',
        'activity_windows',
        type_='unique',
    )
