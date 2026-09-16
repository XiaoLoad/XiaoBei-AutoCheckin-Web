# 操作日志（审计）的唯一落库出口与事件订阅者。
# 为什么走订阅者而不是逐路由埋点：用户与权限变更已有 4 个 user_changed 发布点、
# 登出已有 auth_logged_out，订阅即可全覆盖；发布方不 import 本模块（只 import app.events），
# 将来再挂「异地登录提醒」「连续失败告警」等订阅者也不必回头改路由。
# 写入失败一律就地吞掉并记日志：审计日志永远不能反噬业务主流程。
#
# 记录对象是「操作者」而非「被操作者」：管理员改了谁，那行日志的 user 列应是管理员本人，
# 被改的人（目标）落在 summary 与 detail 里。故 user/username/role 三个列存的是操作者快照，
# 无请求上下文（脚本/CLI 触发）时记 'system'，登录失败则留空（用户名在 summary 里）。
import logging

from flask import has_request_context, request

from app.events import (auth_logged_out, auth_login, auth_password_changed,
                        user_changed)
from app.extensions import db
from app.models.op_log import OpLog

log = logging.getLogger('op_log')

CATEGORY_AUTH = 'auth'
CATEGORY_USER = 'user'

RESULT_SUCCESS = 'success'
RESULT_FAIL = 'fail'


def client_ip():
    """客户端 IP。反代（nginx）下 remote_addr 恒为代理地址，故优先取转发头，
    取 X-Forwarded-For 首段（最靠近真实客户端的一跳）。"""
    if not has_request_context():
        return ''
    xff = request.headers.get('X-Forwarded-For') or ''
    if xff:
        return xff.split(',')[0].strip()[:64]
    real = (request.headers.get('X-Real-IP') or '').strip()
    if real:
        return real[:64]
    return (request.remote_addr or '')[:64]


def client_agent():
    """客户端 User-Agent 原文（截断到列宽）"""
    if not has_request_context():
        return ''
    return (request.headers.get('User-Agent') or '')[:255]


def _actor():
    """当前请求的登录用户（操作者）；无请求上下文或未登录（如登录接口本身）返回 None。"""
    if not has_request_context():
        return None
    return getattr(request, 'current_user', None)


def _payload():
    """当前请求的 JSON body（用于还原本次提交的字段）；非 JSON / 无 body 返回 {}"""
    if not has_request_context():
        return {}
    try:
        data = request.get_json(silent=True)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def record(action, category, result=RESULT_SUCCESS, summary='', detail=None, user=None,
           username='', role=''):
    """写一条操作日志。user 为操作者对象（可 None）。

    自带 commit：发布者均在自身事务提交之后发布事件，此处独立提交不会影响业务数据；
    提交失败时回滚，最坏结果只是丢一条日志。"""
    try:
        entry = OpLog(
            user_id=getattr(user, 'id', None),
            username=((getattr(user, 'username', '') or username or 'system'))[:64],
            role=((getattr(user, 'role', '') or role or 'system'))[:16],
            action=(action or '')[:48],
            category=(category or '')[:24],
            result=(result or RESULT_SUCCESS)[:16],
            summary=(summary or '')[:255],
            ip=client_ip(),
            user_agent=client_agent(),
        )
        entry.set_detail(detail)
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception('操作日志写入失败：action=%s', action)


# ===== 用户与权限变更（订阅 user_changed）=====
# users.py 的发布点：users.create / users.update / users.status / users.delete
_CHANGE_FIELDS = ('username', 'role', 'enabled', 'quota')


def _changes(payload, before, user):
    """还原本次真正生效的字段变更（仅取提交过的字段）；有 before 时值未变的不入明细，
    避免「保存」按钮一按就记一堆无意义的行。缺 before 时 from 记 None。"""
    known = isinstance(before, dict)
    out = []
    for key in _CHANGE_FIELDS:
        if key not in payload:
            continue
        new = getattr(user, key, None)
        old = before.get(key) if known else None
        if known and key in before and old == new:
            continue
        out.append({'field': key, 'from': old, 'to': new})
    return out


