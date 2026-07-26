"""Tests for the browser-profile registry and sandbox (snap/flatpak) probing.

Offline: bc3 loader and the filesystem HOME are faked throughout.

浏览器 profile 注册表与沙箱（snap/flatpak）探测的测试。

全离线：bc3 loader 与文件系统 HOME 均为伪件。
"""

from pathlib import Path

import pytest

from pplx_export.core.cookies import loaders, profiles
from pplx_export.core.errors import AuthError


class TestCandidateCookieFiles:
    def test_finds_snap_and_flatpak(self, tmp_path):
        """Registry globs resolve against a fake HOME, existing files only,
        in registry order.

        注册表 glob 对伪 HOME 解析，仅收现存文件，按注册表顺序。
        """
        snap = tmp_path / "snap/chromium/current/.config/chromium/Default"
        snap.mkdir(parents=True)
        (snap / "Cookies").write_text("x")
        fp = tmp_path / ".var/app/com.google.Chrome/config/google-chrome/Default"
        fp.mkdir(parents=True)
        (fp / "Cookies").write_text("x")
        out = profiles.candidate_cookie_files("chrome", home=tmp_path)
        assert [m for m, _ in out] == ["snap", "flatpak"]
        assert out[0][1] == snap / "Cookies"

    def test_unknown_browser_and_missing_files(self, tmp_path):
        """Unknown names yield nothing; globs with no hits are skipped.

        未知名字为空；无命中的 glob 跳过。
        """
        assert profiles.candidate_cookie_files("netscape", home=tmp_path) == []
        assert profiles.candidate_cookie_files("chrome", home=tmp_path) == []


class TestFromBrowserRawSandbox:
    def test_native_first_no_sandbox_probe(self, monkeypatch):
        """A non-empty native jar short-circuits — sandbox paths never probed.

        原生库非空即短路——不再探测沙箱路径。
        """
        class C:
            name, domain, value = "k", "perplexity.ai", "v"

        monkeypatch.setattr(loaders, "_bc3_loader",
                            lambda name: (lambda domain_name=None, **kw: [C()]))
        monkeypatch.setattr(loaders, "candidate_cookie_files",
                            lambda name: pytest.fail("不应探测沙箱"))
        assert loaders.from_browser_raw("chrome") == [("k", "perplexity.ai", "v")]

    def test_sandbox_fallback_with_cookie_file(self, monkeypatch):
        """Native failure falls through to the registry path via cookie_file=.

        原生失败后按注册表路径以 cookie_file= 继续探测。
        """
        calls = []

        class C:
            name, domain, value = "k", "perplexity.ai", "v"

        def fake_loader(name):
            def load(domain_name=None, **kw):
                calls.append(kw)
                if "cookie_file" not in kw:
                    raise RuntimeError("native path missing")
                return [C()]
            return load

        monkeypatch.setattr(loaders, "_bc3_loader", fake_loader)
        monkeypatch.setattr(loaders, "candidate_cookie_files",
                            lambda name: [("snap", Path("/fake/Cookies"))])
        assert loaders.from_browser_raw("chrome") == [("k", "perplexity.ai", "v")]
        assert calls == [{}, {"cookie_file": "/fake/Cookies"}]

    def test_all_paths_fail_raises_autherror(self, monkeypatch):
        """Native + sandbox all failing surfaces AuthError, mentioning the last cause.

        原生与沙箱全部失败时抛 AuthError 并带最后原因。
        """
        monkeypatch.setattr(loaders, "_bc3_loader",
                            lambda name: (lambda domain_name=None, **kw: (_ for _ in ()).throw(RuntimeError("boom"))))
        monkeypatch.setattr(loaders, "candidate_cookie_files",
                            lambda name: [("snap", Path("/fake/Cookies"))])
        with pytest.raises(AuthError, match="boom"):
            loaders.from_browser_raw("chrome")


class TestKeyringBypass:
    """Linux keyring D-Bus transport failures retry with Chromium's default
    password; other failures are not retried.

    Linux keyring 的 D-Bus 传输层失败会用 Chromium 默认密码重试；其他失败不重试。
    """

    FakeAuthError = type("AuthenticationError", (Exception,), {"__module__": "jeepney.auth"})

    def test_dbus_auth_failure_retried_with_default_password(self, monkeypatch):
        """First call raises a jeepney-style AuthenticationError; the bypassed
        retry succeeds, and the real password manager is restored afterwards.

        首次调用抛 jeepney 式 AuthenticationError;绕过 keyring 的重试成功,
        且事后恢复真正的密码管理器。
        """
        import browser_cookie3 as bc3

        monkeypatch.setattr("sys.platform", "linux")

        class C:
            name, domain, value = "k", "perplexity.ai", "v"

        calls = []

        def fake_loader(name):
            def load(domain_name=None, **kw):
                calls.append(kw)
                if len(calls) == 1:
                    raise self.FakeAuthError("REJECTED ANONYMOUS")
                return [C()]
            return load

        monkeypatch.setattr(loaders, "_bc3_loader", fake_loader)
        monkeypatch.setattr(loaders, "candidate_cookie_files",
                            lambda name: pytest.fail("首次重试即成功,不应探测沙箱"))
        real_pm = bc3._LinuxPasswordManager
        assert loaders.from_browser_raw("edge") == [("k", "perplexity.ai", "v")]
        assert calls == [{}, {}]
        assert bc3._LinuxPasswordManager is real_pm

    def test_non_keyring_failure_not_retried(self, monkeypatch):
        """A plain RuntimeError is reported without any bypass retry.

        普通 RuntimeError 不触发绕过重试,直接上报。
        """
        monkeypatch.setattr("sys.platform", "linux")
        calls = []

        def fake_loader(name):
            def load(domain_name=None, **kw):
                calls.append(kw)
                raise RuntimeError("boom")
            return load

        monkeypatch.setattr(loaders, "_bc3_loader", fake_loader)
        monkeypatch.setattr(loaders, "candidate_cookie_files", lambda name: [])
        with pytest.raises(AuthError, match="boom"):
            loaders.from_browser_raw("edge")
        assert calls == [{}]

    def test_keyring_failure_still_failing_surfaces_original(self, monkeypatch):
        """When the bypass retry also fails, the original D-Bus cause is reported.

        绕过重试也失败时,报告原始的 D-Bus 原因。
        """
        monkeypatch.setattr("sys.platform", "linux")

        def fake_loader(name):
            return lambda domain_name=None, **kw: (_ for _ in ()).throw(
                self.FakeAuthError("REJECTED ANONYMOUS"))

        monkeypatch.setattr(loaders, "_bc3_loader", fake_loader)
        monkeypatch.setattr(loaders, "candidate_cookie_files", lambda name: [])
        with pytest.raises(AuthError, match="REJECTED ANONYMOUS"):
            loaders.from_browser_raw("edge")

    def test_predicate(self):
        """The transport-error predicate matches jeepney/dbus types only.

        传输层错误判定只匹配 jeepney/dbus 类型。
        """
        assert loaders._is_keyring_transport_error(self.FakeAuthError("x"))
        assert not loaders._is_keyring_transport_error(RuntimeError("x"))
        assert not loaders._is_keyring_transport_error(ValueError("x"))
