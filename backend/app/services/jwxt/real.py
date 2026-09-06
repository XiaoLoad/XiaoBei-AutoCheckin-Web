# 强智教务 HTTP 客户端（单账号会话）。字段与流程均为本校 jw.cqcst.edu.cn 实测结论
# （设计文档 §2.2/§2.7）：登录仅 POST encoded 一个字段到 /xk/LoginToXk；课表 GET
# xskb_list.do（不带参数=当前学期全学期合并视图）；教学周历 GET jxzl/jxzl_query。
# 实测该校服务器存在秒级挂起（连续登录时偶发 read timeout），故读取超时放宽且
# 网络/超时类失败自动重试一次；连接与读取超时可用 JWXT_TIMEOUT 调整。
import base64
import logging
import os
import time

import requests

from app.services.jwxt.base import JwxtError
from app.services.jwxt.parser import parse_current_semester, parse_timetable, parse_week_calendar

log = logging.getLogger('jwxt')

_DEFAULT_BASE = 'http://jw.cqcst.edu.cn/cqdxcskjxy_jsxsd'
_CONNECT_TIMEOUT = 6
_NET_RETRIES = 2          # 网络/超时类失败总尝试次数（含首次）
_NET_RETRY_BACKOFF = 2    # 重试前退避秒数
_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
       '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')


def _read_timeout():
    try:
        return int(os.getenv('JWXT_TIMEOUT', '20') or 20)
    except ValueError:
        return 20


def _timeout():
    return (_CONNECT_TIMEOUT, _read_timeout())


def encode_credentials(student_no, password):
    """强智前端 encodeInp 的等价实现：标准 base64 后以 %%% 拼接（本校实测）。"""
    u = base64.b64encode(str(student_no).encode('utf-8')).decode('ascii')
    p = base64.b64encode(str(password).encode('utf-8')).decode('ascii')
    return f'{u}%%%{p}'


class RealJwxtClient:
    """单账号会话客户端：一次 login 返回带 Cookie 的 session，后续抓取复用。"""

    def __init__(self, base_url=None):
        self.base = (base_url or _DEFAULT_BASE).rstrip('/')

    def _new_session(self):
        s = requests.Session()
        s.headers.update({
            'User-Agent': _UA,
            'Referer': f'{self.base}/xskb/xskb_list.do',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })
        return s

    def _request(self, session, method, path, **kwargs):
        """带重试的请求：超时/连接类失败退避后自动重试一次（覆盖该校服务器的秒级挂起）。
        重试仍失败抛 JwxtError('network')，超时与连接错误给出可操作的中文提示。"""
        url = f'{self.base}{path}'
        kwargs.setdefault('timeout', _timeout())
        last = None
        for attempt in range(1, _NET_RETRIES + 1):
            try:
                resp = session.request(method, url, **kwargs)
                if resp.status_code != 200:
                    raise JwxtError('network', f'教务系统响应异常（HTTP {resp.status_code}）')
                return resp
            except JwxtError:
                raise
            except requests.RequestException as e:
                last = e
                retryable = isinstance(e, (requests.Timeout, requests.ConnectionError))
                if retryable and attempt < _NET_RETRIES:
                    time.sleep(_NET_RETRY_BACKOFF)
                    continue
                break
        if isinstance(last, requests.Timeout):
            raise JwxtError('network', '教务系统响应超时（站点繁忙或网络波动），已自动重试仍失败，请稍后再试')
        raise JwxtError('network', f'请求教务系统失败：{last}')

    def login(self, student_no, password):
        """登录并验证登录态。成功返回会话；凭证错误抛 JwxtError('credential')。
        本校实测：全新会话仅 POST encoded（base64(学号)%%%base64(密码)）即可，
        成功 302 落地 xsMain.jsp，失败回到登录页（含 userPassword 输入框）。"""
        session = self._new_session()
        resp = self._request(session, 'POST', '/xk/LoginToXk',
                             data={'encoded': encode_credentials(student_no, password)},
                             allow_redirects=True)
        text = resp.text
        on_main = ('xsMain.jsp' in resp.url or '个人中心' in text
                   or 'Top1_divLoginName' in text)
        if not on_main:
            if '验证码' in text:
                raise JwxtError('captcha', '教务系统要求验证码（连续失败触发），请稍后再试')
            raise JwxtError('credential', '教务账号或密码错误（或登录被拒绝）')
        return session

    def fetch_current_semester(self, session):
        html = self._request(session, 'GET', '/xskb/xskb_list.do').text
        return parse_current_semester(html)

    def fetch_timetable(self, session, semester=None):
        """全学期合并课表（不带 zc）。semester 为 None 时沿用服务端默认（当前学期）。"""
        params = {'xnxq01id': semester} if semester else None
        html = self._request(session, 'GET', '/xskb/xskb_list.do', params=params).text
        return parse_timetable(html)

    def fetch_week_calendar(self, session, semester):
        html = self._request(session, 'GET', '/jxzl/jxzl_query', params={'xnxq01id': semester}).text
        return parse_week_calendar(html, semester)

    def verify_session(self, session):
        """轻量登录态校验：课表页可访问且含课表表格。"""
        html = self._request(session, 'GET', '/xskb/xskb_list.do').text
        return 'kbtable' in html