def _on_user_changed(sender, **kw):
    actor = _actor()
    kind = str(sender)
    user = kw.get('user')
    payload = _payload()

    if kind == 'users.status' and user is not None:
        enabled = bool(user.enabled)
        record('user.enable' if enabled else 'user.disable', CATEGORY_USER,
               summary=f'{"启用" if enabled else "禁用"}用户「{user.username}」',
               detail={'targetUserId': user.id, 'targetUsername': user.username,
                       'changes': [{'field': 'enabled', 'from': not enabled, 'to': enabled}]},
               user=actor)
        return

    if kind == 'users.delete':
        target_id = kw.get('user_id')
        target = None
        try:
            from app.models.user import User
            target = db.session.get(User, int(target_id))
        except Exception:
            target = None
        name = target.username if target is not None else ''
        # users.delete 目前是桩接口（返回成功但不销毁数据）。日志照实记，不粉饰：
        # 否则管理员看到一条「删除用户」会以为人真的没了。桩实现落地后去掉这句后缀。
        record('user.delete', CATEGORY_USER,
               summary=(f'删除用户「{name}」（桩接口未实际销毁）' if name
                        else f'删除用户（ID {target_id}，桩接口未实际销毁）'),
               detail={'targetUserId': target_id, 'targetUsername': name, 'stub': True},
               user=actor)
        return

    if user is None:
        return

    if kind == 'users.create':
        record('user.create', CATEGORY_USER,
               summary=f'新建用户「{user.username}」（角色 {user.role}，额度 {user.quota}）',
               detail={'targetUserId': user.id, 'targetUsername': user.username,
                       'role': user.role, 'enabled': bool(user.enabled), 'quota': user.quota},
               user=actor)
        return

    if kind == 'users.update':
        changes = _changes(payload, kw.get('before'), user)
        record('user.update', CATEGORY_USER,
               summary=f'修改用户「{user.username}」',
               detail={'targetUserId': user.id, 'targetUsername': user.username,
                       'changes': changes, 'passwordChanged': bool(kw.get('password_changed'))},
               user=actor)
        return


# ===== 认证（订阅 auth_login / auth_logged_out / auth_password_changed）=====
def _on_auth_login(sender, **kw):
    """登录尝试：成功记操作者本人，失败无归属用户（user_id 留空，用户名进 summary），
    失败流水是排查暴力破解与误锁账号的唯一线索，故成功失败都要留痕。"""
    if kw.get('result') == RESULT_FAIL:
        who = kw.get('username') or '未知账号'
        reason = kw.get('reason') or '登录失败'
        record('auth.login', CATEGORY_AUTH, result=RESULT_FAIL,
               summary=f'登录失败「{who}」：{reason}',
               detail={'account': who, 'reason': reason})
        return
    user = kw.get('user')
    record('auth.login', CATEGORY_AUTH, summary='登录成功',
           detail={'account': getattr(user, 'username', '') or kw.get('username', '')},
           user=user)


def _on_logout(sender, **kw):
    user = kw.get('user') or _actor()
    record('auth.logout', CATEGORY_AUTH, summary='退出登录', user=user)


def _on_password_changed(sender, **kw):
    user = kw.get('user') or _actor()
    record('auth.password', CATEGORY_AUTH, summary='修改登录密码', user=user)


_connected = False


def connect_handlers():
    """注册订阅者（应用工厂调用）。进程级幂等：create_app 在测试里会被反复调用，
    重复连接会让同一次操作写多条日志。"""
    global _connected
    if _connected:
        return
    user_changed.connect(_on_user_changed)
    auth_login.connect(_on_auth_login)
    auth_logged_out.connect(_on_logout)
    auth_password_changed.connect(_on_password_changed)
    _connected = True
