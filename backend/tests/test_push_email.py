# 邮件通道多收件人：收件人解析/归一化、SMTP 实际投递列表、凭证校验口径。
# 一对一曾把「一个发件人多个收件人」堵死（收件人被写进凭证且单值必填）。
import email
import email.header
import smtplib

import pytest

from app.schemas.pools_schema import load_credential
from app.services.push_render import parse_recipients, send_email
from app.utils.validators import validate_recipients


@pytest.mark.parametrize('raw,expected', [
    ('a@x.com', ['a@x.com']),
    ('a@x.com, b@y.com', ['a@x.com', 'b@y.com']),
    ('a@x.com;b@y.com', ['a@x.com', 'b@y.com']),
    ('a@x.com，b@y.com', ['a@x.com', 'b@y.com']),      # 中文逗号
    ('a@x.com；b@y.com', ['a@x.com', 'b@y.com']),      # 中文分号
    (' a@x.com   b@y.com ', ['a@x.com', 'b@y.com']),   # 空白分隔
    ('a@x.com,,a@x.com', ['a@x.com']),                 # 去重保序
    ('', []),
    (None, []),
])
def test_parse_recipients(raw, expected):
    assert parse_recipients(raw) == expected


def test_validate_recipients_normalizes_and_rejects():
    ok, norm, _, _ = validate_recipients('b@y.com , a@x.com; b@y.com')
    assert ok and norm == 'b@y.com, a@x.com'

    ok, _, msg, code = validate_recipients('a@x.com, 不是邮箱')
    assert not ok and code == 4321 and '不是邮箱' in msg

    # 账号侧允许「不覆盖收件人」，故 required=False 时空值合法
    ok, norm, _, _ = validate_recipients('', required=False)
    assert ok and norm == ''

    ok, _, _, _ = validate_recipients('a@x.com, b@y.com', required=True)
    assert ok


def _fake_smtp(monkeypatch):
    sent = []

    class FakeSMTP:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            pass

        def login(self, *a):
            pass

        def sendmail(self, frm, tos, msg):
            sent.append((frm, tos, msg))

    monkeypatch.setattr(smtplib, 'SMTP', FakeSMTP)
    return sent


def test_send_email_delivers_to_all_recipients(monkeypatch):
    sent = _fake_smtp(monkeypatch)
    fields = {'emailSmtp': 'smtp.example.com', 'emailFrom': 'a@b.com', 'emailPass': 'pw',
              'emailTo': 'x@y.com; z@w.com, x@y.com'}
    send_email(fields, '标题', '正文')

    assert len(sent) == 1
    frm, tos, msg = sent[0]
    assert frm == 'a@b.com'
    assert tos == ['x@y.com', 'z@w.com']          # 一次投递给全部收件人，已去重

    # 中文主题按 RFC2047 编码，故解码后再比对，避免拿原始报文体猜格式
    parsed = email.message_from_string(msg)
    assert parsed['To'] == 'x@y.com, z@w.com'
    subject = email.header.make_header(email.header.decode_header(parsed['Subject']))
    assert str(subject) == '标题'


def test_send_email_without_recipient_raises():
    with pytest.raises(ValueError):
        send_email({'emailSmtp': 'smtp.x', 'emailFrom': 'a@b.com',
                    'emailPass': 'pw', 'emailTo': '  '}, 's', 'b')


def test_credential_email_normalizes_multi_recipients():
    ok, data, msg, _ = load_credential({
        'channel': 'email', 'name': '我的邮箱',
        'fields': {'emailSmtp': 'smtp.example.com', 'emailFrom': 'a@b.com',
                   'emailPass': 'pw', 'emailTo': 'b@y.com , a@x.com; b@y.com'},
    })
    assert ok, msg
    assert data['fields']['emailTo'] == 'b@y.com, a@x.com'


def test_credential_email_rejects_bad_recipient():
    ok, _, msg, code = load_credential({
        'channel': 'email', 'name': 'x',
        'fields': {'emailSmtp': 'smtp.example.com', 'emailFrom': 'a@b.com',
                   'emailPass': 'pw', 'emailTo': 'a@x.com, nope'},
    })
    assert not ok and code == 4321 and 'nope' in msg
