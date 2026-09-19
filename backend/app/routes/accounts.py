# B 平台账号蓝图：CRUD + 凭据预检 + 重校验 + 记录分页
# 前缀 /api/accounts；资源严格按当前登录用户隔离（user_id 过滤，杜绝越权）
import re
import time

from flask import Blueprint, request
from sqlalchemy.orm import joinedload

from app.events import account_changed
from app.extensions import db
from app.models import BAccount, Schedule, SignRecord, PushLog
from app.models.user import now_cst
from app.schemas.account_schema import load_create, load_update, load_preflight
from app.services.b_platform import get_adapter
from app.services.b_platform.base import BPlatformError
from app.services.b_platform.history import call_with_refresh, fetch_history_tasks, fetch_task_detail
from app.services.scheduler import remove_job
from app.utils.auth import token_required
from app.utils.response import error, success

bp = Blueprint('accounts', __name__, url_prefix='/api/accounts')

# 定时任务不再随账号自动生成；由用户在「定时任务」页显式创建（方案 2：用户可控实例）

# 校验限频（进程内节流）：key → 最近一次 monotonic 时间戳
# 【长期关闭】B 平台无风控（用户确认），间隔设 0 永不节流，不再恢复 60 秒限制
_VERIFY_INTERVAL = 0
_last_verify_at = {}


def _throttled(key):
    now = time.monotonic()
    last = _last_verify_at.get(key)
    _last_verify_at[key] = now
    return last is not None and now - last < _VERIFY_INTERVAL


def _load_owned(account_id):
    """按当前用户过滤加载账号；查无或越权一律视为不存在"""
    return BAccount.query.filter_by(id=account_id, user_id=request.current_user.id).first()


def _run_verify(account, password):
    """调适配器校验；BPlatformError 统一转 HTTP 错误响应"""
    try:
        return get_adapter().verify_and_fetch(account, password), None
    except BPlatformError as e:
        prefix = {'network': 'B 平台网络不可达', 'captcha': '验证码环节失败',
                  'credential': 'B 平台凭证被拒'}.get(e.kind, 'B 平台校验失败')
        return None, error(message=f'{prefix}：{e.message}', code=4301, status=400)


@bp.route('', methods=['GET'])
@token_required
def list_accounts():
    """当前用户的 B 平台账号列表（含平台回填档案与最近签到聚合）"""
    items = (BAccount.query.filter_by(user_id=request.current_user.id)
             .options(joinedload(BAccount.schedules))
             .order_by(BAccount.id.desc()).all())
    return success({'items': [a.to_dict() for a in items], 'total': len(items)})


@bp.route('/preflight', methods=['POST'])
@token_required
def preflight():
    """凭据预检：不落库，实时走 B 平台登录链路，回传 profile 供表单回填预览"""
    payload = request.get_json(silent=True) or {}
    ok, data, msg, code = load_preflight(payload)
    if not ok:
        return error(message=msg, code=code, status=400)
    key = f'{request.current_user.id}:{data["account"]}'
    if _throttled(key):
        return error(message='校验过于频繁，请 1 分钟后再试', code=4290, status=429)
    result, err_resp = _run_verify(data['account'], data['password'])
    if err_resp:
        return err_resp
    return success({'ok': True, 'message': '账号校验通过，可正常对接 B 平台',
                    'profile': result.profile})


