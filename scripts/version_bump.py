#!/usr/bin/env python3
"""版本号递增脚本（SemVer）。

用法:
    python scripts/version_bump.py [minor|major|patch]

读取仓库根目录 VERSION，按类型递增并写回：
    minor  0.y.z -> 0.(y+1).0   开发阶段功能新增 / 开发结束
    major  0.y.z -> 1.0.0       上线 / 破坏性或不兼容变更
    patch  0.y.z -> 0.y.(z+1)   保留项（按规范修复 BUG 不单独增版本）

注意：本脚本只修改版本号，不负责 git 提交；提交由"提交版本"流程统一处理。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(ROOT, "VERSION")
VALID = {"major", "minor", "patch"}


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


def main():
    btype = sys.argv[1] if len(sys.argv) > 1 else "minor"
    if btype not in VALID:
        raise SystemExit(f"类型须为 {sorted(VALID)}，收到: {btype!r}")

    old = read_version()
    new = bump(old, btype)
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(new + "\n")
    print(f"{old} -> {new}  ({btype})")


if __name__ == "__main__":
    main()
