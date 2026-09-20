# 推送内容跨渠道同步性：同一次执行在邮件 / ServerChan / PushPlus / QQ 群里看到的原因
# 与「图片分组」必须一致。回归两处实际偏差：
#   ① 已提前签到时邮件能看到跳过原因（「本时段任务已完成签到…」），走 txt/markdown 的
#      ServerChan / QQ 群只有「跳过」两字；群合并推送的表格连原因列都没有；
#   ② 按分组取图（byGroup）下签到取的是分组绑定的图库，推送卡片却报配置套的默认图库
#      （实测签到用 827、推送显示 829）。
# 隔离策略同 test_group_image_binding：新建唯一用户，用后清空该用户全部关联数据。
import json
import uuid
from datetime import date, datetime

import pytest

from app.extensions import db
from app.models import (BAccount, ImageGroup, PushGroup, PushGroupDigestLog,
                        PushGroupMember, PushLog, Schedule, SignRecord, User)
from app.models.pools import PoolCredential
from app.services import group_digest as gd
from app.services import push_render as pr
from app.services import scheduler as sch
from app.services.crypto import encrypt

SKIP_REASON = '本时段任务已完成签到（07.02查寝签到），无需重复签到'
FAIL_REASON = '平台拒绝了本次提交：任务已截止'
EMAIL_FIELDS = {'emailSmtp': 'smtp.x.com', 'emailFrom': 'a@b.com',
                'emailPass': 'pw', 'emailTo': 'to@x.com'}
D = date(2026, 9, 19)


# ───────────────────────── 桩对象（纯渲染用例，不落库） ─────────────────────────

class _StubAcc:
    def __init__(self, name='张三'):
        self.id = None
        self.account = f'stub_{name}'
        self.profile = {'name': name, 'studentNo': '2023001', 'className': '计科2301',
                        'major': '计算机', 'college': '计院'}


class _StubSchedule:
    def __init__(self, uid=0, task_type='dorm'):
        self.id = 0
        self.user_id = uid
        self.task_type = task_type
        self.mode = 'standalone'
        self.config_set_id = None


class _StubRec:
    def __init__(self, status, fail_reason=None, **kw):
        self.status = status
        self.fail_reason = fail_reason
        self.signed_at = kw.get('signed_at', datetime(2026, 9, 19, 8, 3))
        self.task_name = kw.get('task_name', '07.02查寝签到')
        self.task_initiator = kw.get('task_initiator', '王辅导')
        self.need_photo = kw.get('need_photo', True)


def _resolved(image=None, push=None):
    return {
        'time': {'startHour': 8, 'endHour': 22},
        'locationId': None,
        'remarks': ['签到'],
        'image': image or {'enabled': False, 'strategy': 'recycle', 'groupId': None},
        'push': push or {},
    }


# ───────────────────────── 原因行：三个渲染器同一个出口 ─────────────────────────

def test_reason_of_only_labels_fail_and_skip():
    """成功不带原因；跳过/失败必须有原因；原因空白视同没有。"""
    assert pr.reason_of({'status': 'skip', 'reason': SKIP_REASON}) == ('跳过原因', SKIP_REASON)
    assert pr.reason_of({'status': 'fail', 'reason': FAIL_REASON}) == ('失败原因', FAIL_REASON)
    assert pr.reason_of({'status': 'success', 'reason': SKIP_REASON}) is None
    assert pr.reason_of({'status': 'skip', 'reason': '   '}) is None
    assert pr.reason_of({'status': 'skip'}) is None


@pytest.mark.parametrize('fmt', ['html', 'txt', 'markdown'])
@pytest.mark.parametrize('status,reason', [('skip', SKIP_REASON), ('fail', FAIL_REASON)])
def test_every_renderer_shows_reason(fmt, status, reason):
    """回归：render_txt / render_markdown 曾只判 fail，跳过的原因被静默丢掉，
    于是同一次执行邮件里有「跳过原因」、ServerChan 与 QQ 群里只剩「跳过」两字。"""
    ctx = pr.build_ctx(_StubAcc(), _StubSchedule(), _resolved(), status, reason=reason)
    body = pr.render(ctx, fmt)
    assert reason in body
    assert ('跳过原因' if status == 'skip' else '失败原因') in body


