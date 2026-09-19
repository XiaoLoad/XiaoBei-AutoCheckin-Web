# 操作日志读取蓝图：管理员审计平台用户的关键操作（登录/登出/用户与权限变更）。
# 前缀 /api/op-logs；全部限管理员——日志含全员用户名、IP、UA 与变更明细，属敏感信息。
# 日志本身的写入不在这里：见 services/op_log.py 的事件订阅者（发布方 app/events.py）。
# 本蓝图唯一的写接口是 /anomalies/ack（把告警标记为已处理），写的是确认记录而非日志。
#
# 读取口径各管一件事，互不叠加：
#   /           平铺流水（按时间倒序，供「流水」视图与导出）
#   /sessions   会话段（成功登录 → 登出之间的一切操作归一段，供「会话」视图）
#   /summary    页头指标 + 异常聚合（今日脉搏与「同一 IP 连续登录失败」告警）
#   /meta       筛选项候选值
# 会话由日志现算而非落库：日志是只追加的事实流，会话是它的一个投影；
# 另建 sessions 表会引入「登出时回写」「超时补收口」两套状态同步，得不偿失。
from datetime import datetime, timedelta

from flask import Blueprint, current_app, request
from sqlalchemy import func, or_

from app.extensions import db
from app.models.op_log import OpAnomalyAck, OpLog
from app.models.system_config import get_setting
from app.models.user import now_cst
from app.services.op_log import (ACTION_AUTH_LOGIN, ACTION_AUTH_LOGOUT,
                                 ACTION_AUTH_PASSWORD)
from app.utils.auth import admin_required
from app.utils.response import error, success

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
# 窗口内按 IP 聚合的兜底上限：只为防住「上万个 IP 各失败 3 次」的极端量，
# 正常规模远达不到，故不做 SQL 层的阈值+排序截断（截断后再过滤确认会导致少显示）
_ANOMALY_SCAN_CAP = 200
# 单次「标记已处理」的来源 IP 上限：界面一次最多给 5 条（Top N），留些余量
_ACK_MAX_IPS = 20


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

        if r.action == ACTION_AUTH_LOGIN and r.result == 'success':
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
        if r.action == ACTION_AUTH_LOGOUT:
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
                    OpLog.action.in_((ACTION_AUTH_LOGIN, ACTION_AUTH_LOGOUT)))
            .order_by(OpLog.created_at.asc(), OpLog.id.asc()).all())
    latest = {}
    for r in rows:
        latest[r.user_id] = r
    return sum(1 for r in latest.values()
               if r.action == ACTION_AUTH_LOGIN and r.result == 'success'
               and r.created_at >= now - timedelta(hours=ttl_hours))


def _anomaly_groups(viewer_id, since):
    """近窗口内按 IP 聚合的登录失败，并带上该账号对这些 IP 的「已确认次数」。

    一次查回来交给调用方分档（该显示的 / 被确认压住的）：把「确认过就不再显示」
    也塞进 SQL 的 having 只会让这段更难读，而窗口内的 IP 数是小量，不值得为它下推。
    """
    acks = (db.session.query(OpAnomalyAck.ip,
                             func.max(OpAnomalyAck.count_at_ack).label('acked'))
            .filter(OpAnomalyAck.user_id == viewer_id)
            .group_by(OpAnomalyAck.ip).subquery())
    return (db.session.query(OpLog.ip, func.count(OpLog.id).label('cnt'),
                             func.min(OpLog.created_at), func.max(OpLog.created_at),
                             func.coalesce(func.max(acks.c.acked), 0).label('acked'))
            .outerjoin(acks, acks.c.ip == OpLog.ip)
            .filter(OpLog.action == ACTION_AUTH_LOGIN, OpLog.result == 'fail',
                    OpLog.ip != '', OpLog.created_at >= since)
            .group_by(OpLog.ip)
            .order_by(func.count(OpLog.id).desc())
            .limit(_ANOMALY_SCAN_CAP).all())


