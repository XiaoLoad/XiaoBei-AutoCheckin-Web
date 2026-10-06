# 群合并推送聚合服务（设计文档 §6 v3：任务时间窗触发，无需 EOD 兜底）
#
# 触发：成员寝室签到落库后由 scheduler._commit_result 调 register_digest →
#   取该成员所属分组（dorm 显式成员 / class 按 className 派生），仅已绑 qq_code 的组参与；
#   收集组内全体成员当日 dorm 任务窗（weekday 命中且 enabled），flush_at = 最晚窗结束 + 缓冲；
#   当日无任何成员有寝室任务 → 跳过（off-day 天然不推送）。
# 发送：flush_at 到点（延迟 job + reconcile 双保险）拉成员当日 dorm 记录渲染合并消息 →
#   pushplus 开放接口发到 QQ 群；发送前先 DELETE pending 行原子认领（谁删到谁发），
#   双保险同刻触发也只发一次；失败按 attempts 线性退避重排队，超限记 fail 终态。
# 个人 1-to-1 推送由 dispatch_push 照常并发，本服务仅负责群组汇总。
import json
import logging
from datetime import datetime, timedelta

from app.extensions import db
from app.models import (BAccount, PushGroup, PushGroupDigestLog,
                        PushGroupMember, PushGroupDigestPending)
from app.models.schedule import Schedule
from app.models.sign_record import SignRecord
from app.models.user import now_cst
from app.services.push_render import send_qq
from app.services.crypto import decrypt
from app.utils.schedule_utils import extract_jitter_minutes, extract_schedule_time

log = logging.getLogger('push')

# 最晚任务窗结束后的缓冲（分钟），覆盖时钟/执行延迟；flush 时刻过后必已收齐
BUFFER_MINUTES = 3
# 合并推送凭证：用户级 pushplus-open（消息 Token），全部分组共用一份
DIGEST_CREDENTIAL_CHANNEL = 'pushplus-open'
# 发送失败重排队次数上限：重试间隔随次数线性退避（1/2/3/4 分钟），超限记 fail 终态
MAX_FLUSH_ATTEMPTS = 5


# ───────────────────────── 分组解析 ─────────────────────────

def _groups_for_account(acc):
    """取账号所属的全部已参与推送的分组（dorm 显式 + class 按 className 派生）。"""
    groups = []
    dorm = (PushGroup.query
            .join(PushGroupMember, PushGroupMember.group_id == PushGroup.id)
            .filter(PushGroupMember.account_id == acc.id,
                    PushGroup.type == PushGroup.TYPE_DORM)
            .all())
    groups.extend(dorm)
    cn = (acc.profile or {}).get('className') or ''
    if cn:
        class_groups = PushGroup.query.filter_by(
            user_id=acc.user_id, type=PushGroup.TYPE_CLASS, name=cn).all()
        groups.extend(class_groups)
    return groups


def group_members(g):
    """返回分组内的账号 id 列表（class 按 className 实时派生；dorm 取成员表）。"""
    if g.type == PushGroup.TYPE_CLASS:
        accs = BAccount.query.filter_by(user_id=g.user_id, enabled=True).all()
        return [a.id for a in accs if (a.profile or {}).get('className') == g.name]
    return [r.account_id for r in PushGroupMember.query.filter_by(group_id=g.id).all()]


# ───────────────────────── 触发注册 ─────────────────────────

def _member_window_end_max(member_ids, date):
    """组内成员当日 dorm 任务的最晚窗结束时刻（排程时刻 + 随机延迟上限）；无则 None。"""
    if not member_ids:
        return None
    weekday = date.isoweekday()  # 1=周一..7=周日，与 schedule.weekdays(1..7) 同口径
    scheds = (Schedule.query
              .filter(Schedule.account_id.in_(member_ids),
                      Schedule.task_type == 'dorm',
                      Schedule.enabled.is_(True))
              .all())
    max_end = None
    for s in scheds:
        hour, minute, weekdays = extract_schedule_time(s)
        if weekday not in (weekdays or []):
            continue
        if hour is None or minute is None:
            continue
        jitter = extract_jitter_minutes(s) or 0
        end = datetime(date.year, date.month, date.day, int(hour), int(minute)) \
            + timedelta(minutes=jitter)
        if max_end is None or end > max_end:
            max_end = end
    return max_end


