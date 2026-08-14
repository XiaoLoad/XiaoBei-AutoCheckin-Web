# 用户管理蓝图：列表（分页/过滤）、新增、编辑、禁用启用、删除（桩）
# 前缀 /api/users；除列表外的写操作均限管理员
import re

from flask import Blueprint, request

from app.extensions import db
from app.models.user import User
from app.utils.auth import admin_required, token_required
from app.utils.response import error, success

bp = Blueprint('users', __name__, url_prefix='/api/users')

_VALID_ROLES = ('admin', 'user')
# 用户名白名单：字母、数字、下划线、连字符、点、中文。其余特殊字符一律拒绝，
# 避免把不可控字符写入账号标识导致展示/查询异常。
_USERNAME_RE = re.compile(r'^[A-Za-z0-9_.\-\u4e00-\u9fa5]+$')
_USERNAME_MAX = 64


def _load_user(user_id):
    """按 user_id 取用户；不存在返回 None（调用方决定如何处理）"""
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, uid)


@bp.route('', methods=['GET'])
@token_required
def list_users():
    """
    用户列表：支持分页、关键词（用户名模糊）、角色过滤。
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
    items = [u.to_dict() for u in pagination.items]

    # 全表汇总（不受分页影响），用于前端展示整体概况
    total_users = User.query.count()
    enabled_count = User.query.filter_by(enabled=True).count()
    agg = db.session.query(db.func.sum(User.quota), db.func.sum(User.used_quota)).first()
    summary = {
        'total_users': total_users,
        'enabled': enabled_count,
        'disabled': total_users - enabled_count,
        'total_quota': int(agg[0] or 0),
        'used_quota': int(agg[1] or 0),
    }

    return success(
        {
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size,
            'summary': summary,
        }
    )


@bp.route('', methods=['POST'])
@admin_required
def create_user():
    """新增用户：用户名 + 密码必填；角色默认 user；额度默认 100。"""
    payload = request.get_json(silent=True) or {}
    username = (payload.get('username') or '').strip()
    password = payload.get('password') or ''
    role = (payload.get('role') or 'user').strip()
    enabled = bool(payload.get('enabled', True))
    try:
        quota = int(payload.get('quota', 100))
    except (TypeError, ValueError):
        quota = 100
    if quota < 0:
        quota = 0

    if not username:
        return error(message='用户名不能为空', code=4001, status=400)
    if len(username) > _USERNAME_MAX:
        return error(message='用户名过长（最多 64 字符）', code=4001, status=400)
    if not _USERNAME_RE.match(username):
        return error(message='用户名仅支持字母、数字、下划线、连字符、点及中文', code=4001, status=400)
    if not password or len(password) < 6:
        return error(message='密码至少 6 位', code=4002, status=400)
    if role not in _VALID_ROLES:
        return error(message='角色不合法', code=4003, status=400)
    if User.query.filter_by(username=username).first():
        return error(message='用户名已存在', code=4004, status=409)

    user = User(username=username, role=role, enabled=enabled, quota=quota)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return success(user.to_dict(), message='创建成功', status=201)


@bp.route('/<user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """编辑用户：可改用户名/角色/状态/额度，密码可选（留空不改）。"""
    user = _load_user(user_id)
    if not user:
        return error(message='用户不存在', code=404, status=404)

    payload = request.get_json(silent=True) or {}
    username = (payload.get('username') or '').strip()
    password = payload.get('password') or ''
    role = (payload.get('role') or '').strip()
    enabled = payload.get('enabled', None)
    quota = payload.get('quota', None)

    if username:
        if len(username) > _USERNAME_MAX:
            return error(message='用户名过长（最多 64 字符）', code=4001, status=400)
        if not _USERNAME_RE.match(username):
            return error(message='用户名仅支持字母、数字、下划线、连字符、点及中文', code=4001, status=400)
        if username != user.username and User.query.filter_by(username=username).first():
            return error(message='用户名已存在', code=4004, status=409)
        user.username = username
    if role:
        if role not in _VALID_ROLES:
            return error(message='角色不合法', code=4003, status=400)
        user.role = role
    if enabled is not None:
        user.enabled = bool(enabled)
    if quota is not None:
        try:
            quota_val = int(quota)
        except (TypeError, ValueError):
            return error(message='额度必须为整数', code=4005, status=400)
        if quota_val < 0:
            return error(message='额度不能为负', code=4005, status=400)
        user.quota = quota_val
    if password:
        if len(password) < 6:
            return error(message='密码至少 6 位', code=4002, status=400)
        user.set_password(password)

    db.session.commit()
    return success(user.to_dict(), message='保存成功')


@bp.route('/<user_id>/status', methods=['PATCH'])
@admin_required
def set_status(user_id):
    """禁用 / 启用用户：body { enabled: bool }。禁止禁用当前登录账号以防锁死。"""
    user = _load_user(user_id)
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
    return success(user.to_dict(), message='已更新状态')


@bp.route('/<user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """
    删除用户：当前为前端 UI 演示用桩接口，暂不执行真实删除逻辑。
    直接返回成功，待后端删除逻辑落地后再补充实际销毁。
    """
    # [桩] 暂不实现实际删除（前端仅做 UI 展示）。保留接口契约以便后续对接。
    return success(message='删除成功')
