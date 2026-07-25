"""Browser-store loaders: bc3 glue, account-token enumeration, cookie-file
import, WebBridge extraction, and the resolve() priority chain.

Sandbox installs (snap/flatpak): browser_cookie3's built-in paths cover only
native installs, so after the native attempt fails or comes up empty, the
registry paths in `profiles.py` are probed with an explicit `cookie_file=`.

浏览器库加载：bc3 胶水、账户令牌枚举、cookie 文件导入、WebBridge 提取与 resolve() 优先级链。

沙箱安装（snap/flatpak）：browser_cookie3 内置路径只覆盖原生安装，
原生尝试失败或为空后，按 `profiles.py` 注册表以显式 `cookie_file=` 继续探测。
"""

from __future__ import annotations

import json
from pathlib import Path

from ...config import PPLX_DOMAIN
from ..errors import AuthError
from ..logging import get_logger
from .cache import CookieCache
from .profiles import candidate_cookie_files

log = get_logger("cookies")

_BROWSER_LOADERS = {
    "edge": "edge", "chrome": "chrome", "chromium": "chromium",
    "firefox": "firefox", "safari": "safari", "brave": "brave",
    "opera": "opera", "vivaldi": "vivaldi",
}
AUTO_DETECT_ORDER = ["edge", "chrome", "firefox", "safari"]


def _domain_match(cookie_domain: str, domain: str) -> bool:
    """Domain matching (F-11/N-04): suffix matching — substring matching would
    wrongly admit evilperplexity.ai / perplexity.ai.attacker.com; shared by all
    three import paths.

    域匹配（F-11/N-04）：后缀匹配——子字符串会把 evilperplexity.ai /
    perplexity.ai.attacker.com 误匹配进来；三处导入路径共用。"""
    d = (cookie_domain or "").lstrip(".")
    return d == domain or d.endswith("." + domain)


def _bc3_loader(name: str):
    import browser_cookie3
    return getattr(browser_cookie3, _BROWSER_LOADERS[name])


def from_browser(name: str, domain: str = PPLX_DOMAIN) -> dict[str, str]:
    """Import cookies for a domain from the named browser's cookie store.

    从指定浏览器的 cookie 库导入某域的 cookie。"""
    out: dict[str, str] = {}
    for cname, _cdom, value in from_browser_raw(name, domain):
        out[cname] = value
    if not out:
        raise AuthError(f"{name} 中无 {domain} 的 cookie（该浏览器可能未登录目标站点）")
    return out


def from_browser_raw(name: str, domain: str = PPLX_DOMAIN) -> list[tuple[str, str, str]]:
    """Keep all entries as (cookie name, domain, value) — multi-account session
    cookies share names across domains; flattening would lose them.

    Probe order: the bc3 built-in (native install) path first, then the sandbox
    (snap/flatpak) registry paths with an explicit cookie_file.

    按 (cookie名, 域名, 值) 保留全部条目——多账户会话 cookie 跨域同名，拍平会丢失。

    探测顺序：先 bc3 内置（原生安装）路径，失败或为空再按注册表以显式
    cookie_file 试沙箱（snap/flatpak）路径。
    """
    name = name.lower()
    if name not in _BROWSER_LOADERS:
        raise AuthError(f"不支持的浏览器: {name}（支持: {sorted(_BROWSER_LOADERS)}）")
    errors: list[Exception] = []

    def _try(kwargs: dict) -> list[tuple[str, str, str]]:
        try:
            cj = _bc3_loader(name)(domain_name=domain, **kwargs)
        except Exception as e:
            errors.append(e)
            return []
        return [(c.name, c.domain or "", c.value) for c in cj
                if _domain_match(c.domain or "", domain)]

    rows = _try({})
    if rows:
        return rows
    # Sandbox profiles (snap/flatpak): probed only when the native path failed or came up empty
    # 沙箱档案（snap/flatpak）：原生路径失败或为空才探测
    for _method, db in candidate_cookie_files(name):
        rows = _try({"cookie_file": str(db)})
        if rows:
            log.debug(f"cookie 来源: {name}（沙箱安装路径 {db}）")
            return rows
    raise AuthError(
        f"从 {name} 导入 cookie 失败（可能 keyring 未授权/未登录，或 snap/flatpak 沙箱不可达）"
        f"{f': {errors[-1]}' if errors else ''}")


ACCOUNT_SESSION_PREFIX = "__Secure-pplx.session."
ACTIVE_SESSION_COOKIE = "__Secure-next-auth.session-token"


