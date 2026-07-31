"""Dynamic User-Agent tests: build_ua / build_client_hints / version detection,
CookieTransport header wiring, and cache source-label fidelity in resolve().

Covers:
  - build_ua matrix: {Darwin, Windows, Linux} x {chrome, edge, firefox, safari,
    brave, file:/unknown/empty source}, plus detected-version and config-override
    priority;
  - detect_browser_version: success, failure -> None (never raises), per-family
    caching, unknown family;
  - build_client_hints: Chromium families only, correct platform name, empty for
    firefox/safari/file/override;
  - CookieTransport: per-source UA + client hints observable via a fake opener,
    and the same headers on the ask_api SSE path (post_stream);
  - resolve() cache branch: the saved origin label (browser:<name>) survives a
    cache hit; a legacy "cache" label still resolves to "cache";
  - config: top-level `user_agent` loads into config.USER_AGENT.

Fully offline: tmp_path + monkeypatch + fake openers; no network, no real browser
probing (detection is always monkeypatched or pointed at fake state).

动态 User-Agent 测试：build_ua / build_client_hints / 版本探测、CookieTransport
表头接线，以及 resolve() 的缓存来源标签保真。

覆盖：
  - build_ua 矩阵：{Darwin, Windows, Linux} × {chrome, edge, firefox, safari,
    brave, file:/未知/空来源}，及探测版本与配置覆盖优先级；
  - detect_browser_version：成功、失败 → None（绝不抛出）、按族缓存、未知族；
  - build_client_hints：仅 Chromium 族、平台名正确、firefox/safari/file/覆盖为空；
  - CookieTransport：经伪 opener 可观测的各来源 UA + client hints，ask_api SSE
    通路（post_stream）同样携带；
  - resolve() 缓存分支：保存的原始标签（browser:<name>）在缓存命中后保留；
    旧式 "cache" 标签仍回退为 "cache"；
  - config：顶层 `user_agent` 载入 config.USER_AGENT。

全离线：tmp_path + monkeypatch + 伪 opener；不触网、不探测真实浏览器
（探测一律被 monkeypatch 或指向伪状态）。
"""

from __future__ import annotations

import json
from http.cookiejar import CookieJar

import pytest

from pplx_export import config as cfg
from pplx_export.core.cookies import resolve
from pplx_export.core.cookies.cache import CookieCache
from pplx_export.core.http import user_agent as ua_mod
from pplx_export.core.http.cookie_transport import CookieTransport
from pplx_export.sites.perplexity.ask_api import post_stream

# Captured at import time, before the autouse fixture stubs the module attribute;
# detection tests re-point the attribute at the real implementation.
# 导入期捕获（早于 autouse fixture 打桩）；探测类测试把模块属性指回真实实现。
_REAL_DETECT = ua_mod.detect_browser_version


@pytest.fixture(autouse=True)
def _no_real_detection(monkeypatch):
    """Never probe a real browser: detection falls through to the static table,
    and the per-family cache is cleared around each test.

    绝不探测真实浏览器：探测落空走静态表，且按族缓存在每个测试前后清空。"""
    ua_mod._version_cache.clear()
    monkeypatch.setattr(ua_mod, "detect_browser_version", lambda family: None)
    yield
    ua_mod._version_cache.clear()


