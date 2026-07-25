"""Heavyweight browser automation (Playwright/Selenium) interface reservation — not implemented this round.

For future enablement when a real browser driver is needed (e.g. browser cookie
store undecryptable, WebBridge unavailable, anti-scraping escalation).
Interface signatures aligned with core.cookies / core.http.transport; implementations marked TODO.

Enablement (future):
  1. Install: pip install playwright && playwright install chromium (or selenium + matching driver)
  2. Add --transport playwright|selenium options in cli.py
  3. Implement PlaywrightCookieSource / SeleniumCookieSource and the corresponding Transport

重量级浏览器自动化（Playwright/Selenium）接口预留 —— 本轮不实现。

供未来需要真实浏览器驱动（如 cookie 库无法解密、WebBridge 不可用、反爬升级）时启用。
接口签名与 core.cookies / core.http.transport 对齐，实现标注 TODO。

启用方式（未来）：
  1. 安装：pip install playwright && playwright install chromium（或 selenium + 对应 driver）
  2. 在 cli.py 增加 --transport playwright|selenium 选项
  3. 实现 PlaywrightCookieSource / SeleniumCookieSource 与对应 Transport
"""

from __future__ import annotations

from typing import Any

from ...config import PPLX_DOMAIN
from ..errors import AuthError
from .transport import Transport


class BrowserAutomationTransport(Transport):
    """Playwright/Selenium-driven Transport (not implemented, placeholder only).

    Playwright/Selenium 驱动的 Transport（未实现，仅占位）。"""

    name = "browser-automation"

    def __init__(self, engine: str = "playwright", headless: bool = True, profile: str | None = None):
        self.engine = engine
        self.headless = headless
        self.profile = profile
        raise NotImplementedError(
            "BrowserAutomationTransport 尚未实现。请使用 --cookies-from（浏览器库）"
            "或 --transport webbridge（页面上下文）。")

    def get_json(self, url: str, timeout: int = 60) -> Any:
        raise NotImplementedError

    def post_json(self, url: str, payload: dict, timeout: int = 60) -> Any:
        raise NotImplementedError

    def download(self, url: str, timeout: int = 120) -> bytes:
        raise NotImplementedError


class PlaywrightCookieSource:
    """Launch a real browser via Playwright to read cookies (not implemented, placeholder only).

    经 Playwright 启动真实浏览器读取 cookie（未实现，仅占位）。"""

    def get(self, domain: str = PPLX_DOMAIN) -> dict[str, str]:
        raise NotImplementedError("PlaywrightCookieSource 未实现（TODO）")


class SeleniumCookieSource:
    """Read cookies via Selenium WebDriver (not implemented, placeholder only).

    经 Selenium WebDriver 读取 cookie（未实现，仅占位）。"""

    def __init__(self, driver_path: str | None = None):
        self.driver_path = driver_path

    def get(self, domain: str = PPLX_DOMAIN) -> dict[str, str]:
        raise NotImplementedError("SeleniumCookieSource 未实现（TODO）")


def not_available(*_args, **_kwargs):
    raise AuthError(
        "浏览器自动化（Playwright/Selenium）接口已预留但未实现。"
        "请改用 --cookies-from <browser> 或 --transport webbridge。")
