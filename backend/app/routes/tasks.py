# 任务日志蓝图：全局跨账号执行日志（sign_records 本地流水）
# 前缀 /api/tasks；严格按当前登录用户隔离（user_id 过滤，杜绝越权）
from flask import Blueprint, request
from sqlalchemy import func

from app.extensions import db
from app.models import BAccount, SignRecord, PushLog
from app.utils.auth import token_required
from app.utils.response import error, success

bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')

# 大表分批删除的批大小：单事务删 N 万行会长时间持行锁并放大 undo 日志，
# 每批 5000 条循环删（带 LIMIT 的子查询删除），锁窗口短、可中途让出
BATCH_SIZE = 5000


def _batched_delete(query, batch_size=BATCH_SIZE):
    """按主键分批执行 DELETE，返回删除总数。
    query 须是已带完整过滤条件的 Query（模型须有 id 主键）；每批只取本批 id
    再按 id 删除，批间独立提交，避免巨型 IN(...) 单事务长时间持锁。"""
    model = query.column_descriptions[0]['entity']
    total = 0
    while True:
        ids = [row[0] for row in query.with_entities(model.id)
               .order_by(model.id).limit(batch_size).all()]
        if not ids:
            break
        total += model.query.filter(model.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
    return total


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
    # 单次 GROUP BY 聚合，替代 4 次独立 .count()（status 维度口径与“统计卡基于口径”一致）
    rows = ov.with_entities(SignRecord.status, func.count(SignRecord.id)).group_by(SignRecord.status).all()
    counts = {s: int(n) for s, n in rows}
    overview = {
        'total': sum(counts.values()),
        'success': counts.get('success', 0),
        'fail': counts.get('fail', 0),
        'skip': counts.get('skip', 0),
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
        # 课程溯源（活动课表窗口轮询命中时记录；寝室/固定策略为空）
        'courseName': r.course_name or '',
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


@bp.route('/logs/<int:rid>/detail', methods=['GET'])
@token_required
def task_log_detail(rid):
    """单条执行日志的「执行配置」详情：优先返回执行时落库的配置快照（历史切片），
    忠实还原该条任务当时实际使用的配置。存量记录（升级前）无快照时返回
    hasSnapshot=false，前端据此显示「无配置快照」。
    pushes 为该次执行各推送通道的落库结果（push_logs），无快照也独立返回。"""
    rec = _owned_record(rid)
    if not rec:
        return error(message='日志不存在或无权查看', code=4406, status=404)
    pushes = (PushLog.query.filter_by(sign_record_id=rec.id)
              .order_by(PushLog.id.asc()).all())
    push_items = [p.to_dict() for p in pushes]
    snap = rec.get_config_snapshot()
    submit_params = rec.get_submit_params()
    if not snap:
        return success({'hasSnapshot': False, 'logId': rec.id,
                        'pushes': push_items, 'submitParams': submit_params})
    return success({'hasSnapshot': True, 'logId': rec.id,
                    'pushes': push_items, 'submitParams': submit_params, **snap})


@bp.route('/logs/<int:rid>', methods=['DELETE'])
@token_required
def delete_task_log(rid):
    """删除单条执行日志（仅本人归属）。"""
    rec = _owned_record(rid)
    if not rec:
        return error(message='日志不存在或无权删除', code=4404, status=404)
    PushLog.query.filter_by(sign_record_id=rec.id).delete(synchronize_session=False)
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

    # 联动清理推送结果改子查询删除（不把日志 id 全量拉进内存），日志本体分批删：
    # 数据量大时单事务巨型 IN(...) 会长时间持行锁，每批 5000 条批间提交
    deleted = _batched_delete(q)
    _batched_delete(PushLog.query.filter(
        PushLog.sign_record_id.in_(
            db.session.query(SignRecord.id).filter(
                SignRecord.account_id.in_(owned_ids),
                SignRecord.created_at < cutoff))))
    return success({'deleted': deleted})