class TestBuildUaMatrix:
    @pytest.mark.parametrize("system,source,expected", [
        ("Darwin", "browser:chrome",
         "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
        ("Windows", "browser:edge",
         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"),
        ("Linux", "browser:firefox",
         "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0"),
        ("Darwin", "browser:firefox",
         "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) "
         "Gecko/20100101 Firefox/127.0"),
        ("Darwin", "browser:safari",
         "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
         "(KHTML, like Gecko) Version/17.5 Safari/605.1.15"),
        ("Linux", "browser:brave",
         "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    ])
    def test_family_os_matrix(self, monkeypatch, system, source, expected):
        monkeypatch.setattr(ua_mod.platform, "system", lambda: system)
        assert ua_mod.build_ua(source) == expected

    @pytest.mark.parametrize("source", ["", "cache", "file:/tmp/cookies.txt",
                                        "browser:netscape", "weird"])
    def test_unknown_source_generic_chrome(self, monkeypatch, source):
        monkeypatch.setattr(ua_mod.platform, "system", lambda: "Darwin")
        assert ua_mod.build_ua(source) == (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

    def test_detected_version_used(self, monkeypatch):
        monkeypatch.setattr(ua_mod.platform, "system", lambda: "Darwin")
        monkeypatch.setattr(ua_mod, "detect_browser_version",
                            lambda family: "130.0.1234.56")
        assert "Chrome/130.0.1234.56" in ua_mod.build_ua("browser:chrome")

    def test_config_override_wins(self, monkeypatch):
        monkeypatch.setattr(cfg, "USER_AGENT", "Custom/1.0")
        assert ua_mod.build_ua("browser:chrome") == "Custom/1.0"
        assert ua_mod.build_ua("browser:firefox") == "Custom/1.0"
        assert ua_mod.build_ua("") == "Custom/1.0"


class TestDetectBrowserVersion:
    """Run the real detector against monkeypatched platform/probe seams.

    让真实探测逻辑跑在 monkeypatch 的平台/探测接缝上。"""

    @pytest.fixture(autouse=True)
    def _real_detector(self, monkeypatch):
        monkeypatch.setattr(ua_mod, "detect_browser_version", _REAL_DETECT)

    def test_success_and_per_family_cache(self, monkeypatch):
        monkeypatch.setattr(ua_mod.sys, "platform", "darwin")
        calls = []
        monkeypatch.setattr(ua_mod, "_detect_mac",
                            lambda family: calls.append(family) or "126.0.6478.126")
        assert ua_mod.detect_browser_version("chrome") == "126.0.6478.126"
        # Second call is served from the cache (no re-probe)
        # 第二次命中缓存（不再探测）
        assert ua_mod.detect_browser_version("chrome") == "126.0.6478.126"
        assert calls == ["chrome"]

    def test_failure_returns_none_and_never_raises(self, monkeypatch):
        monkeypatch.setattr(ua_mod.sys, "platform", "darwin")

        def _boom(family):
            raise OSError("simulated probe failure")

        monkeypatch.setattr(ua_mod, "_detect_mac", _boom)
        assert ua_mod.detect_browser_version("chrome") is None

    def test_unknown_family_returns_none(self):
        assert ua_mod.detect_browser_version("netscape") is None

    def test_linux_probe_parses_version(self, monkeypatch):
        monkeypatch.setattr(ua_mod.sys, "platform", "linux")

        class _Completed:
            stdout = "Mozilla Firefox 128.0.3"

        monkeypatch.setattr(ua_mod.subprocess, "run",
                            lambda *a, **k: _Completed())
        assert ua_mod.detect_browser_version("firefox") == "128.0.3"


class TestBuildClientHints:
    def test_chromium_family_hints(self, monkeypatch):
        monkeypatch.setattr(ua_mod.platform, "system", lambda: "Windows")
        assert ua_mod.build_client_hints("browser:edge") == {
            "sec-ch-ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Microsoft Edge";v="126"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }

    def test_chromium_brand_not_duplicated(self, monkeypatch):
        monkeypatch.setattr(ua_mod.platform, "system", lambda: "Linux")
        hints = ua_mod.build_client_hints("browser:chromium")
        assert hints["sec-ch-ua"] == '"Not/A)Brand";v="8", "Chromium";v="126"'
        assert hints["sec-ch-ua-platform"] == '"Linux"'

    @pytest.mark.parametrize("source", ["browser:firefox", "browser:safari",
                                        "file:/tmp/x", "", "cache"])
    def test_non_chromium_or_unknown_empty(self, source):
        assert ua_mod.build_client_hints(source) == {}

    def test_config_override_suppresses_hints(self, monkeypatch):
        monkeypatch.setattr(cfg, "USER_AGENT", "Custom/1.0")
        assert ua_mod.build_client_hints("browser:chrome") == {}


class _Resp:
    status = 200

    def __init__(self, body: bytes = b'{"ok": true}'):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n: int = -1):
        return self._body

    def read1(self, n: int):
        body, self._body = self._body, b""
        return body


class _Opener:
    """Records the request headers on open() and replays a canned body.

    open() 时记录请求头并回放预置响应体。"""

    def __init__(self, body: bytes = b'{"ok": true}'):
        self.headers = None
        self._body = body

    def open(self, req, timeout=None):
        self.headers = {k.lower(): v for k, v in req.header_items()}
        return _Resp(self._body)


def _transport(source: str) -> tuple[CookieTransport, _Opener]:
    t = CookieTransport({"sid": "x"}, source=source)
    op = _Opener()
    t._opener = op
    return t, op


class TestTransportHeaders:
    def test_chromium_source_sends_ua_and_hints(self, monkeypatch):
        monkeypatch.setattr(ua_mod.platform, "system", lambda: "Darwin")
        t, op = _transport("browser:edge")
        assert t.get_json("https://example.com/x") == {"ok": True}
        assert op.headers["user-agent"].endswith("Edg/126.0.0.0")
        assert op.headers["sec-ch-ua-mobile"] == "?0"
        assert op.headers["sec-ch-ua-platform"] == '"macOS"'
        assert '"Microsoft Edge";v="126"' in op.headers["sec-ch-ua"]

    def test_firefox_source_sends_no_hints(self, monkeypatch):
        monkeypatch.setattr(ua_mod.platform, "system", lambda: "Darwin")
        t, op = _transport("browser:firefox")
        t.get_json("https://example.com/x")
        assert "Firefox/127.0" in op.headers["user-agent"]
        assert not any(k.startswith("sec-ch-ua") for k in op.headers)

    def test_file_source_generic_chrome_no_hints(self, monkeypatch):
        monkeypatch.setattr(ua_mod.platform, "system", lambda: "Darwin")
        t, op = _transport("file:/tmp/cookies.txt")
        t.get_json("https://example.com/x")
        assert "Chrome/126.0.0.0 Safari/537.36" in op.headers["user-agent"]
        assert not any(k.startswith("sec-ch-ua") for k in op.headers)

    def test_override_sent_verbatim_without_hints(self, monkeypatch):
        monkeypatch.setattr(cfg, "USER_AGENT", "Custom/1.0")
        t, op = _transport("browser:chrome")
        t.get_json("https://example.com/x")
        assert op.headers["user-agent"] == "Custom/1.0"
        assert not any(k.startswith("sec-ch-ua") for k in op.headers)

    def test_post_stream_uses_transport_ua_and_hints(self, monkeypatch):
        """The SSE ask path (which builds its own request) carries the same
        per-source UA + hints as _request.

        自建请求的 SSE ask 通路与 _request 携带同样的来源 UA + hints。"""
        monkeypatch.setattr(ua_mod.platform, "system", lambda: "Darwin")
        t = CookieTransport({"sid": "x"}, source="browser:edge")
        op = _Opener(b'data: {"final": true}\n\n')
        t._opener = op
        events = list(post_stream(t, "https://example.com/ask", {"q": "x"}))
        assert events == [{"final": True}]
        assert op.headers["user-agent"].endswith("Edg/126.0.0.0")
        assert op.headers["sec-ch-ua-platform"] == '"macOS"'


class TestCacheSourceFidelity:
    def test_load_with_source_roundtrip(self, tmp_path):
        cache = tmp_path / ".cookies.json"
        CookieCache(cache).save({"k": "v"}, "browser:chrome", "")
        assert CookieCache(cache).load_with_source() == ({"k": "v"}, "browser:chrome")
        # load() keeps its cookies-only contract
        # load() 保持只回 cookies 的契约
        assert CookieCache(cache).load() == {"k": "v"}

    def test_load_with_source_stale_or_missing(self, tmp_path):
        cache = tmp_path / ".cookies.json"
        assert CookieCache(cache).load_with_source() is None
        CookieCache(cache).save({"k": "v"}, "browser:chrome", "")
        assert CookieCache(cache).load_with_source(max_age_s=-1) is None

    def test_load_with_source_missing_source_field(self, tmp_path):
        cache = tmp_path / ".cookies.json"
        cache.write_text(json.dumps({"fetched_at": 9999999999, "cookies": {"k": "v"}}))
        assert CookieCache(cache).load_with_source() == ({"k": "v"}, "")

    def test_resolve_cache_hit_returns_origin_browser(self, tmp_path):
        cache = tmp_path / ".cookies.json"
        CookieCache(cache).save({"k": "v"}, "browser:chrome", "")
        cookies, source = resolve(cache_path=cache)
        assert cookies == {"k": "v"}
        assert source == "browser:chrome"

    def test_resolve_cache_hit_legacy_label_falls_back(self, tmp_path):
        cache = tmp_path / ".cookies.json"
        CookieCache(cache).save({"k": "v"}, "cache", "")
        _cookies, source = resolve(cache_path=cache)
        assert source == "cache"


class TestConfigUserAgent:
    def test_user_agent_loaded_from_toml(self, tmp_path):
        p = tmp_path / "config.toml"
        p.write_text('user_agent = "Custom/1.0"\n', encoding="utf-8")
        cfg.configure(p)
        assert cfg.USER_AGENT == "Custom/1.0"

    def test_user_agent_absent_stays_none(self, tmp_path):
        p = tmp_path / "config.toml"
        p.write_text('default_account = "alice"\n', encoding="utf-8")
        cfg.configure(p)
        assert cfg.USER_AGENT is None


class TestModuleFallbacks:
    def test_module_ua_constant_is_generic(self):
        """The kept module-level UA constant stays a generic (source="") UA.

        保留的模块级 UA 常量保持为通用（source=""）UA。"""
        from pplx_export.core.http.cookie_transport import UA
        assert "Chrome/" in UA and "Safari/537.36" in UA

    def test_cookiejar_ctor_still_works(self):
        """The new `source` kwarg must not disturb existing constructor shapes.

        新增 `source` 参数不得影响既有构造形态。"""
        t = CookieTransport(CookieJar())
        assert t._cookie_header == ""
        assert t._ua
        assert t._client_hints == {}
