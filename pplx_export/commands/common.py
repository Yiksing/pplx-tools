"""Shared layer for commands: account mapping, transport factory, and startup helpers
common to both CLI entries.

cli.py and ask_cli.py share this module to avoid duplicating the same startup code in
two entries. Site constants live in pplx_export.config (single source of truth); the
account registry / BOT space are externalized user-level configuration (loaded via
config.configure) — this module only wires things together.

commands 公共层：账户映射、transport 工厂、双入口共享的启动辅助。

cli.py 与 ask_cli.py 共用本模块，避免双入口重复同一套启动代码。
站点常量集中在 pplx_export.config（单一来源）；账户注册表/BOT 空间为
用户级外置配置（config.configure 加载），本模块只做装配。
"""

from __future__ import annotations

import time
from pathlib import Path

from .. import config
from ..config import DEFAULT_ARCHIVE_ROOT, SESSION_URL
from ..core import cookies as ck
from ..core.http.bridge_transport import WebBridgeTransport
from ..core.http.cookie_transport import CookieTransport
from ..core.logging import get_logger
from ..core.models import Account

log = get_logger("cli")


def _account(username: str) -> Account:
    """Lenient assembly: build an Account from the username alone (display name looked
    up in the registry, falling back to the username itself when unregistered).

    For internal paths (sync-deleted's export_via, assets-backfill's directory names,
    etc. — those usernames come from archived data rather than the CLI, so no
    registration validation is applied). CLI --account parsing and validation go
    through resolve_cli_account.

    宽松装配：仅按用户名建 Account（显示名查注册表，未收录回退用户名本身）。

    供内部路径使用（sync-deleted 的 export_via、assets-backfill 的目录名等，
    这些用户名来自归档数据而非 CLI，不做登记校验）。CLI --account 的解析与
    校验走 resolve_cli_account。
    """
    return Account(username=username,
                   display_name=config.ACCOUNT_DISPLAY_NAMES.get(username, ""))


def resolve_cli_account(account_arg: str | None) -> Account:
    """Resolve CLI --account: explicit value > config default_account > degraded
    placeholder account.

    - Explicitly given but the config file is missing / the account is not registered
      -> SystemExit pointing at config.example.toml;
    - Not given and config missing -> returns a degraded account (username='default');
      email validation is skipped with a warning in make_transport (day-to-day
      offline commands are unaffected).

    解析 CLI --account：显式值 > 配置 default_account > 降级占位账户。

    - 显式指定但配置文件缺失 / 账户未登记 → SystemExit，指向 config.example.toml；
    - 未指定且配置缺失 → 返回降级账户（username='default'），email 校验在
      make_transport 中跳过并 warning（日常离线命令不受影响）。
    """
    if account_arg:
        if config.LOADED_CONFIG_PATH is None:
            raise SystemExit(
                f"[config][ERROR] 显式指定 --account {account_arg}，但未找到用户级配置文件"
                f"（查找顺序：--config PATH > 环境变量 {config.ENV_CONFIG_VAR} > "
                f"默认 {config.DEFAULT_CONFIG_PATH}）。\n"
                f"  请参照仓库内 config.example.toml 创建配置并在 [accounts.{account_arg}] "
                f"中登记 email/user_id。")
        known = (set(config.ACCOUNT_EMAIL) | set(config.ACCOUNT_DISPLAY_NAMES)
                 | set(config.ACCOUNT_UID))
        if account_arg not in known:
            raise SystemExit(
                f"[config][ERROR] 账户 {account_arg} 未在配置文件 "
                f"{config.LOADED_CONFIG_PATH} 中登记。\n"
                f"  请参照 config.example.toml 添加 [accounts.{account_arg}] 表"
                f"（display_name/email/user_id）。")
        return _account(account_arg)
    if config.DEFAULT_ACCOUNT:
        return _account(config.DEFAULT_ACCOUNT)
    if config.LOADED_CONFIG_PATH is None:
        log.warning(f"[config] 未找到用户级配置文件（默认 {config.DEFAULT_CONFIG_PATH}），"
                    f"以降级模式运行：email 归属校验跳过。参照 config.example.toml "
                    f"创建配置即可启用账户校验与多账户切换")
    return _account("default")


