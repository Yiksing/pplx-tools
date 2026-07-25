"""Credential provider: extracts session cookies from the browser, with storage/reuse/expiry refresh.

Cookies are the key to moving off the browser: once fetched, CookieTransport talks
to the API directly; on expiry or 401/403 they are re-extracted via WebBridge
(the only browser touchpoint).

凭证提供：从浏览器提取会话 cookie，存储/复用/过期刷新。

cookie 是迁出浏览器的关键：取一次后由 CookieTransport 直连 API；
过期或 401/403 时经 WebBridge 重新提取（唯一的浏览器触点）。

A Credential protocol (below) generalizes what a Transport can bind to — session
cookies today, bearer tokens / OAuth-style providers tomorrow — without changing
transport call sites.

下方的 Credential 协议把 Transport 可绑定的凭证泛化——今日为会话 cookie，
明日可为 bearer token / OAuth 类 provider——transport 调用点不变。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .errors import AuthError
from .http.bridge_transport import WebBridgeTransport
from ..config import PPLX_DOMAINS


class CredentialProvider:
    """Extract and cache cookies via WebBridge.

    从 WebBridge 提取并缓存 cookie。"""

    def __init__(self, bridge: WebBridgeTransport, cache_path: Path | None = None,
                 domains: tuple[str, ...] = PPLX_DOMAINS):
        self.bridge = bridge
        self.cache_path = cache_path
        self.domains = domains
        self._cookies: dict[str, str] | None = None
        if cache_path and cache_path.exists():
            try:
                self._cookies = json.loads(cache_path.read_text())
            except Exception:
                self._cookies = None

    def _extract_via_bridge(self) -> dict[str, str]:
        """Read document.cookie in the page context (only the non-HttpOnly part);
        fuller coverage requires CDP Storage.getCookies.

        在页面上下文读 document.cookie（只能拿到非 HttpOnly 部分）；
        更完整需经 CDP Storage.getCookies。"""
        # Prefer CDP (able to read HttpOnly cookies)
        # 优先 CDP（能拿 HttpOnly）
        try:
            data = self.bridge._bridge("cdp", {"method": "Storage.getCookies", "params": {}})
            cookies = {}
            for c in data.get("cookies", []):
                if any(d in (c.get("domain") or "") for d in self.domains):
                    cookies[c["name"]] = c["value"]
            if cookies:
                return cookies
        except Exception:
            pass
        # Fall back to document.cookie
        # 退回 document.cookie
        code = "(() => { const m = {}; document.cookie.split('; ').forEach(p => { const i = p.indexOf('='); if (i > 0) m[p.slice(0, i)] = p.slice(i+1); }); return JSON.stringify(m); })()"
        v = self.bridge.evaluate(code)
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            return json.loads(v)
        raise AuthError("无法经 WebBridge 提取 cookie")

    def get(self) -> dict[str, str]:
        if self._cookies is None:
            self._cookies = self._extract_via_bridge()
            self._save()
        return self._cookies

    def refresh(self) -> dict[str, str]:
        self._cookies = self._extract_via_bridge()
        self._save()
        return self._cookies

    def invalidate(self):
        self._cookies = None
        if self.cache_path and self.cache_path.exists():
            self.cache_path.unlink()

    def _save(self):
        if self.cache_path and self._cookies is not None:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._cookies))

    def is_healthy(self) -> bool:
        return bool(self._cookies)


# ── Credential seam: what a Transport can bind to ──
# ── 凭证接缝：Transport 可绑定的凭证 ──

from http.cookiejar import CookieJar
from typing import Protocol, runtime_checkable


@runtime_checkable
class Credential(Protocol):
    """Authentication credential a Transport can bind to.

    Implementations provide the header mapping merged into every request
    (CookieCredential today; OAuth/token providers tomorrow). A provider that
    yields credentials (e.g. an OAuth flow) only needs to produce an object
    satisfying this protocol — no transport call site changes.

    Transport 可绑定的认证凭证。

    实现方提供并入每个请求的头映射（今日 CookieCredential，明日 OAuth/token
    provider）。产出凭证的 provider（如 OAuth 流程）只需给出满足本协议的对象，
    transport 调用点无需改动。
    """

    def auth_headers(self) -> dict[str, str]:
        """Header mapping merged into every request.

        并入每个请求的头映射。"""
        ...

    def is_healthy(self) -> bool:
        """Whether the credential is currently usable.

        凭证当前是否可用。"""
        ...


class CookieCredential:
    """Session-cookie credential — today's main path.

    会话 cookie 凭证——当前主路径。"""

    def __init__(self, cookies, source: str = ""):
        self._cookies = cookies or {}
        self.source = source

    def cookie_dict(self) -> dict[str, str]:
        """Plain {name: value} form (account switching, cache, transports).

        纯 {name: value} 形态（账户切换、缓存、transport 使用）。"""
        if isinstance(self._cookies, CookieJar):
            return {c.name: c.value for c in self._cookies}
        return dict(self._cookies)

    def auth_headers(self) -> dict[str, str]:
        from .http.cookie_transport import CookieTransport
        return {"Cookie": CookieTransport._build_cookie_header(self._cookies)}

    def is_healthy(self) -> bool:
        return bool(self._cookies)


class BearerCredential:
    """Static bearer-token credential — the seam's second implementation,
    proving the protocol is not cookie-shaped. Future OAuth providers plug in
    at this same point (no CLI wiring yet).

    静态 bearer token 凭证——接缝的第二个实现，证明协议不局限于 cookie 形态。
    未来 OAuth provider 在同一位置接入（暂未接 CLI）。
    """

    def __init__(self, token: str, source: str = ""):
        self._token = token
        self.source = source

    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def is_healthy(self) -> bool:
        return bool(self._token)
