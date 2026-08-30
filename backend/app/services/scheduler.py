# 调度器主链路（模块 D）：APScheduler 注册 cron job，到点执行 B 平台签到，
# 写签到记录、回写任务状态、按需分发推送。采用「事件钩子 + 周期性对账」双保险：
# 路由增删改任务即时注册/移除 job；30s 对账线程兜底清理账号级联删除遗留的孤儿 job。
# [部署约束] 调度器随 Web 进程存活、job 存于内存，全系统只允许单实例运行：
# 多 worker / 多进程部署会让各进程重复注册同一批任务，横向扩容前须先拆出独立调度进程。
import atexit
import logging
import os
from datetime import timedelta

import json
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.base import JobLookupError
# 注意是 APScheduler 自带的线程池执行器（默认 max_workers=10），非标准库同名类
from apscheduler.executors.pool import ThreadPoolExecutor

from app.extensions import db
from app.models import BAccount, ConfigSet, Schedule, SignRecord
from app.models.pools import PoolCredential, PoolLocation, PoolUa
from app.models.system_config import get_setting
from app.models.user import now_cst
from app.services import geo
from app.services.b_platform import get_adapter
from app.services.b_platform.base import BPlatformError
from app.services.b_platform.real import generate_image_filename
from app.services.crypto import decrypt
from app.services.image_store import claim_image_for_submit, rollback_claim
from app.services.push_render import build_ctx, send_channel
from app.utils.schedule_utils import compute_next_run, extract_jitter_minutes, extract_schedule_time

log = logging.getLogger('scheduler')

# 进程级单例
_app = None
_scheduler = None
_started = False
_atexit_registered = False

RECONCILE_JOB_ID = '_reconcile'
_RECONCILE_SECONDS = 30


def _job_id(schedule_id):
    return f'sched_{schedule_id}'


def _scheduler_tz():
    return os.getenv('SCHEDULER_TZ', 'Asia/Shanghai')


def get_scheduler():
    """返回进程级 BackgroundScheduler 单例（惰性创建，未 start 前亦可注册 job）。
    多人同刻集中打卡场景需显式配置（APScheduler 默认值不适合该场景）：
    - 线程池默认 10 个槽，签到为网络 I/O，按峰值任务量调大（SCHEDULER_MAX_WORKERS）；
    - 默认 misfire_grace_time=1 秒，排队超 1 秒的任务会被静默丢弃，放宽到补跑窗口内照常执行
      （SCHEDULER_MISFIRE_GRACE）；coalesce=True 将积压的多次触发合并为一次，避免重复执行。"""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(
            timezone=_scheduler_tz(),
            executors={'default': ThreadPoolExecutor(max_workers=int(os.getenv('SCHEDULER_MAX_WORKERS', '30')))},
            job_defaults={
                'misfire_grace_time': int(os.getenv('SCHEDULER_MISFIRE_GRACE', '600')),
                'coalesce': True,
            },
        )
    return _scheduler


def init_scheduler(app):
    """应用工厂调用：保存 app 引用、注册所有启用任务、启动调度器与对账线程。
    SCHEDULER_ENABLED=0 时完全不接管（测试环境默认关闭，避免后台线程干扰）。
    重复调用安全（进程级守卫）。"""
    global _app, _started, _atexit_registered
    _app = app
    if os.getenv('SCHEDULER_ENABLED', '1').lower() in ('0', 'false'):
        return
    # 开发模式开启 reloader 时，父子两进程都会进入本函数、各起一个调度器 → 任务重复执行。
    # reloader 仅在真正提供服务的子进程设置 WERKZEUG_RUN_MAIN='true'，父进程不设置，
    # 故父进程跳过调度器、仅子进程接管（保留热重载，同时消除重复）。非 debug（reloader 关闭）
    # 或生产多进程场景不受此守卫影响，仍按 SCHEDULER_ENABLED 拆分策略处理。
    if app.config.get('DEBUG') and os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        log.info('reloader 父进程不启动调度器（避免任务重复执行），由子进程接管')
        return
    if _started:
        return

    sched = get_scheduler()
    with app.app_context():
        register_all_enabled()
    sched.add_job(reconcile, 'interval', seconds=_RECONCILE_SECONDS,
                  id=RECONCILE_JOB_ID, replace_existing=True)
    sched.start()
    _started = True

    if not _atexit_registered:
        atexit.register(shutdown_scheduler)
        _atexit_registered = True


