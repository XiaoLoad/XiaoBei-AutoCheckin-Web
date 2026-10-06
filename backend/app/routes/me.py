# 个人中心聚合蓝图：当前登录用户视角的概览数据（仪表盘数据源）。
# 前缀 /api/me；全部聚合严格按 user_id 隔离，杜绝越权。
from datetime import datetime, timedelta

from flask import Blueprint, request
from sqlalchemy import case, func

from app.extensions import db
from app.models import BAccount, PushLog, Schedule, SignRecord, User
from app.models.user import now_cst
from app.utils.auth import token_required
from app.utils.response import success

bp = Blueprint('me', __name__, url_prefix='/api/me')

# 概览里「展示用」的账号列表上限。账号数受 users.quota 约束，正常远小于此值，
# 上限只用于兜住异常数据（脚本批量建号、额度误配），避免单次响应与前端卡片渲染被撑爆。
# 统计口径（额度占用、我的 B 账号数）不受它影响——那两处一律现算 count，见 overview。
ACCOUNT_LIST_LIMIT = 200


def _today_local():
    """本地日期（无时区），用于今日/近 N 天聚合的日期窗下界。"""
    return now_cst().date()


def _status_pill(status):
    return {'success': 'success', 'fail': 'fail', 'skip': 'skip'}.get(status, 'skip')


