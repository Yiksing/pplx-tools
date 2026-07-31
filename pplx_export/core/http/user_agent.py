"""Dynamic User-Agent construction: {running OS} x {cookie-source browser family} x {version}.

Single source of truth for the UA and Chromium client hints sent on cookie-direct
requests. Priority:
  1. An explicit `user_agent` override in the user-level config wins — sent verbatim,
     with no automatic client hints;
  2. Otherwise the UA is built dynamically: browser family from the cookie source
     label (`browser:<name>`), version probed from the locally installed browser
     (best-effort, short-timeout, never fatal) with a static per-family fallback,
     platform token from the running OS;
  3. `file:` / cache / unknown sources get a generic current-OS Chrome UA and no
     client hints.

动态 User-Agent 构建：{运行 OS} × {cookie 来源浏览器族} × {版本}。

cookie 直连请求的 UA 与 Chromium client hints 的单一来源。优先级：
  1. 用户级配置里的显式 `user_agent` 覆盖优先——原样发送，不自动附加 client hints；
  2. 否则动态构建：浏览器族取自 cookie 来源标签（`browser:<name>`），版本探测自本机
     已安装浏览器（best-effort、短超时、绝不致命），失败回退每族静态表，平台段取自
     运行 OS；
  3. `file:` / 缓存 / 未知来源使用当前 OS 的通用 Chrome UA，不发 client hints。
"""

from __future__ import annotations

import platform
import re
import subprocess
import sys

from ..logging import get_logger

log = get_logger("ua")

# (UA platform token, sec-ch-ua-platform value) per platform.system()
# 各 platform.system() 的（UA 平台段, sec-ch-ua-platform 值）
_PLATFORM_TOKENS = {
    "Darwin": ("Macintosh; Intel Mac OS X 10_15_7", "macOS"),
    "Windows": ("Windows NT 10.0; Win64; x64", "Windows"),
    "Linux": ("X11; Linux x86_64", "Linux"),
}
_DEFAULT_PLATFORM = _PLATFORM_TOKENS["Linux"]

# Firefox platform tokens differ: a dotted macOS version and no AppleWebKit segment
# Firefox 平台段不同：macOS 版本号带点号，且无 AppleWebKit 段
_FF_PLATFORM_TOKENS = {
    "Darwin": "Macintosh; Intel Mac OS X 10.15",
    "Windows": "Windows NT 10.0; Win64; x64",
    "Linux": "X11; Linux x86_64",
}

# Per-family spec: whether it is Chromium-based, the sec-ch-ua brand name, an optional
# UA suffix tag, and a static fallback version. The fallback versions age — bump them
# occasionally (they only apply when version detection fails).
# Brand strings and tags are approximations: e.g. Brave deliberately sends a plain
# Chrome UA, and Opera's OPR tag carries Opera's own version (we reuse the Chromium
# one) — both are low-risk deviations.
# 每族规格：是否 Chromium 系、sec-ch-ua 品牌名、可选 UA 后缀标签、静态回退版本。
# 回退版本会老化——偶尔更新（仅在版本探测失败时生效）。品牌串与标签为近似值：
# 如 Brave 刻意发纯 Chrome UA，Opera 的 OPR 标签带 Opera 自身版本（此处复用
# Chromium 版本）——均为低风险偏差。
_BROWSER_SPECS = {
    "chrome": {"chromium": True, "brand": "Google Chrome", "fallback": "126.0.0.0"},
    "chromium": {"chromium": True, "brand": "Chromium", "fallback": "126.0.0.0"},
    "edge": {"chromium": True, "brand": "Microsoft Edge", "tag": "Edg/{v}",
             "fallback": "126.0.0.0"},
    "brave": {"chromium": True, "brand": "Brave", "fallback": "126.0.0.0"},
    "opera": {"chromium": True, "brand": "Opera", "tag": "OPR/{v}",
              "fallback": "126.0.0.0"},
    "vivaldi": {"chromium": True, "brand": "Vivaldi", "tag": "Vivaldi/{v}",
                "fallback": "126.0.0.0"},
    "firefox": {"chromium": False, "fallback": "127.0"},
    "safari": {"chromium": False, "fallback": "17.5"},
}

