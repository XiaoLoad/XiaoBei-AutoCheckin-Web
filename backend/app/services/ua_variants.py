# UA 模板变体生成器：从一条机型模板批量派生「同机型不同系统/WebView 版本」的变体。
#
# 目的：机型池分配模式（scheduler._resolve_ua）按账号取模散开，池规模 ≥ 账号数时
# 才能接近「一人一机」。单靠手录机型条目很难凑够，而 UA 字符串中的系统版本与
# Chrome/WebView 版本是可枚举的组合维度——同机型派生若干真实存在的版本组合，
# 既扩充池子又不偏离真实设备形态。
#
# 生成规则（确定性，无随机）：同一条模板每次派生结果恒定，便于测试与排查。
import re

# Android 变体维度：系统版本 → 该版本年代常见的 Build 号与 Chrome/WebView 主版本。
# Build 号取机型无关的系统级指纹（同 Android 版本的 Build 在不同机型间本就复用），
# 变体间差异集中在系统版本号、Build 与 Chrome 版本三处。
_ANDROID_VARIANTS = [
    # (Android 版本, Build/指纹, Chrome 主版本)
    ('15', 'AP3A.240905.015', '130'),
    ('14', 'UKQ1.230924.001', '126'),
    ('14', 'UP1A.231005.007', '120'),
    ('13', 'TP1A.220905.001', '116'),
    ('13', 'TQ3A.230901.001', '114'),
    ('12', 'SP1A.210812.016', '110'),
]

# iOS 变体维度：系统版本（Safari/WebKit 版本随系统走，iOS UA 不含 Chrome）
_IOS_VARIANTS = [
    ('18_5', '605.1.15'),
    ('18_2', '605.1.15'),
    ('17_6', '605.1.15'),
    ('17_5', '605.1.15'),
    ('16_7', '605.1.15'),
    ('16_6', '605.1.15'),
]

_ANDROID_RE = re.compile(r'Android (\d+); ([^;]+) Build/([\w.]+)')
_IOS_RE = re.compile(r'iPhone; CPU iPhone OS (\d+_\d+) like Mac OS X')


def _split_android_ua(content):
    """拆出 Android UA 的 (版本, 型号, Build)。非 Android 形态返回 None"""
    m = _ANDROID_RE.search(content)
    if not m:
        return None
    return m.group(1), m.group(2).strip(), m.group(3)


def _split_ios_ua(content):
    """拆出 iOS UA 的系统版本（如 18_2）。非 iOS 形态返回 None"""
    m = _IOS_RE.search(content)
    return m.group(1) if m else None


def derive_variants(content, count=8):
    """从一条 UA 模板派生至多 count 条变体（不含原版）。

    Android：替换「Android 版本 / Build / Chrome 全版本号」三维；
    iOS：替换系统版本（保留 AppleWebKit 版本）。
    超出维度组合数时返回实际可生成数（不循环拼凑重复 UA）。
    非法/无法识别的 UA 返回空列表。"""
    try:
        count = 8 if count is None else int(count)
    except (TypeError, ValueError):
        count = 8
    count = max(1, min(count, 12))
    variants = []
    android = _split_android_ua(content or '')
    if android:
        _, model, _build = android
        for ver, build, chrome in _ANDROID_VARIANTS:
            if len(variants) >= count:
                break
            # Chrome 主版本展开为完整三位版本号（Mobile Safari 形态惯例 .0.0.0 补位）
            new = _ANDROID_RE.sub(
                f'Android {ver}; {model} Build/{build}',
                content, count=1)
            new = re.sub(r'Chrome/\d+(\.\d+)*', f'Chrome/{chrome}.0.0.0', new, count=1)
            if new and new != content and new not in variants:
                variants.append(new)
        return variants

    ios_ver = _split_ios_ua(content or '')
    if ios_ver:
        for ver, _wk in _IOS_VARIANTS:
            if len(variants) >= count:
                break
            new = content.replace(f'iPhone OS {ios_ver} like Mac OS X',
                                  f'iPhone OS {ver} like Mac OS X', 1)
            if new and new != content and new not in variants:
                variants.append(new)
        return variants

    return []