@pytest.mark.parametrize('fmt', ['html', 'txt', 'markdown'])
def test_renderer_has_no_reason_block_on_success(fmt):
    """成功不得凭空多出一段原因（空原因也不能渲染出标签）。"""
    ctx = pr.build_ctx(_StubAcc(), _StubSchedule(), _resolved(), 'success', reason='')
    body = pr.render(ctx, fmt)
    assert '失败原因' not in body and '跳过原因' not in body


# ───────────────────────── 通道载荷：原因必须真的发出去 ─────────────────────────

def _capture_posts(monkeypatch):
    calls = []

    def fake_post(url, **kw):
        calls.append((url, kw))
        payload = {'code': 200, 'msg': 'ok'} if 'pushplus' in url else {'code': 0, 'message': ''}
        return type('R', (), {'status_code': 200, 'json': lambda self: payload})()

    monkeypatch.setattr(pr.requests, 'post', fake_post)
    return calls


def test_skip_reason_reaches_every_http_channel(app_ctx, monkeypatch):
    """逐通道核对实际请求体：ServerChan(纯文本) / PushPlus(三模板) / QQ群 都要带上原因。"""
    calls = _capture_posts(monkeypatch)
    ctx = pr.build_ctx(_StubAcc(), _StubSchedule(), _resolved(), 'skip', reason=SKIP_REASON)

    pr.send_channel('serverchan', 'SCT', ctx, template='html')
    assert SKIP_REASON in calls[-1][1]['data']['desp']

    for fmt in ('html', 'markdown', 'txt'):
        pr.send_channel('pushplus', 'PP', ctx, template=fmt)
        assert SKIP_REASON in calls[-1][1]['json']['content'], f'pushplus/{fmt}'

    # QQ 群：html 不支持，按 markdown 发——原因同样要在
    pr.send_channel('qq', {'token': 'T', 'qqCode': 'grp'}, ctx, template='html')
    assert calls[-1][1]['json']['template'] == 'markdown'
    assert SKIP_REASON in calls[-1][1]['json']['content']


@pytest.mark.parametrize('template,subtype', [('html', 'html'), ('markdown', 'plain')])
def test_skip_reason_reaches_email(app_ctx, monkeypatch, template, subtype):
    """邮件按 push.template 分走 HTML / 纯文本两条渲染器，两条都要有原因。"""
    sent = []
    monkeypatch.setattr(pr, 'send_email',
                        lambda fields, subject, body, subtype='plain': sent.append((subtype, body)))
    ctx = pr.build_ctx(_StubAcc(), _StubSchedule(), _resolved(), 'skip', reason=SKIP_REASON)
    ok, err = pr.send_channel('email', EMAIL_FIELDS, ctx, template=template)
    assert ok, err
    assert sent[-1][0] == subtype and SKIP_REASON in sent[-1][1]


# ───────────────────────── 图片分组：报实际取图的那个 ─────────────────────────

@pytest.fixture()
def env(app_ctx):
    """唯一用户 + 账号 + 两个图库：used=分组绑定（真正取图的那个）、default=配置套默认。"""
    uname = f'tc_sync_{uuid.uuid4().hex[:10]}'
    u = User(username=uname, role='user', enabled=True, quota=100, used_quota=0)
    u.set_password('pw')
    db.session.add(u)
    db.session.flush()
    acc = BAccount(user_id=u.id, account=f'acc_{uname}', password_enc='x')
    img_used = ImageGroup(user_id=u.id, name='3栋827')
    img_default = ImageGroup(user_id=u.id, name='3栋829')
    db.session.add_all([acc, img_used, img_default])
    db.session.commit()

    uid = u.id
    yield {'uid': uid, 'acc': acc, 'used': img_used.id, 'default': img_default.id}

    gids = [g.id for g in PushGroup.query.filter_by(user_id=uid).all()]
    if gids:
        PushGroupMember.query.filter(PushGroupMember.group_id.in_(gids)) \
            .delete(synchronize_session=False)
        PushGroupDigestLog.query.filter(PushGroupDigestLog.group_id.in_(gids)) \
            .delete(synchronize_session=False)
    # 删序即外键依赖序：push_logs 指向账号/排程/记录，必须最先清
    for model in (PushLog, PushGroup, SignRecord, Schedule, ImageGroup, BAccount,
                  PoolCredential):
        model.query.filter_by(user_id=uid).delete(synchronize_session=False)
    db.session.delete(db.session.get(User, uid))
    db.session.commit()


