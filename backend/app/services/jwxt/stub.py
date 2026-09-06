# 教务适配离线桩（USE_STUB_JWXT=true 时启用）：不访问网络，返回固定课表，
# 供前后端联调降级与测试环境使用。形状与 real.py 完全一致。
from app.services.jwxt.base import TimetableEntry

_STUB_SEMESTER = '2026-2027-1'
_STUB_ENTRIES = [
    TimetableEntry(course='Web开发技术课程设计', teacher='李路加', weeks=[1, 2],
                   sections=[1, 2, 3, 4, 5, 6, 7, 8], room='厚德楼306', weekday=1),
    TimetableEntry(course='形势与政策4', teacher='肖和平', weeks=[5, 6],
                   sections=[3, 4], room='', weekday=7),
]


class StubJwxtClient:
    def login(self, student_no, password):
        from app.services.jwxt.real import RealJwxtClient
        _ = RealJwxtClient  # noqa: F841  形状对齐说明用
        return object()  # 桩会话无状态

    def fetch_current_semester(self, session):
        return _STUB_SEMESTER

    def fetch_timetable(self, session, semester=None):
        return [TimetableEntry(**e.to_dict()) for e in _STUB_ENTRIES]

    def fetch_week_calendar(self, session, semester):
        from datetime import date
        return date(2026, 9, 7), 25

    def verify_session(self, session):
        return True
