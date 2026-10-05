# 调度器主链路（模块 D）：APScheduler 注册 cron job，到点执行 B 平台签到，
# 写签到记录、回写任务状态、按需分发推送。采用「事件钩子 + 周期性对账」双保险：
# 路由增删改任务即时注册/移除 job；30s 对账线程兜底清理账号级联删除遗留的孤儿 job。
# [部署约束] 调度器随 Web 进程存活、job 存于内存，全系统只允许单实例运行：
# 多 worker / 多进程部署会让各进程重复注册同一批任务，横向扩容前须先拆出独立调度进程。
import atexit
import logging
import os
import time
from datetime import timedelta

import json
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.base import JobLookupError
# 注意是 APScheduler 自带的线程池执行器（默认 max_workers=10），非标准库同名类
from apscheduler.executors.pool import ThreadPoolExecutor
# 标准库线程池：仅用于推送通道并发扇出（与 APScheduler 执行线程池互不干扰）
from concurrent.futures import ThreadPoolExecutor as FuturesThreadPool, as_completed

from app.extensions import db
from app.models import ActivityWindow, BAccount, ConfigSet, JwAccount, OpLog, Schedule, SignRecord, PushLog
from app.models.b_account import binding_cred_id
from app.models.group_push import PushGroup, PushGroupMember
from app.models.pools import ImageGroup, PoolCredential, PoolLocation, PoolUa
from app.models.system_config import get_setting
from app.models.user import now_cst
from app.services import geo
from app.services.b_platform import get_adapter
from app.services.b_platform.base import BPlatformError
from app.services.b_platform.real import generate_image_filename
from app.services.crypto import decrypt, InvalidToken
from app.services.image_store import claim_image_for_submit, rollback_claim
from app.services.jwxt.sync import expand_windows_daily, expand_windows_for_schedule_locked
from app.services.push_render import build_ctx, send_channel
from app.utils.schedule_utils import (compute_next_run, extract_jitter_minutes,
                                      extract_schedule_time, resolve_activity_cfg,
                                      resolve_config)

log = logging.getLogger('scheduler')

