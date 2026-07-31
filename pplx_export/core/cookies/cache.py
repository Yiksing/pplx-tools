"""Cookie cache: freshness-validated, account-labelled, atomically written.

The cache lets repeated runs skip the browser store within the freshness
window (CACHE_MAX_AGE_S, 12h). Session cookies are login-equivalent
credentials, so writes are 0o600 from creation.

cookie 缓存：新鲜期校验、账户标注、原子写入。

缓存让新鲜期（CACHE_MAX_AGE_S，12h）内的重复运行免去浏览器库读取。
会话 cookie 等价登录凭证，故写入自创建起即为 0o600。
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

# Cache freshness window: 12h
# 缓存新鲜期 12h
CACHE_MAX_AGE_S = 12 * 3600


class CookieCache:
    """Cookie cache with freshness and account validation.

    带新鲜度与账户校验的 cookie 缓存。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self, max_age_s: int = CACHE_MAX_AGE_S) -> dict[str, str] | None:
        hit = self.load_with_source(max_age_s)
        return hit[0] if hit else None

    def load_with_source(self, max_age_s: int = CACHE_MAX_AGE_S) -> tuple[dict[str, str], str] | None:
        """Fresh cache as (cookies, origin source label); None when absent/stale/corrupt.

        The origin label (e.g. `browser:chrome`, written by save()) lets callers keep
        source fidelity on cache hits — e.g. deriving the right User-Agent family.

        新鲜缓存返回 (cookies, 原始来源标签)；缺失/过期/损坏返回 None。

        来源标签（save() 写入，如 `browser:chrome`）让调用方在缓存命中时仍保有
        来源保真——例如推导正确的 User-Agent 浏览器族。"""
        if not self.path.exists():
            return None
        try:
            doc = json.loads(self.path.read_text())
        except Exception:
            return None
        ts = doc.get("fetched_at", 0)
        if not isinstance(ts, (int, float)):
            # fetched_at manually corrupted (e.g. a string): treat as no cache, do not raise TypeError
            # fetched_at 被手工改坏（字符串等）：按无缓存处理，不抛 TypeError
            return None
        if time.time() - ts > max_age_s:
            return None
        cookies = doc.get("cookies")
        if not isinstance(cookies, dict):
            return None
        source = doc.get("source")
        return cookies, source if isinstance(source, str) else ""

    def save(self, cookies: dict[str, str], source: str, account_email: str = ""):
        """Atomic write (V5-06, aligned with BatchState.save): the temp file is
        created with 0o600, then os.replace — eliminates both "interrupted
        overwrite leaving a truncated JSON" and the "644 window at creation
        exposing session cookies" problems (session cookies are login-equivalent
        credentials).

        原子写入（V5-06，对齐 BatchState.save）：临时文件以 0o600 创建后
        os.replace——消除「直接覆写被中断留下截断 JSON」与「创建瞬间 644
        窗口期会话 cookie 暴露」两个问题（会话 cookie 等价登录凭证）。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps({
                "fetched_at": time.time(), "source": source,
                "account_email": account_email, "cookies": cookies,
            }))
        os.replace(tmp, self.path)
