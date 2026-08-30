# 管理员仪表盘聚合：单端点返回全站汇总/趋势/失败归类/额度分桶与预警/高频失败/账号健康/调度器/全局日志。
# 原则：聚合全部 SQL 下推（GROUP BY + 子查询 + LIMIT，命中既有索引），响应体恒定几 KB，
# 用户量增长不影响仪表盘；列表类只出 Top-N，全量明细归属用户管理页。
from datetime import timedelta

from flask import Blueprint, request
from sqlalchemy import case, func

from app.extensions import db
from app.models import BAccount, Schedule, SignRecord, User
from app.models.system_config import get_setting
from app.models.user import now_cst
from app.utils.auth import admin_required
from app.utils.response import success

bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# 失败原因归类：fail_reason 含动态信息（任务 id/距离等），直接 GROUP BY 会碎片化；
# 先按原文聚合 Top 200，再按已知前缀归类合并（顺序即优先级，越具体的越靠前）
_FAIL_CATEGORIES = [
    ('行为验证码', ('行为验证码', 'msg=302')),
    ('围栏拦截', ('围栏拦截',)),
    ('账号校验失败', ('账号校验失败',)),
    ('登录态失效', ('登录态失效', 'token失效', '认证失败')),
    ('缺少签到图片', ('需要上传签到图片', '图库暂无可用图片')),
    ('B 平台拒绝', ('B 平台拒绝',)),
    ('执行异常', ('执行异常',)),
]


def _classify_fail_reason(reason):
    r = reason or ''
    for name, keys in _FAIL_CATEGORIES:
        if any(k in r for k in keys):
            return name
    return '其他'


def _status_counts(base_q):
    """按状态聚合计数：返回 {success, fail, skip, total}"""
    rows = base_q.with_entities(
        SignRecord.status,
        func.count(SignRecord.id),
    ).group_by(SignRecord.status).all()
    counts = {s: n for s, n in rows}
    total = sum(counts.values())
    return {'success': counts.get('success', 0), 'fail': counts.get('fail', 0),
            'skip': counts.get('skip', 0), 'total': total}


def _trend_series(days):
    """近 N 天逐日 success/fail/skip 序列（含今日，缺数据日补零）"""
    today = now_cst().date()
    start = today - timedelta(days=days - 1)
    rows = (SignRecord.query
            .filter(SignRecord.sign_date >= start)
            .with_entities(
                SignRecord.sign_date,
                func.sum(case((SignRecord.status == 'success', 1), else_=0)).label('success'),
                func.sum(case((SignRecord.status == 'fail', 1), else_=0)).label('fail'),
                func.sum(case((SignRecord.status == 'skip', 1), else_=0)).label('skip'),
            )
            .group_by(SignRecord.sign_date).all())
    by_date = {r[0]: {'success': int(r[1] or 0), 'fail': int(r[2] or 0), 'skip': int(r[3] or 0)}
               for r in rows}
    out = []
    cur = start
    for _ in range(days):
        d = cur.strftime('%m-%d')
        c = by_date.get(cur, {})
        out.append({'date': d, 'success': c.get('success', 0),
                    'fail': c.get('fail', 0), 'skip': c.get('skip', 0)})
        cur += timedelta(days=1)
    return out


def _fail_categories():
    """近 30 天失败原因归类分布（原文聚合 Top 200 → 前缀归类合并 → 降序）"""
    start = now_cst().date() - timedelta(days=29)
    rows = (SignRecord.query
            .filter(SignRecord.sign_date >= start, SignRecord.status == 'fail')
            .with_entities(SignRecord.fail_reason, func.count(SignRecord.id))
            .group_by(SignRecord.fail_reason)
            .order_by(func.count(SignRecord.id).desc())
            .limit(200).all())
    merged = {}
    for reason, cnt in rows:
        name = _classify_fail_reason(reason)
        merged[name] = merged.get(name, 0) + int(cnt)
    items = sorted(merged.items(), key=lambda x: x[1], reverse=True)
    return [{'category': k, 'count': v} for k, v in items]


