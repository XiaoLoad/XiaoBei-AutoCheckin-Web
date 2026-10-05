# 审计 F2/F3 回归：
# F2——① purge_user 只删库不删盘，pool_images/{uid}/ 永久残留（uuid 文件名无索引可清）；
#      现行为：删除接口在 DB 事务成功后调用 purge_user_files 整目录清理，失败仅记日志。
#      ② trash 过期清理只在应用启动时执行一次，长驻进程内磁盘缓慢无界增长；
#      现行为：purge_expired_trash 挂进调度器每日清理 job（与日志清理同模式）。
# F3——① find_active_task 固定 pageSize=50，进行中任务超 50 条时目标任务不在首屏，
#      误判「无进行中任务」而 skip；现行为：按若依信封 total 分页拉全（上限 10 页）。
#      ② randomDelayMax 无上限，10**9 让任务近乎永不触发；现行为：写入端 clamp 0~60。
import os

os.environ['USE_STUB_BPLATFORM'] = '1'

import uuid

import pytest

import app.services.b_platform.real as real
from app.extensions import db
from app.models import (BAccount, ConfigSet, ImageGroup, PoolImage, Schedule,
                        SignRecord, User, PushGroup, PushGroupMember)
from app.models.user import now_cst
from app.schemas.config_schema import sanitize_config
from app.schemas.schedule_schema import _clean_custom
from app.services.image_store import purge_expired_trash, purge_user_files, save_file, user_dir


# ───────────────────────── F3.2：randomDelayMax 边界 ─────────────────────────

def test_sanitize_config_clamps_random_delay_max():
    """standalone/follow 配置路径：超限 clamp 到 60，负数抬到 0，合法值不动。"""
    base = {'time': {'signTime': {'hour': 8, 'minute': 0}, 'startHour': 8, 'endHour': 22,
                     'weekdays': [1, 2], 'mode': 'normal'},
            'remarks': ['r'], 'image': {}, 'push': {}, 'advanced': {}}

    cfg = {**base, 'time': {**base['time'], 'randomDelayMax': 10 ** 9}}
    ok, cleaned = sanitize_config(cfg)
    assert ok and cleaned['time']['randomDelayMax'] == 60

    cfg = {**base, 'time': {**base['time'], 'randomDelayMax': -5}}
    ok, cleaned = sanitize_config(cfg)
    assert ok and cleaned['time']['randomDelayMax'] == 0

    cfg = {**base, 'time': {**base['time'], 'randomDelayMax': 30}}
    ok, cleaned = sanitize_config(cfg)
    assert ok and cleaned['time']['randomDelayMax'] == 30


def test_clean_custom_clamps_random_delay_max():
    """custom 模式内联 randomDelayMax 同口径 clamp（schedule.custom 顶层）。"""
    ok, cfg = _clean_custom({'hour': 8, 'minute': 0, 'weekdays': [1], 'randomDelayMax': 10 ** 9})
    assert ok and cfg['randomDelayMax'] == 60
    ok, cfg = _clean_custom({'hour': 8, 'minute': 0, 'weekdays': [1], 'randomDelayMax': 5})
    assert ok and cfg['randomDelayMax'] == 5


# ───────────────────────── F3.1：find_active_task 分页拉全 ─────────────────────────

SESSION = {'token': 'tok', 'ua': 'UA/1'}


def _row(i, finished=0):
    return {'id': 100000 + i, 'knowingName': f'任务{i}', 'isPicture': 1,
            'isFinishKnowing': finished, 'startTime': '19:00:00', 'endTime': '23:00:00'}


def test_find_active_task_paginates_beyond_first_page(monkeypatch):
    """目标在第 2 页（rows 61 条、total=61）：不翻页时 50 条首屏找不到 → 现在
    分页拉全后必须找到第 61 条任务，而不是误判「无进行中任务」。"""
    list_calls = []

    def fake_request(method, url, **kw):
        if url.endswith('/student/know/list'):
            list_calls.append(kw.get('params'))
            page = kw['params']['pageNum']
            if page == 1:
                # 首屏 50 条全部已签（finish=1），未签任务在第 2 页
                return type('R', (), {'json': lambda s: {
                    'code': 200, 'total': 61,
                    'rows': [_row(i, finished=1) for i in range(50)]}})()
            return type('R', (), {'json': lambda s: {
                'code': 200, 'total': 61,
                'rows': [_row(i, finished=0) for i in range(50, 61)]}})()
        # 找到任务后的详情补查（围栏）
        return type('R', (), {'json': lambda s: {
            'code': 200, 'data': {'id': 100060, 'location': '[]'}}})()

    monkeypatch.setattr(real.requests, 'request', fake_request)
    ctx = real.RealAdapter().find_active_task(SESSION, 'dorm')
    assert len(list_calls) == 2
    assert ctx['task']['id'] == 100050  # 第 2 页第一条未签任务


def test_find_active_task_stops_after_single_page_when_total_fits(monkeypatch):
    """total ≤ pageSize：列表只请求一页（详情补查不计入翻页断言）。"""
    list_calls = []

    def fake_request(method, url, **kw):
        if url.endswith('/student/know/list'):
            list_calls.append(kw.get('params'))
            return type('R', (), {'json': lambda s: {
                'code': 200, 'total': 1,
                'rows': [_row(1, finished=0)]}})()
        return type('R', (), {'json': lambda s: {
            'code': 200, 'data': {'id': 100001, 'location': '[]'}}})()

    monkeypatch.setattr(real.requests, 'request', fake_request)
    ctx = real.RealAdapter().find_active_task(SESSION, 'dorm')
    assert len(list_calls) == 1
    assert ctx['task']['id'] == 100001


