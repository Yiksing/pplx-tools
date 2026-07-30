"""Regression tests for the user-level external config (config externalization:
the account registry / BOT space are split out of config.py).

Covers:
  - load priority: --config PATH > env var PPLX_EXPORT_CONFIG > default path;
  - missing-file degradation: missing default path → degrade to an empty
    registry (no error); missing explicit path → ConfigError; broken config
    (TOML parse failure) → always ConfigError (never silently degraded);
  - config.example.toml parses and holds placeholders only (keeps real private
    data from flowing back into the repo);
  - resolve_cli_account: explicit --account + config missing/unregistered →
    SystemExit pointing at example; unspecified + config missing → degraded
    account 'default'; default_account takes effect;
  - configure() mutates dicts in place (`from config import ACCOUNT_EMAIL`
    bindings stay valid).

Fully offline: temp files + monkeypatch; no network, no real ~/.config reads.

用户级外置配置回归测试（配置外置：账户注册表/BOT 空间剥离出 config.py）。

覆盖：
  - 加载优先级：--config PATH > 环境变量 PPLX_EXPORT_CONFIG > 默认路径；
  - 缺失降级：默认路径缺失 → 空注册表降级（不抛错）；显式路径缺失 → ConfigError；
    配置损坏（TOML 解析失败）→ 一律 ConfigError（不静默降级）；
  - config.example.toml 可解析且为占位符（防真实隐私回流仓库）；
  - resolve_cli_account：显式 --account + 配置缺失/未登记 → SystemExit 指向 example；
    未指定 + 配置缺失 → 降级账户 'default'；default_account 生效；
  - configure() 就地更新 dict（`from config import ACCOUNT_EMAIL` 绑定不失效）。

全离线：临时文件 + monkeypatch，不触网、不读真实 ~/.config。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from pplx_export import config as cfg
from pplx_export.commands.common import resolve_cli_account

EXAMPLE = Path(__file__).parent.parent / "config.example.toml"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

TOML_A = """\
default_account = "alice"
[accounts.alice]
display_name = "Alice Example"
email = "alice@example.com"
user_id = "00000000-0000-4000-8000-0000000000aa"
[bot_space]
uuid = "00000000-0000-4000-8000-0000000000b0"
slug = "bot-EXAMPLE"
"""

TOML_B = """\
default_account = "bob"
[accounts.bob]
display_name = "Bob Example"
email = "bob@example.com"
user_id = "00000000-0000-4000-8000-0000000000bb"
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


class TestPriority:
    def test_cli_path_beats_env_and_default(self, tmp_path, monkeypatch):
        pa = _write(tmp_path, "a.toml", TOML_A)
        pb = _write(tmp_path, "b.toml", TOML_B)
        monkeypatch.setenv(cfg.ENV_CONFIG_VAR, str(pb))
        monkeypatch.setattr(cfg, "DEFAULT_CONFIG_PATH", tmp_path / "none.toml")
        assert cfg.configure(pa) == pa
        assert cfg.DEFAULT_ACCOUNT == "alice"
        assert cfg.ACCOUNT_EMAIL == {"alice": "alice@example.com"}

    def test_env_beats_default(self, tmp_path, monkeypatch):
        pb = _write(tmp_path, "b.toml", TOML_B)
        monkeypatch.setenv(cfg.ENV_CONFIG_VAR, str(pb))
        monkeypatch.setattr(cfg, "DEFAULT_CONFIG_PATH", tmp_path / "none.toml")
        assert cfg.configure() == pb
        assert cfg.DEFAULT_ACCOUNT == "bob"
        assert cfg.ACCOUNT_DISPLAY_NAMES == {"bob": "Bob Example"}

    def test_default_path_used_when_no_explicit(self, tmp_path, monkeypatch):
        pd = _write(tmp_path, "config.toml", TOML_A)
        monkeypatch.delenv(cfg.ENV_CONFIG_VAR, raising=False)
        monkeypatch.setattr(cfg, "DEFAULT_CONFIG_PATH", pd)
        assert cfg.configure() == pd
        assert cfg.ACCOUNT_UID == {"alice": "00000000-0000-4000-8000-0000000000aa"}
        assert cfg.BOT_SPACE_UUID == "00000000-0000-4000-8000-0000000000b0"
        assert cfg.BOT_SPACE_SLUG == "bot-EXAMPLE"