# ===== 执行时配置快照（详情回显用）=====
# 把 resolved 配置渲染成带有可读名称的展示快照，在落库瞬间抓取，作为该条日志的
# 历史切片 —— 之后即使位置池/配置套改名或删除，历史记录亦不受影响。
_CHANNEL_LABELS = {'serverchan': 'Server酱', 'pushplus': 'PushPlus', 'email': '邮箱'}
_IMAGE_STRATEGY_LABELS = {'recycle': '循环复用', 'trash': '用后入回收站', 'delete': '用后删除'}
_WEEKDAY_NAMES = {1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六', 7: '日'}
_MODE_LABELS = {'follow': '跟随配置套', 'custom': '自定义', 'standalone': '独立配置'}


def _snap_to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _snap_fmt_hm(hour, minute):
    try:
        return f'{int(hour):02d}:{int(minute):02d}'
    except (TypeError, ValueError):
        return ''


def _snap_weekday_label(weekdays):
    ws = sorted({int(w) for w in (weekdays or []) if _snap_to_int(w) and 1 <= int(w) <= 7})
    if not ws:
        return '未设置'
    if ws == [1, 2, 3, 4, 5, 6, 7]:
        return '每天'
    if ws == [1, 2, 3, 4, 5]:
        return '工作日'
    if ws == [6, 7]:
        return '周末'
    return '、'.join(f'周{_WEEKDAY_NAMES[w]}' for w in ws)


def build_config_view(schedule, resolved, uid, acc=None):
    """将 resolved 配置渲染为执行时配置快照（含可读名称）。无 resolved 返回 None。
    acc 用于「按分组取图」模式解析本账号实际取图范围，快照记录的是真实使用的图库。"""
    if not resolved:
        return None
    cfg = resolved

    time_cfg = cfg.get('time') or {}
    sign_time = time_cfg.get('signTime') or {}
    sh, eh = time_cfg.get('startHour'), time_cfg.get('endHour')
    time_view = {
        'mode': time_cfg.get('mode') or 'normal',
        'signTime': _snap_fmt_hm(sign_time.get('hour'), sign_time.get('minute')),
        'weekdayLabel': _snap_weekday_label(time_cfg.get('weekdays')),
        'window': (f'{int(sh):02d}:00 - {int(eh):02d}:00'
                   if _snap_to_int(sh) is not None and _snap_to_int(eh) is not None else '—'),
        'randomDelayMax': _snap_to_int(time_cfg.get('randomDelayMax')) or 0,
    }

    loc_view = None
    loc_id = _snap_to_int(cfg.get('locationId'))
    if loc_id:
        loc = db.session.get(PoolLocation, loc_id)
        if loc is not None:
            loc_view = {'id': loc.id, 'name': loc.name, 'address': loc.address or '',
                        'lat': loc.lat, 'lng': loc.lng, 'offsetM': loc.offset_m}

    image_cfg = cfg.get('image') or {}
    image_mode = 'byGroup' if image_cfg.get('mode') == 'byGroup' else 'fixed'
    group_kind = (image_cfg.get('groupKind') if image_cfg.get('groupKind') in
                  (PushGroup.TYPE_CLASS, PushGroup.TYPE_DORM) else PushGroup.TYPE_DORM)
    # byGroup 按账号实时解析，与 _checkin_flow 共用 resolve_image_group，
    # 保证快照记的就是本次真正取图的图库（fixed 直接取配置值，不查库）
    gid = (resolve_image_group(uid, cfg, acc) if image_mode == 'byGroup'
           else _snap_to_int(image_cfg.get('groupId')))
    group_name = ''
    if gid:
        g = db.session.get(ImageGroup, gid)
        group_name = g.name if g else ''
    image_view = {
        'enabled': bool(image_cfg.get('enabled')),
        'strategy': image_cfg.get('strategy') or '',
        'strategyLabel': _IMAGE_STRATEGY_LABELS.get(image_cfg.get('strategy'), '—'),
        'mode': image_mode,
        'groupKind': group_kind,
        'groupId': gid,
        'groupName': group_name,
    }

    push_cfg = cfg.get('push') or {}
    channels = push_cfg.get('channels') or []
    use_own = bool(push_cfg.get('useOwnCredential'))
    use_account = bool(push_cfg.get('useAccountCredential'))
    # 各账号自带凭证时凭证名逐账号不同，快照里不展示配置套级凭证名
    cred_ids = push_cfg.get('credIds') or {} if (use_own and not use_account) else {}
    cred_names = {}
    for ch in channels:
        cid = _snap_to_int(cred_ids.get(ch))
        if not cid:
            continue
        c = db.session.get(PoolCredential, cid)
        # 仅认本人凭证：他人凭证即便 id 命中也不展示名称（与 _resolve_push_creds 口径一致）
        if c is not None and c.user_id == uid:
            cred_names[ch] = c.name
    notify = push_cfg.get('notify')
    if not isinstance(notify, dict) or not notify:
        notify = {'success': True, 'skip': True, 'fail': True}
    push_view = {
        'channels': [{'key': ch, 'label': _CHANNEL_LABELS.get(ch, ch),
                      'credentialName': cred_names.get(ch, '')} for ch in channels],
        'template': push_cfg.get('template') or 'html',
        'useOwnCredential': use_own,
        'useAccountCredential': use_account,
        'credSourceLabel': '各账号自带凭证' if use_account else ('回填我的凭证' if use_own else '直接填写'),
        'notify': notify,
    }

    adv_cfg = cfg.get('advanced') or {}
    ua_name = ''
    ua_id = _snap_to_int(adv_cfg.get('uaTemplateId'))
    if ua_id:
        ua = db.session.get(PoolUa, ua_id)
        if ua is not None:
            ua_name = (ua.remark or '').strip() or (ua.content or '').strip()[:24]
    advanced_view = {
        'uaTemplateId': ua_id,
        'uaTemplateName': ua_name,
        'customUa': adv_cfg.get('customUa') or '',
    }

    # 活动签到专属块快照（课表驱动调度参数）；fixed 策略或缺失时为 None
    act_cfg = cfg.get('activity') or {}
    activity_view = None
    if act_cfg.get('strategy') == 'course':
        course = act_cfg.get('course') or {}
        fallback = act_cfg.get('fallback') or {}
        activity_view = {
            'strategy': 'course',
            'leadMinutes': _snap_to_int(course.get('leadMinutes')),
            'tailMinutes': _snap_to_int(course.get('tailMinutes')),
            'pollIntervalSec': _snap_to_int(course.get('pollIntervalSec')),
            'excludeCourses': course.get('excludeCourses') or [],
            'weekdays': course.get('weekdays') or [],
            'fallbackEnabled': bool(fallback.get('enabled', True)),
        }

    # 配置套来源：follow 实时跟随、套用配置套后 mode=standalone 但 config_set_id 仍保留为来源标签；
    # 两者都要解析套名（用于「来自配置套 X」与快照来源展示），而非仅 follow 才解析。
    cs_name = None
    if schedule.config_set_id:
        cs = db.session.get(ConfigSet, schedule.config_set_id)
        cs_name = cs.name if cs else None

    mode = schedule.mode
    if mode == 'standalone' and schedule.config_set_id:
        # 套用配置套：自持快照但来源标签仍在，不应显示「独立配置」；来源套已删除时降级为「独立配置」
        mode_label = '套用配置套' if cs_name else '独立配置'
    else:
        mode_label = _MODE_LABELS.get(mode, mode)

    return {
        'mode': schedule.mode,
        'modeLabel': mode_label,
        'configSetId': schedule.config_set_id,
        'configSetName': cs_name,
        'time': time_view,
        'location': loc_view,
        'fence': cfg.get('fence') or {},
        'remarks': cfg.get('remarks') or [],
        'image': image_view,
        'push': push_view,
        'advanced': advanced_view,
        'activity': activity_view,
    }


# 进程级单例
_app = None
_scheduler = None
_started = False
_atexit_registered = False

RECONCILE_JOB_ID = '_reconcile'
_RECONCILE_SECONDS = 30
# 启动对账补跑宽限：仅补跑「计划时刻在当天」的任务。两类任务的时间规律都锚定当天——
# 寝室签到按辅导员节奏当天发布当晚有效（如周日/周四晚），活动签到按上午/下午时段
# 当天有效；跨天之后平台任务窗口必然已关闭，补跑只会产出必然失败的噪音记录与推送，
# 改为落一条 skip 说明并推进 next_run_at。环境变量可调：0 = 不限（不推荐）。
_RECONCILE_SAME_DAY_ONLY = (os.getenv('SCHEDULER_RECONCILE_SAME_DAY', '1').lower()
                            not in ('0', 'false'))
# 超期日志清理周期（每日一次）
_PRUNE_INTERVAL_HOURS = 24


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
        # 启动漏跑对账：进程重启落在签到时刻附近时，cron 只会排「下一次未来时刻」，
        # 刚过去的触发会被静默丢失（无记录、无失败、无推送），此处按 DB 缓存的
        # next_run_at 找回并补跑（详见 _reconcile_missed_runs）
        _reconcile_missed_runs()
        # 活动课表窗口：启动即重建当日窗口（进程重启不丢当日课表调度）
        try:
            expand_windows_daily()
        except Exception:
            log.exception('启动期活动窗口展开失败（不影响 cron 注册）')
    sched.add_job(reconcile, 'interval', seconds=_RECONCILE_SECONDS,
                  id=RECONCILE_JOB_ID, replace_existing=True)
    # 超期日志清理：每日独立 job（启动后 30s 先跑一次，此后 24h 周期）
    sched.add_job(
        _prune_old_sign_records, 'interval', hours=_PRUNE_INTERVAL_HOURS,
        id='_prune_logs', replace_existing=True,
        next_run_time=now_cst() + timedelta(seconds=30),
    )
    # 活动窗口每日展开：00:10 重建当日窗口（跨零点清掉昨日，按新课表/新配置生成）
    sched.add_job(
        _expand_windows_job, 'cron', hour=0, minute=10,
        id='_expand_windows', replace_existing=True, timezone=_scheduler_tz(),
    )
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


def _reconcile_missed_runs():
    """启动漏跑对账：进程重启落在签到时刻附近时，重新注册的 cron 只会排
    「下一次未来时刻」，刚过去的触发被静默丢失——无记录、无失败、无推送。
    以 DB 缓存的 next_run_at 为基准：enabled 且 next_run_at <= now 的任务分两档：
    计划时刻在**当天**（SCHEDULER_RECONCILE_SAME_DAY=1，默认开）→ 安排立即补跑
    （每任务错峰 2 秒，避免重启瞬间集中打向 B 平台）；计划时刻在**昨天及更早**
    → 平台任务窗口必然已关闭（两类签到任务都只当天有效），补跑只会产出必然
    失败的噪音记录与推送，改为落一条 skip 说明并推进 next_run_at。

    补跑走完整执行链路（run_schedule）：内部自会做账号可用性与平台时间窗校验，
    不适用的场景（如平台无进行中任务）会如实落 skip/fail 记录而非凭空消失，
    并把 next_run_at 推进到未来、不会重复进入本对账。

    防重复提交：_commit_result 中签到记录与 next_run_at 同事务原子提交——
    已成功执行的任务 next_run_at 必已推进到未来，不会进入本对账；唯一残留歧义是
    「平台已受理但进程在落库前崩溃」，此时补跑最坏得到一条平台「已签到」的
    业务失败记录，不会产生两条成功日志。"""
    now = now_cst()
    stale = (Schedule.query
             .filter(Schedule.enabled.is_(True),
                     Schedule.next_run_at.isnot(None),
                     Schedule.next_run_at <= now)
             .all())
    if not stale:
        return
    runnable, expired = [], []
    for s in stale:
        # 同日判定：计划时刻的日期 == 今天才补跑（跨天即视为平台窗口已关）
        if not _RECONCILE_SAME_DAY_ONLY or s.next_run_at.date() == now.date():
            runnable.append(s)
        else:
            expired.append(s)
    if runnable:
        log.info('启动对账：发现 %d 个任务的计划执行时刻已过，安排补跑', len(runnable))
        sched = get_scheduler()
        for idx, s in enumerate(runnable):
            sched.add_job(
                run_schedule,
                trigger=DateTrigger(run_date=now + timedelta(seconds=2 * idx)),
                args=[s.id, True],
                id=f'_reconcile_{s.id}',
                replace_existing=True,
            )
    if expired:
        # 跨天超期任务：不补跑，落一条 skip 说明留痕（_commit_result 自会推进
        # next_run_at 到下一次未来时刻），保持「任何结局都有痕」；
        # skip 结果照常走推送分发（notify.skip 开关裁决），与正常路径同口径。
        log.info('启动对账：%d 个任务的计划时刻在昨天及更早，不补跑，仅推进计划时刻',
                 len(expired))
        for s in expired:
            missed_at = s.next_run_at
            acc = db.session.get(BAccount, s.account_id)
            rec = _commit_result(s, acc, 'skip',
                                 f'计划执行时刻（{missed_at:%m-%d %H:%M}）已跨天，'
                                 f'平台任务窗口已关闭，启动对账不再补跑')
            resolved = _resolve(s)
            _push_outcome(s, acc, resolved, 'skip', rec.fail_reason, rec)


def sync_schedule(schedule):
    """事件钩子：单个任务状态/参数变更后对齐 job 注册与课表窗口。
    enabled → 注册/替换 cron（course 策略且关闭兜底时不注册）并展开当日窗口；
    停用 → 移除 cron 并清空当日窗口。不依赖调度器是否已 start。"""
    if schedule.enabled:
        _register_job(schedule)
        try:
            if resolve_activity_cfg(schedule) is not None:
                expand_windows_for_schedule_locked(schedule)
        except Exception:
            log.exception('任务 %s 课表窗口展开失败（不影响 cron 注册）', schedule.id)
    else:
        remove_job(schedule.id)
        try:
            ActivityWindow.query.filter_by(schedule_id=schedule.id).delete(synchronize_session=False)
            db.session.commit()
        except Exception:
            db.session.rollback()
            log.exception('任务 %s 停用清空活动窗口失败', schedule.id)


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
    - 活动课表窗口轮询：命中窗口内且到间隔的活动任务发起 B 平台查询（见 _poll_activity_windows）
    超期签到日志清理已拆出为每日独立 job（_prune_logs），不再挂在 30s 对账上——
    按 created_at 范围 DELETE 的清理无需 30 秒级的执行频率。"""
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
        try:
            _poll_activity_windows()
        except Exception:
            db.session.rollback()
            log.exception('活动窗口轮询异常（不影响 cron 对账）')
        # 群合并推送对账兜底：补发到点未发的待触发记录（防延迟 job 丢失，非 EOD 补发）
        try:
            from app.services.group_digest import reconcile_pending_digests
            reconcile_pending_digests()
        except Exception:
            db.session.rollback()
            log.exception('群合并推送对账异常（不影响 cron 对账）')


def _expand_windows_job():
    """活动窗口每日展开 job 包装（调度线程无 app context，自行进入）。"""
    if _app is None:
        return
    with _app.app_context():
        try:
            expand_windows_daily()
        except Exception:
            db.session.rollback()
            log.exception('活动窗口每日展开失败')


def _dispatch_run(schedule_id, course_name):
    """把完整签到链路派发到调度器线程池异步执行（T4）。

    reconcile 是 30s interval job 且 max_instances=1：若在心跳线程内就地跑
    run_schedule（登录/定位/提交/推送，最坏数分钟），心跳即被绑死——期间孤儿
    清理、状态对账、群推送补发全部顺延。改为 DateTrigger 立即派发后，心跳只做
    轻量对账，链路照常在线程池执行（30 workers 有充足余量）。
    链路自容错（run_schedule 全程异常隔离），派发失败仅记日志、窗口保持 done，
    由 cron 兜底（若启用）接管。"""
    try:
        sched = get_scheduler()
        sched.add_job(
            run_schedule, trigger=DateTrigger(run_date=now_cst()),
            args=[schedule_id], kwargs={'allow_retry': True, 'course_name': course_name},
            id=f'dispatch_{schedule_id}_{int(time.time() * 1000)}',
            replace_existing=False, misfire_grace_time=120,
        )
        return True
    except Exception:
        log.exception('任务 %s（%s）签到链路派发失败', schedule_id, course_name)
        return False


def _poll_activity_windows():
    """活动课表窗口轮询（30s 心跳内调用）：对"窗口内 + 到达轮询间隔 + 未完结"的
    活动任务查询一次 B 平台；查到进行中活动 → 窗口完结并转完整签到链路
    （定位/围栏/图片/提交/记录/推送全在链路内）；未查到 → 静默等待下一间隔
    （不写签到记录，避免高频空转刷屏）。凭证失效直接转完整链路（内部自会重登重试）；
    网络抖动保持窗口待下个周期再试。轮询时刻记在窗口行上，跨周期错峰。"""
    now = now_cst()
    windows = (ActivityWindow.query
               .filter(ActivityWindow.date == now.date(),
                       ActivityWindow.done.is_(False),
                       ActivityWindow.start_at <= now,
                       ActivityWindow.end_at >= now)
               .all())
    if not windows:
        return
    adapter = get_adapter()
    for w in windows:
        # 逐窗口重读时刻：链路内 commit 后时间推进，防止对已过窗口重复发起
        now = now_cst()
        if w.end_at < now:
            continue
        s = db.session.get(Schedule, w.schedule_id)
        if s is None or not s.enabled:
            w.done = True
            db.session.commit()
            continue
        act = resolve_activity_cfg(s)
        if act is None:
            # 配置已改回 fixed / 非 course：窗口作废（cron 兜底已接管）
            w.done = True
            db.session.commit()
            continue
        acc = db.session.get(BAccount, s.account_id)
        if acc is None or not acc.enabled:
            w.done = True
            db.session.commit()
            continue
        last = w.last_polled_at or w.start_at
        if (now - last).total_seconds() < act['poll']:
            continue
        w.last_polled_at = now
        resolved = _resolve(s)
        session = {
            'token': acc.get_token(),
            'account': acc.account,
            'profile': acc.profile,
            'ua': _resolve_ua(resolved),
        }
        try:
            ctx = adapter.find_active_task(session, 'activity') or {}
        except BPlatformError as e:
            db.session.commit()
            if e.kind == 'credential':
                # 凭证失效：完整链路内部自会重登重试（本轮视为已消费，防重复转正）
                w.done = True
                db.session.commit()
                log.info('窗口 %s 轮询遇凭证失效，转完整链路重登', w.id)
                _dispatch_run(s.id, w.course_name)
            else:
                log.info('窗口 %s 轮询失败（%s），下个周期再试', w.id, e.message)
            continue
        if not ctx.get('task'):
            # 该课程暂无待签活动：未发布或本人已签（后者保持轮询到期，与历史行为一致，
            # 避免误关掉同时段可能二次发布的活动窗口），仅记录轮询时刻
            db.session.commit()
            continue
        w.done = True
        db.session.commit()
        log.info('窗口 %s 命中活动任务（%s），转入签到流程', w.id, w.course_name)
        _dispatch_run(s.id, w.course_name)


def _prune_old_sign_records():
    """按 sign_log_retention_days 清理超期执行日志（全局策略，不区分用户），
    并按 op_log_retention_days（默认 365 天，长于签到日志）清理超期操作审计日志。
    作为每日独立 job 运行（此前挂在 30s 对账上，created_at 已加索引仍无必要逐 30s 扫描）。
    调度线程执行时无 Flask 应用上下文，此处自行入上下文（与 reconcile 同款守卫）；
    读取失败回退默认值，清理异常仅记日志不中断。"""
    if _app is None:
        return
    with _app.app_context():
        try:
            days = get_setting('sign_log_retention_days') or 180
            cutoff = now_cst() - timedelta(days=int(days))
            deleted = SignRecord.query.filter(SignRecord.created_at < cutoff).delete(synchronize_session=False)
            # push_logs 随签到日志同周期清理（created_at 与执行记录同刻生成）
            PushLog.query.filter(PushLog.created_at < cutoff).delete(synchronize_session=False)
            op_days = get_setting('op_log_retention_days') or 365
            op_cutoff = now_cst() - timedelta(days=int(op_days))
            op_deleted = OpLog.query.filter(OpLog.created_at < op_cutoff).delete(synchronize_session=False)
            # 登录失败计数（防爆破）过期清理：锁定态最长 15 分钟，7 天前的记录必然失去意义
            from app.services.login_guard import purge_expired as purge_login_failures
            lf_deleted = purge_login_failures(days=7)
            if deleted:
                log.info('清理超期签到日志 %d 条（保留 %d 天）', deleted, int(days))
            if op_deleted:
                log.info('清理超期用户日志 %d 条（保留 %d 天）', op_deleted, int(op_days))
            if lf_deleted:
                log.info('清理超期登录失败计数 %d 条', lf_deleted)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            log.warning('日志自动清理失败：%s', e)


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
    避免多账号在同一分钟整点集中打卡。
    活动 course 策略且关闭每日兜底时**不注册 cron**——该任务的执行完全由课表窗口轮询接管，
    全天零固定触发（无课日零查询）。"""
    act = resolve_activity_cfg(schedule)
    if act is not None and not act['fallbackEnabled']:
        remove_job(schedule.id)
        return
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


def run_schedule(schedule_id, allow_retry=True, course_name=None):
    """执行入口（被 APScheduler job 与测试直接调用）。全程异常隔离，不向上抛。
    allow_retry=False：网络失败补跑 job 自身失败不再级联安排重试（每次失败至多补跑一次）。
    course_name：活动课表窗口轮询命中时传入，签到记录据此溯源到课程。"""
    if _app is None:
        return
    with _app.app_context():
        _run(schedule_id, allow_retry=allow_retry, course_name=course_name)


def _run(schedule_id, allow_retry=True, course_name=None):
    """执行入口（被 run_schedule 调用）。异常由 _execute 内部就地回写，
    此处仅兜底提交失败等极端情况。"""
    s = db.session.get(Schedule, schedule_id)
    if s is None or not s.enabled:
        # 此处静默 return 会让「任务到点为什么没执行」彻底无从查起。能走到这里只可能是
        # 删任务/禁用后残留的 job（正常禁用会一并撤销 job），量极小，INFO 不会刷屏。
        log.info('任务 %s 未执行：任务不存在或已禁用', schedule_id)
        return
    try:
        _execute(s, allow_retry=allow_retry, course_name=course_name)
    except Exception as e:
        log.exception('任务 %s 外层兜底异常', schedule_id)
        try:
            _commit_result(s, None, 'fail', f'执行异常：{e}', course_name=course_name)
        except Exception:
            pass


def _resolve(schedule):
    """解析任务真实执行配置（口径统一在 schedule_utils.resolve_config，
    与课表窗口展开共用）。standalone（config_json 非空）= 任务自持完整配置，权威来源；
    follow = 配置套 + 字段级覆盖浅合并（overrides 顶层键替换套内同键，未覆盖键继续跟随
    配置套）；custom = 内联 time-only。缺配置返回 None。"""
    return resolve_config(schedule)


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


def resolve_image_group(uid, resolved, acc):
    """取图范围解析：返回图库分组 id，None = 不过滤分组（全部图库）。

    fixed（默认）：直接用配置套的 image.groupId。
    byGroup：按 image.groupKind（dorm 默认 / class）取该账号所属分组的图库归属，
    组内任一分组绑了图库即用之；账号不属任何分组、分组未绑图库或图库已被删，
    逐级回退配置套默认图库，仍为空则回退全部图库。单人寝室不必建分组，
    不建即自动走配置套默认图库，无需额外约定。"""
    image_cfg = (resolved or {}).get('image') or {}
    default_gid = _snap_to_int(image_cfg.get('groupId'))
    if image_cfg.get('mode') != 'byGroup':
        return default_gid
    kind = image_cfg.get('groupKind')
    if kind not in (PushGroup.TYPE_CLASS, PushGroup.TYPE_DORM):
        kind = PushGroup.TYPE_DORM
    return _account_group_image_id(uid, acc, kind) or default_gid


def _account_group_image_id(uid, acc, kind):
    """账号所属分组绑定的图库 id；无归属分组或分组未绑图库返回 None。
    班级分组按 className 派生匹配，寝室分组按成员表匹配（与 group_push 口径一致）。"""
    # 无 id 的替身对象（测试桩）没有归属可查，直接回落默认图库，
    # 不让一次 AttributeError 把整条推送打断
    if acc is None or getattr(acc, 'id', None) is None:
        return None
    q = PushGroup.query.filter_by(user_id=uid, type=kind)
    if kind == PushGroup.TYPE_CLASS:
        cls_name = ((acc.profile or {}).get('className') or '').strip()
        if not cls_name:
            return None
        q = q.filter(PushGroup.name == cls_name)
    else:
        q = q.join(PushGroupMember, PushGroupMember.group_id == PushGroup.id).filter(
            PushGroupMember.account_id == acc.id)
    # 同一账号理论上只属一个寝室分组，多属时取已绑图库的那个（id 升序保证结果稳定）
    for g in q.order_by(PushGroup.id.asc()).all():
        if g.image_group_id and ImageGroup.query.filter_by(
                id=g.image_group_id, user_id=uid).first() is not None:
            return g.image_group_id
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
    # 取图范围延迟到第 ⑤ 步解析：按分组取图要查库，无任务/超窗/围栏拦截等早退路径不必付这个成本
    group = None

    # 本次尝试提交的参数快照：跨分支累计，skip/fail/成功均带回，供落库回显「提交参数」。
    # 仅「无进行中任务」这种尚未触及任何提交信息的场景才为空（无参数可记）。
    attempt = {
        'task_id': None, 'task_name': '', 'task_start': '', 'task_end': '',
        'need_photo': False, 'lng': None, 'lat': None, 'address': '',
        'location_str': '', 'submit_remark': None, 'image_id': None,
        'image_group_id': None, 'strategy': strategy, 'warning': None,
    }
    claimed = None
    try:
        # ① 进行中任务（提交只能用 /list 的任务 id）
        ctx = adapter.find_active_task(session, schedule.task_type) or {}
        if not ctx.get('task'):
            # 无待签项有两种成因，文案必须分开：本人已签到的进行中任务同样列在 /list 里，
            # 若一并报「无进行中任务」，事后排查会误判成漏签（用户实测就踩过这个歧义）。
            done = ctx.get('finished_task') or {}
            if done:
                return 'skip', (f'本时段任务已完成签到（{done.get("taskName") or "进行中任务"}），'
                                f'无需重复签到'), {}
            return 'skip', '当前无进行中的签到任务', {}
        task = ctx['task']
        attempt['task_id'] = task.get('id')
        attempt['task_name'] = task.get('taskName') or ''
        attempt['task_start'] = task.get('startTime') or ''
        attempt['task_end'] = task.get('endTime') or ''
        attempt['need_photo'] = bool(task.get('needPhoto'))
        # 任务发起人为 B 平台任务字段（sendName · sendRole），透传给推送与详情，
        # 替换此前硬编码的「系统自动」占位。无 task（如跳过无进行中任务）时为空。
        attempt['initiator'] = task.get('initiator') or ''

        # ② 平台任务时间窗（know 'HH:mm:ss' / sign 'HH:mm'）
        ts = _parse_platform_time(task.get('startTime'))
        te = _parse_platform_time(task.get('endTime'))
        now_t = now_cst().time()
        if ts and te and (now_t < ts or now_t > te):
            return 'skip', f'当前时间不在平台任务时间窗（{task.get("startTime")}~{task.get("endTime")}）', attempt

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
        attempt['lng'] = lng
        attempt['lat'] = lat
        attempt['address'] = address
        attempt['location_str'] = location_str
        attempt['warning'] = warning

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
                                f'或在配置套中关闭围栏拦截）'), attempt

        # ⑤ 图片：一律以配置项 image.enabled 为准。
        #    未启用 → 不取图、不上传；只有平台任务确实要求图片时才判失败（宁可失败可感知，
        #    不静默交白卷）。启用 → 取一张附上（原子抢占，防同组并发取同一张），失败再回滚。
        #    ⚠️启用但取不到图时，只有 needPhoto 为真才判失败；任务并不要求图片的降级为无图提交，
        #    否则一个本来不需要图就能签到的任务，会仅仅因为图库空了而失败。
        need_photo = bool(task.get('needPhoto'))
        if not image_cfg.get('enabled'):
            if need_photo:
                return 'fail', '该任务需要上传签到图片，请在配置套中启用图库并确认有可用图片', attempt
        else:
            group = resolve_image_group(uid, resolved, acc)
            # 记下本次实际命中的图库：byGroup 下它与配置套默认图库不是一个，
            # 不记则推送只能读配置值，报出来的分组与实际取图不符
            attempt['image_group_id'] = group
            claimed = claim_image_for_submit(uid, group, strategy)
            if not claimed and need_photo:
                return 'fail', '图库暂无可用图片，请先上传或调整取图范围', attempt

        # ⑥ 提交（know 实证契约 / sign 镜像契约）
        image = ({'bytes': claimed['bytes'], 'filename': generate_image_filename()}
                 if claimed else None)
        submit_remark = remark if remark and remark != '—' else None
        attempt['submit_remark'] = submit_remark
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

        # 每次尝试都留一条 INFO：成功也必须有痕，否则事后只剩库记录，
        # 拿不到当时的请求上下文（坐标/备注/图片/平台原始响应）就无从判断是哪种失败。
        rsp = (result.detail or {}).get('rsp') or {}
        log.info('任务 %s 签到提交结果：status=%s｜任务=%s(%s)｜坐标=%s｜地址=%s｜备注=%s｜图片=%s｜原因=%s｜平台响应=%s',
                 schedule.id, result.status, task.get('id'), task.get('taskName') or '—',
                 location_str or '空', address or '空', submit_remark or '—',
                 image['filename'] if image else '无',
                 result.fail_reason or '—', rsp or '—')

        # 提交后重新同步图片 id（失败回滚后 claimed 已置空），连同前述坐标/备注/任务信息
        # 一并作为本次「提交参数」快照落库，供详情回显——成功与平台返回失败都带完整参数。
        attempt['image_id'] = claimed['id'] if claimed else None
        if result.status == 'success':
            return 'success', '', attempt
        return result.status, result.fail_reason or '平台返回失败', attempt
    except BPlatformError:
        if claimed:
            rollback_claim(claimed['id'], uid, strategy)
        raise
    except Exception:
        if claimed:
            rollback_claim(claimed['id'], uid, strategy)
        raise


