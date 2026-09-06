# 定时任务蓝图：账号 × 任务类型的真实调度接口（承接前端从 mock 切换）。
# GET 列表 + 显式 POST 创建（幂等）+ PUT 更新（含开启校验）+ DELETE 删除。
import json

from flask import Blueprint, request
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import BAccount, ConfigSet, JwAccount, PoolLocation, PushLog, Schedule, SignRecord
from app.schemas.schedule_schema import load_create, load_update
from app.utils.auth import token_required
from app.utils.response import error, success
from app.utils.schedule_utils import compute_next_run, resolve_activity_cfg
from app.services.scheduler import sync_schedule, remove_job

bp = Blueprint('schedules', __name__, url_prefix='/api/schedules')


def _activity_enable_issue(schedule):
    """活动 course 策略任务的开启前置校验：必须已绑定教务账号。
    needs_attention 允许开启（调度器自动回落每日兜底行为），但未绑定一律拦截。"""
    if resolve_activity_cfg(schedule) is None:
        return None
    if JwAccount.query.filter_by(b_account_id=schedule.account_id).first() is None:
        return '该账号未绑定教务系统，无法按课表调度活动签到（请在签到配置的活动签到节点绑定）'
    return None


@bp.route('', methods=['GET'])
@token_required
def list_schedules():
    """当前用户全部任务实例（账号 × 任务类型），含账号信息与下次执行时间"""
    items = (Schedule.query
             .filter_by(user_id=request.current_user.id)
             .options(joinedload(Schedule.account))
             .order_by(Schedule.account_id, Schedule.task_type).all())
    return success({'items': [s.to_dict() for s in items]})


@bp.route('', methods=['POST'])
@token_required
def create_schedule():
    """显式创建定时任务实例（账号 × 任务类型）；同账号同类型已存在则幂等返回已有"""
    payload = request.get_json(silent=True) or {}
    ok, data, msg, code = load_create(payload)
    if not ok:
        return error(message=msg, code=code, status=400)

    user = request.current_user
    acc = BAccount.query.filter_by(id=data['account_id'], user_id=user.id).first()
    if not acc:
        return error(message='账号不存在', code=4040, status=404)
    if not acc.enabled:
        return error(message='账号未启用，无法创建定时任务', code=4407, status=400)

    existing = Schedule.query.filter_by(
        user_id=user.id, account_id=acc.id, task_type=data['task_type']).first()
    if existing:
        return success(existing.to_dict(), message='该任务已存在')

    s = Schedule(
        user_id=user.id,
        account_id=acc.id,
        task_type=data['task_type'],
        mode='follow',
        enabled=False,
        config_set_id=None,
    )
    db.session.add(s)
    db.session.commit()
    return success(s.to_dict(), message='创建成功', status=201)


@bp.route('/<int:sched_id>', methods=['DELETE'])
@token_required
def delete_schedule(sched_id):
    """删除定时任务实例（校验归属）。删除前解除签到记录的引用：
    sign_records.schedule_id 外键无级联规则，任务执行过即有记录，直接删会被
    MySQL 1451 拦截；置空保留历史（记录内已冗余 task_name/task_type，仍可独立展示）。
    注：模块 D 落地后，删除前需同步移除调度器已注册的 job。"""
    s = Schedule.query.filter_by(id=sched_id, user_id=request.current_user.id).first()
    if not s:
        return error(message='任务不存在', code=4040, status=404)
    SignRecord.query.filter_by(schedule_id=s.id).update({'schedule_id': None})
    # push_logs.schedule_id 外键同样无级联规则：推送日志随签到记录保留历史，仅摘除任务引用
    PushLog.query.filter_by(schedule_id=s.id).update({'schedule_id': None})
    db.session.delete(s)
    db.session.commit()
    # 事件钩子：移除调度器已注册 job（与账号级联删除共用兜底，此处即时清理）
    remove_job(sched_id)
    return success(message='删除成功')