def make_transport(account: Account, cookies_from=None, cookies_file=None, transport_mode="cookie",
                   throttle=None, out_root: Path | None = None):
    """Build the transport. Cookie-direct (browser/file) by default; WebBridge only
    when transport_mode=='webbridge'.

    throttle: optional shared Throttle (passed by batch, unifying backoff counting /
    pacing with the transport layer); CookieTransport creates its own default
    instance when None.
    out_root: archive root (the cookie cache lands at <out_root>/index/.cookies.json,
    following --out; falls back to the default archive root when None).

    构造 transport。默认 cookie 直连（browser/file），仅 transport_mode=='webbridge' 才走 WebBridge。

    throttle：可选共享 Throttle（batch 传入，与传输层统一退避计数/节奏）；
    None 时 CookieTransport 自建默认实例。
    out_root：归档根（cookie 缓存落 <out_root>/index/.cookies.json，跟随 --out；
    None 时回退默认归档根）。
    """
    cache = Path(out_root or DEFAULT_ARCHIVE_ROOT) / "index" / ".cookies.json"
    if transport_mode == "webbridge":
        if cookies_from or cookies_file:
            raise SystemExit(
                "[ERROR] --cookies/--cookies-from 与 --transport webbridge 互斥：webbridge 在"
                "用户浏览器页面上下文发请求（自动带浏览器 cookie），外部 cookie 不生效。请只选其一。")
        bridge = WebBridgeTransport()
        _validate_bridge_account(bridge, account)
        return bridge, "webbridge"
    cdict, source = ck.resolve(cookies_from=cookies_from, cookies_file=cookies_file,
                               cache_path=cache)
    # Verify the account (avoid "using account B's cookies as account A") and refresh the cache
    # 校验账户（避免「账户 B 当 A 用」），并刷新缓存
    cookie = CookieTransport(cdict, throttle=throttle)
    try:
        sess = cookie.get_json(SESSION_URL, timeout=20)
        email = ((sess or {}).get("user") or {}).get("email", "")
        log.info(f"[auth] cookie 来源 {source}，当前账户: {email or '(未知)'}")
        expected = config.ACCOUNT_EMAIL.get(account.username)
        if expected and email and email.lower() != expected.lower():
            # With multiple accounts logged in at once, no manual switch is needed:
            # enumerate the per-account session tokens in the browser and try each until one matches
            # 多账户同登时无需手动切换：枚举浏览器里的账户会话令牌，逐个试到匹配
            switched = _try_switch_account(cdict, expected)
            if switched:
                cdict, email = switched
                # Switching must not drop the shared backoff counters (F-02)
                # 切换不丢共享退避计数（F-02）
                cookie = CookieTransport(cdict, throttle=throttle)
                log.info(f"[auth] 已自动切换到目标账户: {email}")
            else:
                raise SystemExit(
                    f"[auth][ERROR] 当前 cookie 属于 {email}，与目标账户 {account.username}（{expected}）不符，"
                    f"且自动切换失败（浏览器中可能未登录该账户）。\n"
                    f"  请先在浏览器登录/切换该账户，再重试。")
        if not expected:
            log.warning(f"[auth] 账户 {account.username} 未在用户级配置登记 email"
                        f"（{config.LOADED_CONFIG_PATH or '配置缺失'}），"
                        f"无法校验 cookie 归属——请确认浏览器登录的是正确账户")
        ck.CookieCache(cache).save(cdict, source, email)
    except SystemExit:
        raise
    except Exception as e:
        log.warning(f"[auth] cookie 账户校验失败（cookie 可能已失效）: {e}")
    return cookie, source


def _validate_bridge_account(bridge: WebBridgeTransport, account: Account) -> None:
    """Account validation for the webbridge path: request /api/auth/session through
    the bridge and check whether the browser's current login email belongs to the
    target account (mirroring the cookie path's validation).

    When the bridge is unreachable, only log.warning and proceed — webbridge is the
    fallback path and must not fail hard.

    webbridge 通路账户校验：经 bridge 请求 /api/auth/session，核对浏览器当前
    登录 email 是否属于目标账户（对齐 cookie 通路的校验方式）。

    bridge 不可达时仅 log.warning 放行——webbridge 是备用通路，不硬失败。
    """
    expected = config.ACCOUNT_EMAIL.get(account.username)
    try:
        sess = bridge.get_json(SESSION_URL, timeout=20)
        email = ((sess or {}).get("user") or {}).get("email", "")
        log.info(f"[auth] webbridge 通路，浏览器当前账户: {email or '(未知)'}")
        if expected and email and email.lower() != expected.lower():
            raise SystemExit(
                f"[auth][ERROR] 浏览器当前账户为 {email}，与目标账户 {account.username}"
                f"（{expected}）不符。请先在浏览器切换/登录该账户，再重试。")
        if not expected:
            log.warning(f"[auth] 账户 {account.username} 未在用户级配置登记 email"
                        f"（{config.LOADED_CONFIG_PATH or '配置缺失'}），"
                        f"无法校验浏览器账户归属——请确认浏览器登录的是正确账户")
    except SystemExit:
        raise
    except Exception as e:
        log.warning(f"[auth] webbridge 账户校验失败（bridge 不可达？），跳过校验继续: {e}")


