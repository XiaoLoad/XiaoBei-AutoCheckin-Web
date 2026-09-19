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

from app.events import (account_changed, auth_logged_out, auth_login,
                        auth_password_changed, schedule_changed, user_changed)
from app.extensions import db
from app.models.op_log import OpLog

log = logging.getLogger('op_log')

CATEGORY_AUTH = 'auth'
CATEGORY_USER = 'user'
CATEGORY_ACCOUNT = 'account'
CATEGORY_SCHEDULE = 'schedule'

RESULT_SUCCESS = 'success'
RESULT_FAIL = 'fail'

# 动作码（op_logs.action 的取值域）。集中定义而非就地写字符串：拼错一个动作码不会报任何错，
# 日志照样落库、界面照样显示，只是筛选下拉里多出一个谁也不认识的项——这类错误没有运行时反馈，
# 只能靠「只有一处能写错」来防。查询侧（routes/op_logs.py 的统计与聚合）同样引用这里，
# 免得写入端改了码值、读取端还在按旧值统计，数字静默归零。
# ⚠️ 新增动作必须同步前端的中文表 frontend/src/utils/opLogMeta.js::OP_ACTION_META，
# 否则筛选下拉会把码值（如 pool.create）原样显示给管理员。
ACTION_AUTH_LOGIN = 'auth.login'
ACTION_AUTH_LOGOUT = 'auth.logout'
ACTION_AUTH_PASSWORD = 'auth.password'
ACTION_USER_CREATE = 'user.create'
ACTION_USER_UPDATE = 'user.update'
ACTION_USER_ENABLE = 'user.enable'
ACTION_USER_DISABLE = 'user.disable'
ACTION_USER_DELETE = 'user.delete'
ACTION_ACCOUNT_CREATE = 'account.create'
ACTION_ACCOUNT_UPDATE = 'account.update'
ACTION_ACCOUNT_DELETE = 'account.delete'
ACTION_ACCOUNT_SECRET_VIEW = 'account.secret_view'
ACTION_SCHEDULE_CREATE = 'schedule.create'
ACTION_SCHEDULE_UPDATE = 'schedule.update'
ACTION_SCHEDULE_DELETE = 'schedule.delete'
ACTION_SCHEDULE_ENABLE = 'schedule.enable'
ACTION_SCHEDULE_DISABLE = 'schedule.disable'

