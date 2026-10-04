# 应用入口（供 Gunicorn / 生产环境使用）
# [部署约束] 调度器随 Web 进程启动且 job 存于内存，全系统只允许单实例运行，
# 多 worker 会各自注册同一批 cron 任务导致同一账号重复打卡。形如：
#   gunicorn -w 1 --threads 8 "app:create_app()"
# 横向扩容 Web 前需先将调度器拆分为独立进程（Web 进程置 SCHEDULER_ENABLED=0）。
import os

from app import create_app

# 缺省 production（而非 development）：本入口自述供 Gunicorn/生产使用，若缺省落在
# development，误漏配 FLASK_ENV 时会以 Werkzeug 调试器 + 0.0.0.0 暴露，且生产密钥
# 守护（_assert_production_secrets）被整体绕过。本地开发请用 run.py（缺省 development），
# 或在 backend/.env 中显式写 FLASK_ENV=development。
app = create_app(os.getenv('FLASK_ENV', 'production'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