def _try_switch_account(cdict: dict, expected_email: str):
    """On email mismatch, try switching automatically: enumerate each account's
    session token in the browser, replace __Secure-next-auth.session-token one at a
    time and validate the session. Returns (new cdict, email) on success, None on
    failure.

    email 不匹配时尝试自动切换：枚举浏览器中各账户的会话令牌，逐个替换
    __Secure-next-auth.session-token 并验证 session。成功返回 (新 cdict, email)，失败 None。
    """
    try:
        tokens = ck.list_account_tokens()
    except Exception:
        return None
    for uid, (token, browser) in tokens.items():
        try:
            new = dict(cdict)
            new[ck.ACTIVE_SESSION_COOKIE] = token
            probe = CookieTransport(new)
            sess = probe.get_json(SESSION_URL, timeout=20)
            email = ((sess or {}).get("user") or {}).get("email", "")
            if email.lower() == expected_email.lower():
                log.info(f"[auth] 自动切换: 从 browser:{browser} 取得账户 {email} 的会话令牌")
                return new, email
        except Exception:
            continue
    return None


def resolve_log_file(log_file_arg, out_root: Path, cmd: str) -> Path | None:
    """--log-file handling: None = no file logging; AUTO / no value = automatic path;
    otherwise use the given path.

    --log-file 处理：None=不落盘；AUTO/无值=自动路径；否则用给定路径。
    """
    if log_file_arg is None:
        return None
    if log_file_arg == "AUTO":
        ts = time.strftime("%Y%m%d-%H%M%S")
        return Path(out_root) / "index" / "logs" / f"{cmd}-{ts}.log"
    return Path(log_file_arg)


def add_common_args(ap, *, with_site: bool = False, with_transport: bool = False):
    """Common arguments shared by both CLI entries (account / output / cookies /
    debug / logging; pplx-export additionally gets site and transport).

    Help text takes the most complete version across both entries; argument names and
    defaults are identical in all places, eliminating drift.

    双入口共享的通用参数（账户/输出/cookie/调试/日志；pplx-export 另加站点与通路）。

    help 文案取双入口中最完整版本；参数名/默认值三处一致，消除漂移。
    """
    ap.add_argument("--account", default=None,
                    help="目标账户（默认取用户级配置的 default_account，配置缺失时降级运行）；"
                         "cookie 归属与登记 email 不符时自动枚举浏览器令牌切换")
    ap.add_argument("--config", default=None, metavar="PATH",
                    help="用户级配置文件（账户注册表/BOT 空间）；优先级：--config > 环境变量 "
                         "PPLX_EXPORT_CONFIG > 默认 ~/.config/pplx-export/config.toml")
    if with_site:
        ap.add_argument("--site", default="perplexity",
                        help="站点适配器（默认 perplexity）")
    ap.add_argument("--out", type=Path, default=DEFAULT_ARCHIVE_ROOT,
                    help="归档输出根目录（默认 ./web_archive）")
    ap.add_argument("--cookies-from", default=None, metavar="BROWSER",
                    help="从指定浏览器导入 cookie（edge/chrome/firefox/safari/brave…）")
    ap.add_argument("--cookies", default=None, metavar="FILE",
                    help="Netscape cookie 文件或 JSON cookie 文件")
    if with_transport:
        ap.add_argument("--transport", default="cookie", choices=["cookie", "webbridge"],
                        help="数据通路：默认 cookie 直连；仅明确指定 webbridge 才走页面上下文")
    ap.add_argument("-v", "--verbose", action="count", default=0,
                    help="调试输出：-v 显示请求追踪/内部判定等 DEBUG 细节（默认仅进度）")
    ap.add_argument("--log-file", nargs="?", const="AUTO", default=None, metavar="PATH",
                    help="全量日志落盘：不带值自动落 web_archive/index/logs/<cmd>-<时间戳>.log")
    return ap
