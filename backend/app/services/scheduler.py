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
from app.models.pools import PoolCredential
from app.models.system_config import get_setting
from app.models.user import now_cst
from app.services.b_platform import get_adapter
from app.services.b_platform.base import BPlatformError
from app.services.crypto import decrypt
from app.services.image_store import consume_next_image
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


def _execute(schedule):
    acc = db.session.get(BAccount, schedule.account_id)
    if acc is None or not acc.enabled:
        log.info('任务 %s 跳过：账号不存在或已禁用', schedule.id)
        return  # 禁用态不写记录，避免刷屏

    outcome = None
    reason = ''
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
        # 同时交给 checkin（真实提交 B 平台用）与推送展示，保证「提交什么就推送什么」。
        submitted_remark = _select_remark(resolved)
        session = {
            'token': acc.get_token(),
            'account': acc.account,
            'profile': acc.profile,
        }
        task = {'taskType': schedule.task_type, **resolved, 'submittedRemark': submitted_remark}
        result = get_adapter().checkin(session, task)
        if result is None or not result.ok:
            reason = result.fail_reason if result else '无返回'
            outcome = 'fail'
        elif result.status == 'skip':
            reason = result.fail_reason or '平台返回跳过'
            outcome = 'skip'
        else:
            outcome = 'success'
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

    # 后置动作（推送 / 消费图库图片）与「执行结果落库」解耦：失败仅记日志，
    # 绝不再写第二条 SignRecord，避免一次执行产生「成功 + 失败」两条重复日志
    try:
        if outcome is not None:
            # 成功时先消费图片拿回 URL，供推送展示签到凭证图
            image_url = ''
            if outcome == 'success':
                image_url = _consume_configured_image(schedule, resolved) or ''
            dispatch_push(resolved, schedule, acc, outcome, reason,
                          image_url=image_url, submitted_remark=submitted_remark)
    except Exception as e:
        log.warning('任务 %s 后置动作失败（已落库的执行记录不受影响）：%s', schedule.id, e)


def _consume_configured_image(schedule, resolved):
    """按配置套 image 配置消费一张图库图片。
    enabled 未开启直接跳过；groupId ''=全部图库，否则限定分组；strategy：recycle 轮回
    （用尽整批回池）/ trash 回收站 / delete 删除，未知兜底 trash。无图仅记日志，不影响主链路。
    返回可被推送展示的图片 URL（delete 策略已物理删除故返回空），无图返回空串。"""
    cfg = (resolved or {}).get('image')
    if not isinstance(cfg, dict) or not cfg.get('enabled'):
        return ''
    raw_group = cfg.get('groupId')
    try:
        group_id = int(raw_group) if raw_group not in (None, '', 0) else None
    except (TypeError, ValueError):
        group_id = None
    strategy = cfg.get('strategy') if cfg.get('strategy') in ('recycle', 'trash', 'delete') else 'trash'
    consumed = consume_next_image(schedule.user_id, group_id, strategy)
    if consumed is None:
        log.warning('任务 %s 签到成功但取图范围内无可用图片（范围=%s，策略=%s）',
                    schedule.id, f'分组{group_id}' if group_id else '全部图库', strategy)
        return ''
    log.info('任务 %s 消费图片 #%s（策略=%s）', schedule.id, consumed, strategy)
    # delete 策略已物理删除，仅 recycle/trash 仍可被外部预览（需配置 PUSH_IMAGE_BASE 公网地址）
    if strategy == 'delete':
        return ''
    base = os.getenv('PUSH_IMAGE_BASE', '').strip().rstrip('/')
    if not base:
        return ''
    return f'{base}/api/pools/images/{consumed}/file'


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

    creds = _resolve_push_creds(push, schedule.user_id)
    if not creds:
        log.warning('任务 %s 未解析到任何可用推送凭证（通道=%s，请检查凭证来源/绑定），跳过推送',
                    schedule.id, channels)
        return

    template = push.get('template') or 'html'
    ctx = build_ctx(acc, schedule, resolved, status, reason=reason,
                    image_url=image_url, remark=submitted_remark or None)
    for ch, key in creds.items():
        ok, err = send_channel(ch, key, ctx, template)
        if ok:
            log.info('任务 %s %s 推送成功', schedule.id, ch)
        else:
            log.warning('%s 推送失败：%s', ch, err)


def _resolve_push_creds(push, user_id):
    """从 push 结构解析出各通道可用密钥。
    useOwnCredential=true（回填我的凭证）→ 按 push.credIds 解密资源池凭证（仅限本人）；
    useOwnCredential=false（直接填写）→ 读 push.cred 内联字段。
    返回 {channel: key_or_fields}，仅含已选且密钥非空的通道。"""
    channels = push.get('channels') or []
    use_own = push.get('useOwnCredential', False)
    out = {}
    if use_own:
        cred_ids = push.get('credIds') or {}
        for ch in channels:
            cid = cred_ids.get(ch)
            if not cid:
                continue
            c = db.session.get(PoolCredential, cid)
            if c is None or not c.enabled or c.user_id != user_id:
                continue
            try:
                fields = json.loads(decrypt(c.secret_enc))
            except Exception:
                continue
            if ch == 'serverchan' and fields.get('serverchanKey'):
                out['serverchan'] = fields['serverchanKey']
            elif ch == 'pushplus' and fields.get('pushplusToken'):
                out['pushplus'] = fields['pushplusToken']
            elif ch == 'email':
                if fields.get('emailSmtp') and fields.get('emailFrom') and fields.get('emailTo'):
                    out['email'] = {k: fields.get(k) for k in
                                    ('emailSmtp', 'emailFrom', 'emailPass', 'emailTo')}
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
    return out
