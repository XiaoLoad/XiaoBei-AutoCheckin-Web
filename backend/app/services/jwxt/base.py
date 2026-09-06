# 教务系统适配器公共载体（风格同 b_platform.base）：错误分类与解析结果结构。
# 本校部署为强智科技教务系统，数据路径仅一条：Web 页面 HTML（移动端 app.do 已被校方禁用，
# 见 docs/superpowers/specs/2026-09-06-activity-course-scheduling-design.md §2.7）。
from dataclasses import dataclass, field


class JwxtError(Exception):
    """教务系统交互异常。kind 用于上层分类处理：
    network=网络不可达 / credential=账号或密码错误 / captcha=触发验证码 / parse=页面结构异常"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message

    def __str__(self):
        return self.message


@dataclass
class TimetableEntry:
    """一条去重后的逻辑课程（同一课程块跨大节行重复渲染，已按
    星期+课程+老师+周次+周类型+小节+教室 归并）。weekday: 1=周一..7=周日；
    weeks 为已展开单双周后的周次列表；sections 为覆盖的小节（升序）。"""
    course: str
    teacher: str = ''
    clazz: str = ''
    weeks: list = field(default_factory=list)
    sections: list = field(default_factory=list)
    room: str = ''
    weekday: int = 0

    def to_dict(self):
        return {
            'weekday': self.weekday, 'course': self.course, 'teacher': self.teacher,
            'clazz': self.clazz, 'weeks': self.weeks, 'sections': self.sections,
            'room': self.room,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            weekday=int(d.get('weekday') or 0), course=d.get('course') or '',
            teacher=d.get('teacher') or '', clazz=d.get('clazz') or '',
            weeks=[int(x) for x in (d.get('weeks') or [])],
            sections=[int(x) for x in (d.get('sections') or [])],
            room=d.get('room') or '',
        )