def _quota_overview():
    """额度健康：全站分桶直方图 + 预警用户 Top 20（使用率≥阈值，阈值可在系统设置调整）。
    used 按产品定义恒等于账号数（现算），quota 上限来自 users.quota。"""
    warn_ratio = int(get_setting('quota_warn_ratio') or 80)
    acct = (db.session.query(BAccount.user_id, func.count(BAccount.id).label('cnt'))
            .group_by(BAccount.user_id).subquery())
    rows = (db.session.query(User.id, User.username, User.quota, User.enabled,
                             func.coalesce(acct.c.cnt, 0).label('used'))
            .outerjoin(acct, User.id == acct.c.user_id).all())

    buckets = {'unused': 0, 'lt50': 0, 'r50to79': 0, 'r80to99': 0, 'full': 0}
    warn = []
    for uid, username, quota, enabled, used in rows:
        quota = int(quota or 0)
        used = int(used or 0)
        pct = round(used / quota * 100) if quota > 0 else 100
        if pct >= 100:
            buckets['full'] += 1
        elif pct >= 80:
            buckets['r80to99'] += 1
        elif pct >= 50:
            buckets['r50to79'] += 1
        elif pct > 0:
            buckets['lt50'] += 1
        else:
            buckets['unused'] += 1
        if quota > 0 and pct >= warn_ratio:
            warn.append({'user_id': uid, 'username': username, 'enabled': bool(enabled),
                         'used': used, 'quota': quota, 'pct': pct})
    warn.sort(key=lambda x: (-x['pct'], -(x['quota'] - x['used'])))
    return {'buckets': buckets, 'warnRatio': warn_ratio,
            'warnTotal': len(warn), 'warnUsers': warn[:20]}


def _risk_users(days=7):
    """近 7 天高频失败用户：失败 ≥3 次，或失败率 ≥50% 且总次数 ≥5；按失败次数降序 Top 10"""
    today = now_cst().date()
    start = today - timedelta(days=days - 1)
    agg = (db.session.query(
            SignRecord.user_id,
            func.count(SignRecord.id).label('total'),
            func.sum(case((SignRecord.status == 'fail', 1), else_=0)).label('fails'))
           .filter(SignRecord.sign_date >= start)
           .group_by(SignRecord.user_id).subquery())
    rows = (db.session.query(User.username, agg.c.total, agg.c.fails)
            .join(User, User.id == agg.c.user_id)
            .filter(agg.c.fails >= 3)
            .order_by(agg.c.fails.desc()).limit(10).all())
    out = []
    for username, total, fails in rows:
        total, fails = int(total), int(fails)
        rate = round(fails / total * 100) if total else 0
        risky = fails >= 3 or (total >= 5 and rate >= 50)
        if not risky:
            continue
        out.append({'username': username, 'total': total, 'fails': fails,
                    'rate': rate, 'lastFailReason': ''})
    # 补最近一次失败原因（Top 10 逐条查，量小可接受）
    for item in out:
        u = db.session.query(User.id).filter_by(username=item['username']).first()
        if not u:
            continue
        rec = (SignRecord.query
               .filter(SignRecord.user_id == u.id, SignRecord.status == 'fail')
               .order_by(SignRecord.created_at.desc(), SignRecord.id.desc()).first())
        item['lastFailReason'] = (rec.fail_reason or '') if rec else ''
    return out


def _account_health():
    """账号健康：① 凭证异常（verify_status≠ok，自动签必失败的前兆）；
    ② 疑似漏签（启用中的任务其账号 >3 天无签到记录或从未签到）"""
    today = now_cst().date()
    threshold = today - timedelta(days=3)

    invalid_rows = (BAccount.query
                    .filter(BAccount.verify_status != 'ok')
                    .order_by(BAccount.id.desc()).limit(8).all())
    invalid_list = []
    for a in invalid_rows:
        u = db.session.get(User, a.user_id)
        invalid_list.append({
            'account': a.account,
            'username': u.username if u else '',
            'verifyStatus': a.verify_status,
            'checkedAt': a.verified_at.strftime('%m-%d %H:%M') if a.verified_at else '',
        })

    latest = (db.session.query(SignRecord.account_id, func.max(SignRecord.sign_date).label('last'))
              .group_by(SignRecord.account_id).subquery())
    rows = (db.session.query(Schedule, BAccount, latest.c.last)
            .join(BAccount, Schedule.account_id == BAccount.id)
            .outerjoin(latest, BAccount.id == latest.c.account_id)
            .filter(Schedule.enabled.is_(True), BAccount.enabled.is_(True))
            .all())
    stale = []
    for sched, acc, last in rows:
        if last is None:
            days = None
        else:
            days = (today - last).days
        if days is None or days > 3:
            u = db.session.get(User, acc.user_id)
            stale.append({
                'account': acc.account,
                'username': u.username if u else '',
                'taskType': sched.task_type,
                'lastSign': last.strftime('%m-%d') if last else '',
                'days': days,
            })
    stale.sort(key=lambda x: (x['days'] is not None, x['days'] if x['days'] is not None else 0),
               reverse=True)
    return {
        'invalidCredentials': {'total': len(invalid_list), 'list': invalid_list},
        'staleSign': {'total': len(stale), 'list': stale[:8]},
    }


