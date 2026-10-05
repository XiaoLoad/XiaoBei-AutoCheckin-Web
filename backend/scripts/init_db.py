# 数据库初始化脚本：建表 + 种子数据（开发联调用）
# 用法（backend 目录下）：
#   python scripts/init_db.py
# 前置：本地 MySQL 已启动，且已执行 CREATE DATABASE xiaobei_auto;
#
# 安全守卫（S8）：本脚本只允许对开发默认库执行——
#   ① FLASK_ENV=production 时拒绝；② 数据库连接串不是开发默认值时拒绝
#   （连接串被改写通常意味着指向真实库）。两条守卫确保弱口令种子
#   永远进不了生产库，绕过生产密钥守护的旧路径不复存在。
# 种子密码（S8）：不再写死弱口令，创建时随机生成并仅在终端打印一次；
#   已存在的种子账号不会被重置密码。
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入 app 即完成 config 的 .env 加载，此后 os.getenv 能读到 .env 值
from app import _DEV_DEFAULT_DB_URI, create_app
from app.extensions import db
from app.models.token_blacklist import TokenBlacklist
from app.models.user import User, now_cst

# 开发环境种子账号（不含密码——创建时随机生成，仅终端显示一次）
# 仅保留一个管理员 + 一个普通用户；B 平台对接开发期间不再需要批量演示数据
# quota=总额度，used_quota=已使用额度
SEED_USERS = [
    {'username': 'admin', 'role': 'admin', 'enabled': True, 'quota': 999, 'used_quota': 128},
    {'username': 'user01', 'role': 'user', 'enabled': True, 'quota': 50, 'used_quota': 12},
]


def _guard():
    """执行前校验目标库形态：生产环境或非开发默认库一律拒绝（S8）。

    旧实现硬编码 create_app('development') 可绕过生产密钥守护，把
    弱口令种子写进真实库；现在在触碰任何数据库之前先行拦截。"""
    if os.getenv('FLASK_ENV', '') == 'production':
        raise SystemExit(
            '[init_db] 已拒绝执行：FLASK_ENV=production。'
            '本脚本只用于开发库初始化（弱口令种子 + 演示额度），'
            '生产库请用迁移管理结构（flask db upgrade），账号由管理员在界面创建。'
        )
    db_uri = os.getenv('SQLALCHEMY_DATABASE_URI') or _DEV_DEFAULT_DB_URI
    if db_uri != _DEV_DEFAULT_DB_URI:
        raise SystemExit(
            '[init_db] 已拒绝执行：数据库连接串不是开发默认值'
            '（root:***@localhost/xiaobei_auto）。'
            '连接串被改写通常意味着指向真实库，为防种子弱口令写入，本脚本拒绝继续。'
        )


def main():
    _guard()
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
            password = secrets.token_urlsafe(12)
            u.set_password(password)
            db.session.add(u)
            created.append((spec['username'], password))
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

    print('[init_db] 建表完成。')
    if created:
        print('[init_db] 已创建用户（随机密码仅本次显示，请立即保存）：')
        for name, password in created:
            print(f'          {name} / {password}')
    else:
        print('[init_db] 种子用户已存在，无需创建')


if __name__ == '__main__':
    main()
