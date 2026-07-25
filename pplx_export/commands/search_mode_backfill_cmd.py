"""cmd: search-mode-backfill — backfill the platform-authoritative search_mode field
into the library index.

Background: library index rows (GraphQL LibraryThreadsRelayQuery) do not carry
search_mode, so `batch --mode` can only filter by the mode/displayModel heuristics
(observed: study threads with displayModel=pplx_beta are missed by --mode study).
This command backfills the archive-side authoritative signal into the index rows so
that --mode filtering can use the authoritative SEARCH_MODE_MAP mapping.

Field semantics (the ``search_mode`` key written back into index rows):
  stores the **platform raw value** (SEARCH / RESEARCH / ASI / AGENTIC_RESEARCH /
  STUDY / STUDIO...) with no mode-name normalization — when a thread carries
  multiple values, the most specific one by specificity
  computer>council>study>deep-research>search wins and its corresponding raw value
  is written back (normalize.aggregate_search_mode, the same aggregation rule as
  detect_mode).

Extraction order (local first, online fallback):
  1. Local: for archived threads (directory found under web_archive by uuid8 plus an
     exact thread.json web_uuid match), extract from entries[].search_mode in
     raw_entries.json — zero network;
  2. Online fallback: only for index rows without local raw data, extract online via
     GET /rest/thread/<uuid> (plain). Threads in expired terminal state in
     batch_state are skipped and faithfully recorded (not retried); threads newly
     found ENTRY_EXPIRED online are marked in batch_state (sparing future requests).
     Rate discipline as in batch: 10-20s random interval per thread, no concurrency,
     429/5xx backed off by the transport layer; auth failures raise immediately
     (fail-fast).

Idempotent and resumable: rows that already have search_mode are skipped; progress
is saved every 25 rows, and reruns after interruption only process the remaining
rows. An index refresh preserves this command's enrichment through cmd_index's
merge logic.

cmd：search-mode-backfill —— 给 library 索引补平台权威 search_mode 字段。

背景：library 索引行（GraphQL LibraryThreadsRelayQuery）不含 search_mode，
`batch --mode` 只能靠 mode/displayModel 启发式过滤（实测 study 线程
displayModel=pplx_beta 会被 --mode study 漏掉）。本命令把归档侧权威判别信号
补进索引行，使 --mode 过滤可走 SEARCH_MODE_MAP 权威映射。

字段语义（写回索引行的 ``search_mode`` 键）：
  存**平台原始值**（SEARCH / RESEARCH / ASI / AGENTIC_RESEARCH / STUDY /
  STUDIO…），不做模式名归一——线程内多值时按特异性
  computer>council>study>deep-research>search 取最高后写回对应的一个原始值
  （normalize.aggregate_search_mode，与 detect_mode 同一聚合规则）。

提取顺序（本地优先，联网兜底）：
  1. 本地：已归档线程（web_archive 下按 uuid8 + thread.json web_uuid 全等
     找到目录）从 raw_entries.json 的 entries[].search_mode 提取，零网络；
  2. 联网兜底：仅本地无 raw 的索引行走 GET /rest/thread/<uuid>（plain）
     在线提取。batch_state 中 expired 终态线程直接跳过并如实记录（不重试）；
     在线新发现 ENTRY_EXPIRED 的标记进 batch_state（下轮免请求）。
     限频纪律同 batch：每线程 10–20s 随机间隔、无并发、429/5xx 由
     transport 层退避；鉴权失败立即抛错（fail-fast）。

幂等可续跑：已有 search_mode 的索引行跳过；每 25 条中途落盘，中断后重跑
只处理剩余行。index 刷新会经 cmd_index 的合并逻辑保留本命令的富化结果。
"""

from __future__ import annotations

import json
from pathlib import Path

from ..core.errors import EntryDeletedError, EntryExpiredError
from ..core.logging import get_logger
from ..core.state import BatchState
from ..core.throttle import Throttle
from ..sites.perplexity.fs_writer import FilesystemWriter
from ..sites.perplexity.normalize import aggregate_search_mode

log = get_logger("cli")


def _write_index(lib_path: Path, doc: dict) -> None:
    lib_path.parent.mkdir(parents=True, exist_ok=True)
    lib_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1))


