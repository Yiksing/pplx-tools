"""CookieTransport: direct urllib connection (carrying session cookies), no browser driver needed.

Cookies are provided by CredentialProvider; requests are rate-limited; 429/5xx/network
errors back off and retry; 401/403 are auth failures and raise AuthTransportError
immediately (no backoff).

CookieTransport：urllib 直连（携带会话 cookie），无需浏览器驱动。

cookie 由 CredentialProvider 提供；请求带限频；429/5xx/网络错误退避重试，
401/403 为鉴权失败，立即抛 AuthTransportError（不退避）。
"""

from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..auth import Credential

from ..errors import AuthTransportError, RateLimitError, TransportError
from ..logging import get_logger
from ..throttle import Throttle
from .transport import Transport

log = get_logger("transport")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def _sanitize(url: str) -> str:
    """Log-safe URL form: keep only host+path (query params of signed URLs, e.g. Policy/Signature, are never logged).

    日志安全形态：只留 host+path（签名 URL 的 Policy/Signature 等查询参数不记录）。"""
    try:
        p = urllib.parse.urlparse(url)
        return f"{p.netloc}{p.path}"
    except Exception:
        return url[:80]


class CookieTransport(Transport):
    name = "cookie"

    def __init__(self, cookies: dict[str, str] | CookieJar | None = None,
                 throttle: Throttle | None = None, max_retries: int = 3,
                 credential: "Credential | None" = None):
        self.throttle = throttle or Throttle()
        self.max_retries = max_retries
        # Credential seam (core/auth.py): extra auth headers merged into every request
        # 凭证接缝（core/auth.py）：并入每个请求的额外表头
        self._auth_headers = dict(credential.auth_headers()) if credential is not None else {}
        self._cookie_header = self._build_cookie_header(cookies)
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar()))

    @staticmethod
    def _build_cookie_header(cookies) -> str:
        if not cookies:
            return ""
        if isinstance(cookies, CookieJar):
            return "; ".join(f"{c.name}={c.value}" for c in cookies)
        return "; ".join(f"{k}={v}" for k, v in cookies.items())

    def _open_read(self, req: urllib.request.Request, timeout: int) -> tuple[int, bytes]:
        """Open the request and read the full body, emitting an INFO heartbeat every
        throttle.heartbeat_interval while the round-trip is in flight — so a stalled
        request (slow network) is visible at default verbosity instead of a silent
        terminal. The watchdog only logs; it never changes timing, and any HTTPError /
        network error propagates out unchanged (the watchdog is always stopped).

        打开请求并读满响应体；在途期间每隔 throttle.heartbeat_interval 打一条 INFO 心跳——
        让卡住的请求（慢网络）在默认档可见而非静默终端。看门狗只打日志，不改时序，
        任何 HTTPError/网络错误照常抛出（看门狗必被关闭）。
        """
        interval = getattr(self.throttle, "heartbeat_interval", 10.0)
        if not interval or interval <= 0:
            with self._opener.open(req, timeout=timeout) as r:
                return r.status, r.read()
        done = threading.Event()

        def _beat():
            waited = 0.0
            while not done.wait(interval):
                waited += interval
                try:
                    log.info(f"仍在等待响应 {_sanitize(req.full_url)}（已 {waited:.0f}s）")
                except Exception:
                    pass

        beat = threading.Thread(target=_beat, daemon=True)
        beat.start()
        try:
            with self._opener.open(req, timeout=timeout) as r:
                return r.status, r.read()
        finally:
            done.set()

    def _request(self, req: urllib.request.Request, timeout: int) -> bytes:
        req.add_header("User-Agent", UA)
        if self._cookie_header:
            req.add_header("Cookie", self._cookie_header)
        for k, v in self._auth_headers.items():
            req.add_header(k, v)
        last_err: Exception | None = None
        t0 = time.monotonic()
        for attempt in range(self.max_retries):
            try:
                status, body = self._open_read(req, timeout)
                log.debug(f"{req.method} {_sanitize(req.full_url)} → {status} "
                          f"{len(body)}B {time.monotonic() - t0:.1f}s")
                # Reset backoff counter on success, avoiding monotonic accumulation across requests
                # 成功清零退避计数，避免跨请求单调累积
                self.throttle.reset()
                return body
            except urllib.error.HTTPError as e:
                body = e.read()[:200]
                log.debug(f"{req.method} {_sanitize(req.full_url)} → HTTP {e.code}")
                if e.code in (401, 403):
                    # Auth failure: raise immediately, no backoff (backoff cannot self-heal; the batch layer fail-fasts)
                    # 鉴权失败：立即抛，不退避（退避无法自愈，batch 层会 fail-fast）
                    raise AuthTransportError(f"鉴权失败 {e.code}: {body!r}") from e
                if e.code == 429:
                    last_err = RateLimitError(f"429 限流: {body!r}")
                    if attempt < self.max_retries - 1:
                        # N-06: no pointless sleep after the final failed attempt
                        # N-06：末次失败不再白睡
                        self.throttle.backoff()
                    continue
                if e.code == 400 and b"ENTRY_DELETED" in body:
                    from ..errors import EntryDeletedError
                    raise EntryDeletedError(f"线程已被用户/远端删除: {body!r}") from e
                if e.code == 400 and b"ENTRY_EXPIRED" in body:
                    from ..errors import EntryExpiredError
                    raise EntryExpiredError(f"线程已被平台清除: {body!r}") from e
                if e.code in (500, 502, 503, 504):
                    # Non-429 5xx (incl. Cloudflare's common transient 504): back off and retry at least once before giving up
                    # 非 429 的 5xx（含 Cloudflare 常见的 504 瞬态）：至少退避重试一次再放弃
                    last_err = TransportError(f"HTTP {e.code}: {body!r}")
                    if attempt < self.max_retries - 1:
                        # N-06: no pointless sleep after the final failed attempt
                        # N-06：末次失败不再白睡
                        self.throttle.backoff()
                    continue
                # 404 and other statuses: keep them retryable ordinary errors — exporting right after
                # pplx-ask creates a thread may hit a transient 404 (propagation delay); must never be
                # mapped to the EntryExpiredError terminal state
                # (terminal means never retried, which would bury a live thread that is only briefly invisible).
                # 404 等其他状态码：保持可重试普通错误——pplx-ask 建线程后立即导出
                # 可能瞬态 404（传播延迟），绝不可映射为 EntryExpiredError 终态
                # （终态永不再试，会把暂不可见的活线程误葬）。
                last_err = TransportError(f"HTTP {e.code}: {body!r}")
                break
            except Exception as e:
                # Network-layer error: back off and retry
                # 网络层错误，退避重试
                last_err = TransportError(str(e))
                log.debug(f"{req.method} {_sanitize(req.full_url)} 网络错误: {e}")
                if attempt < self.max_retries - 1:
                    # N-06: no pointless sleep after the final failed attempt
                    # N-06：末次失败不再白睡
                    self.throttle.backoff()
        raise last_err or TransportError("请求失败")

    def get_json(self, url: str, timeout: int = 60) -> Any:
        req = urllib.request.Request(url, method="GET")
        data = self._request(req, timeout)
        try:
            return json.loads(data)
        except json.JSONDecodeError as e:
            # N-09: HTTP 200 with a non-JSON body (Cloudflare interstitial / login HTML), classified as a transport error
            # N-09：HTTP 200 但非 JSON 体（Cloudflare 过场页/登录 HTML），纳入传输错误分类
            raise TransportError(f"GET {_sanitize(url)} → 200 非 JSON 体: {e}") from e

    def post_json(self, url: str, payload: dict, timeout: int = 60) -> Any:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        data = self._request(req, timeout)
        try:
            return json.loads(data)
        except json.JSONDecodeError as e:
            # N-09: HTTP 200 with a non-JSON body (Cloudflare interstitial / login HTML), classified as a transport error
            # N-09：HTTP 200 但非 JSON 体（Cloudflare 过场页/登录 HTML），纳入传输错误分类
            raise TransportError(f"POST {_sanitize(url)} → 200 非 JSON 体: {e}") from e

    def download(self, url: str, timeout: int = 120) -> bytes:
        req = urllib.request.Request(url, method="GET")
        return self._request(req, timeout)