def _push_outcome(schedule, acc, resolved, outcome, reason, rec, extra=None,
                  submitted_remark=''):
    """推送后置动作：按配置套 push 分发执行结果。与「执行结果落库」解耦——
    内部异常仅记日志，绝不再写第二条 SignRecord，避免一次执行产生重复日志。
    正常路径与异常失败路径（校验失败/平台异常/未预期异常）共用，保证
    「凡落库必有推送机会」，notify 开关在 dispatch_push 内统一裁决。"""
    try:
        if outcome is None:
            return
        # 成功且图片策略可回看时，推送带签到凭证图 URL（delete 已物理删除故无 URL）
        ex = extra or {}
        image_url = ''
        if outcome == 'success' and ex.get('image_id') and ex.get('strategy') in ('recycle', 'trash'):
            base = os.getenv('PUSH_IMAGE_BASE', '').strip().rstrip('/')
            if base:
                image_url = f"{base}/api/pools/images/{ex['image_id']}/file"
        dispatch_push(resolved, schedule, acc, outcome, reason,
                      image_url=image_url, submitted_remark=submitted_remark, extra=ex,
                      sign_record_id=rec.id if rec else None)
    except Exception as e:
        log.warning('任务 %s 后置动作失败（已落库的执行记录不受影响）：%s', schedule.id, e)


