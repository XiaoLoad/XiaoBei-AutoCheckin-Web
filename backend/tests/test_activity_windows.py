# 活动课表驱动调度单测：activity 配置解析归一化 + 当日窗口展开数学
# （课表条目 × 作息时间 × 提前/延续/过滤）。窗口断言口径与人工推演一致：
# 周一 1-8 节（08:20 开课 / 17:40 下课）+ lead15/tail30 → 窗口 08:05 ~ 18:10。
from datetime import date, datetime

import pytest

from app.extensions import db
from app.models import (ActivityWindow, BAccount, ConfigSet, JwSemester,
                        JwTimetable, Schedule, SystemConfig, User)
from app.services.jwxt.base import TimetableEntry
from app.services.jwxt.sync import (expand_windows_for_schedule,
                                    get_period_times)
from app.utils.schedule_utils import resolve_activity_cfg


def _cleanup_jw_test_data(user_id=None, username=None):
    """幂等清理本测试的全部数据（共享 MySQL，先前失败运行的残留会让 setup 直接撞唯一键，
    且 setup 失败时 teardown 不会执行，故创建前也清一次）。"""
    from sqlalchemy import or_
    users = User.query.filter(or_(User.id == user_id, User.username == username)).all() \
        if user_id or username else []
    for u in users:
        ActivityWindow.query.filter(ActivityWindow.schedule_id.in_(
            [s.id for s in Schedule.query.filter_by(user_id=u.id).all()])).delete(
            synchronize_session=False)
        for acc in BAccount.query.filter_by(user_id=u.id).all():
            JwTimetable.query.filter_by(b_account_id=acc.id).delete(synchronize_session=False)
        Schedule.query.filter_by(user_id=u.id).delete(synchronize_session=False)
        ConfigSet.query.filter_by(user_id=u.id).delete(synchronize_session=False)
        BAccount.query.filter_by(user_id=u.id).delete(synchronize_session=False)
        User.query.filter_by(id=u.id).delete(synchronize_session=False)
    SystemConfig.query.filter_by(key='class_period_times').delete(synchronize_session=False)
    JwSemester.query.filter_by(semester='2026-2027-1').delete(synchronize_session=False)
    db.session.commit()


@pytest.fixture()
def jw_env(app_ctx):
    """一套最小可用环境：用户 + B 账号 + 配置套 + 活动 course 策略任务 + 课表与学期。"""
    _cleanup_jw_test_data(username='jw_test_user')
    user = User(username='jw_test_user', role='user', enabled=True, quota=100, used_quota=0)
    user.set_password('pw-jw_test_user')
    db.session.add(user)
    db.session.flush()
    acc = BAccount(user_id=user.id, account='jw_test_bp', platform='B 打卡平台',
                   type='general', enabled=True)
    acc.set_password('bp-pwd')
    db.session.add(acc)
    db.session.flush()
    cs = ConfigSet(user_id=user.id, name='jw测试套', is_default=False)
    cs.set_config({
        'time': {'signTime': {'hour': 8, 'minute': 0}, 'startHour': 8, 'endHour': 22,
                 'weekdays': [1, 2, 3, 4, 5, 6, 7], 'randomDelayMax': 5, 'mode': 'normal'},
        'locationId': None,
        'remarks': ['测试备注'],
        'image': {'enabled': False, 'strategy': 'recycle', 'groupId': ''},
        'push': {'channels': []},
        'advanced': {'uaTemplateId': None, 'customUa': ''},
        'fence': {'intercept': True},
        'activity': {'strategy': 'course', 'course': {'leadMinutes': 15, 'tailMinutes': 30,
                                                      'pollIntervalSec': 120,
                                                      'excludeCourses': ['企业项目实践']},
                     'fallback': {'enabled': False}},
    })
    db.session.add(cs)
    db.session.flush()
    sched = Schedule(user_id=user.id, account_id=acc.id, task_type='activity',
                     mode='standalone', enabled=True, config_set_id=cs.id)
    sched.set_config(cs.config)
    db.session.add(sched)
    db.session.flush()
    db.session.add(JwSemester(semester='2026-2027-1', week1_monday=date(2026, 9, 7),
                              total_weeks=25))
    tt = JwTimetable(b_account_id=acc.id, semester='2026-2027-1', content_hash='test')
    tt.set_entries([
        TimetableEntry(weekday=1, course='Web开发技术课程设计', teacher='李路加',
                       weeks=[1, 2], sections=[1, 2, 3, 4, 5, 6, 7, 8], room='厚德楼306').to_dict(),
        TimetableEntry(weekday=7, course='形势与政策4', teacher='肖和平',
                       weeks=[5, 6], sections=[3, 4], room='').to_dict(),
        TimetableEntry(weekday=4, course='移动应用开发技术课程设计', teacher='左亚玲',
                       weeks=[3, 5], sections=[5, 6, 7, 8], room='厚德楼304').to_dict(),
        TimetableEntry(weekday=3, course='企业项目实践', teacher='企业教师',
                       weeks=[6, 7, 8, 9], sections=[1, 2], room='').to_dict(),
    ])
    db.session.add(tt)
    db.session.commit()
    yield {'user': user, 'account': acc, 'schedule': sched, 'config_set': cs}
    # 清理：测试数据不残留（共享库；幂等清理见上）
    _cleanup_jw_test_data(user_id=user.id)


