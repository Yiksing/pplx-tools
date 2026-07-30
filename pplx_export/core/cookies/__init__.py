"""Cookie sourcing package: unified retrieval of target-site session cookies
from browser cookie stores / files / WebBridge.

Layout (maintenance guide):
  `profiles.py`  browser × install-method path registry (snap/flatpak) — add a
                 browser or an install method HERE, no loader changes needed;
  `loaders.py`   browser_cookie3 glue, account-token enumeration, cookie-file
                 import, resolve() priority chain;
  `cache.py`     the 12h freshness-validated cookie cache.
Credential abstraction (OAuth / token / …) lives one level up in `core/auth.py`.

cookie 来源包：从浏览器 cookie 库 / 文件 / WebBridge 统一获取目标站点会话 cookie。

布局（维护指引）：
  `profiles.py`  浏览器 × 安装方式路径注册表（snap/flatpak）——新增浏览器或
                 安装方式只改这里，loader 零改动；
  `loaders.py`   browser_cookie3 胶水、账户令牌枚举、cookie 文件导入、
                 resolve() 优先级链；
  `cache.py`     12h 新鲜期校验的 cookie 缓存。
认证抽象（OAuth / token / …）在上一层 `core/auth.py`。

Priority (see cli.py arguments):
  --cookies-from <browser>  import from the named browser store (edge/chrome/firefox/safari/brave…)
  --cookies <file>          Netscape cookie file or exported JSON
  --transport webbridge     WebBridge page context, only when explicitly requested
  default                   fresh cache first → auto-detect browser stores (edge→chrome→firefox→safari)

优先级（见 cli.py 参数）：
  --cookies-from <browser>  从指定浏览器库导入（edge/chrome/firefox/safari/brave…）
  --cookies <file>          Netscape cookie 文件或导出的 JSON
  --transport webbridge     明确指定才用 WebBridge 页面上下文
  默认                       先用新鲜缓存 → auto-detect 浏览器库（edge→chrome→firefox→safari）

Note for tests: monkeypatching internals must target the submodule (e.g.
`pplx_export.core.cookies.loaders._bc3_loader`) — the names re-exported here
are aliases, patching them does not affect the submodule's own references.

测试注意：对内部实现打 monkeypatch 须指向子模块（如
`pplx_export.core.cookies.loaders._bc3_loader`）——此处再导出的名字是别名，
patch 别名不影响子模块内部引用。
"""

from .cache import CACHE_MAX_AGE_S, CookieCache
from .loaders import (ACCOUNT_SESSION_PREFIX, ACTIVE_SESSION_COOKIE,
                      AUTO_DETECT_ORDER, _bc3_loader as _bc3_loader,
                      _domain_match as _domain_match,
                      from_browser, from_browser_raw, from_file,
                      from_webbridge, list_account_tokens, resolve)
from .profiles import (BrowserProfile, PROFILE_REGISTRY,
                       candidate_cookie_files)

__all__ = [
    "CACHE_MAX_AGE_S", "CookieCache",
    "ACCOUNT_SESSION_PREFIX", "ACTIVE_SESSION_COOKIE", "AUTO_DETECT_ORDER",
    "from_browser", "from_browser_raw", "from_file", "from_webbridge",
    "list_account_tokens", "resolve",
    "BrowserProfile", "PROFILE_REGISTRY", "candidate_cookie_files",
]
