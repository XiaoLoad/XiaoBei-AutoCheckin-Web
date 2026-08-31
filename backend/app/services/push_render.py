# 推送内容渲染 + 单通道发送（供调度器分发与凭证测试推送共用）。
# 模板格式：html（默认，微信/UI 友好）/ txt（纯文本）/ markdown。
# 标题含签到账号姓名 + 状态（成功/失败/跳过）；内容按四分区组织：
# 签到状态（类型/状态/时间）、个人信息（姓名/学号/专业/班级）、
# 签到任务（任务名/时间段/发起人/是否需要图片）、签到参数（地址/经纬度/备注/图组/配置套）。
# 通道差异：pushplus 按 template 渲染；serverchan 仅纯文本；email 支持 HTML——
# template=html 时以 text/html 邮件发送，txt/markdown 回落纯文本。
# PushPlus 长度守卫：标题≤100 字、内容≤20000 字（取实名用户下限，会员更高，保守值避免被截断）。
import logging
import os
import warnings

import requests
from app.extensions import db
from app.models import ConfigSet
from app.models.pools import ImageGroup, PoolLocation
from app.models.user import now_cst
from urllib3.exceptions import InsecureRequestWarning

log = logging.getLogger('push')

# 推送目标（Server酱 / PushPlus）与 B 平台同理：部分域名证书链不完整（缺中间签发者），
# 本机标准校验必失败；默认关闭校验与 B 平台对齐。PUSH_VERIFY_SSL=1 可开启（配合系统信任库）。
PUSH_VERIFY_SSL = (os.getenv('PUSH_VERIFY_SSL') or '').lower() in ('1', 'true')
if not PUSH_VERIFY_SSL:
    warnings.simplefilter('ignore', InsecureRequestWarning)

PUSHPLUS_TITLE_MAX = 100
PUSHPLUS_CONTENT_MAX = 20000
STATUS_LABEL = {'success': '成功', 'skip': '跳过', 'fail': '失败'}
STATUS_COLOR = {'success': '#15a05a', 'skip': '#d97706', 'fail': '#e23b3b'}
# 状态色浅底（用于 chip / 分组强调），与主色同源，保证配色统一
STATUS_COLOR_SOFT = {'success': '#e7f6ee', 'skip': '#fdf2e3', 'fail': '#fdecec'}

TEMPLATES = ('html', 'txt', 'markdown')


def _truncate(s, n):
    s = s or ''
    return s if len(s) <= n else s[: n - 1] + '…'


def _esc(s):
    """HTML 文本节点 / 属性值转义（图片 URL 走属性，引号也需转义）。"""
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;').replace("'", '&#39;'))


def _lookup_location(location_id):
    """按位置池 id 取名称/经纬度/地址；缺失返回 None（推送里展示为未配置）。"""
    if not location_id:
        return None
    try:
        loc = db.session.get(PoolLocation, int(location_id))
    except (TypeError, ValueError):
        return None
    if loc is None:
        return None
    return {'name': loc.name or '', 'lat': loc.lat, 'lng': loc.lng, 'address': loc.address or ''}