def _execute(schedule, allow_retry=True, course_name=None):
    acc = db.session.get(BAccount, schedule.account_id)
    if acc is None or not acc.enabled:
        log.info('任务 %s 跳过：账号不存在或已禁用', schedule.id)
        return  # 禁用态不写记录，避免刷屏

    outcome = None
    reason = ''
    extra = {}
    resolved = None
    try:
        # 凭据解密单独前置校验：密钥轮换/数据损坏时 Fernet 抛 InvalidToken（str 为空，
        # 落进通用 Exception 分支只会得到一条「执行异常：」的无因失败）。此处就地给出
        # 可操作文案并置 verify_status='fail'，下次执行自动重校验拿新 token 自愈。
        try:
            acc.get_password()
            acc.get_token()
        except InvalidToken:
            log.warning('任务 %s 凭据解密失败（密钥不匹配或数据损坏），账号转入待重校验', schedule.id)
            acc.verify_status = 'fail'
            db.session.commit()
            rec = _commit_result(schedule, acc, 'fail',
                                 '账号凭据解密失败（服务端密钥可能已轮换），请重新校验该账号',
                                 resolved=resolved, course_name=course_name)
            _push_outcome(schedule, acc, resolved, 'fail', rec.fail_reason, rec)
            return

        if acc.verify_status != 'ok':
            try:
                res = get_adapter().verify_and_fetch(acc.account, acc.get_password())
            except BPlatformError as e:
                log.warning('任务 %s 账号校验失败：%s', schedule.id, e.message)
                rec = _commit_result(schedule, acc, 'fail', f'账号校验失败：{e.message}',
                                     resolved=resolved, course_name=course_name)
                _push_outcome(schedule, acc, resolved, 'fail', f'账号校验失败：{e.message}', rec)
                return
            acc.set_token(res.token)
            acc.set_profile(res.profile)
            acc.bp_uid = res.bp_uid
            acc.verify_status = 'ok'
            acc.verified_at = now_cst()
            db.session.flush()

        resolved = _resolve(schedule)
        if resolved is None:
            _commit_result(schedule, acc, 'skip', '配置缺失（配置套未绑定或已删除）',
                           resolved=resolved, course_name=course_name)
            return
        # 本次实际提交的单条备注：多条随机选一、单条即用该条、无则占位；
        # 模板占位符（{username}=B 平台账号姓名）在此一次性渲染，提交与推送共用同一结果，
        # 保证「提交什么就推送什么」。
        submitted_remark = _render_remark(_select_remark(resolved), acc)
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
        # 统一在此回写：成功/失败/跳过都落 SignRecord 并回写任务与账号状态；
        # 把本次提交参数快照一并传入，详情回显「提交参数」
        rec = _commit_result(schedule, acc, outcome, reason, resolved=resolved, extra=extra,
                             course_name=course_name)
    except BPlatformError as e:
        # acc 仍在作用域内，账号聚合与任务状态一同更新，杜绝两者不一致
        if e.kind == 'credential':
            acc.verify_status = 'fail'  # 凭证失效，下次执行触发 reverify
        log.warning('任务 %s 执行异常（B 平台）：%s', schedule.id, e.message)
        fail_reason = f'B 平台错误：{e.message}'
        rec = _commit_result(schedule, acc, 'fail', fail_reason, resolved=resolved,
                             course_name=course_name)
        # 异常失败同样推送（notify.fail 开关裁决），不再静默——此前网络类失败
        # （如验证码超时）只落库不出通知，用户感知不到当天签到已失败
        _push_outcome(schedule, acc, resolved, 'fail', fail_reason, rec)
        # 网络类失败：安排窗口内补跑（请求层已有 3 次指数退避，此处覆盖更长的平台抖动；
        # credential 已在上方就地重登重试过、业务失败重跑无意义，均不补跑）
        if e.kind == 'network' and allow_retry:
            _schedule_retry(schedule)
        return
    except Exception as e:
        log.exception('任务 %s 执行异常', schedule.id)
        fail_reason = f'执行异常：{e}'
        rec = _commit_result(schedule, acc, 'fail', fail_reason, resolved=resolved,
                             course_name=course_name)
        _push_outcome(schedule, acc, resolved, 'fail', fail_reason, rec)
        return

    # 后置动作（推送）与「执行结果落库」解耦：成功/失败/跳过统一走 _push_outcome，
    # 其内部自捕获异常，不再产生「成功 + 失败」两条重复日志
    _push_outcome(schedule, acc, resolved, outcome, reason, rec,
                  extra=extra, submitted_remark=submitted_remark)


