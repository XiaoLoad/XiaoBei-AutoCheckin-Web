# 推送分发单测：验证 dispatch_push 能正确解析配置套 push 结构
# （直接填写 / 资源池凭证两种来源）、按 notify 开关分发、覆盖 serverchan / pushplus。
import json

import pytest

import app.services.scheduler as sch
from app.services.crypto import encrypt
from app.models.pools import PoolCredential
from app.models.push_log import PushLog
from app.models.user import User


@pytest.fixture(autouse=True)
def _clean_creds(app_ctx):
    # 逐通道跳过原因会写 push_logs（含本用例的「未绑定凭证」分支），一并按用户清理，避免残留
    yield
    uid = _uid(sch.db)
    sch.db.session.query(PushLog).filter_by(user_id=uid).delete()
    sch.db.session.query(PoolCredential).filter_by(user_id=uid).delete()
    sch.db.session.commit()


class _FakeSchedule:
    def __init__(self, user_id, task_type='dorm'):
        self.id = 0
        self.user_id = user_id
        self.task_type = task_type


class _FakeAcc:
    account = 'tc_push_acc'


def _make_cred(db, user_id, channel, fields):
    c = PoolCredential(user_id=user_id, channel=channel, name='t',
                       secret_enc=encrypt(json.dumps(fields, ensure_ascii=False)),
                       enabled=True)
    db.session.add(c)
    db.session.commit()
    return c.id


def _capture(monkeypatch, body=None):
    """伪造 requests.post：默认返回各通道业务成功码；body 可覆盖以模拟平台拒绝。
    HTTP 层通不代表送达——业务码校验依赖响应体，fake 须提供 json()。"""
    calls = []

    def fake_post(url, **kw):
        calls.append((url, kw))
        if body is None:
            payload = {'code': 200, 'msg': 'ok'} if 'pushplus' in url else {'code': 0, 'message': ''}
        else:
            payload = body
        return type('R', (), {'status_code': 200, 'json': lambda self: payload})()

    monkeypatch.setattr(sch.requests, 'post', fake_post)
    return calls


def _uid(db):
    u = User.query.filter_by(username='tc_push_user').first()
    if u is None:
        u = User(username='tc_push_user', role='user', enabled=True, quota=10, used_quota=0)
        u.set_password('pw')
        db.session.add(u)
        db.session.commit()
    return u.id


def test_dispatch_resolves_pool_credential_serverchan(app_ctx, monkeypatch):
    db = sch.db
    uid = _uid(db)
    cid = _make_cred(db, uid, 'serverchan', {'serverchanKey': 'SCTxyz'})

    calls = _capture(monkeypatch)
    resolved = {'push': {
        'channels': ['serverchan'],
        'useOwnCredential': True,
        'credIds': {'serverchan': cid, 'pushplus': None, 'email': None},
        'cred': {},
        'notify': {'success': True, 'skip': False, 'fail': False},
    }}
    sch.dispatch_push(resolved, _FakeSchedule(uid), _FakeAcc(), 'success')

    assert len(calls) == 1
    assert calls[0][0] == 'https://sctapi.ftqq.com/SCTxyz.send'


def test_dispatch_resolves_direct_fill_pushplus(app_ctx, monkeypatch):
    db = sch.db
    uid = _uid(db)

    calls = _capture(monkeypatch)
    resolved = {'push': {
        'channels': ['pushplus'],
        'useOwnCredential': False,
        'credIds': {'serverchan': None, 'pushplus': None, 'email': None},
        'cred': {'pushplusToken': 'PPTok'},
        'notify': {'success': True, 'skip': False, 'fail': False},
    }}
    sch.dispatch_push(resolved, _FakeSchedule(uid), _FakeAcc(), 'success')

    assert len(calls) == 1
    assert calls[0][0] == 'https://www.pushplus.plus/send'
    assert calls[0][1]['json']['token'] == 'PPTok'


def test_dispatch_respects_notify_success_off(app_ctx, monkeypatch):
    db = sch.db
    uid = _uid(db)
    cid = _make_cred(db, uid, 'serverchan', {'serverchanKey': 'SCTxyz'})

    calls = _capture(monkeypatch)
    resolved = {'push': {
        'channels': ['serverchan'],
        'useOwnCredential': True,
        'credIds': {'serverchan': cid, 'pushplus': None, 'email': None},
        'cred': {},
        'notify': {'success': False, 'skip': True, 'fail': True},  # 成功关闭
    }}
    sch.dispatch_push(resolved, _FakeSchedule(uid), _FakeAcc(), 'success')

    assert calls == []  # 成功开关关闭，不发


