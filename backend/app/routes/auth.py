# 鉴权蓝图：登录、当前用户信息
# 前缀 /api/auth
from datetime import datetime

from flask import Blueprint, request

from app.extensions import db
from app.models.system_config import get_setting
from app.models.user import User, now_cst
from app.utils.auth import blacklist_token, generate_token, token_required
from app.utils.response import error, success
from app.events import auth_logged_out

bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@bp.route('/login', methods=['POST'])
def login():
    """
    登录：校验账号密码 → 生成 JWT → 返回 token 与用户基本信息
    错误码：1000 参数缺失 / 1001 账号不存在 / 1003 账号禁用 / 1002 密码错误
    """
    payload = request.get_json(silent=True) or {}
    account = (payload.get('account') or '').strip()
    password = payload.get('password') or ''
    if not account or not password:
        return error(message='账号和密码不能为空', code=1000, status=400)

    user = User.query.filter_by(username=account).first()
    if not user:
        return error(message='账号不存在', code=1001, status=401)
    if not user.enabled:
        return error(message='账号已被禁用', code=1003, status=403)
    if not user.check_password(password):
        return error(message='密码错误', code=1002, status=401)

    token = generate_token(user)
    user.last_login = now_cst()
    db.session.commit()

    return success(
        {
            'token': token,
            'user_id': user.id,
            'username': user.username,
            'role': user.role,
        },
        message='登录成功',
    )


@bp.route('/me', methods=['GET'])
@token_required
def me():
    """获取当前登录用户基本信息（用于前端刷新态校验）"""
    u = request.current_user
    return success(
        {
            'user_id': u.id,
            'username': u.username,
            'role': u.role,
            'enabled': u.enabled,
        }
    )


@bp.route('/password', methods=['PUT'])
@token_required
def change_password():
    """
    修改当前登录用户密码：校验原密码 → 按系统配置的密码最小长度校验新密码 → 重设哈希。
    错误码：1000 参数缺失 / 1002 原密码错误 / 4002 新密码不合规
    """
    u = request.current_user
    payload = request.get_json(silent=True) or {}
    old_password = payload.get('old_password') or ''
    new_password = payload.get('new_password') or ''
    if not old_password or not new_password:
        return error(message='原密码和新密码不能为空', code=1000, status=400)

    min_len = get_setting('password_min_length') or 6
    if len(new_password) < min_len:
        return error(message=f'新密码至少 {min_len} 位', code=4002, status=400)
    if new_password == old_password:
        return error(message='新密码不能与原密码相同', code=4002, status=400)
    if not u.check_password(old_password):
        return error(message='原密码错误', code=1002, status=400)

    u.set_password(new_password)
    db.session.commit()
    return success(message='密码修改成功')


@bp.route('/logout', methods=['POST'])
@token_required
def logout():
    """
    注销：将当前 token 的 jti 加入黑名单，使其在有效期内也立即失效。
    即便客户端已清除本地 token，服务端仍会拒绝任何携带该 token 的请求，
    从而保证退出登录后无法继续访问受保护资源。
    """
    payload = getattr(request, 'token_payload', None) or {}
    jti = payload.get('jti')
    exp = payload.get('exp')
    if jti and exp:
        try:
            blacklist_token(jti, datetime.utcfromtimestamp(exp))
        except Exception:
            # 吊销失败不影响前端本地退出；最坏情况该 token 仍可在 exp 前使用，由前端兜底清理
            pass
    # 发布登出事件，供前端（或未来后端订阅者）统一响应清理，避免调用方硬连线
    auth_logged_out.send('auth.logout', user=request.current_user)
    return success(message='注销成功')
