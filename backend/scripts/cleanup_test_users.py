# 一次性脚本：清理测试残留用户（tc_* 前缀 + 测试固定用户），复用 purge_user 级联链路。
# 用法：.venv/Scripts/python.exe scripts/cleanup_test_users.py
# 保留：username 不以 tc_ 开头的全部账号（admin/user01 等真实账号不受影响）。
import os
import shutil
import sys

os.environ.setdefault('SCHEDULER_ENABLED', '0')

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_env_path = os.path.join(_ROOT, '.env')
if os.path.exists(_env_path):
    with open(_env_path, 'r', encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith('#') or '=' not in _line:
                continue
            _k, _v = _line.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

sys.path.insert(0, _ROOT)

from flask import current_app

from app import create_app
from app.models.user import User
from app.services.scheduler import remove_job
from app.services.user_service import purge_user


def main():
    app = create_app()
    with app.app_context():
        victims = [u for u in User.query.all() if u.username.startswith('tc_')]
        print(f'待清理测试用户 {len(victims)} 个（保留全部非 tc_ 账号）')
        if not victims:
            print('无可清理用户')
            return

        total = {}
        upload_root = current_app.config['UPLOAD_DIR']
        removed_dirs = 0
        for u in victims:
            uid = u.id
            result = purge_user(u)
            for sid in result.get('scheduleIds') or []:
                remove_job(sid)
            for k, v in result['counts'].items():
                total[k] = total.get(k, 0) + (v or 0)
            user_img_dir = os.path.join(upload_root, 'pool_images', str(uid))
            if os.path.isdir(user_img_dir):
                shutil.rmtree(user_img_dir, ignore_errors=True)
                removed_dirs += 1

        print('级联清理汇总：')
        for k, v in sorted(total.items()):
            if v:
                print(f'  {k}: {v}')
        print(f'图库磁盘目录已删 {removed_dirs} 个')
        print(f'剩余 {User.query.count()} 个用户：')
        for u in User.query.order_by(User.id).all():
            print(f'  id={u.id} username={u.username} role={u.role}')


if __name__ == '__main__':
    main()
