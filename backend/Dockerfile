# 后端镜像：Flask + Gunicorn 单实例（调度器内存态，多 worker 会重复打卡，见 docker-compose.yml）
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 先装依赖再拷代码，代码变更不触发 pip 重装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# 非 root 运行；-m 确保 home 目录存在且属主正确（gunicorn 26 control server 会在
# 用户 home 下落控制 socket，目录缺失/属主不对会让 worker 加载失败）
COPY . .
RUN groupadd -r appuser \
    && useradd -r -g appuser -m -d /home/appuser appuser \
    && chown appuser:appuser /home/appuser \
    && mkdir -p uploads logs \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

# 健康检查打无鉴权的 /api/health（只回状态，不泄露部署信息）
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=4)" || exit 1

# 单实例铁律：-w 1 写死在镜像内，防止误用多 worker。
# 入口是 wsgi:app——包 app/ 与同名模块 app.py 冲突（包优先），
# gunicorn 解析 "app:app" 会命中包而非入口模块
CMD ["gunicorn", "-w", "1", "--threads", "8", "-b", "0.0.0.0:5000", "--access-logfile", "-", "wsgi:app"]
