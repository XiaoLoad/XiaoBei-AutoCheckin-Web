# 系统设置蓝图：管理员读取/保存运行期系统参数；公开端点仅暴露无敏感性的开关。
# 前缀 /api/settings
from flask import Blueprint, request

from app.extensions import db
from app.models.system_config import get_setting, set_setting
from app.schemas.settings_schema import describe_settings, load_update
from app.utils.auth import admin_required
from app.utils.response import error, success

bp = Blueprint('settings', __name__, url_prefix='/api/settings')


@bp.route('', methods=['GET'])
@admin_required
def list_settings():
    """设置项全量读取：当前值 + 元数据（label/desc/范围/默认值），驱动管理端表单"""
    return success({'items': describe_settings()})


@bp.route('', methods=['PUT'])
@admin_required
def update_settings():
    """
    批量保存：body { settings: {key: value} }。
    逐键校验（见 settings_schema）后 upsert 落库，并记录操作人作为审计线索；
    会话时长等参数对下一次签发生效，无需重启服务。
    """
    payload = request.get_json(silent=True) or {}
    ok, data, msg, code = load_update(payload)
    if not ok:
        return error(message=msg, code=code, status=400)

    operator = getattr(request.current_user, 'username', '')
    for key, value in data['settings'].items():
        set_setting(key, value, operator=operator)
    db.session.commit()

    return success({'items': describe_settings()}, message='设置已保存')


@bp.route('/public', methods=['GET'])
def public_settings():
    """
    公开配置：无需登录，仅暴露不影响安全的展示型开关（注册是否开放），
    供注册页在未登录状态下渲染引导文案。切勿在此追加敏感配置项。
    数据库不可用时 get_setting 回退默认值，保证注册入口不被误关死。
    """
    return success({'registration_enabled': bool(get_setting('registration_enabled'))})
