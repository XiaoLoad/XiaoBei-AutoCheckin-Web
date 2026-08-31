# 用户管理蓝图：列表（分页/过滤）、新增、编辑、禁用启用、删除（桩）
# 前缀 /api/users；全部操作均限管理员——列表含全员用户名/角色/额度，不向普通用户开放
from flask import Blueprint, request
from sqlalchemy import func

from app.extensions import db
from app.models.b_account import BAccount
from app.models.user import User
from app.utils.auth import admin_required
from app.utils.response import error, success
from app.services.user_service import load_user, user_summary
from app.schemas.user_schema import load_create, load_update
from app.events import user_changed

bp = Blueprint('users', __name__, url_prefix='/api/users')


@bp.route('', methods=['GET'])
@admin_required
def list_users():
    """
    用户列表：支持分页、关键词（用户名模糊）、角色过滤。仅管理员可访问，
    普通用户请求返回 403（响应体含全员用户名/角色/额度，属敏感信息）。
    返回结构：{ items, total, page, page_size, summary }
      summary 为全表聚合，用于前端汇总卡片（总数 / 启用 / 禁用 / 额度使用）。
    """
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(100, max(1, int(request.args.get('page_size', 10))))
    except (TypeError, ValueError):
        page_size = 10

    keyword = (request.args.get('keyword') or '').strip()
    role = (request.args.get('role') or '').strip()

    query = User.query
    if keyword:
        query = query.filter(User.username.like(f'%{keyword}%'))
    if role:
        query = query.filter(User.role == role)

    total = query.count()
    pagination = query.order_by(User.id).paginate(page=page, per_page=page_size, error_out=False)
    # 一次性聚合已用额度（账号数按 user_id 分组），避免逐用户 COUNT 的 N+1
    user_ids = [u.id for u in pagination.items]
    if user_ids:
        used_rows = (db.session.query(BAccount.user_id, func.count(BAccount.id))
                     .filter(BAccount.user_id.in_(user_ids)).group_by(BAccount.user_id).all())
        used_map = {int(uid): int(cnt) for uid, cnt in used_rows}
    else:
        used_map = {}
    items = [u.to_dict(used=used_map.get(u.id, 0)) for u in pagination.items]

    return success(
        {
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size,
            'summary': user_summary(),
        }
    )


@bp.route('', methods=['POST'])
@admin_required
def create_user():
    """新增用户：用户名 + 密码必填；角色默认 user；额度默认 100。"""
    payload = request.get_json(silent=True) or {}

    # 入参校验集中到 schema 层，统一错误信息与错误码
    ok, data, msg, code = load_create(payload)
    if not ok:
        return error(message=msg, code=code, status=400)
    if User.query.filter_by(username=data['username']).first():
        return error(message='用户名已存在', code=4004, status=409)

    user = User(username=data['username'], role=data['role'], enabled=data['enabled'], quota=data['quota'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    user_changed.send('users.create', user=user)
    return success(user.to_dict(), message='创建成功', status=201)


@bp.route('/<user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """编辑用户：可改用户名/角色/状态/额度，密码可选（留空不改）。"""
    user = load_user(user_id)
    if not user:
        return error(message='用户不存在', code=404, status=404)

    payload = request.get_json(silent=True) or {}
    ok, data, msg, code = load_update(payload)
    if not ok:
        return error(message=msg, code=code, status=400)
    # 重名检查（仅在修改用户名时）
    if 'username' in data and data['username'] != user.username and User.query.filter_by(username=data['username']).first():
        return error(message='用户名已存在', code=4004, status=409)

    # password 不能进 setattr 循环：模型列是 password_hash，setattr(user, 'password', 明文)
    # 只会挂一个瞬时属性并在 commit 后丢弃（密码看似保存实则未变），必须走 set_password 哈希
    password = data.pop('password', None)
    for key, value in data.items():
        setattr(user, key, value)
    if password:
        user.set_password(password)
    db.session.commit()
    user_changed.send('users.update', user=user)
    return success(user.to_dict(), message='保存成功')


@bp.route('/<user_id>/status', methods=['PATCH'])
@admin_required
def set_status(user_id):
    """禁用 / 启用用户：body { enabled: bool }。禁止禁用当前登录账号以防锁死。"""
    user = load_user(user_id)
    if not user:
        return error(message='用户不存在', code=404, status=404)

    payload = request.get_json(silent=True) or {}
    enabled = payload.get('enabled', None)
    if enabled is None:
        return error(message='缺少 enabled 参数', code=4006, status=400)

    current = request.current_user
    # [安全] 禁止管理员禁用自身，避免系统无可用管理员
    if current.id == user.id and not bool(enabled):
        return error(message='不能禁用当前登录的账号', code=1006, status=403)

    user.enabled = bool(enabled)
    db.session.commit()
    user_changed.send('users.status', user=user)
    return success(user.to_dict(), message='已更新状态')


@bp.route('/<user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """
    删除用户：当前为前端 UI 演示用桩接口，暂不执行真实删除逻辑。
    直接返回成功，待后端删除逻辑落地后再补充实际销毁。
    """
    # [桩] 暂不实现实际删除（前端仅做 UI 展示）。保留接口契约以便后续对接。
    user_changed.send('users.delete', user_id=user_id)
    return success(message='删除成功')