def shutdown_scheduler():
    """进程退出时关闭调度器（幂等）"""
    global _started
    if _scheduler is not None and _started:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
    _started = False


def register_all_enabled():
    """为所有 enabled 的 Schedule 注册 cron job（启动 / 对账补注册共用）。"""
    sched = get_scheduler()
    for s in Schedule.query.filter_by(enabled=True).all():
        _register_job(s)


def sync_schedule(schedule):
    """事件钩子：单个任务状态/参数变更后对齐 job 注册。
    enabled → 注册/替换；停用 → 移除。不依赖调度器是否已 start。"""
    if schedule.enabled:
        _register_job(schedule)
    else:
        remove_job(schedule.id)


def remove_job(schedule_id):
    """移除指定任务的 job（任务删除 / 账号级联删除时调用）。"""
    sched = get_scheduler()
    try:
        sched.remove_job(_job_id(schedule_id))
    except JobLookupError:
        pass


def reconcile():
    """周期性对账：对齐 DB 启用态与调度器 job 注册。
    - 已注册但 DB 无启用任务（账号删除 / 任务禁用 / 参数变更）→ 移除 job（孤儿清理）
    - DB 启用但未注册（错过事件钩子的极端情况）→ 补注册
    - 超期签到日志清理：按系统配置 sign_log_retention_days 删除陈旧 SignRecord（全局策略）"""
    if _scheduler is None or _app is None:
        return
    with _app.app_context():
        sched = get_scheduler()
        jobs = {j.id for j in sched.get_jobs()}
        for jid in list(jobs):
            if jid.startswith('sched_'):
                sid = int(jid.split('_', 1)[1])
                s = db.session.get(Schedule, sid)
                if s is None or not s.enabled:
                    try:
                        sched.remove_job(jid)
                    except JobLookupError:
                        pass
        for s in Schedule.query.filter_by(enabled=True).all():
            if _job_id(s.id) not in jobs:
                _register_job(s)
        _prune_old_sign_records()


def _prune_old_sign_records():
    """按 sign_log_retention_days 清理超期执行日志（全局策略，不区分用户）。
    读取失败回退默认值，清理异常仅记录不中断对账周期。"""
    try:
        days = get_setting('sign_log_retention_days') or 180
        cutoff = now_cst() - timedelta(days=int(days))
        deleted = SignRecord.query.filter(SignRecord.created_at < cutoff).delete()
        if deleted:
            db.session.commit()
            log.info('清理超期签到日志 %d 条（保留 %d 天）', deleted, int(days))
    except Exception as e:
        db.session.rollback()
        log.warning('签到日志自动清理失败：%s', e)


def _extract_jitter(schedule):
    """随机延迟上限（分钟）→ 供 CronTrigger.jitter 使用（秒）。
    统一从解析后的配置 time.randomDelayMax 取（standalone/follow 二者均落在 _resolve 的完整配置里）；
    custom 为内联 time-only 扁平结构，随机延迟在 schedule.custom 顶层。旧实现对 standalone 误读
    schedule.custom（空）导致 jitter=0、多任务整点一起触发，现已修正。
    口径实现在 schedule_utils.extract_jitter_minutes（与前端展示的 nextRunJitterMin 共用）。"""
    return extract_jitter_minutes(schedule)


