"""Tests for cmd: init (auto-discover accounts and write the user-level config).

Offline: browser access, session probes and space listing are replaced by fakes;
the only real side effect is the config file under tmp_path.

cmd: init 的测试（自动发现账户并生成用户级配置）。

全离线：浏览器访问、会话探测与空间列表均以伪件替代；唯一真实副作用是
tmp_path 下的配置文件。
"""

import json
import os
import stat
import tomllib
from types import SimpleNamespace

import pytest

from pplx_export.core import cookies as ck
from pplx_export.commands import init_cmd
from pplx_export.commands.init_cmd import (_enumerate_tokens, _name_key,
                                           cmd_init, find_bot_space,
                                           render_config, write_config)


def _args(tmp_path, **kw):
    base = dict(config=None, out=tmp_path, cookies_from=None, cookies=None,
                transport="cookie", force=False, create_bot_space=False)
    base.update(kw)
    return SimpleNamespace(**base)


class _FakeTransport:
    """get_json stub: session responses keyed by the active session token;
    everything else returns the collections payload.

    get_json 伪件：按生效会话令牌返回对应会话响应；其余 URL 返回空间列表负载。
    """

    def __init__(self, cdict, sessions, collections):
        self._token = cdict.get(ck.ACTIVE_SESSION_COOKIE, "")
        self._sessions = sessions
        self._collections = collections

    def get_json(self, url, timeout=30):
        if "auth/session" in url:
            return self._sessions.get(self._token, {"user": {}})
        return self._collections


def _patch_common(monkeypatch, tokens, sessions, collections):
    """Patch cookie resolution, token enumeration and the transport factory.

    统一打补丁：cookie 解析、令牌枚举与 transport 工厂。
    """
    monkeypatch.setattr(ck, "resolve", lambda **kw: (
        {ck.ACTIVE_SESSION_COOKIE: "tok-a"}, "test"))
    monkeypatch.setattr(init_cmd, "_enumerate_tokens", lambda *a: tokens)
    factory = lambda cdict: _FakeTransport(cdict, sessions, collections)
    return factory


# ── Pure helpers ──
# ── 纯函数 ──

class TestNameKey:
    def test_sanitize_and_fallback(self):
        """Email local part is restricted to safe characters; empty email uses the uid prefix.

        email 本地部分被规范化；空 email 回退 uid 前缀。
        """
        taken = set()
        assert _name_key("Alice.Doe@example.com", "u1", taken) == "alice-doe"
        assert _name_key("", "12345678-abcd", taken) == "account-12345678"

    def test_collision_suffix(self):
        """Duplicate keys get -2/-3 suffixes.

        键撞名时加 -2/-3 后缀。
        """
        taken = set()
        assert _name_key("a@x.com", "u1", taken) == "a"
        assert _name_key("a@y.com", "u2", taken) == "a-2"
        assert _name_key("a@z.com", "u3", taken) == "a-3"


class TestFindBotSpace:
    def test_case_insensitive_match(self):
        """Title match is exact but case-insensitive.

        标题精确匹配但大小写不敏感。
        """
        items = [{"title": "notes", "uuid": "u0"},
                 {"title": " bot ", "uuid": "u1", "slug": "bot"}]
        assert find_bot_space(items) == ("u1", "bot")

    def test_no_match(self):
        """No matching title yields empty strings.

        无匹配标题返回空串。
        """
        assert find_bot_space([{"title": "other", "uuid": "u9"}]) == ("", "")


