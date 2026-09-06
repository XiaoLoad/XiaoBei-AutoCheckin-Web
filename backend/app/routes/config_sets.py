# 配置套蓝图：用户级签到配置预设。默认套随三期调度解析一同落地（见计划差异决策 3）。
from flask import Blueprint, request

from app.extensions import db
from app.models import BAccount, ConfigSet, PoolLocation, Schedule
from app.schemas.config_schema import load_create, load_update
from app.utils.auth import token_required
from app.utils.response import error, success

bp = Blueprint('config_sets', __name__, url_prefix='/api/config-sets')


def _resolve_location(user, raw_cfg):
    """提取配置体 locationId 并校验可见性（系统位置或本人私有）→ (列值, err_resp)"""
    loc_id = raw_cfg.get('locationId')
    if not loc_id:
        return None, None
    loc = db.session.get(PoolLocation, loc_id)
    if not loc or (not loc.is_system and loc.user_id != user.id):
        return None, error(message='所选位置不存在或不可用', code=4203, status=400)
    return loc.id, None


@bp.route('', methods=['GET'])
@token_required
def list_sets():
    items = (ConfigSet.query.filter_by(user_id=request.current_user.id)
             .order_by(ConfigSet.id.asc()).all())
    return success({'items': [s.to_dict() for s in items]})


@bp.route('', methods=['POST'])
@token_required
def create_set():
    payload = request.get_json(silent=True) or {}
    ok, data, msg, code = load_create(payload)
    if not ok:
        return error(message=msg, code=code, status=400)
    location_id, err = _resolve_location(request.current_user, data['config'])
    if err:
        return err
    s = ConfigSet(user_id=request.current_user.id, name=data['name'],
                  task_type=data['task_type'],
                  location_id=location_id, is_default=False)
    s.set_config(data['config'])
    db.session.add(s)
    if data.get('is_default'):
        db.session.flush()  # 先取 s.id 供唯一性约束使用
        s.is_default = True
        ConfigSet.enforce_single_default(request.current_user.id, s.id, task_type=s.task_type)
    db.session.commit()
    return success(s.to_dict(), message='创建成功', status=201)


@bp.route('/<int:set_id>', methods=['PUT'])
@token_required
def update_set(set_id):
    s = ConfigSet.query.filter_by(id=set_id, user_id=request.current_user.id).first()
    if not s:
        return error(message='配置套不存在', code=4040, status=404)
    payload = request.get_json(silent=True) or {}
    ok, data, msg, code = load_update(payload)
    if not ok:
        return error(message=msg, code=code, status=400)
    if 'name' in data:
        s.name = data['name']
    if 'config' in data:
        location_id, err = _resolve_location(request.current_user, data['config'])
        if err:
            return err
        s.location_id = location_id
        s.set_config(data['config'])
    if 'is_default' in data:
        s.is_default = data['is_default']
        if s.is_default:
            ConfigSet.enforce_single_default(request.current_user.id, s.id, task_type=s.task_type)
    db.session.commit()
    # 配置套仅为模板：保存只更新配置套本身，不回写已绑定任务（任务持自有快照，互不影响）
    return success(s.to_dict(), message='保存成功')


@bp.route('/<int:set_id>', methods=['DELETE'])
@token_required
def delete_set(set_id):
    s = ConfigSet.query.filter_by(id=set_id, user_id=request.current_user.id).first()
    if not s:
        return error(message='配置套不存在', code=4040, status=404)
    # 任务已自持配置快照且解绑（config_set_id 仅作源自标签），删除配置套不再受引用限制
    Schedule.query.filter_by(config_set_id=s.id).update({'config_set_id': None})
    db.session.delete(s)
    db.session.commit()
    return success(message='删除成功')


@bp.route('/<int:set_id>/apply-batch', methods=['POST'])
@token_required
def apply_set_batch(set_id):
    """批量套用：把配置套配置覆盖写入指定账号的任务实例（body: {targets:[{accountId,taskType}]}）。

    语义与单任务「套用配置套」一致：任务转为独立持有快照（standalone），
    config_set_id 退化为来源标签；实例不存在的账号任务现场补建（默认停用，不自动开启）。
    账号不存在或未启用则跳过；已启用的任务覆盖后重算下次执行时间并对齐调度器 job。
    """
    s = ConfigSet.query.filter_by(id=set_id, user_id=request.current_user.id).first()
    if not s:
        return error(message='配置套不存在', code=4040, status=404)

    payload = request.get_json(silent=True) or {}
    raw = payload.get('targets')
    if not isinstance(raw, list):
        return error(message='缺少应用目标', code=4401, status=400)

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
        return error(message='缺少有效的应用目标', code=4401, status=400)

    from app.services.scheduler import sync_schedule
    from app.utils.schedule_utils import compute_next_run

    user = request.current_user
    updated = created = skipped = mismatched = 0
    for acc_id, task_type in targets:
        # 类型过滤：寝室套不套到活动任务、活动套不套到寝室任务（配置语义错配防护）
        if task_type != s.task_type:
            mismatched += 1
            continue
        acc = BAccount.query.filter_by(id=acc_id, user_id=user.id).first()
        if not acc or not acc.enabled:
            skipped += 1
            continue
        sc = Schedule.query.filter_by(user_id=user.id, account_id=acc.id, task_type=task_type).first()
        if sc:
            sc.set_config(s.config)
            sc.mode = 'standalone'
            sc.config_set_id = s.id
        else:
            sc = Schedule(user_id=user.id, account_id=acc.id, task_type=task_type,
                          mode='standalone', enabled=False, config_set_id=s.id)
            sc.set_config(s.config)
            db.session.add(sc)
            created += 1
        if sc.enabled:
            sc.next_run_at = compute_next_run(sc)
            sync_schedule(sc)
        updated += 1
    db.session.commit()

    msg = f'已套用到 {updated} 个账号任务'
    if created:
        msg += f'（新建 {created}）'
    if mismatched:
        label = '活动' if s.task_type == 'activity' else '寝室'
        msg += f'，跳过 {mismatched} 个（本套仅适用于{label}签到任务）'
    if skipped:
        msg += f'，跳过 {skipped} 个（账号不存在或未启用）'
    return success({'updated': updated, 'created': created,
                    'skipped': skipped + mismatched}, message=msg)
