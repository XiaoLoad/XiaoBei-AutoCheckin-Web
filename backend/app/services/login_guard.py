# 登录防爆破：三维度失败计数 + 锁定（持久化到 login_failures 表，重启不失效）。
# 维度设计：
#   账号×IP（低阈值）——拦单点暴力破解；攻击者换 IP 即落入账号全局维度。
#   账号全局（高阈值）——拦多 IP 分布式撞库；阈值高于账号×IP 是为了
#     避免攻击者用少量失败恶意锁死他人账号（DoS）。
#   IP 全局（最宽）——拦跨用户名喷洒；寝室场景大量用户共享出口 NAT，故放宽。
# 时间一律 datetime.utcnow（与 token_blacklist 口径一致；锁只比时间差，不受展示口径影响）。
# F4.3 归口说明：全站三处 utcnow（JWT exp/iat、token_blacklist 清理、登录失败计数窗口）
# 均为「只比差值、不展示」的内部口径，与业务展示时间（now_cst，中国本地）互不混用，保持现状。
from datetime import datetime, timedelta

from app.extensions import db
from app.models.login_failure import LoginFailure

# 阈值与锁定时长（窗口为 last_fail_at 起的滑动窗口）
_WINDOW = timedelta(minutes=15)
_LOCK = timedelta(minutes=15)
# (维度后缀, 窗口内允许失败次数, 窗口)：账号×IP / 账号全局 / IP 全局
# 账号全局窗口放宽到 1h×20：分布式撞库的容忍度必须显著高于单点爆破
_RULES = (
    ('u:{username}:ip:{ip}', 10, _WINDOW),
    ('u:{username}', 20, timedelta(hours=1)),
    ('ip:{ip}', 100, timedelta(hours=1)),
)


def _now():
    return datetime.utcnow()


def check_locked(username, ip):
    """任一维度锁定中即拦截。返回锁定剩余秒数（>0 表示被拦），0 表示放行。"""
    now = _now()
    keys = (
        f'u:{username}:ip:{ip}',
        f'u:{username}',
        f'ip:{ip}',
    )
    rows = LoginFailure.query.filter(LoginFailure.key.in_(keys)).all()
    remaining = 0
    for r in rows:
        if r.locked_until and r.locked_until > now:
            remaining = max(remaining, int((r.locked_until - now).total_seconds()))
    return remaining


def record_failure(username, ip):
    """记录一次失败：三个维度各 upsert 计数，达到阈值即置 locked_until。
    窗口过期（now - last_fail_at ≥ 该维度窗口）则重新从 1 计数。"""
    now = _now()
    for pattern, threshold, window in _RULES:
        key = pattern.format(username=username, ip=ip)
        row = db.session.get(LoginFailure, key)
        if row is None:
            db.session.add(LoginFailure(
                key=key, fail_count=1, last_fail_at=now,
                locked_until=_LOCK if threshold <= 1 else None))
            continue
        expired = (now - row.last_fail_at) >= window
        row.fail_count = 1 if expired else row.fail_count + 1
        row.last_fail_at = now
        if row.fail_count >= threshold:
            row.locked_until = now + _LOCK


def clear_failures(username):
    """登录成功后清掉该账号名下全部失败计数（含其各 IP 维度）；IP 维度
    （ip:{ip}）保留——它服务的是跨用户名喷洒防护，与单账号登录成功无关。"""
    LoginFailure.query.filter(
        LoginFailure.key.like(f'u:{username}:%')).delete(synchronize_session=False)
    LoginFailure.query.filter(
        LoginFailure.key == f'u:{username}').delete(synchronize_session=False)


def purge_expired(days=7):
    """物理删除 last_fail_at 超过 days 天的记录，挂每日清理 job。"""
    cutoff = _now() - timedelta(days=days)
    return LoginFailure.query.filter(LoginFailure.last_fail_at < cutoff).delete(
        synchronize_session=False)
