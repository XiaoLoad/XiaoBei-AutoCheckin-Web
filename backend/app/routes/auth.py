# 鉴权蓝图：登录、当前用户信息
# 前缀 /api/auth
from datetime import datetime

from flask import Blueprint, request

from app.extensions import db
from app.models.system_config import get_setting
from app.models.user import User, now_cst
from app.services import login_guard
from app.services.op_log import client_ip
from app.utils.auth import blacklist_token, generate_token, token_required
from app.utils.response import error, success
from app.events import auth_logged_out, auth_login, auth_password_changed

bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@bp.route('/login', methods=['POST'])
def login():
    """
    登录：防爆破查锁 → 校验账号密码 → 生成 JWT → 返回 token 与用户基本信息
    错误码：1000 参数缺失 / 1001 账号或密码错误（不区分不存在与密码错，防枚举）
            / 1003 账号禁用（仅在密码正确时可见）/ 1004 触发防爆破锁定
    失败分支同样发布 auth_login（result='fail'），审计日志据此留痕。
    """
    payload = request.get_json(silent=True) or {}
    account = (payload.get('account') or '').strip()
    password = payload.get('password') or ''
    if not account or not password:
        return error(message='账号和密码不能为空', code=1000, status=400)

    ip = client_ip()

    # ① 防爆破查锁：账号×IP / 账号全局 / IP 全局任一锁定中即拒绝。
    #    锁定响应不提示剩余时间——固定话术避免给攻击者提供探测信息。
    locked = login_guard.check_locked(account, ip)
    if locked:
        auth_login.send('auth.login', result='fail', username=account, reason='防爆破锁定中')
        return error(message='尝试过于频繁，请稍后再试', code=1004, status=429)

    user = User.query.filter_by(username=account).first()
    # ② 先验密码、后查禁用：向无密码者只暴露统一的凭据错误，
    #    持正确密码者才可见「账号已被禁用」（需要告知原因的合法场景）
    if user is None or not user.check_password(password):
        login_guard.record_failure(account, ip)
        db.session.commit()
        reason = '账号不存在' if user is None else '密码错误'
        auth_login.send('auth.login', result='fail', username=account, reason=reason)
        return error(message='账号或密码错误', code=1001, status=401)
    if not user.enabled:
        auth_login.send('auth.login', result='fail', username=account, reason='账号已被禁用')
        return error(message='账号已被禁用', code=1003, status=403)

    # ③ 成功：清掉该账号全部失败计数再发 token
    login_guard.clear_failures(account)
    db.session.commit()

    token = generate_token(user)
    user.last_login = now_cst()
    db.session.commit()
    auth_login.send('auth.login', result='success', user=user)

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
    auth_password_changed.send('auth.password', user=u)
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
