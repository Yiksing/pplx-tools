"""FallbackTransport: direct cookie connection first; on failure, refresh cookies and degrade to WebBridge.

FallbackTransport：Cookie 直连优先，失败时刷新 cookie 并降级到 WebBridge。"""

from __future__ import annotations

from typing import Any

from ..errors import AuthTransportError, TransportError
from .transport import Transport


class FallbackTransport(Transport):
    name = "fallback"

    def __init__(self, cookie: Transport, bridge: Transport, credential_provider=None):
        self.cookie = cookie
        self.bridge = bridge
        # Refreshes cookies on 401/403
        # 401/403 时刷新 cookie
        self.credential_provider = credential_provider
        self._use_bridge = False

    def _refresh_cookie(self) -> bool:
        if self.credential_provider is None:
            return False
        try:
            new = self.credential_provider.refresh()
            if new and hasattr(self.cookie, "_cookie_header"):
                from .cookie_transport import CookieTransport
                self.cookie._cookie_header = CookieTransport._build_cookie_header(new)
                return True
        except Exception:
            pass
        return False

    def _run(self, method: str, *args, **kwargs) -> Any:
        if not self._use_bridge:
            try:
                return getattr(self.cookie, method)(*args, **kwargs)
            except TransportError as e:
                # Type check (F-16: the original string match would misjudge a 5xx body containing "401" as an auth failure)
                # 类型判断（F-16：原字符串匹配会把含 "401" 字样的 5xx body 误判为鉴权失败）
                if isinstance(e, AuthTransportError):
                    if self._refresh_cookie():
                        try:
                            return getattr(self.cookie, method)(*args, **kwargs)
                        except TransportError:
                            pass
                    # Degrade to WebBridge
                    # 降级
                    self._use_bridge = True
                else:
                    raise
        return getattr(self.bridge, method)(*args, **kwargs)

    def get_json(self, url: str, timeout: int = 60) -> Any:
        return self._run("get_json", url, timeout)

    def post_json(self, url: str, payload: dict, timeout: int = 60) -> Any:
        return self._run("post_json", url, payload, timeout)

    def download(self, url: str, timeout: int = 120) -> bytes:
        return self._run("download", url, timeout)
