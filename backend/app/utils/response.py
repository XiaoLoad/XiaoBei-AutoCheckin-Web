# 统一接口返回格式
# 约定：{ "code": 0, "message": "success", "data": ... }
#   code == 0 表示成功，非 0 表示业务/请求错误
# 职责单一：仅负责响应格式化，不含任何路由定义（健康检查路由见 routes/health.py）。
from flask import jsonify


def success(data=None, message='success', code=0, status=200):
    """统一成功返回"""
    return jsonify({'code': code, 'message': message, 'data': data}), status


def error(message='error', code=1, data=None, status=400):
    """统一错误返回"""
    return jsonify({'code': code, 'message': message, 'data': data}), status
