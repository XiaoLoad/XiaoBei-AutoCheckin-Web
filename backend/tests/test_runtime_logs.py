# 运行日志端点测试：鉴权（普通用户 403）、tail 截断、关键字过滤、跨轮转文件拼接
import os

import pytest

from app.routes.admin import _read_log_tail


@pytest.fixture()
def fake_logs_dir(app, monkeypatch, tmp_path):
    """把端点的日志目录指向 tmp_path，造 app.log 与 app.log.1 两档。"""
    log_dir = tmp_path
    (log_dir / 'app.log').write_text(
        '2026-10-04 19:05:25 INFO [scheduler] 启动对账：发现 2 个任务\n'
        '2026-10-04 19:05:36 INFO [scheduler] 任务 2151 网络失败，已安排 10 分钟后补跑\n'
        '2026-10-04 19:39:40 INFO [scheduler] 任务 3779 执行落库：状态=success\n',
        encoding='utf-8')
    (log_dir / 'app.log.1').write_text(
        '2026-10-03 21:20:01 INFO [scheduler] 任务 2151 执行落库：状态=success\n'
        '2026-10-03 21:58:45 INFO [scheduler] 启动对账：发现 143 个任务\n',
        encoding='utf-8')

    import app.routes.admin as admin_mod
    # 端点内按 __file__ 拼 logs 目录，这里 monkeypatch _read_log_tail 的调用入参不可行，
    # 改为在 tmp 下还原相对结构并重定向模块级常量目录的计算——直接 patch 内部函数最稳
    real_read = admin_mod._read_log_tail

    def patched(path, max_bytes=real_read.__defaults__[0] if real_read.__defaults__ else 512 * 1024):
        name = os.path.basename(path)
        return real_read(os.path.join(str(log_dir), name), max_bytes=max_bytes)

    monkeypatch.setattr(admin_mod, '_read_log_tail', patched)
    return log_dir


def test_runtime_logs_requires_admin(fake_logs_dir, app, user_headers, admin_headers):
    c = app.test_client()
    assert c.get('/api/admin/runtime-logs', headers=user_headers).status_code == 403
    res = c.get('/api/admin/runtime-logs', headers=admin_headers)
    assert res.status_code == 200
    data = res.get_json()['data']
    assert data['items'] and data['items'][0]['file'] == 'app.log'


def test_runtime_logs_newest_first_and_tail(fake_logs_dir, app, admin_headers):
    c = app.test_client()
    res = c.get('/api/admin/runtime-logs?tail=2', headers=admin_headers)
    items = res.get_json()['data']['items']
    assert len(items) == 2
    # 倒序：最新一条在前
    assert '19:39:40' in items[0]['line']
    assert '19:05:36' in items[1]['line']


def test_runtime_logs_keyword_filter(fake_logs_dir, app, admin_headers):
    c = app.test_client()
    res = c.get('/api/admin/runtime-logs?q=补跑', headers=admin_headers)
    items = res.get_json()['data']['items']
    assert len(items) == 1
    assert '补跑' in items[0]['line']
    # 关键字大小写不敏感（对 ASCII）：默认不带轮转，app.log 内 3 行全命中
    res = c.get('/api/admin/runtime-logs?q=INFO', headers=admin_headers)
    assert len(res.get_json()['data']['items']) == 3


def test_runtime_logs_rotated_included(fake_logs_dir, app, admin_headers):
    c = app.test_client()
    res = c.get('/api/admin/runtime-logs?tail=10&rotated=1', headers=admin_headers)
    items = res.get_json()['data']['items']
    # app.log 全部在前（新→旧），随后是轮转文件（同为文件内新→旧）
    assert len(items) == 5
    assert items[0]['file'] == 'app.log' and '19:39:40' in items[0]['line']
    assert items[-1]['file'] == 'app.log.1'
    assert '21:20:01' in items[-1]['line']  # 轮转文件里最旧的一条收尾


def test_read_log_tail_drops_partial_first_line(tmp_path):
    """从中间起读时首行残缺必须丢弃，不能吐出半行时间戳。"""
    p = tmp_path / 'partial.log'
    content = ''.join(f'line-{i:03d} ' + 'x' * 100 + '\n' for i in range(50))
    p.write_text(content, encoding='utf-8')
    lines = _read_log_tail(str(p), max_bytes=200)
    assert all(l.startswith('line-') for l in lines)
    assert lines[0].startswith('line-0')  # 某个整行起点


def test_runtime_logs_export_txt(fake_logs_dir, app, admin_headers):
    """format=txt：导出为纯文本附件（当前筛选的原文投影），文件名带关键字与时间戳。"""
    c = app.test_client()
    res = c.get('/api/admin/runtime-logs?format=txt&tail=10&q=补跑', headers=admin_headers)
    assert res.status_code == 200
    assert res.mimetype == 'text/plain'
    disposition = res.headers.get('Content-Disposition', '')
    assert 'attachment' in disposition and 'runtime_logs_' in disposition
    assert res.headers.get('Cache-Control') == 'no-store'
    body = res.get_data(as_text=True)
    # 每行带来源文件前缀，且只含命中的行
    lines = body.splitlines()
    assert len(lines) == 1
    assert '[app.log]' in lines[0] and '补跑' in lines[0]


def test_runtime_logs_export_txt_unfiltered(fake_logs_dir, app, admin_headers):
    """无关键字导出：文件名用 all 标记，行数等于 tail 上限。"""
    c = app.test_client()
    res = c.get('/api/admin/runtime-logs?format=txt&tail=3&rotated=1', headers=admin_headers)
    body = res.get_data(as_text=True)
    lines = body.splitlines()
    assert len(lines) == 3
    assert 'runtime_logs_all_' in res.headers['Content-Disposition']
