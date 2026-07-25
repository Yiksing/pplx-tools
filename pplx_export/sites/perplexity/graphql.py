"""Perplexity GraphQL query set (persisted queries, APQ) with cursor pagination.

Data path (mapped on 2026-07-19):
  - List first page: LibraryThreadsRelayQuery (25 per page)
  - Pagination: LibraryRecentThreadsPaginationQuery (variables $cursor/$count)
  - Endpoint: POST /rest/perplexity_ask/graphql
Note: the pagination variable names are cursor/count (not after/first).

Perplexity GraphQL 查询集（持久化查询 APQ）与 cursor 分页。

数据通路（2026-07-19 探明）：
  - 列表首页：LibraryThreadsRelayQuery（每页 25）
  - 分页：LibraryRecentThreadsPaginationQuery（变量 $cursor/$count）
  - 端点：POST /rest/perplexity_ask/graphql
注：分页变量名是 cursor/count（不是 after/first）。
"""

from __future__ import annotations

from typing import Any, Iterator

from ...core.http.transport import Transport

GRAPHQL_URL = "https://www.perplexity.ai/rest/perplexity_ask/graphql"

Q_LIBRARY = "LibraryThreadsRelayQuery"
H_LIBRARY = "a5229c390a6a00f81764187a21885cff655670029355c663fe393cc6e98f9ebe"

Q_LIBRARY_PAGE = "LibraryRecentThreadsPaginationQuery"
H_LIBRARY_PAGE = "4f6dfcb8e9d3c065aca20ca1e82ca7fe464aaffc1faefade295bb7e333199629"

_BASE_VARS = {
    "includeSearchPreview": False,
    "searchTerm": None,
    "sortOrder": "NEWEST",
    "statuses": None,
    "threadTypes": None,
    "sources": None,
    "includeTemporary": None,
}


class GraphQLClient:
    def __init__(self, transport: Transport, url: str = GRAPHQL_URL):
        self.transport = transport
        self.url = url

    def query(self, operation: str, sha256: str, variables: dict) -> dict:
        return self.transport.post_graphql(self.url, operation, variables, sha256)

    def list_threads(self, page_size: int = 25, max_pages: int = 50) -> Iterator[dict]:
        """Cursor-paginate through all thread nodes (node dict).

        游标分页拉取全部线程节点（node dict）。
        """
        cursor = None
        for page in range(max_pages):
            if page == 0:
                v = dict(_BASE_VARS)
                # The first page carries count too (previously it only took effect from page 2, pinning page 1 to 25).
                # 首页同样带 count（此前仅第 2 页起生效，首页被固定回 25）
                v["count"] = page_size
                j = self.query(Q_LIBRARY, H_LIBRARY, v)
            else:
                v = dict(_BASE_VARS)
                v.update({"cursor": cursor, "count": page_size})
                j = self.query(Q_LIBRARY_PAGE, H_LIBRARY_PAGE, v)
            th = (((j or {}).get("data") or {}).get("viewer") or {}).get("recentGroup", {}).get("threads")
            if not th:
                break
            edges = th.get("edges") or []
            if not edges:
                break
            for e in edges:
                node = e.get("node")
                if node:
                    yield node
            page_info = th.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
            if not cursor:
                # hasNextPage is true but endCursor is empty: paging with an empty cursor repeats the same page.
                # hasNextPage 为真但 endCursor 为空：带空 cursor 翻页会重复同页
                break
