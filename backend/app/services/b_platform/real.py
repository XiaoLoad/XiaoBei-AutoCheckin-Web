# B 平台真实适配器：验证码 → 登录 → 学生信息 三步链路（报文来自 2026-08 抓包）
# 注意：密码传输编码是 Base64（非加密）；showCode 是测试环境的明文验证码后门，
# 正式环境关闭时需在 solve_captcha 钩子接打码方案（本期不做）。
import base64
import json
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

    def _request(self, method, path, token=None, params=None, json=None):
        """统一的 B 平台读取请求：拼 /xiaobei-api/ 前缀，走信封校验。"""
        url = f'{BASE_URL}/xiaobei-api/{path}'
        try:
            resp = requests.request(
                method, url, headers=self._headers(None, token),
                params=params, json=json, timeout=_TIMEOUT, verify=SSL_VERIFY,
            )
        except requests.RequestException as e:
            raise BPlatformError('network', f'请求 B 平台失败：{e}')
        return self._check(resp)

    # ---- 历史签到读取（v1.5 抓包闭环：overlist → {id} 围栏 → listLog）----
    def fetch_history_tasks(self, token, kind, page_num=1, page_size=200):
        """寝/活历史任务列表（overlist）。kind: 'know'|'sign'，返回统一行列表。"""
        if kind not in ('know', 'sign'):
            raise BPlatformError('unknown', f'未知任务模块：{kind}')
        data = self._request('GET', f'student/{kind}/overlist', token=token,
                             params={'pageNum': page_num, 'pageSize': page_size})
        rows = data.get('rows') or []
        return [self._unify_task(r, kind) for r in rows]

    def fetch_task_detail(self, token, kind, task_id):
        """任务详情：地理围栏 JSON 字符串位于 data.location（know 详情独有，sign 亦含）。"""
        if kind not in ('know', 'sign'):
            raise BPlatformError('unknown', f'未知任务模块：{kind}')
        data = self._request('GET', f'student/{kind}/{task_id}', token=token)
        task = data.get('data') or {}
        return {'geoFence': self._parse_geo(task.get('location')),
                'task': self._unify_task(task, kind)}

    def fetch_task_logs(self, token, kind, task_id):
        """签到记录列表（listLog）。know 用 knowingId，sign 用 signId；仅取已完成记录。"""
        if kind not in ('know', 'sign'):
            raise BPlatformError('unknown', f'未知任务模块：{kind}')
        param = 'knowingId' if kind == 'know' else 'signId'
        finish_key = 'isFinishKnowing' if kind == 'know' else 'isFinishSign'
        data = self._request('GET', f'student/{kind}/listLog', token=token,
                             params={param: task_id, finish_key: 1,
                                     'pageNum': 1, 'pageSize': 200})
        rows = data.get('rows') or []
        return [self._unify_log(r, kind) for r in rows]

    def _initiator(self, r):
        name = r.get('sendName') or ''
        role = r.get('sendRole') or ''
        return f'{name} · {role}' if (name and role) else (name or '—')

    def _unify_task(self, r, kind):
        """B 平台任务行 → 统一字段（know/sign 拼写字段在此归一）。

        needPhoto：第三方平台约定 isPicture/isPictrue == 0 表示「需要拍照」、
        1 表示「无需拍照」（与常规布尔相反，旧版 XiaoBeiCheck 亦如此实现：
        `task.get('isPicture', 0) == 0`）。str 比较以兼容 int 与可能的字符串 "0"/"1"。
        """
        raw_photo = r.get('isPicture') if kind == 'know' else r.get('isPictrue')
        need_photo = str(raw_photo) == '0'
        base = {
            'id': r.get('id'),
            'kind': kind,
            'type': 'dorm' if kind == 'know' else 'activity',
            'taskName': r.get('knowingName') if kind == 'know' else r.get('signName') or '',
            'startDate': r.get('startDate') or '',
            'endDate': r.get('endDate') or '',
            'startTime': r.get('startTime') or '',
            'endTime': r.get('endTime') or '',
            'initiator': self._initiator(r),
            'needPhoto': need_photo,
            'finished': bool(r.get('isFinishKnowing') if kind == 'know' else r.get('isFinishSign')),
        }
        return base

    def _unify_log(self, r, kind):
        """B 平台签到记录行 → 统一字段（注意 file 尾随逗号需剔除）。

        image_url 直接回填 B 平台图片直链：该接口为公开静态资源、无需鉴权，且 <img>
        标签不受 CORS 约束，前端直接 <img :src> 即可，无需后端代理。路径须字面量透传，
        不得再做 percent-encode（浏览器对查询串内的 // 与括号保持原样，正好对齐 App 抓包）。
        """
        file_path = (r.get('file') or '').rstrip(',')
        # 防御：file 内若混入 ?/# 会截断查询串（理论上 B 平台路径不会含，仅兜底）
        file_path = file_path.split('?')[0].split('#')[0]
        image_url = f'{BASE_URL}/xiaobei-api/image/get?path={file_path}' if file_path else ''
        if kind == 'know':
            return {
                'id': r.get('id'),
                'studentNumber': r.get('studentNumber') or '',
                'studentName': r.get('studentName') or '',
                'className': '',
                'location': r.get('location') or '',
                'remark': r.get('remark') or '',
                'time': r.get('knowingTime') or '',
                'file': file_path,
                'imageUrl': image_url,
                'finished': bool(r.get('isFinishKnowing')),
            }
        return {
            'id': r.get('id'),
            'studentNumber': r.get('studentNumber') or '',
            'studentName': r.get('studentName') or '',
            'className': r.get('studentClass') or '',
            'location': r.get('location') or '',
            'remark': r.get('signRemark') or '',
            'time': r.get('signTime') or '',
            'file': file_path,
            'imageUrl': image_url,
            'finished': bool(r.get('isFinishSign')),
        }

    @staticmethod
    def _parse_geo(loc):
        """location 是 JSON 数组字符串（可能为空/非法），解析为围栏列表。"""
        if not loc:
            return []
        try:
            arr = json.loads(loc) if isinstance(loc, str) else loc
        except (ValueError, TypeError):
            return []
        out = []
        for g in (arr or []):
            out.append({
                'alias': g.get('alias') or '',
                'latitude': g.get('latitude') or '',
                'longitude': g.get('longitude') or '',
                'location': g.get('location') or '',
                'radius': g.get('radius') or '',
            })
        return out

    # ---- 打卡执行（Module E，本期仍留桩）----
    def checkin(self, session, task):
        from app.services.b_platform.base import CheckinResult
        return CheckinResult(ok=True, status='success', detail={'stub': True})


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
