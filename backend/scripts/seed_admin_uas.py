# 一次性脚本：把热门/旗舰机型的 UA 模板批量写入「管理员的平台模板池」（is_system=1，归属管理员账号）。
# 仅依赖项目既有环境：python backend/.venv/Scripts/python.exe scripts/seed_admin_uas.py
# 安全约束：SCHEDULER_ENABLED=0（create_app 不再启动调度器、不会误触发任何签到）；不触碰任何加密字段。
import os
import sys

# 1) 关掉调度器（必须在 import app 之前）
os.environ.setdefault('SCHEDULER_ENABLED', '0')

# 2) .env 由 config/__init__.py 的 load_dotenv 统一加载（不再脚本侧手动解析）

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/

sys.path.insert(0, _ROOT)

from app import create_app, db  # noqa: E402
from app.models import PoolUa, User  # noqa: E402

# 安卓 uni-app（WebView Chrome）模板
ANDROID = [
    ("Mozilla/5.0 (Linux; Android 14; 23127PN0CC Build/UKQ1.230804.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0.6099.43 Mobile Safari/537.36 uni-app (Immersed/24.0)", "小米14（旗舰）"),
    ("Mozilla/5.0 (Linux; Android 14; SM-S9280 Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0.6099.43 Mobile Safari/537.36 uni-app (Immersed/24.0)", "三星Galaxy S24 Ultra（旗舰）"),
    ("Mozilla/5.0 (Linux; Android 14; PHZ110 Build/UKQ1.231108.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0.6099.43 Mobile Safari/537.36 uni-app (Immersed/24.0)", "OPPO Find X7（旗舰）"),
    ("Mozilla/5.0 (Linux; Android 14; V2309A Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/119.0.6045.163 Mobile Safari/537.36 uni-app (Immersed/24.0)", "vivo X100 Pro（旗舰）"),
    ("Mozilla/5.0 (Linux; Android 12; ALN-AL00 Build/HUAWEIALN-AL00; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/114.0.5735.196 Mobile Safari/537.36 uni-app (Immersed/24.0)", "华为Mate 60 Pro（旗舰）"),
    ("Mozilla/5.0 (Linux; Android 13; 2312DRA50C Build/TP1A.220905.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 uni-app (Immersed/24.0)", "红米Note 13（热门）"),
    ("Mozilla/5.0 (Linux; Android 13; PHJ110 Build/TP1A.220905.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/113.0.5672.76 Mobile Safari/537.36 uni-app (Immersed/24.0)", "OPPO A58（热门）"),
    ("Mozilla/5.0 (Linux; Android 13; V2249A Build/SP1A.210812.003; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/114.0.5735.196 Mobile Safari/537.36 uni-app (Immersed/24.0)", "vivo Y27（热门）"),
]

# iOS uni-app（WKWebView / WebKit）模板
IOS = [
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 uni-app (Immersed/24.0)", "iPhone 16 Pro（旗舰）"),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 uni-app (Immersed/24.0)", "iPhone 16（旗舰）"),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 uni-app (Immersed/24.0)", "iPhone 15 Pro Max（旗舰）"),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 uni-app (Immersed/24.0)", "iPhone 15（热门）"),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 uni-app (Immersed/24.0)", "iPhone 14（热门）"),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 uni-app (Immersed/24.0)", "iPhone 13（热门）"),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 uni-app (Immersed/24.0)", "iPhone SE 第三代（入门热门）"),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 uni-app (Immersed/24.0)", "iPhone 12（旧热门）"),
]

ALL = ANDROID + IOS


def main():
    app = create_app()
    with app.app_context():
        admin = (User.query.filter_by(role='admin').order_by(User.id.asc()).first())
        if not admin:
            print('ERROR: 未找到 role=admin 的管理员账号，无法写入平台模板池', file=sys.stderr)
            sys.exit(1)

        existing = {r.content for r in PoolUa.query.with_entities(PoolUa.content).all()}
        added, skipped = [], 0
        for content, remark in ALL:
            if content in existing:
                skipped += 1
                continue
            db.session.add(PoolUa(
                user_id=admin.id, is_system=True, content=content,
                remark=remark, enabled=True,
            ))
            added.append((remark, content[:48] + ('…' if len(content) > 48 else '')))

        db.session.commit()
        print(f'管理员账号 user_id={admin.id}（{admin.username}）')
        print(f'新增 {len(added)} 条，跳过已存在 {skipped} 条，UA 模板池当前共 {PoolUa.query.count()} 条')
        for remark, preview in added:
            print(f'  + [{remark}] {preview}')


if __name__ == '__main__':
    main()
