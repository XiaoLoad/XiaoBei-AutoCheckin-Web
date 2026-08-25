# B 平台登录诊断脚本：定位「正确凭据被拒」的原因
# 用法（backend 目录下）：
#   set BP_TEST_ACCOUNT=13800000000        （手机号或身份证号）
#   set BP_TEST_PASSWORD=你的密码
#   .venv\Scripts\python.exe scripts\diag_bp_login.py
# 说明：密码经环境变量传入，不进命令行历史；脚本会依次用三种验证码取值
# 各取一次新验证码尝试登录，打印 B 平台完整响应，据此区分：
#   - 全部变体均「用户不存在/密码错误」→ 大概率触发平台失败锁号（等 15 分钟再试）
#   - 仅 code=200 变体成功            → 服务端校验的是旧版后门口径，适配器需调整
#   - showCode 成功                   → 当前实现无误（可能是此前触发锁号的余波）
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

from app.services.b_platform.real import BASE_URL, DEFAULT_UA

TIMEOUT = 10


def headers(token=None):
    h = {'User-Agent': DEFAULT_UA}
    if token:
        h['Authorization'] = f'Bearer {token}'
    return h


def get_captcha():
    rsp = requests.get(f'{BASE_URL}/xiaobei-api/captchaImage', headers=headers(), timeout=TIMEOUT)
    data = rsp.json()
    print(f'[验证码] code={data.get("code")} uuid={str(data.get("uuid"))[:12]}… '
          f'showCode={data.get("showCode")} (img 长度 {len(data.get("img") or "")})')
    return data.get('uuid'), data.get('showCode')


def try_login(tag, username, password_b64, code_value):
    uuid_, _ = get_captcha()
    payload = {
        'username': username,
        'password': password_b64,
        'code': code_value(uuid_),
        'uuid': uuid_,
        'appUuid': '',
    }
    rsp = requests.post(f'{BASE_URL}/xiaobei-api/userLogin', json=payload, headers=headers(), timeout=TIMEOUT)
    try:
        data = rsp.json()
    except ValueError:
        data = {'_raw': rsp.text[:120]}
    shown = {k: v for k, v in data.items() if k != 'token'}
    token = data.get('token')
    print(f'[{tag}] HTTP {rsp.status_code} -> {json.dumps(shown, ensure_ascii=False)[:160]}'
          f'{" | 拿到 token ✓" if token else ""}')
    return token


def main():
    username = os.getenv('BP_TEST_ACCOUNT', '').strip()
    password = os.getenv('BP_TEST_PASSWORD', '')
    if not username or not password:
        print('请先设置环境变量 BP_TEST_ACCOUNT 与 BP_TEST_PASSWORD 再运行')
        return
    pwd_b64 = base64.b64encode(password.encode('utf-8')).decode('ascii')

    variants = [
        ('变体A: code=showCode（真实App口径，当前项目实现）', lambda u: get_captcha()[1]),
        ('变体B: code="200"（旧版工程后门口径）', lambda u: '200'),
        ('变体C: code=""（空串探边界）', lambda u: ''),
    ]
    token = None
    for tag, code_fn in variants:
        try:
            # 每个变体独立取一次验证码，避免 uuid 单次有效互相污染
            uuid_, show_code = get_captcha()
            payload = {
                'username': username, 'password': pwd_b64,
                'code': show_code if 'A' in tag else ('200' if 'B' in tag else ''),
                'uuid': uuid_, 'appUuid': '',
            }
            rsp = requests.post(f'{BASE_URL}/xiaobei-api/userLogin', json=payload,
                                headers=headers(), timeout=TIMEOUT)
            try:
                data = rsp.json()
            except ValueError:
                data = {'_raw': rsp.text[:120]}
            shown = {k: v for k, v in data.items() if k != 'token'}
            ok = bool(data.get('token'))
            print(f'{tag}: HTTP {rsp.status_code} -> '
                  f'{json.dumps(shown, ensure_ascii=False)[:150]}{" | 拿到 token ✓" if ok else ""}')
            if ok and not token:
                token = data['token']
        except requests.RequestException as e:
            print(f'{tag}: 网络异常 {e}')

    if token:
        rsp = requests.get(f'{BASE_URL}/xiaobei-api/student/studentInfo',
                           headers=headers(token), timeout=TIMEOUT)
        data = rsp.json().get('data') or {}
        print(f'[学生信息] 姓名={data.get("studentName")} 学号={data.get("studentNumber")} '
              f'班级={data.get("deptName")}')

    print('\n判读：三变体全被拒且文案含「密码」→ 大概率平台锁号，等约 15 分钟后再跑一次；'
          '仅变体B成功 → 服务端只认 200 后门口径，告诉我结果我来改适配器。')


if __name__ == '__main__':
    main()
