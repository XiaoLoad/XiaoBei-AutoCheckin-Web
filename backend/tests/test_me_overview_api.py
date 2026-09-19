# 「我的概览」端点测试：展示列表的防御上限不得污染统计口径。
# 两条红线：① 额度占用恒等于账号数，必须精确；② 日志行的账号名不能因上限被截掉。
from app.extensions import db
from app.models import BAccount, Schedule, SignRecord, User
from app.models.user import now_cst
from app.routes import me as me_route
from app.utils.auth import generate_token


def _seed_user(accounts=0, quota=100, with_schedule=False):
    """独立测试用户，挂 N 个平台账号（acc_0 最老；带 schedule 时全部满足展示资格）。"""
    uname = f'tc_mo_{now_cst().strftime("%H%M%S%f")}'
    u = User(username=uname, role='user', enabled=True, quota=quota)
    u.set_password('pw')
    u.last_login = now_cst()
    db.session.add(u)
    db.session.flush()
    accs = []
    for i in range(accounts):
        a = BAccount(user_id=u.id, account=f'mo_acc_{i}', password_enc='x')
        a.set_profile({'name': f'姓名{i}', 'college': '计算机学院', 'className': f'{i}班'})
        db.session.add(a)
        db.session.flush()
        accs.append(a)
        if with_schedule:
            s = Schedule(user_id=u.id, account_id=a.id, task_type='dorm', enabled=True)
            s.set_config({'stub': True})
            db.session.add(s)
    db.session.commit()
    return u, accs, {'Authorization': f'Bearer {generate_token(u)}'}


def _cleanup(u):
    # FK 均为 RESTRICT：sign_records → schedules → b_accounts → users
    SignRecord.query.filter_by(user_id=u.id).delete()
    Schedule.query.filter_by(user_id=u.id).delete()
    BAccount.query.filter_by(user_id=u.id).delete()
    db.session.delete(u)
    db.session.commit()


def test_overview_requires_auth(app):
    c = app.test_client()
    assert c.get('/api/me/overview').status_code in (401, 403)


def test_account_total_exact_beyond_display_limit(app, app_ctx, monkeypatch):
    """账号数超过展示上限时：列表被截到上限，但账号总数与额度占用仍按真实账号数计。"""
    monkeypatch.setattr(me_route, 'ACCOUNT_LIST_LIMIT', 3)
    c = app.test_client()
    u, _, headers = _seed_user(accounts=5, with_schedule=True)
    try:
        data = c.get('/api/me/overview', headers=headers).get_json()['data']
        assert len(data['accounts']['items']) == 3
        assert data['accounts']['total'] == 5
        assert data['quota']['used'] == 5
    finally:
        _cleanup(u)


def test_log_account_name_survives_display_limit(app, app_ctx, monkeypatch):
    """列表按 id 倒序截断后，落在上限之外的老账号仍要能回显在签到日志里。"""
    monkeypatch.setattr(me_route, 'ACCOUNT_LIST_LIMIT', 3)
    c = app.test_client()
    u, accs, headers = _seed_user(accounts=5)
    db.session.add(SignRecord(
        user_id=u.id, account_id=accs[0].id, task_type='dorm',
        sign_date=now_cst().date(), signed_at=now_cst(), status='success',
    ))
    db.session.commit()
    try:
        logs = c.get('/api/me/overview', headers=headers).get_json()['data']['recentLogs']
        assert len(logs) == 1
        assert logs[0]['account'] == 'mo_acc_0'
        assert logs[0]['name'] == '姓名0'
    finally:
        _cleanup(u)