def test_dispatch_skip_fires_when_notify_skip_on(app_ctx, monkeypatch):
    db = sch.db
    uid = _uid(db)
    cid = _make_cred(db, uid, 'serverchan', {'serverchanKey': 'SCTxyz'})

    calls = _capture(monkeypatch)
    resolved = {'push': {
        'channels': ['serverchan'],
        'useOwnCredential': True,
        'credIds': {'serverchan': cid, 'pushplus': None, 'email': None},
        'cred': {},
        'notify': {'success': False, 'skip': True, 'fail': False},
    }}
    sch.dispatch_push(resolved, _FakeSchedule(uid), _FakeAcc(), 'skip', reason='平台返回跳过')

    assert len(calls) == 1
    assert '跳过' in calls[0][1]['data']['title']


def _resolved_for(channels, cred_ids=None, cred=None, uid=None):
    return {'push': {
        'channels': channels,
        'useOwnCredential': cred_ids is not None,
        'credIds': cred_ids or {'serverchan': None, 'pushplus': None, 'email': None},
        'cred': cred or {},
        'notify': {'success': True, 'skip': False, 'fail': False},
    }}


def test_send_channel_serverchan_rejected_on_business_code(monkeypatch):
    """ServerChan HTTP 200 但 code!=0（如 key 无效）必须判失败并带回平台原因"""
    from app.services.push_render import send_channel, build_ctx
    monkeypatch.setattr(
        sch.requests, 'post',
        lambda url, **kw: type('R', (), {'status_code': 200,
                                         'json': lambda self: {'code': 400, 'message': '无效的key'}})())
    ctx = build_ctx(_FakeAcc(), _FakeSchedule(1), {}, 'success')
    ok, err = send_channel('serverchan', 'SCTbad', ctx)
    assert ok is False
    assert 'code=400' in err and '无效的key' in err


def test_send_channel_pushplus_rejected_on_business_code(monkeypatch):
    """PushPlus HTTP 200 但 code!=200（如 token 失效）必须判失败并带回平台原因"""
    from app.services.push_render import send_channel, build_ctx
    monkeypatch.setattr(
        sch.requests, 'post',
        lambda url, **kw: type('R', (), {'status_code': 200,
                                         'json': lambda self: {'code': 903, 'msg': 'token验证失败'}})())
    ctx = build_ctx(_FakeAcc(), _FakeSchedule(1), {}, 'success')
    ok, err = send_channel('pushplus', 'PPTbad', ctx)
    assert ok is False
    assert 'code=903' in err and 'token验证失败' in err


def test_send_channel_non_json_response_is_failure(monkeypatch):
    """响应体非 JSON（网关错误页等）不得假报成功"""
    from app.services.push_render import send_channel, build_ctx
    monkeypatch.setattr(
        sch.requests, 'post',
        lambda url, **kw: type('R', (), {'status_code': 502,
                                         'json': lambda self: (_ for _ in ()).throw(ValueError())})())
    ctx = build_ctx(_FakeAcc(), _FakeSchedule(1), {}, 'success')
    ok, err = send_channel('serverchan', 'SCTx', ctx)
    assert ok is False
    assert '502' in err


def test_build_ctx_initiator_passthrough():
    """发起人须用 B 平台真实字段透传，而非写死的「系统自动」；缺省回退「—」。"""
    from app.services.push_render import build_ctx
    ctx = build_ctx(_FakeAcc(), _FakeSchedule(1), {}, 'success', initiator='张三 · 辅导员')
    assert ctx['initiator'] == '张三 · 辅导员'
    # 无 task（如跳过无进行中任务）时不应再出现旧的硬编码占位
    ctx_default = build_ctx(_FakeAcc(), _FakeSchedule(1), {}, 'skip')
    assert ctx_default['initiator'] == '—'


def _resolved_multi(uid=None):
    return {'push': {
        'channels': ['pushplus', 'email'],
        'useOwnCredential': False,
        'credIds': {'serverchan': None, 'pushplus': None, 'email': None},
        'cred': {
            'pushplusToken': 'PPTok',
            'emailSmtp': 'smtp.example.com', 'emailFrom': 'a@b.com',
            'emailPass': 'pw', 'emailTo': 'c@d.com',
        },
        'notify': {'success': True, 'skip': False, 'fail': False},
    }}


