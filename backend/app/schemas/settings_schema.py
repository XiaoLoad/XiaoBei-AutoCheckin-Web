# 系统设置入参校验层：与 user_schema 同风格，作为前后端契约的权威定义。
# 校验依据是 system_config.DEFAULTS 注册表（type/min/max），新增配置项自动纳入。
from app.models.system_config import DEFAULTS, SystemConfig, get_setting
from config import get_config as _flask_config


def _env_session_hours_default():
    """session_hours 未落库时的兜底默认值来自 .env 的 JWT_EXPIRES_HOURS"""
    try:
        return int(_flask_config().JWT_EXPIRES_HOURS)
    except Exception:
        return 12


def effective_defaults():
    """给前端表单用的默认值视图：session_hours 的 None 替换为 env 兜底值"""
    defaults = {}
    for key, spec in DEFAULTS.items():
        value = spec['value']
        if value is None:
            value = _env_session_hours_default()
        defaults[key] = value
    return defaults


def load_update(payload):
    """
    校验『批量保存系统设置』入参 { settings: {key: value} }。
    返回 (ok, data, message, code)。仅接受注册表中已定义的键，逐键按类型与范围校验。
    """
    payload = payload or {}
    settings = payload.get('settings')
    if not isinstance(settings, dict) or not settings:
        return False, None, '缺少待保存的配置项', 4000

    data = {}
    for key, raw in settings.items():
        spec = DEFAULTS.get(key)
        if not spec:
            return False, None, f'不支持的配置项: {key}', 4001
        if spec['type'] == 'bool':
            if not isinstance(raw, bool):
                return False, None, f'{spec["label"]} 必须为开关值', 4002
            data[key] = raw
            continue

        # str 类型：文本配置（如高德地图 Key），去首尾空白
        if spec['type'] == 'str':
            if not isinstance(raw, str):
                return False, None, f'{spec["label"]} 必须为文本', 4003
            data[key] = raw.strip()
            continue

        # int 类型：兼容前端把数字输入框值传成字符串的情况
        if isinstance(raw, bool) or not isinstance(raw, (int, str)):
            return False, None, f'{spec["label"]} 必须为数字', 4003
        try:
            num = int(str(raw).strip())
        except (TypeError, ValueError):
            return False, None, f'{spec["label"]} 必须为整数', 4003
        lo, hi = spec.get('min'), spec.get('max')
        if (lo is not None and num < lo) or (hi is not None and num > hi):
            return False, None, f'{spec["label"]} 需在 {lo} ~ {hi} 之间', 4004
        data[key] = num

    # 密码最小长度收紧时不低于 4 位，防止误配为 0/1 导致弱口令
    if 'password_min_length' in data and data['password_min_length'] < DEFAULTS['password_min_length']['min']:
        return False, None, '密码最小长度不能低于 4 位', 4004

    # 会话时长与当前生效值一致时也允许保存（幂等），但至少要有一项变更才值得写库
    return True, {'settings': data}, '', 0


def describe_settings():
    """导出设置项元数据（label/desc/type/范围/当前值/默认值/最后修改人），驱动前端表单渲染"""
    # 一次性取回全部落库行，用于补充审计线索（最后修改人/时间）；未落库的键无此信息
    try:
        rows = {row.key: row for row in SystemConfig.query.all()}
    except Exception:
        rows = {}
    items = []
    for key, spec in DEFAULTS.items():
        current = get_setting(key)
        if key == 'session_hours' and current is None:
            current = _env_session_hours_default()
        item = {
            'key': key,
            'label': spec['label'],
            'desc': spec['desc'],
            'type': spec['type'],
            'current': current,
            'default': spec['value'] if spec['value'] is not None else _env_session_hours_default(),
        }
        if spec['type'] == 'int':
            item['min'] = spec.get('min')
            item['max'] = spec.get('max')
        row = rows.get(key)
        if row is not None:
            item['updated_by'] = row.updated_by or ''
            item['updated_at'] = row.updated_at.strftime('%Y-%m-%d %H:%M') if row.updated_at else ''
        items.append(item)
    return items