# ===== 网络失败补跑（窗口内重试）=====
# 平台瞬时抖动（断网/超时/5xx）常在几分钟内自愈，而 cron 当天不会再触发。
# 请求层已有 3 次指数退避（覆盖秒级抖动），此处覆盖分钟级抖动：失败后安排一次
# 一次性延迟 job 重走完整执行链路。环境变量可调：SCHEDULER_RETRY_DELAY_MIN 延迟分钟数（默认 10）。
RETRY_JOB_PREFIX = '_retry_'
_RETRY_DELAY_MINUTES = max(1, int(os.getenv('SCHEDULER_RETRY_DELAY_MIN', '10') or 10))


def runtime_settings():
    """调度器的运行节奏参数：管理端展示「它按什么节奏工作」时读取。

    这些值分别来自模块常量、环境变量与系统设置，展示层各自复制一份必然漂移，只在此处取。
    """
    return {
        'reconcileSeconds': _RECONCILE_SECONDS,
        'reconcileSameDayOnly': _RECONCILE_SAME_DAY_ONLY,
        'pruneIntervalHours': _PRUNE_INTERVAL_HOURS,
        'retryDelayMinutes': _RETRY_DELAY_MINUTES,
        'logRetentionDays': int(get_setting('sign_log_retention_days') or 180),
        'opLogRetentionDays': int(get_setting('op_log_retention_days') or 365),
    }