def build_ctx(acc, schedule, resolved, status, reason='', signed_at=None, image_url='', remark=None,
              task_name='', task_window='', need_photo=None):
    """组装推送上下文：账号信息来自 acc.profile，任务/时间/位置来自 schedule 与 resolved。
    remark 显式传入时（调度器按本次实际提交选取的单条）优先使用；为 None 时回退到
    合并全部备注（凭证测试推送预览用，便于一眼看全已配置备注）。
    task_name/task_window/need_photo 来自 B 平台进行中任务（调度器执行时经 extra 传入；
    任务未找到或测试推送等场景留空，卡片显示「—」）。
    config_source 按 schedule.mode 推导：follow→配置套名，custom→自定义，standalone→独立配置。"""
    profile = getattr(acc, 'profile', None) or {}
    name = (profile.get('name') or '').strip() or (getattr(acc, 'account', '') or '未知账号')
    task_label = '寝室签到' if schedule.task_type == 'dorm' else '活动签到'
    time = (resolved or {}).get('time') or {}
    sh, eh = time.get('startHour'), time.get('endHour')
    if sh is not None and eh is not None:
        time_window = f'{int(sh):02d}:00 - {int(eh):02d}:00'
    else:
        time_window = '—'
    sign_at = signed_at or now_cst()
    sign_time = sign_at.strftime('%Y-%m-%d %H:%M')
    loc = _lookup_location((resolved or {}).get('locationId'))
    # 图片分组名：从 resolved 配置的 image.groupId 解析（不展示图片本身，仅展示所用分组）
    image_cfg = (resolved or {}).get('image') or {}
    image_group_name = ''
    gid = image_cfg.get('groupId')
    if gid:
        try:
            g = db.session.get(ImageGroup, int(gid))
            image_group_name = g.name if g else ''
        except (TypeError, ValueError):
            image_group_name = ''
    if remark is None:
        remarks = (resolved or {}).get('remarks') or []
        remark = ' / '.join(str(r) for r in remarks if str(r).strip()) if remarks else '—'
    # 配置套来源：follow 查套名（仅当 schedule 真有 mode/config_set_id 时）；
    # 测试推送等场景 schedule 为简单占位对象，getattr 兜底为「—」
    config_source = '—'
    mode = getattr(schedule, 'mode', None)
    if mode == 'follow':
        cs_name = ''
        cs_id = getattr(schedule, 'config_set_id', None)
        if cs_id:
            try:
                cs = db.session.get(ConfigSet, int(cs_id))
                cs_name = cs.name if cs else ''
            except (TypeError, ValueError):
                cs_name = ''
        config_source = cs_name or '来源套已删除'
    elif mode == 'custom':
        config_source = '自定义'
    elif mode == 'standalone':
        config_source = '独立配置'
    return {
        'name': name,
        'student_no': profile.get('studentNo') or '—',
        'college': profile.get('college') or '—',
        'major': profile.get('major') or '—',
        'className': profile.get('className') or '—',
        'task_label': task_label,
        'task_type': schedule.task_type,
        'task_name': task_name or '',
        'task_window': task_window or '',
        'need_photo': need_photo,
        'config_source': config_source,
        'status': status,
        'status_label': STATUS_LABEL.get(status, status),
        'initiator': '系统自动',
        'time_window': time_window,
        'sign_time': sign_time,
        'location_name': loc['name'] if loc else '',
        'lat': loc['lat'] if loc else None,
        'lng': loc['lng'] if loc else None,
        'address': loc['address'] if loc else '',
        'remark': remark,
        'image_group_name': image_group_name,
        'image_url': image_url or '',
        'reason': reason or '',
    }


def _title(ctx):
    return f"小北{ctx['task_label']} {ctx['name']} {ctx['status_label']}"