@bp.route('/<int:sched_id>', methods=['PUT'])
@token_required
def update_schedule(sched_id):
    s = Schedule.query.filter_by(id=sched_id, user_id=request.current_user.id).first()
    if not s:
        return error(message='任务不存在', code=4040, status=404)

    payload = request.get_json(silent=True) or {}
    ok, data, msg, code = load_update(payload)
    if not ok:
        return error(message=msg, code=code, status=400)

    if 'mode' in data:
        s.mode = data['mode']
    if 'config' in data:
        # 写入任务自持完整配置：standalone 模式权威来源；并默认与配置套解绑
        s.set_config(data['config'])
        s.mode = 'standalone'
        if 'config_set_id' not in data or data.get('config_set_id') is None:
            s.config_set_id = None
        # 后端兜底：配置引用的位置必须真实存在（防位置池被清空后旧引用仍被放行启用）
        raw_loc = (data['config'] or {}).get('locationId')
        if raw_loc:
            try:
                loc = db.session.get(PoolLocation, int(raw_loc))
            except (TypeError, ValueError):
                loc = None
            if not loc or (not loc.is_system and loc.user_id != request.current_user.id):
                return error(message='所选位置不存在或不可用', code=4403, status=400)
    if 'config_set_id' in data:
        if data['config_set_id'] is not None:
            cs = ConfigSet.query.filter_by(id=data['config_set_id'], user_id=request.current_user.id).first()
            if not cs:
                return error(message='配置套不存在或不可用', code=4400, status=400)
            # 类型校验：寝室套/活动套与任务一一对应，错配会让活动块成为不可消费的死配置
            if cs.task_type != s.task_type:
                label = '活动' if cs.task_type == 'activity' else '寝室'
                return error(message=f'该配置套是{label}签到套，与当前任务类型不符', code=4404, status=400)
        # 套用配置套（带 config + configSetId）时同样写入来源标签；纯绑定（仅 configSetId）走 follow 逻辑
        s.config_set_id = data['config_set_id']
    # 应用配置套即跟随模式：仅传 config_set_id（无 config）时自动置 follow（前端"应用到此任务"只发 configSetId）
    if 'config_set_id' in data and data['config_set_id'] is not None and 'mode' not in data and 'config' not in data:
        s.mode = 'follow'
    if 'custom' in data:
        s.custom_json = json.dumps(data['custom'], ensure_ascii=False)
    if 'overrides' in data:
        s.overrides_json = json.dumps(data['overrides'], ensure_ascii=False) if data['overrides'] else None
    if 'enabled' in data:
        s.enabled = data['enabled']

    # 开启前校验：保证任务有可执行配置，否则拒绝（与前端 4401/4402 呼应）
    if s.enabled:
        if s.mode == 'standalone':
            if not s.has_own_config:
                return error(message='独立任务缺少配置，请先保存配置再启用', code=4401, status=400)
        elif s.mode == 'follow':
            if not s.config_set_id:
                return error(message='跟随配置套模式下开启任务必须先绑定配置套', code=4401, status=400)
            cs = ConfigSet.query.filter_by(id=s.config_set_id, user_id=request.current_user.id).first()
            if not cs:
                return error(message='绑定的配置套不存在或不可用', code=4401, status=400)
        elif s.mode == 'custom':
            cfg = s.custom
            wd = cfg.get('weekdays')
            if not isinstance(wd, list) or not wd:
                return error(message='自定义模式下开启任务必须设置星期', code=4402, status=400)
            if (not isinstance(cfg.get('hour'), int) or not isinstance(cfg.get('minute'), int)
                    or not (0 <= cfg['hour'] <= 23) or not (0 <= cfg['minute'] <= 59)):
                return error(message='自定义模式下开启任务必须设置合法的小时与分钟', code=4402, status=400)
        # 活动 course 策略任务：未绑定教务账号一律拦截（needs_attention 允许开启、自动兜底）
        issue = _activity_enable_issue(s)
        if issue:
            return error(message=issue, code=4403, status=400)

    # 维护下次执行时间缓存：开启即计算，停用清空
    s.next_run_at = compute_next_run(s) if s.enabled else None
    db.session.commit()
    # 事件钩子：对齐调度器 job 注册（启用→注册/替换，停用→移除）
    sync_schedule(s)
    return success(s.to_dict(), message='保存成功')