def _schedule_retry(schedule):
    """网络类失败后的窗口内补跑：安排一次延迟 job（默认 10 分钟后）重走完整执行链路。
    replace_existing 防止连续失败堆叠多个重试；补跑失败不再级联安排（args 传 allow_retry=False）。
    注意：提交型超时存在「平台已受理但响应超时」的固有二义性，补跑最坏得到一条
    平台「已签到」的业务失败记录，不会产生两条成功日志。补跑内部自会校验任务
    启用状态与平台时间窗，窗口已关则如实落 skip。"""
    sched = get_scheduler()
    run_at = now_cst() + timedelta(minutes=_RETRY_DELAY_MINUTES)
    try:
        sched.add_job(
            run_schedule,
            trigger=DateTrigger(run_date=run_at),
            args=[schedule.id, False],
            id=f'{RETRY_JOB_PREFIX}{schedule.id}',
            replace_existing=True,
        )
        log.info('任务 %s 网络失败，已安排 %d 分钟后补跑', schedule.id, _RETRY_DELAY_MINUTES)
    except Exception:
        log.exception('任务 %s 补跑安排失败（不影响已落库的失败记录）', schedule.id)


def _render_remark(text, acc):
    """渲染备注模板占位符为实际值。当前仅支持 {username}（B 平台账号姓名）。
    姓名为空时回落到登录账号标识；两者皆空则原样保留（含字面 {username}，由后端兜底不泄露）。"""
    if not text or text == '—':
        return text
    profile = getattr(acc, 'profile', None)
    if not isinstance(profile, dict):
        profile = {}
    name = (profile.get('name') or '').strip()
    if not name:
        name = getattr(acc, 'account', '') or ''
    if not name:
        return text
    return text.replace('{username}', name)


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


