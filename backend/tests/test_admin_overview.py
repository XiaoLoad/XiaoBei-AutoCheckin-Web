# 管理员仪表盘聚合端点测试：鉴权（普通用户 403）、区块结构、聚合口径与失败归类
import pytest

from app.extensions import db
from app.models import BAccount, PushLog, Schedule, SignRecord, User
from app.models.user import now_cst
from app.routes.admin import _classify_fail_reason, _classify_push_reason, clear_agg_cache


@pytest.fixture(autouse=True)
def _fresh_agg_cache():
    """聚合结果有 60s TTL 内存缓存，用例之间必须失效——否则先跑的用例把待断言的数据
    提前缓存掉，后跑的用例读到上一个用例的投影，断言会随执行顺序时红时绿。"""
    clear_agg_cache()
    yield
    clear_agg_cache()


def _seed_today_records(uid, acc_id, success=2, fail=1, skip=1):
    rows = []
    for i in range(success):
        rows.append(SignRecord(user_id=uid, account_id=acc_id, sign_date=now_cst().date(),
                               status='success', task_type='dorm'))
    for i in range(fail):
        rows.append(SignRecord(user_id=uid, account_id=acc_id, sign_date=now_cst().date(),
                               status='fail', task_type='dorm', fail_reason='B 平台拒绝：不在签到时间内'))
    for i in range(skip):
        rows.append(SignRecord(user_id=uid, account_id=acc_id, sign_date=now_cst().date(),
                               status='skip', task_type='dorm'))
    db.session.add_all(rows)
    db.session.commit()


def test_overview_requires_admin(app, user_headers, admin_headers):
    c = app.test_client()
    assert c.get('/api/admin/overview', headers=user_headers).status_code == 403
    res = c.get('/api/admin/overview', headers=admin_headers)
    assert res.status_code == 200
    data = res.get_json()['data']
    for key in ('summary', 'trend', 'failCategories', 'quota', 'riskUsers',
                'accountHealth', 'pushHealth', 'scheduler', 'recentLogs'):
        assert key in data, key
    assert data['summary']['quota']['total'] >= 0


def test_overview_today_stats_and_quota_derivation(app, admin_headers):
    c = app.test_client()
    # 独立用户：1 账号（quota 100 → 使用率 1%）；今日 成功2/失败1/跳过1
    uname = f'tc_ov_{now_cst().strftime("%H%M%S%f")}'
    u = User(username=uname, role='user', enabled=True, quota=100)
    u.set_password('pw')
    db.session.add(u)
    db.session.flush()
    acc = BAccount(user_id=u.id, account='ov_acc', password_enc='x')
    db.session.add(acc)
    db.session.flush()
    _seed_today_records(u.id, acc.id)

    data = c.get('/api/admin/overview', headers=admin_headers).get_json()['data']
    today = data['summary']['today']
    assert today['success'] >= 2 and today['fail'] >= 1 and today['skip'] >= 1
    # 额度使用率 = 账号数现算：该用户 1 账号
    assert data['quota']['warnTotal'] >= 0
    buckets = data['quota']['buckets']
    assert buckets['lt50'] >= 1  # 1/100 → <50% 桶

    # 清理
    SignRecord.query.filter_by(user_id=u.id).delete()
    Schedule.query.filter_by(user_id=u.id).delete()
    BAccount.query.filter_by(user_id=u.id).delete()
    db.session.delete(u)
    db.session.commit()


def test_fail_reason_classification():
    f = _classify_fail_reason
    assert f('围栏拦截：配置位置距签到点 823 米') == '围栏拦截'
    assert f('触发平台行为验证码（msg=302）') == '行为验证码'
    assert f('B 平台拒绝：不在签到时间内') == 'B 平台拒绝'
    assert f('B 平台错误：登录态失效：token失效') == '登录态失效'
    assert f('该任务需要上传签到图片，请...') == '缺少签到图片'
    assert f('执行异常：boom') == '执行异常'
    assert f('某种未知的新错误') == '其他'
    assert f('') == '其他'


def test_push_reason_classification():
    f = _classify_push_reason
    # 跳过类：剥「已跳过：」前缀后只查跳过表，不会被当成通道故障
    assert f('已跳过：该账号未绑定此通道的推送凭证') == '未绑定凭证'
    assert f('已跳过：未绑定凭证') == '未绑定凭证'
    assert f('已跳过：凭证缺少必要字段') == '凭证缺少字段'
    assert f('已跳过：内联凭证缺少 SMTP 地址/发件人/收件人字段') == '凭证缺少字段'
    # 发送失败类
    assert f('ServerChan 推送被拒（code=400，message=bad）') == '平台拒绝'
    assert f('PushPlus 推送被拒（code=400）（已重试，共尝试 3 次）') == '平台拒绝'
    assert f('PushPlus 响应非 JSON（HTTP 502）') == '响应异常'
    assert f('收件人为空') == '响应异常'
    assert f('HTTPSConnectionPool(host=x): Read timed out.') == '连接超时'
    assert f('内部异常：boom') == '内部异常'
    assert f('某种没见过的失败') == '其他'
    assert f('') == '其他'


