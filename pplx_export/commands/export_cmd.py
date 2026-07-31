"""cmd: export — export a single thread.

cmd：export —— 导出单个线程。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..core.errors import EntryDeletedError, EntryExpiredError
from ..core.logging import get_logger
from ..core.state import BatchState
from ..sites.perplexity.fs_writer import FilesystemWriter
from .common import update_last_export, maybe_auto_commit

log = get_logger("cli")


def _idx_thread_for(out_root: Path, uuid: str) -> dict | None:
    """Look up the thread's index row in the local library index (V5-01): the
    single-export path also takes lastUpdated from the platform index's updatedAt
    (microsecond ISO), sharing semantics and format with batch/state;
    returns None when not found (index not refreshed / another account's thread),
    and the adapter falls back to the true ISO value.

    从本地 library 索引查该线程的索引行（V5-01）：单导路径也让 lastUpdated
    取平台索引 updatedAt（微秒 ISO），与 batch/state 同语义同格式；
    查不到（索引未刷新/他账户线程）返回 None，由 adapter 兜底真 ISO。
    """
    for f in sorted((out_root / "index").glob("library_*.json")):
        try:
            doc = json.loads(f.read_text())
        except Exception:
            continue
        for t in doc.get("threads", []):
            if t.get("entryUUID") == uuid:
                return t
    return None


def cmd_export(adapter, writer: FilesystemWriter, url_or_uuid: str, account, force: bool,
               out_root: Path):
    m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", url_or_uuid)
    if not m:
        raise SystemExit(f"[ERROR] 无法解析 UUID: {url_or_uuid}")
    uuid = m.group(1)
    url = url_or_uuid if url_or_uuid.startswith("http") else f"https://www.perplexity.ai/search/{uuid}"
    try:
        conv = adapter.get_thread(uuid, url=url, idx_thread=_idx_thread_for(out_root, uuid))
    except EntryDeletedError:
        # Note: EntryDeletedError is a subclass of EntryExpiredError and must be caught first
        # Terminal-state registration (same semantics as batch); the local archive is
        # kept untouched — exit gracefully without a traceback
        # 注意：EntryDeletedError 是 EntryExpiredError 子类，必须先于它捕获
        # 终态登记（与 batch 同语义），本地归档保留不动——优雅退出不 traceback
        state = BatchState(out_root / "index" / "batch_state.json")
        prev = state.get(uuid)
        state.mark_deleted(uuid, prev.get("lastUpdated"), prev.get("title") or "",
                           "ENTRY_DELETED（用户/远端已删除，不可恢复）")
        state.save()
        raise SystemExit(f"[export] 线程已被用户/远端删除（ENTRY_DELETED），无法导出: {uuid}\n"
                         f"  batch_state 已标记终态 deleted；本地已有归档保持原样（本仓库即备份）。")
    except EntryExpiredError:
        state = BatchState(out_root / "index" / "batch_state.json")
        prev = state.get(uuid)
        state.mark_expired(uuid, prev.get("lastUpdated"), prev.get("title") or "",
                           "ENTRY_EXPIRED（平台已清除，不可恢复）")
        state.save()
        raise SystemExit(f"[export] 线程已被平台清除（ENTRY_EXPIRED），无法导出: {uuid}\n"
                         f"  batch_state 已标记终态 expired；本地已有归档保持原样（本仓库即备份）。")
    conv.export_via = account.username
    conv.author = conv.author or account.folder
    thread_dir = writer.thread_dir_for(conv)
    if not force and writer.is_unchanged(conv, thread_dir):
        log.info(f"[export] 未变化，跳过: {thread_dir}")
        return
    conv.assets = adapter.get_assets(conv, dest_dir=thread_dir / "assets" / "files")
    out = writer.write_thread(conv, adapter=adapter)
    # Write back batch state: a single export also counts as "exported and unchanged"
    # so the incremental plan can see it
    # 回写批量状态：单条导出同样计入「已导出且未变」，增量计划才看得到
    state = BatchState(out_root / "index" / "batch_state.json")
    state.mark_ok(uuid, conv.last_updated, conv.title)
    state.save()
    update_last_export()
    maybe_auto_commit(out_root, account=account.username)
    log.info(f"[export] 完成 → {out}（{conv.mode}，{conv.n_turns} 轮，引文 {len(conv.citations)}，资产 {len(conv.assets)}）")