def list_account_tokens(browsers: list[str] | None = None,
                        domain: str = PPLX_DOMAIN) -> dict[str, tuple[str, str]]:
    """Enumerate session tokens of all logged-in accounts in browsers:
    {user_id: (token, source browser)}.

    With multiple accounts signed in, each account has a
    `__Secure-pplx.session.<uid>` cookie; writing its value into
    `__Secure-next-auth.session-token` completes the switch (verified in practice).

    枚举浏览器中全部已登录账户的会话令牌：{user_id: (token, 来源浏览器)}。

    多账户同登时每个账户有一条 `__Secure-pplx.session.<uid>` cookie；
    把它的值写进 `__Secure-next-auth.session-token` 即完成切换（已实测验证）。
    """
    out: dict[str, tuple[str, str]] = {}
    for b in (browsers or AUTO_DETECT_ORDER):
        try:
            raw = from_browser_raw(b, domain)
        except AuthError:
            continue
        for n, d, v in raw:
            if n.startswith(ACCOUNT_SESSION_PREFIX):
                uid = n[len(ACCOUNT_SESSION_PREFIX):]
                # Prefer the entry on the same domain as API requests (the www. subdomain)
                # 与 API 请求同域（www. 子域）的那条优先
                if uid and (uid not in out or d == f"www.{PPLX_DOMAIN}"):
                    out[uid] = (v, b)
        if out:
            # The first browser containing account cookies suffices (multiple accounts share one store)
            # 第一个含账户 cookie 的浏览器即可（同库内多账户共享）
            break
    return out


def from_file(path: str | Path, domain: str = PPLX_DOMAIN) -> dict[str, str]:
    """Import from a Netscape cookie file or a JSON file.

    从 Netscape cookie 文件或 JSON 文件导入。"""
    p = Path(path).expanduser()
    if not p.exists():
        raise AuthError(f"cookie 文件不存在: {p}")
    text = p.read_text(errors="replace")
    if p.suffix == ".json" or text.lstrip().startswith(("{", "[")):
        data = json.loads(text)
        if isinstance(data, dict):
            # Tolerate the cache-file shape ({"fetched_at":…, "cookies": {…}}): take the inner cookie table
            # 兼容缓存文件形态（{"fetched_at":…, "cookies": {…}}）：取内层 cookie 表
            if isinstance(data.get("cookies"), dict):
                return data["cookies"]
            return data
        if isinstance(data, list):  # [{name,value,domain},...]
            # Domain suffix matching (N-04: closes the F-11 gap); entries missing name/value keys are skipped, no KeyError
            # 域后缀匹配（N-04：补 F-11 遗漏）；缺 name/value 键的条目跳过，不抛 KeyError
            return {c["name"]: c["value"] for c in data
                    if isinstance(c, dict) and c.get("name") is not None
                    and c.get("value") is not None
                    and _domain_match(c.get("domain") or "", domain)}
        raise AuthError(f"无法解析 JSON cookie 文件: {p}")
    # Netscape format: domain\tflag\tpath\tsecure\texpiry\tname\tvalue
    # Netscape 格式: domain\tflag\tpath\tsecure\texpiry\tname\tvalue
    out = {}
    for line in text.splitlines():
        if line.startswith("#HttpOnly_"):
            # The HttpOnly prefix is not a comment (nearly all session cookies carry it)
            # HttpOnly 前缀不是注释（会话 cookie 几乎都是它）
            line = line[len("#HttpOnly_"):]
        elif line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            if _domain_match(parts[0], domain):
                out[parts[5]] = parts[6].rstrip("\n")
    if not out:
        raise AuthError(f"cookie 文件 {p} 中无 {domain} 的记录")
    return out


def from_webbridge(domain: str = PPLX_DOMAIN) -> dict[str, str]:
    """Extract via the WebBridge page context (fallback channel).

    [Reserved] No current caller, not wired into the resolve() priority chain
    (F-09) — part of CredentialProvider's reserved degradation chain, kept for
    wiring when FallbackTransport is enabled.

    经 WebBridge 页面上下文提取（回退通道）。

    【预留】当前无调用方、未接入 resolve() 优先级链（F-09）——
    属 CredentialProvider 预留降级链的一部分，保留备 FallbackTransport 启用时接线。
    """
    from ..auth import CredentialProvider
    from ..http.bridge_transport import WebBridgeTransport
    cred = CredentialProvider(WebBridgeTransport())
    return cred.refresh()


def resolve(*, cookies_from: str | None = None, cookies_file: str | None = None,
            transport: str = "cookie", cache_path: str | Path | None = None) -> tuple[dict[str, str], str]:
    """Resolve cookies by priority, returning (cookies, source_label).

    Explicit cookies_from / cookies_file win; otherwise fresh cache first, then
    auto-detect browser stores.

    按优先级解析 cookie，返回 (cookies, source_label)。

    cookies_from / cookies_file 显式指定优先；否则先缓存后 auto-detect 浏览器库。
    """
    if cookies_from:
        log.debug(f"cookie 来源: browser:{cookies_from}")
        return from_browser(cookies_from), f"browser:{cookies_from}"
    if cookies_file:
        log.debug(f"cookie 来源: file:{cookies_file}")
        return from_file(cookies_file), f"file:{cookies_file}"
    if cache_path:
        cached = CookieCache(cache_path).load()
        if cached:
            log.debug("cookie 来源: cache（12h 新鲜期内）")
            return cached, "cache"
    last_err: Exception | None = None
    for name in AUTO_DETECT_ORDER:
        try:
            log.debug(f"cookie auto-detect 尝试: {name}")
            return from_browser(name), f"browser:{name}"
        except Exception as e:
            last_err = e
    raise AuthError(
        f"无法自动获取 {PPLX_DOMAIN} 的 cookie：缓存失效且各浏览器库均不可用。"
        f"请用 --cookies-from <browser> 指定浏览器，或 --cookies <file> 提供文件。"
        f"（最后错误: {last_err}）")
