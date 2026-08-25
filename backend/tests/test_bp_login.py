# 登录链路单测：mock requests 层，断言请求体形状与 token 提取
from app.services.b_platform.real import RealAdapter
from app.services.b_platform.base import BPlatformError


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_login_success_shape(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured['captcha_url'] = url
        return FakeResp({'code': 200, 'msg': '操作成功', 'img': 'xx',
                         'showCode': 'VKD6', 'uuid': 'u-123'})

    def fake_post(url, json=None, headers=None, timeout=None):
        captured['login_url'] = url
        captured['login_body'] = json
        return FakeResp({'msg': '操作成功', 'code': 200,
                         'token': 'tok-abc'})

    monkeypatch.setattr('app.services.b_platform.real.requests.get', fake_get)
    monkeypatch.setattr('app.services.b_platform.real.requests.post', fake_post)

    adapter = RealAdapter()
    token = adapter.login('18290449672', 'Lovexjw2095')

    assert token == 'tok-abc'
    assert captured['login_body']['username'] == '18290449672'
    # 密码必须是 Base64 编码后的值
    import base64
    expect = base64.b64encode('Lovexjw2095'.encode()).decode()
    assert captured['login_body']['password'] == expect
    assert captured['login_body']['code'] == 'VKD6'
    assert captured['login_body']['uuid'] == 'u-123'
    assert captured['login_body']['appUuid'] == ''


def test_login_wrong_password(monkeypatch):
    monkeypatch.setattr(
        'app.services.b_platform.real.requests.get',
        lambda url, headers=None, timeout=None: FakeResp(
            {'code': 200, 'showCode': 'ABCD', 'uuid': 'u'})
    )
    monkeypatch.setattr(
        'app.services.b_platform.real.requests.post',
        lambda url, json=None, headers=None, timeout=None: FakeResp(
            {'code': 500, 'msg': '密码错误'})
    )
    import pytest
    with pytest.raises(BPlatformError) as ei:
        RealAdapter().login('x', 'wrong')
    assert ei.value.kind == 'credential'