class TestRenderAndWrite:
    def test_render_escapes_and_shape(self, tmp_path):
        """Rendered TOML parses and escapes quotes/backslashes.

        渲染的 TOML 可解析且正确转义引号/反斜杠。
        """
        accounts = {"bob": {"display_name": 'B "Q"', "email": "b@x.com", "user_id": "u2"}}
        text = render_config(accounts, "bob", "uuid-1", "bot")
        cfg = tomllib.loads(text)
        assert cfg["default_account"] == "bob"
        assert cfg["accounts"]["bob"]["display_name"] == 'B "Q"'
        assert cfg["bot_space"]["uuid"] == "uuid-1"

    def test_write_0600_no_overwrite_force(self, tmp_path):
        """Write is atomic with 0600; overwrite refused without force, allowed with it.

        写入为 0600 原子写；不加 force 拒绝覆盖，加了才覆盖。
        """
        p = tmp_path / "sub" / "config.toml"
        write_config(p, "a = 1\n")
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
        with pytest.raises(SystemExit):
            write_config(p, "a = 2\n")
        write_config(p, "a = 2\n", force=True)
        assert p.read_text() == "a = 2\n"
        assert stat.S_IMODE(p.stat().st_mode) == 0o600


class TestEnumerateFromFile:
    def test_scans_account_session_cookies(self, tmp_path, monkeypatch):
        """A cookie file is scanned for __Secure-pplx.session.<uid> entries.

        cookie 文件被扫描出 __Secure-pplx.session.<uid> 条目。
        """
        monkeypatch.setattr(ck, "from_file", lambda p: {
            ck.ACCOUNT_SESSION_PREFIX + "uid-1": "t1",
            ck.ACCOUNT_SESSION_PREFIX + "uid-2": "t2",
            "other": "x"})
        tokens = _enumerate_tokens(None, "f.json")
        assert tokens == {"uid-1": ("t1", "file:f.json"), "uid-2": ("t2", "file:f.json")}


# ── cmd_init end to end ──
# ── cmd_init 端到端 ──

SESSIONS = {
    "tok-a": {"user": {"email": "alice@example.com", "name": "Alice Example"}},
    "tok-b": {"user": {"email": "bob@example.com", "name": "Bob Example"}},
}
TOKENS = {"uid-a": ("tok-a", "edge"), "uid-b": ("tok-b", "edge")}


def test_cmd_init_end_to_end(tmp_path, monkeypatch, capsys):
    """Two tokens -> two accounts; default follows the active session; BOT matched
    by title; config written with 0600 and the summary JSON printed.

    两个令牌 -> 两个账户；default 跟随当前会话；BOT 按标题匹配；
    配置以 0600 写入并打印摘要 JSON。
    """
    collections = {"collections": [{"title": "BOT", "uuid": "uuid-bot", "slug": "bot"}]}
    factory = _patch_common(monkeypatch, TOKENS, SESSIONS, collections)
    out = tmp_path / "init.toml"
    cmd_init(_args(tmp_path, config=str(out)), transport_factory=factory)
    cfg = tomllib.loads(out.read_text())
    assert sorted(cfg["accounts"]) == ["alice", "bob"]
    assert cfg["accounts"]["alice"] == {"display_name": "Alice Example",
                                        "email": "alice@example.com", "user_id": "uid-a"}
    assert cfg["default_account"] == "alice"
    assert cfg["bot_space"]["uuid"] == "uuid-bot"
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["default_account"] == "alice" and summary["bot_space_uuid"] == "uuid-bot"


def test_cmd_init_single_account_fallback(tmp_path, monkeypatch):
    """No enumerable tokens: probe the active session only; user_id stays empty.

    无可枚举令牌：仅探测当前会话；user_id 留空。
    """
    factory = _patch_common(monkeypatch, {}, SESSIONS, {"collections": []})
    out = tmp_path / "init.toml"
    cmd_init(_args(tmp_path, config=str(out)), transport_factory=factory)
    cfg = tomllib.loads(out.read_text())
    assert cfg["accounts"]["alice"]["user_id"] == ""
    assert cfg["default_account"] == "alice"
    assert cfg["bot_space"]["uuid"] == ""


def test_cmd_init_create_bot_space(tmp_path, monkeypatch):
    """--create-bot-space: no title match -> the creator runs once and the new
    uuid/slug land in the config.

    --create-bot-space：标题无匹配时创建一次，新 uuid/slug 落入配置。
    """
    factory = _patch_common(monkeypatch, TOKENS, SESSIONS, {"collections": []})
    calls = []

    def _create(transport, title):
        calls.append(title)
        return {"uuid": "uuid-new", "slug": "bot"}

    out = tmp_path / "init.toml"
    cmd_init(_args(tmp_path, config=str(out), create_bot_space=True),
             transport_factory=factory, create_space_fn=_create)
    assert calls == ["BOT"]
    assert tomllib.loads(out.read_text())["bot_space"]["uuid"] == "uuid-new"


