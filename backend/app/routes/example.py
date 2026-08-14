# 示例蓝图：演示一个标准业务模块的接口组织方式
# 前缀 /api/example
from flask import Blueprint, request

from app.utils.response import success, error

bp = Blueprint('example', __name__, url_prefix='/api/example')

# 内存中的示例数据（真实项目应替换为数据库模型）
_EXAMPLES = [
    {'id': 1, 'name': '示例数据一'},
    {'id': 2, 'name': '示例数据二'},
]


@bp.route('', methods=['GET'])
def list_examples():
    """获取示例列表（支持 keyword 模糊过滤，演示前后端联通）"""
    keyword = (request.args.get('keyword') or '').strip()
    if keyword:
        data = [e for e in _EXAMPLES if keyword in e['name']]
    else:
        data = _EXAMPLES
    return success(data)


@bp.route('/<int:example_id>', methods=['GET'])
def get_example(example_id):
    """获取单条示例"""
    item = next((e for e in _EXAMPLES if e['id'] == example_id), None)
    if not item:
        return error(message='示例不存在', code=404, status=404)
    return success(item)


@bp.route('', methods=['POST'])
def create_example():
    """创建示例（演示请求体解析）"""
    payload = request.get_json(silent=True) or {}
    name = payload.get('name')
    if not name:
        return error(message='name 不能为空', code=400, status=400)
    new_id = max((e['id'] for e in _EXAMPLES), default=0) + 1
    item = {'id': new_id, 'name': name}
    _EXAMPLES.append(item)
    return success(item, message='创建成功', status=201)
