# B 平台真实适配器：验证码 → 登录 → 学生信息 三步链路（报文来自 2026-08 抓包）
# + 提交签到（模块 E）：know 提交契约经旧版 XiaoBeiCheck 生产环境验证；
#   sign 模块为镜像推断（仅任务 id 字段名不同），待真机抓包核准——失败时
#   fail_reason 透传平台 msg，便于定位修正。
# 注意：密码传输编码是 Base64（非加密）；showCode 是测试环境的明文验证码后门，
# 正式环境关闭时需在 solve_captcha 钩子接打码方案（本期不做）。
import base64
import json
import os
import random
import string
import time
import warnings

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from app.services.b_platform.base import BPlatformError, CheckinResult, VerifyResult

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
_SUBMIT_TIMEOUT = (5, 30)
_MAX_NET_RETRIES = 3

# know/sign 双模块的路径与字段拼写映射（sign 为平台原生拼写差异，见接口文档 §5.8）
_MODULES = {
    'dorm': {
        'kind': 'know',
        'list': '/student/know/list',
        'submit': '/student/know/updateStudentKnow',
        'submit_no_file': '/student/know/updateStudentKnowNoFile',
        'task_id_field': 'knowingId',
        'finish_field': 'isFinishKnowing',
        'need_photo_field': 'isPicture',
    },
    'activity': {
        'kind': 'sign',
        'list': '/student/sign/list',
        'submit': '/student/sign/updateStudentSign',  # 镜像推断，待真机核准
        'submit_no_file': '/student/sign/updateStudentSignNoFile',  # 镜像推断，待真机核准
        'task_id_field': 'signId',
        'finish_field': 'isFinishSign',
        'need_photo_field': 'isPictrue',
    },
}


def _module(task_type):
    mod = _MODULES.get(task_type)
    if not mod:
        raise BPlatformError('unknown', f'未知任务类型：{task_type}')
    return mod


def generate_image_filename():
    """B 平台提交图片文件名约定：{毫秒时间戳}{随机小写字母}.jpeg（旧版 generate_filename 同款）"""
    ts = str(int(time.time() * 1000))
    return f'{ts}{random.choice(string.ascii_lowercase)}.jpeg'


def _is_submit_success(rsp):
    """提交成功判定（旧版生产实证）：code==200 && msg=='操作成功'，或 code==6111（视作已接受）"""
    return (rsp.get('code') == 200 and rsp.get('msg') == '操作成功') or rsp.get('code') == 6111


