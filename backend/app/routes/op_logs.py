# 操作日志读取蓝图：管理员审计平台用户的关键操作（登录/登出/用户与权限变更）。
# 前缀 /api/op-logs；全部限管理员——日志含全员用户名、IP、UA 与变更明细，属敏感信息。
# 写入不在这里：见 services/op_log.py 的事件订阅者（发布方 app/events.py）。
#
# 三个读取口径，各管一件事，互不叠加：
#   /           平铺流水（按时间倒序，供「流水」视图与导出）
#   /sessions   会话段（成功登录 → 登出之间的一切操作归一段，供「会话」视图）
#   /summary    页头指标 + 异常聚合（今日脉搏与「同一 IP 连续登录失败」告警）
# 会话由日志现算而非落库：日志是只追加的事实流，会话是它的一个投影；
# 另建 sessions 表会引入「登出时回写」「超时补收口」两套状态同步，得不偿失。
from datetime import datetime, timedelta

from flask import Blueprint, current_app, request
from sqlalchemy import func, or_

from app.extensions import db
from app.models.op_log import OpLog
from app.models.system_config import get_setting
from app.models.user import now_cst
from app.utils.auth import admin_required
from app.utils.response import success

bp = Blueprint('op_logs', __name__, url_prefix='/api/op-logs')

# 每页上限：日志表随使用量线性增长，放开了只会让页面与数据库都难受
_MAX_PAGE_SIZE = 100
_DEFAULT_PAGE_SIZE = 20
# 单次会话聚合的扫描行数上限（取最新 N 行后反转）。会话必须看到全量才能正确收口，
# 故不能分页下推；用上限兜住极端数据量，代价只是时间范围最旧处的那一段可能被截断。
_SESSION_SCAN_CAP = 20000
# 异常聚合：同一 IP 在窗口内登录失败达到该次数才提示
_ANOMALY_WINDOW_DAYS = 7
_ANOMALY_MIN_FAILS = 3
_ANOMALY_TOP_N = 5


def _parse_date(raw, end_of_day=False):
    """解析 YYYY-MM-DD；非法返回 None（忽略该条件而非报 400——
    筛选条上的日期由日期选择器给出，脏值只可能是人为构造的请求）。"""
    if not raw:
        return None
    try:
        d = datetime.strptime(str(raw).strip()[:10], '%Y-%m-%d')
    except (TypeError, ValueError):
        return None
    return d + timedelta(days=1) if end_of_day else d


def _filtered_query():
    """按查询串组装过滤后的查询。

    keyword 一栏兼顾三处（用户名 / IP / 摘要）：界面只有一个搜索框，
    而「谁做的」「哪个 IP」「动了谁」是同一类追问，拆成三个输入框反而更难用。
    """
    category = (request.args.get('category') or '').strip()
    result = (request.args.get('result') or '').strip()
    action = (request.args.get('action') or '').strip()
    username = (request.args.get('username') or '').strip()
    keyword = (request.args.get('keyword') or '').strip()
    date_from = _parse_date(request.args.get('date_from'))
    date_to = _parse_date(request.args.get('date_to'), end_of_day=True)

    q = OpLog.query
    if category:
        q = q.filter(OpLog.category == category)
    if result:
        q = q.filter(OpLog.result == result)
    if action:
        q = q.filter(OpLog.action == action)
    if username:
        q = q.filter(OpLog.username.like(f'%{username}%'))
    if keyword:
        like = f'%{keyword}%'
        q = q.filter(or_(OpLog.username.like(like), OpLog.ip.like(like),
                         OpLog.summary.like(like)))
    if date_from:
        q = q.filter(OpLog.created_at >= date_from)
    if date_to:
        q = q.filter(OpLog.created_at < date_to)
    return q


def _page_args(default_size=_DEFAULT_PAGE_SIZE):
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        size = min(_MAX_PAGE_SIZE, max(1, int(request.args.get('page_size', default_size))))
    except (TypeError, ValueError):
        size = default_size
    return page, size


def _session_ttl_hours():
    """会话时长：与 JWT 签发口径一致（设置页 session_hours，未配置回退 .env）。
    一段会话的寿命就是那张令牌的寿命，两处取值必须同源，否则会话视图会与
    「刷新后突然要重新登录」的真实体验对不上。"""
    try:
        hours = get_setting('session_hours')
        if hours:
            return int(hours)
    except Exception:
        pass
    try:
        return int(current_app.config['JWT_EXPIRES_HOURS'])
    except Exception:
        return 12


# 会话收口原因 → 只回码值，中文说法在前端 utils/opLogMeta.js（全站同一条约定）
def _event_dict(r):
    return {
        'id': r.id,
        'time': r.created_at.strftime('%H:%M') if r.created_at else '',
        'createdAt': r.created_at.strftime('%Y-%m-%d %H:%M:%S') if r.created_at else '',
        'action': r.action or '',
        'category': r.category or '',
        'result': r.result or 'success',
        'summary': r.summary or '',
        'detail': r.get_detail(),
        'ip': r.ip or '',
    }


