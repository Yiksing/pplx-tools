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

    def __init__(self, delay_min: float = 10.0, delay_max: float = 20.0, backoff_factor: float = 3.0,
                 heartbeat_interval: float = 10.0):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.backoff_factor = backoff_factor
        # Emit a still-waiting heartbeat every this-many seconds during a long backoff sleep,
        # so a slow network is visible at default verbosity instead of a silent terminal.
        # 长退避睡眠期间每隔这么多秒打一条"仍在等待"心跳，让慢网络在默认档可见，而非静默终端。
        self.heartbeat_interval = heartbeat_interval
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
        # Sleep the full d, but in heartbeat-sized chunks so a long wait is visible at default
        # verbosity (INFO) rather than a silent terminal; total wall-clock is unchanged.
        # 睡满 d，但按心跳分片，让长等待在默认档（INFO）可见而非静默终端；总时长不变。
        self._sleep_with_heartbeat(d)
        return d

    def _sleep_with_heartbeat(self, total: float) -> None:
        """Sleep `total` seconds, emitting an INFO heartbeat up front and every
        heartbeat_interval seconds. The sum of chunk sleeps equals `total` exactly,
        so pacing/anti-ban behavior is byte-identical to a single sleep(total).

        睡满 `total` 秒，起始打一条 INFO，随后每 heartbeat_interval 秒打一次心跳。
        各分片之和严格等于 `total`，节奏/反风控行为与单次 sleep(total) 逐字节一致。
        """
        interval = self.heartbeat_interval
        if interval <= 0 or total <= interval:
            log.info(f"退避 {total:.0f}s（连续失败 {self._consecutive_errors} 次）")
            time.sleep(total)
            return
        log.info(f"退避 ~{total:.0f}s（连续失败 {self._consecutive_errors} 次，网络异常重试中）")
        remaining = total
        while remaining > 1e-6:
            chunk = min(interval, remaining)
            time.sleep(chunk)
            remaining -= chunk
            if remaining > 1e-6:
                log.info(f"仍在等待重试，剩余 ~{remaining:.0f}s")

    def reset(self):
        self._consecutive_errors = 0
