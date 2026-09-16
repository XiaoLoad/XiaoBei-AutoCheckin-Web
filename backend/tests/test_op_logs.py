# 用户日志（操作审计）回归：
# - 事件订阅链路真的把人做的事写进了 op_logs（登录成功/失败、用户增删改状态）
# - 变更明细能还原 from→to（改角色这类审计重点，拿不到原值就失去意义）
# - 读取接口仅管理员可用
# - 普通用户请求日志列表必须 403（含全员用户名/IP/UA，属敏感信息）
import pytest

from app.extensions import db
from app.models.op_log import OpAnomalyAck, OpLog
from app.models.user import User

# 本文件创建的测试用户；审计行需按前缀清（见 audit_cleanup）
_TEST_USERS = ('tc_audit_target', 'tc_audit_pwd')
# 合成失败登录的来源 IP：RFC 5737 文档示例网段，不会与真实来源或测试客户端的 127.0.0.1 撞车
# （撞车会让本文件的用例互相踩：某个用例确认了 127.0.0.1，别的用例就再也看不到告警）
_ACK_IP = '203.0.113.9'


def _ensure_user(username, password='pw-123456', role='user'):
    u = User.query.filter_by(username=username).first()
    if not u:
        u = User(username=username, role=role, enabled=True, quota=10, used_quota=0)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
    return u


def _fail_logins(ip, n, account='tc_audit_target'):
    """直接落库造失败登录行。真实登录请求的来源都是 127.0.0.1，
    造不出「指定 IP 反复失败」，而异常聚合恰恰只按 IP 看。"""
    for _ in range(n):
        row = OpLog(action='auth.login', category='auth', result='fail',
                    username='system', role='', ip=ip,
                    summary=f'登录失败「{account}」：密码错误')
        row.set_detail({'account': account, 'reason': '密码错误'})
        db.session.add(row)
    db.session.commit()