def _dorm_group(uid, name, accounts=(), image_group_id=None, qq_code=None):
    g = PushGroup(user_id=uid, type=PushGroup.TYPE_DORM, name=name,
                  qq_code=qq_code, image_group_id=image_group_id)
    db.session.add(g)
    db.session.flush()
    for a in accounts:
        db.session.add(PushGroupMember(group_id=g.id, account_id=a.id))
    db.session.commit()
    return g


def _cred(uid, channel, fields):
    c = PoolCredential(user_id=uid, channel=channel, name='t',
                       secret_enc=encrypt(json.dumps(fields)), enabled=True)
    db.session.add(c)
    db.session.commit()
    return c.id


def _by_group_cfg(default_gid):
    return {'enabled': True, 'strategy': 'recycle', 'mode': 'byGroup',
            'groupKind': 'dorm', 'groupId': default_gid}


def test_build_ctx_prefers_effective_group_over_config_default(env):
    """显式传入实际命中的图库时以它为准；未传（无账号语境的凭证测试预览）才退回配置值。"""
    cfg = _resolved(image=_by_group_cfg(env['default']))
    sched = _StubSchedule(env['uid'])
    assert pr.build_ctx(env['acc'], sched, cfg, 'success',
                        image_group_id=env['used'])['image_group_name'] == '3栋827'
    assert pr.build_ctx(env['acc'], sched, cfg, 'success')['image_group_name'] == '3栋829'


def test_dispatch_push_reports_group_actually_used_for_images(env, monkeypatch):
    """回归 BUG：按分组取图时签到用 827 的图，推送卡片必须也是 827 而不是配置套默认的 829。"""
    _dorm_group(env['uid'], '507', accounts=[env['acc']],
                image_group_id=env['used'], qq_code='grp-507')
    cid = _cred(env['uid'], 'serverchan', {'serverchanKey': 'SCT'})
    sched = Schedule(user_id=env['uid'], account_id=env['acc'].id, task_type='dorm',
                     mode='standalone', enabled=True)
    db.session.add(sched)
    db.session.commit()

    seen = {}

    def fake_send_channel(channel, key, ctx, template):
        seen['ctx'] = ctx
        return True, ''

    monkeypatch.setattr(sch, 'send_channel', fake_send_channel)
    resolved = _resolved(image=_by_group_cfg(env['default']), push={
        'channels': ['serverchan'], 'useOwnCredential': True,
        'credIds': {'serverchan': cid, 'pushplus': None, 'email': None},
        'cred': {}, 'notify': {'success': True, 'skip': True, 'fail': True},
    })
    sch.dispatch_push(resolved, sched, env['acc'], 'success')

    assert seen['ctx']['image_group_name'] == '3栋827'
    body = pr.render(seen['ctx'], 'html')
    assert '3栋827' in body and '3栋829' not in body


def test_dispatch_push_honors_group_id_from_checkin_attempt(env, monkeypatch):
    """签到认领时记下的图库（extra）优先于现场重解析：早退路径无该记录才落回解析。"""
    cid = _cred(env['uid'], 'serverchan', {'serverchanKey': 'SCT'})
    sched = Schedule(user_id=env['uid'], account_id=env['acc'].id, task_type='dorm',
                     mode='standalone', enabled=True)
    db.session.add(sched)
    db.session.commit()

    seen = {}

    def fake_send_channel(channel, key, ctx, template):
        seen['ctx'] = ctx
        return True, ''

    monkeypatch.setattr(sch, 'send_channel', fake_send_channel)
    resolved = _resolved(image=_by_group_cfg(env['default']), push={
        'channels': ['serverchan'], 'useOwnCredential': True,
        'credIds': {'serverchan': cid, 'pushplus': None, 'email': None},
        'cred': {}, 'notify': {'success': True, 'skip': True, 'fail': True},
    })
    sch.dispatch_push(resolved, sched, env['acc'], 'success',
                      extra={'image_group_id': env['used']})
    assert seen['ctx']['image_group_name'] == '3栋827'