def test_cmd_init_no_accounts(tmp_path, monkeypatch):
    """All probes failing -> SystemExit, no file written.

    全部探测失败 -> SystemExit，不写文件。
    """
    monkeypatch.setattr(ck, "resolve", lambda **kw: ({ck.ACTIVE_SESSION_COOKIE: "t"}, "test"))
    monkeypatch.setattr(init_cmd, "_enumerate_tokens", lambda *a: {})

    class _Dead:
        def get_json(self, url, timeout=30):
            raise RuntimeError("401")

    with pytest.raises(SystemExit):
        cmd_init(_args(tmp_path, config=str(tmp_path / "c.toml")),
                 transport_factory=lambda cdict: _Dead())
    assert not (tmp_path / "c.toml").exists()


def test_cmd_init_rejects_existing_without_force(tmp_path, monkeypatch):
    """An existing config is kept unless --force.

    已有配置不加 --force 时保留。
    """
    factory = _patch_common(monkeypatch, TOKENS, SESSIONS, {"collections": []})
    out = tmp_path / "init.toml"
    out.write_text("default_account = \"custom\"\n")
    with pytest.raises(SystemExit):
        cmd_init(_args(tmp_path, config=str(out)), transport_factory=factory)
    assert "custom" in out.read_text()
    cmd_init(_args(tmp_path, config=str(out), force=True), transport_factory=factory)
    assert tomllib.loads(out.read_text())["default_account"] == "alice"


def test_cmd_init_custom_bot_title(tmp_path, monkeypatch):
    """--bot-title matches a differently named space.

    --bot-title 可匹配不同命名的空间。
    """
    collections = {"collections": [{"title": "My Inbox", "uuid": "uuid-mb",
                                    "slug": "my-inbox"}]}
    factory = _patch_common(monkeypatch, TOKENS, SESSIONS, collections)
    out = tmp_path / "init.toml"
    cmd_init(_args(tmp_path, config=str(out), bot_title="My Inbox"),
             transport_factory=factory)
    assert tomllib.loads(out.read_text())["bot_space"]["uuid"] == "uuid-mb"


def test_cmd_init_create_bot_space_custom_title(tmp_path, monkeypatch):
    """--create-bot-space TITLE: creation uses the explicit title.

    --create-bot-space 标题：创建时使用显式标题。
    """
    factory = _patch_common(monkeypatch, TOKENS, SESSIONS, {"collections": []})
    calls = []

    def _create(transport, title):
        calls.append(title)
        return {"uuid": "uuid-x", "slug": "my-space"}

    out = tmp_path / "init.toml"
    cmd_init(_args(tmp_path, config=str(out), create_bot_space="My Space"),
             transport_factory=factory, create_space_fn=_create)
    assert calls == ["My Space"]
    assert tomllib.loads(out.read_text())["bot_space"]["uuid"] == "uuid-x"


def test_cmd_init_create_title_matches_existing(tmp_path, monkeypatch):
    """--create-bot-space TITLE drives matching too: an existing space with that
    title is matched, nothing is created.

    --create-bot-space 标题同样驱动匹配：已有同名空间则直接匹配，不再创建。
    """
    collections = {"collections": [{"title": "My Space", "uuid": "uuid-have",
                                    "slug": "my-space"}]}
    factory = _patch_common(monkeypatch, TOKENS, SESSIONS, collections)
    calls = []
    out = tmp_path / "init.toml"
    cmd_init(_args(tmp_path, config=str(out), create_bot_space="My Space"),
             transport_factory=factory,
             create_space_fn=lambda t, title: calls.append(title) or {})
    assert calls == []
    assert tomllib.loads(out.read_text())["bot_space"]["uuid"] == "uuid-have"
