# 登录防爆破回归（审计 S3）：
# - 账号×IP 连续失败达阈值 → 正确密码也被 429 拒绝，锁到期自动恢复
# - 登录成功清零该账号全部失败计数
# - 「账号不存在」与「密码错误」对外完全一致（防用户名枚举），原因只进审计
# - 禁用账号仅对持正确密码者可见（403），无密码者只看到统一凭据错误
# - IP 全局维度：跨用户名喷洒达阈值 → 该 IP 整体被锁
import pytest

from app.extensions import db
from app.models.login_failure import LoginFailure
from app.models.user import User

# 与 login_guard._RULES 的账号×IP 阈值保持一致（超阈值即锁）
_ACCOUNT_IP_THRESHOLD = 10


def _ensure_user(username, password='pw-123456', role='user', enabled=True):
    u = User.query.filter_by(username=username).first()
    if not u:
        u = User(username=username, role=role, enabled=enabled, quota=10, used_quota=0)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
    else:
        u.enabled = enabled
        db.session.commit()
    return u


def _clear_failures():
    """每个用例独立起表：失败计数是持久化的，不清会让用例互相踩（阈值累积）。"""
    LoginFailure.query.delete(synchronize_session=False)
    db.session.commit()


@pytest.fixture()
def lockout_cleanup(app_ctx):
    _clear_failures()
    yield
    _clear_failures()


def _login(client, account, password):
    return client.post('/api/auth/login', json={'account': account, 'password': password})


def test_lockout_blocks_correct_password_after_threshold(app_ctx, lockout_cleanup):
    _ensure_user('tc_lock_user')
    client = app_ctx.test_client()

    for _ in range(_ACCOUNT_IP_THRESHOLD):
        res = _login(client, 'tc_lock_user', 'wrong-pw')
        assert res.status_code == 401  # 未达阈值前是统一凭据错误

    # 达阈值：正确密码也被拒，且是 429 而非凭据错误
    res = _login(client, 'tc_lock_user', 'pw-123456')
    assert res.status_code == 429 and res.get_json()['code'] == 1004


def test_lock_expires_and_allows_login_again(app_ctx, lockout_cleanup):
    _ensure_user('tc_lock_user')
    client = app_ctx.test_client()
    for _ in range(_ACCOUNT_IP_THRESHOLD):
        _login(client, 'tc_lock_user', 'wrong-pw')
    assert _login(client, 'tc_lock_user', 'pw-123456').status_code == 429

    # 模拟锁定到期（锁定时长 15 分钟）
    for row in LoginFailure.query.all():
        if row.locked_until:
            from datetime import datetime, timedelta
            row.locked_until = datetime.utcnow() - timedelta(minutes=1)
    db.session.commit()

    res = _login(client, 'tc_lock_user', 'pw-123456')
    assert res.status_code == 200 and res.get_json()['code'] == 0


def test_success_clears_failure_count(app_ctx, lockout_cleanup):
    _ensure_user('tc_lock_user')
    client = app_ctx.test_client()

    for _ in range(_ACCOUNT_IP_THRESHOLD - 1):
        _login(client, 'tc_lock_user', 'wrong-pw')
    res = _login(client, 'tc_lock_user', 'pw-123456')
    assert res.status_code == 200

    # 成功后计数清零：再来 4 次失败不会被历史次数顶到阈值
    for _ in range(_ACCOUNT_IP_THRESHOLD - 1):
        assert _login(client, 'tc_lock_user', 'wrong-pw').status_code == 401
    assert _login(client, 'tc_lock_user', 'pw-123456').status_code == 200


def test_nonexistent_and_wrong_password_responses_identical(app_ctx, lockout_cleanup):
    """防枚举核心断言：两个分支的状态码/错误码/文案必须逐字段一致。"""
    _ensure_user('tc_lock_user')
    client = app_ctx.test_client()

    gone = _login(client, 'tc_no_such_user_xyz', 'whatever').get_json()
    badpw = _login(client, 'tc_lock_user', 'wrong-pw').get_json()
    assert gone['code'] == badpw['code']
    assert gone['message'] == badpw['message']
    assert _login(client, 'tc_no_such_user_xyz', 'whatever').status_code == \
        _login(client, 'tc_lock_user', 'wrong-pw').status_code


def test_disabled_account_hidden_behind_correct_password(app_ctx, lockout_cleanup):
    """禁用信息只对持正确密码者可见；无密码者仍得统一凭据错误（不能借禁用接口探测账号存在性）。"""
    _ensure_user('tc_lock_disabled', enabled=False)
    client = app_ctx.test_client()

    res = _login(client, 'tc_lock_disabled', 'pw-123456')
    assert res.status_code == 403 and res.get_json()['code'] == 1003
    res = _login(client, 'tc_lock_disabled', 'wrong-pw')
    assert res.status_code == 401 and res.get_json()['message'] == '账号或密码错误'


def test_ip_global_lock_blocks_spray_across_usernames(app_ctx, lockout_cleanup):
    """IP 全局维度：同一 IP 对大量不存在的用户名喷洒，达 100 次/小时后该 IP 整体被锁。"""
    client = app_ctx.test_client()
    for i in range(100):
        assert _login(client, f'tc_spray_{i}', 'x').status_code == 401

    # 第 101 次：无论用户名是什么，直接 429
    res = _login(client, 'tc_spray_999', 'x')
    assert res.status_code == 429 and res.get_json()['code'] == 1004


def test_expired_rows_purged_by_daily_job(app_ctx, lockout_cleanup):
    from datetime import datetime, timedelta

    from app.services.login_guard import purge_expired

    client = app_ctx.test_client()
    _login(client, 'some_user', 'wrong')

    fresh = LoginFailure.query.count()
    assert fresh > 0

    # 把 last_fail_at 拨到 8 天前 → 清理应删光；昨天的记录保留
    LoginFailure.query.update(
        {LoginFailure.last_fail_at: datetime.utcnow() - timedelta(days=8)},
        synchronize_session=False)
    db.session.commit()
    assert purge_expired(days=7) == fresh
    db.session.commit()
    assert LoginFailure.query.count() == 0
