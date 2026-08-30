# 地理工具：定位抖动 + 围栏距离（提交签到链路共用）。
# 抖动算法移植自旧版 XiaoBeiCheck.apply_location_jitter（圆内均匀采样，更接近真实 GPS 漂移）。
import math
import random

_EARTH_LAT_M = 111320.0  # 每纬度对应的米数（近似）


def apply_location_jitter(latitude, longitude, jitter_meters):
    """在原始坐标周围随机漂移指定范围（米），返回 (lat_str, lng_str)。
    圆内均匀采样：r = R*sqrt(u)，避免按角度均匀时向圆心聚集。"""
    if latitude in (None, '') or longitude in (None, ''):
        return latitude, longitude
    if not jitter_meters or jitter_meters <= 0:
        return str(latitude), str(longitude)
    try:
        lat = float(latitude)
        lng = float(longitude)
    except (TypeError, ValueError):
        return str(latitude), str(longitude)

    angle = random.uniform(0, 2 * math.pi)
    r = float(jitter_meters) * math.sqrt(random.uniform(0, 1))
    lat_offset = r * math.cos(angle) / _EARTH_LAT_M
    lng_offset = r * math.sin(angle) / (_EARTH_LAT_M * math.cos(math.radians(lat)))

    return str(round(lat + lat_offset, 7)), str(round(lng + lng_offset, 7))


def haversine_m(lat1, lng1, lat2, lng2):
    """球面距离（米）。入参可为字符串/数字；非法返回 None（调用方按未知处理）。"""
    try:
        p1, q1, p2, q2 = float(lat1), float(lng1), float(lat2), float(lng2)
    except (TypeError, ValueError):
        return None
    phi1, phi2 = math.radians(p1), math.radians(p2)
    dphi = math.radians(p2 - p1)
    dlmb = math.radians(q2 - q1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 6371000.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