# Version-detection tables: family -> fixed app paths / binary names owned by this
# module. Detection NEVER executes a user-controlled string: the family only selects
# an entry from these whitelists, and subprocess calls use list argv (no shell).
# 版本探测表：族 -> 本模块自有的固定应用路径 / 二进制名。探测绝不执行用户可控
# 字符串：family 仅用于从这些白名单中选取条目，subprocess 一律 list 传参（无 shell）。
_MAC_APP_PATHS = {
    "chrome": "/Applications/Google Chrome.app",
    "chromium": "/Applications/Chromium.app",
    "edge": "/Applications/Microsoft Edge.app",
    "brave": "/Applications/Brave Browser.app",
    "opera": "/Applications/Opera.app",
    "vivaldi": "/Applications/Vivaldi.app",
    "firefox": "/Applications/Firefox.app",
    "safari": "/Applications/Safari.app",
}
_LINUX_BINS = {
    "chrome": ("google-chrome", "google-chrome-stable"),
    "chromium": ("chromium", "chromium-browser"),
    "edge": ("microsoft-edge", "microsoft-edge-stable"),
    "brave": ("brave-browser", "brave"),
    "opera": ("opera",),
    "vivaldi": ("vivaldi", "vivaldi-stable"),
    "firefox": ("firefox",),
}
_WIN_EXES = {
    "chrome": (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
               r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    "chromium": (r"C:\Program Files\Chromium\Application\chrome.exe",),
    "edge": (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
             r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    "brave": (r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",),
    "opera": (r"C:\Program Files\Opera\opera.exe",),
    "vivaldi": (r"C:\Program Files\Vivaldi\Application\vivaldi.exe",),
    "firefox": (r"C:\Program Files\Mozilla Firefox\firefox.exe",),
}

_DETECT_TIMEOUT_S = 3
_VERSION_RE = re.compile(r"\d+(?:\.\d+)+")

# In-process per-family detection cache (None = detection already failed)
# 进程内按族探测缓存（None = 已探测且失败）
_version_cache: dict[str, str | None] = {}


def _platform_tokens() -> tuple[str, str]:
    return _PLATFORM_TOKENS.get(platform.system(), _DEFAULT_PLATFORM)


def _family_from_source(source: str) -> str | None:
    """Extract the browser family from a resolve() source label (`browser:<name>`).

    从 resolve() 来源标签（`browser:<name>`）提取浏览器族。"""
    if source.startswith("browser:"):
        family = source[len("browser:"):].strip().lower()
        if family in _BROWSER_SPECS:
            return family
    return None


def _detect_mac(family: str) -> str | None:
    """Read CFBundleShortVersionString from the app's Info.plist (no exec at all).

    读取应用 Info.plist 的 CFBundleShortVersionString（完全不执行进程）。"""
    import plistlib
    from pathlib import Path
    plist = Path(_MAC_APP_PATHS[family]) / "Contents" / "Info.plist"
    with plist.open("rb") as f:
        return str(plistlib.load(f).get("CFBundleShortVersionString") or "") or None


def _detect_linux(family: str) -> str | None:
    for binary in _LINUX_BINS[family]:
        try:
            out = subprocess.run([binary, "--version"], capture_output=True, text=True,
                                 timeout=_DETECT_TIMEOUT_S).stdout
        except Exception:
            continue
        m = _VERSION_RE.search(out or "")
        if m:
            return m.group(0)
    return None


def _detect_windows(family: str) -> str | None:
    import os
    for exe in _WIN_EXES[family]:
        if not os.path.isfile(exe):
            continue
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-Item '{exe}').VersionInfo.ProductVersion"],
                capture_output=True, text=True, timeout=_DETECT_TIMEOUT_S).stdout
        except Exception:
            continue
        m = _VERSION_RE.search(out or "")
        if m:
            return m.group(0)
    return None


def detect_browser_version(family: str) -> str | None:
    """Best-effort probe of the installed browser's version; None on any failure.

    Strictly short-timeout and fully exception-swallowing — detection must never
    block or break an export. Results are cached per family for the process.

    尽力探测本机已安装浏览器的版本；任何失败返回 None。

    严格短超时、异常全捕获——探测绝不阻断或破坏导出。结果按族缓存到进程结束。
    """
    family = family.lower()
    if family in _version_cache:
        return _version_cache[family]
    version: str | None = None
    try:
        if sys.platform == "darwin" and family in _MAC_APP_PATHS:
            version = _detect_mac(family)
        elif sys.platform.startswith("linux") and family in _LINUX_BINS:
            version = _detect_linux(family)
        elif sys.platform.startswith("win") and family in _WIN_EXES:
            version = _detect_windows(family)
    except Exception:
        version = None
    if version:
        log.debug(f"UA 版本探测: {family} → {version}")
    _version_cache[family] = version
    return version


def _config_override() -> str | None:
    """Explicit config `user_agent` override (lazy import: config must not load at module import).

    配置里的显式 `user_agent` 覆盖（lazy import：config 不得在模块导入期加载）。"""
    from ... import config
    ua = (getattr(config, "USER_AGENT", None) or "").strip()
    return ua or None


def _render(family: str, version: str) -> str:
    if family == "firefox":
        plat = _FF_PLATFORM_TOKENS.get(platform.system(), _FF_PLATFORM_TOKENS["Linux"])
        return f"Mozilla/5.0 ({plat}; rv:{version}) Gecko/20100101 Firefox/{version}"
    if family == "safari":
        # Safari is macOS-only; no AppleWebKit version drift tracking, pinned token
        # Safari 仅 macOS；不跟踪 AppleWebKit 版本漂移，平台段钉死
        return ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                f"(KHTML, like Gecko) Version/{version} Safari/605.1.15")
    plat, _ch = _platform_tokens()
    ua = (f"Mozilla/5.0 ({plat}) AppleWebKit/537.36 (KHTML, like Gecko) "
          f"Chrome/{version} Safari/537.36")
    tag = _BROWSER_SPECS[family].get("tag")
    if tag:
        ua += " " + tag.format(v=version)
    return ua


