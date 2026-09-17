# 群合并推送：pushplus 开放接口（QQ 群）的单元测试。
# 隔离外部 HTTP（monkeypatch requests.post），验证 send_qq 与 send_channel 的 qq 分支
# 是否正确构造「消息 token 走 URL 路径 /send/{token}」+ channel=qq / option=qq_code 载荷，
# 并处理业务码与异常。
import requests

from app.services.push_render import send_channel, send_qq, build_ctx

BASE = 'https://www.pushplus.plus/send'


class _FakeSchedule:
    def __init__(self, task_type='dorm'):
        self.id = 0
        self.task_type = task_type


class _FakeAcc:
    account = 'tc_qq_acc'


def _capture(monkeypatch, payload=None):
    """拦截 requests.post；payload 缺省返回业务成功码，可覆盖模拟平台拒绝/非 JSON。"""
    calls = []

    def fake_post(url, **kw):
        calls.append((url, kw))
        if payload is None:
            body = {'code': 200, 'msg': 'ok'}
        elif payload == 'nonjson':
            return type('R', (), {
                'status_code': 502,
                'json': lambda self: (_ for _ in ()).throw(ValueError('bad json')),
            })()
        else:
            body = payload
        return type('R', (), {'status_code': 200, 'json': lambda self: body})()

    monkeypatch.setattr(requests, 'post', fake_post)
    return calls


# ───────────── send_qq（群合并汇总专用入口） ─────────────

def test_send_qq_success_builds_qq_payload(monkeypatch):
    """成功路径：token 走 URL 路径 /send/{token} + channel=qq + option=qq_code + template=markdown；无 access-key 头"""
    calls = _capture(monkeypatch)
    ok, err = send_qq('TKtest', 'GROUP123', '汇总标题', '汇总内容', template='markdown')
    assert ok is True and err == ''
    assert len(calls) == 1
    url, kw = calls[0]
    assert url == f'{BASE}/TKtest'
    assert kw.get('headers') is None or kw.get('headers') == {}
    body = kw['json']
    assert body['channel'] == 'qq'
    assert body['option'] == 'GROUP123'
    assert body['template'] == 'markdown'
    assert body['title'] == '汇总标题'
    assert body['content'] == '汇总内容'


def test_send_qq_default_template_is_markdown(monkeypatch):
    """未显式传 template 时回落 markdown（群汇总默认格式）"""
    calls = _capture(monkeypatch)
    send_qq('TK', 'G', 't', 'c')
    assert calls[0][1]['json']['template'] == 'markdown'


def test_send_qq_missing_token(monkeypatch):
    calls = _capture(monkeypatch)
    ok, err = send_qq('', 'GROUP123', 't', 'c')
    assert ok is False and 'Token' in err
    assert calls == []  # 前置校验失败，不发请求


def test_send_qq_missing_qq_code(monkeypatch):
    calls = _capture(monkeypatch)
    ok, err = send_qq('TKtest', None, 't', 'c')
    assert ok is False and 'QQ 群' in err
    assert calls == []


def test_send_qq_rejected_on_business_code(monkeypatch):
    """HTTP 200 但 code!=200（如 token 失效）必须判失败并带回平台原因"""
    calls = _capture(monkeypatch, {'code': 903, 'msg': 'token验证失败'})
    ok, err = send_qq('TKbad', 'G', 't', 'c')
    assert ok is False
    assert 'code=903' in err and 'token验证失败' in err


def test_send_qq_non_json_response_is_failure(monkeypatch):
    """响应体非 JSON（网关错误页）不得假报成功"""
    calls = _capture(monkeypatch, 'nonjson')
    ok, err = send_qq('TK', 'G', 't', 'c')
    assert ok is False
    assert '502' in err and '非 JSON' in err


def test_send_qq_title_length_guard(monkeypatch):
    """标题超长须按 PushPlus 上限截断，避免被平台截断或拒绝"""
    from app.services.push_render import PUSHPLUS_TITLE_MAX
    long_title = '汇总标题' * 50
    calls = _capture(monkeypatch)
    send_qq('TK', 'G', long_title, 'c')
    sent_title = calls[0][1]['json']['title']
    assert len(sent_title) <= PUSHPLUS_TITLE_MAX
    assert sent_title.endswith('…')


# ───────────── send_channel 的 qq 分支（单人卡片经开放接口） ─────────────

def test_send_channel_qq_branch_builds_payload(monkeypatch):
    """send_channel('qq', {token, qqCode}, ctx)：走开放接口 /send/{token}、载荷正确、无 access-key 头；
    html 模板在 QQ 通道回落 markdown（QQ 不支持 HTML）"""
    calls = _capture(monkeypatch)
    ctx = build_ctx(_FakeAcc(), _FakeSchedule(), {}, 'success')
    ok, err = send_channel('qq', {'token': 'TKtest', 'qqCode': 'GROUP123'}, ctx)
    assert ok is True and err == ''
    url, kw = calls[0]
    assert url == f'{BASE}/TKtest'
    assert kw.get('headers') is None or kw.get('headers') == {}
    body = kw['json']
    assert body['channel'] == 'qq'
    assert body['option'] == 'GROUP123'
    # QQ 通道 html 回落 markdown；标题含账号姓名 + 状态
    assert body['template'] == 'markdown'
    assert '成功' in body['title']


def test_send_channel_qq_missing_token(monkeypatch):
    calls = _capture(monkeypatch)
    ctx = build_ctx(_FakeAcc(), _FakeSchedule(), {}, 'success')
    ok, err = send_channel('qq', {'qqCode': 'G'}, ctx)
    assert ok is False and 'Token' in err
    assert calls == []


def test_send_channel_qq_omits_option_without_qq_code(monkeypatch):
    """send_channel 的 qq 分支对 qqCode 缺失仅省略 option（发给本人），不视为失败"""
    calls = _capture(monkeypatch)
    ctx = build_ctx(_FakeAcc(), _FakeSchedule(), {}, 'success')
    ok, err = send_channel('qq', {'token': 'TKtest'}, ctx)
    assert ok is True and err == ''
    body = calls[0][1]['json']
    assert body['channel'] == 'qq'
    assert 'option' not in body


def test_send_channel_qq_rejected_on_business_code(monkeypatch):
    calls = _capture(monkeypatch, {'code': 903, 'msg': 'token验证失败'})
    ctx = build_ctx(_FakeAcc(), _FakeSchedule(), {}, 'success')
    ok, err = send_channel('qq', {'token': 'TKbad', 'qqCode': 'G'}, ctx)
    assert ok is False
    assert 'code=903' in err and 'token验证失败' in err
