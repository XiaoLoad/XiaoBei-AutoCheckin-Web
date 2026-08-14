# 数据库初始化脚本：建表 + 种子数据（开发联调用）
# 用法（backend 目录下）：
#   python scripts/init_db.py
# 前置：本地 MySQL 已启动，且已执行 CREATE DATABASE xiaobei_auto;
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.token_blacklist import TokenBlacklist
from app.models.user import User

# 开发环境种子账号（上线请删除或改为强口令）
SEED_USERS = [
    {'username': 'admin', 'password': 'admin123', 'role': 'admin', 'enabled': True},
    {'username': 'user01', 'password': 'user123', 'role': 'user', 'enabled': True},
    # 禁用账号：用于验证"账号已被禁用"拦截
    {'username': 'frozen01', 'password': 'frozen123', 'role': 'user', 'enabled': False},
]


def main():
    app = create_app('development')
    with app.app_context():
        db.create_all()
        created = []
        for spec in SEED_USERS:
            if User.query.filter_by(username=spec['username']).first():
                continue
            u = User(
                username=spec['username'],
                role=spec['role'],
                enabled=spec['enabled'],
            )
            u.set_password(spec['password'])
            db.session.add(u)
            created.append(spec['username'])
        db.session.commit()

    if created:
        print(f'[init_db] 已创建用户：{", ".join(created)}')
    else:
        print('[init_db] 用户已存在，无需创建')
    print('[init_db] 建表完成。登录凭据：')
    print('          管理员  admin / admin123')
    print('          普通用户 user01 / user123')
    print('          禁用账号 frozen01 / frozen123（用于验证禁用拦截）')


if __name__ == '__main__':
    main()
