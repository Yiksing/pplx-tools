"""N-05 / N-06 / N-09 fix regression tests (fully offline).

- N-05: WebBridgeTransport error classification (401/403→Auth, 400+ENTRY_EXPIRED→Expired, 5xx→backoff retry)
- N-06: no more wasted sleep after the final failed retry (all backoff paths on both cookie/bridge sides)
- N-09: 200 non-JSON bodies from CookieTransport.get_json/post_json wrapped into TransportError

N-05 / N-06 / N-09 修复回归测试（全离线）。

- N-05：WebBridgeTransport 错误分类（401/403→Auth、400+ENTRY_EXPIRED→Expired、5xx→退避重试）
- N-06：末次重试失败不再白睡（cookie/bridge 两侧所有退避路径）
- N-09：CookieTransport.get_json/post_json 的 200 非 JSON 体包成 TransportError
"""

from __future__ import annotations

import base64
import io
import json
import logging
import urllib.error

import pytest

from pplx_export.core.errors import (
    AuthTransportError,
    EntryDeletedError,
    EntryExpiredError,
    RateLimitError,
    TransportError,
)
from pplx_export.core.http.bridge_transport import WebBridgeTransport
from pplx_export.core.http.cookie_transport import CookieTransport
from pplx_export.core.throttle import Throttle

URL = "https://www.perplexity.ai/rest/thread/00000000-0000-0000-0000-000000000000"


@pytest.fixture()
def sleep_counter(monkeypatch):
    """Count Throttle.backoff() invocations (one per logical retry wait) and neutralize
    real sleeping. N-06's signal is that backoff() must NOT be called after the final
    attempt; pre-heartbeat this was proxied by counting time.sleep, but backoff() now
    sleeps in heartbeat chunks (many sleeps per backoff), so we count backoff() directly.

    统计 Throttle.backoff() 调用次数（每次逻辑重试等待一次），并让真实睡眠空转。
    N-06 的判据是末次尝试后不得再调 backoff()；心跳化后一次 backoff() 会多次 sleep，
    故改为直接计数 backoff()。"""
    calls: list[float] = []
    monkeypatch.setattr("pplx_export.core.throttle.time.sleep", lambda *_a, **_k: None)
    orig = Throttle.backoff

    def _spy(self, *a, **k):
        calls.append(1.0)
        return orig(self, *a, **k)

    monkeypatch.setattr(Throttle, "backoff", _spy)
    return calls


# ---------- CookieTransport fake opener ----------
# ---------- CookieTransport 假 opener ----------

class _FakeResp:
    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _ScriptedOpener:
    """Return scripted responses or raise errors in order; record the call count.

    按脚本依次返回响应或抛错；记录调用次数。"""

    def __init__(self, script: list):
        self.script = list(script)
        self.calls = 0

    def open(self, req, timeout=None):
        self.calls += 1
        item = self.script.pop(0) if self.script else self._last
        self._last = item
        if isinstance(item, Exception):
            raise item
        return item


def _http_error(code: int, body: bytes = b"") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(URL, code, "err", {}, io.BytesIO(body))


def _cookie_transport(script: list, max_retries: int = 3) -> tuple[CookieTransport, _ScriptedOpener]:
    t = CookieTransport(cookies={}, max_retries=max_retries)
    opener = _ScriptedOpener(script)
    t._opener = opener
    return t, opener


# ---------- N-06: no wasted sleep after the final cookie-side failure ----------
# ---------- N-06：cookie 侧末次失败不白睡 ----------

