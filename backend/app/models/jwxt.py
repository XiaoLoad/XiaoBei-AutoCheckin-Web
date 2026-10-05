# 教务系统对接模型（活动签到课表驱动调度，设计文档 docs/superpowers/specs/
# 2026-09-06-activity-course-scheduling-design.md §4.4）：
#   JwAccount     教务凭证，与 B 平台账号 1:1 绑定（密码 Fernet 可逆加密，仅服务端同步用）
#   JwSemester    学校级共享：当前学期 + 第 1 周周一 + 总周数（全校统一，任一账号代取）
#   JwTimetable   账号级课表快照（每账号每学期一份，含 content_hash 幂等观测）
#   ActivityWindow  课表展开出的"当日活动签到轮询窗口"（按 schedule 即按账号任务）
import json

from app.extensions import db
from app.models.user import now_cst
from app.services.crypto import decrypt, encrypt


class JwAccount(db.Model):
    __tablename__ = 'jw_accounts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    b_account_id = db.Column(db.Integer, db.ForeignKey('b_accounts.id'), nullable=False,
                             unique=True, index=True)   # 1 账号 1 绑定
    student_no = db.Column(db.String(32), nullable=False)
    password_enc = db.Column(db.Text, nullable=False)   # Fernet 密文
    # ok=最近同步成功；needs_attention=连续失败需人工重绑（此时活动任务回退 fixed 兜底行为）
    status = db.Column(db.String(16), nullable=False, default='ok')
    last_error = db.Column(db.String(255))
    fail_count = db.Column(db.Integer, nullable=False, default=0)
    last_login_at = db.Column(db.DateTime)
    last_sync_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=now_cst)
    updated_at = db.Column(db.DateTime, default=now_cst, onupdate=now_cst)

    def set_password(self, raw: str):
        self.password_enc = encrypt(raw)

    def get_password(self) -> str:
        return decrypt(self.password_enc)

    def to_dict(self):
        return {
            'bAccountId': self.b_account_id,
            'studentNo': self.student_no,
            'status': self.status,
            'lastError': self.last_error or '',
            'lastLoginAt': self.last_login_at.strftime('%Y-%m-%d %H:%M') if self.last_login_at else '',
            'lastSyncAt': self.last_sync_at.strftime('%Y-%m-%d %H:%M') if self.last_sync_at else '',
        }


class JwSemester(db.Model):
    __tablename__ = 'jw_semesters'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    semester = db.Column(db.String(16), nullable=False, unique=True)  # 形如 2026-2027-1
    week1_monday = db.Column(db.Date, nullable=False)                 # 第 1 周周一
    total_weeks = db.Column(db.Integer, nullable=False, default=25)
    detected_at = db.Column(db.DateTime, default=now_cst)

    def to_dict(self):
        return {
            'semester': self.semester,
            'week1Monday': self.week1_monday.isoformat() if self.week1_monday else '',
            'totalWeeks': self.total_weeks,
        }


class JwTimetable(db.Model):
    __tablename__ = 'jw_timetables'
    __table_args__ = (
        db.UniqueConstraint('b_account_id', 'semester', name='uq_jw_timetable_account_semester'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    b_account_id = db.Column(db.Integer, db.ForeignKey('b_accounts.id'), nullable=False, index=True)
    semester = db.Column(db.String(16), nullable=False)
    entries_json = db.Column(db.Text, nullable=False)   # TimetableEntry.to_dict() 列表
    # 解析结果内容哈希：同步幂等（课表没变不重写窗口基线）与"同班一致"观测，不做跨账号复用
    content_hash = db.Column(db.String(32), nullable=False, default='')
    synced_at = db.Column(db.DateTime, default=now_cst)

    @property
    def entries(self):
        from app.services.jwxt.base import TimetableEntry
        try:
            return [TimetableEntry.from_dict(d) for d in json.loads(self.entries_json)]
        except (ValueError, TypeError):
            return []

    def set_entries(self, entry_dicts):
        self.entries_json = json.dumps(entry_dicts, ensure_ascii=False)


class ActivityWindow(db.Model):
    __tablename__ = 'activity_windows'
    __table_args__ = (
        db.Index('ix_activity_windows_schedule_date', 'schedule_id', 'date'),
        # 唯一约束（T6 兜底）：窗口展开是删插事务，并发下唯一键拦住重复行，
        # 防同一课程窗口重复 → 同一活动发起两次签到
        db.UniqueConstraint('schedule_id', 'date', 'course_name', 'sections',
                            name='uq_activity_windows_schedule_date_course_sections'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedules.id'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    start_at = db.Column(db.DateTime, nullable=False)
    end_at = db.Column(db.DateTime, nullable=False)
    course_name = db.Column(db.String(64), nullable=False, default='')
    sections = db.Column(db.String(32), nullable=False, default='')   # 如 "1-4"，展示用
    last_polled_at = db.Column(db.DateTime)
    done = db.Column(db.Boolean, nullable=False, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'scheduleId': self.schedule_id,
            'date': self.date.isoformat() if self.date else '',
            'startAt': self.start_at.strftime('%Y-%m-%d %H:%M') if self.start_at else '',
            'endAt': self.end_at.strftime('%Y-%m-%d %H:%M') if self.end_at else '',
            'courseName': self.course_name,
            'sections': self.sections,
            'lastPolledAt': self.last_polled_at.strftime('%Y-%m-%d %H:%M') if self.last_polled_at else '',
            'done': bool(self.done),
        }
