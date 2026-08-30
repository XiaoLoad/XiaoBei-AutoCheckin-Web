# 地图服务配置：登录用户读取高德 Web 端 Key/安全密钥（位置池「地图拾取」用）。
# Key/安全码按高德模型本就在浏览器侧公开使用，防盗用靠高德控制台的域名白名单与配额管理；
# 未配置（Key 为空）时前端隐藏拾取入口，手动输入不受影响。
from flask import Blueprint

from app.models.system_config import get_setting
from app.utils.auth import token_required
from app.utils.response import success

bp = Blueprint('map', __name__, url_prefix='/api/map')


@bp.route('/config', methods=['GET'])
@token_required
def map_config():
    key = (get_setting('amap_web_key') or '').strip()
    return success({
        'provider': 'amap',
        'key': key,
        'securityCode': (get_setting('amap_security_code') or '').strip() if key else '',
    })
