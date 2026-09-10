# 提交签到适配器层单测（模块 E）：mock requests，验证 know/sign 双模块契约与结果判定。
# 契约来源：接口文档 v1.5 §4.14/§4.16 + 旧版 XiaoBeiCheck 生产实证（成功码/302/双文件部分）。
import os

import pytest
import requests as real_requests

import app.services.b_platform.real as real
from app.services.b_platform.base import BPlatformError
from app.services.geo import apply_location_jitter, haversine_m

os.environ.pop('CHECKIN_DRYRUN', None)

SESSION = {'token': 'tok', 'ua': 'UA/1'}


class FakeResp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if self._payload is None:
            raise ValueError('not json')
        return self._payload


def _list_rows(finished=0):
    return {'code': 200, 'msg': '查询成功', 'total': 1, 'rows': [
        {'id': 58088, 'knowingName': '07.02查寝签到', 'startDate': '2026-06-07',
         'endDate': '2026-06-07', 'startTime': '19:00:00', 'endTime': '23:00:00',
         'isPicture': 1, 'isFinishKnowing': finished},
    ]}


def _detail():
    return {'code': 200, 'msg': '操作成功', 'data': {
        'id': 58088,
        'location': '[{"alias":"校区","latitude":"29.34","longitude":"106.53","location":"某楼","radius":"500"}]',
    }}


# ── find_active_task ──

def test_find_active_task_picks_unfinished_and_loads_fence(monkeypatch):
    calls = []

    def fake_request(method, url, **kw):
        calls.append(url)
        if url.endswith('/student/know/list'):
            return FakeResp(_list_rows(finished=0))
        return FakeResp(_detail())

    monkeypatch.setattr(real.requests, 'request', fake_request)
    ctx = real.RealAdapter().find_active_task(SESSION, 'dorm')
    assert ctx['task']['id'] == 58088
    assert ctx['task']['needPhoto'] is False      # isPicture=1 → 无需图（反直觉布尔）
    assert ctx['fence'][0]['radius'] == '500'
    assert calls[0].endswith('/student/know/list')  # 提交只能取自 /list


def test_find_active_task_reports_finished_when_all_signed(monkeypatch):
    """/list 有行但全部已签：不返回 None，而是带出 finished_task——
    None 会让上层把「已签到」误报成「当前无进行中的签到任务」，事后排查误判漏签。"""
    monkeypatch.setattr(real.requests, 'request',
                        lambda m, u, **kw: FakeResp(_list_rows(finished=1)))
    ctx = real.RealAdapter().find_active_task(SESSION, 'dorm')
    assert ctx['task'] is None
    assert ctx['finished_task']['id'] == 58088


def test_find_active_task_both_none_when_no_rows(monkeypatch):
    """/list 无任何行 = 真的没有进行中任务，两个字段都为 None"""
    monkeypatch.setattr(real.requests, 'request',
                        lambda m, u, **kw: FakeResp({'code': 200, 'rows': []}))
    ctx = real.RealAdapter().find_active_task(SESSION, 'dorm')
    assert ctx['task'] is None
    assert ctx['finished_task'] is None


def test_find_active_task_sign_module_paths(monkeypatch):
    urls = []

    def fake_request(method, url, **kw):
        urls.append(url)
        if url.endswith('/student/sign/list'):
            return FakeResp({'code': 200, 'rows': [
                {'id': 36589, 'signName': '06.26查课签到', 'isPictrue': 0,
                 'isFinishSign': 0, 'startTime': '09:30', 'endTime': '12:10'}]})
        return FakeResp({'code': 200, 'data': {'id': 36589, 'location': '[]'}})

    monkeypatch.setattr(real.requests, 'request', fake_request)
    ctx = real.RealAdapter().find_active_task(SESSION, 'activity')
    assert ctx['task']['id'] == 36589
    assert ctx['task']['needPhoto'] is True       # isPictrue=0 → 需要图
    assert any(u.endswith('/student/sign/36589') for u in urls)


# ── submit_checkin ──

def test_submit_multipart_know_contract(monkeypatch):
    captured = {}

    def fake_post(url, **kw):
        captured['url'] = url
        captured['data'] = kw.get('data')
        captured['files'] = kw.get('files')
        return FakeResp({'code': 200, 'msg': '操作成功'})

    monkeypatch.setattr(real.requests, 'post', fake_post)
    image = {'bytes': b'jpeg-bytes', 'filename': '1760273554079a.jpeg'}
    result = real.RealAdapter().submit_checkin(
        SESSION, 'dorm', 48241, '106.53:29.34', '某楼', '打卡', image)

    assert result.status == 'success'
    assert captured['url'].endswith('/student/know/updateStudentKnow')
    assert captured['data']['knowingId'] == '48241'          # 字符串化
    assert captured['data']['location'] == '106.53:29.34'    # 经度在前
    assert captured['data']['size'] == '1'
    # photo 与 file0 为同图双文件部分
    assert captured['files']['photo'][0] == captured['files']['file0'][0] == '1760273554079a.jpeg'
    assert captured['files']['photo'][1] == b'jpeg-bytes'


