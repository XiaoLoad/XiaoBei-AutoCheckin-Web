# 节假日模式回归：法定假期段跳过（skip 落库）、双休/调休补班照跑、末日豁免开关
# 两态、normal 模式不受影响、库未覆盖年份 fail-open。日期取 2026 国庆实测窗口
# （10-01~10-07 假期段，10-10 调休补班，10-11 普通周日）。
import uuid
from datetime import date

import pytest

from app.extensions import db
from app.models import BAccount, Schedule, SignRecord, User
from app.services import scheduler as sch
from app.services.holiday import (SKIP_HOLIDAY, SKIP_LAST_DAY, is_last_day_of_holiday,
                                  is_legal_holiday, holiday_skip_reason)

# 2026 年实测锚点（chinesecalendar 1.11.0）
D_HOLIDAY_START = date(2026, 10, 1)   # 国庆假期首日（周四）
D_HOLIDAY_MID = date(2026, 10, 5)     # 假期段内周一
D_HOLIDAY_LAST = date(2026, 10, 7)    # 假期末日（周三）
D_WORKDAY_AFTER = date(2026, 10, 8)   # 假期后第一个工作日（周四）
D_ORDINARY_SAT = date(2026, 9, 12)    # 普通周六（双休不算假）
D_MAKEUP_SAT = date(2026, 10, 10)     # 调休补班周六
D_ORDINARY_SUN = date(2026, 10, 11)   # 普通周日（假期段外）


def _resolved(mode='holiday', last_day_sign=False):
    return {'time': {'mode': mode, 'weekdays': [1, 2, 3, 4, 5, 6, 7],
                     'holiday': {'lastDaySign': last_day_sign}}}


# ===== holiday.py 纯判定层 =====

def test_legal_holiday_covers_period_including_weekend_in_period():
    assert is_legal_holiday(D_HOLIDAY_START)
    assert is_legal_holiday(D_HOLIDAY_MID)
    assert is_legal_holiday(D_HOLIDAY_LAST)


def test_ordinary_weekend_is_not_holiday():
    """双休不算假日：普通周六/周日不在假期段字典内"""
    assert not is_legal_holiday(D_ORDINARY_SAT)
    assert not is_legal_holiday(D_ORDINARY_SUN)


def test_makeup_workday_is_not_holiday():
    assert not is_legal_holiday(D_MAKEUP_SAT)


def test_last_day_detection():
    assert is_last_day_of_holiday(D_HOLIDAY_LAST)
    assert not is_last_day_of_holiday(D_HOLIDAY_MID)
    assert not is_last_day_of_holiday(D_WORKDAY_AFTER)


def test_skip_reason_modes():
    # normal 模式恒不跳过（普通周末照跑由 weekdays 决定，与此判定无关）
    for d in (D_HOLIDAY_START, D_HOLIDAY_LAST, D_ORDINARY_SUN, D_MAKEUP_SAT):
        assert holiday_skip_reason(_resolved(mode='normal'), d) is None
    # holiday 模式：假期段内跳过
    assert holiday_skip_reason(_resolved(), D_HOLIDAY_START) == SKIP_HOLIDAY
    assert holiday_skip_reason(_resolved(), D_HOLIDAY_MID) == SKIP_HOLIDAY
    # 假期段外不跳过
    assert holiday_skip_reason(_resolved(), D_WORKDAY_AFTER) is None
    assert holiday_skip_reason(_resolved(), D_ORDINARY_SUN) is None
    assert holiday_skip_reason(_resolved(), D_MAKEUP_SAT) is None


def test_last_day_switch_two_states():
    # 默认关闭：末日也跳过
    assert holiday_skip_reason(_resolved(), D_HOLIDAY_LAST) == SKIP_LAST_DAY
    # 开启：末日照常执行
    assert holiday_skip_reason(_resolved(last_day_sign=True), D_HOLIDAY_LAST) is None


def test_fail_open_on_uncovered_year():
    """库未覆盖的年份 holidays.get 返回 None → 视为非假期照常执行"""
    assert holiday_skip_reason(_resolved(), date(2030, 10, 1)) is None


def test_holiday_block_missing_defaults_closed():
    """旧配置无 time.holiday 子块：末日开关按关闭处理（末日跳过）"""
    resolved = {'time': {'mode': 'holiday', 'weekdays': [1, 2, 3, 4, 5, 6, 7]}}
    assert holiday_skip_reason(resolved, D_HOLIDAY_LAST) == SKIP_LAST_DAY
    assert holiday_skip_reason(resolved, D_HOLIDAY_MID) == SKIP_HOLIDAY


# ===== 执行链路（_execute 前置判定 → skip 落库）=====

