"""cmd: index — extract the account's conversation list index.

Default is an incremental refresh: page NEWEST-first and stop once a full
page's worth of consecutive rows is already known and unchanged, then merge
the fetched head onto the existing library (older rows are carried over
verbatim). `--full` restores the complete sweep that rewrites the library.

The incremental path cannot observe remote deletions or space changes of
older threads (they never appear in the fetched head). Deletion authority
stays with `sync-deleted --online`; the library document counts incremental
runs since the last full sweep and warns when a full reconciliation is due.

cmd：index —— 提取账户对话列表索引。

默认增量刷新：按 NEWEST 翻页，遇到「连续一整页都已知且未变」即停，把抓到的
头部合并到既有库上（更旧的行原样保留）。`--full` 恢复全量翻页并整体重写。

增量路径看不到旧线程的远端删除与空间变更（它们不会出现在抓取的头部）。
删除权威仍是 `sync-deleted --online`；库文档记录距上次全量的增量次数，
到期提醒做一次全量对账。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..core.fsio import atomic_write_text
from ..core.logging import get_logger

log = get_logger("cli")

# One full page (graphql.list_threads pages by 25) of consecutive known-unchanged
# rows means the head has caught up with the existing library — stop paging.
# 连续一整页（graphql.list_threads 每页 25）已知且未变，说明头部已追上旧库——停止翻页。
_STOP_RUN = 25
# After this many incremental runs without a full sweep, warn that remote
# deletions / space changes of older threads may have gone unnoticed.
# 连续这么多次增量而无全量后告警：旧线程的远端删除/空间变更可能一直未被发现。
_FULL_REMINDER_RUNS = 10


def cmd_index(adapter, account, out_root: Path, full: bool = False):
    p = out_root / "index" / f"library_{account.username}.json"
    old_doc: dict = {}
    if p.exists():
        try:
            old_doc = json.loads(p.read_text())
        except Exception as e:
            log.warning(f"[index] 旧索引读取失败，本次按全量处理（search_mode 富化将无法保留）: {e}")
            old_doc = {}
    old_rows = old_doc.get("threads") or []
    old_by_uuid = {t["entryUUID"]: t for t in old_rows if t.get("entryUUID")}
    # Preserve the enrichment written by search-mode-backfill: GraphQL index rows do
    # not carry search_mode themselves, and a refresh would wash away the backfilled
    # field — merge it back from the old index by entryUUID
    # 保留 search-mode-backfill 的富化结果：GraphQL 索引行本身不含 search_mode，
    # 刷新会冲掉已补字段——按 entryUUID 从旧索引合并回来
    old_sm = {u: t["search_mode"] for u, t in old_by_uuid.items() if t.get("search_mode")}

    incremental = (not full) and bool(old_by_uuid)
    fetched: list[dict] = []
    changed = 0
    run = 0
    stopped_early = False
    # Early-stop relies on list_threads being ordered newest-by-updatedAt (graphql
    # sortOrder NEWEST → node.updatedAt → row.lastUpdated), so an edited older thread
    # resurfaces in the fetched head; a --full sweep is the backstop if that ever drifts.
    # 早停依赖 list_threads 按 updatedAt 从新到旧（graphql NEWEST → updatedAt → lastUpdated），
    # 被编辑的旧线程会浮回头部；若该前提漂移，--full 全量为兜底。
    for t in adapter.list_threads(account):
        fetched.append(t)
        u = t.get("entryUUID")
        known_unchanged = (u in old_by_uuid
                           and t.get("lastUpdated")
                           and old_by_uuid[u].get("lastUpdated") == t.get("lastUpdated"))
        if known_unchanged:
            run += 1
        else:
            run = 0
            changed += 1
        if incremental and run >= _STOP_RUN:
            # Stopping consumption closes the lazy pagination — no further requests.
            # 停止消费即终止惰性翻页——不再发请求。
            stopped_early = True
            break

    n_kept = 0
    for t in fetched:
        sm = old_sm.get(t.get("entryUUID") or "")
        if sm:
            t["search_mode"] = sm
            n_kept += 1

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # A partial refresh only happened if we actually early-stopped; an incremental run
    # that exhausted pagination paged the whole library and is a full reconciliation.
    # 只有真正早停才是部分刷新；增量却翻到尽头意味着已全量翻页，等同一次全量对账。
    partial = incremental and stopped_early
    if partial:
        seen = {u for u in (t.get("entryUUID") for t in fetched) if u}
        # Carry over old rows not in the fetched head; keep uuid-less rows (dedup only
        # applies when an entryUUID is present) so incremental never drops what --full keeps.
        # 沿用未出现在头部的旧行；缺 entryUUID 的行原样保留（仅在有 uuid 时去重），
        # 使增量不会丢弃 --full 会保留的行。
        tail = [t for t in old_rows if (not t.get("entryUUID")) or t["entryUUID"] not in seen]
        rows = fetched + tail
        # Legacy docs (pre-incremental) were always full sweeps: their extracted_at
        # is the last full reconciliation.
        # 旧文档（增量之前）都是全量：其 extracted_at 即上次全量对账时间。
        last_full = old_doc.get("last_full_index_at") or old_doc.get("extracted_at") or ""
        runs_since = int(old_doc.get("incremental_runs_since_full") or 0) + 1
    else:
        rows = fetched
        tail = []
        last_full = now
        runs_since = 0

    doc = {"account": account.username, "extracted_at": now,
           "count": len(rows), "threads": rows,
           "last_full_index_at": last_full,
           "incremental_runs_since_full": runs_since}
    atomic_write_text(p, json.dumps(doc, ensure_ascii=False, indent=1))
    if partial:
        log.info(f"[index] 增量：抓取 {len(fetched)} 行（新增/更新 {changed} 条，到已知边界早停），"
                 f"沿用旧库 {len(tail)} 条 → 共 {len(rows)} 条 → {p}")
        if runs_since >= _FULL_REMINDER_RUNS:
            log.warning(f"[index] 已连续 {runs_since} 次增量刷新未做全量对账——增量看不到"
                        f"旧线程的远端删除与空间变更，建议运行一次 `pplx-export index --full`"
                        f"（或 `sync --full`），并配合 `sync-deleted --online` 标记远端删除")
    else:
        log.info(f"[index] {len(rows)} 条（保留 search_mode 富化 {n_kept} 条）→ {p}")