# ── 渲染：HTML（默认，移动端卡片，内联样式兼容微信/pushplus/email） ──
# 四分区：签到状态（hero：类型/状态/时间）、个人信息、签到任务、签到参数。
# 视觉基调：浅灰底 + 白卡 + 状态色点缀，无重渐变，行式标签-值排版，邮件客户端友好。
def render_html(ctx):
    color = STATUS_COLOR.get(ctx['status'], '#2563eb')
    color_soft = STATUS_COLOR_SOFT.get(ctx['status'], '#eef2ff')
    loc_name = ctx['location_name'] or '—'
    addr_no = ctx['address'] or '—'
    loc_text = f"{ctx['lng']}, {ctx['lat']}" if ctx['lng'] is not None and ctx['lat'] is not None else '—'
    group_name = ctx['image_group_name'] or '—'
    if ctx.get('need_photo') is None:
        need_photo = '—'
    else:
        need_photo = '需要' if ctx['need_photo'] else '不需要'

    def head(title):
        return (f'<div style="display:flex;align-items:center;gap:7px;margin:20px 0 2px;">'
                f'<span style="width:6px;height:6px;border-radius:50%;background:{color};display:inline-block;"></span>'
                f'<span style="font-size:11px;font-weight:700;color:#9aa1ab;letter-spacing:2px;">{_esc(title)}</span></div>')

    def row(label, value, last=False):
        border = 'none' if last else '1px solid #f2f3f5'
        return (f'<div style="display:flex;align-items:baseline;gap:12px;padding:9px 0;border-bottom:{border};">'
                f'<div style="width:76px;flex:none;font-size:12px;color:#9aa1ab;letter-spacing:.5px;">{_esc(label)}</div>'
                f'<div style="flex:1;font-size:14px;color:#1f2733;line-height:1.6;word-break:break-all;">{_esc(value)}</div></div>')

    remark_html = (f'<div style="margin-top:12px;padding:11px 13px;border-radius:10px;'
                   f'background:#f7f8fa;font-size:13px;color:#1f2733;line-height:1.6;word-break:break-all;">'
                   f'<span style="font-size:11px;font-weight:700;color:#9aa1ab;letter-spacing:1px;">签到备注</span>'
                   f'<span style="opacity:.5;margin:0 6px;">·</span>{_esc(ctx["remark"] or "—")}</div>')

    reason_html = ''
    if ctx['status'] in ('fail', 'skip') and ctx['reason']:
        label = '失败原因' if ctx['status'] == 'fail' else '跳过原因'
        reason_html = (f'<div style="margin:14px 0 4px;padding:11px 13px;border-radius:10px;'
                       f'background:{color_soft};color:{color};font-size:13px;line-height:1.55;">'
                       f'<span style="font-weight:700;">{label}</span>'
                       f'<span style="opacity:.55;margin:0 6px;">·</span>{_esc(ctx["reason"])}</div>')

    hero = (f'<div style="padding:22px 22px 18px;border-bottom:1px solid #f2f3f5;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div style="font-size:11px;font-weight:600;color:#9aa1ab;letter-spacing:2px;">小北自动打卡</div>'
            f'<div style="font-size:12px;font-weight:600;color:{color};background:{color_soft};border-radius:999px;padding:4px 12px;">{_esc(ctx["task_label"])}</div>'
            f'</div>'
            f'<div style="font-size:30px;font-weight:800;line-height:1.15;margin-top:14px;letter-spacing:2px;color:{color};">{_esc(ctx["status_label"])}</div>'
            f'<div style="font-size:13px;color:#6b7280;margin-top:8px;">签到时间 {_esc(ctx["sign_time"])}</div>'
            f'</div>')

    html = (f'<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;'
            f'max-width:560px;margin:0 auto;background:#eef0f3;padding:16px;border-radius:18px;">'
            f'<div style="background:#ffffff;border-radius:16px;overflow:hidden;'
            f'box-shadow:0 1px 2px rgba(16,24,40,.05),0 8px 24px rgba(16,24,40,.06);">'
            f'{hero}'
            f'<div style="padding:2px 22px 20px;">'
            f'{reason_html}'
            f'{head("个人信息")}'
            f'{row("姓名", ctx["name"])}'
            f'{row("学号", ctx["student_no"])}'
            f'{row("专业", ctx["major"])}'
            f'{row("班级", ctx["className"], last=True)}'
            f'{head("签到任务")}'
            f'{row("任务名称", ctx["task_name"] or "—")}'
            f'{row("任务时间段", ctx["task_window"] or "—")}'
            f'{row("发起人", ctx["initiator"])}'
            f'{row("是否需要图片", need_photo, last=True)}'
            f'{head("签到参数")}'
            f'{row("地址名称", loc_name)}'
            f'{row("地址号", addr_no)}'
            f'{row("经纬度", loc_text)}'
            f'{row("图片分组", group_name)}'
            f'{row("配置套", ctx["config_source"] or "—", last=True)}'
            f'{remark_html}'
            f'</div>'
            f'</div>'
            f'<div style="text-align:center;color:#aab0b8;font-size:11px;margin-top:12px;letter-spacing:.5px;">小北寝室自动打卡 · {_esc(ctx["sign_time"])}</div>'
            f'</div>')
    return _truncate(html, PUSHPLUS_CONTENT_MAX)


# ── 渲染：TXT（纯文本，Server酱/邮件/QQ 通用） ──
def render_txt(ctx):
    lines = [
        f"小北{ctx['task_label']} · {ctx['name']} · 签到{ctx['status_label']}",
        '',
        '【位置】',
        f"名称：{ctx['location_name'] or '（未命名位置）'}",
        f"经纬度：{ctx['lng']}, {ctx['lat']}" if ctx['lng'] is not None else '经纬度：—',
        f"地址：{ctx['address'] or '（未配置）'}",
        '',
        '【备注】',
        ctx['remark'],
        '',
        '【图片分组】',
        ctx['image_group_name'] or '（未配置）',
        '',
        '【执行信息】',
        f"学号：{ctx['student_no']}",
        f"签到时间段：{ctx['time_window']}",
        f"签到时间：{ctx['sign_time']}",
        f"发起人：{ctx['initiator']}",
    ]
    if ctx['status'] == 'fail' and ctx['reason']:
        lines += ['', f"失败原因：{ctx['reason']}"]
    return _truncate('\n'.join(lines), PUSHPLUS_CONTENT_MAX)