def _with_accounts(groups, since):
    """把「被尝试的账号」补进去：它只存在 detail JSON 里，故取回这批 IP 的行后自己解析
    （已限定 IP 与窗口，规模可控）。"""
    if not groups:
        return []
    rows = (OpLog.query
            .filter(OpLog.action == ACTION_AUTH_LOGIN, OpLog.result == 'fail',
                    OpLog.ip != '', OpLog.created_at >= since,
                    OpLog.ip.in_([g.ip for g in groups]))
            .order_by(OpLog.created_at.desc()).limit(200).all())
    accounts = {}
    for r in rows:
        acc = (r.get_detail() or {}).get('account')
        if acc:
            accounts.setdefault(r.ip, [])
            if acc not in accounts[r.ip]:
                accounts[r.ip].append(acc)
    return [{
        'ip': g.ip,
        'count': int(g.cnt),
        'firstAt': g[2].strftime('%m-%d %H:%M') if g[2] else '',
        'lastAt': g[3].strftime('%m-%d %H:%M') if g[3] else '',
        'accounts': accounts.get(g.ip, [])[:6],
    } for g in groups]


def _anomalies(viewer_id):
    """同一 IP 连续登录失败：登录失败没有归属用户，也就没有会话可看，
    只能按 IP 聚合成一条「未能建立会话的尝试」，否则这批记录在会话视图里完全隐形。

    已确认过的 IP 不再提示，但只在它「没有新增失败」时保持沉默：确认记的是确认当时的
    次数，之后再挨新的失败（次数超过它）就要重新冒出来——否则一次确认就能把一个
    还在被撞的 IP 永久藏起来，那这条告警还不如不做。

    返回 (该显示的, 被确认压住的)：后者不是内部细节，界面要用它说明「已处理 N 个」
    ——关掉的东西必须仍然可见，否则「已处理」与「被删掉」在用户眼里没有区别。
    """
    since = now_cst() - timedelta(days=_ANOMALY_WINDOW_DAYS)
    groups = _anomaly_groups(viewer_id, since)

    def _qualifies(g):
        return g.cnt >= _ANOMALY_MIN_FAILS

    hits = [g for g in groups if _qualifies(g) and g.cnt > (g.acked or 0)]
    quiet = [g for g in groups if _qualifies(g) and g.cnt <= (g.acked or 0)][:_ANOMALY_TOP_N]

    counts = {g.ip: int(g.cnt) for g in quiet}
    acked_quiet = []
    if quiet:
        # 取确认记录而不是从聚合结果里凑：确认人、确认时间就是这条「已处理」的凭据本身
        acked_quiet = [dict(a.to_dict(), count=counts.get(a.ip, 0)) for a in
                       OpAnomalyAck.query
                       .filter(OpAnomalyAck.user_id == viewer_id,
                               OpAnomalyAck.ip.in_(list(counts)))
                       .order_by(OpAnomalyAck.created_at.desc()).all()]
    return _with_accounts(hits[:_ANOMALY_TOP_N], since), acked_quiet


@bp.route('/summary', methods=['GET'])
@admin_required
def op_log_summary():
    """页头指标 + 异常聚合 + 保留天数。

    指标是「今日」口径的当日脉搏，**不随筛选条件变化**：筛选是在追问历史，
    而这四个数回答的是「今天这个平台还健康吗」，被筛选牵着走就失去意义了。
    """
    ttl_hours = _session_ttl_hours()
    today_start = datetime.combine(now_cst().date(), datetime.min.time())
    # 以「当前登录的管理员」为口径：确认是个人行为，甲处理过不等于乙也看过了
    anomalies, acked_quiet = _anomalies(request.current_user.id)

    def _count(*conds):
        return OpLog.query.filter(*conds).count()

    return success({
        'metrics': {
            'loginToday': _count(OpLog.action == ACTION_AUTH_LOGIN, OpLog.result == 'success',
                                 OpLog.created_at >= today_start),
            'loginFailToday': _count(OpLog.action == ACTION_AUTH_LOGIN, OpLog.result == 'fail',
                                     OpLog.created_at >= today_start),
            # 「权限与额度变更」= 用户管理类操作 + 改密：两者都在改「谁能做什么」
            'userChangeToday': _count(OpLog.result == 'success',
                                      OpLog.created_at >= today_start,
                                      or_(OpLog.category == 'user',
                                          OpLog.action == ACTION_AUTH_PASSWORD)),
            'ongoingSessions': _ongoing_count(ttl_hours),
        },
        'anomalies': anomalies,
        # 已被确认压住的那些：界面据此说明「已处理 N 个来源 IP」，
        # 关掉的告警仍要看得见，否则「已处理」和「被删掉」在用户眼里没区别
        'ackedQuiet': acked_quiet,
        'anomalyWindowDays': _ANOMALY_WINDOW_DAYS,
        'retentionDays': int(get_setting('op_log_retention_days') or 365),
    })