class TestN06CookieBackoff:
    def test_429_exhausted_no_final_sleep(self, sleep_counter):
        t, opener = _cookie_transport([_http_error(429)] * 3)
        with pytest.raises(RateLimitError):
            t.get_json(URL)
        assert opener.calls == 3
        assert len(sleep_counter) == 2, "末次失败后不应再退避睡眠"

    def test_5xx_exhausted_no_final_sleep(self, sleep_counter):
        t, opener = _cookie_transport([_http_error(503)] * 3)
        with pytest.raises(TransportError):
            t.get_json(URL)
        assert opener.calls == 3
        assert len(sleep_counter) == 2

    def test_network_error_exhausted_no_final_sleep(self, sleep_counter):
        err = urllib.error.URLError("boom")
        t, opener = _cookie_transport([err] * 3)
        with pytest.raises(TransportError):
            t.get_json(URL)
        assert opener.calls == 3
        assert len(sleep_counter) == 2

    def test_5xx_recovers_on_retry(self, sleep_counter):
        ok = _FakeResp(b'{"a": 1}')
        t, opener = _cookie_transport([_http_error(500), ok])
        assert t.get_json(URL) == {"a": 1}
        assert opener.calls == 2
        assert len(sleep_counter) == 1

    def test_401_raises_immediately_no_sleep(self, sleep_counter):
        t, opener = _cookie_transport([_http_error(401, b"denied")])
        with pytest.raises(AuthTransportError):
            t.get_json(URL)
        assert opener.calls == 1
        assert sleep_counter == []

    def test_entry_expired_terminal_no_sleep(self, sleep_counter):
        t, opener = _cookie_transport([_http_error(400, b'{"error":"ENTRY_EXPIRED"}')])
        with pytest.raises(EntryExpiredError):
            t.get_json(URL)
        assert opener.calls == 1
        assert sleep_counter == []

    def test_entry_deleted_terminal_no_sleep(self, sleep_counter):
        """ENTRY_DELETED (verified against the delete endpoint: after deletion,
        GET thread returns 400 ENTRY_DELETED) → EntryDeletedError terminal state;
        also 400 but a different code, must not be misclassified as transient and retried.

        ENTRY_DELETED（删除端点实测：删除后 GET thread 返回 400 ENTRY_DELETED）
        → EntryDeletedError 终态；同为 400 但 code 不同，不得漏判为瞬态重试。"""
        t, opener = _cookie_transport(
            [_http_error(400, b'{"error":"ENTRY_DELETED","message":"This entry has been deleted"}')])
        with pytest.raises(EntryDeletedError) as exc_info:
            t.get_json(URL)
        assert opener.calls == 1
        assert sleep_counter == []
        # Subclass fallback semantics
        # 子类兜底语义
        assert isinstance(exc_info.value, EntryExpiredError)

    def test_entry_deleted_distinguishable_from_expired(self, sleep_counter):
        """ENTRY_DELETED must not be swallowed by the ENTRY_EXPIRED check (the two
        codes are classified independently).

        ENTRY_DELETED 不得被 ENTRY_EXPIRED 判定吞掉（两个 code 独立分类）。"""
        t, _ = _cookie_transport([_http_error(400, b'{"error":"ENTRY_DELETED"}')])
        with pytest.raises(EntryDeletedError):
            t.get_json(URL)
        t2, _ = _cookie_transport([_http_error(400, b'{"error":"ENTRY_EXPIRED"}')])
        with pytest.raises(EntryExpiredError) as exc2:
            t2.get_json(URL)
        assert not isinstance(exc2.value, EntryDeletedError)


# ---------- N-09: cookie-side 200 non-JSON body → TransportError ----------
# ---------- N-09：cookie 侧 200 非 JSON 体 → TransportError ----------

class TestN09NonJsonBody:
    def test_get_json_200_html_body(self, sleep_counter):
        t, _ = _cookie_transport([_FakeResp(b"<html>Cloudflare</html>")])
        with pytest.raises(TransportError) as exc_info:
            t.get_json(URL)
        assert not isinstance(exc_info.value, json.JSONDecodeError)
        assert "非 JSON" in str(exc_info.value)

    def test_post_json_200_html_body(self, sleep_counter):
        t, _ = _cookie_transport([_FakeResp(b"<html>login</html>")])
        with pytest.raises(TransportError) as exc_info:
            t.post_json(URL, {"q": 1})
        assert not isinstance(exc_info.value, json.JSONDecodeError)

    def test_get_json_valid_json_unaffected(self, sleep_counter):
        t, _ = _cookie_transport([_FakeResp(b'{"ok": true}')])
        assert t.get_json(URL) == {"ok": True}


