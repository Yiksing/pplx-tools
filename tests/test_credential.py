"""Tests for the Credential seam (core/auth.py) and its transport binding.

Offline: the transport's urllib opener is replaced by a recording stub.

凭证接缝（core/auth.py）及其 transport 绑定的测试。

全离线：transport 的 urllib opener 以记录桩替代。
"""

from http.cookiejar import CookieJar

from pplx_export.core.auth import (BearerCredential, CookieCredential,
                                   Credential)
from pplx_export.core.http.cookie_transport import CookieTransport


class TestCredentials:
    def test_cookie_credential_headers(self):
        """CookieCredential emits a Cookie header; dict and CookieJar inputs both work.

        CookieCredential 产出 Cookie 头；dict 与 CookieJar 输入均可。
        """
        c = CookieCredential({"sid": "x"})
        assert c.auth_headers() == {"Cookie": "sid=x"}
        assert c.cookie_dict() == {"sid": "x"}
        assert c.is_healthy()
        jar = CookieJar()
        assert CookieCredential(jar).cookie_dict() == {}
        assert not CookieCredential({}).is_healthy()

    def test_bearer_credential_headers(self):
        """BearerCredential emits an Authorization header and satisfies the protocol.

        BearerCredential 产出 Authorization 头且满足协议。
        """
        b = BearerCredential("tok-1")
        assert b.auth_headers() == {"Authorization": "Bearer tok-1"}
        assert b.is_healthy()
        assert isinstance(b, Credential)
        assert not BearerCredential("").is_healthy()


class _Resp:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b'{"ok": true}'


class _Opener:
    """Records the request headers on open().

    open() 时记录请求头。"""

    def __init__(self):
        self.headers = None

    def open(self, req, timeout=None):
        self.headers = dict(req.header_items())
        return _Resp()


class TestTransportCredentialMerge:
    def test_credential_headers_merged(self):
        """A credential's headers are merged into the request alongside Cookie.

        凭证头与 Cookie 头一同并入请求。
        """
        t = CookieTransport({"sid": "x"}, credential=BearerCredential("tok"))
        op = _Opener()
        t._opener = op
        assert t.get_json("https://example.com/x") == {"ok": True}
        assert op.headers["Cookie"] == "sid=x"
        assert op.headers["Authorization"] == "Bearer tok"

    def test_no_credential_behavior_unchanged(self):
        """Without a credential, requests carry exactly the legacy headers.

        无凭证时请求头与旧行为一致。
        """
        t = CookieTransport({"sid": "x"})
        op = _Opener()
        t._opener = op
        t.get_json("https://example.com/x")
        assert "Authorization" not in op.headers
        assert op.headers["Cookie"] == "sid=x"

    def test_cookie_credential_as_transport_credential(self):
        """CookieTransport also accepts a CookieCredential directly.

        CookieTransport 亦可直接接受 CookieCredential。
        """
        t = CookieTransport(credential=CookieCredential({"sid": "y"}))
        op = _Opener()
        t._opener = op
        t.get_json("https://example.com/x")
        assert op.headers["Cookie"] == "sid=y"