def _commit_result(schedule, acc, status, fail_reason='', resolved=None, extra=None,
                   course_name=None):
    """写签到记录 + 回写任务状态 + 刷新账号最近签到聚合；统一提交。
    resolved 非 None 时把执行时配置快照写入记录，供详情回显历史切片；
    extra 非 None（调用方传回的提交参数快照）时一并写入 submit_params，供详情回显「提交参数」；
    course_name 非 None（课表窗口轮询命中）时写入课程溯源。
    函数本身即「执行出口」：无论哪种结局都在此落库并写一条 INFO 日志。"""
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
        course_name=course_name or None,
    )
    # 任务发起人（B 平台真实姓名）与是否需要图片：取自执行时 extra（无 extra 如早期跳过则为空）
    ex = extra or {}
    rec.task_initiator = ex.get('initiator') or ''
    rec.need_photo = ex.get('need_photo')
    # 执行时配置快照：忠实还原该条日志当时实际使用的配置（resolved 为 None 表示
    # 执行前配置缺失/校验失败，无快照可抓，落 NULL，详情端显示「无配置快照」）
    if resolved is not None:
        rec.set_config_snapshot(build_config_view(schedule, resolved, schedule.user_id, acc=acc))
    # 提交参数快照：仅当确实构造了尝试提交参数（非空 dict）才落库；
    # 纯早期跳过（如「无进行中任务」）传回 {} 表示无参数，落 NULL 保持详情简洁。
    if extra:
        rec.set_submit_params(extra)
    db.session.add(rec)
    schedule.last_run_at = now_cst()
    schedule.last_status = status
    schedule.run_count = (schedule.run_count or 0) + 1
    schedule.next_run_at = compute_next_run(schedule)
    if acc is not None:
        acc.last_sign_at = now_cst()
        acc.last_sign_status = status
    db.session.commit()

    # 群合并推送注册：寝室签到落库即登记本成员所属分组的合并触发（个人 1-to-1 仍由 dispatch_push 并发）。
    # 异常隔离，绝不波及主链路落库结果。
    if schedule.task_type == 'dorm':
        try:
            from app.services.group_digest import register_digest
            register_digest(acc, schedule)
        except Exception:
            log.exception('群合并推送注册失败（不影响执行记录） schedule=%s', schedule.id)

    # 统一出口日志：_commit_result 是全部执行路径（成功/失败/跳过，含提交前的各早退分支、
    # 甚至外层兜底）唯一的落库点，只有在这里留一条 INFO 才能保证「任何一种结局都有痕」。
    # 此前仅走到提交的路径打日志，skip 类原因（无进行中任务/已完成签到/配置缺失/图库无图）
    # 在库外完全查不到，事后只能翻 sign_records 反推。
    who = '—'
    if acc is not None:
        name = (acc.profile or {}).get('name')
        who = f'{acc.account}({name})' if name else str(acc.account)
    log.info('任务 %s 执行落库：账号=%s｜类型=%s｜状态=%s｜平台任务=%s｜原因=%s',
             schedule.id, who, schedule.task_type, status,
             (extra or {}).get('task_name') or '—', fail_reason or '—')
    return rec


# 推送发送重试：瞬时故障（网络抖动/超时/pushplus 5xx）自愈，失败原因仍完整落库。
# 环境变量可调：PUSH_SEND_ATTEMPTS 总尝试次数（默认 3），PUSH_RETRY_BACKOFF 退避基数秒（默认 2，线性递增）。
PUSH_SEND_ATTEMPTS = max(1, int(os.getenv('PUSH_SEND_ATTEMPTS', '3') or 3))
PUSH_RETRY_BACKOFF = max(0.0, float(os.getenv('PUSH_RETRY_BACKOFF', '2') or 2))


def _send_one(ch, key, ctx, template):
    """单通道发送（供线程池扇出）：失败按总尝试次数自动重试（线性退避），重试发生在
    worker 线程内不阻塞其它通道。返回 (ch, ok, err, attempts)，单通道内部异常隔离为
    失败，不波及其它通道。"""
    attempts = 0
    err = ''
    ok = False
    for attempt in range(1, PUSH_SEND_ATTEMPTS + 1):
        attempts = attempt
        try:
            ok, err = send_channel(ch, key, ctx, template)
        except Exception as e:
            ok, err = False, f'内部异常：{e}'
        if ok:
            break
        if attempt < PUSH_SEND_ATTEMPTS and PUSH_RETRY_BACKOFF > 0:
            time.sleep(PUSH_RETRY_BACKOFF * attempt)
    if not ok and attempts > 1:
        err = f'{err}（已重试，共尝试 {attempts} 次）'
    return ch, ok, err, attempts


