#!/usr/bin/env python3
"""版本号递增脚本（SemVer）。

用法:
    python scripts/version_bump.py [minor|major|patch]

读取仓库根目录 VERSION，按类型递增并写回：
    minor  x.y.z -> x.(y+1).0   功能新增 / 开发结束
    major  x.y.z -> (x+1).0.0   上线 / 破坏性或不兼容变更
    patch  x.y.z -> x.y.(z+1)   独立 BUG 修复（1.x 起生效；随功能提交的
                                零星修复并入该功能版本，不单独发版）

递增的同时把 README 顶部的版本徽标同步为新版本号；README 部署示例用
`git describe --tags --abbrev=0` 自动取最新 tag，不写死版本号，无需同步。

注意：本脚本只修改版本号，不负责 git 提交；提交由"提交版本"流程统一处理。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(ROOT, "VERSION")
README_FILE = os.path.join(ROOT, "README.md")
VALID = {"major", "minor", "patch"}

# README 顶部版本徽标：https://img.shields.io/badge/version-<x.y.z>-blue
README_BADGE_RE = re.compile(r"(badge/version-)\d+\.\d+\.\d+(-blue)")


def read_version():
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        text = f.read().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", text):
        raise SystemExit(f"VERSION 格式非法: {text!r}")
    return text


def bump(version, btype):
    major, minor, patch = (int(x) for x in version.split("."))
    if btype == "major":
        return f"{major + 1}.0.0"
    if btype == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def sync_readme_badge(new_version):
    """把 README 顶部版本徽标替换为新版本号，返回替换处数。"""
    with open(README_FILE, "r", encoding="utf-8") as f:
        text = f.read()
    new_text, count = README_BADGE_RE.subn(rf"\g<1>{new_version}\g<2>", text)
    if count == 0:
        raise SystemExit(
            "README 未找到版本徽标（badge/version-x.y.z-blue），请检查 README 结构"
        )
    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write(new_text)
    return count


def main():
    btype = sys.argv[1] if len(sys.argv) > 1 else "minor"
    if btype not in VALID:
        raise SystemExit(f"类型须为 {sorted(VALID)}，收到: {btype!r}")

    old = read_version()
    new = bump(old, btype)
    count = sync_readme_badge(new)
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(new + "\n")
    print(f"{old} -> {new}  ({btype})")
    print(f"README 版本徽标已同步 {count} 处")


if __name__ == "__main__":
    main()
