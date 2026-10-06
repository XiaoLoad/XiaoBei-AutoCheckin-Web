# 用户管理蓝图：列表（分页/过滤）、新增、编辑、禁用启用、删除（级联真删）
# 前缀 /api/users；全部操作均限管理员——列表含全员用户名/角色/额度，不向普通用户开放
from flask import Blueprint, current_app, request
from sqlalchemy import func

from app.extensions import db
from app.models.b_account import BAccount
from app.models.user import User
from app.utils.auth import admin_required
from app.utils.response import error, success
from app.services.user_service import load_user, purge_user, user_delete_blockers, user_summary
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

    # [安全] 与 set_status/delete 同源的防呆：编辑接口同样不得禁用或降级自己，
    # 否则当场失去会话/管理权限（单管理员场景下系统将再无可用管理员）
    current = request.current_user
    if current.id == user.id:
        if data.get('enabled') is False:
            return error(message='不能禁用当前登录的账号', code=1006, status=403)
        if user.role == 'admin' and data.get('role') not in (None, 'admin'):
            return error(message='不能降低当前登录账号的角色', code=1006, status=403)

    # password 不能进 setattr 循环：模型列是 password_hash，setattr(user, 'password', 明文)
    # 只会挂一个瞬时属性并在 commit 后丢弃（密码看似保存实则未变），必须走 set_password 哈希
    password = data.pop('password', None)
    # 审计用：先抓取本次要改字段的原值，订阅者据此还原 from→to（改角色这类变更是重点）
    before = {k: getattr(user, k, None) for k in data}
    for key, value in data.items():
        setattr(user, key, value)
    if password:
        user.set_password(password)
        # 管理员重置密码同样递增 pwd_ver，吊销该用户全部存量 token（S7 同口径）
        user.pwd_ver = (user.pwd_ver or 1) + 1
    db.session.commit()
    user_changed.send('users.update', user=user, before=before, password_changed=bool(password))
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
    """删除用户：物理删除，并级联清掉名下全部私有数据（见 services/user_service.purge_user）。

    三类拒绝与「禁用自己」同源，都是防呆而非权限：删掉自己会当场失去会话；
    删掉最后一个管理员则再没人能登录管理端；被他人引用时直接拒绝，
    因为那些引用属于别人的配置，替他们决定删除是一种越权。
    """
    user = load_user(user_id)
    if not user:
        return error(message='用户不存在', code=404, status=404)

    current = request.current_user
    if current.id == user.id:
        return error(message='不能删除当前登录的账号', code=1006, status=403)
    if user.role == 'admin' and User.query.filter_by(role='admin').count() <= 1:
        return error(message='至少保留一个管理员账号', code=1007, status=403)

    blockers = user_delete_blockers(user)
    if blockers:
        detail = '、'.join(f"{b['label']} {b['refs']} 处" for b in blockers)
        return error(message=f'该用户的共享资源仍被其他账号使用（{detail}），请先解除引用',
                     code=4009, data={'blockers': blockers}, status=409)

    # 审计快照须在删除前抓：行删掉后属性不可读，被删用户名也要靠它落进日志
    snapshot = {'targetUserId': user.id, 'targetUsername': user.username, 'role': user.role}
    try:
        result = purge_user(user)
    except Exception:
        db.session.rollback()
        current_app.logger.exception('删除用户失败：id=%s', user_id)
        return error(message='删除失败，数据未变更', code=5001, status=500)

    # 调度器 job 按 schedule_id 显式移除：purge 走 ORM 批量删除、不经过 schedules 路由
    # （30s 对账线程是兜底，但等它扫到之前会一直触发指向已删任务的重试）
    from app.services.scheduler import remove_job
    for sid in result.get('scheduleIds') or []:
        remove_job(sid)
    # 磁盘图片目录在 DB 事务成功后清理（F2）：uuid 文件名无索引可寻，不删则永久残留。
    # 失败只记日志不回滚——库已删完，残留目录不再有任何引用。
    from app.services.image_store import purge_user_files
    purge_user_files(user.id)
    user_changed.send('users.delete', user_id=user.id, snapshot=snapshot, cascade=result['counts'])
    return success(message='删除成功')