def _ago_text(dt):
    """距今多久的粗粒度中文描述（None → 空串）。与 routes/admin.py 同口径。"""
    if dt is None:
        return ''
    mins = int((now_cst() - dt).total_seconds() // 60)
    if mins < 1:
        return '刚刚'
    if mins < 60:
        return f'{mins} 分钟前'
    if mins < 1440:
        return f'{mins // 60} 小时前'
    return f'{mins // 1440} 天前'


@bp.route('/account-info', methods=['GET'])
@token_required
def me_account_info():
    """个人设置页「账户信息」只读卡：身份体征（注册/最近登录）与额度体征。
    额度口径与仪表盘一致：上限取 users.quota，已用恒等于平台账号数现算，不读 used_quota 计数器。"""
    u = request.current_user
    used = BAccount.query.filter_by(user_id=u.id).count()
    limit = u.quota or 0
    pct = round(used / limit * 100) if limit else 0
    return success(
        {
            'userId': u.id,
            'username': u.username,
            'role': u.role,
            'createdAt': u.created_at.strftime('%Y-%m-%d %H:%M') if u.created_at else '',
            'lastLogin': u.last_login.strftime('%Y-%m-%d %H:%M') if u.last_login else '',
            'quota': {'used': used, 'limit': limit, 'pct': pct},
        }
    )


def _my_scheduler_info(uid):
    """调度器视角的「我的任务」状态（对齐 routes/admin.py::_scheduler_info 的字段口径，
    但数据范围严格限本人：jobCount/nextRuns/lastRun 只统计本人 schedule 的 job）。

    与管理员侧的差异：调度器是全站单例，「running」是服务级状态（调度器线程活着），
    对普通用户同样有意义（它决定我的任务会不会被执行），故保留展示；任务计数、
    即将执行的窗口与最近执行时刻则一律过滤出本人任务，他人任务不可见。"""
    from app.services.scheduler import get_scheduler

    my_ids = {s.id for s in Schedule.query.filter_by(user_id=uid).all()}
    sched = get_scheduler()
    jobs = sorted((j for j in sched.get_jobs() if str(j.id).startswith('sched_')),
                  key=lambda j: j.next_run_time or None)

    # 即将执行的窗口：只取本人任务的 job，按 next_run_time 升序最多 5 条。
    # 附带账号与任务类型——普通用户多账号时，只看时刻无法知道要签哪个号。
    next_runs = []
    for j in jobs:
        if len(next_runs) >= 5:
            break
        try:
            sid = int(str(j.id).split('_', 1)[1])
        except ValueError:
            continue
        if sid not in my_ids:
            continue
        s = db.session.get(Schedule, sid)
        acc = db.session.get(BAccount, s.account_id)
        nrt = j.next_run_time.astimezone() if j.next_run_time else None
        # 距执行的分钟数：按请求时刻现算，前端按 <1h / <24h / ≥24h 分档展示
        in_minutes = max(0, int((nrt - datetime.now(nrt.tzinfo)).total_seconds() // 60)) if nrt else None
        next_runs.append({
            'account': acc.account if acc else '',
            'studentName': ((acc.profile or {}).get('name') or '') if acc else '',
            'taskLabel': '寝室签到' if s.task_type == 'dorm' else '活动签到',
            'time': nrt.strftime('%m-%d %H:%M') if nrt else '',
            'inMinutes': in_minutes,
        })

    my_jobs = [j for j in jobs
               if str(j.id).startswith('sched_')
               and str(j.id).split('_', 1)[-1].isdigit()
               and int(str(j.id).split('_', 1)[1]) in my_ids]
    my_enabled = Schedule.query.filter_by(user_id=uid, enabled=True).all()
    type_counts = {}
    for s in my_enabled:
        type_counts[s.task_type] = type_counts.get(s.task_type, 0) + 1
    # 未注册 cron 的启用任务 = 活动 course 策略且关闭每日兜底（执行完全由课表窗口轮询
    # 接管，不注册 job）。判定走 resolve_activity_cfg 权威口径，与调度器注册逻辑同源。
    from app.utils.schedule_utils import resolve_activity_cfg
    unregistered = sum(1 for s in my_enabled
                       if resolve_activity_cfg(s) is not None
                       and not resolve_activity_cfg(s)['fallbackEnabled'])

    last_run = (db.session.query(func.max(SignRecord.created_at))
                .filter(SignRecord.user_id == uid).scalar())
    next_in = None
    if my_jobs and my_jobs[0].next_run_time:
        nrt = my_jobs[0].next_run_time
        next_in = max(0, int((nrt - datetime.now(nrt.tzinfo)).total_seconds() // 60))

    return {
        'running': bool(sched.running),
        'jobCount': len(my_jobs),
        'unregistered': unregistered,
        'taskTypes': {'dorm': type_counts.get('dorm', 0),
                      'activity': type_counts.get('activity', 0)},
        # 累计执行次数：本人全部任务的 run_count 求和（含停用任务的历史贡献）
        'runTotal': int(db.session.query(func.coalesce(func.sum(Schedule.run_count), 0))
                        .filter(Schedule.user_id == uid).scalar() or 0),
        'lastRunAt': last_run.strftime('%m-%d %H:%M') if last_run else '',
        'lastRunAgo': _ago_text(last_run),
        'nextRunIn': next_in,
        'nextRuns': next_runs,
    }


def _my_push_health(uid, days=7):
    """本人推送送达统计（近 N 天）：口径对齐 routes/admin.py::_push_health——
    成功率分母只含真实发送（attempts>0），未发送（未配凭证等）单列不计入分母。"""
    start = now_cst() - timedelta(days=days)
    sent_sum = func.sum(case((PushLog.attempts > 0, 1), else_=0))
    ok_sum = func.sum(case((PushLog.ok.is_(True), 1), else_=0))
    skip_sum = func.sum(case((PushLog.attempts == 0, 1), else_=0))
    rows = (db.session.query(PushLog.channel, sent_sum, ok_sum, skip_sum)
            .filter(PushLog.user_id == uid, PushLog.created_at >= start)
            .group_by(PushLog.channel).all())
    by_channel = []
    tot = {'sent': 0, 'ok': 0, 'skipped': 0}
    for ch, sent, ok, skipped in rows:
        sent, ok, skipped = int(sent or 0), int(ok or 0), int(skipped or 0)
        by_channel.append({
            'channel': ch, 'sent': sent, 'ok': ok, 'fail': sent - ok, 'skipped': skipped,
            'rate': round(ok / sent * 100) if sent else None,
        })
        tot['sent'] += sent
        tot['ok'] += ok
        tot['skipped'] += skipped
    # 真实失败多的在前（与管理员侧同排序语义）
    by_channel.sort(key=lambda x: (-x['fail'], -x['sent']))

    # 签到成功但通知未送达的最近明细（最多 5 条）：这是普通用户最该关心的异常。
    cross = (db.session.query(PushLog)
             .join(SignRecord, PushLog.sign_record_id == SignRecord.id)
             .filter(PushLog.user_id == uid, PushLog.created_at >= start,
                     PushLog.ok.is_(False), SignRecord.status == 'success')
             .order_by(PushLog.attempts.desc(), PushLog.created_at.desc(),
                       PushLog.id.desc())
             .limit(5).all())
    acc_ids = {p.account_id for p in cross if p.account_id}
    accs = ({a.id: a for a in BAccount.query.filter(BAccount.id.in_(acc_ids)).all()}
            if acc_ids else {})
    cross_items = [{
        'account': (accs.get(p.account_id).account if accs.get(p.account_id) else ''),
        'channel': p.channel,
        'error': (p.error or '')[:120],
        'skipped': int(p.attempts or 0) == 0,
        'time': p.created_at.strftime('%m-%d %H:%M') if p.created_at else '',
    } for p in cross]

    return {
        'days': days,
        'summary': {'sent': tot['sent'], 'ok': tot['ok'], 'fail': tot['sent'] - tot['ok'],
                    'skipped': tot['skipped'],
                    'rate': round(tot['ok'] / tot['sent'] * 100) if tot['sent'] else None,
                    'channels': len([c for c in by_channel if c['sent'] > 0])},
        'byChannel': by_channel,
        'signOkPushFail': {'total': len(cross_items), 'list': cross_items},
    }


@bp.route('/overview', methods=['GET'])
@token_required
def me_overview():
    """普通用户仪表盘聚合：配额 / 账号 / 任务 / 今日 / 趋势 / 类型分布 / 完成情况 /
    最近日志 / 我的调度状态 / 我的推送送达。
    所有查询均以 request.current_user.id 为作用域，与任务日志页口径一致（user 隔离）。"""
    uid = request.current_user.id
    today = _today_local()

    # 任务（schedules）：一次拉全后内存按账号分组，供资格判定与 sign_tasks 派生复用，
    # 避免每账号各查一遍 Schedule（sign_tasks 内部还会再查一次）造成 3N+ 查询
    schedules = Schedule.query.filter_by(user_id=uid).all()
    scheds_by_account = {}
    for s in schedules:
        scheds_by_account.setdefault(s.account_id, []).append(s)

    # 账号（本人 b_accounts）；仪表盘仅展示「已启用定时任务且配置了配置套」的账号，
    # 并派生类型标签（寝室/活动/通用）+ 平台档案（姓名/学院/专业/班级）。
    # 统计口径与展示列表解耦：额度占用恒等于账号数、必须是精确值，故单独 count，
    # 不能拿下面这个带 ACCOUNT_LIST_LIMIT 的列表取长度。
    account_total = BAccount.query.filter_by(user_id=uid).count()
    accounts = (
        BAccount.query.filter_by(user_id=uid)
        .order_by(BAccount.id.desc())
        .limit(ACCOUNT_LIST_LIMIT)
        .all()
    )

    # 配额（users.quota 为上限；已用额度按产品定义恒等于平台账号数——
    # 存储 used_quota 计数器已被历史操作污染出漂移，展示与校验一律现算账号数）
    user = db.session.get(User, uid)
    quota_limit = user.quota if user else 0
    quota_used = account_total
    quota_pct = round(quota_used / quota_limit * 100) if quota_limit else 0

    def _sign_tasks_of(acc_id):
        """该账号已添加定时任务的签到类型及启用态（对齐 BAccount.sign_tasks 口径，
        但吃内存分组数据，不再逐账号回查）。"""
        rows = scheds_by_account.get(acc_id, [])
        out = []
        for t in ('dorm', 'activity'):
            s = next((x for x in rows if x.task_type == t), None)
            out.append({
                'type': t,
                'enabled': bool(s.enabled) if s else False,
                'exists': s is not None,
                'configSetId': s.config_set_id if (s and s.config_set_id is not None) else None,
            })
        return out

    def _account_qualifies(acc_id):
        """账号是否「启用了定时任务且配置了配置套」（follow 引用配置套或 standalone 自持配置）。"""
        for s in scheds_by_account.get(acc_id, []):
            if s.enabled and (s.config_set_id is not None or s.has_own_config):
                return True
        return False

    def _type_code(sign_tasks):
        """按启用态派生类型码：两类都启用→general，仅其一→该类型，皆未启用→none。

        展示文案已归到前端 utils/accountType.js（与账号树/记录页/账号管理页同源），
        中文 type 仅为兼容既有消费方保留。
        """
        dorm_on = any(t['type'] == 'dorm' and t['enabled'] for t in sign_tasks)
        act_on = any(t['type'] == 'activity' and t['enabled'] for t in sign_tasks)
        if dorm_on and act_on:
            return 'general'
        if dorm_on:
            return 'dorm'
        if act_on:
            return 'activity'
        return 'none'

    # 历史中文取值，由类型码派生，避免两个字段各自判定后漂移
    type_labels = {'general': '通用', 'dorm': '寝室', 'activity': '活动', 'none': '未配置'}

    account_items = []
    for a in accounts:
        if not _account_qualifies(a.id):
            continue
        p = a.profile
        st = _sign_tasks_of(a.id)
        code = _type_code(st)
        account_items.append({
            'id': a.id,
            'account': a.account,
            'name': p.get('name') or '',
            'college': p.get('college') or '',
            'major': p.get('major') or '',
            'className': p.get('className') or '',
            'type': type_labels[code],
            'typeCode': code,
            'platform': a.platform,
            'enabled': bool(a.enabled),
            'lastStatus': a.last_sign_status or 'never',
            'lastSignIn': a.last_sign_at.strftime('%Y-%m-%d %H:%M') if a.last_sign_at else '',
            'signTasks': st,
        })
    # 最近打卡时间倒序（无时间排末尾），让「最近活跃」的账号靠前
    account_items.sort(key=lambda x: x['lastSignIn'] or '0000', reverse=True)

    # 任务计数（复用已拉取的全量列表）
    tasks_total = len(schedules)
    tasks_active = sum(1 for s in schedules if s.enabled)

    # 今日打卡（sign_date = 今日，本地）
    today_records = SignRecord.query.filter_by(user_id=uid, sign_date=today).all()
    today_stat = {
        'total': len(today_records),
        'success': sum(1 for r in today_records if r.status == 'success'),
        'fail': sum(1 for r in today_records if r.status == 'fail'),
        'skip': sum(1 for r in today_records if r.status == 'skip'),
    }

    # 近 30 天窗（含今日）
    cutoff_30 = today - timedelta(days=29)
    recent = SignRecord.query.filter(
        SignRecord.user_id == uid,
        SignRecord.sign_date >= cutoff_30,
    ).all()

    # 趋势：按 sign_date 聚合（7d / 30d）
    def trend_series(days):
        lo = today - timedelta(days=days - 1)
        buckets = {}
        for r in recent:
            if r.sign_date < lo:
                continue
            d = r.sign_date
            b = buckets.setdefault(d, {'success': 0, 'fail': 0, 'skip': 0})
            b[_status_pill(r.status)] += 1
        arr = []
        cur = lo
        for _ in range(days):
            b = buckets.get(cur, {'success': 0, 'fail': 0, 'skip': 0})
            arr.append({
                'date': cur.strftime('%Y-%m-%d'),
                'success': b['success'],
                'fail': b['fail'],
                'skip': b['skip'],
            })
            cur += timedelta(days=1)
        return arr

    trend = {'7d': trend_series(7), '30d': trend_series(30)}

    # 类型分布（近 30 天按 task_type 计数）
    type_dist = {'dorm': 0, 'activity': 0}
    for r in recent:
        if r.task_type in type_dist:
            type_dist[r.task_type] += 1

    # 完成情况（近 30 天按 status 计数）
    task_summary = {
        'success': sum(1 for r in recent if r.status == 'success'),
        'fail': sum(1 for r in recent if r.status == 'fail'),
        'skip': sum(1 for r in recent if r.status == 'skip'),
    }

    # 最近日志（最新 8 条，按执行时间倒序）
    recent_logs = (
        SignRecord.query.filter_by(user_id=uid)
        .order_by(SignRecord.created_at.desc(), SignRecord.id.desc())
        .limit(8)
        .all()
    )
    # 日志行的账号名按日志实际涉及的账号回查，不复用上方那个受 ACCOUNT_LIST_LIMIT
    # 约束的列表——否则账号数超上限时，排在上限之外的老账号会让整行丢掉姓名与班级。
    log_acc_ids = {r.account_id for r in recent_logs if r.account_id is not None}
    acc_map = (
        {a.id: a for a in BAccount.query.filter(BAccount.id.in_(log_acc_ids)).all()}
        if log_acc_ids else {}
    )
    log_items = []
    for r in recent_logs:
        acc = acc_map.get(r.account_id)
        prof = acc.profile if acc else {}
        log_items.append({
            'id': r.id,
            'accountId': r.account_id,
            'time': (r.signed_at or r.created_at).strftime('%Y-%m-%d %H:%M') if (r.signed_at or r.created_at) else '',
            'name': prof.get('name') or '',
            'account': acc.account if acc else '',
            'college': prof.get('college') or '',
            'className': prof.get('className') or '',
            'type': '寝室签到' if r.task_type == 'dorm' else '活动签到',
            'taskType': r.task_type,
            'result': _status_pill(r.status),
            'note': r.fail_reason or ('已自动完成打卡' if r.status == 'success' else ''),
        })

    return success({
        'quota': {'used': quota_used, 'limit': quota_limit, 'pct': quota_pct},
        'accounts': {'total': account_total, 'items': account_items},
        'tasks': {'total': tasks_total, 'active': tasks_active},
        'today': today_stat,
        'trend': trend,
        'typeDist': type_dist,
        'taskSummary': task_summary,
        'recentLogs': log_items,
        'scheduler': _my_scheduler_info(uid),
        'pushHealth': _my_push_health(uid, 7),
    })