class TestMissingAndDegraded:
    def test_default_missing_degrades_silently(self, tmp_path, monkeypatch):
        monkeypatch.delenv(cfg.ENV_CONFIG_VAR, raising=False)
        monkeypatch.setattr(cfg, "DEFAULT_CONFIG_PATH", tmp_path / "none.toml")
        assert cfg.configure() is None
        assert cfg.LOADED_CONFIG_PATH is None
        assert cfg.ACCOUNT_EMAIL == {} and cfg.ACCOUNT_DISPLAY_NAMES == {}
        assert cfg.BOT_SPACE_UUID == "" and cfg.DEFAULT_ACCOUNT == ""

    def test_explicit_missing_raises(self, tmp_path):
        with pytest.raises(cfg.ConfigError, match="config.example.toml"):
            cfg.configure(tmp_path / "none.toml")

    def test_env_missing_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv(cfg.ENV_CONFIG_VAR, str(tmp_path / "none.toml"))
        with pytest.raises(cfg.ConfigError):
            cfg.configure()

    def test_broken_toml_always_raises(self, tmp_path, monkeypatch):
        bad = _write(tmp_path, "bad.toml", "not = [valid")
        monkeypatch.delenv(cfg.ENV_CONFIG_VAR, raising=False)
        monkeypatch.setattr(cfg, "DEFAULT_CONFIG_PATH", bad)
        with pytest.raises(cfg.ConfigError, match="解析失败"):
            cfg.configure()


class TestExampleFile:
    def test_example_parses_with_placeholders(self, monkeypatch, tmp_path):
        """The committed config.example.toml must parse and contain only
        shared placeholders (no real private data).

        仓库内 config.example.toml 必须可解析，且只含共享占位符（无真实隐私）。"""
        assert EXAMPLE.is_file(), "config.example.toml 缺失"
        text = EXAMPLE.read_text(encoding="utf-8")
        cfg.configure(EXAMPLE)
        assert cfg.DEFAULT_ACCOUNT == "alice"
        assert cfg.ACCOUNT_DISPLAY_NAMES == {"alice": "Alice Example",
                                             "bob": "Bob Example"}
        assert cfg.ACCOUNT_EMAIL == {"alice": "alice@example.com",
                                     "bob": "bob@example.com"}
        assert cfg.ACCOUNT_UID == {"alice": "00000000-0000-4000-8000-0000000000aa",
                                   "bob": "00000000-0000-4000-8000-0000000000bb"}
        assert cfg.BOT_SPACE_UUID == "00000000-0000-4000-8000-0000000000b0"
        assert cfg.BOT_SPACE_SLUG == "bot-EXAMPLE"
        # Real private data must never flow back into example (fragments are
        # concatenated so the literals themselves stay out of the repo)
        # 真实隐私不得回流 example（片段拼接，避免字面量本身入库）
        frags = [("iek", "seng"), ("chee", "nxs"), ("ic", "loud.com"), ("Iek", " Seng"),
                 ("5840", "2122"), ("5617", "d9d6"), ("5890", "541a"), ("WJB", "UGk")]
        for leaked in (a + b for a, b in frags):
            assert leaked not in text, f"example 含真实隐私: {leaked[:4]}…"


