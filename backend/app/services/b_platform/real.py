# B 平台真实适配器：验证码 → 登录 → 学生信息 三步链路（报文来自 2026-08 抓包）
# 注意：密码传输编码是 Base64（非加密）；showCode 是测试环境的明文验证码后门，
# 正式环境关闭时需在 solve_captcha 钩子接打码方案（本期不做）。
import base64
import os
import warnings

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from app.services.b_platform.base import BPlatformError, VerifyResult

BASE_URL = 'https://xiaobei.yinghuaonline.com'

# 该域名证书链不完整（缺中间签发者），本机标准校验必失败；旧版工程同样全程 verify=False。
# 默认关闭校验与旧版对齐；环境变量 BP_VERIFY_SSL=1 可开启（配合系统信任库或修链后）。
SSL_VERIFY = (os.getenv('BP_VERIFY_SSL') or '').lower() in ('1', 'true')
if not SSL_VERIFY:
    warnings.simplefilter('ignore', InsecureRequestWarning)

# 抓包所得 uni-app 默认 UA：配置套未指定 uaId 时一律用它
DEFAULT_UA = (
    'Mozilla/5.0 (Linux; Android 12; SM-A5560 Build/V417IR; wv) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/110.0.5481.154 '
    'Mobile Safari/537.36 uni-app Html5Plus/1.0 (Immersed/24.0)'
)

_TIMEOUT = 10


class RealAdapter:
    name = 'real'

    def _headers(self, ua=None, token=None):
        headers = {'User-Agent': ua or DEFAULT_UA}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return headers

    def _check(self, resp):
        """统一信封校验：HTTP 层异常→network；业务码非 200→credential"""
        try:
            data = resp.json()
        except ValueError:
            raise BPlatformError('unknown', 'B 平台返回了非 JSON 内容')
        code = data.get('code')
        if code != 200:
            # 若依体系 401 表示登录态失效；此处发生在登录阶段，归为凭证问题
            kind = 'credential' if code in (401, 500) else 'unknown'
            raise BPlatformError(kind, data.get('msg') or f'B 平台业务错误码 {code}')
        return data

    def get_captcha(self, ua=None):
        """获取图形验证码。返回 (uuid, showCode)；测试环境 showCode 即明文答案"""
        try:
            resp = requests.get(
                f'{BASE_URL}/xiaobei-api/captchaImage',
                headers=self._headers(ua), timeout=_TIMEOUT, verify=SSL_VERIFY,
            )
            data = self._check(resp)
        except BPlatformError:
            raise
        except requests.RequestException as e:
            raise BPlatformError('network', f'获取验证码失败：{e}')
        uuid_ = data.get('uuid')
        show_code = data.get('showCode')
        if not uuid_ or not show_code:
            raise BPlatformError('captcha', '验证码接口未返回 showCode（正式环境需接打码方案）')
        return uuid_, show_code

    def login(self, username, password, ua=None):
        """登录并返回 token；username 为手机号或身份证号，password 传输前 Base64 编码"""
        uuid_, show_code = self.get_captcha(ua)
        payload = {
            'username': username,
            'password': base64.b64encode(password.encode('utf-8')).decode('ascii'),
            'code': show_code,
            'uuid': uuid_,
            'appUuid': '',
        }
        try:
            resp = requests.post(
                f'{BASE_URL}/xiaobei-api/userLogin',
                json=payload, headers=self._headers(ua), timeout=_TIMEOUT, verify=SSL_VERIFY,
            )
            data = self._check(resp)
        except BPlatformError:
            raise
        except requests.RequestException as e:
            raise BPlatformError('network', f'登录请求失败:{e}')
        token = data.get('token')
        if not token:
            raise BPlatformError('unknown', '登录成功但响应中缺少 token')
        return token

    def fetch_profile(self, token, ua=None):
        """拉取学生信息；返回标准 profile 字典与 bp_uid"""
        try:
            resp = requests.get(
                f'{BASE_URL}/xiaobei-api/student/studentInfo',
                headers=self._headers(ua, token), timeout=_TIMEOUT, verify=SSL_VERIFY,
            )
            data = self._check(resp)
        except BPlatformError:
            raise
        except requests.RequestException as e:
            raise BPlatformError('network', f'获取学生信息失败:{e}')
        profile, bp_uid = map_student_info(data.get('data') or {})
        return profile, bp_uid

    def verify_and_fetch(self, username, password, ua=None):
        """一步到位：登录 + 学生信息。供添加账号 / 重校验调用"""
        token = self.login(username, password, ua)
        profile, bp_uid = self.fetch_profile(token, ua)
        return VerifyResult(ok=True, token=token, bp_uid=bp_uid, profile=profile)

    # ---- 本期留桩：打卡执行与历史记录（抓包到位后在 RealAdapter 内补真实现）----
    def checkin(self, session, task):
        from app.services.b_platform.base import CheckinResult
        return CheckinResult(ok=True, status='success', detail={'stub': True})

    def fetch_records(self, session, account):
        return []


def map_student_info(data: dict):
    """B 平台学生信息 → 标准 profile 字典（纯函数，便于单测）。
    安全裁剪：studentIdCard（身份证）与 paasword（回显密码）绝不入库。"""
    profile = {
        'name': data.get('studentName') or '',
        'college': data.get('collegeName') or '',
        'major': data.get('professionalName') or '',
        'className': data.get('deptName') or '',
        'studentNo': data.get('studentNumber') or '',
        'school': data.get('schoolName') or '',
        'phone': data.get('studentIpone') or '',
        'sex': data.get('studentSex'),
        'enrollDate': data.get('studentSchoolTime') or '',
    }
    return profile, data.get('id')
