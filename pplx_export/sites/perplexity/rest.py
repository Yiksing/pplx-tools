"""Perplexity /rest/thread data fetching.

Two response flavors:
  - plain: entries[].text holds all steps; background_entries holds complete sub-agent workflows
  - schematized: blocks (workflow/unified_assets/markdown/plan_block) hold
    workflow_payload (sub-agent prompts), asset signed URLs, and file contents
Throttling: page_delay seconds between page turns.

Perplexity /rest/thread 数据抓取。

两种响应：
  - 普通（plain）：entries[].text 含全部步骤；background_entries 含子代理完整工作流
  - schematized：blocks（workflow/unified_assets/markdown/plan_block）含 workflow_payload
    （子代理 prompt）、资产签名 URL、文件内容
限频：翻页间隔 page_delay 秒。
"""

from __future__ import annotations

import time
import urllib.parse
from typing import Any

from ...core.http.transport import Transport
from . import platform as _plat

# Query fragment for schematized thread reads — single source in platform.py.
# schematized 线程读取的查询片段——单一来源在 platform.py。
SCHEMATIZED_USE_CASES = _plat.schematized_query()


class ThreadFetcher:
    def __init__(self, transport: Transport, page_delay: float = 3.0):
        self.transport = transport
        self.page_delay = page_delay

    def _fetch_paginated(self, make_path, max_pages: int) -> dict:
        all_entries, all_background, metadata = [], [], None
        cursor = None
        for page in range(max_pages):
            path = make_path(cursor)
            j = self.transport.get_json(path, timeout=120)
            if metadata is None:
                metadata = j.get("thread_metadata") or {}
            all_entries.extend(j.get("entries") or [])
            all_background.extend(j.get("background_entries") or [])
            if not j.get("has_next_page") or not j.get("next_cursor"):
                break
            cursor = j["next_cursor"]
            time.sleep(self.page_delay)
        return {"metadata": metadata or {}, "entries": all_entries, "background_entries": all_background}

    def get_thread(self, uuid: str, max_pages: int = 20) -> dict:
        def make(cursor):
            p = f"https://www.perplexity.ai/rest/thread/{uuid}?version={_plat.API_VERSION}&source=default"
            if cursor:
                p += "&cursor=" + urllib.parse.quote(cursor, safe="")
            return p
        return self._fetch_paginated(make, max_pages)

    def get_thread_blocks(self, uuid: str, max_pages: int = 10) -> dict:
        def make(cursor):
            p = (f"https://www.perplexity.ai/rest/thread/{uuid}?with_parent_info=true"
                 f"&with_schematized_response=true&version={_plat.API_VERSION}&source=default"
                 f"&limit=100&offset=0&from_first=false&{SCHEMATIZED_USE_CASES}")
            if cursor:
                p += "&cursor=" + urllib.parse.quote(cursor, safe="")
            return p
        return self._fetch_paginated(make, max_pages)

    def get_collection(self, slug: str) -> dict:
        """Space metadata (owner_user/contributor_users/access/max_contributors, direct cookie access).

        空间元数据（owner_user/contributor_users/access/max_contributors，cookie 直连）。
        """
        p = ("https://www.perplexity.ai/rest/collections/get_collection"
             f"?collection_slug={urllib.parse.quote(slug, safe='')}&version={_plat.API_VERSION}&source=default")
        return self.transport.get_json(p, timeout=30)
