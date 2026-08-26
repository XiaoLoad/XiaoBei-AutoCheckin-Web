# backend/tests/test_config_schema.py
from app.schemas.config_schema import load_create, load_update, sanitize_config


def _valid_cfg():
    return {
        'time': {'signTime': {'hour': 8, 'minute': 0}, 'startHour': 8, 'endHour': 22,
                 'weekdays': [1, 2, 3, 4, 5], 'randomDelayMax': 5, 'mode': 'normal'},
        'locationId': None,
        'remarks': ['签到'],
        'image': {'enabled': False, 'strategy': 'recycle'},
        'push': {'channels': [], 'useOwnCredential': True,
                 'credIds': {}, 'cred': {}, 'notify': {}},
        'advanced': {'uaTemplateId': None, 'customUa': ''},
    }


def test_sanitize_ok():
    ok, cfg = sanitize_config(_valid_cfg())
    assert ok and cfg['time']['weekdays'] == [1, 2, 3, 4, 5]


def test_sanitize_rejects_non_dict_and_unknown_top_key():
    assert sanitize_config(None)[0] is False
    bad = _valid_cfg()
    bad['hacker'] = 1
    assert sanitize_config(bad)[0] is False


def test_sanitize_rejects_bad_weekdays():
    cfg = _valid_cfg()
    cfg['time']['weekdays'] = [0, 9]
    assert sanitize_config(cfg)[0] is False


def test_sanitize_rejects_unhashable_weekdays():
    cfg = _valid_cfg()
    cfg['time']['weekdays'] = [[1], {'a': 1}]
    assert sanitize_config(cfg)[0] is False


def test_load_create_requires_name():
    ok, data, msg, code = load_create({'config': _valid_cfg()})
    assert not ok and code == 4200


def test_load_create_ok_strips_name():
    ok, data, _, _ = load_create({'name': '  标准套 ', 'config': _valid_cfg()})
    assert ok and data['name'] == '标准套'


def test_load_update_partial():
    ok, data, _, code = load_update({})
    assert not ok and code == 4202
    ok, data, _, _ = load_update({'name': '新名'})
    assert ok and data == {'name': '新名'}