def test_submit_no_image_json_contract(monkeypatch):
    captured = {}

    def fake_post(url, **kw):
        captured['url'] = url
        captured['json'] = kw.get('json')
        return FakeResp({'code': 200, 'msg': '操作成功'})

    monkeypatch.setattr(real.requests, 'post', fake_post)
    result = real.RealAdapter().submit_checkin(SESSION, 'dorm', 48241, '106.53:29.34', '', '', None)

    assert result.status == 'success'
    assert captured['url'].endswith('/student/know/updateStudentKnowNoFile')
    assert captured['json']['size'] == '0'
    assert captured['json']['photo'] == []


def test_submit_accepts_6111_as_success(monkeypatch):
    monkeypatch.setattr(real.requests, 'post',
                        lambda url, **kw: FakeResp({'code': 6111, 'msg': 'x'}))
    result = real.RealAdapter().submit_checkin(SESSION, 'dorm', 1, '1:1', '', '', None)
    assert result.status == 'success'


def test_submit_msg_302_is_captcha_fail(monkeypatch):
    monkeypatch.setattr(real.requests, 'post',
                        lambda url, **kw: FakeResp({'code': 200, 'msg': '302'}))
    result = real.RealAdapter().submit_checkin(SESSION, 'dorm', 1, '1:1', '', '', None)
    assert result.status == 'fail'
    assert '行为验证码' in result.fail_reason


def test_submit_token_expired_raises_credential(monkeypatch):
    monkeypatch.setattr(real.requests, 'post',
                        lambda url, **kw: FakeResp({'code': 500, 'msg': 'token失效'}))
    with pytest.raises(BPlatformError) as ei:
        real.RealAdapter().submit_checkin(SESSION, 'dorm', 1, '1:1', '', '', None)
    assert ei.value.kind == 'credential'


def test_submit_business_error_fails_without_retry(monkeypatch):
    calls = []

    def fake_post(url, **kw):
        calls.append(url)
        return FakeResp({'code': 500, 'msg': '不在签到时间内'})

    monkeypatch.setattr(real.requests, 'post', fake_post)
    result = real.RealAdapter().submit_checkin(SESSION, 'dorm', 1, '1:1', '', '', None)
    assert result.status == 'fail'
    assert '不在签到时间内' in result.fail_reason
    assert len(calls) == 1        # 业务错误不重试


def test_submit_network_error_retries_then_succeeds(monkeypatch):
    calls = []
    monkeypatch.setattr(real.time, 'sleep', lambda s: None)

    def fake_post(url, **kw):
        calls.append(url)
        if len(calls) < 3:
            raise real_requests.ConnectionError('reset')
        return FakeResp({'code': 200, 'msg': '操作成功'})

    monkeypatch.setattr(real.requests, 'post', fake_post)
    result = real.RealAdapter().submit_checkin(SESSION, 'dorm', 1, '1:1', '', '', None)
    assert result.status == 'success'
    assert len(calls) == 3


def test_submit_dryrun_skips_request(monkeypatch):
    monkeypatch.setenv('CHECKIN_DRYRUN', '1')
    called = []

    monkeypatch.setattr(real.requests, 'post', lambda url, **kw: called.append(url) or FakeResp({}))
    result = real.RealAdapter().submit_checkin(SESSION, 'dorm', 1, '1:1', '', '备注', None)
    monkeypatch.delenv('CHECKIN_DRYRUN')

    assert called == []
    assert result.status == 'skip'
    assert '演练' in result.fail_reason


# ── geo 工具 ──

def test_jitter_stays_within_radius():
    for _ in range(50):
        lat, lng = apply_location_jitter('29.34', '106.53', 10)
        d = haversine_m(lat, lng, 29.34, 106.53)
        assert d is not None and d <= 10.5


def test_haversine_known_distance():
    # 同一经线 1 纬度 ≈ 111.32km（允许 1% 误差）
    d = haversine_m(29.0, 106.5, 30.0, 106.5)
    assert abs(d - 111320) < 11132


def test_haversine_invalid_returns_none():
    assert haversine_m('', None, 1, 2) is None