@pytest.fixture()
def audit_cleanup(app_ctx):
    """收尾：op_logs 不参与 tests/conftest 的懒创建清理，且删除 users 前必须先删引用它的
    日志行（FK→users.id）。登录失败行 user_id 为 NULL、操作者列记 'system'，
    被尝试的账号只在 summary 里，故两处都要按前缀匹配（含历史运行残留）。
    确认记录同理按确认人前缀清——留着会让后续用例的告警一直处于「已处理」状态。"""
    from sqlalchemy import or_

    def _purge():
        db.session.rollback()
        ids = [u.id for u in User.query.filter(User.username.in_(_TEST_USERS)).all()]
        conds = [OpLog.username.like('tc_%'), OpLog.username.like('smoke_%'),
                 OpLog.ip == _ACK_IP]
        for name in _TEST_USERS:
            conds.append(OpLog.summary.like(f'%{name}%'))
        if ids:
            conds.append(OpLog.user_id.in_(ids))
        OpLog.query.filter(or_(*conds)).delete(synchronize_session=False)
        OpAnomalyAck.query.filter(or_(OpAnomalyAck.username.like('tc_%'),
                                      OpAnomalyAck.username.like('smoke_%'))
                                ).delete(synchronize_session=False)
        if ids:
            User.query.filter(User.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()

    _purge()
    yield
    _purge()


def _latest(action):
    return (OpLog.query.filter_by(action=action).order_by(OpLog.id.desc()).first())


def test_op_logs_requires_admin(app_ctx, user_headers, admin_headers):
    client = app_ctx.test_client()
    # 三个读取口径都必须限管理员：会话与指标同样暴露全员用户名/IP
    for path in ('/api/op-logs', '/api/op-logs/sessions', '/api/op-logs/summary',
                 '/api/op-logs/meta'):
        assert client.get(path, headers=user_headers).status_code == 403, path
    res = client.get('/api/op-logs', headers=admin_headers)
    assert res.status_code == 200
    assert res.get_json()['code'] == 0
    assert isinstance(res.get_json()['data']['items'], list)


def test_op_log_item_shape_matches_frontend_contract(app_ctx, admin_headers, audit_cleanup):
    """序列化键名是前后端契约，前端 mapLog 按 camelCase 取值，
    漏字段不会报错、只会静默显示空白，故在此钉死键集合。"""
    _ensure_user('tc_audit_target')
    client = app_ctx.test_client()
    client.post('/api/auth/login', json={'account': 'tc_audit_target', 'password': 'x'})

    data = client.get('/api/op-logs?page_size=1', headers=admin_headers).get_json()['data']
    assert {'items', 'total', 'page', 'page_size'} <= set(data)
    item = data['items'][0]
    assert {'id', 'userId', 'username', 'role', 'action', 'category', 'result',
            'summary', 'detail', 'ip', 'userAgent', 'createdAt'} <= set(item)
    assert item['createdAt'].count(':') == 2  # 'YYYY-MM-DD HH:MM:SS'，前端按 [11:19] 取时间


def test_summary_shape_matches_frontend_contract(app_ctx, admin_headers, audit_cleanup):
    """页头指标 + 异常块 + 保留天数：同一套键名契约，漏了页面只会显示空白。"""
    client = app_ctx.test_client()
    data = client.get('/api/op-logs/summary', headers=admin_headers).get_json()['data']
    assert {'metrics', 'anomalies', 'ackedQuiet', 'retentionDays'} <= set(data)
    assert {'loginToday', 'loginFailToday', 'userChangeToday', 'ongoingSessions'} \
        <= set(data['metrics'])
    assert isinstance(data['anomalies'], list)
    assert isinstance(data['ackedQuiet'], list)
    assert data['retentionDays'] >= 1


def test_anomaly_aggregates_failed_logins_by_ip(app_ctx, admin_headers, audit_cleanup):
    """同一 IP 连续登录失败要聚成一条「未能建立会话」，否则这批记录在会话视图里完全隐形
    （登录失败行没有 user_id，进不了任何会话段）。"""
    client = app_ctx.test_client()
    for acc in ('tc_audit_target', 'root', 'admin'):
        client.post('/api/auth/login', json={'account': acc, 'password': 'wrong'})

    data = client.get('/api/op-logs/summary', headers=admin_headers).get_json()['data']
    hits = [a for a in data['anomalies'] if a['count'] >= 3]
    assert hits, '三连失败未触发异常聚合'
    assert hits[0]['ip']  # 无 IP 归不到一起，聚合就失去意义
    assert 'tc_audit_target' in hits[0]['accounts']


def test_anomaly_ack_silences_until_new_failures(app_ctx, admin_headers, audit_cleanup):
    """确认告警后不再提示，但该 IP 一旦出现新增失败就要重新冒出来——
    否则一次确认就能把一个还在被撞的 IP 永久藏起来，这条告警不如不做。"""
    client = app_ctx.test_client()

    def summary():
        return client.get('/api/op-logs/summary', headers=admin_headers).get_json()['data']

    def find(hay, ip):
        return [a for a in hay if a['ip'] == ip]

    _fail_logins(_ACK_IP, 3)
    data = summary()
    assert find(data['anomalies'], _ACK_IP)[0]['count'] == 3
    assert find(data['ackedQuiet'], _ACK_IP) == []

    res = client.post('/api/op-logs/anomalies/ack', headers=admin_headers,
                      json={'ips': [_ACK_IP]})
    assert res.get_json()['code'] == 0

    # 确认后从告警里消失，但要以「已处理」的身份继续可见（关掉 ≠ 删掉）
    data = summary()
    assert find(data['anomalies'], _ACK_IP) == []
    quiet = find(data['ackedQuiet'], _ACK_IP)
    assert quiet and quiet[0]['countAtAck'] == 3 and quiet[0]['count'] == 3
    assert quiet[0]['username'] == 'tc_admin'   # 谁处理的要留痕
    assert quiet[0]['ackedAt']

    # 再失败一次：次数越过确认时的 3 → 重新出现在告警里
    _fail_logins(_ACK_IP, 1)
    data = summary()
    assert find(data['anomalies'], _ACK_IP)[0]['count'] == 4
    assert find(data['ackedQuiet'], _ACK_IP) == []

    # 再次确认则覆盖同一条记录（同账号同 IP 只留最新一次），不是追加
    client.post('/api/op-logs/anomalies/ack', headers=admin_headers, json={'ips': [_ACK_IP]})
    assert OpAnomalyAck.query.filter(OpAnomalyAck.ip == _ACK_IP).count() == 1
    assert find(summary()['ackedQuiet'], _ACK_IP)[0]['countAtAck'] == 4


def test_anomaly_ack_requires_admin_and_valid_payload(app_ctx, user_headers, admin_headers,
                                                      audit_cleanup):
    """确认记录带操作者身份，必须是管理员；载荷要能挡住脏值，别把 500 丢给前端。"""
    client = app_ctx.test_client()
    assert client.post('/api/op-logs/anomalies/ack', headers=user_headers,
                       json={'ips': [_ACK_IP]}).status_code == 403

    for bad in ('nope', [], ['', '  '], None):
        res = client.post('/api/op-logs/anomalies/ack', headers=admin_headers,
                          json={'ips': bad})
        assert res.status_code == 400, bad
        assert res.get_json()['code'] != 0
    # 凭空确认一个从未出现过的 IP 不该报错（服务端按库里的真实次数记 0），
    # 但它也不会因此出现在任何列表里
    assert client.post('/api/op-logs/anomalies/ack', headers=admin_headers,
                       json={'ips': [_ACK_IP]}).get_json()['code'] == 0
    data = client.get('/api/op-logs/summary', headers=admin_headers).get_json()['data']
    assert [a for a in data['anomalies'] if a['ip'] == _ACK_IP] == []


def test_sessions_group_login_to_logout(app_ctx, admin_headers, audit_cleanup):
    """会话段 = 成功登录 → 登出之间的全部操作；这是「会话」视图的唯一数据来源。"""
    _ensure_user('tc_audit_target')
    client = app_ctx.test_client()
    token = client.post('/api/auth/login', json={
        'account': 'tc_audit_target', 'password': 'pw-123456'}).get_json()['data']['token']
    headers = {'Authorization': f'Bearer {token}'}
    client.put('/api/auth/password', headers=headers,
               json={'old_password': 'pw-123456', 'new_password': 'pw-abcdef'})
    client.post('/api/auth/logout', headers=headers)

    data = client.get('/api/op-logs/sessions?keyword=tc_audit_target',
                      headers=admin_headers).get_json()['data']
    assert data['total'] >= 1
    session = data['items'][0]
    assert {'id', 'userId', 'username', 'role', 'ip', 'startAt', 'endAt', 'startTime',
            'durationSeconds', 'running', 'closeReason', 'eventCount', 'events'} <= set(session)
    assert session['closeReason'] == 'logout'
    assert session['running'] is False
    actions = [e['action'] for e in session['events']]
    # 登录、改密都在同一段里，且顺序为时间升序
    assert actions[0] == 'auth.login'
    assert 'auth.password' in actions
    assert actions[-1] == 'auth.logout'
    assert session['eventCount'] == len(session['events'])
    # 段内事件也要给前端的 camelCase 契约
    assert {'id', 'time', 'createdAt', 'action', 'category', 'result',
            'summary', 'detail', 'ip'} <= set(session['events'][0])


def test_login_success_and_failure_both_logged(app_ctx, audit_cleanup):
    u = _ensure_user('tc_audit_target')
    client = app_ctx.test_client()

    assert client.post('/api/auth/login', json={
        'account': 'tc_audit_target', 'password': 'pw-123456'}).get_json()['code'] == 0
    ok = (OpLog.query.filter_by(action='auth.login', result='success', user_id=u.id)
          .order_by(OpLog.id.desc()).first())
    assert ok is not None
    assert ok.username == 'tc_audit_target'

    # 密码错误：无归属用户，但必须留痕（连续失败是排查暴力破解的唯一线索）
    assert client.post('/api/auth/login', json={
        'account': 'tc_audit_target', 'password': 'wrong-pw'}).get_json()['code'] == 1002
    bad = (OpLog.query.filter_by(action='auth.login', result='fail')
           .order_by(OpLog.id.desc()).first())
    assert bad is not None
    assert bad.user_id is None
    assert 'tc_audit_target' in bad.summary and '密码错误' in bad.summary


def test_logout_and_password_change_logged(app_ctx, audit_cleanup):
    _ensure_user('tc_audit_pwd')
    client = app_ctx.test_client()
    res = client.post('/api/auth/login', json={
        'account': 'tc_audit_pwd', 'password': 'pw-123456'}).get_json()
    headers = {'Authorization': f"Bearer {res['data']['token']}"}

    assert client.put('/api/auth/password', headers=headers, json={
        'old_password': 'pw-123456', 'new_password': 'pw-654321'}).get_json()['code'] == 0
    assert _latest('auth.password') is not None

    assert client.post('/api/auth/logout', headers=headers).get_json()['code'] == 0
    assert _latest('auth.logout') is not None


def test_user_change_events_logged_with_diff(app_ctx, admin_headers, audit_cleanup):
    client = app_ctx.test_client()

    res = client.post('/api/users', headers=admin_headers, json={
        'username': 'tc_audit_target', 'password': 'pw-123456', 'role': 'user', 'quota': 10})
    assert res.status_code == 201
    uid = res.get_json()['data']['user_id']
    created = _latest('user.create')
    assert created is not None and created.username == 'tc_admin'  # 记的是操作者
    assert (created.get_detail() or {}).get('targetUserId') == uid
    assert 'tc_audit_target' in created.summary

    # 改角色：明细必须还原 from→to（拿不到原值的审计等于没记）
    assert client.put(f'/api/users/{uid}', headers=admin_headers,
                      json={'role': 'admin'}).status_code == 200
    updated = _latest('user.update')
    assert updated is not None
    changes = (updated.get_detail() or {}).get('changes') or []
    role_change = [c for c in changes if c['field'] == 'role']
    assert role_change and role_change[0]['from'] == 'user' and role_change[0]['to'] == 'admin'

    # 状态变更走独立动作，便于筛选「谁被停用了」
    assert client.patch(f'/api/users/{uid}/status', headers=admin_headers,
                        json={'enabled': False}).status_code == 200
    assert _latest('user.disable') is not None


def test_op_logs_filter_and_paging(app_ctx, admin_headers, audit_cleanup):
    client = app_ctx.test_client()
    client.post('/api/auth/login', json={'account': 'tc_audit_target', 'password': 'x'})

    res = client.get('/api/op-logs?category=auth&result=fail&page=1&page_size=5',
                     headers=admin_headers)
    data = res.get_json()['data']
    assert data['page_size'] == 5
    assert all(i['category'] == 'auth' and i['result'] == 'fail' for i in data['items'])
    assert data['total'] >= 1

    # keyword 单框兼顾三处：用户名 / IP / 摘要。登录失败行没有归属用户，
    # 被尝试的账号只在摘要里，这是唯一能反查「谁试过登录这个账号」的入口
    res = client.get('/api/op-logs?keyword=tc_audit_target&result=fail', headers=admin_headers)
    hits = res.get_json()['data']['items']
    assert hits and all('tc_audit_target' in i['summary'] for i in hits)

    meta = client.get('/api/op-logs/meta', headers=admin_headers).get_json()['data']
    assert {'categories', 'actions'} <= set(meta)
    assert any(a['value'] == 'auth.login' for a in meta['actions'])