def _new_session(r):
    return {
        'userId': r.user_id,
        'username': r.username or '',
        'role': r.role or '',
        'ip': r.ip or '',
        'startAt': r.created_at,
        'lastAt': r.created_at,
        'reason': 'ongoing',
        'events': [],
    }


def _build_sessions(rows):
    """把按时间升序的操作日志切成会话段。

    规则与 JWT 生命周期对齐（用户登录 → 登出之间的一切操作都归该段）：
      - 成功的 auth.login 开一段；同一用户已有未收口段则记为 superseded（被新登录顶替）；
      - auth.logout 收口当前段（logout）；
      - 距上一事件超过 TTL 视为令牌已过期，段就地收口为 expired；
      - 其它操作追加到该用户当前段；若没有当前段（历史数据、或令牌未过期时的操作）
        则开一段 orphan —— 记为「无登录记录」而不是丢弃，否则这些操作会凭空消失。

    无归属用户的行（登录失败，user_id 为 NULL）不进会话：它们本就是「没建立起会话」
    的那些尝试，由 /summary 的异常聚合单独呈现。
    """
    ttl_seconds = _session_ttl_hours() * 3600
    sessions = []
    open_by_user = {}

    for r in rows:
        uid = r.user_id
        ts = r.created_at
        if uid is None or ts is None:
            continue

        cur = open_by_user.get(uid)
        if cur is not None and cur['lastAt'] is not None \
                and (ts - cur['lastAt']).total_seconds() > ttl_seconds:
            cur['reason'] = 'expired'
            open_by_user.pop(uid, None)
            cur = None

        if r.action == 'auth.login' and r.result == 'success':
            if cur is not None:
                cur['reason'] = 'superseded'
            cur = _new_session(r)
            sessions.append(cur)
            open_by_user[uid] = cur
        elif cur is None:
            cur = _new_session(r)
            cur['reason'] = 'orphan'
            sessions.append(cur)
            open_by_user[uid] = cur

        cur['events'].append(_event_dict(r))
        cur['lastAt'] = ts
        if not cur['ip'] and r.ip:
            cur['ip'] = r.ip
        if r.action == 'auth.logout':
            cur['reason'] = 'logout'
            open_by_user.pop(uid, None)

    now = now_cst()
    for s in sessions:
        start, last = s['startAt'], s['lastAt']
        if s['reason'] == 'ongoing' and start is not None \
                and (now - start).total_seconds() > ttl_seconds:
            s['reason'] = 'expired'
        s['running'] = s['reason'] == 'ongoing'
        end = now if s['running'] else last
        s['endAt'] = last
        s['durationSeconds'] = max(0, int((end - start).total_seconds())) if start and end else 0
        s['eventCount'] = len(s['events'])
    return sessions


def _session_dict(s):
    def fmt(dt):
        return dt.strftime('%Y-%m-%d %H:%M') if dt else ''
    return {
        'id': f"{s['userId']}-{s['events'][0]['id']}" if s['events'] else '',
        'userId': s['userId'],
        'username': s['username'],
        'role': s['role'],
        'ip': s['ip'],
        'startAt': fmt(s['startAt']),
        'endAt': fmt(s['endAt']),
        'startTime': s['startAt'].strftime('%H:%M') if s['startAt'] else '',
        'durationSeconds': s['durationSeconds'],
        'running': bool(s['running']),
        'closeReason': s['reason'],
        'eventCount': s['eventCount'],
        'events': s['events'],
    }


@bp.route('', methods=['GET'])
@admin_required
def list_op_logs():
    """操作日志平铺流水（时间倒序）。

    查询参数：page / page_size（≤100）、category、result、action、username、
    keyword（用户名 / IP / 摘要三选一即命中）、date_from / date_to（YYYY-MM-DD，含当天）。
    """
    page, size = _page_args()
    q = _filtered_query()
    total = q.count()
    rows = (q.order_by(OpLog.created_at.desc(), OpLog.id.desc())
            .offset((page - 1) * size).limit(size).all())
    return success({
        'items': [r.to_dict() for r in rows],
        'total': total,
        'page': page,
        'page_size': size,
    })


@bp.route('/sessions', methods=['GET'])
@admin_required
def list_sessions():
    """会话段列表（按开始时间倒序）。过滤参数与平铺流水完全一致。

    过滤发生在会话切分之前：筛「只看失败」时同一段会话里只会留下失败事件，
    这是筛选的应有含义，不额外补齐被滤掉的事件。
    """
    page, size = _page_args(10)
    q = _filtered_query()
    # 会话必须看到全量才能正确收口，故不能把分页下推到 SQL；
    # 取最新 _SESSION_SCAN_CAP 行再反转成升序（旧端被截断的代价小于新端被截断）
    rows = (q.order_by(OpLog.created_at.desc(), OpLog.id.desc())
            .limit(_SESSION_SCAN_CAP).all())
    rows.reverse()

    sessions = _build_sessions(rows)
    sessions.sort(key=lambda s: (s['startAt'] or datetime.min, s['lastAt'] or datetime.min),
                  reverse=True)
    total = len(sessions)
    start = (page - 1) * size
    page_items = sessions[start:start + size]
    return success({
        'items': [_session_dict(s) for s in page_items],
        'total': total,
        'page': page,
        'page_size': size,
    })


