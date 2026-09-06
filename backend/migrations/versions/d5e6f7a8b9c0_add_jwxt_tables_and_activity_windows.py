"""活动签到课表驱动调度：教务对接四表 + 签到记录课程溯源列

jw_accounts（教务凭证，B 平台账号 1:1）/ jw_semesters（学期与周历，学校级共享）/
jw_timetables（账号级课表快照）/ activity_windows（课表展开的当日轮询窗口）；
sign_records.course_name 让活动签到记录可溯源到课程窗口。

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd5e6f7a8b9c0'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'jw_accounts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('b_account_id', sa.Integer(), nullable=False),
        sa.Column('student_no', sa.String(length=32), nullable=False),
        sa.Column('password_enc', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='ok'),
        sa.Column('last_error', sa.String(length=255), nullable=True),
        sa.Column('fail_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['b_account_id'], ['b_accounts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('b_account_id', name='uq_jw_accounts_b_account'),
    )
    op.create_index('ix_jw_accounts_b_account_id', 'jw_accounts', ['b_account_id'])

    op.create_table(
        'jw_semesters',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('semester', sa.String(length=16), nullable=False),
        sa.Column('week1_monday', sa.Date(), nullable=False),
        sa.Column('total_weeks', sa.Integer(), nullable=False, server_default='25'),
        sa.Column('detected_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('semester', name='uq_jw_semesters_semester'),
    )

    op.create_table(
        'jw_timetables',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('b_account_id', sa.Integer(), nullable=False),
        sa.Column('semester', sa.String(length=16), nullable=False),
        sa.Column('entries_json', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=32), nullable=False, server_default=''),
        sa.Column('synced_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['b_account_id'], ['b_accounts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('b_account_id', 'semester', name='uq_jw_timetable_account_semester'),
    )
    op.create_index('ix_jw_timetables_b_account_id', 'jw_timetables', ['b_account_id'])

    op.create_table(
        'activity_windows',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('schedule_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('start_at', sa.DateTime(), nullable=False),
        sa.Column('end_at', sa.DateTime(), nullable=False),
        sa.Column('course_name', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('sections', sa.String(length=32), nullable=False, server_default=''),
        sa.Column('last_polled_at', sa.DateTime(), nullable=True),
        sa.Column('done', sa.Boolean(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['schedule_id'], ['schedules.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_activity_windows_schedule_id', 'activity_windows', ['schedule_id'])
    op.create_index('ix_activity_windows_schedule_date', 'activity_windows', ['schedule_id', 'date'])

    op.add_column('sign_records', sa.Column('course_name', sa.String(length=64), nullable=True))


def downgrade():
    op.drop_column('sign_records', 'course_name')
    op.drop_index('ix_activity_windows_schedule_date', table_name='activity_windows')
    op.drop_index('ix_activity_windows_schedule_id', table_name='activity_windows')
    op.drop_table('activity_windows')
    op.drop_index('ix_jw_timetables_b_account_id', table_name='jw_timetables')
    op.drop_table('jw_timetables')
    op.drop_table('jw_semesters')
    op.drop_index('ix_jw_accounts_b_account_id', table_name='jw_accounts')
    op.drop_table('jw_accounts')