def test_find_active_task_caps_at_10_pages(monkeypatch):
    """平台脏 total（永远大于已取行数）时以 10 页（500 条）封顶，不无限翻页。"""

    def fake_request(method, url, **kw):
        page = kw['params']['pageNum']
        return type('R', (), {'json': lambda s: {
            'code': 200, 'total': 10 ** 9,
            'rows': [_row(i, finished=1) for i in range(50)]}})()

    monkeypatch.setattr(real.requests, 'request', fake_request)
    ctx = real.RealAdapter().find_active_task(SESSION, 'dorm')
    # 10 页全部已签 → finished_task 语义兜住，不抛错不无限翻
    assert ctx['task'] is None
    assert ctx['finished_task'] is not None


# ───────────────────────── F2：图片文件生命周期 ─────────────────────────

@pytest.fixture()
def file_env(app_ctx, tmp_path):
    """唯一用户 + 独立 UPLOAD_DIR：purge_user_files 是真删目录操作，必须隔离。"""
    app_ctx.config['UPLOAD_DIR'] = str(tmp_path)
    uname = f'tc_f2f3_{uuid.uuid4().hex[:10]}'
    u = User(username=uname, role='user', enabled=True, quota=100, used_quota=0)
    u.set_password('pw')
    db.session.add(u)
    db.session.flush()
    yield {'uid': u.id, 'app': app_ctx}
    for model in (PoolImage, PushGroup, Schedule, ImageGroup, BAccount, SignRecord):
        model.query.filter_by(user_id=u.id).delete(synchronize_session=False)
    remaining = db.session.get(User, u.id)
    if remaining is not None:  # 端到端用例里用户已被删除接口清掉
        db.session.delete(remaining)
    db.session.commit()


def test_purge_user_files_removes_directory(file_env):
    """purge_user_files 删除整个 pool_images/{uid}/ 目录；目录不存在时静默。"""
    uid = file_env['uid']
    d = user_dir(uid)  # user_dir 会建目录
    fname = save_file(uid, b'\xff\xd8fake', '.jpg')
    assert os.path.exists(os.path.join(d, fname))

    purge_user_files(uid)
    assert not os.path.exists(d)
    purge_user_files(uid)  # 幂等：再删一次不抛错


def test_delete_user_endpoint_removes_disk_files(file_env):
    """端到端：DELETE /api/users/{id} 后磁盘图片目录一并消失（F2 主场景）。"""
    uid = file_env['uid']
    save_file(uid, b'\xff\xd8fake', '.jpg')
    assert os.path.exists(user_dir(uid))

    from app.utils.auth import generate_token
    from app.models import User as U
    admin = U.query.filter_by(username='tc_admin').first()
    if admin is None:  # 与 conftest._ensure_user 同口径的懒创建
        admin = U(username='tc_admin', role='admin', enabled=True, quota=100, used_quota=0)
        admin.set_password('pw-tc_admin')
        db.session.add(admin)
        db.session.commit()
    # 断言前先取目录路径：user_dir() 有 makedirs 副作用，删除后再调用会把目录建回来
    user_dir_path = user_dir(uid)
    r = file_env['app'].test_client().delete(
        f'/api/users/{uid}',
        headers={'Authorization': f'Bearer {generate_token(admin)}'})
    assert r.status_code == 200, r.get_json()
    assert not os.path.exists(user_dir_path)


def test_purge_expired_trash_removes_stale_rows_and_files(file_env):
    """trash 过期清理（挂每日 job 的实现本体）：过期 trash 记录+文件被清，新的保留。"""
    from datetime import timedelta
    uid = file_env['uid']

    def _trash_img(name, trashed_at):
        img = PoolImage(user_id=uid, orig_name=name, filename=f'{name}_{uuid.uuid4().hex[:6]}.jpg',
                        size=64, mime='image/jpeg', status='trash', trashed_at=trashed_at)
        db.session.add(img)
        db.session.commit()
        with open(os.path.join(user_dir(uid), img.filename), 'wb') as f:
            f.write(b'\xff\xd8fake')
        return img

    stale = _trash_img('old', now_cst() - timedelta(days=8))
    fresh = _trash_img('new', now_cst() - timedelta(days=1))

    n = purge_expired_trash(days=7)
    assert n == 1
    assert db.session.get(PoolImage, stale.id) is None
    assert not os.path.exists(os.path.join(user_dir(uid), stale.filename))
    assert db.session.get(PoolImage, fresh.id) is not None
    assert os.path.exists(os.path.join(user_dir(uid), fresh.filename))


def test_daily_prune_job_invokes_trash_cleanup(file_env, monkeypatch):
    """调度器每日清理 job 必须调用 purge_expired_trash（F2 第二半的挂接点回归）。"""
    from app.services import scheduler as sch
    called = {'n': 0}
    monkeypatch.setattr('app.services.image_store.purge_expired_trash',
                        lambda days=7: called.__setitem__('n', called['n'] + 1) or 0)
    monkeypatch.setattr(sch, '_app', file_env['app'])
    # 伪装 get_setting 返回 None → 走默认保留天数
    monkeypatch.setattr(sch, 'get_setting', lambda k: None)
    # 各表清理走真实 DB（空表无害），SignRecord/PushLog/OpLog 模型已在模块导入
    sch._prune_old_sign_records()
    assert called['n'] == 1
