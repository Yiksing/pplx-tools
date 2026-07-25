"""Rate limiter: randomized intervals, failure backoff. Guards against account risk control, explicitly requested by the owner.

限频器：随机间隔、失败退避。防账号风控，用户明确要求。"""

from __future__ import annotations

import random
import time

from .logging import get_logger

log = get_logger("throttle")


class Throttle:
    """Controls request pacing.

    - delay(): randomized interval between threads/requests
    - backoff(): backoff on failure (429 rate limit / network error / 5xx); 401/403 auth failures do not back off (raise immediately)

    控制请求节奏。

    - delay()：线程/请求之间的随机间隔
    - backoff()：失败（429 限流/网络错误/5xx）时退避；401/403 鉴权失败不退避（立即抛）
    """

    def __init__(self, delay_min: float = 10.0, delay_max: float = 20.0, backoff_factor: float = 3.0):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.backoff_factor = backoff_factor
        self._consecutive_errors = 0

    def delay(self) -> float:
        d = random.uniform(self.delay_min, self.delay_max)
        time.sleep(d)
        return d

    def backoff(self, base: float | None = None) -> float:
        self._consecutive_errors += 1
        base = base if base is not None else self.delay_max
        # Clamp the exponent first: 20×3^8×1.2 is still capped at 300s, preventing float overflow at n≈644
        # 先钳制指数：20×3^8×1.2 仍被 300s 封顶，杜绝 n≈644 时浮点溢出
        n = min(self._consecutive_errors, 8)
        d = base * (self.backoff_factor ** n)
        # ±20% jitter against synchronization, capped at 5 minutes
        # ±20% jitter 防同步，上限 5 分钟
        d = min(d * random.uniform(0.8, 1.2), 300.0)
        log.debug(f"退避 {d:.1f}s（连续失败 {self._consecutive_errors} 次）")
        time.sleep(d)
        return d

    def reset(self):
        self._consecutive_errors = 0