@bp.route('/anomalies/ack', methods=['POST'])
@admin_required
def op_log_anomaly_ack():
    """把异常告警标记为已处理，按当前管理员账号留痕。

    记的是「确认当时该 IP 失败了几次」，而不是一句「已忽略」：之后再出现新增失败
    （窗口内次数超过这个数）就会重新冒出来。确认依据必须由服务端现算——
    沿用前端传来的次数，等于让界面自己决定它什么时候再提醒自己。
    同一账号对同一 IP 重复确认是覆盖（更新次数与时间），不是追加。
    """
    viewer = request.current_user
    payload = request.get_json(silent=True) or {}
    raw = payload.get('ips')
    if not isinstance(raw, list):
        return error(message='ips 必须是数组', code=4000, status=400)

    ips = []
    for item in raw[:_ACK_MAX_IPS]:
        ip = str(item if item is not None else '').strip()
        if ip and ip not in ips:
            ips.append(ip)
    if not ips:
        return error(message='没有可标记的来源 IP', code=4001, status=400)

    since = now_cst() - timedelta(days=_ANOMALY_WINDOW_DAYS)
    counts = dict(db.session.query(OpLog.ip, func.count(OpLog.id))
                  .filter(OpLog.action == ACTION_AUTH_LOGIN, OpLog.result == 'fail',
                          OpLog.ip.in_(ips), OpLog.created_at >= since)
                  .group_by(OpLog.ip).all())

    existing = {a.ip: a for a in OpAnomalyAck.query
                .filter(OpAnomalyAck.user_id == viewer.id, OpAnomalyAck.ip.in_(ips)).all()}
    now = now_cst()
    for ip in ips:
        row = existing.get(ip)
        if row is None:
            db.session.add(OpAnomalyAck(user_id=viewer.id, username=viewer.username or '',
                                        ip=ip, count_at_ack=int(counts.get(ip, 0)),
                                        created_at=now))
        else:
            row.username = viewer.username or ''
            row.count_at_ack = int(counts.get(ip, 0))
            row.created_at = now
    db.session.commit()

    return success({'acked': ips, 'ackedAt': now.strftime('%Y-%m-%d %H:%M')})


@bp.route('/meta', methods=['GET'])
@admin_required
def op_log_meta():
    """筛选项：分类与动作的现存值（带计数，供筛选条只展示有数据的项）。

    计数按「全表现存记录」算而非当前筛选结果——筛选条本身是筛选条件的来源，
    不能随筛选结果收缩，否则选中一项后其余项全部消失、无法回退。

    也不加时间窗：项一旦从候选里落下去，用户就再没法按它筛出更早那段时间的记录。

    一次 GROUP BY (action, category) 同时算出两组候选：动作在先，分类随它推导。
    原先分两遍扫全表，而 op_logs 只增不减（保留 365 天），同样的扫描做两遍没有意义。
    按 action 聚拢后由 Python 累加出分类计数，顺带把「同一动作的分类漂移」并成一行
    （若某动作的分类改过值，界面只会看到一个动作，计数是两侧之和）。

    显式 ORDER BY action：不排时 MySQL 的返回顺序随执行计划变，同一份数据在不同版本
    或索引下会排出不同次序，下拉项看起来就是「乱跳」。
    覆盖索引 (action, category)（见 OpLog.__table_args__）：本查询是所有读取口径里唯一
    要扫全表的，有了它按序覆盖扫描即可，不必等「涨到十万行」再处理。
    """
    rows = (db.session.query(OpLog.action, OpLog.category, func.count(OpLog.id))
            .group_by(OpLog.action, OpLog.category)
            .order_by(OpLog.action).all())
    actions, categories = {}, {}
    for action, category, n in rows:
        n = int(n)
        if action:
            actions[action] = actions.get(action, 0) + n
        if category:
            categories[category] = categories.get(category, 0) + n
    return success({
        'actions': [{'value': a, 'count': n} for a, n in actions.items()],
        'categories': [{'value': c, 'count': n} for c, n in categories.items()],
    })
