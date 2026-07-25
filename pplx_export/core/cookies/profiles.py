"""Browser cookie-store profiles: where each browser keeps its cookie database
across install methods (native / snap / flatpak).

The registry is the single place to extend when adding a browser or an install
method — loader code needs no changes. Native paths are intentionally absent:
browser_cookie3 already covers them; only sandbox (snap/flatpak) increments
live here.

浏览器 cookie 库档案：各浏览器在不同安装方式（原生/snap/flatpak）下的 cookie 数据库位置。

新增浏览器或安装方式只需改本注册表，loader 代码零改动。原生路径刻意不列：
browser_cookie3 已覆盖；此处仅收录沙箱（snap/flatpak）增量。
"""

from __future__ import annotations

import glob
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class BrowserProfile:
    """Cookie-DB locations of one browser beyond the native install path.

    单个浏览器在原生安装路径之外的 cookie 数据库位置。
    """

    name: str
    # (install_method, glob) pairs, probed in order after the native path
    # （安装方式, glob）对，原生路径之后按序探测
    sandbox_globs: tuple[tuple[str, str], ...] = field(default_factory=tuple)


PROFILE_REGISTRY: dict[str, BrowserProfile] = {
    "chrome": BrowserProfile("chrome", (
        ("snap", "~/snap/chromium/current/.config/chromium/*/Cookies"),
        ("flatpak", "~/.var/app/com.google.Chrome/config/google-chrome/*/Cookies"),
    )),
    "chromium": BrowserProfile("chromium", (
        ("snap", "~/snap/chromium/current/.config/chromium/*/Cookies"),
        ("flatpak", "~/.var/app/org.chromium.Chromium/config/chromium/*/Cookies"),
    )),
    "edge": BrowserProfile("edge", (
        ("flatpak", "~/.var/app/com.microsoft.Edge/config/microsoft-edge/*/Cookies"),
    )),
    "brave": BrowserProfile("brave", (
        ("snap", "~/snap/brave/current/.config/BraveSoftware/Brave-Browser/*/Cookies"),
        ("flatpak", "~/.var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser/*/Cookies"),
    )),
    "opera": BrowserProfile("opera", (
        ("flatpak", "~/.var/app/com.opera.Opera/config/opera/*/Cookies"),
    )),
    "vivaldi": BrowserProfile("vivaldi", (
        ("snap", "~/snap/vivaldi/current/.config/vivaldi/*/Cookies"),
        ("flatpak", "~/.var/app/com.vivaldi.Vivaldi/config/vivaldi/*/Cookies"),
    )),
    "firefox": BrowserProfile("firefox", (
        ("snap", "~/snap/firefox/common/.mozilla/firefox/*.default*/cookies.sqlite"),
        ("flatpak", "~/.var/app/org.mozilla.firefox/.mozilla/firefox/*.default*/cookies.sqlite"),
    )),
    # safari: macOS only, no Linux sandbox variants
    # safari：仅 macOS，无 Linux 沙箱变体
    "safari": BrowserProfile("safari"),
}


def candidate_cookie_files(name: str, home: Path | None = None) -> list[tuple[str, Path]]:
    """Existing sandbox cookie-DB files for the browser, in registry order.

    Linux-only in production (snap/flatpak exist nowhere else); `home` is
    injectable so tests can point at a fake HOME on any platform.

    该浏览器现存于沙箱路径的 cookie 数据库文件，按注册表顺序。

    生产环境仅 Linux 有意义（snap/flatpak 仅存在于 Linux）；
    `home` 可注入，便于测试在任意平台指向伪 HOME。
    """
    if home is None and not sys.platform.startswith("linux"):
        return []
    profile = PROFILE_REGISTRY.get(name.lower())
    if profile is None:
        return []
    out: list[tuple[str, Path]] = []
    for method, pattern in profile.sandbox_globs:
        if home is not None:
            pattern = str(home) + pattern[pattern.index("~/") + 1:]
        for hit in sorted(glob.glob(os.path.expanduser(pattern))):
            p = Path(hit)
            if p.is_file():
                out.append((method, p))
    return out
