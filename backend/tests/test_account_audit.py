# 账号域 / 定时任务域操作审计回归：
# - 事件订阅链路把增删改写进 op_logs（account.create/update/delete、schedule.*）
# - 密码明文零泄漏：用真实密码字符串 grep 日志 detail 原文必须 0 命中（防回归的关键断言）
# - 受限回显接口：仅管理员、登录密码二次验证、限流、成功与失败都落审计
import types

import pytest

from app.extensions import db
from app.models import BAccount, PushLog, Schedule, SignRecord
from app.models.op_log import OpLog
from app.models.user import User, now_cst
from app.routes import admin as admin_routes

_REAL_PASSWORDS = ('S3cret-pw-9137', 'N3w-secret-77', 'The-Bpw-42')


def _seed_account(account, password='The-Bpw-42'):
    """ORM 直建账号（绕过 B 平台校验），返回已提交的 acc"""
    u = User.query.filter_by(username='tc_user').first()
    acc = BAccount.query.filter_by(user_id=u.id, account=account).first()
    if not acc:
        acc = BAccount(user_id=u.id, account=account)
        acc.set_password(password)
        db.session.add(acc)
        db.session.commit()
    return acc


@pytest.fixture()
def audit_cleanup(app_ctx):
    """收尾清 tc_ 前缀审计行与本文件造的账号（纪律同 test_op_logs.audit_cleanup）；
    回显接口的限流器是模块级状态，必须复位，否则用例间互相 429。"""
    admin_routes._secret_throttle._last.clear()

    def _purge():
        db.session.rollback()
        # 删序对齐仓库纪律：push_logs → sign_records → schedules → b_accounts，
        # 否则 schedules.account_id 的 FK 会把账号删除拦成 1451
        acc_ids = [a.id for a in BAccount.query.filter(BAccount.account.like('tc_audit_%')).all()]
        if acc_ids:
            PushLog.query.filter(PushLog.account_id.in_(acc_ids)).delete(synchronize_session=False)
            SignRecord.query.filter(SignRecord.account_id.in_(acc_ids)).delete(synchronize_session=False)
            Schedule.query.filter(Schedule.account_id.in_(acc_ids)).delete(synchronize_session=False)
        BAccount.query.filter(BAccount.account.like('tc_audit_%')).delete(synchronize_session=False)
        OpLog.query.filter(OpLog.username.like('tc_%')).delete(synchronize_session=False)
        db.session.commit()

    _purge()
    yield
    admin_routes._secret_throttle._last.clear()
    _purge()


def _latest(action, **kw):
    q = OpLog.query.filter_by(action=action)
    for f, v in kw.items():
        q = q.filter_by(**{f: v})
    return q.order_by(OpLog.id.desc()).first()


def test_create_account_writes_audit_without_plaintext(app_ctx, user_headers, audit_cleanup, monkeypatch):
    """添加账号落 account.create 审计；detail 与 summary 里不得出现明文密码"""
    monkeypatch.setattr(
        'app.routes.accounts._run_verify',
        lambda account, password: (types.SimpleNamespace(
            bp_uid=99001, profile={'name': '审计回显'}, token='tok-x'), None),
    )
    c = app_ctx.test_client()
    r = c.post('/api/accounts', headers=user_headers,
               json={'account': 'tc_audit_create', 'password': 'S3cret-pw-9137'})
    assert r.status_code == 201, r.get_json()

    row = _latest('account.create', category='account')
    assert row is not None
    assert 'tc_audit_create' in row.summary
    d = row.get_detail()
    assert d['passwordChanged'] is True and d['account'] == 'tc_audit_create'
    # 关键断言：明文密码在整行（summary + detail 原文）中零命中
    raw = (row.summary or '') + (row.detail or '')
    for pw in _REAL_PASSWORDS:
        assert pw not in raw


def test_update_account_password_audited_without_plaintext(app_ctx, user_headers, audit_cleanup, monkeypatch):
    """改密码落 account.update：passwordChanged=true 且无明文；空保存不记行"""
    # 改密码会重走 B 平台校验（need_verify），按纪律 monkeypatch 拦 HTTP 层
    monkeypatch.setattr(
        'app.routes.accounts._run_verify',
        lambda account, password: (types.SimpleNamespace(
            bp_uid=99001, profile={'name': '审计回显'}, token='tok-x'), None),
    )
    acc = _seed_account('tc_audit_upd', password='The-Bpw-42')
    c = app_ctx.test_client()

    r = c.put(f'/api/accounts/{acc.id}', headers=user_headers, json={'password': 'N3w-secret-77'})
    assert r.status_code == 200

    row = _latest('account.update', category='account')
    assert row is not None
    d = row.get_detail()
    assert d['passwordChanged'] is True
    raw = (row.summary or '') + (row.detail or '')
    for pw in _REAL_PASSWORDS:
        assert pw not in raw

    # 值未变的空保存不产生新审计行
    before_count = OpLog.query.filter_by(action='account.update').count()
    c.put(f'/api/accounts/{acc.id}', headers=user_headers, json={'enabled': True})
    assert OpLog.query.filter_by(action='account.update').count() == before_count


