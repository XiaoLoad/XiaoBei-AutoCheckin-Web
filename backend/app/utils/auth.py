# 鉴权工具：JWT 生成/解析 + 路由鉴权装饰器 + 令牌吊销（黑名单）
# 安全原则：不信任前端权限控制，敏感接口一律后端校验；非法访问统一返回 401/403。
import datetime
import functools
import uuid

import jwt
from flask import current_app, request

from app.extensions import db
from app.models.token_blacklist import TokenBlacklist
from app.models.user import User
from app.utils.response import error
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

# 统一错误码（前端据此展示清晰提示）
ERR = {
    'NO_TOKEN': (1005, '未携带有效凭证', 401),
    'EXPIRED': (1004, 'Token 已过期，请重新登录', 401),
    'ILLEGAL': (1005, 'Token 非法', 401),
    'USER_GONE': (1001, '用户不存在', 401),
    'DISABLED': (1003, '账号已被禁用', 403),
    'FORBIDDEN_ADMIN': (1006, '权限不足，仅限管理员访问', 403),
    'FORBIDDEN_USER': (1006, '权限不足，仅限普通用户访问', 403),
    # 已注销：token 被加入黑名单（用户主动退出登录），视为失效需重新登录
    'REVOKED': (1007, '登录已失效，请重新登录', 401),
}


def _jwt_secret():
    return current_app.config['JWT_SECRET_KEY']


def _jwt_expires_hours():
    return current_app.config['JWT_EXPIRES_HOURS']


def generate_token(user):
    """生成 JWT：payload 携带 uid、role、唯一 jti 与过期时间"""
    now = datetime.datetime.utcnow()
    payload = {
        'uid': user.id,
        'role': user.role,
        'jti': uuid.uuid4().hex,
        'iat': now,
        'exp': now + datetime.timedelta(hours=_jwt_expires_hours()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm='HS256')


def decode_token(token):
    """解析 JWT；过期/非法由调用方捕获"""
    return jwt.decode(token, _jwt_secret(), algorithms=['HS256'])


def _fail(key):
    code, msg, status = ERR[key]
    return error(message=msg, code=code, status=status)


def is_blacklisted(jti):
    """校验 jti 是否已被吊销；出现异常（如黑名单表未创建）时降级为不拦截，避免误伤正常请求"""
    if not jti:
        return False
    try:
        return db.session.get(TokenBlacklist, jti) is not None
    except Exception:
        return False


def blacklist_token(jti, exp):
    """
    将 token 加入黑名单使其立即失效，并清理已过期条目避免表膨胀。
    任何异常均被吞掉，保证注销流程不被阻断（最坏情况：该 token 仍可在 exp 前使用，由前端兜底清理）。
    """
    if not jti:
        return
    try:
        now = datetime.datetime.utcnow()
        # 先清理过期条目，控制表体积
        TokenBlacklist.query.filter(TokenBlacklist.exp < now).delete()
        db.session.commit()
        if not db.session.get(TokenBlacklist, jti):
            db.session.add(TokenBlacklist(jti=jti, exp=exp))
            db.session.commit()
    except Exception:
        db.session.rollback()


def token_required(view):
    """鉴权装饰器：任意已登录且启用的用户（admin / user 均可）"""

    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return _fail('NO_TOKEN')
        token = auth[7:].strip()
        try:
            payload = decode_token(token)
        except ExpiredSignatureError:
            return _fail('EXPIRED')
        except InvalidTokenError:
            return _fail('ILLEGAL')

        # 已注销（加入黑名单）的 token 一律拦截，使退出登录后立即失效
        jti = payload.get('jti')
        if is_blacklisted(jti):
            return _fail('REVOKED')

        user = User.query.get(payload.get('uid'))
        if not user:
            return _fail('USER_GONE')
        if not user.enabled:
            return _fail('DISABLED')

        # 将当前用户与解密后的 payload 挂载到 request，供视图/注销接口直接使用
        request.current_user = user
        request.token_payload = payload
        return view(*args, **kwargs)

    return wrapper


def admin_required(view):
    """鉴权装饰器：仅限管理员访问"""

    @functools.wraps(view)
    @token_required
    def wrapper(*args, **kwargs):
        if request.current_user.role != 'admin':
            return _fail('FORBIDDEN_ADMIN')
        return view(*args, **kwargs)

    return wrapper


def user_required(view):
    """鉴权装饰器：仅限普通登录用户访问（管理员不可越权访问用户专属接口）"""

    @functools.wraps(view)
    @token_required
    def wrapper(*args, **kwargs):
        if request.current_user.role != 'user':
            return _fail('FORBIDDEN_USER')
        return view(*args, **kwargs)

    return wrapper