# ---------- WebBridgeTransport fake evaluate ----------
# ---------- WebBridgeTransport 假 evaluate ----------

def _bridge_transport(script: list, max_retries: int = 3) -> tuple[WebBridgeTransport, list]:
    t = WebBridgeTransport(max_retries=max_retries)
    calls: list[str] = []
    queue = list(script)

    def fake_evaluate(code, timeout=120):
        calls.append(code)
        item = queue.pop(0) if queue else script[-1]
        if isinstance(item, Exception):
            raise item
        return item

    t.evaluate = fake_evaluate
    return t, calls


# ---------- N-05: bridge-side error classification ----------
# ---------- N-05：bridge 侧错误分类 ----------

class TestN05BridgeClassify:
    def test_get_json_401_auth(self, sleep_counter):
        t, calls = _bridge_transport([{"status": 401, "head": "denied"}])
        with pytest.raises(AuthTransportError):
            t.get_json(URL)
        assert len(calls) == 1
        assert sleep_counter == []

    def test_get_json_403_auth(self, sleep_counter):
        t, _ = _bridge_transport([{"status": 403, "head": "forbidden"}])
        with pytest.raises(AuthTransportError):
            t.get_json(URL)

    def test_get_json_entry_expired(self, sleep_counter):
        t, calls = _bridge_transport([{"status": 400, "head": '{"error":"ENTRY_EXPIRED"}'}])
        with pytest.raises(EntryExpiredError):
            t.get_json(URL)
        assert len(calls) == 1
        assert sleep_counter == []

    def test_get_json_entry_deleted(self, sleep_counter):
        """Bridge-side counterpart: 400 ENTRY_DELETED → EntryDeletedError (terminal).

        bridge 侧同款：400 ENTRY_DELETED → EntryDeletedError（终态）。"""
        t, calls = _bridge_transport(
            [{"status": 400, "head": '{"error":"ENTRY_DELETED","message":"This entry has been deleted"}'}])
        with pytest.raises(EntryDeletedError) as exc_info:
            t.get_json(URL)
        assert len(calls) == 1
        assert sleep_counter == []
        # Subclass fallback semantics
        # 子类兜底语义
        assert isinstance(exc_info.value, EntryExpiredError)

    def test_get_json_400_without_expired_is_plain_error(self, sleep_counter):
        t, _ = _bridge_transport([{"status": 400, "head": '{"error":"BAD_REQUEST"}'}])
        with pytest.raises(TransportError) as exc_info:
            t.get_json(URL)
        assert not isinstance(exc_info.value, EntryExpiredError)

    def test_get_json_5xx_retry_then_success(self, sleep_counter):
        t, calls = _bridge_transport([
            {"status": 503, "head": ""},
            {"status": 200, "json": {"entries": []}},
        ])
        assert t.get_json(URL) == {"entries": []}
        assert len(calls) == 2
        assert len(sleep_counter) == 1

    def test_get_json_5xx_exhausted_no_final_sleep(self, sleep_counter):
        t, calls = _bridge_transport([{"status": 504, "head": ""}] * 3)
        with pytest.raises(TransportError):
            t.get_json(URL)
        assert len(calls) == 3
        assert len(sleep_counter) == 2, "N-06：末次失败不再白睡"

    def test_get_json_429_exhausted_no_final_sleep(self, sleep_counter):
        t, calls = _bridge_transport([{"status": 429, "head": ""}] * 3)
        with pytest.raises(RateLimitError):
            t.get_json(URL)
        assert len(calls) == 3
        assert len(sleep_counter) == 2

    def test_get_json_other_status_raises_immediately(self, sleep_counter):
        t, calls = _bridge_transport([{"status": 404, "head": "not found"}])
        with pytest.raises(TransportError):
            t.get_json(URL)
        assert len(calls) == 1
        assert sleep_counter == []

    def test_get_json_non_dict_result_generic_error(self, sleep_counter):
        # Preserved current behavior: when the JS side cannot obtain a status
        # (non-JSON body etc.), fall back to the generic TransportError
        # 现状保留：JS 侧拿不到 status（非 JSON 体等）时走泛化 TransportError
        t, _ = _bridge_transport(["garbage"])
        with pytest.raises(TransportError):
            t.get_json(URL)

    def test_post_json_500_retry_exhausted(self, sleep_counter):
        t, calls = _bridge_transport([{"status": 500, "head": ""}] * 3)
        with pytest.raises(TransportError):
            t.post_json(URL, {"q": 1})
        assert len(calls) == 3
        assert len(sleep_counter) == 2

    def test_post_json_403_auth(self, sleep_counter):
        t, _ = _bridge_transport([{"status": 403, "head": ""}])
        with pytest.raises(AuthTransportError):
            t.post_json(URL, {"q": 1})

    def test_download_403_auth(self, sleep_counter):
        t, calls = _bridge_transport([{"status": 403, "head": "", "b64": None}])
        with pytest.raises(AuthTransportError):
            t.download(URL)
        assert len(calls) == 1
        assert sleep_counter == []

    def test_download_5xx_exhausted_no_final_sleep(self, sleep_counter):
        t, calls = _bridge_transport([{"status": 502, "head": "", "b64": None}] * 3)
        with pytest.raises(TransportError):
            t.download(URL)
        assert len(calls) == 3
        assert len(sleep_counter) == 2

    def test_download_success(self, sleep_counter):
        payload = base64.b64encode(b"hello").decode()
        t, _ = _bridge_transport([{"status": 200, "b64": payload}])
        assert t.download(URL) == b"hello"
        assert sleep_counter == []