def _register_job(schedule):
    """为单个 Schedule 注册/替换 cron job；无有效时刻则跳过（不应发生，enabled 已校验）。
    随机延迟通过 CronTrigger.jitter 实现：每次触发在 [0, randomDelayMax*60) 秒间随机漂移，
    避免多账号在同一分钟整点集中打卡。"""
    sched = get_scheduler()
    hour, minute, weekdays = extract_schedule_time(schedule)
    if hour is None or minute is None or not weekdays:
        log.warning('任务 %s 缺少有效执行时刻，跳过注册', schedule.id)
        return
    trigger_kwargs = dict(
        day_of_week=','.join(str(w - 1) for w in weekdays),
        hour=hour, minute=minute,
        timezone=_scheduler_tz(),
    )
    jitter = _extract_jitter(schedule)
    if jitter and jitter > 0:
        trigger_kwargs['jitter'] = jitter * 60  # CronTrigger.jitter 单位为秒
    trigger = CronTrigger(**trigger_kwargs)
    sched.add_job(run_schedule, trigger=trigger, id=_job_id(schedule.id),
                  args=[schedule.id], replace_existing=True)


def run_schedule(schedule_id):
    """执行入口（被 APScheduler job 与测试直接调用）。全程异常隔离，不向上抛。"""
    if _app is None:
        return
    with _app.app_context():
        _run(schedule_id)


def _run(schedule_id):
    """执行入口（被 run_schedule 调用）。异常由 _execute 内部就地回写，
    此处仅兜底提交失败等极端情况。"""
    s = db.session.get(Schedule, schedule_id)
    if s is None or not s.enabled:
        return
    try:
        _execute(s)
    except Exception as e:
        log.exception('任务 %s 外层兜底异常', schedule_id)
        try:
            _commit_result(s, None, 'fail', f'执行异常：{e}')
        except Exception:
            pass


def _resolve(schedule):
    """解析任务真实执行配置。
    standalone（config_json 非空）= 任务自持完整配置，权威来源；
    follow = 配置套 + 字段级覆盖浅合并（overrides 顶层键替换套内同键，未覆盖键继续跟随配置套）；
    custom = 内联 time-only。缺配置返回 None。"""
    if schedule.has_own_config:
        return schedule.config or {}
    if schedule.mode == 'follow':
        if not schedule.config_set_id:
            return None
        cs = db.session.get(ConfigSet, schedule.config_set_id)
        if cs is None:
            return None
        return {**(cs.config or {}), **(schedule.overrides or {})}
    return schedule.custom or {}


def _resolve_ua(resolved):
    """UA 解析：advanced.customUa 非空优先，其次 uaTemplateId → UA 模板池内容，否则 None（适配器默认 UA）"""
    adv = (resolved or {}).get('advanced') or {}
    custom = (adv.get('customUa') or '').strip()
    if custom:
        return custom
    ua_id = adv.get('uaTemplateId')
    if ua_id:
        try:
            ua = db.session.get(PoolUa, int(ua_id))
            if ua is not None and (ua.content or '').strip():
                return ua.content.strip()
        except (TypeError, ValueError):
            pass
    return None


def _load_location(resolved):
    """位置池解析：返回 PoolLocation 或 None（locationId 缺失/非法/不可见均视为未配置）"""
    loc_id = (resolved or {}).get('locationId')
    if not loc_id:
        return None
    try:
        return db.session.get(PoolLocation, int(loc_id))
    except (TypeError, ValueError):
        return None


def _parse_platform_time(s):
    """解析平台任务时间窗（know 'HH:mm:ss' / sign 'HH:mm'），非法返回 None"""
    try:
        parts = [int(x) for x in str(s).split(':')]
        from datetime import time as dtime
        return dtime(parts[0], parts[1], parts[2] if len(parts) > 2 else 0)
    except (TypeError, ValueError, IndexError):
        return None