@pytest.fixture()
def holiday_env(app_ctx):
    uname = f'tc_hol_{uuid.uuid4().hex[:10]}'
    u = User(username=uname, role='user', enabled=True, quota=10, used_quota=0)
    u.set_password('pw')
    db.session.add(u)
    db.session.flush()
    acc = BAccount(user_id=u.id, account=f'hol_{uname}', password_enc='x')
    db.session.add(acc)
    db.session.flush()
    s = Schedule(user_id=u.id, account_id=acc.id, task_type='dorm',
                 mode='standalone', enabled=True)
    s.set_config({'time': {'signTime': {'hour': 8, 'minute': 0}, 'startHour': 8,
                           'endHour': 22, 'weekdays': [1, 2, 3, 4, 5, 6, 7],
                           'randomDelayMax': 5, 'mode': 'holiday',
                           'holiday': {'lastDaySign': False}},
                  'remarks': ['签到'], 'image': {'enabled': False},
                  'push': {}, 'advanced': {}})
    db.session.add(s)
    db.session.commit()
    yield {'user': u, 'acc': acc, 'schedule': s}
    db.session.rollback()


def test_execute_skips_on_legal_holiday(holiday_env, monkeypatch):
    """holiday 模式 + 法定假日：登录前直接 skip 落库，不触碰平台适配器"""
    s = holiday_env['schedule']

    def _boom(*a, **kw):
        raise AssertionError('法定假日不应走到平台适配器')

    monkeypatch.setattr(sch, 'get_adapter', _boom)
    monkeypatch.setattr(sch, '_resolve', lambda schedule: _resolved('holiday'))
    # _execute 内取真实今天执行判定；测试把「今天」钉在假期中段，避免跨日跑测漂移
    monkeypatch.setattr(sch, 'holiday_skip_reason',
                        lambda resolved: holiday_skip_reason(resolved, D_HOLIDAY_MID))

    sch._execute(s)
    recs = SignRecord.query.filter_by(schedule_id=s.id).all()
    assert len(recs) == 1
    assert recs[0].status == 'skip'
    assert recs[0].fail_reason == SKIP_HOLIDAY
    # 跳过也回写任务节奏
    assert holiday_env['schedule'].last_status == 'skip'


def test_execute_runs_on_ordinary_weekend(holiday_env, monkeypatch):
    """holiday 模式 + 普通周日（假期段外）：不跳过，继续走正常执行链"""
    s = holiday_env['schedule']
    called = {}
    monkeypatch.setattr(sch, '_resolve', lambda schedule: _resolved('holiday'))
    monkeypatch.setattr(sch, 'holiday_skip_reason', lambda resolved: None)
    # 走到凭据校验即证明未被节假日拦截；凭据失败就地返回，链路到此为止
    real_get_password = holiday_env['acc'].get_password

    def _fake_get_password():
        called['reached'] = True
        raise Exception('链路已越过节假日判定')

    holiday_env['acc'].get_password = _fake_get_password
    try:
        sch._execute(s)
    except Exception:
        pass
    finally:
        holiday_env['acc'].get_password = real_get_password
    assert called.get('reached'), '普通周日应照常执行（未被节假日判定拦截）'


def test_execute_last_day_sign_switch_via_execute(holiday_env, monkeypatch):
    """末日豁免开关经 _execute 全链路验证：开启后末日不落 skip"""
    s = holiday_env['schedule']
    monkeypatch.setattr(sch, '_resolve',
                        lambda schedule: _resolved('holiday', last_day_sign=True))
    monkeypatch.setattr(sch, 'holiday_skip_reason',
                        lambda resolved: holiday_skip_reason(resolved, D_HOLIDAY_LAST))
    sch._execute(s)
    recs = SignRecord.query.filter_by(schedule_id=s.id).all()
    assert len(recs) == 1
    assert recs[0].status == 'fail'  # 走到了真实链路：凭据假数据执行失败（而非 skip）


def test_execute_normal_mode_untouched(holiday_env, monkeypatch):
    """normal 模式：即使当天是法定假日也不受节假日判定影响"""
    s = holiday_env['schedule']
    monkeypatch.setattr(sch, '_resolve',
                        lambda schedule: _resolved('normal'))
    monkeypatch.setattr(sch, 'holiday_skip_reason', holiday_skip_reason)
    monkeypatch.setattr(sch, 'get_adapter',
                        lambda: (_ for _ in ()).throw(AssertionError('不应调用')))
    sch._execute(s)
    recs = SignRecord.query.filter_by(schedule_id=s.id).all()
    # 无节假日拦截：直接走凭据校验失败路径（password_enc='x' 解密失败）
    assert len(recs) == 1
    assert recs[0].status == 'fail'
    assert recs[0].fail_reason.startswith('账号凭据解密失败')