def _upsert_pending(group_id, date, flush_at):
    """upsert 待触发记录：始终取最晚 flush_at（单调向后，不往前挪）。"""
    row = PushGroupDigestPending.query.filter_by(group_id=group_id, date=date).first()
    if row is None:
        db.session.add(PushGroupDigestPending(group_id=group_id, date=date, flush_at=flush_at))
    elif flush_at > row.flush_at:
        row.flush_at = flush_at
    db.session.commit()


def _schedule_flush(group_id, date, flush_at):
    """安排一次性延迟 job 在 flush_at 触发 flush；reconcile 作二次兜底（防 job 丢失，非补发）。"""
    from app.services.scheduler import get_scheduler
    try:
        sched = get_scheduler()
        sched.add_job(_flush_job, trigger='date', run_date=flush_at,
                      args=[group_id, date.isoformat()],
                      id=f'_digest_{group_id}_{date.isoformat()}',
                      replace_existing=True)
    except Exception:
        log.exception('群合并推送延迟 job 安排失败 group=%s date=%s', group_id, date)


def register_digest(acc, schedule, date=None):
    """寝室签到落库后调用：为该成员所属已绑定的分组注册/刷新合并推送触发。
    当日组内无成员有寝室任务 → 跳过（不推送）。异常隔离，绝不波及主链路。"""
    if schedule is None or schedule.task_type != 'dorm':
        return
    date = date or now_cst().date()
    groups = []
    try:
        groups = _groups_for_account(acc)
        for g in groups:
            if not g.bound:
                continue
            members = group_members(g)
            if not members:
                continue
            max_end = _member_window_end_max(members, date)
            if max_end is None:
                continue  # 当日该组无寝室任务，off-day 不推送
            flush_at = max_end + timedelta(minutes=BUFFER_MINUTES)
            now = now_cst()
            if flush_at <= now:
                flush_at = now + timedelta(minutes=1)  # 已过点则尽快触发
            _upsert_pending(g.id, date, flush_at)
            _schedule_flush(g.id, date, flush_at)
    except Exception:
        log.exception('群合并推送注册失败（不影响执行记录） acc=%s group_count=%d',
                     getattr(acc, 'id', None), len(groups))


# ───────────────────────── 发送与审计 ─────────────────────────

def _resolve_open_token(user_id):
    """取用户启用的 pushplus-open 凭证 Token；无则 (None, 原因)。"""
    from app.models import PoolCredential
    c = (PoolCredential.query
         .filter_by(user_id=user_id, channel=DIGEST_CREDENTIAL_CHANNEL, enabled=True)
         .order_by(PoolCredential.id.asc()).first())
    if c is None:
        return None, '未配置 pushplus-open 凭证'
    try:
        fields = json.loads(decrypt(c.secret_enc))
    except Exception:
        return None, '凭证密钥解析失败'
    token = fields.get('token')
    if not token:
        return None, '凭证缺少 Token'
    return token, None


def _member_records(member_ids, date):
    """取每个成员当日 dorm 记录（success 优先，否则最新一条）；返回 [(account, rec|None)]。
    一次 IN 查询取回全员当日记录后按账号分组（逐成员查询在 30~50 人的分组里是 N 次往返）。"""
    accs = {a.id: a for a in BAccount.query.filter(BAccount.id.in_(member_ids)).all()}
    recs = (SignRecord.query
            .filter(SignRecord.account_id.in_(member_ids),
                    SignRecord.sign_date == date,
                    SignRecord.task_type == 'dorm')
            .order_by(SignRecord.id.asc()).all())
    by_acc = {}
    for r in recs:  # id 升序遍历，后写覆盖前写 → 每账号停在最新一条
        by_acc[r.account_id] = r
    picked = {}
    for r in recs:  # success 优先：同账号有多条时以最新 success 为准（无 success 保持最新一条）
        if r.status == 'success':
            picked[r.account_id] = r
    out = []
    for aid in member_ids:
        rec = picked.get(aid) or by_acc.get(aid)
        out.append((accs.get(aid), rec))
    return out