def _checkin_flow(schedule, acc, session, resolved, remark):
    """提交签到主流程（模块 E）。返回 (outcome, reason, extra)；extra 供推送与详情。

    时序：找进行中任务 → 平台时间窗 → 定位（位置池优先，回退围栏中心）→ 围栏拦截
    （配置套 fence.intercept 开关，默认开）→ 需图校验 → 认领图库图片 → 提交。
    图片认领发生在提交前（提交需要图片字节）；提交失败或异常时回滚认领
    （recycle/trash → 恢复 active；delete 不回滚）；credential 异常向上抛，
    由 _execute 重登后整体重试（重试前同样回滚认领）。"""
    uid = schedule.user_id
    adapter = get_adapter()
    image_cfg = (resolved or {}).get('image') or {}
    strategy = image_cfg.get('strategy') if image_cfg.get('strategy') in ('recycle', 'trash', 'delete') else 'trash'
    group_raw = image_cfg.get('groupId')
    try:
        group = int(group_raw) if group_raw not in (None, '', 0) else None
    except (TypeError, ValueError):
        group = None

    claimed = None
    try:
        # ① 进行中任务（提交只能用 /list 的任务 id）
        ctx = adapter.find_active_task(session, schedule.task_type)
        if ctx is None:
            return 'skip', '当前无进行中的签到任务', {}
        task = ctx['task']

        # ② 平台任务时间窗（know 'HH:mm:ss' / sign 'HH:mm'）
        ts = _parse_platform_time(task.get('startTime'))
        te = _parse_platform_time(task.get('endTime'))
        now_t = now_cst().time()
        if ts and te and (now_t < ts or now_t > te):
            return 'skip', f'当前时间不在平台任务时间窗（{task.get("startTime")}~{task.get("endTime")}）', {}

        # ③ 定位：位置池配置优先（按 offset_m 抖动）；未配置回退任务围栏中心（默认 10 米）；
        #    均无则提交空定位（与旧版行为一致），记 warning 供详情展示
        warning = None
        loc = _load_location(resolved)
        fence = (ctx.get('fence') or [{}])[0] if ctx.get('fence') else {}
        if loc is not None and loc.lat is not None and loc.lng is not None:
            lat, lng = geo.apply_location_jitter(loc.lat, loc.lng, loc.offset_m or 10)
            address = loc.address or ''
        elif fence.get('latitude') and fence.get('longitude'):
            lat, lng = geo.apply_location_jitter(fence.get('latitude'), fence.get('longitude'), 10)
            address = fence.get('location') or ''
            warning = '未配置签到位置，已回退使用任务围栏中心'
        else:
            lat = lng = None
            address = ''
            warning = '未配置签到位置，将提交空定位'
        location_str = f'{lng}:{lat}' if lat and lng else ''

        # ④ 围栏拦截（配置套 fence.intercept，默认开）：配置点超出围栏半径则本地拒绝，
        #    防止异常位置暴露风险；服务端已确认不做距离校验，拦截纯为客户端自保
        intercept = bool((resolved.get('fence') or {}).get('intercept', True))
        if intercept and fence and lat is not None and fence.get('latitude'):
            dist = geo.haversine_m(lat, lng, fence.get('latitude'), fence.get('longitude'))
            try:
                radius = float(fence.get('radius') or 0)
            except (TypeError, ValueError):
                radius = 0
            if dist is not None and radius > 0 and dist > radius:
                return 'fail', (f'围栏拦截：配置位置距签到点 {int(dist)} 米，'
                                f'超出围栏半径 {int(radius)} 米（请调整位置池坐标，'
                                f'或在配置套中关闭围栏拦截）'), {}

        # ⑤ 图片：任务需要图但未启用图库 → fail（宁可失败可感知，不静默交白卷）；
        #    启用则先认领（原子抢占防同组并发取同一张），失败提交后回滚
        need_photo = bool(task.get('needPhoto'))
        if need_photo and not image_cfg.get('enabled'):
            return 'fail', '该任务需要上传签到图片，请在配置套中启用图库并确认有可用图片', {}
        if image_cfg.get('enabled'):
            claimed = claim_image_for_submit(uid, group, strategy)
            if not claimed:
                return 'fail', '图库暂无可用图片，请先上传或调整取图范围', {}

        # ⑥ 提交（know 实证契约 / sign 镜像契约）
        image = ({'bytes': claimed['bytes'], 'filename': generate_image_filename()}
                 if claimed else None)
        submit_remark = remark if remark and remark != '—' else None
        try:
            result = adapter.submit_checkin(session, schedule.task_type, task.get('id'),
                                            location_str, address, submit_remark, image)
            if result.status != 'success' and claimed:
                rollback_claim(claimed['id'], uid, strategy)
                claimed = None
        except Exception:
            if claimed:
                rollback_claim(claimed['id'], uid, strategy)
                claimed = None
            raise

        extra = {'warning': warning, 'task_name': task.get('taskName') or '',
                 'image_id': claimed['id'] if claimed else None, 'strategy': strategy}
        if result.status == 'success':
            return 'success', '', extra
        return result.status, result.fail_reason or '平台返回失败', {}
    except BPlatformError:
        if claimed:
            rollback_claim(claimed['id'], uid, strategy)
        raise
    except Exception:
        if claimed:
            rollback_claim(claimed['id'], uid, strategy)
        raise


