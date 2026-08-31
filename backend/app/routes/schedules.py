# 定时任务蓝图：账号 × 任务类型的真实调度接口（承接前端从 mock 切换）。
# GET 列表 + 显式 POST 创建（幂等）+ PUT 更新（含开启校验）+ DELETE 删除。
import json

from flask import Blueprint, request
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import BAccount, ConfigSet, PoolLocation, Schedule, SignRecord
from app.schemas.schedule_schema import load_create, load_update
from app.utils.auth import token_required
from app.utils.response import error, success
from app.utils.schedule_utils import compute_next_run
from app.services.scheduler import sync_schedule, remove_job

bp = Blueprint('schedules', __name__, url_prefix='/api/schedules')


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

    # 维护下次执行时间缓存：开启即计算，停用清空
    s.next_run_at = compute_next_run(s) if s.enabled else None
    db.session.commit()
    # 事件钩子：对齐调度器 job 注册（启用→注册/替换，停用→移除）
    sync_schedule(s)
    return success(s.to_dict(), message='保存成功')