def build_ua(source: str = "") -> str:
    """User-Agent for a cookie source label; see the module docstring for priority.

    按 cookie 来源标签构建 User-Agent；优先级见模块 docstring。"""
    override = _config_override()
    if override:
        return override
    family = _family_from_source(source)
    if family:
        version = detect_browser_version(family) or _BROWSER_SPECS[family]["fallback"]
        return _render(family, version)
    # file: / cache / unknown sources: generic current-OS Chrome
    # file: / 缓存 / 未知来源：当前 OS 的通用 Chrome
    return _render("chrome", _BROWSER_SPECS["chrome"]["fallback"])


def build_client_hints(source: str = "") -> dict[str, str]:
    """Chromium client hints for a cookie source label; empty for non-Chromium
    families, file/unknown sources, and when a config UA override is in effect.

    按 cookie 来源标签构建 Chromium client hints；非 Chromium 族、file/未知来源、
    以及配置了 UA 覆盖时返回空 dict。"""
    if _config_override():
        return {}
    family = _family_from_source(source)
    if not family or not _BROWSER_SPECS[family]["chromium"]:
        return {}
    version = detect_browser_version(family) or _BROWSER_SPECS[family]["fallback"]
    major = version.split(".")[0]
    brand = _BROWSER_SPECS[family]["brand"]
    brands = f'"Not/A)Brand";v="8", "Chromium";v="{major}"'
    if brand != "Chromium":
        brands += f', "{brand}";v="{major}"'
    _plat, ch_platform = _platform_tokens()
    return {
        "sec-ch-ua": brands,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": f'"{ch_platform}"',
    }
