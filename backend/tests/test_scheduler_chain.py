# backend/tests/test_scheduler_chain.py
# 模块 D：调度器主链路 —— resolve→前置检查→执行→写记录→状态回写→推送分发
# 用 Stub 适配器（USE_STUB_BPLATFORM=1）验证整条链路，不依赖真机。
# 调度器自动接管在测试环境关闭（conftest 设 SCHEDULER_ENABLED=0），此处显式驱动。
# 读记录/任务状态一律走 HTTP 接口（每次独立事务），规避直写会话的连接可见性差异。
import os

os.environ['USE_STUB_BPLATFORM'] = '1'

import uuid

from app.extensions import db
from app.models import BAccount, ConfigSet, Schedule, SignRecord, User
from app.services import scheduler as sch
from app.services.b_platform.base import BPlatformError, CheckinResult, VerifyResult


def _cfg(weekdays=(1, 2, 3, 4, 5)):
    return {'time': {'signTime': {'hour': 8, 'minute': 0}, 'startHour': 8, 'endHour': 22,
                     'weekdays': list(weekdays), 'randomDelayMax': 5, 'mode': 'normal'},
            'remarks': ['签到'], 'image': {'enabled': False, 'strategy': 'recycle'},
            'push': {}, 'advanced': {'uaTemplateId': None, 'customUa': ''}}


def _uid(c, headers):
    return c.get('/api/auth/me', headers=headers).get_json()['data']['user_id']


def _create_account(c, headers):
    name = f'tc_{uuid.uuid4().hex[:12]}'
    r = c.post('/api/accounts', json={'account': name, 'password': 'x1', 'type': 'dorm'}, headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()['data']['id']


def _create_config_set(c, headers, weekdays=(1, 2, 3, 4, 5)):
    r = c.post('/api/config-sets', json={'name': '链路口套', 'config': _cfg(weekdays)}, headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()['data']['id']


def _create_schedule(c, headers, acc_id, task_type='dorm'):
    r = c.post('/api/schedules', json={'accountId': acc_id, 'taskType': task_type}, headers=headers)
    assert r.status_code in (200, 201), r.get_json()
    return r.get_json()['data']['id']


def _enable(c, headers, sid, cs_id):
    r = c.put(f'/api/schedules/{sid}', json={'configSetId': cs_id, 'enabled': True}, headers=headers)
    assert r.status_code == 200, r.get_json()
    return r.get_json()['data']


def _records(c, headers, acc_id):
    return c.get(f'/api/accounts/{acc_id}/records', headers=headers).get_json()['data']['items']


def _schedule_dict(c, headers, sid):
    items = c.get('/api/schedules', headers=headers).get_json()['data']['items']
    return next((s for s in items if s['id'] == sid), None)


import pytest


@pytest.fixture(autouse=True)
def _clean_scheduler():
    """每个用例前清空调度器单例的 job，避免跨用例残留干扰。"""
    sch.get_scheduler().remove_all_jobs()
    yield
    sch.get_scheduler().remove_all_jobs()


@pytest.fixture
def chain_user(app_ctx):
    """独立唯一用户，避免与共享 tc_user 的其它测试互相污染 DB 行。"""
    from app.utils.auth import generate_token

    uname = f'tc_chain_{uuid.uuid4().hex[:10]}'
    u = User(username=uname, role='user', enabled=True, quota=100, used_quota=0)
    u.set_password('pw')
    db.session.add(u)
    db.session.commit()
    uid = u.id
    yield {'Authorization': f'Bearer {generate_token(u)}'}
    # teardown：清理本用户全部关联数据，杜绝跨测试残留
    SignRecord.query.filter_by(user_id=uid).delete()
    Schedule.query.filter_by(user_id=uid).delete()
    ConfigSet.query.filter_by(user_id=uid).delete()
    BAccount.query.filter_by(user_id=uid).delete()
    db.session.delete(u)
    db.session.commit()


def test_run_schedule_success_writes_record(app, chain_user):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)
    sid = _create_schedule(c, chain_user, acc_id)
    _enable(c, chain_user, sid, cs_id)

    sch.run_schedule(sid)
    # 刷新连接快照（MySQL REPEATABLE READ + 连接池复用），使后续 HTTP 读可见本次提交
    db.session.commit()

    recs = _records(c, chain_user, acc_id)
    assert any(r['result'] == 'success' for r in recs), recs
    s = _schedule_dict(c, chain_user, sid)
    assert s['lastStatus'] == 'success'
    assert s['runCount'] >= 1
    assert s['nextRunAt']


def test_run_schedule_disabled_account_skips_no_record(app, chain_user):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)
    sid = _create_schedule(c, chain_user, acc_id)
    _enable(c, chain_user, sid, cs_id)
    acc = db.session.get(__import__('app.models', fromlist=['BAccount']).BAccount, acc_id)
    acc.enabled = False
    db.session.commit()

    sch.run_schedule(sid)
    db.session.commit()

    assert _records(c, chain_user, acc_id) == []  # 账号禁用不写记录，避免刷屏
    s = _schedule_dict(c, chain_user, sid)
    assert s['lastStatus'] in (None, 'never')


def test_run_schedule_missing_config_skips(app, chain_user):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    sid = _create_schedule(c, chain_user, acc_id)
    # 直接 ORM 置为启用但无配置套（绕过路由开启校验，专测 resolve 缺失分支）
    s = db.session.get(Schedule, sid)
    s.enabled = True
    s.config_set_id = None
    s.mode = 'follow'
    db.session.commit()

    sch.run_schedule(sid)
    db.session.commit()

    recs = _records(c, chain_user, acc_id)
    assert any(r['result'] == 'skip' for r in recs), recs
    assert '配置缺失' in (recs[0]['failReason'] or '')