@bp.route('', methods=['POST'])
@token_required
def create_account():
    """新增账号：实时校验 → 加密入库 → 占用额度（定时任务由用户显式创建）"""
    payload = request.get_json(silent=True) or {}
    ok, data, msg, code = load_create(payload)
    if not ok:
        return error(message=msg, code=code, status=400)

    user = request.current_user
    if BAccount.query.filter_by(user_id=user.id, account=data['account']).first():
        return error(message='该 B 平台账号已存在', code=4103, status=409)
    # 额度=账号数（产品定义）：已用现算，不再信任存储计数器（历史漂移已不可信）
    if BAccount.query.filter_by(user_id=user.id).count() >= (user.quota or 0):
        return error(message='账号额度已用完，请联系管理员调整', code=4104, status=403)
    if _throttled(f'{user.id}:create:{data["account"]}'):
        return error(message='操作过于频繁，请稍后再试', code=4290, status=429)

    result, err_resp = _run_verify(data['account'], data['password'])
    if err_resp:
        return err_resp

    acc = BAccount(
        user_id=user.id,
        account=data['account'],
        platform='B 打卡平台',
        type=data['type'],
        enabled=data['enabled'],
        bp_uid=result.bp_uid,
        verify_status='ok',
        verified_at=now_cst(),
    )
    acc.set_password(data['password'])
    acc.set_profile(result.profile)
    acc.set_token(result.token)
    if 'pushCreds' in data:
        acc.set_push_creds(data['pushCreds'])
    db.session.add(acc)
    # 额度占用不再维护计数器：展示与校验一律按账号数现算（见 create 的额度校验）
    db.session.commit()
    # 事件钩子：审计在自身事务提交之后发布（record 内独立 commit，不影响业务数据）
    account_changed.send('accounts.create', account=acc)
    return success(acc.to_dict(), message='添加成功', status=201)


@bp.route('/<int:account_id>', methods=['PUT'])
@token_required
def update_account(account_id):
    """编辑账号：改标识或密码会重新走 B 平台校验并刷新 token/profile"""
    acc = _load_owned(account_id)
    if not acc:
        return error(message='账号不存在', code=4040, status=404)

    payload = request.get_json(silent=True) or {}
    ok, data, msg, code = load_update(payload)
    if not ok:
        return error(message=msg, code=code, status=400)

    # 审计 before 快照：受管字段旧值；push_creds 只比对序列化串是否变化，值本身不进日志
    before = {'account': acc.account, 'type': acc.type,
              'enabled': bool(acc.enabled), 'push_creds_json': acc.push_cred_json}

    need_verify = 'password' in data or ('account' in data and data['account'] != acc.account)
    if 'account' in data and data['account'] != acc.account:
        dup = BAccount.query.filter_by(user_id=request.current_user.id, account=data['account']).first()
        if dup:
            return error(message='该 B 平台账号已存在', code=4103, status=409)

    if need_verify:
        target_account = data.get('account', acc.account)
        target_password = data.get('password', acc.get_password())
        result, err_resp = _run_verify(target_account, target_password)
        if err_resp:
            return err_resp
        acc.set_token(result.token)
        acc.set_profile(result.profile)
        acc.bp_uid = result.bp_uid
        acc.verify_status = 'ok'
        acc.verified_at = now_cst()

    if 'account' in data:
        acc.account = data['account']
    if 'password' in data:
        acc.set_password(data['password'])
    if 'type' in data:
        acc.type = data['type']
    if 'enabled' in data:
        acc.enabled = data['enabled']
    if 'pushCreds' in data:
        acc.set_push_creds(data['pushCreds'])

    db.session.commit()
    # 事件钩子：before 供审计还原 from→to；密码不落日志，只记是否变更
    account_changed.send('accounts.update', account=acc, before=before,
                         password_changed='password' in data)
    return success(acc.to_dict(), message='保存成功')


