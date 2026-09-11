# B 平台历史读取服务：签到历史任务与任务详情的代理读取，token 失效自动重登刷新一次。
# 两个调用方共用同一实现：accounts 蓝图（本人账号）与 admin 蓝图（管理员全站巡检），
# 保证「管理员看到的记录与用户自己看到的完全同源同口径」。
from app.extensions import db
from app.services.b_platform import get_adapter
from app.services.b_platform.base import BPlatformError
from app.utils.response import error


def call_with_refresh(account, call):
    """调用 B 平台读取函数；token 失效（credential 类错误）自动重登并刷新一次。
    返回 (result, err_resp)：成功时 err_resp 为 None，失败时 result 为 None。"""
    adapter = get_adapter()
    token = account.get_token()
    if not token:
        try:
            result = adapter.verify_and_fetch(account, account.get_password())
        except BPlatformError as e:
            prefix = {'network': 'B 平台网络不可达', 'captcha': '验证码环节失败',
                      'credential': 'B 平台凭证被拒'}.get(e.kind, 'B 平台校验失败')
            return None, error(message=f'{prefix}：{e.message}', code=4301, status=400)
        account.set_token(result.token)
        db.session.commit()
        token = result.token
    try:
        return call(adapter, token), None
    except BPlatformError as e:
        if e.kind != 'credential':
            return None, error(message=f'B 平台读取失败：{e.message}', code=4302, status=502)
        # token 失效：重登刷新后重试一次
        try:
            new_token = adapter.login(account.account, account.get_password())
        except BPlatformError as le:
            return None, error(message=f'B 平台重登失败：{le.message}', code=4303, status=502)
        account.set_token(new_token)
        db.session.commit()
        try:
            return call(adapter, new_token), None
        except BPlatformError as e2:
            return None, error(message=f'B 平台读取失败：{e2.message}', code=4302, status=502)


def fetch_history_tasks(account, type_filter='all', status_filter='all',
                        date_from=None, date_to=None):
    """合并寝/活历史任务（各自取全量），按类型/状态/日期窗口筛选后排序，附全历史口径统计。

    筛选口径与用户端完全一致（自 accounts.list_sign_records 抽取）：
      type       dorm | activity | all
      status     all | signed | unsigned | needPhoto（按平台回传 finished/needPhoto 过滤）
      date_from / date_to   任务区间（startDate~endDate）与窗口重叠者入选

    返回 ({merged, overview, meta}, err_resp)：
      overview  全历史口径统计（type+status 过滤、不受日期窗口影响）：total/finished/unsigned/needPhoto/rate
      meta      全历史口径的最早/最晚任务日期（earliest_date/latest_date）
    """
    def _raw(ad, tk):
        return ad.fetch_history_tasks(tk, 'know') + ad.fetch_history_tasks(tk, 'sign')

    result, err = call_with_refresh(account, _raw)
    if err:
        return None, err
    merged = result
    if type_filter in ('dorm', 'activity'):
        merged = [t for t in merged if t['type'] == type_filter]

    def _range_of(t):
        s = (t.get('startDate') or '')[:10]
        e = (t.get('endDate') or s)[:10]
        return s, e

    # 全历史统计与最近数据月份：type 过滤后、status/日期过滤前计算
    finished = sum(1 for t in merged if t.get('finished'))
    need_photo = sum(1 for t in merged if t.get('needPhoto'))
    total_all = len(merged)
    dates = [d for t in merged for d in _range_of(t) if d]
    overview = {
        'total': total_all,
        'finished': finished,
        'unsigned': total_all - finished,
        'needPhoto': need_photo,
        'rate': round(finished / total_all * 100) if total_all else 0,
    }
    meta = {'earliest_date': min(dates) if dates else None,
            'latest_date': max(dates) if dates else None}

    if status_filter == 'signed':
        merged = [t for t in merged if t.get('finished')]
    elif status_filter == 'unsigned':
        merged = [t for t in merged if not t.get('finished')]
    elif status_filter == 'needPhoto':
        merged = [t for t in merged if t.get('needPhoto')]

    # 日期窗口：任务区间与窗口有重叠即入选（覆盖长任务跨月/跨日的日历语义）
    if date_from or date_to:
        def _overlap(t):
            s, e = _range_of(t)
            if not s:
                return False
            if date_from and e < date_from:
                return False
            if date_to and s > date_to:
                return False
            return True
        merged = [t for t in merged if _overlap(t)]

    merged.sort(key=lambda t: (t['startDate'], t['startTime']), reverse=True)
    return {'merged': merged, 'overview': overview, 'meta': meta}, None


def fetch_task_detail(account, kind, task_id):
    """任务地理围栏 + 签到记录列表（listLog）。know/sign 由 kind 区分。
    返回 ({geoFence, logs}, err_resp)。"""
    def _raw(ad, tk):
        detail = ad.fetch_task_detail(tk, kind, task_id)
        logs = ad.fetch_task_logs(tk, kind, task_id)
        return {'geoFence': detail['geoFence'], 'logs': logs}

    return call_with_refresh(account, _raw)
