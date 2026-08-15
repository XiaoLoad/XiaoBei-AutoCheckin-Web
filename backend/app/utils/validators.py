# 可复用输入校验片段：集中定义，便于跨路由与未来服务层复用，
# 避免用户名正则、角色白名单等规则散落在多个路由中、易漂移。
import re

USERNAME_RE = re.compile(r'^[A-Za-z0-9_.\-\u4e00-\u9fa5]+$')
USERNAME_MAX = 64
VALID_ROLES = ('admin', 'user')


def validate_username(raw, *, required=True):
    """校验用户名。返回 (ok, value, message, code)。
    required=False 时允许为空（用于编辑场景的「不修改用户名」）。"""
    username = (raw or '').strip()
    if not username:
        if required:
            return False, '', '用户名不能为空', 4001
        return True, '', '', 0
    if len(username) > USERNAME_MAX:
        return False, username, f'用户名过长（最多 {USERNAME_MAX} 字符）', 4001
    if not USERNAME_RE.match(username):
        return False, username, '用户名仅支持字母、数字、下划线、连字符、点及中文', 4001
    return True, username, '', 0


def validate_role(raw, *, default='user'):
    """校验角色是否在白名单内。返回 (ok, value, message, code)。"""
    role = (raw or default).strip()
    if role not in VALID_ROLES:
        return False, role, '角色不合法', 4003
    return True, role, '', 0
