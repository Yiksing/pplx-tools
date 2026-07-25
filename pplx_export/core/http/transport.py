"""Transport abstraction: unified get/post interface hiding the two implementations,
"direct cookie connection" and "browser page context".

Transport 抽象：统一 get/post 接口，屏蔽「cookie 直连」与「浏览器页面上下文」两种实现。"""

from __future__ import annotations

import abc
from typing import Any


class Transport(abc.ABC):
    """HTTP transport abstraction.

    HTTP 传输抽象。"""

    name = "abstract"

    @abc.abstractmethod
    def get_json(self, url: str, timeout: int = 60) -> Any:
        """GET; returns parsed JSON.

        GET，返回解析后的 JSON。"""
        raise NotImplementedError

    @abc.abstractmethod
    def post_json(self, url: str, payload: dict, timeout: int = 60) -> Any:
        """POST a JSON body; returns parsed JSON.

        POST JSON body，返回解析后的 JSON。"""
        raise NotImplementedError

    @abc.abstractmethod
    def download(self, url: str, timeout: int = 120) -> bytes:
        """Download binary content (assets/reports).

        下载二进制（资产/报告）。"""
        raise NotImplementedError

    def post_graphql(self, url: str, operation: str, variables: dict, sha256: str, timeout: int = 60) -> Any:
        """Persisted GraphQL query (APQ).

        持久化 GraphQL 查询（APQ）。"""
        payload = {
            "operationName": operation,
            "variables": variables,
            "extensions": {"persistedQuery": {"version": 1, "sha256Hash": sha256}},
        }
        return self.post_json(url, payload, timeout=timeout)