def _execute(schedule):
    acc = db.session.get(BAccount, schedule.account_id)
    if acc is None or not acc.enabled:
        log.info('任务 %s 跳过：账号不存在或已禁用', schedule.id)
        return  # 禁用态不写记录，避免刷屏

    outcome = None
    reason = ''
    extra = {}
    try:
        if acc.verify_status != 'ok':
            try:
                res = get_adapter().verify_and_fetch(acc.account, acc.get_password())
            except BPlatformError as e:
                log.warning('任务 %s 账号校验失败：%s', schedule.id, e.message)
                _commit_result(schedule, acc, 'fail', f'账号校验失败：{e.message}')
                return
            acc.set_token(res.token)
            acc.set_profile(res.profile)
            acc.bp_uid = res.bp_uid
            acc.verify_status = 'ok'
            acc.verified_at = now_cst()
            db.session.flush()

        resolved = _resolve(schedule)
        if resolved is None:
            _commit_result(schedule, acc, 'skip', '配置缺失（配置套未绑定或已删除）')
            return
        # 本次实际提交的单条备注：多条随机选一、单条即用该条、无则占位；
        # 同时交给提交与推送展示，保证「提交什么就推送什么」。
        submitted_remark = _select_remark(resolved)
        session = {
            'token': acc.get_token(),
            'account': acc.account,
            'profile': acc.profile,
            'ua': _resolve_ua(resolved),
        }
        try:
            outcome, reason, extra = _checkin_flow(schedule, acc, session, resolved, submitted_remark)
        except BPlatformError as e:
            if e.kind != 'credential':
                raise
            # 登录态失效：重登刷新后整体重试一次（图片认领已在流程内回滚，重试重新认领）
            log.info('任务 %s 提交遇登录态失效，重登后重试', schedule.id)
            res = get_adapter().verify_and_fetch(acc.account, acc.get_password())
            acc.set_token(res.token)
            acc.set_profile(res.profile)
            acc.bp_uid = res.bp_uid
            acc.verify_status = 'ok'
            acc.verified_at = now_cst()
            db.session.flush()
            session['token'] = res.token
            outcome, reason, extra = _checkin_flow(schedule, acc, session, resolved, submitted_remark)
        # 统一在此回写：成功/失败/跳过都落 SignRecord 并回写任务与账号状态
        _commit_result(schedule, acc, outcome, reason)
    except BPlatformError as e:
        # acc 仍在作用域内，账号聚合与任务状态一同更新，杜绝两者不一致
        if e.kind == 'credential':
            acc.verify_status = 'fail'  # 凭证失效，下次执行触发 reverify
        log.warning('任务 %s 执行异常（B 平台）：%s', schedule.id, e.message)
        _commit_result(schedule, acc, 'fail', f'B 平台错误：{e.message}')
        return
    except Exception as e:
        log.exception('任务 %s 执行异常', schedule.id)
        _commit_result(schedule, acc, 'fail', f'执行异常：{e}')
        return

    # 后置动作（推送）与「执行结果落库」解耦：失败仅记日志，
    # 绝不再写第二条 SignRecord，避免一次执行产生「成功 + 失败」两条重复日志
    try:
        if outcome is not None:
            # 成功且图片策略可回看时，推送带签到凭证图 URL（delete 已物理删除故无 URL）
            image_url = ''
            if outcome == 'success' and extra.get('image_id') and extra.get('strategy') in ('recycle', 'trash'):
                base = os.getenv('PUSH_IMAGE_BASE', '').strip().rstrip('/')
                if base:
                    image_url = f"{base}/api/pools/images/{extra['image_id']}/file"
            dispatch_push(resolved, schedule, acc, outcome, reason,
                          image_url=image_url, submitted_remark=submitted_remark)
    except Exception as e:
        log.warning('任务 %s 后置动作失败（已落库的执行记录不受影响）：%s', schedule.id, e)