@bp.route('/batch-manage', methods=['POST'])
@token_required
def batch_manage():
    """批量管理：对一批「账号 × 任务类型」统一开启或关闭调度。

    body: { action: 'enable'|'disable', targets:[{accountId,taskType}], configSetId? }
    - enable：可选 configSetId，给定则先套用配置套（快照写 config_json、mode=standalone、
      config_set_id 退化为来源标签）再开启；不给定则沿用各任务自身现有配置。
      开启前复用与单任务一致的校验（4401/4402），不满足计入 skipped 并给出原因。
    - disable：无需配置，直接关闭；任务实例不存在或本就未启用则计入 skipped。
      关闭后 next_run_at 置空并移除调度 job（与单任务 update_schedule 同语义）。
    返回 {action, affected, skipped, skippedReasons, affectedList}；affectedList 供结果页按账号分组展示。
    """
    payload = request.get_json(silent=True) or {}
    action = payload.get('action') or 'enable'
    if action not in ('enable', 'disable'):
        return error(message='操作类型不合法', code=4400, status=400)

    raw = payload.get('targets')
    if not isinstance(raw, list):
        return error(message='缺少操作目标', code=4401, status=400)

    # 去重 + 过滤非法项（taskType 仅接受两种签到类型）
    seen = set()
    targets = []
    for t in raw:
        if not isinstance(t, dict):
            continue
        acc_id, task_type = t.get('accountId'), t.get('taskType')
        if acc_id is None or task_type not in ('dorm', 'activity'):
            continue
        key = (int(acc_id), task_type)
        if key not in seen:
            seen.add(key)
            targets.append(key)
    if not targets:
        return error(message='缺少有效的操作目标', code=4401, status=400)

    config_set_id = payload.get('configSetId')
    apply_set = None
    if action == 'enable' and config_set_id is not None:
        apply_set = ConfigSet.query.filter_by(id=config_set_id, user_id=request.current_user.id).first()
        if not apply_set:
            return error(message='配置套不存在或不可用', code=4400, status=400)
    user = request.current_user
    affected = skipped_count = 0
    skipped_reasons = []
    affected_list = []
    task_label = {'dorm': '寝室签到', 'activity': '活动签到'}

    # 跳过项统一登记：保证 skipped 计数与明细不会因分支增多而漏计/重复
    def skip(acc_id, task_type, name, reason):
        nonlocal skipped_count
        skipped_count += 1
        skipped_reasons.append({
            'accountId': acc_id, 'taskType': task_type,
            'accountName': name, 'taskLabel': task_label[task_type],
            'reason': reason,
        })

    def succeed(acc_id, task_type, name):
        nonlocal affected
        affected += 1
        affected_list.append({
            'accountId': acc_id, 'taskType': task_type,
            'accountName': name, 'taskLabel': task_label[task_type],
        })

    for acc_id, task_type in targets:
        acc = BAccount.query.filter_by(id=acc_id, user_id=user.id).first()
        if not acc:
            skip(acc_id, task_type, f'账号{acc_id}', '账号不存在')
            continue
        # 启用要求账号本身启用；关闭不受此限（账号停用也可显式关闭其任务）
        if action == 'enable' and not acc.enabled:
            skip(acc_id, task_type, acc.profile.get('name') or acc.account, '账号未启用')
            continue

        name = acc.profile.get('name') or acc.account
        sc = Schedule.query.filter_by(user_id=user.id, account_id=acc.id, task_type=task_type).first()

        # ── 关闭：无需配置，未启用或无实例即跳过 ──
        if action == 'disable':
            if not sc or not sc.enabled:
                skip(acc_id, task_type, name, '任务未启用，无需关闭')
                continue
            sc.enabled = False
            sc.next_run_at = None
            sync_schedule(sc)
            succeed(acc_id, task_type, name)
            continue

        # ── 启用：可选套用配置套 ──
        # 类型校验：所选统一配置套必须与任务类型一致（寝室套/活动套一一对应）
        if action == 'enable' and apply_set is not None and apply_set.task_type != task_type:
            set_label = '活动' if apply_set.task_type == 'activity' else '寝室'
            skip(acc_id, task_type, name,
                 f'所选配置套是{set_label}签到套，与该任务类型不符')
            continue
        if apply_set:
            if sc:
                sc.set_config(apply_set.config)
                sc.mode = 'standalone'
                sc.config_set_id = apply_set.id
            else:
                sc = Schedule(user_id=user.id, account_id=acc.id, task_type=task_type,
                              mode='standalone', enabled=False, config_set_id=apply_set.id)
                sc.set_config(apply_set.config)
                db.session.add(sc)
                # 新建实例尚未 flush，sc.id 为 None；sync_schedule 注册 job 依赖 schedule.id，
                # 须先 flush 拿到真实主键，否则 job 注册成 sched_None 且 run_schedule 回查不到。
                db.session.flush()

        if not sc:
            skip(acc_id, task_type, name, '任务实例不存在且未选配置套，无法启用（请先在签到配置中配置该任务）')
            continue

        # 开启前校验（与 update_schedule 的 4401/4402 呼应）
        reason = None
        if sc.mode == 'standalone':
            if not sc.has_own_config:
                reason = '本任务缺少配置，请先完善配置再启用'
        elif sc.mode == 'follow':
            if not sc.config_set_id:
                reason = '请先绑定配置套再启用'
            else:
                cs = ConfigSet.query.filter_by(id=sc.config_set_id, user_id=user.id).first()
                if not cs:
                    reason = '绑定的配置套不存在或不可用'
        elif sc.mode == 'custom':
            cfg = sc.custom or {}
            if not isinstance(cfg.get('weekdays'), list) or not cfg['weekdays']:
                reason = '自定义模式下必须设置执行星期'
            elif (not isinstance(cfg.get('hour'), int) or not isinstance(cfg.get('minute'), int)
                  or not (0 <= cfg['hour'] <= 23) or not (0 <= cfg['minute'] <= 59)):
                reason = '自定义模式下必须设置合法的小时与分钟'
        if reason is None:
            reason = _activity_enable_issue(sc)

        if reason:
            skip(acc_id, task_type, name, reason)
            continue

        sc.enabled = True
        sc.next_run_at = compute_next_run(sc)
        sync_schedule(sc)
        succeed(acc_id, task_type, name)

    db.session.commit()

    verb = '启用' if action == 'enable' else '关闭'
    msg = f'已{verb} {affected} 个账号任务'
    if skipped_count:
        msg += f'，跳过 {skipped_count} 个'
    return success(
        {'action': action, 'affected': affected, 'skipped': skipped_count,
         'skippedReasons': skipped_reasons, 'affectedList': affected_list},
        message=msg,
    )