# ───────────────────────── 群合并推送：补上原因说明 ─────────────────────────

def test_render_digest_lists_reasons_of_skips_and_failures(app_ctx):
    """只给「跳过」两个字，收件人分不清「已完成签到无需重复」与「漏签」——
    表格后须附说明段列出原因（与个人推送同一字段 fail_reason）。"""
    g = PushGroup(user_id=1, type=PushGroup.TYPE_DORM, name='507')
    rows = [
        (_StubAcc('张三'), _StubRec('skip', SKIP_REASON)),
        (_StubAcc('李四'), _StubRec('success')),
        (_StubAcc('王五'), _StubRec('fail', FAIL_REASON)),
        (_StubAcc('赵六'), None),
    ]
    title, content = gd._render_digest(g, D, rows)
    assert '507' in title
    assert '**说明**' in content
    assert SKIP_REASON in content and FAIL_REASON in content
    assert content.count('\n- ') == 2  # 成功与未签到不得混进说明段
    assert '> 共 4 人，已签 **1** 人' in content


def test_render_digest_omits_notes_when_no_reason(app_ctx):
    """全组无原因（如全成功、跳过但平台未给原因）时不出现空说明段。"""
    g = PushGroup(user_id=1, type=PushGroup.TYPE_DORM, name='507')
    rows = [(_StubAcc('张三'), _StubRec('success')), (_StubAcc('李四'), _StubRec('skip'))]
    _title, content = gd._render_digest(g, D, rows)
    assert '说明' not in content


def test_flush_digest_sends_skip_reason_to_group(env, monkeypatch):
    """端到端：已提前签到的成员，群合并推送里要能看到与邮件同一句原因，而不是只有「跳过」。"""
    acc2 = BAccount(user_id=env['uid'], account=f'a2_{uuid.uuid4().hex[:6]}', password_enc='x')
    acc2.set_profile({'name': '李四', 'studentNo': '2023002', 'className': '计科2301'})
    db.session.add(acc2)
    db.session.commit()

    group = _dorm_group(env['uid'], '507', accounts=[env['acc'], acc2], qq_code='grp-507')
    _cred(env['uid'], 'pushplus-open', {'token': 'OPEN-TOKEN'})

    env['acc'].set_profile({'name': '张三', 'studentNo': '2023001', 'className': '计科2301'})
    db.session.add_all([
        SignRecord(user_id=env['uid'], account_id=env['acc'].id, task_type='dorm',
                   sign_date=D, status='skip', fail_reason=SKIP_REASON,
                   task_name='07.02查寝签到', task_initiator='王辅导', need_photo=True,
                   signed_at=datetime(2026, 9, 19, 8, 3)),
        SignRecord(user_id=env['uid'], account_id=acc2.id, task_type='dorm',
                   sign_date=D, status='success', task_name='07.02查寝签到',
                   task_initiator='王辅导', need_photo=True,
                   signed_at=datetime(2026, 9, 19, 8, 5)),
    ])
    db.session.commit()

    sent = {}

    def fake_send_qq(token, qq_code, title, content, template='markdown'):
        sent.update(token=token, qq_code=qq_code, title=title, content=content,
                    template=template)
        return True, ''

    monkeypatch.setattr(gd, 'send_qq', fake_send_qq)
    gd.flush_digest(group.id, D, force=True)

    assert sent['qq_code'] == 'grp-507' and sent['template'] == 'markdown'
    assert SKIP_REASON in sent['content']          # 关键：群推送也带上了原因
    assert '张三' in sent['content'] and '李四' in sent['content']
    assert '王辅导' in sent['content']             # 任务发起人逐人回显
    log = PushGroupDigestLog.query.filter_by(group_id=group.id, date=D).first()
    assert log is not None and log.status == PushGroupDigestLog.STATUS_PARTIAL
    assert (log.member_done, log.member_total) == (1, 2)
