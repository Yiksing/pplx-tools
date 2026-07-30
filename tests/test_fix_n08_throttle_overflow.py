"""N-08 regression: Throttle.backoff must not raise OverflowError under huge
consecutive-error counts.

N-08 回归测试：Throttle.backoff 连续失败大次数下不抛 OverflowError。"""

from __future__ import annotations

from unittest.mock import patch

from pplx_export.core.throttle import Throttle


def test_backoff_no_overflow_on_huge_consecutive_errors():
    t = Throttle()
    # Far beyond the overflow threshold (n≈644); pre-fix, backoff() raised OverflowError here
    # 远超溢出阈值（n≈644），修复前此处 backoff 会抛 OverflowError
    t._consecutive_errors = 1000
    with patch("pplx_export.core.throttle.time.sleep"):
        d = t.backoff()
    assert d <= 300.0
    # The counter still increments faithfully, keeping logs readable
    # 计数仍如实递增，日志可读
    assert t._consecutive_errors == 1001


def test_backoff_normal_path_unchanged():
    t = Throttle()
    with patch("pplx_export.core.throttle.time.sleep"):
        for _ in range(8):
            d = t.backoff()
        # For n≤8 the exponential is unclamped: base=20, factor=3, jitter 0.8~1.2 —
        # pre-clamp the result can exceed the cap
        # n≤8 时指数未钳制：base=20、factor=3、jitter 0.8~1.2，结果必封顶前可达上限之外
        assert 0 < d <= 300.0
    # Clamp boundary: results for n=8 and n=9 should both already be capped at ≤300 — identical behavior
    # 钳制边界：n=8 与 n=9 的结果都应已封顶到 ≤300，行为一致
    t2 = Throttle()
    with patch("pplx_export.core.throttle.time.sleep"):
        t2._consecutive_errors = 8
        d8 = t2.backoff()
        t2._consecutive_errors = 20
        d20 = t2.backoff()
    # 20×3^8×0.8 ≈ 105k >> 300; both paths yield the same capped value
    # 20×3^8×0.8 ≈ 105k >> 300，两路径同为封顶值
    assert d8 == 300.0 and d20 == 300.0


def test_backoff_heartbeat_preserves_total_and_chunks():
    """Heartbeat chunking must not change total wall-clock: the sum of chunk sleeps
    equals the returned d exactly, split into ceil(d/interval) chunks.

    心跳分片不得改变总时长：各分片之和严格等于返回的 d，分成 ceil(d/interval) 片。"""
    import math

    slept: list[float] = []
    t = Throttle(heartbeat_interval=10.0)
    with patch("pplx_export.core.throttle.time.sleep", slept.append):
        t._consecutive_errors = 1  # base=20, n=2 → 20*9=180 before jitter/cap → long enough to chunk
        d = t.backoff()
    assert d <= 300.0
    assert abs(sum(slept) - d) < 1e-6, "分片之和必须等于 d，总时长不变"
    assert len(slept) == math.ceil(d / 10.0), "分片数应为 ceil(d/interval)"
    assert all(s <= 10.0 + 1e-9 for s in slept), "每片不超过心跳间隔"


def test_backoff_short_wait_single_sleep():
    """A wait shorter than the heartbeat interval sleeps exactly once (no heartbeat spam).

    短于心跳间隔的等待只睡一次（不刷心跳）。"""
    slept: list[float] = []
    t = Throttle(heartbeat_interval=10.0)
    with patch("pplx_export.core.throttle.time.sleep", slept.append):
        d = t.backoff(base=1.0)  # ~1*3=3s before jitter → < 10s interval
    assert len(slept) == 1
    assert abs(slept[0] - d) < 1e-6
