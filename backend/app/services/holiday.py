# 法定节假日判定（chinese_calendar）。
# 判定口径：双休不算假日——普通周末照常按触发星期执行；只有法定假期段
# （元旦/春节/清明/劳动/端午/中秋/国庆）内的日子才跳过。库的 holidays 字典恰好
# 只含假期段内的日子：段内周末在字典、普通周末与调休补班日不在，天然对齐口径；
# 普通周末与调休补班日照跑是执行端「不跳过」的自然结果，无需单独判定。
# 库数据未覆盖的年份 holidays.get 返回 None → fail-open（视为非假期照常执行）。
from datetime import timedelta

import chinese_calendar

from app.models.user import now_cst

# 节假日模式下的跳过原因文案（skip 落库与推送共用）
SKIP_HOLIDAY = '法定节假日，按配置跳过'
# 假期末日豁免未开时的末日跳过文案
SKIP_LAST_DAY = '法定假日期末日，按配置跳过（未开启末日签到）'

# 库对未覆盖年份调用 is_holiday 等会抛 NotImplementedError（fail-open 捕获范围）
_CAL_ERRORS = (NotImplementedError, ValueError, KeyError, OverflowError)


def is_legal_holiday(d):
    """d 是否属于法定假期段（双休、调休补班日均不算）。异常 fail-open 返回 False。"""
    try:
        return chinese_calendar.holidays.get(d) is not None
    except _CAL_ERRORS:
        return False


def is_last_day_of_holiday(d):
    """d 是否为法定假期段的最后一天（今天在段内、明天不在段内）。
    明天「不在段内」含明年在库外抛异常的情形——按不跳过处理即末日豁免语义。"""
    if not is_legal_holiday(d):
        return False
    try:
        return chinese_calendar.holidays.get(d + timedelta(days=1)) is None
    except _CAL_ERRORS:
        return True


def holiday_skip_reason(resolved, today=None):
    """节假日模式的执行入口判定：返回 None = 照常执行，返回文案 = 跳过原因。
    仅 time.mode == 'holiday' 时生效；normal 模式恒 None（普通周末/调休补班日
    由 weekdays 过滤自然决定是否执行，与本判定无关）。

    lastDaySign 开关（time.holiday.lastDaySign）：假期末日学校常查寝，开启后
    末日照常执行；未开启（默认）末日也跳过。"""
    if not isinstance(resolved, dict):
        return None
    t = resolved.get('time') or {}
    if t.get('mode') != 'holiday':
        return None
    d = today or now_cst().date()
    if not is_legal_holiday(d):
        return None
    # 假期末日：开关开启则照常执行（末日豁免），否则跳过
    if is_last_day_of_holiday(d) and (t.get('holiday') or {}).get('lastDaySign'):
        return None
    if is_last_day_of_holiday(d):
        return SKIP_LAST_DAY
    return SKIP_HOLIDAY