def _scheduler_info():
    """调度器真实状态：运行标志 / job 总数 / 今日执行次数 / 即将执行 Top 5"""
    from app.services.scheduler import get_scheduler
    today = now_cst().date()
    sched = get_scheduler()
    jobs = sorted((j for j in sched.get_jobs() if str(j.id).startswith('sched_')),
                  key=lambda j: j.next_run_time or None)
    next_runs = []
    for j in jobs[:5]:
        try:
            sid = int(str(j.id).split('_', 1)[1])
        except ValueError:
            continue
        s = db.session.get(Schedule, sid)
        if s is None:
            continue
        acc = db.session.get(BAccount, s.account_id)
        nrt = j.next_run_time.astimezone().strftime('%m-%d %H:%M') if j.next_run_time else ''
        next_runs.append({
            'account': acc.account if acc else '',
            'taskLabel': '寝室签到' if s.task_type == 'dorm' else '活动签到',
            'time': nrt,
        })
    today_runs = SignRecord.query.filter(SignRecord.sign_date == today).count()
    return {'running': bool(sched.running), 'jobCount': len(jobs),
            'todayRuns': today_runs, 'nextRuns': next_runs}


def _recent_logs():
    """全局最新打卡日志：跨全站，支持 type 筛选与用户名模糊筛选，服务端分页（每页 10）"""
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    type_filter = (request.args.get('type') or 'all').strip()
    username = (request.args.get('username') or '').strip()

    q = SignRecord.query
    if type_filter in ('dorm', 'activity'):
        q = q.filter(SignRecord.task_type == type_filter)
    if username:
        like = f'%{username}%'
        q = q.join(User, User.id == SignRecord.user_id).filter(User.username.like(like))

    total = q.count()
    rows = (q.order_by(SignRecord.created_at.desc(), SignRecord.id.desc())
            .offset((page - 1) * 10).limit(10).all())
    items = []
    for r in rows:
        u = db.session.get(User, r.user_id)
        acc = db.session.get(BAccount, r.account_id)
        name = ''
        if acc:
            name = (acc.profile or {}).get('name') or ''
        items.append({
            'id': r.id,
            'time': (r.signed_at or r.created_at).strftime('%m-%d %H:%M') if (r.signed_at or r.created_at) else '',
            'username': u.username if u else '',
            'studentName': name,
            'account': acc.account if acc else '',
            'type': '活动签到' if r.task_type == 'activity' else '寝室签到',
            'status': r.status,
            'failReason': r.fail_reason or '',
        })
    return {'items': items, 'total': total, 'page': page, 'page_size': 10}


@bp.route('/overview', methods=['GET'])
@admin_required
def overview():
    today = now_cst().date()
    users_total = User.query.count()
    accounts_total = BAccount.query.count()
    accounts_enabled = BAccount.query.filter_by(enabled=True).count()
    quota_total = int(db.session.query(func.coalesce(func.sum(User.quota), 0)).scalar() or 0)
    active30 = db.session.query(
        func.count(func.distinct(SignRecord.user_id))
    ).filter(SignRecord.sign_date >= today - timedelta(days=29)).scalar()

    today_q = SignRecord.query.filter(SignRecord.sign_date == today)
    today_stats = _status_counts(today_q)

    trend_30 = _trend_series(30)
    schedule_enabled = Schedule.query.filter_by(enabled=True).count()

    return success({
        'summary': {
            'users': users_total,
            'activeUsers30d': int(active30 or 0),
            'accounts': accounts_total,
            'accountsEnabled': accounts_enabled,
            'quota': {'used': accounts_total, 'total': quota_total,
                      'pct': round(accounts_total / quota_total * 100) if quota_total else 0},
            'today': {'success': today_stats['success'], 'fail': today_stats['fail'],
                      'skip': today_stats['skip'], 'total': today_stats['total']},
        },
        'trend': {'7d': trend_30[-7:], '30d': trend_30},
        'failCategories': _fail_categories(),
        'quota': _quota_overview(),
        'riskUsers': _risk_users(7),
        'accountHealth': _account_health(),
        'scheduler': _scheduler_info(),
        'recentLogs': _recent_logs(),
        'schedulesEnabled': schedule_enabled,
    })