@bp.route('/<int:account_id>', methods=['DELETE'])
@token_required
def delete_account(account_id):
    """删除账号：级联清理定时任务与签到记录，释放额度"""
    acc = _load_owned(account_id)
    if not acc:
        return error(message='账号不存在', code=4040, status=404)

    sched_ids = [s.id for s in Schedule.query.filter_by(account_id=acc.id).all()]
    # 审计快照必须在删除前抓：ORM 行删除后属性不可读；级联计数取各 delete() 的返回行数
    delete_snapshot = {'account_id': acc.id, 'account': acc.account,
                       'cascade': {'schedules': len(sched_ids), 'signRecords': 0, 'pushLogs': 0}}
    # 顺序敏感：sign_records.schedule_id 外键无级联规则，必须先删签到记录再删任务，
    # 否则任务被记录引用，DELETE schedules 触发 MySQL 1451（0.35.0 修过删单任务的同类问题，
    # 此处为删账号级联路径的同源缺陷）。确认弹窗已告知"配置与日志一并移除"，故物理删除。
    # push_logs.sign_record_id 同样无级联规则，随签到记录先行清理，避免孤儿行。
    delete_snapshot['cascade']['pushLogs'] = PushLog.query.filter_by(account_id=acc.id).delete()
    delete_snapshot['cascade']['signRecords'] = SignRecord.query.filter_by(account_id=acc.id).delete()
    delete_snapshot['cascade']['schedules'] = Schedule.query.filter_by(account_id=acc.id).delete()
    # 删除即释放额度：已用额度按账号数现算，无需维护计数器
    db.session.delete(acc)
    db.session.commit()
    # 事件钩子：清理该账号任务在调度器注册的 job（delete 走 ORM 批量删除，
    # 不经过 schedules 路由，故在此显式移除；30s 对账线程作兜底）
    for sid in sched_ids:
        remove_job(sid)
    account_changed.send('accounts.delete', snapshot=delete_snapshot)
    return success(message='删除成功')


@bp.route('/<int:account_id>/verify', methods=['POST'])
@token_required
def reverify_account(account_id):
    """重校验：解密存储密码重登 B 平台，刷新 token/profile；失败置 verify_status='fail'"""
    acc = _load_owned(account_id)
    if not acc:
        return error(message='账号不存在', code=4040, status=404)
    if _throttled(f'{request.current_user.id}:reverify:{acc.id}'):
        return error(message='校验过于频繁，请 1 分钟后再试', code=4290, status=429)

    result, err_resp = _run_verify(acc.account, acc.get_password())
    if err_resp:
        acc.verify_status = 'fail'
        acc.verified_at = now_cst()
        db.session.commit()
        return err_resp

    acc.set_token(result.token)
    acc.set_profile(result.profile)
    acc.bp_uid = result.bp_uid
    acc.verify_status = 'ok'
    acc.verified_at = now_cst()
    db.session.commit()
    return success(acc.to_dict(), message='校验通过')


@bp.route('/<int:account_id>/records', methods=['GET'])
@token_required
def list_records(account_id):
    """指定账号的签到记录分页（一期仅有调度写入的数据；契约对齐细节四期收口）"""
    acc = _load_owned(account_id)
    if not acc:
        return error(message='账号不存在', code=4040, status=404)
    try:
        page = max(1, int(request.args.get('page', 1)))
        page_size = min(100, max(1, int(request.args.get('page_size', 10))))
    except (TypeError, ValueError):
        page, page_size = 1, 10
    type_filter = (request.args.get('type') or '').strip()

    query = SignRecord.query.filter_by(account_id=acc.id)
    if type_filter:
        query = query.filter(SignRecord.task_type == type_filter)
    total = query.count()
    pagination = (query.order_by(SignRecord.sign_date.desc(), SignRecord.id.desc())
                  .paginate(page=page, per_page=page_size, error_out=False))
    items = [{
        'id': r.id,
        'accountId': r.account_id,
        'taskName': r.task_name,
        'type': r.task_type,
        'date': r.sign_date.strftime('%Y-%m-%d') if r.sign_date else '',
        'time': r.signed_at.strftime('%H:%M') if r.signed_at else '',
        'initiator': r.initiator,
        'status': 'signed' if r.status == 'success' else 'unsigned',
        'result': r.status,
        'failReason': r.fail_reason or '',
    } for r in pagination.items]
    return success({'items': items, 'total': total, 'page': page, 'page_size': page_size})


def _call_with_refresh(account, call):
    """兼容别名：实现已抽到 services/b_platform/history.py，与 admin 全站巡检共用。"""
    return call_with_refresh(account, call)


