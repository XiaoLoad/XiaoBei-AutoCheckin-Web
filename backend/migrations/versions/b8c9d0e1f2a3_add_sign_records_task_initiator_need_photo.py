"""签到记录补充任务发起人与是否需要图片

群合并推送汇总需在 QQ 群消息里逐人展示「任务发起人（B 平台任务真实姓名）」与
「是否需要图片」，二者此前未落库（SignRecord.initiator 仅记执行触发方 system/manual，
真实发起人姓名只在执行时经 extra 透传给渲染，未持久化）。本迁移新增两列，
由调度器落库，供群汇总与后续详情回显复用。存量记录两列均为 NULL（详情/汇总显示「—」）。

Revision ID: b8c9d0e1f2a3
Revises: a7f3c9d2e1b0
Create Date: 2026-09-17
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b8c9d0e1f2a3'
down_revision = 'a7f3c9d2e1b0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sign_records',
                  sa.Column('task_initiator', sa.String(length=64), nullable=True))
    op.add_column('sign_records',
                  sa.Column('need_photo', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('sign_records', 'need_photo')
    op.drop_column('sign_records', 'task_initiator')