def _select_remark(resolved):
    """本次提交实际选用的单条备注：多条随机选一、单条即用该条、无则占位。
    选择结果与 checkin 提交、推送展示共用，确保「提交什么就推送什么」，避免
    多条备注被一并塞进推送（曾误把所有备注用 ' / ' 拼接上报）。"""
    import random
    remarks = (resolved or {}).get('remarks') or []
    remarks = [str(r).strip() for r in remarks if str(r).strip()]
    if not remarks:
        return '—'
    if len(remarks) == 1:
        return remarks[0]
    return random.choice(remarks)


def _commit_result(schedule, acc, status, fail_reason=''):
    """写签到记录 + 回写任务状态 + 刷新账号最近签到聚合；统一提交。"""
    rec = SignRecord(
        user_id=schedule.user_id,
        account_id=schedule.account_id,
        schedule_id=schedule.id,
        task_name='寝室签到' if schedule.task_type == 'dorm' else '活动签到',
        task_type=schedule.task_type,
        sign_date=now_cst().date(),
        signed_at=now_cst() if status == 'success' else None,
        status=status,
        fail_reason=fail_reason,
        initiator='system',
    )
    db.session.add(rec)
    schedule.last_run_at = now_cst()
    schedule.last_status = status
    schedule.run_count = (schedule.run_count or 0) + 1
    schedule.next_run_at = compute_next_run(schedule)
    if acc is not None:
        acc.last_sign_at = now_cst()
        acc.last_sign_status = status
    db.session.commit()