def test_run_schedule_checkin_error_writes_fail(app, chain_user, monkeypatch):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)
    sid = _create_schedule(c, chain_user, acc_id)
    _enable(c, chain_user, sid, cs_id)

    class FailAdapter:
        name = 'fail'

        def verify_and_fetch(self, *a, **k):
            return VerifyResult(ok=True, token='t', bp_uid=1, profile={})

        def checkin(self, session, task):
            raise BPlatformError('network', '断网了')

    monkeypatch.setattr(sch, 'get_adapter', lambda: FailAdapter())

    sch.run_schedule(sid)
    db.session.commit()

    recs = _records(c, chain_user, acc_id)
    assert any(r['result'] == 'fail' for r in recs), recs
    assert 'B 平台错误' in (recs[0]['failReason'] or '')


def test_sync_schedule_register_and_remove(app, chain_user):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)
    sid = _create_schedule(c, chain_user, acc_id)
    jid = sch._job_id(sid)

    _enable(c, chain_user, sid, cs_id)
    assert sch.get_scheduler().get_job(jid) is not None

    c.put(f'/api/schedules/{sid}', json={'enabled': False}, headers=chain_user)
    assert sch.get_scheduler().get_job(jid) is None


def test_reconcile_removes_orphan_and_registers_missing(app, chain_user):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)
    sid = _create_schedule(c, chain_user, acc_id)
    sid2 = _create_schedule(c, chain_user, acc_id, task_type='activity')
    jid = sch._job_id(sid)

    # 经路由启用 → 事件钩子注册 job
    _enable(c, chain_user, sid, cs_id)
    assert sch.get_scheduler().get_job(jid) is not None

    # 模拟孤儿：直接删 Schedule 行（如账号级联删除绕过路由）
    orphan = db.session.get(Schedule, sid)
    db.session.delete(orphan)
    db.session.commit()
    sch.reconcile()
    assert sch.get_scheduler().get_job(jid) is None

    # 另一条启用任务经 ORM 直接建立（错过事件钩子）→ 对账补注册
    s2 = db.session.get(Schedule, sid2)
    s2.enabled = True
    s2.config_set_id = cs_id
    s2.mode = 'follow'
    db.session.commit()
    sch.reconcile()
    assert sch.get_scheduler().get_job(sch._job_id(sid2)) is not None


def test_register_all_enabled(app, chain_user):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)
    sid1 = _create_schedule(c, chain_user, acc_id)
    sid2 = _create_schedule(c, chain_user, acc_id, task_type='activity')
    for sid in (sid1, sid2):
        s = db.session.get(Schedule, sid)
        s.enabled = True
        s.config_set_id = cs_id
        s.mode = 'follow'
    db.session.commit()

    sch.register_all_enabled()

    assert sch.get_scheduler().get_job(sch._job_id(sid1)) is not None
    assert sch.get_scheduler().get_job(sch._job_id(sid2)) is not None


def test_register_job_applies_random_delay_jitter(app, chain_user):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user, weekdays=(1,))  # randomDelayMax=5（见 _cfg）
    sid = _create_schedule(c, chain_user, acc_id)
    s = db.session.get(Schedule, sid)
    s.enabled = True
    s.config_set_id = cs_id
    s.mode = 'follow'
    db.session.commit()

    sch._register_job(s)
    job = sch.get_scheduler().get_job(sch._job_id(sid))
    assert job is not None
    # CronTrigger.jitter 单位为秒；randomDelayMax=5 分钟 → 300 秒
    assert job.trigger.jitter == 300


def test_register_job_no_jitter_when_delay_zero(app, chain_user):
    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user, weekdays=(1,))
    # 把配置套 randomDelayMax 改 0（config 是只读 property，必须用 set_config）
    cs = db.session.get(ConfigSet, cs_id)
    cfg = dict(cs.config)
    cfg['time'] = dict(cfg['time'])
    cfg['time']['randomDelayMax'] = 0
    cs.set_config(cfg)
    db.session.commit()
    sid = _create_schedule(c, chain_user, acc_id)
    s = db.session.get(Schedule, sid)
    s.enabled = True
    s.config_set_id = cs_id
    s.mode = 'follow'
    db.session.commit()

    sch._register_job(s)
    job = sch.get_scheduler().get_job(sch._job_id(sid))
    assert job is not None
    assert job.trigger.jitter is None


def test_resolve_merges_overrides(app, chain_user):
    """follow 模式 = 配置套 + 覆盖浅合并：覆盖键生效，未覆盖键继续跟随配置套；
    执行时刻解析（注册/展示共用）同口径应用覆盖。"""
    from app.utils.schedule_utils import extract_schedule_time

    c = app.test_client()
    acc_id = _create_account(c, chain_user)
    cs_id = _create_config_set(c, chain_user)  # 08:00，randomDelayMax=5，remarks=['签到']
    sid = _create_schedule(c, chain_user, acc_id)
    _enable(c, chain_user, sid, cs_id)
    ov = {'time': {'signTime': {'hour': 7, 'minute': 30}, 'startHour': 8, 'endHour': 22,
                   'weekdays': [1], 'randomDelayMax': 2, 'mode': 'normal'}}
    r = c.put(f'/api/schedules/{sid}', json={'overrides': ov}, headers=chain_user)
    assert r.status_code == 200, r.get_json()

    with app.app_context():
        s = db.session.get(Schedule, sid)
        merged = sch._resolve(s)
    assert merged['time']['signTime']['hour'] == 7      # 覆盖生效
    assert merged['remarks'] == ['签到']                # 未覆盖键继续跟随配置套

    hour, minute, weekdays = extract_schedule_time(db.session.get(Schedule, sid))
    assert (hour, minute, weekdays) == (7, 30, [1])
