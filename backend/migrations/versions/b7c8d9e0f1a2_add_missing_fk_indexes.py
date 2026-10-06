"""add missing fk indexes

Revision ID: b7c8d9e0f1a2
Revises: e2a7b4c9d8f1
Create Date: 2026-10-06

P1 修复配套：三个外键列声明了 ForeignKey 但未建索引（MySQL 不会为外键自动建索引），
级联 UPDATE/DELETE 与按列过滤均退化为全表扫描：
- sign_records.schedule_id：流水表增长最快，删任务时的 UPDATE ... WHERE schedule_id= 最疼
- schedules.config_set_id：删配置套级联 update、follow 任务解析
- config_sets.location_id：位置引用计数 COUNT
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b7c8d9e0f1a2'
down_revision = 'e2a7b4c9d8f1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_records_schedule', 'sign_records', ['schedule_id'])
    op.create_index('ix_schedules_config_set', 'schedules', ['config_set_id'])
    op.create_index('ix_config_sets_location', 'config_sets', ['location_id'])


def downgrade():
    op.drop_index('ix_config_sets_location', table_name='config_sets')
    op.drop_index('ix_schedules_config_set', table_name='schedules')
    op.drop_index('ix_records_schedule', table_name='sign_records')