# ---------- in-flight request heartbeat (CookieTransport._open_read) ----------
# ---------- 在途请求心跳（CookieTransport._open_read）----------

class TestInflightRequestHeartbeat:
    def test_slow_request_emits_heartbeat(self, caplog):
        import time as _t

        from pplx_export.core.throttle import Throttle

        class _SlowOpener:
            def open(self, req, timeout=None):
                _t.sleep(0.12)  # exceeds the tiny heartbeat interval below
                return _FakeResp(b'{"ok": true}')

        t = CookieTransport(cookies={}, throttle=Throttle(heartbeat_interval=0.03))
        t._opener = _SlowOpener()
        with caplog.at_level(logging.INFO, logger="pplx_export.transport"):
            assert t.get_json(URL) == {"ok": True}
        beats = [r for r in caplog.records if "仍在等待响应" in r.getMessage()]
        assert beats, "在途慢请求应在默认档打出心跳"

    def test_fast_request_no_heartbeat(self, caplog):
        t = CookieTransport(cookies={})
        t._opener = _ScriptedOpener([_FakeResp(b'{"ok": true}')])
        with caplog.at_level(logging.INFO, logger="pplx_export.transport"):
            assert t.get_json(URL) == {"ok": True}
        beats = [r for r in caplog.records if "仍在等待响应" in r.getMessage()]
        assert beats == [], "快速请求不应打心跳"


# ---------- SSE idle heartbeat (ask_api.post_stream) ----------
# ---------- SSE 空闲心跳（ask_api.post_stream）----------

class TestSseIdleHeartbeat:
    def test_idle_stream_emits_heartbeat(self, caplog):
        import time as _t

        from pplx_export.core.throttle import Throttle
        from pplx_export.sites.perplexity.ask_api import post_stream

        class _Resp:
            def __init__(self):
                self._n = 0

            def read1(self, n):
                self._n += 1
                if self._n == 1:
                    _t.sleep(0.12)  # idle gap > interval → heartbeat fires
                    return b'data: {"a": 1}\n\n'
                return b""

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class _Opener:
            def open(self, req, timeout=None):
                return _Resp()

        class _T:
            _cookie_header = ""
            _opener = _Opener()
            throttle = Throttle(heartbeat_interval=0.03)

        with caplog.at_level(logging.INFO, logger="pplx_export.ask"):
            evs = list(post_stream(_T(), "https://example.invalid/sse", {}))
        assert evs == [{"a": 1}]
        beats = [r for r in caplog.records if "仍在等待响应流" in r.getMessage()]
        assert beats, "SSE 空闲应打出心跳"