def dispatch_push(resolved, schedule, acc, status='success', reason='', image_url='', submitted_remark='',
                  extra=None, sign_record_id=None):
    """按配置套 push 分发执行结果（ServerChan / PushPlus / Email）。
    读取配置套的 push 结构：channels 决定通道、useOwnCredential 决定密钥来源
    （直接填写用 push.cred 内联字段；回填凭证用 push.credIds 引用资源池并解密）；
    notify 开关控制各状态是否推送。无可用密钥则不发，发送失败仅记录，不影响主链路。
    标题含签到账号姓名 + 状态；内容按 push.template(html/txt/markdown) 渲染；
    extra 携带 B 平台任务信息（任务名/时间段/是否需要图片）供卡片「签到任务」分区展示；
    长度受 pushplus 限制守护。sign_record_id 关联本次执行记录，逐通道结果落 push_logs
    （成败/原因/尝试次数/时刻），任务日志详情直接可见——失败不再只进控制台日志。"""
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

    creds, issues = _resolve_push_creds(push, schedule.user_id, acc)
    template = push.get('template') or 'html'
    # 跳过原因落 push_logs（ok=false, attempts=0）：此前只进服务端日志，任务日志详情里
    # 表现为「没有推送记录」，用户无法排查「配了推送但没收到」——现与发送结果同表可见
    if issues:
        try:
            for it in issues:
                db.session.add(PushLog(
                    user_id=schedule.user_id,
                    account_id=getattr(acc, 'id', None),
                    schedule_id=getattr(schedule, 'id', None),
                    sign_record_id=sign_record_id,
                    channel=it['channel'],
                    ok=False,
                    error=('已跳过：' + it['reason'])[:500],
                    attempts=0,
                    template=template,
                ))
            db.session.commit()
        except Exception:
            db.session.rollback()
            log.exception('任务 %s 推送跳过原因落库失败', schedule.id)
        for it in issues:
            log.warning('任务 %s 推送通道被跳过：%s（%s）', schedule.id, it['channel'], it['reason'])
    if not creds:
        log.warning('任务 %s 未解析到任何可用推送凭证（通道=%s），跳过推送',
                    schedule.id, channels)
        return

    # build_ctx 含 DB 读取（位置池/图库/配置套名），须在调用线程（已持 app context）完成；
    # 仅把无状态、纯网络 I/O 的 send_channel 扇出到线程池并发执行：
    # 墙钟时间由「各通道之和」降为「最慢单通道」，单通道异常仍隔离互不干扰。
    extra = extra or {}
    start, end = extra.get('task_start') or '', extra.get('task_end') or ''
    # 卡片里的「图片分组」必须是本次实际取图的图库：byGroup 下分组绑定的图库与配置套
    # 默认图库不是一个，直接读配置值会把分组报错（实测签到用 827、推送显示 829）。
    # 认领时已解析过一次并记在 extra；早退路径（无进行中任务/已完成签到等尚未取图）
    # 没有那次记录，故在此按同一函数补解析，口径与认领完全一致。
    image_group_id = extra.get('image_group_id')
    if image_group_id is None:
        image_group_id = resolve_image_group(schedule.user_id, resolved, acc)
    ctx = build_ctx(acc, schedule, resolved, status, reason=reason,
                    image_url=image_url, remark=submitted_remark or None,
                    task_name=extra.get('task_name') or '',
                    task_window=f'{start}~{end}' if (start or end) else '',
                    need_photo=extra.get('need_photo'),
                    initiator=extra.get('initiator') or '',
                    image_group_id=image_group_id)

    if len(creds) == 1:
        ch, key = next(iter(creds.items()))
        results = [_send_one(ch, key, ctx, template)]
    else:
        results = []
        with FuturesThreadPool(max_workers=min(len(creds), 4)) as ex:
            futures = {ex.submit(_send_one, ch, key, ctx, template): ch
                       for ch, key in creds.items()}
            for fut in as_completed(futures):
                results.append(fut.result())

    # 结果落库：每通道一行 push_logs（含最终成败、原因原文、尝试次数、发送时刻）。
    # 落库失败只回滚本批插入，不影响已发出的推送与主链路。
    for ch, ok, err, attempts in results:
        if ok:
            log.info('任务 %s %s 推送成功', schedule.id, ch)
        else:
            log.warning('任务 %s %s 推送失败：%s', schedule.id, ch, err)
    summary = '；'.join(f'{ch}={"成功" if ok else f"失败（{err}）"}' for ch, ok, err, _a in results)
    log.info('任务 %s 推送汇总：%s', schedule.id, summary)
    try:
        for ch, ok, err, attempts in results:
            db.session.add(PushLog(
                user_id=schedule.user_id,
                account_id=getattr(acc, 'id', None),
                schedule_id=getattr(schedule, 'id', None),
                sign_record_id=sign_record_id,
                channel=ch,
                ok=ok,
                error=(err or '')[:500],
                attempts=attempts,
                template=template,
            ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception('任务 %s 推送结果落库失败', schedule.id)


def _acc_cred_entry(raw):
    """账号绑定项归一化 → (cred_id|None, to)。
    兼容三种形态：纯凭证 id / {credId, to} / 仅 {to}（收件人独立于凭证覆盖）。"""
    to = str(raw.get('to') or '').strip() if isinstance(raw, dict) else ''
    return binding_cred_id(raw), to


def _resolve_push_creds(push, user_id, account=None):
    """从 push 结构解析出各通道可用密钥。
    useAccountCredential=true（各账号自带凭证）→ 优先取该账号绑定的凭证，该账号未绑定的
      通道回落配置套 push.credIds（若有），仍无则记 issue；
    useOwnCredential=true（回填我的凭证）→ 按 push.credIds 解密资源池凭证（仅限本人）；
    useOwnCredential=false（直接填写）→ 读 push.cred 内联字段。
    账号级收件人（b_accounts.push_creds.email.to）与凭证来源正交：邮件发给谁是这个账号的
    属性，故三种来源下都覆盖凭证里的默认收件人。
    返回 (creds, issues)：creds={channel: key_or_fields} 仅含已选且密钥非空的通道；
    issues=[{channel, reason}] 逐通道跳过原因——凭证解析失败必须显式暴露（此前静默
    continue，通道被跳过用户完全无感知），调用方负责把 issues 落 push_logs 并记日志。"""
    channels = push.get('channels') or []
    use_own = push.get('useOwnCredential', False)
    use_account = bool(push.get('useAccountCredential'))
    out = {}
    issues = []

    acc_creds = (getattr(account, 'push_creds', None) or {}) if account is not None else {}
    acc_email_to = _acc_cred_entry(acc_creds.get('email'))[1]

    def _cred_fields(cid):
        c = db.session.get(PoolCredential, cid)
        if c is None or not c.enabled or c.user_id != user_id:
            return None, '凭证不存在或已停用'
        try:
            return json.loads(decrypt(c.secret_enc)), None
        except Exception:
            return None, '凭证解密失败（主密钥不匹配或数据损坏）'

    def _take(ch, cid, to=''):
        """按凭证 id 解析并落 out；调用前须确认 cid 非空。to 仅对 email 生效（账号级收件人覆盖）。"""
        fields, err = _cred_fields(cid)
        if fields is None:
            issues.append({'channel': ch, 'reason': err})
            return
        key_field = {'serverchan': 'serverchanKey', 'pushplus': 'pushplusToken'}.get(ch)
        if key_field and fields.get(key_field):
            out[ch] = fields[key_field]
            return
        if ch == 'email' and fields.get('emailSmtp') and fields.get('emailFrom'):
            tos = to or fields.get('emailTo') or ''
            if tos:
                out[ch] = {k: fields.get(k) for k in ('emailSmtp', 'emailFrom', 'emailPass')}
                out[ch]['emailTo'] = tos
                return
        issues.append({'channel': ch, 'reason': '凭证缺少必要字段'})

    if use_account:
        # 账号未绑定的通道回落配置套 credIds（便于「多数账号共用一份、个别账号自带」）
        set_ids = push.get('credIds') or {}
        for ch in channels:
            acc_cid, acc_to = _acc_cred_entry(acc_creds.get(ch))
            cid = acc_cid or set_ids.get(ch)
            if not cid:
                issues.append({'channel': ch, 'reason': '该账号未绑定此通道的推送凭证'})
                continue
            _take(ch, cid, acc_to if ch == 'email' else '')
    elif use_own:
        cred_ids = push.get('credIds') or {}
        for ch in channels:
            cid = cred_ids.get(ch)
            if not cid:
                issues.append({'channel': ch, 'reason': '未绑定凭证'})
                continue
            _take(ch, cid, acc_email_to if ch == 'email' else '')
    else:
        cred = push.get('cred') or {}
        if 'serverchan' in channels and cred.get('serverchanKey'):
            out['serverchan'] = cred['serverchanKey']
        if 'pushplus' in channels and cred.get('pushplusToken'):
            out['pushplus'] = cred['pushplusToken']
        if 'email' in channels:
            to = acc_email_to or cred.get('emailTo')
            if cred.get('emailSmtp') and cred.get('emailFrom') and to:
                out['email'] = {k: cred.get(k) for k in ('emailSmtp', 'emailFrom', 'emailPass')}
                out['email']['emailTo'] = to
            else:
                issues.append({'channel': 'email', 'reason': '内联凭证缺少 SMTP 地址/发件人/收件人字段'})
    return out, issues
