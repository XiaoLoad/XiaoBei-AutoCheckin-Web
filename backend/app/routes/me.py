# 个人中心聚合蓝图：当前登录用户视角的概览数据（仪表盘数据源）。
# 前缀 /api/me；全部聚合严格按 user_id 隔离，杜绝越权。
from datetime import timedelta

from flask import Blueprint, request

from app.extensions import db
from app.models import BAccount, Schedule, SignRecord, User
from app.models.user import now_cst
from app.utils.auth import token_required
from app.utils.response import success

bp = Blueprint('me', __name__, url_prefix='/api/me')


def _today_local():
    """本地日期（无时区），用于今日/近 N 天聚合的日期窗下界。"""
    return now_cst().date()


def _status_pill(status):
    return {'success': 'success', 'fail': 'fail', 'skip': 'skip'}.get(status, 'skip')


@bp.route('/overview', methods=['GET'])
@token_required
def me_overview():
    """普通用户仪表盘聚合：配额 / 账号 / 任务 / 今日 / 趋势 / 类型分布 / 完成情况 / 最近日志。
    所有查询均以 request.current_user.id 为作用域，与任务日志页口径一致（user 隔离）。"""
    uid = request.current_user.id
    today = _today_local()

    # 配额（users.quota / used_quota）
    user = db.session.get(User, uid)
    quota_limit = user.quota if user else 0
    quota_used = user.used_quota if user else 0
    quota_pct = round(quota_used / quota_limit * 100) if quota_limit else 0

    # 账号（本人 b_accounts）+ 最近签到状态 + 任务类型派生
    accounts = BAccount.query.filter_by(user_id=uid).order_by(BAccount.id.desc()).all()
    account_items = [{
        'id': a.id,
        'account': a.account,
        'type': a.type,
        'platform': a.platform,
        'enabled': bool(a.enabled),
        'lastStatus': a.last_sign_status or 'never',
        'lastSignIn': a.last_sign_at.strftime('%Y-%m-%d %H:%M') if a.last_sign_at else '',
        'signTasks': a.sign_tasks(),
    } for a in accounts]

    # 任务（schedules 计数 / 启用计数）
    schedules = Schedule.query.filter_by(user_id=uid).all()
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
    acc_map = {a.id: a for a in accounts}
    log_items = [{
        'id': r.id,
        'time': (r.signed_at or r.created_at).strftime('%Y-%m-%d %H:%M') if (r.signed_at or r.created_at) else '',
        'account': acc_map.get(r.account_id, {}).account if acc_map.get(r.account_id) else '',
        'type': '寝室打卡' if r.task_type == 'dorm' else '活动签到',
        'result': _status_pill(r.status),
        'note': r.fail_reason or ('已自动完成打卡' if r.status == 'success' else ''),
    } for r in recent_logs]

    return success({
        'quota': {'used': quota_used, 'limit': quota_limit, 'pct': quota_pct},
        'accounts': {'total': len(accounts), 'items': account_items},
        'tasks': {'total': tasks_total, 'active': tasks_active},
        'today': today_stat,
        'trend': trend,
        'typeDist': type_dist,
        'taskSummary': task_summary,
        'recentLogs': log_items,
    })
