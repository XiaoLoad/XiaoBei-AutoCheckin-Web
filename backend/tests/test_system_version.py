# /api/system/info 版本读取回归：VERSION 位置候选覆盖本地开发与 Docker 镜像两种布局，
# 缺失时回退 unknown（曾因构建上下文不含根级 VERSION，线上管理面板显示 vunknown）。
import os

from app.routes.system import _read_version, _version_candidates


def test_version_candidates_cover_local_and_docker_layouts():
    """候选 ① = 仓库根 VERSION（本地开发命中），候选 ② = backend/VERSION（Docker 镜像内命中）"""
    first, second = _version_candidates()
    # 本地仓库布局：候选①（routes 向上三级）应命中仓库根 VERSION
    assert os.path.isfile(first), first
    # 候选②（向上两级 = backend/）本地无该文件（由 Dockerfile 在镜像内打入 /app/VERSION）
    assert second.endswith(os.path.join('backend', 'VERSION')), second


def test_read_version_returns_semver_in_repo():
    """本地开发布局下能读到真实版本号（SemVer，非 unknown）"""
    v = _read_version()
    assert v != 'unknown'
    assert v.count('.') == 2
    assert v[0].isdigit()


def test_read_version_falls_back_to_unknown(monkeypatch):
    """两个候选都读不到时回退 unknown，不抛异常"""
    monkeypatch.setattr('app.routes.system._version_candidates',
                        lambda: ['/nonexistent/A/VERSION', '/nonexistent/B/VERSION'])
    assert _read_version() == 'unknown'
