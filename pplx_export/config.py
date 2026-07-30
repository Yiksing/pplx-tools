"""Centralized configuration: site constants and default paths (single source of truth)
plus user-level account/space configuration loading (externalized).

Site constants and default paths live only in this file; every module imports them
from here instead of hard-coding its own copies.

The account registry (display names / email / user_id) and the BOT space are personal
privacy data and are NOT committed to the repository; they live in an external
user-level TOML config file, loaded with this precedence:
  1. CLI `--config PATH`
  2. Environment variable `PPLX_EXPORT_CONFIG`
  3. Default `~/.config/pplx-export/config.toml`
See `config.example.toml` in the repository for a template (placeholders). When the
config file is missing, the module-level registries stay empty: commands that do not
explicitly pass an account run in degraded mode (email validation is skipped with a
warning); an explicit `--account` gets a clear error pointing at the example file from
commands/common.resolve_cli_account.

Note: the three ACCOUNT_* tables are mutable dicts updated IN PLACE (a binding created
by `from ..config import ACCOUNT_EMAIL` stays valid after configure() reloads);
BOT_SPACE_UUID / BOT_SPACE_SLUG / DEFAULT_ACCOUNT are strings, which are REBOUND on
reload — consumers must use `from .. import config` and read attributes.

集中配置：站点常量、默认路径（单一来源）+ 用户级账户/空间配置加载（外置）。

站点常量与默认路径以本文件为唯一来源，各模块一律 import，不再各自硬编码。

账户注册表（显示名/email/user_id）与 BOT 空间属**个人隐私，不入库**，
外置到用户级 TOML 配置，加载优先级：
  1. CLI `--config PATH`
  2. 环境变量 `PPLX_EXPORT_CONFIG`
  3. 默认 `~/.config/pplx-export/config.toml`
模板见仓库内 `config.example.toml`（占位符）。配置文件缺失时模块级注册表为空：
未显式指定账户的命令降级运行（email 校验跳过并 warning）；显式 `--account`
由 commands/common.resolve_cli_account 给出指向 example 的清晰报错。

注意：ACCOUNT_* 三张表为**就地更新**的可变 dict（`from ..config import ACCOUNT_EMAIL`
的绑定在 configure() 重载后仍有效）；BOT_SPACE_UUID/BOT_SPACE_SLUG/DEFAULT_ACCOUNT
是字符串，重载会重新绑定——使用方一律 `from .. import config` 后取属性。
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

# ── Site (Perplexity) ─────────────────────────────────────
# ── 站点（Perplexity）─────────────────────────────────────
PPLX_DOMAIN = "perplexity.ai"
PPLX_DOMAINS = ("perplexity.ai", ".perplexity.ai", "www.perplexity.ai")
SESSION_URL = "https://www.perplexity.ai/api/auth/session"

# ── Default paths ─────────────────────────────────────────
# Default archive root (relative to CWD; overridable via --out)
# ── 默认路径 ─────────────────────────────────────────────
# 默认归档根（相对 CWD；--out 可覆盖）
DEFAULT_ARCHIVE_ROOT = Path("web_archive")

# ── User-level config directory ──────────────────────────
# 用户级配置目录
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "pplx-export"

# ── User-level config (account registry + BOT space; externalized, not committed) ──
# ── 用户级配置（账户注册表 + BOT 空间；外置，不入库）────────
ENV_CONFIG_VAR = "PPLX_EXPORT_CONFIG"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.toml"
MODELS_CACHE_PATH = DEFAULT_CONFIG_DIR / "models_cache.json"

# Account username -> full display name (used for archive directory naming;
# falls back to the username itself when not registered)
# 账户用户名 → 完整显示名（用于归档目录命名；未收录时回退用户名本身）
ACCOUNT_DISPLAY_NAMES: dict[str, str] = {}
# Login email per account: used to verify cookie ownership, preventing
# "account B's export carrying account A's session"
# 各账户的登录 email：用于校验 cookie 归属，防止「账户 B 的导出带着账户 A 的会话」
ACCOUNT_EMAIL: dict[str, str] = {}
# Account uid (required by the thread-viewed telemetry)
# 账户 uid（thread viewed 遥测需要）
ACCOUNT_UID: dict[str, str] = {}
# BOT space (the collection point for threads created by pplx-ask)
# BOT 空间（pplx-ask 完成后线程的集中收纳处）
BOT_SPACE_UUID = ""
BOT_SPACE_SLUG = ""
# Default account from the config (used when --account is not given; empty = degraded)
# 配置中的默认账户（--account 未给时取用；空则降级）
DEFAULT_ACCOUNT = ""
# Optional user-configured archive root (top-level `archive_root` in the TOML).
# Serves as the --out fallback: precedence is --out > config archive_root > DEFAULT_ARCHIVE_ROOT.
# None when unset. Rebound on configure() reload (read via `from .. import config`).
# 可选的用户配置归档根（TOML 顶层 `archive_root`）。作为 --out 的回退：
# 优先级 --out > 配置 archive_root > DEFAULT_ARCHIVE_ROOT。未设为 None。configure() 重载会重新绑定。
ARCHIVE_ROOT: Path | None = None
# Path of the config file actually loaded (None = not loaded, degraded mode)
# 实际加载的配置文件路径（None=未加载，降级模式）
LOADED_CONFIG_PATH: Path | None = None
# Refreshable model catalog loaded from the [models] table (auto-managed by
# `pplx-ask models --refresh` / init — not hand-authored). Empty when absent;
# overrides the pinned fallback in sites/perplexity/platform.py. Updated IN PLACE
# on reload (a `from ..config import MODEL_CONFIG` binding stays valid).
# 从 [models] 表加载的可刷新模型目录（由 `pplx-ask models --refresh` / init 自动维护，
# 非手写）。缺失为空；覆盖 sites/perplexity/platform.py 的钉死兜底。重载就地更新
# （`from ..config import MODEL_CONFIG` 绑定不失效）。
MODEL_CONFIG: dict = {}
# Timestamp of the last successful export (top-level `last_export` in the TOML;
# ISO 8601 UTC). Empty when never exported. Rebound on configure() reload.
# 上次成功导出的时间戳（TOML 顶层 `last_export`，ISO 8601 UTC）。未导出时为空。
# configure() 重载会重新绑定。
LAST_EXPORT = ""


class ConfigError(Exception):
    """An explicitly specified user-level config is missing / unreadable / unparseable.

    用户级配置显式指定但缺失/不可读/解析失败。
    """


def _candidate_path(cli_path: str | os.PathLike | None) -> tuple[Path, bool]:
    """Resolve the candidate config path by precedence; returns (path, is_explicit).

    Explicit means the --config argument or the PPLX_EXPORT_CONFIG environment
    variable; the default path does not count as explicit.

    按优先级解析候选配置路径，返回 (路径, 是否显式指定)。

    显式 = --config 参数或 PPLX_EXPORT_CONFIG 环境变量；默认路径不算显式。
    """
    if cli_path:
        return Path(cli_path).expanduser(), True
    env = os.environ.get(ENV_CONFIG_VAR)
    if env:
        return Path(env).expanduser(), True
    return DEFAULT_CONFIG_PATH, False


def configure(cli_path: str | os.PathLike | None = None,
              *, strict_explicit: bool = True) -> Path | None:
    """(Re)load the user-level config into the module-level registries (dicts are
    updated in place; idempotent).

    Returns the config path actually loaded; None when nothing was loaded.
    - Default path missing: normal degradation (empty registries), returns None, no error;
    - Explicitly specified (--config / env var) but missing: raises ConfigError when
      strict_explicit is set;
    - File exists but fails to parse: always raises ConfigError (a corrupt config must
      not silently degrade).

    （重）加载用户级配置到模块级注册表（dict 就地更新，幂等）。

    返回实际加载的配置路径；未加载返回 None。
    - 默认路径缺失：正常降级（空注册表），返回 None，不抛错；
    - 显式指定（--config/环境变量）但文件缺失：strict_explicit 时抛 ConfigError；
    - 文件存在但解析失败：一律抛 ConfigError（配置损坏不应静默降级）。
    """
    global BOT_SPACE_UUID, BOT_SPACE_SLUG, DEFAULT_ACCOUNT, ARCHIVE_ROOT, LOADED_CONFIG_PATH, LAST_EXPORT
    ACCOUNT_DISPLAY_NAMES.clear()
    ACCOUNT_EMAIL.clear()
    ACCOUNT_UID.clear()
    MODEL_CONFIG.clear()
    BOT_SPACE_UUID = BOT_SPACE_SLUG = DEFAULT_ACCOUNT = LAST_EXPORT = ""
    ARCHIVE_ROOT = None
    LOADED_CONFIG_PATH = None

    path, explicit = _candidate_path(cli_path)
    if not path.is_file():
        if explicit and strict_explicit:
            raise ConfigError(
                f"显式指定的配置文件不存在: {path}\n"
                f"  请参照仓库内 config.example.toml 创建该文件，"
                f"或不指定 --config/{ENV_CONFIG_VAR} 使用默认路径 {DEFAULT_CONFIG_PATH}。")
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ConfigError(f"配置文件解析失败: {path}: {e}") from e

    accounts = data.get("accounts") or {}
    if not isinstance(accounts, dict):
        raise ConfigError(f"配置文件 [accounts] 必须是表: {path}")
    for name, tbl in accounts.items():
        if not isinstance(tbl, dict):
            continue
        if tbl.get("display_name"):
            ACCOUNT_DISPLAY_NAMES[str(name)] = str(tbl["display_name"])
        if tbl.get("email"):
            ACCOUNT_EMAIL[str(name)] = str(tbl["email"])
        if tbl.get("user_id"):
            ACCOUNT_UID[str(name)] = str(tbl["user_id"])
    bot = data.get("bot_space") or {}
    if not isinstance(bot, dict):
        raise ConfigError(f"配置文件 [bot_space] 必须是表: {path}")
    BOT_SPACE_UUID = str(bot.get("uuid") or "")
    BOT_SPACE_SLUG = str(bot.get("slug") or "")
    DEFAULT_ACCOUNT = str(data.get("default_account") or "")
    ar = data.get("archive_root")
    if ar:
        ARCHIVE_ROOT = Path(str(ar)).expanduser()
    le = data.get("last_export")
    if le:
        LAST_EXPORT = str(le)
    models_tbl = data.get("models")
    if isinstance(models_tbl, dict):
        MODEL_CONFIG.update(models_tbl)
    # Load model cache from models_cache.json (new format), or fall back to
    # legacy [models] data already loaded above.
    # 从 models_cache.json 加载模型缓存（新格式），若缺失则回退到上方已加载的
    # 旧格式 [models] 数据。
    _load_models_cache()
    LOADED_CONFIG_PATH = path
    return path


def _load_models_cache() -> None:
    """Load frontend-visible model data from models_cache.json into MODEL_CONFIG.

    Only extracts: default_models, council_defaults (from
    agentic_research_compare_models), search_config, computer_config.
    The ``models`` (raw 113-model catalog) field stays on disk only.

    When models_cache.json is absent, fall back to legacy config.toml [models]
    keys (mode_defaults → default_models, council_defaults, catalog) that were
    already loaded above.

    从 models_cache.json 加载前端可见的模型数据到 MODEL_CONFIG。

    仅提取：default_models、council_defaults（来自
    agentic_research_compare_models）、search_config、computer_config。
    ``models``（原始 113 模型目录）字段仅保留在磁盘上。

    当 models_cache.json 缺失时，回退到上方已加载的旧格式 config.toml [models]
    键（mode_defaults → default_models、council_defaults、catalog）。
    """
    import json as _json

    if not MODELS_CACHE_PATH.is_file():
        # Fallback: migrate old-style MODEL_CONFIG keys to new field names
        # 回退：将旧版 MODEL_CONFIG 键迁移到新字段名
        if "mode_defaults" in MODEL_CONFIG:
            # Old format: mode_defaults uses CLI names; convert back to API names
            # 旧格式：mode_defaults 使用 CLI 名称；转换回 API 名称
            defaults = {}
            for api_mode, cli_mode in _API_MODE_TO_CLI_LEGACY.items():
                mid = MODEL_CONFIG["mode_defaults"].get(cli_mode) or MODEL_CONFIG["mode_defaults"].get(api_mode)
                if mid:
                    defaults[api_mode] = mid
            if defaults:
                MODEL_CONFIG.setdefault("default_models", {}).update(defaults)
        return

    try:
        raw = _json.loads(MODELS_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, _json.JSONDecodeError):
        return

    defaults = raw.get("default_models")
    if isinstance(defaults, dict):
        MODEL_CONFIG.setdefault("default_models", {}).update(defaults)
    council = raw.get("agentic_research_compare_models")
    if isinstance(council, list) and council:
        if "council_defaults" not in MODEL_CONFIG or not MODEL_CONFIG["council_defaults"]:
            MODEL_CONFIG["council_defaults"] = council
    sc = raw.get("search_config")
    if isinstance(sc, list) and sc:
        MODEL_CONFIG["search_config"] = sc
    cc = raw.get("computer_config")
    if isinstance(cc, list) and cc:
        MODEL_CONFIG["computer_config"] = cc


# Reverse mapping: CLI mode name → API mode name, for legacy fallback.
# 反向映射：CLI 模式名 → API 模式名，用于旧版回退。
_API_MODE_TO_CLI_LEGACY = {
    "search": "search", "pro": "search", "research": "deep-research",
    "deep research": "deep-research", "agentic_research": "council",
    "study": "study", "studio": "study",
}


def write_models_cache(raw: dict) -> None:
    """Atomically write the raw models/config/v2 response to models_cache.json (0600).

    原子写入 models_cache.json（0600），并存原始 models/config/v2 响应。
    """
    import json as _json
    import tempfile

    MODELS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(MODELS_CACHE_PATH.parent),
                                prefix=".models_cache-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            _json.dump(raw, f, ensure_ascii=False, separators=(",", ":"))
        os.chmod(tmp, 0o600)
        os.replace(tmp, MODELS_CACHE_PATH)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_last_export(config_path: str | os.PathLike, timestamp: str) -> None:
    """Replace/insert the top-level `last_export` key in config.toml, preserving all
    other tables, keys, and comments (tomlkit round-trip); atomic 0600 write.

    替换/插入 config.toml 的顶层 `last_export` 键，其余表/键/注释原样保留
    （tomlkit round-trip）；原子 0600 写入。
    """
    import tempfile

    import tomlkit

    path = Path(config_path)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    doc = tomlkit.parse(text)
    doc["last_export"] = timestamp
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".config-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_models_section(config_path: str | os.PathLike, models: dict) -> None:
    """Replace/insert the `[models]` table in an existing config.toml, preserving
    every other table, key, and comment (tomlkit round-trip); atomic 0600 write.

    Only the `[models]` table is machine-managed; the user's accounts/bot_space and
    hand-written comments are carried over verbatim. An absent file starts empty.

    替换/插入既有 config.toml 的 `[models]` 表，其余表/键/注释原样保留（tomlkit
    round-trip）；原子 0600 写入。仅 `[models]` 为机器托管；用户账户/BOT 空间/手写
    注释逐字沿用。文件不存在则从空起。
    """
    import tempfile

    import tomlkit

    path = Path(config_path)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    doc = tomlkit.parse(text)
    doc["models"] = models
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".config-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# Fault-tolerant load at import time (default path / env var; a missing file means
# empty registries in degraded mode, no error).
# The CLI reloads in strict mode per --config after parse_args.
# import 期容错加载（默认路径/环境变量；缺失即空注册表降级，不抛错）。
# CLI 在 parse_args 后会以 strict 模式按 --config 重新加载。
configure(strict_explicit=False)