def test_delete_account_audit_records_cascade_counts(app_ctx, user_headers, audit_cleanup):
    """删账号的审计必须写清连带删除量（物理删除后无法反查）"""
    acc = _seed_account('tc_audit_del')
    s = Schedule(user_id=acc.user_id, account_id=acc.id, task_type='dorm', mode='custom',
                 custom_json='{"hour":8,"minute":0,"weekdays":[1]}')
    db.session.add(s)
    db.session.commit()
    db.session.add(SignRecord(
        user_id=acc.user_id, account_id=acc.id, schedule_id=s.id,
        task_name='寝室签到', task_type='dorm',
        sign_date=now_cst().date(), signed_at=now_cst(), status='success',
    ))
    db.session.commit()

    c = app_ctx.test_client()
    r = c.delete(f'/api/accounts/{acc.id}', headers=user_headers)
    assert r.status_code == 200

    row = _latest('account.delete', category='account')
    assert row is not None
    assert 'tc_audit_del' in row.summary
    assert row.get_detail()['cascade']['schedules'] == 1
    assert row.get_detail()['cascade']['signRecords'] == 1


def test_schedule_lifecycle_writes_audit(app_ctx, user_headers, audit_cleanup):
    """定时任务 建改删 + 批量关闭 各落一条审计；启停走 update 的 changes"""
    acc = _seed_account('tc_audit_sched')
    c = app_ctx.test_client()

    r = c.post('/api/schedules', headers=user_headers,
               json={'accountId': acc.id, 'taskType': 'dorm'})
    assert r.status_code == 201, r.get_json()
    sched_id = r.get_json()['data']['id']
    assert _latest('schedule.create', category='schedule') is not None

    # 启用（custom 模式合法参数）→ schedule.update，changes 里 enabled false→true + 配置占位项
    r = c.put(f'/api/schedules/{sched_id}', headers=user_headers,
              json={'mode': 'custom', 'custom': {'weekdays': [1], 'hour': 8, 'minute': 0},
                    'enabled': True})
    assert r.status_code == 200, r.get_json()
    row = _latest('schedule.update', category='schedule')
    changes = {(c['field'], c.get('from'), c.get('to')) for c in row.get_detail()['changes']}
    assert ('enabled', False, True) in changes
    # 提交的 custom 是内容不落日志的字段 → 只给「已更新」占位项（无 from/to）
    assert ('custom',) in {(c['field'],) for c in row.get_detail()['changes']}

    # 批量关闭 → schedule.disable 且 affected=1
    r = c.post('/api/schedules/batch-manage', headers=user_headers,
               json={'action': 'disable', 'targets': [{'accountId': acc.id, 'taskType': 'dorm'}]})
    assert r.status_code == 200, r.get_json()
    row = _latest('schedule.disable', category='schedule')
    assert row.get_detail()['affected'] == 1

    # 删除 → schedule.delete
    r = c.delete(f'/api/schedules/{sched_id}', headers=user_headers)
    assert r.status_code == 200
    assert _latest('schedule.delete', category='schedule') is not None


def test_secret_view_requires_admin(app_ctx, user_headers, audit_cleanup):
    """回显接口仅管理员：普通用户 403（哪怕是账号所有者本人）"""
    acc = _seed_account('tc_audit_sec')
    c = app_ctx.test_client()
    r = c.post(f'/api/admin/accounts/{acc.id}/secret', headers=user_headers,
               json={'login_password': 'whatever'})
    assert r.status_code == 403


def test_secret_view_success_audited_without_plaintext(app_ctx, admin_headers, audit_cleanup):
    """登录密码验证通过 → 返回明文一次；审计行不含 B 平台密码，也不含登录密码"""
    acc = _seed_account('tc_audit_sec', password='The-Bpw-42')
    c = app_ctx.test_client()
    r = c.post(f'/api/admin/accounts/{acc.id}/secret', headers=admin_headers,
               json={'login_password': 'pw-tc_admin'})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['data']['password'] == 'The-Bpw-42'
    assert r.headers.get('Cache-Control') == 'no-store'

    row = _latest('account.secret_view', category='account')
    assert row is not None and row.result == 'success'
    raw = (row.summary or '') + (row.detail or '')
    assert 'The-Bpw-42' not in raw
    assert 'pw-tc_admin' not in raw


def test_secret_view_wrong_password_audited_as_fail(app_ctx, admin_headers, audit_cleanup):
    """登录密码错误 → 400 且审计记 fail（暴力尝试的唯一线索）"""
    acc = _seed_account('tc_audit_sec')
    c = app_ctx.test_client()
    r = c.post(f'/api/admin/accounts/{acc.id}/secret', headers=admin_headers,
               json={'login_password': 'totally-wrong'})
    assert r.status_code == 400 and r.get_json()['code'] == 1002

    row = _latest('account.secret_view', category='account')
    assert row is not None and row.result == 'fail'


def test_secret_view_throttled_within_interval(app_ctx, admin_headers, audit_cleanup):
    """60s 间隔内的第二次查看被限流拦截（接口是登录密码的爆破面，不能敞开）"""
    acc = _seed_account('tc_audit_sec')
    c = app_ctx.test_client()
    body = {'login_password': 'pw-tc_admin'}
    first = c.post(f'/api/admin/accounts/{acc.id}/secret', headers=admin_headers, json=body)
    assert first.status_code == 200
    second = c.post(f'/api/admin/accounts/{acc.id}/secret', headers=admin_headers, json=body)
    assert second.status_code == 429
