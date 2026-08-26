# 配置套蓝图：用户级签到配置预设。默认套随三期调度解析一同落地（见计划差异决策 3）。
from flask import Blueprint, request

from app.extensions import db
from app.models import ConfigSet, PoolLocation, Schedule
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
                  location_id=location_id, is_default=False)
    s.set_config(data['config'])
    db.session.add(s)
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
    db.session.commit()
    return success(s.to_dict(), message='保存成功')


@bp.route('/<int:set_id>', methods=['DELETE'])
@token_required
def delete_set(set_id):
    s = ConfigSet.query.filter_by(id=set_id, user_id=request.current_user.id).first()
    if not s:
        return error(message='配置套不存在', code=4040, status=404)
    refs = Schedule.query.filter_by(config_set_id=s.id).count()
    if refs:
        return error(message=f'该配置套被 {refs} 个定时任务引用，请先解除关联',
                     code=4204, data={'refs': refs}, status=409)
    db.session.delete(s)
    db.session.commit()
    return success(message='删除成功')
