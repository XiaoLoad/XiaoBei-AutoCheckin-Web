# 教务系统对接蓝图：B 平台账号 ↔ 教务账号绑定、课表同步、概览与当日窗口预览。
# 资源严格按当前登录用户隔离（账号归属校验同 accounts.py）。
# 绑定/同步均为**异步**：接口仅落库凭证并入队，立即返回；教务网偶发秒级挂起
# （单请求最坏 20s×2 重试），阻塞式会让前端 HTTP 先超时误报"网络错误"。
# 前端凭概览里的 syncRunning 轮询至完成，再按 account.status/lastError 展示结果。
from flask import Blueprint, current_app, request

from app.extensions import db
from app.models import ActivityWindow, BAccount, JwAccount
from app.services.jwxt.sync import jwxt_overview, queue_sync, unbind_b_account
from app.utils.auth import token_required
from app.utils.response import error, success

bp = Blueprint('jwxt', __name__, url_prefix='/api/b-accounts')


def _own_account(account_id):
    return BAccount.query.filter_by(id=account_id, user_id=request.current_user.id).first()


@bp.route('/<int:account_id>/jwxt', methods=['GET'])
@token_required
def get_jwxt(account_id):
    """绑定状态 + 课表概览（课程去重清单，供课程排除多选）+ 当日窗口预览。"""
    acc = _own_account(account_id)
    if not acc:
        return error(message='账号不存在', code=4040, status=404)
    overview = jwxt_overview(account_id)
    if overview is None:
        return success({'bound': False, 'windows': []})
    today = request.args.get('date')
    from datetime import date as ddate
    from datetime import datetime as ddatetime
    query_date = None
    if today:
        try:
            query_date = ddatetime.strptime(today, '%Y-%m-%d').date()
        except ValueError:
            return error(message='date 参数格式应为 YYYY-MM-DD', code=4400, status=400)
    from app.models.user import now_cst
    query_date = query_date or now_cst().date()
    schedule_ids = [s.id for s in acc.schedules] if hasattr(acc, 'schedules') else []
    windows = (ActivityWindow.query
               .filter(ActivityWindow.schedule_id.in_(schedule_ids or [0]),
                       ActivityWindow.date == query_date)
               .order_by(ActivityWindow.start_at).all())
    overview['windows'] = [w.to_dict() for w in windows]
    overview['windowDate'] = query_date.isoformat()
    return success(overview)


@bp.route('/<int:account_id>/jwxt', methods=['POST'])
@token_required
def bind_jwxt(account_id):
    """绑定（或更新）教务凭证：**先同步探测登录、验证通过才落库**——错误的学号/
    密码不绑定，用户需重新填写再试。验证通过后提交后台课表同步，结果经概览
    轮询获取（account.status / lastError）。"""
    acc = _own_account(account_id)
    if not acc:
        return error(message='账号不存在', code=4040, status=404)
    payload = request.get_json(silent=True) or {}
    student_no = str(payload.get('studentNo') or '').strip()
    password = str(payload.get('password') or '')
    if not (4 <= len(student_no) <= 32):
        return error(message='教务学号格式不正确（4~32 位）', code=4400, status=400)
    if not (1 <= len(password) <= 64):
        return error(message='教务密码不能为空（64 位以内）', code=4400, status=400)

    # 凭证探测：登录成功即丢弃会话（真实课表拉取由后台同步完成）；失败不落库
    from app.services.jwxt import get_client
    from app.services.jwxt.base import JwxtError
    client = get_client()
    try:
        client.login(student_no, password)
    except JwxtError as e:
        kind_code = {'credential': 4501, 'captcha': 4502, 'network': 4503}.get(e.kind, 4504)
        kind_message = {
            'credential': '教务账号或密码错误，未绑定；请核对后重新填写',
            'captcha': '教务系统触发验证码，未绑定；请稍后在浏览器确认可登录后再试',
            'network': '教务系统暂不可达，未保存本次填写，请稍后再试',
        }.get(e.kind, e.message)
        return error(message=kind_message, code=kind_code, status=400)

    jw = JwAccount.query.filter_by(b_account_id=account_id).first()
    if jw is None:
        jw = JwAccount(b_account_id=account_id, student_no=student_no)
        db.session.add(jw)
    else:
        jw.student_no = student_no
        jw.status = 'ok'
        jw.fail_count = 0
        jw.last_error = ''
    jw.set_password(password)
    db.session.commit()

    queue_sync(account_id, current_app._get_current_object())
    return success({'overview': jwxt_overview(account_id)}, message='绑定成功，课表同步中…')


@bp.route('/<int:account_id>/jwxt/sync', methods=['POST'])
@token_required
def sync_jwxt(account_id):
    """手动触发一次课表同步（后台执行，立即返回；结果经概览轮询获取）。"""
    acc = _own_account(account_id)
    if not acc:
        return error(message='账号不存在', code=4040, status=404)
    if JwAccount.query.filter_by(b_account_id=account_id).first() is None:
        return error(message='该账号尚未绑定教务系统', code=4505, status=400)
    queued = queue_sync(account_id, current_app._get_current_object())
    return success({'overview': jwxt_overview(account_id), 'queued': queued},
                   message='同步已提交' if queued else '同步正在进行中')


@bp.route('/<int:account_id>/jwxt', methods=['DELETE'])
@token_required
def unbind_jwxt(account_id):
    """解绑教务账号：清理凭证与课表快照，课程策略任务回落为每日兜底行为。"""
    acc = _own_account(account_id)
    if not acc:
        return error(message='账号不存在', code=4040, status=404)
    if JwAccount.query.filter_by(b_account_id=account_id).first() is None:
        return error(message='该账号尚未绑定教务系统', code=4505, status=400)
    unbind_b_account(account_id)
    # 事件钩子：绑定关系变化影响 course 策略任务的窗口与 cron 注册，立即对齐
    from app.services.scheduler import sync_schedule
    for s in acc.schedules:
        sync_schedule(s)
    return success(message='已解绑教务账号')
