#!/usr/bin/env python3
"""从 CHANGELOG.md 顶部条目生成 GitHub Release 正文。

用法:
    python scripts/release_notes.py --tag v1.2.0 [--prev v1.1.1]

校验 --tag 与 CHANGELOG 顶部版本一致后，把该条目的说明作为「更新内容」输出；
提供 --prev 时附上一版对比链接。正文写 stdout，供 release.yml 传给
gh release create --notes-file。
"""
import argparse
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_REPO = "XiaoLoad/XiaoBei-AutoCheckin-Web"

# 表格数据行：| 版本 | 日期 | 说明 |
ROW = re.compile(
    r"^\|\s*(\d+\.\d+\.\d+)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|\s*$")


def changelog_top():
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
        for line in f:
            m = ROW.match(line)
            if m:
                return m.group(1), m.group(2).strip(), m.group(3).strip()
    raise SystemExit("CHANGELOG.md 未找到版本条目（形如 | 1.2.0 | 日期 | 说明 |）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="本次发布的 tag（v1.2.0）")
    ap.add_argument("--prev", default="", help="上一个 tag，用于 Full Changelog 对比链接")
    args = ap.parse_args()

    version, date, note = changelog_top()
    if args.tag.lstrip("v") != version:
        raise SystemExit(f"CHANGELOG 顶部为 {version}，与 tag {args.tag} 不一致")

    repo = os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO
    parts = [
        "## 更新内容",
        "",
        f"**{version}**（{date}）",
        "",
        note,
        "",
        "## 部署 / 升级",
        "",
        "```bash",
        f"git fetch --tags && git checkout {args.tag}",
        "docker compose up -d --build",
        "```",
        "",
        f"完整变更见 [CHANGELOG.md](https://github.com/{repo}/blob/main/CHANGELOG.md)。",
    ]
    if args.prev:
        parts.append(
            f"**Full Changelog**: https://github.com/{repo}/compare/{args.prev}...{args.tag}")
    print("\n".join(parts))


if __name__ == "__main__":
    main()
