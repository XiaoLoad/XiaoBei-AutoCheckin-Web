# 进程内滑动节流：key → 最近一次 monotonic 时间戳，间隔内重复调用视为被拦。
# accounts.py 的校验节流走自己的本地实现（_VERIFY_INTERVAL=0 长期关闭）；
# 本工具给「间隔不可为 0」的场景用（如密码回显接口，不限流就是爆破点）。
import time

# 单实例 key 上限：key 含用户可控字符串（如账号名）时，字典会随尝试次数无限增长。
# 超限整批清空——节流的语义是「短间隔防重放」，全清最坏情况是攻击者趁机多打一发，
# 不会破坏限流本身；远优于内存无界增长（DoS 面）。
MAX_KEYS = 10000


class Throttle:
    def __init__(self, interval):
        self.interval = interval
        self._last = {}

    def hit(self, key):
        """记录本次尝试并返回是否被拦：interval 内已出现过同 key 调用即拦截。
        必须在真正执行敏感动作之前调用——每次尝试都要刷新时间戳，连续尝试才会被拦住。"""
        now = time.monotonic()
        last = self._last.get(key)
        if last is None and len(self._last) >= MAX_KEYS:
            self._last.clear()
        self._last[key] = now
        return last is not None and now - last < self.interval