def cmd_search_mode_backfill(adapter_factory, account, out_root: Path, limit=None,
                             delay_min: float = 10.0, delay_max: float = 20.0,
                             online: bool = True):
    """Backfill the search_mode key for each row of library_<account>.json
    (semantics in the module docstring).

    adapter_factory: lazy adapter factory (signature adapter_factory(throttle=...)),
    invoked only when the online fallback is actually needed — fully local runs
    touch the network zero times.

    补全 library_<account>.json 各行的 search_mode 键（语义见模块 docstring）。

    adapter_factory：惰性适配器工厂（签名为 adapter_factory(throttle=...)），
    只有确需联网兜底时才调用——纯本地可解时全程零网络。
    """
    lib = out_root / "index" / f"library_{account.username}.json"
    if not lib.exists():
        raise SystemExit(f"[ERROR] 索引不存在，先运行 index: {lib}")
    doc = json.loads(lib.read_text())
    rows = doc.get("threads", [])
    state = BatchState(out_root / "index" / "batch_state.json")
    writer = FilesystemWriter(out_root)

    pending = [t for t in rows if t.get("entryUUID") and not t.get("search_mode")]
    if limit:
        pending = pending[:limit]
    log.info(f"[search-mode] 待补 {len(pending)} 条（索引共 {len(rows)} 行，"
             f"已富化 {len(rows) - len(pending)} 行跳过）")

    # Lazy: no transport is built when everything resolves locally (not even a session probe)
    # 惰性：本地全解时不建 transport（连 session 探测都没有）
    adapter = None
    throttle = Throttle(delay_min, delay_max)
    local = online_ok = expired_skip = fail = 0
    enriched_since_save = 0
    for i, t in enumerate(pending, 1):
        uuid = t["entryUUID"]
        title = (t.get("title") or "")[:45]
        if state.is_expired(uuid):
            expired_skip += 1
            log.info(f"[search-mode {i}/{len(pending)}] expired 终态，跳过: {title}")
            continue
        # 1) Local first: raw_entries.json (uuid8 archive-wide lookup + exact web_uuid check)
        # 1) 本地优先：raw_entries.json（uuid8 全库查找 + web_uuid 全等核验）
        value = ""
        for d in writer.find_thread_dirs(uuid):
            raw = d / "raw_entries.json"
            if not raw.exists():
                continue
            try:
                value = aggregate_search_mode(
                    (json.loads(raw.read_text()) or {}).get("entries"))
            except Exception as e:
                log.warning(f"[search-mode] {uuid[:8]} raw_entries.json 读取失败: {e}")
            if value:
                break
        if value:
            t["search_mode"] = value
            local += 1
            enriched_since_save += 1
            log.info(f"[search-mode {i}/{len(pending)}] 本地 → {value}: {title}")
        elif not online:
            fail += 1
            log.info(f"[search-mode {i}/{len(pending)}] 本地无 raw，--offline 不联网，"
                     f"留待下轮: {title}")
            continue
        else:
            # 2) Online fallback: GET /rest/thread/<uuid> (plain, with pagination)
            # 2) 联网兜底：GET /rest/thread/<uuid>（plain，含翻页）
            if adapter is None:
                adapter = adapter_factory(throttle=throttle)
            try:
                plain = adapter.fetcher.get_thread(uuid)
                value = aggregate_search_mode(plain.get("entries"))
                if value:
                    t["search_mode"] = value
                    online_ok += 1
                    enriched_since_save += 1
                    log.info(f"[search-mode {i}/{len(pending)}] 在线 → {value}: {title}")
                else:
                    fail += 1
                    log.warning(f"[search-mode {i}/{len(pending)}] 在线响应无 "
                                f"search_mode，留待下轮: {title}")
            except EntryDeletedError:
                # Note: EntryDeletedError is a subclass of EntryExpiredError and must
                # be caught first
                # 注意：EntryDeletedError 是 EntryExpiredError 子类，必须先于它捕获
                expired_skip += 1
                state.mark_deleted(uuid, t.get("lastUpdated"), t.get("title") or "",
                                   "ENTRY_DELETED（用户/远端已删除，不可恢复）")
                state.save()
                log.info(f"[search-mode {i}/{len(pending)}] 远端已删除，"
                         f"标记 deleted: {title}")
            except EntryExpiredError:
                expired_skip += 1
                state.mark_expired(uuid, t.get("lastUpdated"), t.get("title") or "",
                                   "ENTRY_EXPIRED（平台已清除，不可恢复）")
                state.save()
                log.info(f"[search-mode {i}/{len(pending)}] 平台已清除，"
                         f"标记 expired: {title}")
            except Exception as e:
                fail += 1
                log.warning(f"[search-mode {i}/{len(pending)}] 在线提取失败"
                            f"（留待下轮）: {str(e)[:100]}")
            throttle.delay()
        if enriched_since_save >= 25:
            _write_index(lib, doc)
            enriched_since_save = 0
            log.info(f"[search-mode] 中途落盘（{i}/{len(pending)}）")
    _write_index(lib, doc)
    log.info(f"[search-mode] 完成: 本地 {local} / 在线 {online_ok} / "
             f"expired 跳过 {expired_skip} / 未解决 {fail} → {lib}")