def _render_digest(g, date, member_rows):
    """渲染合并消息标题与 markdown 正文（学号/班级/姓名/状态/任务/发起人/是否需要图片/时间）。

    失败与跳过另在表格后附「说明」列出原因：只给「跳过」两个字，收件人无法判断是
    「已完成签到无需重复」还是「漏签」，与个人推送的失败/跳过原因口径对齐
    （同一字段 sign_records.fail_reason）。无原因时不出现该段。"""
    label = '班级' if g.type == PushGroup.TYPE_CLASS else '寝室'
    title = f'小北自动打卡 · {g.name} {label}签到汇总'
    lines = [
        f'# 小北自动打卡 · {label}签到汇总',
        '',
        f'**分组**：{g.name}（{label}）　**日期**：{date.isoformat()}',
        '',
        '| 学号 | 班级 | 姓名 | 状态 | 任务 | 发起人 | 是否需要图片 | 签到时间 |',
        '| --- | --- | --- | --- | --- | --- | --- | --- |',
    ]
    done = 0
    notes = []
    for acc, rec in member_rows:
        profile = acc.profile if acc else {}
        name = profile.get('name') or (acc.account if acc else '未知')
        student_no = profile.get('studentNo') or '—'
        className = profile.get('className') or '—'
        if rec is None:
            status, sign_time, task, initiator, need_photo = '未签到', '—', '—', '—', '—'
        else:
            status = {'success': '已签到', 'fail': '失败', 'skip': '跳过'}.get(rec.status, rec.status)
            sign_time = rec.signed_at.strftime('%H:%M') if rec.signed_at else '—'
            task = rec.task_name or '—'
            initiator = rec.task_initiator or '—'
            if rec.need_photo is None:
                need_photo = '—'
            else:
                need_photo = '需要' if rec.need_photo else '不需要'
            if rec.status == 'success':
                done += 1
            reason = (rec.fail_reason or '').strip()
            if rec.status in ('fail', 'skip') and reason:
                notes.append(f'- {name}（{status}）：{reason}')
        lines.append(f'| {student_no} | {className} | {name} | {status} | {task} | {initiator} | {need_photo} | {sign_time} |')
    total = len(member_rows)
    lines += ['', f'> 共 {total} 人，已签 **{done}** 人']
    if notes:
        lines += ['', '**说明**'] + notes
    return title, '\n'.join(lines)


def _write_log(group_id, date, status, member_total, member_done, message=None):
    if PushGroupDigestLog.query.filter_by(group_id=group_id, date=date).first():
        return
    db.session.add(PushGroupDigestLog(
        group_id=group_id, date=date, status=status,
        member_total=member_total, member_done=member_done, message=message))
    db.session.commit()


def flush_digest(group_id, date, force=False):
    """执行合并推送：拉成员当日 dorm 记录 → 渲染 → 发 QQ 群 → 写审计（幂等）。

    发送前原子认领：DELETE 已到点的 pending 行并检查 rowcount，谁删到谁发——延迟 job 与
    30s 对账兜底同刻触发时只有一方能认领成功，另一方直接退出，杜绝重复推送
    （此前「查 log 再发」的防重挡不住双路径并发窗口内的第二次网络请求）。
    发送失败按 attempts 重排队（线性退避），超限记 fail 终态不再重试。"""
    g = db.session.get(PushGroup, group_id)
    if g is None or not g.bound:
        return
    if not force and PushGroupDigestLog.query.filter_by(group_id=group_id, date=date).first():
        return  # 同组同天只发一次

    if force:
        prev_attempts = 0
    else:
        prev_attempts = _claim_pending(group_id, date)
        if prev_attempts is None:
            return  # 认领失败：pending 行已被延迟 job / 对账另一方删走，由对方发送

    members = group_members(g)
    member_rows = _member_records(members, date) if members else []
    member_total = len(members)
    member_done = sum(1 for _, r in member_rows if r is not None and r.status == 'success')

    token, err = _resolve_open_token(g.user_id)
    if token is None:
        _write_log(group_id, date, PushGroupDigestLog.STATUS_FAIL, member_total, member_done, err)
        _clear_pending(group_id, date)
        return

    title, content = _render_digest(g, date, member_rows)
    ok, errmsg = send_qq(token, g.qq_code, title, content, template='markdown')
    if ok:
        status = (PushGroupDigestLog.STATUS_SUCCESS if member_done == member_total
                  else PushGroupDigestLog.STATUS_PARTIAL)
        _write_log(group_id, date, status, member_total, member_done)
        log.info('群合并推送成功 group=%s(%s) date=%s done=%d/%d',
                 g.id, g.name, date, member_done, member_total)
        _clear_pending(group_id, date)
    else:
        _requeue_failed_flush(group_id, date, prev_attempts + 1, member_total, errmsg)
        log.warning('群合并推送失败 group=%s(%s) date=%s: %s',
                    g.id, g.name, date, errmsg)


