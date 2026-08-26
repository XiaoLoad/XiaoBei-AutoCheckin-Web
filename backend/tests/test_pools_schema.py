from app.schemas.pools_schema import (load_location, load_ua, load_credential,
                                      load_credential_update, mask_fields,
                                      required_missing)


def test_location_ok_and_offset_clamp():
    ok, d, _, _ = load_location({'name': '寝室', 'lat': '30.5', 'lng': '120.4', 'offset': 9999})
    assert ok and d['offset_m'] == 500 and isinstance(d['lat'], float)


def test_location_rejects_bad_latlng():
    assert not load_location({'name': 'x', 'lat': 'abc', 'lng': 120})[0]
    assert not load_location({'name': '', 'lat': 30, 'lng': 120})[0]


def test_ua_requires_content():
    ok, d, _, _ = load_ua({'content': ' Mozilla/5.0 ', 'remark': '小米'})
    assert ok and d['content'] == 'Mozilla/5.0'
    assert not load_ua({'remark': '空'})[0]


def test_credential_create_validates_channel_fields():
    ok, d, _, _ = load_credential({'channel': 'serverchan', 'name': '主力',
                                   'fields': {'serverchanKey': 'SCT123'}})
    assert ok and d['fields'] == {'serverchanKey': 'SCT123'}
    assert not load_credential({'channel': 'wechat', 'name': 'x', 'fields': {}})[0]
    assert not load_credential({'channel': 'email', 'name': 'x',
                                'fields': {'emailSmtp': ''}})[0]


def test_credential_update_masked_values_dropped():
    ok, d, _, _ = load_credential_update({'fields': {'serverchanKey': '••••abcd',
                                                     'serverchanKey2': 'new'}})
    assert ok and d['fields'] == {'serverchanKey2': 'new'}
    ok, d, _, code = load_credential_update({})
    assert not ok and code == 4322


def test_mask_and_required():
    m = mask_fields({'serverchanKey': 'SCT12345678', 'note': '明文'})
    assert m['serverchanKey'] == '••••5678' and m['note'] == '明文'
    miss = required_missing('email', {'emailSmtp': 's', 'emailFrom': 'f'})
    assert set(miss) == {'emailPass', 'emailTo'}


def test_credential_rejects_composite_field_values():
    ok, d, _, code = load_credential({'channel': 'serverchan', 'name': 'x',
                                      'fields': {'serverchanKey': {'nested': 1}}})
    assert not ok and code == 4321


def test_required_missing_guards_non_dict():
    assert required_missing('email', None) == ['emailSmtp', 'emailFrom', 'emailPass', 'emailTo']
    assert required_missing('email', ['bad']) == ['emailSmtp', 'emailFrom', 'emailPass', 'emailTo']