def dispatch_push(resolved, schedule, acc, status='success', reason='', image_url='', submitted_remark=''):
    """按配置套 push 分发执行结果（ServerChan / PushPlus / Email）。
    读取配置套的 push 结构：channels 决定通道、useOwnCredential 决定密钥来源
    （直接填写用 push.cred 内联字段；回填凭证用 push.credIds 引用资源池并解密）；
    notify 开关控制各状态是否推送。无可用密钥则不发，发送失败仅记录，不影响主链路。
    标题含签到账号姓名 + 状态；内容按 push.template(html/txt/markdown) 渲染，含账号/任务/
    时间/位置/备注/图片；长度受 pushplus 限制守护。"""
    push = (resolved or {}).get('push')
    if not isinstance(push, dict) or not push:
        log.info('任务 %s 未配置推送，跳过分发', schedule.id)
        return
    channels = push.get('channels') or []
    if not channels:
        log.info('任务 %s 未选择任何推送通道，跳过分发', schedule.id)
        return
    notify = push.get('notify')
    if not isinstance(notify, dict) or not notify:
        notify = {'success': True, 'skip': True, 'fail': True}
    if not notify.get(status, False):
        log.info('任务 %s 状态=%s 被 notify 开关关闭，跳过推送', schedule.id, status)
        return

    creds, issues = _resolve_push_creds(push, schedule.user_id)
    for msg in issues:
        log.warning('任务 %s 推送通道被跳过：%s', schedule.id, msg)
    if not creds:
        log.warning('任务 %s 未解析到任何可用推送凭证（通道=%s），跳过推送',
                    schedule.id, channels)
        return

    template = push.get('template') or 'html'
    ctx = build_ctx(acc, schedule, resolved, status, reason=reason,
                    image_url=image_url, remark=submitted_remark or None)
    results = []
    for ch, key in creds.items():
        try:
            ok, err = send_channel(ch, key, ctx, template)
        except Exception as e:  # 单通道内部异常不阻断其它通道
            ok, err = False, f'内部异常：{e}'
        results.append(f'{ch}={"成功" if ok else f"失败（{err}）"}')
        if ok:
            log.info('任务 %s %s 推送成功', schedule.id, ch)
        else:
            log.warning('任务 %s %s 推送失败：%s', schedule.id, ch, err)
    log.info('任务 %s 推送汇总：%s', schedule.id, '；'.join(results))


def _resolve_push_creds(push, user_id):
    """从 push 结构解析出各通道可用密钥。
    useOwnCredential=true（回填我的凭证）→ 按 push.credIds 解密资源池凭证（仅限本人）；
    useOwnCredential=false（直接填写）→ 读 push.cred 内联字段。
    返回 (creds, issues)：creds={channel: key_or_fields} 仅含已选且密钥非空的通道；
    issues=[被跳过通道的原因]——凭证解析失败必须显式暴露（此前静默 continue，
    通道被跳过用户完全无感知，表现为「设置了推送但从不推送」且无从排查）。"""
    channels = push.get('channels') or []
    use_own = push.get('useOwnCredential', False)
    out = {}
    issues = []

    def _cred_fields(cid):
        c = db.session.get(PoolCredential, cid)
        if c is None or not c.enabled or c.user_id != user_id:
            return None, '凭证不存在或已停用'
        try:
            return json.loads(decrypt(c.secret_enc)), None
        except Exception:
            return None, '凭证解密失败（主密钥不匹配或数据损坏）'

    if use_own:
        cred_ids = push.get('credIds') or {}
        for ch in channels:
            cid = cred_ids.get(ch)
            if not cid:
                issues.append(f'{ch} 通道未绑定凭证')
                continue
            fields, err = _cred_fields(cid)
            if fields is None:
                issues.append(f'{ch} 通道{err}')
                continue
            key_field = {'serverchan': 'serverchanKey', 'pushplus': 'pushplusToken'}.get(ch)
            if key_field and fields.get(key_field):
                out[ch] = fields[key_field]
                continue
            if ch == 'email' and fields.get('emailSmtp') and fields.get('emailFrom') and fields.get('emailTo'):
                out[ch] = {k: fields.get(k) for k in ('emailSmtp', 'emailFrom', 'emailPass', 'emailTo')}
                continue
            issues.append(f'{ch} 通道凭证缺少必要字段')
    else:
        cred = push.get('cred') or {}
        if 'serverchan' in channels and cred.get('serverchanKey'):
            out['serverchan'] = cred['serverchanKey']
        if 'pushplus' in channels and cred.get('pushplusToken'):
            out['pushplus'] = cred['pushplusToken']
        if 'email' in channels:
            email = {k: cred.get(k) for k in ('emailSmtp', 'emailFrom', 'emailPass', 'emailTo')}
            if email.get('emailSmtp') and email.get('emailFrom') and email.get('emailTo'):
                out['email'] = email
            else:
                issues.append('email 通道内联凭证缺少 SMTP 地址/发件人/收件人字段')
    return out, issues
