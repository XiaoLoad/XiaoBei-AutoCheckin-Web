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
from app.models.user import User, now_cst

# 开发环境种子账号（上线请删除或改为强口令）
# quota=总额度，used_quota=已使用额度，用于演示用户额度展示
SEED_USERS = [
    {'username': 'admin', 'password': 'admin123', 'role': 'admin', 'enabled': True, 'quota': 999, 'used_quota': 128},
    {'username': 'user01', 'password': 'user123', 'role': 'user', 'enabled': True, 'quota': 50, 'used_quota': 12},
    # 禁用账号：用于验证"账号已被禁用"拦截
    {'username': 'frozen01', 'password': 'frozen123', 'role': 'user', 'enabled': False, 'quota': 30, 'used_quota': 4},
    # 演示用普通账号：用于展示分页与额度进度条区分度（上线可清理）
    {'username': 'demo01', 'password': 'demo123', 'role': 'user', 'enabled': True, 'quota': 40, 'used_quota': 36},
    {'username': 'demo02', 'password': 'demo123', 'role': 'user', 'enabled': True, 'quota': 60, 'used_quota': 10},
    {'username': 'demo03', 'password': 'demo123', 'role': 'user', 'enabled': True, 'quota': 80, 'used_quota': 74},
    {'username': 'demo04', 'password': 'demo123', 'role': 'user', 'enabled': True, 'quota': 100, 'used_quota': 45},
    {'username': 'demo05', 'password': 'demo123', 'role': 'user', 'enabled': True, 'quota': 15, 'used_quota': 15},
    {'username': 'demo06', 'password': 'demo123', 'role': 'user', 'enabled': True, 'quota': 200, 'used_quota': 22},
    {'username': 'demo07', 'password': 'demo123', 'role': 'user', 'enabled': False, 'quota': 50, 'used_quota': 3},
    {'username': 'demo08', 'password': 'demo123', 'role': 'user', 'enabled': True, 'quota': 75, 'used_quota': 60},
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
                quota=spec.get('quota', 100),
                used_quota=spec.get('used_quota', 0),
            )
            u.set_password(spec['password'])
            db.session.add(u)
            created.append(spec['username'])
        db.session.commit()

        # 已存在的种子账号：强制补齐演示用额度，使管理页进度条有区分度；
        # 同时把创建时间统一修正为中国本地时间（修复早期 utcnow 落库导致展示偏早 8 小时）。
        for spec in SEED_USERS:
            u = User.query.filter_by(username=spec['username']).first()
            if u:
                u.quota = spec.get('quota', 100)
                u.used_quota = spec.get('used_quota', 0)
                u.created_at = now_cst()
                db.session.add(u)
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