def _channel_row(by_channel, channel):
    """通道行缺失时（干净库 before 无任何推送）返回零值行，口径与后端一致：
    sent/ok/fail/skipped 为 0、rate 为 None（无数据而非 0%）。"""
    for row in by_channel:
        if row['channel'] == channel:
            return row
    return {'channel': channel, 'sent': 0, 'ok': 0, 'fail': 0, 'skipped': 0, 'rate': None}


def _cnt(items, name):
    for it in items:
        if it['category'] == name:
            return it['count']
    return 0


def test_push_health_splits_skips_from_success_rate(app, admin_headers):
    """核心口径：跳过（attempts=0）不计入成功率分母、单独计数并单独归类；
    「签到成功但通知未送达」要被抓出来，并区分「真失败」与「压根没发出去」。"""
    c = app.test_client()
    # 全站聚合，历史数据不可预设 → 用调用前后的增量断言，不写死绝对值
    before = c.get('/api/admin/overview', headers=admin_headers).get_json()['data']['pushHealth']

    uname = f'tc_push_{now_cst().strftime("%H%M%S%f")}'
    u = User(username=uname, role='user', enabled=True, quota=100)
    u.set_password('pw')
    db.session.add(u)
    db.session.flush()
    acc = BAccount(user_id=u.id, account='push_acc', password_enc='x')
    db.session.add(acc)
    db.session.flush()
    rec = SignRecord(user_id=u.id, account_id=acc.id, sign_date=now_cst().date(),
                     status='success', task_type='dorm')
    db.session.add(rec)
    db.session.flush()
    db.session.add_all([
        PushLog(user_id=u.id, account_id=acc.id, sign_record_id=rec.id,
                channel='serverchan', ok=True, attempts=1),
        PushLog(user_id=u.id, account_id=acc.id, sign_record_id=rec.id,
                channel='pushplus', ok=False, attempts=3,
                error='PushPlus 推送被拒（code=400，message=bad）'),
        PushLog(user_id=u.id, account_id=acc.id, sign_record_id=rec.id,
                channel='email', ok=False, attempts=0,
                error='已跳过：该账号未绑定此通道的推送凭证'),
    ])
    db.session.commit()
    clear_agg_cache()  # 基线那次请求已把当时的投影写进缓存

    after = c.get('/api/admin/overview', headers=admin_headers).get_json()['data']['pushHealth']
    # rate 在无真实发送时语义为 None（「无数据」，与 by_channel 行口径一致），不做增量；
    # 干净库基线（sent=0）下本用例新增 2 发 1 成，rate 应恰为 50
    delta = {k: after['summary'][k] - before['summary'][k]
             for k in before['summary'] if before['summary'][k] is not None}
    if before['summary']['rate'] is None:
        assert after['summary']['rate'] == 50
    assert delta['sent'] == 2      # 3 行里只有 2 行真发出去了
    assert delta['ok'] == 1
    assert delta['fail'] == 1      # 跳过不算失败
    assert delta['skipped'] == 1

    plus_b, plus_a = _channel_row(before['byChannel'], 'pushplus'), _channel_row(after['byChannel'], 'pushplus')
    assert plus_a['sent'] - plus_b['sent'] == 1 and plus_a['fail'] - plus_b['fail'] == 1
    mail_b, mail_a = _channel_row(before['byChannel'], 'email'), _channel_row(after['byChannel'], 'email')
    assert mail_a['skipped'] - mail_b['skipped'] == 1
    assert mail_a['sent'] == mail_b['sent']          # 跳过不抬高发送数、也不压低成功率

    assert _cnt(after['failReasons'], '平台拒绝') - _cnt(before['failReasons'], '平台拒绝') == 1
    assert _cnt(after['skipReasons'], '未绑定凭证') - _cnt(before['skipReasons'], '未绑定凭证') == 1
    assert '未绑定凭证' not in [it['category'] for it in after['failReasons']]

    assert after['signOkPushFail']['total'] - before['signOkPushFail']['total'] == 2
    mine = [x for x in after['signOkPushFail']['list'] if x['username'] == uname]
    assert len(mine) == 2, '新造的两条未送达应进入前 8 条'
    assert mine[0]['channel'] == 'pushplus' and mine[0]['skipped'] is False
    assert mine[1]['channel'] == 'email' and mine[1]['skipped'] is True

    PushLog.query.filter_by(user_id=u.id).delete()
    SignRecord.query.filter_by(user_id=u.id).delete()
    BAccount.query.filter_by(user_id=u.id).delete()
    db.session.delete(u)
    db.session.commit()
