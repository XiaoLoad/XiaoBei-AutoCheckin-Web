# 任务日志蓝图：全局跨账号执行日志（sign_records 本地流水）
# 前缀 /api/tasks；严格按当前登录用户隔离（user_id 过滤，杜绝越权）
from flask import Blueprint, request

from app.models import BAccount, SignRecord
from app.utils.auth import token_required
from app.utils.response import error, success

bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')


def _owned_accounts():
    """当前用户全部 B 平台账号（按 id 倒序）"""
    return BAccount.query.filter_by(user_id=request.current_user.id).order_by(BAccount.id.desc()).all()


def _profile_of(account):
    p = account.profile or {}
    return {
        'accountName': account.account,
        'studentName': p.get('name') or '',
        'college': p.get('college') or '',
        'major': p.get('major') or '',
        'className': p.get('className') or '',
        'studentNo': p.get('studentNo') or '',
    }


def _parse_int(v, default):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


@bp.route('/logs', methods=['GET'])
@token_required
def task_logs():
    """全局跨账号执行日志（sign_records）。平铺、按执行时间倒序；
    概览统计基于账号+类型口径（不含状态筛选），与「统计卡基于口径」约定一致。"""
    page = max(1, _parse_int(request.args.get('page', 1), 1))
    page_size = min(100, max(1, _parse_int(request.args.get('page_size', 10), 10)))
    account_filter = (request.args.get('accountId') or '').strip()
    type_filter = (request.args.get('type') or '').strip()
    status_filter = (request.args.get('status') or 'all').strip()

    accounts = _owned_accounts()
    prof = {a.id: _profile_of(a) for a in accounts}
    owned_ids = [a.id for a in accounts]

    def scoped():
        return SignRecord.query.filter(
            SignRecord.account_id.in_(owned_ids) if owned_ids else SignRecord.account_id.in_([])
        )

    base = scoped()
    if account_filter:
        try:
            aid = int(account_filter)
            if aid in owned_ids:
                base = base.filter(SignRecord.account_id == aid)
            else:
                base = SignRecord.query.filter(SignRecord.account_id.in_([]))
        except ValueError:
            base = SignRecord.query.filter(SignRecord.account_id.in_([]))
    if type_filter and type_filter != 'all':
        base = base.filter(SignRecord.task_type == type_filter)
    if status_filter in ('success', 'fail', 'skip'):
        base = base.filter(SignRecord.status == status_filter)

    total = base.count()

    # 概览：仅叠加账号+类型筛选（不含状态），与「统计卡基于口径」约定一致
    ov = scoped()
    if account_filter:
        try:
            aid = int(account_filter)
            if aid in owned_ids:
                ov = ov.filter(SignRecord.account_id == aid)
        except ValueError:
            ov = ov.filter(SignRecord.account_id.in_([]))
    if type_filter and type_filter != 'all':
        ov = ov.filter(SignRecord.task_type == type_filter)
    overview = {
        'total': ov.count(),
        'success': ov.filter(SignRecord.status == 'success').count(),
        'fail': ov.filter(SignRecord.status == 'fail').count(),
        'skip': ov.filter(SignRecord.status == 'skip').count(),
    }

    pagination = base.order_by(SignRecord.created_at.desc(), SignRecord.id.desc()).paginate(
        page=page, per_page=page_size, error_out=False
    )
    items = [{
        'id': r.id,
        'accountId': r.account_id,
        'accountName': prof.get(r.account_id, {}).get('accountName', ''),
        'studentName': prof.get(r.account_id, {}).get('studentName', ''),
        'college': prof.get(r.account_id, {}).get('college', ''),
        'major': prof.get(r.account_id, {}).get('major', ''),
        'className': prof.get(r.account_id, {}).get('className', ''),
        'studentNo': prof.get(r.account_id, {}).get('studentNo', ''),
        'taskName': r.task_name or '',
        'taskType': r.task_type or '',
        'taskLabel': '寝室签到' if r.task_type == 'dorm' else '活动签到',
        'signDate': r.sign_date.strftime('%Y-%m-%d') if r.sign_date else '',
        'signedAt': r.signed_at.strftime('%Y-%m-%d %H:%M:%S') if r.signed_at else '',
        'createdAt': r.created_at.strftime('%Y-%m-%d %H:%M:%S') if r.created_at else '',
        'status': r.status,
        'failReason': r.fail_reason or '',
        'initiator': r.initiator or 'system',
    } for r in pagination.items]
    return success({'items': items, 'total': total, 'page': page, 'page_size': page_size, 'overview': overview})


def _owned_record(rid):
    """取出当前用户归属的执行日志；非本人或无记录返回 None（调用方判 404）。"""
    owned_ids = [a.id for a in _owned_accounts()]
    if not owned_ids:
        return None
    rec = SignRecord.query.filter(
        SignRecord.account_id.in_(owned_ids) if owned_ids else SignRecord.account_id.in_([])
    ).filter(SignRecord.id == rid).first()
    return rec


@bp.route('/logs/<int:rid>', methods=['DELETE'])
@token_required
def delete_task_log(rid):
    """删除单条执行日志（仅本人归属）。"""
    rec = _owned_record(rid)
    if not rec:
        return error(message='日志不存在或无权删除', code=4404, status=404)
    db.session.delete(rec)
    db.session.commit()
    return success(message='已删除')


@bp.route('/logs', methods=['DELETE'])
@token_required
def purge_task_logs():
    """批量删除本人执行日志：必须带 before（YYYY-MM-DD），清理该日期之前的全部记录。
    无 before 直接拒绝，避免误清空全部历史。accountId/type/status 可选叠加过滤（仍限本人）。"""
    before = (request.args.get('before') or '').strip()
    if not before:
        return error(message='批量删除必须指定 before（YYYY-MM-DD）日期上限', code=4405, status=400)

    from datetime import datetime
    try:
        cutoff = datetime.strptime(before, '%Y-%m-%d')
    except ValueError:
        return error(message='before 格式应为 YYYY-MM-DD', code=4405, status=400)

    accounts = _owned_accounts()
    owned_ids = [a.id for a in accounts]
    if not owned_ids:
        return success({'deleted': 0})

    q = SignRecord.query.filter(SignRecord.account_id.in_(owned_ids))
    q = q.filter(SignRecord.created_at < cutoff)
    account_filter = (request.args.get('accountId') or '').strip()
    if account_filter:
        try:
            aid = int(account_filter)
            if aid in owned_ids:
                q = q.filter(SignRecord.account_id == aid)
        except ValueError:
            pass
    type_filter = (request.args.get('type') or '').strip()
    if type_filter and type_filter != 'all':
        q = q.filter(SignRecord.task_type == type_filter)
    status_filter = (request.args.get('status') or '').strip()
    if status_filter in ('success', 'fail', 'skip'):
        q = q.filter(SignRecord.status == status_filter)

    deleted = q.delete()
    db.session.commit()
    return success({'deleted': deleted})
