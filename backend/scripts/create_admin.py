# 首个管理员创建脚本（手动兜底）：全新部署的默认路径是启动自动引导——
# users 表为空时应用自动创建 admin 并把随机密码打印到启动日志一次。
# 本脚本用于错过一次性密码或需要指定用户名时手动建号。
# 用法（backend 目录下）：
#   python scripts/create_admin.py <用户名>
# 运行时交互输入密码（不回显，输入两遍确认）。
#
# 安全设计：
#   - 仅当 users 表为空时允许执行；已存在任何账号即拒绝（防止绕过界面直接造号）
#   - 用户名走与接口一致的校验器；密码校验与系统设置 password_min_length、
#     bcrypt 72 字节上限对齐（与 API 入口同一套规则）
#   - FLASK_ENV=production 时经 create_app 自动执行生产密钥守护
#     （SECRET_KEY/JWT_SECRET_KEY 仍为开发默认值、CORS 含 '*'、连接串为开发默认 → 拒绝启动）
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.system_config import get_setting
from app.models.user import User
from app.utils.validators import (PASSWORD_MAX_BYTES, password_too_long,
                                  validate_username)


def create_first_admin(username, password):
    """建号核心逻辑（需 app 上下文）。系统已有账号时拒绝执行。"""
    ok, name, message, _code = validate_username(username)
    if not ok:
        raise SystemExit(f'[create_admin] 用户名不合法：{message}')
    if User.query.count() > 0:
        raise SystemExit(
            '[create_admin] 已拒绝执行：系统中已存在账号。'
            '本脚本只用于全新部署创建首个管理员，'
            '后续账号请由管理员在「用户管理」界面创建。'
        )
    min_len = get_setting('password_min_length') or 6
    if len(password) < min_len:
        raise SystemExit(f'[create_admin] 密码至少 {min_len} 位')
    if password_too_long(password):
        raise SystemExit(f'[create_admin] 密码过长（最多 {PASSWORD_MAX_BYTES} 字节）')
    admin = User(username=name, role='admin', enabled=True)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    return admin


def main():
    if len(sys.argv) != 2:
        raise SystemExit('用法：python scripts/create_admin.py <用户名>')
    app = create_app()
    with app.app_context():
        min_len = get_setting('password_min_length') or 6
        password = getpass.getpass(f'请输入管理员密码（至少 {min_len} 位，输入不回显）：')
        if len(password) < min_len:
            raise SystemExit(f'[create_admin] 密码至少 {min_len} 位')
        confirm = getpass.getpass('请再输入一遍确认：')
        if password != confirm:
            raise SystemExit('[create_admin] 两次输入不一致，未创建')
        admin = create_first_admin(sys.argv[1], password)
        print(f'[create_admin] 管理员 {admin.username} 已创建，请尽快登录修改密码。')


if __name__ == '__main__':
    main()
