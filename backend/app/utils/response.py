# 统一接口返回格式
# 约定：{ "code": 0, "message": "success", "data": ... }
#   code == 0 表示成功，非 0 表示业务/请求错误
import os

from flask import Blueprint, jsonify

api_bp = Blueprint('api', __name__, url_prefix='/api')


def success(data=None, message='success', code=0, status=200):
    """统一成功返回"""
    return jsonify({'code': code, 'message': message, 'data': data}), status


def error(message='error', code=1, data=None, status=400):
    """统一错误返回"""
    return jsonify({'code': code, 'message': message, 'data': data}), status


@api_bp.route('/health', methods=['GET'])
def health():
    """健康检查接口：验证后端服务可用"""
    return success({'status': 'ok', 'env': os.getenv('FLASK_ENV', 'development')})