def _ongoing_count(ttl_hours):
    """进行中会话数 = 「最近一次认证事件是成功登录、且还在令牌有效期内」的用户数。
    只看用户与动作、不看全部日志，代价与用户量同阶而非与日志量同阶。"""
    now = now_cst()
    window_start = now - timedelta(hours=ttl_hours * 2)
    rows = (OpLog.query
            .filter(OpLog.created_at >= window_start,
                    OpLog.user_id.isnot(None),
                    OpLog.action.in_(('auth.login', 'auth.logout')))
            .order_by(OpLog.created_at.asc(), OpLog.id.asc()).all())
    latest = {}
    for r in rows:
        latest[r.user_id] = r
    return sum(1 for r in latest.values()
               if r.action == 'auth.login' and r.result == 'success'
               and r.created_at >= now - timedelta(hours=ttl_hours))


def _anomalies():
    """同一 IP 连续登录失败：登录失败没有归属用户，也就没有会话可看，
    只能按 IP 聚合成一条「未能建立会话的尝试」，否则这批记录在会话视图里完全隐形。"""
    since = now_cst() - timedelta(days=_ANOMALY_WINDOW_DAYS)
    base = [OpLog.action == 'auth.login', OpLog.result == 'fail',
            OpLog.ip != '', OpLog.created_at >= since]
    groups = (db.session.query(OpLog.ip, func.count(OpLog.id),
                               func.min(OpLog.created_at), func.max(OpLog.created_at))
              .filter(*base)
              .group_by(OpLog.ip)
              .having(func.count(OpLog.id) >= _ANOMALY_MIN_FAILS)
              .order_by(func.count(OpLog.id).desc())
              .limit(_ANOMALY_TOP_N).all())
    if not groups:
        return []

    ips = [g[0] for g in groups]
    # 被尝试的账号只存在 detail JSON 里，故取回这批 IP 的行后在前端侧解析（已限定 IP 与窗口，规模可控）
    rows = (OpLog.query.filter(*base, OpLog.ip.in_(ips))
            .order_by(OpLog.created_at.desc()).limit(200).all())
    accounts = {}
    for r in rows:
        detail = r.get_detail() or {}
        acc = detail.get('account')
        if acc:
            accounts.setdefault(r.ip, [])
            if acc not in accounts[r.ip]:
                accounts[r.ip].append(acc)
    return [{
        'ip': ip,
        'count': int(cnt),
        'firstAt': first.strftime('%m-%d %H:%M') if first else '',
        'lastAt': last.strftime('%m-%d %H:%M') if last else '',
        'accounts': accounts.get(ip, [])[:6],
    } for ip, cnt, first, last in groups]


@bp.route('/summary', methods=['GET'])
@admin_required
def op_log_summary():
    """页头指标 + 异常聚合 + 保留天数。

    指标是「今日」口径的当日脉搏，**不随筛选条件变化**：筛选是在追问历史，
    而这四个数回答的是「今天这个平台还健康吗」，被筛选牵着走就失去意义了。
    """
    ttl_hours = _session_ttl_hours()
    today_start = datetime.combine(now_cst().date(), datetime.min.time())

    def _count(*conds):
        return OpLog.query.filter(*conds).count()

    return success({
        'metrics': {
            'loginToday': _count(OpLog.action == 'auth.login', OpLog.result == 'success',
                                 OpLog.created_at >= today_start),
            'loginFailToday': _count(OpLog.action == 'auth.login', OpLog.result == 'fail',
                                     OpLog.created_at >= today_start),
            # 「权限与额度变更」= 用户管理类操作 + 改密：两者都在改「谁能做什么」
            'userChangeToday': _count(OpLog.result == 'success',
                                      OpLog.created_at >= today_start,
                                      or_(OpLog.category == 'user',
                                          OpLog.action == 'auth.password')),
            'ongoingSessions': _ongoing_count(ttl_hours),
        },
        'anomalies': _anomalies(),
        'anomalyWindowDays': _ANOMALY_WINDOW_DAYS,
        'retentionDays': int(get_setting('op_log_retention_days') or 365),
    })


@bp.route('/meta', methods=['GET'])
@admin_required
def op_log_meta():
    """筛选项：分类与动作的现存值（带计数，供筛选条只展示有数据的项）。

    计数按「全表现存记录」算而非当前筛选结果——筛选条本身是筛选条件的来源，
    不能随筛选结果收缩，否则选中一项后其余项全部消失、无法回退。
    """
    cat_rows = (db.session.query(OpLog.category, func.count(OpLog.id))
                .group_by(OpLog.category).all())
    act_rows = (db.session.query(OpLog.action, func.count(OpLog.id))
                .group_by(OpLog.action).all())
    return success({
        'categories': [{'value': c, 'count': int(n)} for c, n in cat_rows if c],
        'actions': [{'value': a, 'count': int(n)} for a, n in act_rows if a],
    })