def _claim_pending(group_id, date):
    """原子认领「已到点」的待触发记录：DELETE pending 行并按 rowcount 判归属，谁删到谁发。

    只认领 flush_at <= now 的行——失败重排队的新行（flush_at 在未来）不可被同刻的
    另一发送路径立即抢走，重试严格由到点后的对账驱动；SELECT 与 DELETE 都带时间
    过滤，认领前行被删走（claimed=0）返回 None，调用方放弃发送——重复推送在结构上
    不再可能。返回认领前行携带的 attempts（供失败重排队延续计数）。"""
    now = now_cst()
    try:
        scope = (PushGroupDigestPending.group_id == group_id,
                 PushGroupDigestPending.date == date,
                 PushGroupDigestPending.flush_at <= now)
        prev = (PushGroupDigestPending.query.filter(*scope)
                .with_entities(PushGroupDigestPending.attempts).first())
        if prev is None:
            return None
        claimed = (PushGroupDigestPending.query.filter(*scope)
                   .delete(synchronize_session=False))
        db.session.commit()
        return prev[0] if claimed else None
    except Exception:
        db.session.rollback()
        log.exception('群合并推送认领失败 group=%s date=%s', group_id, date)
        return None


def _requeue_failed_flush(group_id, date, attempts, member_total, errmsg):
    """发送失败重排队：按已尝试次数线性退避；超过上限记 fail 终态，对账不再重试。

    认领时 pending 行已删除，重排队即重插一行携带累计 attempts；这是发送失败后的
    唯一出路，不再走 _clear_pending（否则重排队行会被立刻清掉，重试失效）。"""
    try:
        if attempts >= MAX_FLUSH_ATTEMPTS:
            _write_log(group_id, date, PushGroupDigestLog.STATUS_FAIL,
                       member_total, 0, f'重试 {attempts} 次仍失败：{errmsg[:200]}')
            return
        db.session.add(PushGroupDigestPending(
            group_id=group_id, date=date,
            flush_at=now_cst() + timedelta(minutes=attempts), attempts=attempts))
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception('群合并推送失败重排队异常 group=%s date=%s', group_id, date)


def _clear_pending(group_id, date):
    try:
        PushGroupDigestPending.query.filter_by(group_id=group_id, date=date).delete(
            synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()


def _flush_job(group_id, date_iso):
    """延迟 job 包装：进入 app context 后执行 flush。"""
    from app.services.scheduler import _app
    if _app is None:
        return
    with _app.app_context():
        try:
            flush_digest(group_id, datetime.strptime(date_iso, '%Y-%m-%d').date())
        except Exception:
            log.exception('群合并推送 flush 失败 group=%s date=%s', group_id, date_iso)


def reconcile_pending_digests():
    """对账兜底：扫描到点未发的待触发记录并补发；清理过期 pending。
    仅防延迟 job 丢失，非 EOD 补发——到点的记录即视为当日收齐。"""
    now = now_cst()
    due = PushGroupDigestPending.query.filter(PushGroupDigestPending.flush_at <= now).all()
    for p in due:
        if PushGroupDigestLog.query.filter_by(group_id=p.group_id, date=p.date).first():
            _clear_pending(p.group_id, p.date)
            continue
        try:
            flush_digest(p.group_id, p.date)
        except Exception:
            log.exception('群合并推送对账补发失败 group=%s date=%s', p.group_id, p.date)
    # 清理超过 2 天的陈旧 pending（理论不应残留，防堆积）
    stale_cut = now.date() - timedelta(days=2)
    try:
        PushGroupDigestPending.query.filter(PushGroupDigestPending.date < stale_cut).delete(
            synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
