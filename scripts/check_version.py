#!/usr/bin/env python3
"""版本一致性校验：VERSION == CHANGELOG 顶部条目 == README 徽标。

用法:
    python scripts/check_version.py [--expect-tag v1.2.0]

四方（加 tag 时）必须全部一致，否则非零退出。
供 CI 守门（.github/workflows/ci.yml）与发版工作流（release.yml）调用；
本地发版前也可手动跑一次。
"""
import argparse
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEMVER = re.compile(r"\d+\.\d+\.\d+")


def read_version_file():
    with open(os.path.join(ROOT, "VERSION"), encoding="utf-8") as f:
        text = f.read().strip()
    if not SEMVER.fullmatch(text):
        raise SystemExit(f"VERSION 格式非法: {text!r}")
    return text


def changelog_top_version():
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
        for line in f:
            m = re.match(r"\|\s*(\d+\.\d+\.\d+)\s*\|", line)
            if m:
                return m.group(1)
    raise SystemExit("CHANGELOG.md 未找到版本条目（形如 | 1.2.0 | 日期 | 说明 |）")


def readme_badge_version():
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"badge/version-(\d+\.\d+\.\d+)-blue", text)
    if not m:
        raise SystemExit("README.md 未找到版本徽标（badge/version-x.y.z-blue）")
    return m.group(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect-tag", help="额外校验：tag 名（v1.2.0）与 VERSION 一致")
    args = ap.parse_args()

    sources = {
        "VERSION": read_version_file(),
        "CHANGELOG 顶部条目": changelog_top_version(),
        "README 徽标": readme_badge_version(),
    }
    if args.expect_tag:
        sources[f"tag {args.expect_tag}"] = args.expect_tag.lstrip("v")

    for name, value in sources.items():
        print(f"  {name}: {value}")
    distinct = sorted(set(sources.values()))
    if len(distinct) != 1:
        raise SystemExit(f"版本不一致: {distinct}")
    print(f"版本一致: {distinct[0]}")


if __name__ == "__main__":
    main()