def test_resolve_activity_cfg_normalization(jw_env):
    sched = jw_env['schedule']
    act = resolve_activity_cfg(sched)
    assert act is not None
    assert act == {'lead': 15, 'tail': 30, 'poll': 120, 'exclude': ['企业项目实践'],
                   'weekdays': None, 'fallbackEnabled': False}


def test_resolve_activity_cfg_none_for_dorm(app_ctx):
    sched = Schedule(task_type='dorm', mode='standalone')
    sched.set_config({'activity': {'strategy': 'course'}})
    assert resolve_activity_cfg(sched) is None


def test_expand_windows_monday_week1(jw_env):
    sched = jw_env['schedule']
    count = expand_windows_for_schedule(sched, today=date(2026, 9, 7))   # 第 1 周周一
    assert count == 1
    rows = (ActivityWindow.query.filter_by(schedule_id=sched.id).all())
    assert len(rows) == 1
    w = rows[0]
    assert w.course_name == 'Web开发技术课程设计'
    assert w.start_at == datetime(2026, 9, 7, 8, 5)    # 08:20 - lead15
    assert w.end_at == datetime(2026, 9, 7, 18, 10)    # 17:40 + tail30
    assert w.sections == '1-8'
    assert w.done is False


def test_expand_windows_sunday_and_exclude(jw_env):
    # 第 5 周周日：形势与政策4 有窗口；第 6 周周三的企业项目实践被 excludeCourses 排除
    sched = jw_env['schedule']
    expand_windows_for_schedule(sched, today=date(2026, 10, 11))   # 第 5 周周日（教务口径）
    rows = ActivityWindow.query.filter_by(schedule_id=sched.id).all()
    assert [w.course_name for w in rows] == ['形势与政策4']
    assert rows[0].start_at == datetime(2026, 10, 11, 10, 10)   # 10:25 - 15
    assert rows[0].end_at == datetime(2026, 10, 11, 12, 35)     # 12:05 + 30

    expand_windows_for_schedule(sched, today=date(2026, 10, 14))   # 第 6 周周三
    # 展开按日期替换：仅当日窗口应为空（企业项目实践被排除，周三无其余课程）
    rows = ActivityWindow.query.filter_by(schedule_id=sched.id, date=date(2026, 10, 14)).all()
    assert rows == []


def test_expand_windows_holiday_clears(jw_env):
    # 第 20 周（寒假阶段课表仍在周历内但无课）与周历之前（寒假之外）都应为空窗口
    sched = jw_env['schedule']
    assert expand_windows_for_schedule(sched, today=date(2026, 8, 20)) == 0   # 开学前
    rows = ActivityWindow.query.filter_by(schedule_id=sched.id).all()
    assert rows == []


def test_expand_windows_preserves_poll_state(jw_env):
    sched = jw_env['schedule']
    expand_windows_for_schedule(sched, today=date(2026, 9, 7))
    row = ActivityWindow.query.filter_by(schedule_id=sched.id).one()
    row.done = True
    row.last_polled_at = datetime(2026, 9, 7, 9, 0)
    db.session.commit()
    # 重复展开（如再次同步/调度心跳触发）不得丢失轮询状态
    expand_windows_for_schedule(sched, today=date(2026, 9, 7))
    row2 = ActivityWindow.query.filter_by(schedule_id=sched.id).one()
    assert row2.done is True
    assert row2.last_polled_at == datetime(2026, 9, 7, 9, 0)


def test_get_period_times_default_and_override(jw_env):
    times = get_period_times()
    assert str(times[1][0]) == '08:20:00'
    assert str(times[12][1]) == '22:30:00'
    # system_configs JSON 覆盖整表校准
    from app.models import SystemConfig
    db.session.add(SystemConfig(key='class_period_times', value='{"1": "08:30-09:15"}'))
    db.session.commit()
    times2 = get_period_times()
    assert str(times2[1][0]) == '08:30:00'
    assert str(times2[2][0]) == '09:15:00'   # 未覆盖的小节仍走默认