class RealAdapter:
    name = 'real'

    def _headers(self, ua=None, token=None):
        headers = {'User-Agent': ua or DEFAULT_UA}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return headers

    def _check(self, resp):
        """统一信封校验：HTTP 层异常→network；业务码非 200→credential/unknown。
        仅 401 归 credential（若依体系登录态失效的确定性信号）；500 等服务端错误归
        unknown——此前 500 被误判为凭证失效，导致无谓的重登重试并把账号污染成
        verify_status='fail'，之后每次执行都全量重登、放大平台压力。"""
        try:
            data = resp.json()
        except ValueError:
            raise BPlatformError('unknown', 'B 平台返回了非 JSON 内容')
        code = data.get('code')
        if code != 200:
            kind = 'credential' if code == 401 else 'unknown'
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

    def _request(self, method, path, token=None, params=None, json=None, ua=None):
        """统一的 B 平台读取请求：拼 /xiaobei-api/ 前缀，走信封校验。
        网络异常指数退避重试 ≤3 次（与提交链路同策略）：找任务/读历史同属签到关键路径，
        平台一次抖动不应让当天签到直接失败；业务码/凭证错误不重试。"""
        url = f'{BASE_URL}/xiaobei-api/{path}'
        last_err = None
        for attempt in range(_MAX_NET_RETRIES):
            try:
                resp = requests.request(
                    method, url, headers=self._headers(ua, token),
                    params=params, json=json, timeout=_TIMEOUT, verify=SSL_VERIFY,
                )
                return self._check(resp)
            except BPlatformError:
                raise
            except requests.RequestException as e:
                last_err = e
                if attempt < _MAX_NET_RETRIES - 1:
                    time.sleep(1 * (2 ** attempt))
        raise BPlatformError('network', f'请求 B 平台失败（已重试 {_MAX_NET_RETRIES} 次）：{last_err}')

    # ---- 提交签到（模块 E）----

    def _file_headers(self, ua=None, token=None):
        """multipart 提交头（对齐旧版 FILE_HEADERS）：不带 Content-Type，交由 requests 按 boundary 生成"""
        headers = {'User-Agent': ua or DEFAULT_UA, 'Charset': 'UTF-8',
                   'Connection': 'Keep-Alive', 'Accept-Encoding': 'gzip'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return headers

    def find_active_task(self, session, task_type):
        """查询可提交的进行中签到任务（提交只能使用 /list 进行中任务的 id，overlist 的 id 不可用）。
        返回 {'task': 归一任务(含 needPhoto/startTime/endTime) 或 None,
              'fence': 围栏列表, 'finished_task': 本人已签到的进行中任务 或 None}
        ——不返回 None：`/list` 会同时给出本人已签到的行，据此区分「本来就没任务」与
        「已签到无需重复提交」，否则两者都只能报「无进行中任务」，会被误当漏签排查。
        会话 token 失效由 _check 抛 credential。

        分页拉全（F3）：固定 pageSize=50 时，多班级集中发布导致进行中任务超 50 条，
        目标任务不在首屏 → 误判「无进行中任务」而 skip。若依信封的 total 给出全量行数，
        按页翻完再找目标；上限 10 页（500 条）防平台脏 total 造成无限翻页。"""
        mod = _module(task_type)
        finish_field = mod['finish_field']
        page_size = 50
        rows = []
        for page in range(1, 11):
            data = self._request('GET', mod['list'].lstrip('/'), token=session.get('token'),
                                 params={'pageNum': page, 'pageSize': page_size},
                                 ua=session.get('ua'))
            page_rows = data.get('rows') or []
            rows.extend(page_rows)
            total = data.get('total')
            if not page_rows or not isinstance(total, int) or len(rows) >= total:
                break
        task = next((r for r in rows if str(r.get(finish_field)) == '0'), None)
        if task is None:
            done = next((r for r in rows if str(r.get(finish_field)) == '1'), None)
            return {'task': None, 'fence': [],
                    'finished_task': self._unify_task(done, mod['kind']) if done else None}
        # 围栏：列表行通常不带 location，补查详情（fetch_task_detail 复用既有解析）
        detail = self.fetch_task_detail(session.get('token'), mod['kind'], task.get('id'))
        return {'task': self._unify_task(task, mod['kind']), 'fence': detail['geoFence'],
                'finished_task': None}

    def fetch_active_tasks(self, token, task_type):
        """进行中任务列表（/list 中平台判定为「进行中」的全部行，含本人已签到的），
        供前端「正在进行」卡片展示。

        不过滤 finished：任务未结束即属进行中，本人可能已签到（isFinishKnowing/
        isFinishSign == 1），此时仍需展示并标注状态——否则「已签但未结束」的任务
        会在卡片与 overlist 历史之间整段消失。与只取首条未完成项用于提交的
        find_active_task 区分。列表行不带围栏，详情由前端按需懒加载。
        """
        mod = _module(task_type)
        data = self._request('GET', mod['list'].lstrip('/'), token=token,
                             params={'pageNum': 1, 'pageSize': 50})
        rows = data.get('rows') or []
        return [self._unify_task(r, mod['kind']) for r in rows]

    def submit_checkin(self, session, task_type, platform_task_id, location, address, remark, image=None):
        """提交签到。image=None → 无图 JSON（photo:[]，size:"0"）；否则有图 multipart
        （photo+file0 同图双文件部分，size:"1"，文件名 {毫秒}{随机小写字母}.jpeg）。

        结果判定（旧版生产实证）：成功 = code==200&&msg=='操作成功' 或 code==6111；
        code==200&&msg=='302' 为风控行为验证码（判失败，需人工）；msg 含 token 失效/认证失败
        → credential（上层重登后重试一次）；业务错误（含中文提示）不重试直接失败；
        网络异常指数退避重试 ≤3 次。CHECKIN_DRYRUN=1 时完整构造但不发送（演练模式）。

        重试安全边界（T5）：仅「请求未抵达平台」的异常可安全重试——连接失败
        （ConnectionError/ConnectTimeout）时请求从未发出；读超时（ReadTimeout）时
        请求已发出、平台可能已受理签到，重发会造成重复提交，立即终止重试。"""
        mod = _module(task_type)
        data = {
            mod['task_id_field']: str(platform_task_id),
            'location': location or '',
            'address': address or '',
            'remark': remark or '签到',
            'size': '1' if image else '0',
        }
        if os.getenv('CHECKIN_DRYRUN', '').lower() in ('1', 'true'):
            safe_payload = {**data, 'image': image.get('filename') if image else None}
            return CheckinResult(ok=True, status='skip',
                                 fail_reason='演练：已构造提交未发送（CHECKIN_DRYRUN）',
                                 detail={'payload': safe_payload})

        # 前缀不可省：漏了会被 nginx 兜底成 SPA 的 HTML 页（HTTP 200），报「非 JSON 内容」
        url = f"{BASE_URL}/xiaobei-api{mod['submit'] if image else mod['submit_no_file']}"
        last_err = None
        for attempt in range(_MAX_NET_RETRIES):
            try:
                if image:
                    filename = image.get('filename') or generate_image_filename()
                    files = {
                        'photo': (filename, image['bytes'], 'image/jpeg'),
                        'file0': (filename, image['bytes'], 'image/jpeg'),
                    }
                    resp = requests.post(
                        url, data=data, files=files,
                        headers=self._file_headers(session.get('ua'), session.get('token')),
                        timeout=_SUBMIT_TIMEOUT, verify=SSL_VERIFY)
                else:
                    resp = requests.post(
                        url, json={**data, 'photo': []},
                        headers=self._headers(session.get('ua'), session.get('token')),
                        timeout=_SUBMIT_TIMEOUT, verify=SSL_VERIFY)
                try:
                    rsp = resp.json()
                except ValueError:
                    # 网关/反代的瞬时 5xx 常返回 HTML 错误页，是最典型的可重试瞬态故障，
                    # 纳入重试循环（此前直接跳出、单发即失败）；4xx 非 JSON 才是真正的协议异常
                    if resp.status_code >= 500:
                        last_err = f'HTTP {resp.status_code} 非 JSON 响应'
                        if attempt < _MAX_NET_RETRIES - 1:
                            time.sleep(1 * (2 ** attempt))
                        continue
                    raise BPlatformError('unknown', f'B 平台返回了非 JSON 内容（HTTP {resp.status_code}）')

                if rsp.get('code') == 200 and rsp.get('msg') == '302':
                    return CheckinResult(ok=False, status='fail',
                                         fail_reason='触发平台行为验证码（msg=302），需人工处理',
                                         detail={'rsp': rsp})
                if _is_submit_success(rsp):
                    return CheckinResult(ok=True, status='success', detail={'rsp': rsp})
                msg = rsp.get('msg') or ''
                if 'token失效' in msg or '认证失败' in msg or resp.status_code == 401:
                    raise BPlatformError('credential', f'登录态失效：{msg or resp.status_code}')
                return CheckinResult(ok=False, status='fail',
                                     fail_reason=f'B 平台拒绝：{msg or "code=" + str(rsp.get("code"))}',
                                     detail={'rsp': rsp})
            except BPlatformError:
                raise
            except requests.RequestException as e:
                # 读超时 = 请求已发出、平台可能已受理签到：重发会重复提交（T5），
                # 立即终止；连接类失败请求从未抵达平台，退避后重试安全。
                if isinstance(e, (requests.ReadTimeout, requests.Timeout)) \
                        and not isinstance(e, requests.ConnectTimeout):
                    raise BPlatformError('network', f'提交读超时（平台可能已受理，不重发）：{e}')
                last_err = e
                if attempt < _MAX_NET_RETRIES - 1:
                    time.sleep(1 * (2 ** attempt))
        raise BPlatformError('network', f'提交请求失败（已重试 {_MAX_NET_RETRIES} 次）：{last_err}')

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

    # ---- 提交签到入口见上方 find_active_task / submit_checkin（模块 E）----


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