def test_dispatch_push_one_channel_exception_does_not_block_others(app_ctx, monkeypatch):
    """某通道内部异常（如 PushPlus 网络错误抛 RuntimeError）不得阻断其它通道。
    回归：dispatch_push 循环曾缺 try/except，单个 send_channel 抛异常会令整个循环崩溃，
    后续通道（如邮件）整体不推送，表现为「设置了推送但从不推送」且无从排查。"""
    uid = _uid(sch.db)
    calls = []
    def fake_send_channel(channel, key, ctx, template):
        calls.append(channel)
        if channel == 'pushplus':
            raise RuntimeError('模拟 PushPlus 网络异常')
        return True, ''
    monkeypatch.setattr(sch, 'send_channel', fake_send_channel)
    sch.dispatch_push(_resolved_multi(), _FakeSchedule(uid), _FakeAcc(), 'success')
    assert 'pushplus' in calls
    assert 'email' in calls  # 关键断言：pushplus 异常后仍尝试了 email


def test_dispatch_push_one_channel_business_failure_does_not_block_others(app_ctx, monkeypatch):
    """某通道业务失败（返回 (False, 原因)）同样不得阻断其它通道。

    失败通道由 _send_one 按 PUSH_SEND_ATTEMPTS 重试，故此处不能断言精确的调用序列
    （历史上按 ['pushplus','email'] 等值断言，重试特性落地后即失效）；
    改为与异常分支同口径：验证失败通道确实尝试过、且其它通道未被阻断。
    """
    uid = _uid(sch.db)
    calls = []
    def fake_send_channel(channel, key, ctx, template):
        calls.append(channel)
        if channel == 'pushplus':
            return False, 'token 失效'
        return True, ''
    monkeypatch.setattr(sch, 'send_channel', fake_send_channel)
    sch.dispatch_push(_resolved_multi(), _FakeSchedule(uid), _FakeAcc(), 'success')
    assert 'pushplus' in calls                                  # 失败通道已尝试
    assert 'email' in calls                                     # 关键断言：未被阻断
    assert calls.count('pushplus') == sch.PUSH_SEND_ATTEMPTS    # 失败按配置重试不再静默


class _FakeAccOwnCreds:
    """带账号级推送凭证绑定的桩账号（方案一：各账号自带凭证）。"""
    def __init__(self, creds):
        self.account = 'tc_push_acc'
        self.push_creds = creds


def _account_push_resolved(channels, set_cred_ids=None):
    return {'push': {
        'channels': channels,
        'useOwnCredential': True,
        'useAccountCredential': True,
        'credIds': set_cred_ids or {'serverchan': None, 'pushplus': None, 'email': None},
        'cred': {},
        'notify': {'success': True, 'skip': False, 'fail': False},
    }}


def test_dispatch_account_credential_used_when_bound(app_ctx, monkeypatch):
    """useAccountCredential：按执行账号绑定的凭证推送（不同账号各推各的目标）"""
    db = sch.db
    uid = _uid(db)
    cid_a = _make_cred(db, uid, 'serverchan', {'serverchanKey': 'ACCA'})
    cid_b = _make_cred(db, uid, 'serverchan', {'serverchanKey': 'ACCB'})

    calls = _capture(monkeypatch)
    resolved = _account_push_resolved(['serverchan'])
    sch.dispatch_push(resolved, _FakeSchedule(uid), _FakeAccOwnCreds({'serverchan': cid_b}), 'success')
    assert [c[0] for c in calls] == ['https://sctapi.ftqq.com/ACCB.send']

    calls.clear()
    sch.dispatch_push(resolved, _FakeSchedule(uid), _FakeAccOwnCreds({'serverchan': cid_a}), 'success')
    assert [c[0] for c in calls] == ['https://sctapi.ftqq.com/ACCA.send']


def test_dispatch_account_credential_falls_back_to_set(app_ctx, monkeypatch):
    """账号未绑定该通道 → 回落配置套 credIds（允许多数账号共用、个别账号自带）"""
    db = sch.db
    uid = _uid(db)
    cid = _make_cred(db, uid, 'serverchan', {'serverchanKey': 'SETKEY'})

    calls = _capture(monkeypatch)
    resolved = _account_push_resolved(['serverchan'], {'serverchan': cid, 'pushplus': None, 'email': None})
    sch.dispatch_push(resolved, _FakeSchedule(uid), _FakeAccOwnCreds({}), 'success')
    assert [c[0] for c in calls] == ['https://sctapi.ftqq.com/SETKEY.send']