# ── 渲染：Markdown（pushplus markdown 通道 / QQ 原生） ──
def render_markdown(ctx):
    loc = f"{ctx['lng']}, {ctx['lat']}" if ctx['lng'] is not None else '—'
    md = [
        f"# 小北{ctx['task_label']} · {ctx['name']} · 签到{ctx['status_label']}",
        '',
        f"**{ctx['task_label']}**",
        '',
        '## 位置',
        f"- **名称**：{ctx['location_name'] or '（未命名位置）'}",
        f"- **经纬度**：{loc}",
        f"- **地址**：{ctx['address'] or '（未配置）'}",
        '',
        '## 备注',
        ctx['remark'],
        '',
        '## 图片分组',
        ctx['image_group_name'] or '（未配置）',
        '',
        '## 执行信息',
        f"- **学号**：{ctx['student_no']}",
        f"- **签到时间段**：{ctx['time_window']}",
        f"- **签到时间**：{ctx['sign_time']}",
        f"- **发起人**：{ctx['initiator']}",
    ]
    if ctx['status'] == 'fail' and ctx['reason']:
        md += ['', f"**失败原因**：{ctx['reason']}"]
    return _truncate('\n'.join(md), PUSHPLUS_CONTENT_MAX)


_RENDERERS = {'html': render_html, 'txt': render_txt, 'markdown': render_markdown}


def render(ctx, fmt):
    """按格式渲染内容；非法格式回退 html。已含长度守卫。"""
    fn = _RENDERERS.get(fmt) if fmt in _RENDERERS else _RENDERERS['html']
    return fn(ctx)


def send_email(fields, subject, body, subtype='plain'):
    """通过 SMTP（STARTTLS，端口 587）发送邮件；subtype='html' 时按 text/html 发送。
    失败抛异常由调用方记录。"""
    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(body, subtype, 'utf-8')
    msg['Subject'] = subject
    msg['From'] = fields['emailFrom']
    msg['To'] = fields['emailTo']
    with smtplib.SMTP(fields['emailSmtp'], 587, timeout=8) as s:
        s.starttls()
        s.login(fields['emailFrom'], fields['emailPass'])
        s.sendmail(fields['emailFrom'], [fields['emailTo']], msg.as_string())


def send_channel(channel, key_or_fields, ctx, template='html'):
    """单通道真实发送；返回 (ok, errmsg)。
    - pushplus：按 template(html/txt/markdown) 渲染并传 template 参数，HTML 优雅卡片；
    - serverchan / email：仅纯文本（desp / body），用 txt 渲染。
    title 含姓名 + 状态，且统一做长度守卫。
    业务结果校验：HTTP 通了不代表送达——serverchan code!=0 / pushplus code!=200
    （如 token 失效）一律视为失败并把平台原因带回，杜绝「凭证无效却报推送成功」。"""
    title = _truncate(_title(ctx), PUSHPLUS_TITLE_MAX)
    if channel == 'serverchan':
        try:
            resp = requests.post(f'https://sctapi.ftqq.com/{key_or_fields}.send',
                                 data={'title': title, 'desp': render_txt(ctx)}, timeout=8,
                                 verify=PUSH_VERIFY_SSL)
        except Exception as e:
            return False, str(e)
        try:
            body = resp.json()
        except ValueError:
            return False, f'ServerChan 响应非 JSON（HTTP {resp.status_code}）'
        if resp.status_code != 200 or body.get('code') != 0:
            return False, (f"ServerChan 推送被拒（code={body.get('code')}，"
                           f"{body.get('message') or f'HTTP {resp.status_code}'}）")
        return True, ''
    if channel == 'pushplus':
        fmt = template if template in TEMPLATES else 'html'
        try:
            resp = requests.post('https://www.pushplus.plus/send',
                                 json={'token': key_or_fields, 'title': title,
                                       'content': render(ctx, fmt), 'template': fmt},
                                 timeout=8, verify=PUSH_VERIFY_SSL)
        except Exception as e:
            return False, str(e)
        try:
            body = resp.json()
        except ValueError:
            return False, f'PushPlus 响应非 JSON（HTTP {resp.status_code}）'
        if resp.status_code != 200 or body.get('code') != 200:
            return False, (f"PushPlus 推送被拒（code={body.get('code')}，"
                           f"{body.get('msg') or f'HTTP {resp.status_code}'}）")
        return True, ''
    if channel == 'email':
        try:
            if template == 'html':
                send_email(key_or_fields, title, render_html(ctx), subtype='html')
            else:
                # txt 原样发送；markdown 邮件客户端不渲染，回落纯文本
                send_email(key_or_fields, title, render_txt(ctx))
            return True, ''
        except Exception as e:
            return False, str(e)
    return False, f'未知通道：{channel}'