@bp.route('/<int:account_id>/sign-records', methods=['GET'])
@token_required
def list_sign_records(account_id):
    """合并寝/活历史任务（各自取全量后后端排序筛选分页），数据来自 B 平台。

    查询参数：
      type       dorm | activity | all（默认 all）
      status     all | signed | unsigned | needPhoto（默认 all，按平台回传 finished/needPhoto 过滤）
      date_from / date_to  YYYY-MM-DD，任务区间（startDate~endDate）与窗口重叠者入选；
                 日历月视图按 42 格网格窗口取数，列表点选某天时 from=to=当天
      page / page_size    常规分页

    响应：{ items, total, page, page_size, overview, meta }
      overview  全历史口径统计（type+status 过滤、不受日期窗口影响）：total/finished/unsigned/needPhoto/rate
      meta      全历史口径的最早/最晚任务日期（earliest_date/latest_date），驱动日历「最近有数据月份」
    """
    acc = _load_owned(account_id)
    if not acc:
        return error(message='账号不存在', code=4040, status=404)
    try:
        page = max(1, int(request.args.get('page', 1)))
        page_size = min(200, max(1, int(request.args.get('page_size', 10))))
    except (TypeError, ValueError):
        page, page_size = 1, 10
    type_filter = (request.args.get('type') or 'all').strip()
    status_filter = (request.args.get('status') or 'all').strip()
    date_from = (request.args.get('date_from') or '').strip() or None
    date_to = (request.args.get('date_to') or '').strip() or None
    # 日期窗口合法性兜底：非法格式视为未传（避免用户手改 URL 时 500）
    for raw in (date_from, date_to):
        if raw and not re.match(r'^\d{4}-\d{2}-\d{2}$', raw):
            return error(message='date_from/date_to 格式应为 YYYY-MM-DD', code=4304, status=400)
    if status_filter not in ('all', 'signed', 'unsigned', 'needPhoto'):
        return error(message='status 仅支持 all/signed/unsigned/needPhoto', code=4305, status=400)

    # 筛选/统计口径已抽到服务层，与 admin 全站巡检共用同一实现
    result, err = fetch_history_tasks(acc, type_filter, status_filter, date_from, date_to)
    if err:
        return err
    merged, overview, meta = result['merged'], result['overview'], result['meta']
    total = len(merged)
    start = (page - 1) * page_size
    items = merged[start:start + page_size]
    return success({'items': items, 'total': total, 'page': page, 'page_size': page_size,
                    'overview': overview, 'meta': meta})


@bp.route('/<int:account_id>/sign-records/<int:task_id>/detail', methods=['GET'])
@token_required
def sign_record_detail(account_id, task_id):
    """任务地理围栏 + 签到记录列表（listLog）。know/sign 由 kind 区分。"""
    acc = _load_owned(account_id)
    if not acc:
        return error(message='账号不存在', code=4040, status=404)
    kind = (request.args.get('kind') or 'know').strip()
    if kind not in ('know', 'sign'):
        return error(message='未知的任务类型', code=4001, status=400)

    data, err = fetch_task_detail(acc, kind, task_id)
    if err:
        return err
    return success(data)


@bp.route('/<int:account_id>/active-tasks', methods=['GET'])
@token_required
def list_active_tasks(account_id):
    """账号在 B 平台「进行中」（本人未完成）的签到任务：寝室(know) + 活动(sign) 各查一次后合并。

    供签到记录页「正在进行」卡片展示，仅读取、不提交；token 失效经 _call_with_refresh 自动重登重试。
    返回 { items }，item 字段与历史任务统一口径（id/kind/type/taskName/日期/时段/发起人/needPhoto）。
    """
    acc = _load_owned(account_id)
    if not acc:
        return error(message='账号不存在', code=4040, status=404)

    def _fetch(ad, tk):
        items = ad.fetch_active_tasks(tk, 'dorm') + ad.fetch_active_tasks(tk, 'activity')
        items.sort(key=lambda t: (t.get('startDate') or '', t.get('startTime') or ''), reverse=True)
        return {'items': items}

    data, err = _call_with_refresh(acc, _fetch)
    if err:
        return err
    return success(data)
