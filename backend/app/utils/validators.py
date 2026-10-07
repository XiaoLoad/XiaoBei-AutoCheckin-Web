# 可复用输入校验片段：集中定义，便于跨路由与未来服务层复用，
# 避免用户名正则、角色白名单等规则散落在多个路由中、易漂移。
import re

USERNAME_RE = re.compile(r'^[A-Za-z0-9_.\-]+$')
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
        return False, username, '用户名仅支持字母、数字、下划线、连字符、点', 4001
    return True, username, '', 0


def validate_role(raw, *, default='user'):
    """校验角色是否在白名单内。返回 (ok, value, message, code)。"""
    role = (raw or default).strip()
    if role not in VALID_ROLES:
        return False, role, '角色不合法', 4003
    return True, role, '', 0


# bcrypt 只取前 72 字节做哈希：超长部分被静默丢弃，用户以为的密码与实际生效的
# 密码不一致（他人用前 72 字节即可通过校验）。入口统一拒绝超长，不静默截断。
PASSWORD_MAX_BYTES = 72


def password_too_long(password):
    """密码是否超过 bcrypt 有效长度（按 UTF-8 字节计）。"""
    return len((password or '').encode('utf-8')) > PASSWORD_MAX_BYTES


# 邮件收件人：一行里可写多个（逗号 / 分号 / 中英文标点 / 空白分隔）。
# 凭证的默认收件人与账号级覆盖共用这一套解析，避免两处各切一次导致行为不一致。
RECIPIENT_SEP_RE = re.compile(r'[,;，；\s]+')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
RECIPIENT_MAX = 512


def parse_recipients(raw):
    """收件人串 → 去重后列表（保序）。"""
    out = []
    for part in RECIPIENT_SEP_RE.split(str(raw or '')):
        p = part.strip()
        if p and p not in out:
            out.append(p)
    return out


def normalize_recipients(raw):
    """收件人串 → 归一化文本（逗号分隔、保序去重）。"""
    return ', '.join(parse_recipients(raw))


def validate_recipients(raw, *, required=True):
    """校验收件人串。返回 (ok, normalized, message, code)。"""
    items = parse_recipients(raw)
    if not items:
        if required:
            return False, '', '收件人不能为空', 4321
        return True, '', '', 0
    bad = [x for x in items if not EMAIL_RE.match(x)]
    if bad:
        return False, '', f'收件人邮箱格式不正确：{bad[0]}', 4321
    norm = ', '.join(items)
    if len(norm) > RECIPIENT_MAX:
        return False, '', f'收件人过多（最多 {RECIPIENT_MAX} 字符）', 4321
    return True, norm, '', 0
