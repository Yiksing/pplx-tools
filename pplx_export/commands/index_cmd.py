"""cmd: index — extract the account's conversation list index.

cmd：index —— 提取账户对话列表索引。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..core.logging import get_logger

log = get_logger("cli")


def cmd_index(adapter, account, out_root: Path):
    rows = list(adapter.list_threads(account))
    p = out_root / "index" / f"library_{account.username}.json"
    # Preserve the enrichment written by search-mode-backfill: GraphQL index rows do
    # not carry search_mode themselves, and a refresh would wash away the backfilled
    # field — merge it back from the old index by entryUUID
    # 保留 search-mode-backfill 的富化结果：GraphQL 索引行本身不含 search_mode，
    # 刷新会冲掉已补字段——按 entryUUID 从旧索引合并回来
    old_sm: dict = {}
    if p.exists():
        try:
            for t in json.loads(p.read_text()).get("threads", []):
                if t.get("entryUUID") and t.get("search_mode"):
                    old_sm[t["entryUUID"]] = t["search_mode"]
        except Exception as e:
            log.warning(f"[index] 旧索引读取失败，search_mode 富化将无法保留: {e}")
    n_kept = 0
    for t in rows:
        sm = old_sm.get(t.get("entryUUID") or "")
        if sm:
            t["search_mode"] = sm
            n_kept += 1
    doc = {"account": account.username, "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "count": len(rows), "threads": rows}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    log.info(f"[index] {len(rows)} 条（保留 search_mode 富化 {n_kept} 条）→ {p}")