class TestResolveCliAccount:
    def test_explicit_account_with_config(self, tmp_path):
        cfg.configure(_write(tmp_path, "a.toml", TOML_A))
        acct = resolve_cli_account("alice")
        assert acct.username == "alice" and acct.folder == "Alice Example"

    def test_explicit_account_config_missing_errors(self, tmp_path, monkeypatch):
        monkeypatch.delenv(cfg.ENV_CONFIG_VAR, raising=False)
        monkeypatch.setattr(cfg, "DEFAULT_CONFIG_PATH", tmp_path / "none.toml")
        cfg.configure()
        with pytest.raises(SystemExit, match="config.example.toml"):
            resolve_cli_account("alice")

    def test_explicit_unknown_account_errors(self, tmp_path):
        cfg.configure(_write(tmp_path, "a.toml", TOML_A))
        with pytest.raises(SystemExit, match="未在配置文件"):
            resolve_cli_account("mallory")

    def test_default_account_from_config(self, tmp_path):
        cfg.configure(_write(tmp_path, "a.toml", TOML_A))
        acct = resolve_cli_account(None)
        assert acct.username == "alice"

    def test_no_config_degrades_to_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv(cfg.ENV_CONFIG_VAR, raising=False)
        monkeypatch.setattr(cfg, "DEFAULT_CONFIG_PATH", tmp_path / "none.toml")
        cfg.configure()
        acct = resolve_cli_account(None)
        assert acct.username == "default" and acct.folder == "default"


class TestInPlaceMutation:
    def test_dict_bindings_survive_reconfigure(self, tmp_path):
        """A `from ..config import ACCOUNT_EMAIL` reference still sees the new
        values after a reload (dicts are mutated in place, never rebound).

        `from ..config import ACCOUNT_EMAIL` 的引用在重载后仍看到新值
        （dict 就地更新，不重新绑定）。"""
        from pplx_export.config import ACCOUNT_EMAIL as bound
        cfg.configure(_write(tmp_path, "a.toml", TOML_A))
        assert bound.get("alice") == "alice@example.com"
        cfg.configure(_write(tmp_path, "b.toml", TOML_B))
        assert bound == {"bob": "bob@example.com"}


@pytest.mark.parametrize("external_config", ["missing", "broken"])
def test_pytest_collection_ignores_caller_config(
    tmp_path: Path,
    external_config: str,
) -> None:
    """Collection must not import the caller's config before fixtures run.

    测试收集必须在 fixture 运行前隔离调用方配置。"""
    config_path = tmp_path / "caller-config.toml"
    if external_config == "broken":
        config_path.write_text("not = [valid", encoding="utf-8")
    environment = os.environ.copy()
    environment["PPLX_EXPORT_CONFIG"] = str(config_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


class TestArchiveRoot:
    """archive_root: optional --out fallback loaded into cfg.ARCHIVE_ROOT.

    archive_root：可选的 --out 回退，载入 cfg.ARCHIVE_ROOT。"""

    def test_absent_is_none(self, tmp_path):
        # TOML_A has no archive_root → ARCHIVE_ROOT stays None (falls back to ./web_archive)
        # TOML_A 无 archive_root → ARCHIVE_ROOT 为 None（回退 ./web_archive）
        cfg.configure(_write(tmp_path, "a.toml", TOML_A))
        assert cfg.ARCHIVE_ROOT is None

    def test_loaded_and_expanded(self, tmp_path):
        toml = 'archive_root = "~/pplx-archive/web_archive"\n' + TOML_A
        cfg.configure(_write(tmp_path, "ar.toml", toml))
        assert cfg.ARCHIVE_ROOT == (Path.home() / "pplx-archive" / "web_archive")

    def test_rebound_to_none_on_reload_without_key(self, tmp_path):
        cfg.configure(_write(tmp_path, "ar.toml", 'archive_root = "/data/wa"\n' + TOML_A))
        assert cfg.ARCHIVE_ROOT == Path("/data/wa")
        # Reload a config without the key → must rebind back to None (no stale leak)
        # 重载不含该键的配置 → 必须重新绑定回 None（不留残值）
        cfg.configure(_write(tmp_path, "b.toml", TOML_B))
        assert cfg.ARCHIVE_ROOT is None
