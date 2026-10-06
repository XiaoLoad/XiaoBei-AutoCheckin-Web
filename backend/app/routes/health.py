# 健康检查蓝图：验证后端服务可用
# 从 utils/response 中独立出来，使响应工具只负责格式化、不承担路由职责。
# 无鉴权暴露面：只回固定状态，不回 env 等部署信息（未认证可探测）。
from flask import Blueprint

from app.utils.response import success

bp = Blueprint('health', __name__, url_prefix='/api')


@bp.route('/health', methods=['GET'])
def health():
    """健康检查接口：验证后端服务可用"""
    return success({'status': 'ok'})