# B 平台密码查看动作的统一文案（成功/失败共用主语，区别在 result 与后缀）
SECRET_VIEW_SUMMARY = '查看账号「{account}」的 B 平台密码'


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
# 删除用户时连带清理的行数 → 摘要里的量词与名称（顺序即重要程度）
_DELETE_CASCADE_LABELS = (('accounts', '个', '账号'), ('schedules', '个', '定时任务'),
                          ('signRecords', '条', '签到记录'), ('pushLogs', '条', '推送日志'))


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
        record(ACTION_USER_ENABLE if enabled else ACTION_USER_DISABLE, CATEGORY_USER,
               summary=f'{"启用" if enabled else "禁用"}用户「{user.username}」',
               detail={'targetUserId': user.id, 'targetUsername': user.username,
                       'changes': [{'field': 'enabled', 'from': not enabled, 'to': enabled}]},
               user=actor)
        return

    if kind == 'users.delete':
        # 删除事件只带普通值快照（users 行已删，commit 后属性不可再读）
        snap = kw.get('snapshot') or {}
        cascade = kw.get('cascade') or {}
        target_id = snap.get('targetUserId', kw.get('user_id'))
        name = snap.get('targetUsername') or ''
        summary = f'删除用户「{name}」' if name else f'删除用户（ID {target_id}）'
        # 物理删除会连带清掉账号/任务/记录，只写「删了用户」事后无法解释数据消失
        tail = '、'.join(f"{cascade[k]} {unit}{label}"
                         for k, unit, label in _DELETE_CASCADE_LABELS if cascade.get(k))
        if tail:
            summary += f'（连带删除 {tail}）'
        record(ACTION_USER_DELETE, CATEGORY_USER, summary=summary,
               detail={'targetUserId': target_id, 'targetUsername': name,
                       'targetRole': snap.get('role', ''), 'cascade': cascade},
               user=actor)
        return

    if user is None:
        return

    if kind == 'users.create':
        record(ACTION_USER_CREATE, CATEGORY_USER,
               summary=f'新建用户「{user.username}」（角色 {user.role}，额度 {user.quota}）',
               detail={'targetUserId': user.id, 'targetUsername': user.username,
                       'role': user.role, 'enabled': bool(user.enabled), 'quota': user.quota},
               user=actor)
        return

    if kind == 'users.update':
        changes = _changes(payload, kw.get('before'), user)
        record(ACTION_USER_UPDATE, CATEGORY_USER,
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
        record(ACTION_AUTH_LOGIN, CATEGORY_AUTH, result=RESULT_FAIL,
               summary=f'登录失败「{who}」：{reason}',
               detail={'account': who, 'reason': reason})
        return
    user = kw.get('user')
    record(ACTION_AUTH_LOGIN, CATEGORY_AUTH, summary='登录成功',
           detail={'account': getattr(user, 'username', '') or kw.get('username', '')},
           user=user)


def _on_logout(sender, **kw):
    user = kw.get('user') or _actor()
    record(ACTION_AUTH_LOGOUT, CATEGORY_AUTH, summary='退出登录', user=user)


def _on_password_changed(sender, **kw):
    user = kw.get('user') or _actor()
    record(ACTION_AUTH_PASSWORD, CATEGORY_AUTH, summary='修改登录密码', user=user)


# ===== 账号域（订阅 account_changed，发布点在 routes/accounts.py 与 admin.py）=====
# 受管字段：diff 只盯这几项；password 永不进 changes（单独 passwordChanged 布尔），
# pushCreds 含密钥同样不落值，只在有变时记「已更新」。
_ACCOUNT_FIELDS = ('account', 'type', 'enabled')


def _account_changes(payload, before, acc):
    known = isinstance(before, dict)
    out = []
    for key in _ACCOUNT_FIELDS:
        if key not in payload:
            continue
        new = getattr(acc, key, None)
        if key == 'enabled':
            new = bool(new)
        old = before.get(key) if known else None
        if known and key in before and old == new:
            continue
        out.append({'field': key, 'from': old, 'to': new})
    # 推送凭证含密钥：值不落日志，仅在确有变更时记一个占位项（前端渲染成「已更新」）
    if 'pushCreds' in payload and known and before.get('push_creds_json') != acc.push_cred_json:
        out.append({'field': 'pushCreds'})
    return out


def _acc_name(acc):
    """账号展示名：优先 B 平台回填的姓名，回落登录账号"""
    return (acc.profile.get('name') if acc.profile else '') or acc.account


def _on_account_changed(sender, **kw):
    kind = str(sender)
    acc = kw.get('account')
    actor = _actor()
    payload = _payload()

    if kind == 'accounts.delete':
        snap = kw.get('snapshot') or {}
        name = snap.get('account') or ''
        cascade = snap.get('cascade') or {}
        summary = f'删除账号「{name}」' if name else f'删除账号（ID {snap.get("account_id")}）'
        if cascade:
            summary += '（连带 %s 个定时任务、%s 条签到记录）' % (
                cascade.get('schedules', 0), cascade.get('signRecords', 0))
        record(ACTION_ACCOUNT_DELETE, CATEGORY_ACCOUNT, summary=summary,
               detail={'accountId': snap.get('account_id'), 'account': name, 'cascade': cascade},
               user=actor)
        return

    if acc is None:
        return

    if kind == 'accounts.create':
        record(ACTION_ACCOUNT_CREATE, CATEGORY_ACCOUNT,
               summary=f'添加账号「{_acc_name(acc)}」（{acc.account}）',
               detail={'accountId': acc.id, 'account': acc.account, 'type': acc.type,
                       'enabled': bool(acc.enabled), 'passwordChanged': True},
               user=actor)
        return

    if kind == 'accounts.update':
        changes = _account_changes(payload, kw.get('before'), acc)
        pwd_changed = bool(kw.get('password_changed'))
        if not changes and not pwd_changed:
            # 无实效变更不记行：与 user.update 同口径，避免空保存刷屏
            return
        record(ACTION_ACCOUNT_UPDATE, CATEGORY_ACCOUNT,
               summary=f'修改账号「{_acc_name(acc)}」（{acc.account}）',
               detail={'accountId': acc.id, 'account': acc.account,
                       'changes': changes, 'passwordChanged': pwd_changed},
               user=actor)
        return

    if kind == 'accounts.secret_view':
        ok = kw.get('result') != RESULT_FAIL
        record(ACTION_ACCOUNT_SECRET_VIEW, CATEGORY_ACCOUNT,
               result=RESULT_SUCCESS if ok else RESULT_FAIL,
               summary=(f'查看账号「{_acc_name(acc)}」（{acc.account}）的 B 平台密码' if ok
                        else f'查看账号「{_acc_name(acc)}」（{acc.account}）密码被拒：{kw.get("reason") or "登录密码验证失败"}'),
               detail={'accountId': acc.id, 'account': acc.account},
               user=actor)
        return


# ===== 定时任务域（订阅 schedule_changed，发布点在 routes/schedules.py）=====
_TASK_LABEL = {'dorm': '寝室签到', 'activity': '活动签到'}


def _task_label(task_type):
    return _TASK_LABEL.get(task_type, task_type or '')


def _on_schedule_changed(sender, **kw):
    kind = str(sender)
    actor = _actor()

    if kind == 'schedules.batch':
        action = kw.get('action')
        affected = kw.get('affected_list') or []
        if not affected:
            # 全部跳过的批量操作没有实效，记行只会刷屏
            return
        if action == 'enable':
            summary = '批量开启 %d 个定时任务' % len(affected)
            if kw.get('config_set_name'):
                summary += '（套用配置套「%s」）' % kw['config_set_name']
        else:
            summary = '批量关闭 %d 个定时任务' % len(affected)
        record(ACTION_SCHEDULE_ENABLE if action == 'enable' else ACTION_SCHEDULE_DISABLE,
               CATEGORY_SCHEDULE, summary=summary,
               detail={'affected': len(affected), 'skipped': kw.get('skipped', 0),
                       'targets': affected,
                       'configSetId': kw.get('config_set_id')},
               user=actor)
        return

    # 删除事件只带普通值快照（ORM 行已删，commit 后属性不可再读），须先于 s 判空处理
    if kind == 'schedules.delete':
        record(ACTION_SCHEDULE_DELETE, CATEGORY_SCHEDULE,
               summary=f'删除定时任务（账号「{kw.get("account_name", "")}」· {_task_label(kw.get("task_type"))}）',
               detail={'scheduleId': kw.get('schedule_id'), 'accountId': kw.get('account_id'),
                       'taskType': kw.get('task_type')},
               user=actor)
        return

    s = kw.get('schedule')
    if s is None:
        return
    label = _task_label(s.task_type)

    if kind == 'schedules.create':
        record(ACTION_SCHEDULE_CREATE, CATEGORY_SCHEDULE,
               summary=f'新建定时任务（账号「{kw.get("account_name", "")}」· {label}）',
               detail={'scheduleId': s.id, 'accountId': s.account_id,
                       'taskType': s.task_type},
               user=actor)
        return

    if kind == 'schedules.update':
        changes = _schedule_changes(kw.get('payload') or {}, kw.get('before'), s)
        if not changes:
            return
        record(ACTION_SCHEDULE_UPDATE, CATEGORY_SCHEDULE,
               summary=f'修改定时任务（账号「{kw.get("account_name", "")}」· {label}）',
               detail={'scheduleId': s.id, 'accountId': s.account_id,
                       'taskType': s.task_type, 'changes': changes},
               user=actor)
        return


# 定时任务受管字段：mode/enabled/config_set_id 做 from→to；config/custom/overrides
# 内容较重且多为配置快照，只记「已更新」占位，不落内容。
_SCHEDULE_FIELDS = ('mode', 'enabled', 'config_set_id')


def _schedule_changes(payload, before, s):
    known = isinstance(before, dict)
    out = []
    for key in _SCHEDULE_FIELDS:
        if key not in payload:
            continue
        new = getattr(s, key, None)
        if key == 'enabled':
            new = bool(new)
        old = before.get(key) if known else None
        if known and key in before and old == new:
            continue
        out.append({'field': key, 'from': old, 'to': new})
    for key in ('config', 'custom', 'overrides'):
        if key in payload:
            out.append({'field': key})
    return out


_connected = False


def connect_handlers():
    """注册订阅者（应用工厂调用）。进程级幂等：create_app 在测试里会被反复调用，
    重复连接会让同一次操作写多条日志。"""
    global _connected
    if _connected:
        return
    user_changed.connect(_on_user_changed)
    account_changed.connect(_on_account_changed)
    schedule_changed.connect(_on_schedule_changed)
    auth_login.connect(_on_auth_login)
    auth_logged_out.connect(_on_logout)
    auth_password_changed.connect(_on_password_changed)
    _connected = True
