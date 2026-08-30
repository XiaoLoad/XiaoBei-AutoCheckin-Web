# 管理员仪表盘聚合端点测试：鉴权（普通用户 403）、区块结构、聚合口径与失败归类
from app.extensions import db
from app.models import BAccount, Schedule, SignRecord, User
from app.models.user import now_cst
from app.routes.admin import _classify_fail_reason


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
                'accountHealth', 'scheduler', 'recentLogs'):
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
