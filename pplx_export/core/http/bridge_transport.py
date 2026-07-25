"""WebBridgeTransport: issues fetch calls inside the user's browser page context
via the local WebBridge (127.0.0.1:10086) (cookies attached automatically),
serving as the fallback/backup channel.

WebBridgeTransport：经本机 WebBridge（127.0.0.1:10086）在用户浏览器
页面上下文中发 fetch（自动带 cookie），作为回退/备用通道。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from ..errors import AuthTransportError, EntryDeletedError, EntryExpiredError, RateLimitError, TransportError
from ..throttle import Throttle
from .transport import Transport


class WebBridgeTransport(Transport):
    name = "webbridge"

    def __init__(self, daemon: str = "http://127.0.0.1:10086", session: str = "pplx-export",
                 max_retries: int = 3):
        self.daemon = daemon.rstrip("/")
        self.session = session
        self.max_retries = max_retries
        self.throttle = Throttle()

    def _bridge(self, action: str, args: dict, timeout: int = 120) -> dict:
        body = json.dumps({"action": action, "args": args, "session": self.session}).encode()
        req = urllib.request.Request(f"{self.daemon}/command", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                resp = json.load(r)
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
            raise TransportError(f"WebBridge 不可达（{self.daemon}）: {e}") from e
        if not resp.get("ok"):
            raise TransportError(f"WebBridge {action} 失败: {resp.get('error')}")
        return resp["data"]

    def evaluate(self, code: str, timeout: int = 120) -> Any:
        data = self._bridge("evaluate", {"code": code}, timeout=timeout)
        v = data.get("value")
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v
        return v

    def _classify(self, method: str, url: str, res: dict) -> Exception:
        """Non-200 status classification (N-05, aligned with CookieTransport semantics):
        401/403 → AuthTransportError (raise immediately, no backoff; batch layer fail-fasts);
        400 with ENTRY_DELETED in the first 200 response chars → EntryDeletedError (terminal, user/remote deletion);
        400 with ENTRY_EXPIRED in the first 200 response chars → EntryExpiredError (terminal, platform purge);
        429/5xx → return a retryable error for the caller to back off and retry; all other statuses raise TransportError immediately.

        非 200 状态分类（N-05，对齐 CookieTransport 语义）：
        401/403 → AuthTransportError（立即抛，不退避，batch 层 fail-fast）；
        400 且响应头 200 字符含 ENTRY_DELETED → EntryDeletedError（终态，用户/远端删除）；
        400 且响应头 200 字符含 ENTRY_EXPIRED → EntryExpiredError（终态，平台清除）；
        429/5xx → 返回可重试错误，由调用方退避重试；其余状态立即抛 TransportError。
        """
        status = res.get("status")
        head = res.get("head") or ""
        if status in (401, 403):
            raise AuthTransportError(f"鉴权失败 {status}: {head[:200]!r}")
        if status == 400 and "ENTRY_DELETED" in head:
            raise EntryDeletedError(f"线程已被用户/远端删除: {head[:200]!r}")
        if status == 400 and "ENTRY_EXPIRED" in head:
            raise EntryExpiredError(f"线程已被平台清除: {head[:200]!r}")
        if status == 429:
            return RateLimitError(f"{method} {url[:70]} → 429 限流")
        if status in (500, 502, 503, 504):
            return TransportError(f"{method} {url[:70]} → HTTP {status}")
        raise TransportError(f"{method} {url[:70]} → {status}")

    def get_json(self, url: str, timeout: int = 60) -> Any:
        # On non-200 the JS side does not parse JSON; it only returns the first 200 body chars for error classification (ENTRY_EXPIRED detection)
        # 非 200 时 JS 不解析 JSON，只回传 body 前 200 字符供错误分类（ENTRY_EXPIRED 判定）
        code = f"""(async () => {{
          const r = await fetch({json.dumps(url)}, {{credentials: "include"}});
          const t = await r.text();
          if (r.status !== 200) return JSON.stringify({{status: r.status, head: t.slice(0, 200)}});
          return JSON.stringify({{status: r.status, json: JSON.parse(t)}});
        }})()"""
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            # Note: on 200 with a non-JSON body, JS-side JSON.parse throws; status is unavailable, so it propagates as a bridge error
            # 注：200 但响应体非 JSON 时 JS 侧 JSON.parse 抛错，拿不到 status，只能按 bridge 错误上抛
            res = self.evaluate(code, timeout=timeout)
            if isinstance(res, dict) and res.get("status") == 200:
                # Reset backoff counter on success (F-05, aligned with CookieTransport)
                # 成功清零退避计数（F-05，对齐 CookieTransport）
                self.throttle.reset()
                return res["json"]
            if isinstance(res, dict):
                # 429/5xx return errors; everything else raises directly
                # 429/5xx 返回错误，其余直接抛
                last_err = self._classify("GET", url, res)
                if attempt < self.max_retries - 1:
                    # N-06: no pointless sleep after the final failed attempt
                    # N-06：末次失败不再白睡
                    self.throttle.backoff()
                continue
            raise TransportError(f"GET {url[:70]} → {res}")
        raise last_err or TransportError(f"GET {url[:70]} → 重试 {self.max_retries} 次仍失败")

    def post_json(self, url: str, payload: dict, timeout: int = 60) -> Any:
        code = f"""(async () => {{
          const r = await fetch({json.dumps(url)}, {{method: "POST", credentials: "include",
            headers: {{"Content-Type": "application/json"}}, body: JSON.stringify({json.dumps(payload)})}});
          const t = await r.text();
          if (r.status !== 200) return JSON.stringify({{status: r.status, head: t.slice(0, 200)}});
          return JSON.stringify({{status: r.status, json: JSON.parse(t)}});
        }})()"""
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            res = self.evaluate(code, timeout=timeout)
            if isinstance(res, dict) and res.get("status") == 200:
                # Reset backoff counter on success (F-05, aligned with CookieTransport)
                # 成功清零退避计数（F-05，对齐 CookieTransport）
                self.throttle.reset()
                return res["json"]
            if isinstance(res, dict):
                last_err = self._classify("POST", url, res)
                if attempt < self.max_retries - 1:
                    # N-06: no pointless sleep after the final failed attempt
                    # N-06：末次失败不再白睡
                    self.throttle.backoff()
                continue
            raise TransportError(f"POST {url[:70]} → {res}")
        raise last_err or TransportError(f"POST {url[:70]} → 重试 {self.max_retries} 次仍失败")

    def download(self, url: str, timeout: int = 120) -> bytes:
        # In-browser fetch → base64, decoded back to bytes (signed URLs work same-origin or cross-origin)
        # 浏览器内 fetch 转 base64，再解回 bytes（签名 URL 同源/跨域均可）
        code = f"""(async () => {{
          const r = await fetch({json.dumps(url)});
          if (!r.ok) return JSON.stringify({{status: r.status, head: (await r.text()).slice(0, 200), b64: null}});
          const buf = await r.arrayBuffer();
          let bin = "";
          const bytes = new Uint8Array(buf);
          const chunk = 0x8000;
          for (let i = 0; i < bytes.length; i += chunk) {{
            bin += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
          }}
          return JSON.stringify({{status: r.status, b64: btoa(bin)}});
        }})()"""
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            res = self.evaluate(code, timeout=timeout)
            # A missing/None b64 key is real failure; empty string = 0-byte file, legal (b64decode("") → b"")
            # b64 键缺失/None 才是真失败；空串 = 0 字节文件，合法（b64decode("") → b""）
            if isinstance(res, dict) and res.get("status") == 200 and res.get("b64") is not None:
                import base64
                # Reset backoff counter on success (F-05)
                # 成功清零退避计数（F-05）
                self.throttle.reset()
                return base64.b64decode(res["b64"])
            if isinstance(res, dict) and res.get("status") is not None:
                last_err = self._classify("download", url, res)
                if attempt < self.max_retries - 1:
                    # N-06: no pointless sleep after the final failed attempt
                    # N-06：末次失败不再白睡
                    self.throttle.backoff()
                continue
            raise TransportError(f"download {url[:70]} → {res if not isinstance(res, dict) else res.get('status')}")
        raise last_err or TransportError(f"download {url[:70]} → 重试 {self.max_retries} 次仍失败")

    def navigate(self, url: str, wait: float = 4.0) -> None:
        try:
            self._bridge("navigate", {"url": url}, timeout=90)
        except TransportError as e:
            if "timeout" not in str(e).lower():
                raise
        time.sleep(wait)