def test_dispatch_account_credential_missing_skips_without_send(app_ctx, monkeypatch):
    """账号未绑定且配置套也无回落 → 不发，逐通道记跳过原因（进 push_logs）"""
    uid = _uid(sch.db)
    calls = _capture(monkeypatch)
    sch.dispatch_push(_account_push_resolved(['serverchan']), _FakeSchedule(uid), _FakeAccOwnCreds({}), 'success')
    assert calls == []


# ---- 账号级邮件收件人：与凭证来源正交（发件端共享、收件人随账号）----

def _capture_channel(monkeypatch):
    """拦在 send_channel 层：拿到 dispatcher 真正解出的通道密钥/字段"""
    seen = {}

    def fake_send_channel(channel, key, ctx, template):
        seen[channel] = key
        return True, ''

    monkeypatch.setattr(sch, 'send_channel', fake_send_channel)
    return seen


def _email_cred(db, uid, to='default@x.com'):
    return _make_cred(db, uid, 'email', {
        'emailSmtp': 'smtp.example.com', 'emailFrom': 'sender@b.com',
        'emailPass': 'pw', 'emailTo': to,
    })


def _email_resolved(set_cred_ids=None, mode='account', cred=None):
    """mode: account=各账号自带 / pool=回填我的凭证 / direct=直接填写"""
    return {'push': {
        'channels': ['email'],
        'useOwnCredential': mode == 'pool',
        'useAccountCredential': mode == 'account',
        'credIds': set_cred_ids or {'serverchan': None, 'pushplus': None, 'email': None},
        'cred': cred or {},
        'notify': {'success': True, 'skip': False, 'fail': False},
    }}


def test_account_email_recipient_overrides_credential_default(app_ctx, monkeypatch):
    """账号自带邮件凭证 + 账号级收件人 → 用账号的收件人，而不是凭证里的默认收件人"""
    db = sch.db
    uid = _uid(db)
    cid = _email_cred(db, uid)

    seen = _capture_channel(monkeypatch)
    acc = _FakeAccOwnCreds({'email': {'credId': cid, 'to': 'mine@x.com, other@y.com'}})
    sch.dispatch_push(_email_resolved(), _FakeSchedule(uid), acc, 'success')

    assert seen['email']['emailTo'] == 'mine@x.com, other@y.com'
    assert seen['email']['emailFrom'] == 'sender@b.com'


def test_account_email_recipient_only_falls_back_to_set_credential(app_ctx, monkeypatch):
    """只覆盖收件人、不绑凭证 → 凭证回落到配置套的，收件人仍用账号的"""
    db = sch.db
    uid = _uid(db)
    cid = _email_cred(db, uid)

    seen = _capture_channel(monkeypatch)
    acc = _FakeAccOwnCreds({'email': {'to': 'only@x.com'}})
    sch.dispatch_push(_email_resolved({'email': cid}), _FakeSchedule(uid), acc, 'success')

    assert seen['email']['emailTo'] == 'only@x.com'


def test_account_email_recipient_applies_in_direct_fill(app_ctx, monkeypatch):
    """直接填写模式下账号级收件人同样生效；账号没写就用内联的默认收件人"""
    uid = _uid(sch.db)
    cred = {'emailSmtp': 'smtp.x.com', 'emailFrom': 'a@b.com',
            'emailPass': 'pw', 'emailTo': 'set@x.com'}

    seen = _capture_channel(monkeypatch)
    resolved = _email_resolved(mode='direct', cred=cred)
    sch.dispatch_push(resolved, _FakeSchedule(uid), _FakeAccOwnCreds({'email': {'to': 'acc@x.com'}}), 'success')
    assert seen['email']['emailTo'] == 'acc@x.com'

    seen.clear()
    sch.dispatch_push(resolved, _FakeSchedule(uid), _FakeAccOwnCreds({}), 'success')
    assert seen['email']['emailTo'] == 'set@x.com'


def test_account_email_without_recipient_uses_credential_default(app_ctx, monkeypatch):
    """账号只绑凭证、不写收件人 → 用凭证里的默认收件人（可多个）"""
    db = sch.db
    uid = _uid(db)
    cid = _email_cred(db, uid, to='a@x.com, b@y.com')

    seen = _capture_channel(monkeypatch)
    sch.dispatch_push(_email_resolved(), _FakeSchedule(uid), _FakeAccOwnCreds({'email': cid}), 'success')

    assert seen['email']['emailTo'] == 'a@x.com, b@y.com'

