"""cmd: sync-deleted — identify "remotely deleted" threads and tombstone the local archive.

Background and the local-archive retention principle:
  This repo is the only persistent backup of the user's Perplexity
  conversations — after the user deletes a conversation remotely (e.g. in a BOT
  space), the local archive must be kept exactly as-is (that is the very reason
  this repo exists). This command only does "identify + mark" (tombstone): it
  **never deletes or moves any local archive file**; it only changes the
  batch_state status and one marker key in thread.json.

Terminal-state semantics (alongside expired):
    expired = the platform returned ENTRY_EXPIRED at export time (platform-side
      purge, ~3-month window);
    deleted = gone from the exporting account's library index + confirmed by
      online verification (user deletion / remote removal).
  Both are terminal: batch incremental planning (plan_incremental) treats
  deleted the same as expired — terminal states are not retried, and --force
  does not re-export either; the batch_state note field records the
  confirmation reason.

Candidate detection (offline, cross-account union):
  A thread with status=ok in batch_state that is missing from the entryUUID
  union of **all** index/library_*.json account indexes → suspected
  remotely-deleted candidate (any index containing the uuid counts as alive).
  Why the union is required: a thread owned by account B and exported by A via
  a shared space (thread.json export_via=A) never appears in A's own index — a
  single-account diff would false-positive that whole set of threads. When all
  indexes are missing/unreadable, skip safely and advise running index first.
  The candidate's account field comes from thread.json export_via (falls back
  to --account when missing); it only selects the adapter account (with
  automatic cookie switching) for --online verification and plays no part in
  candidate detection.

Confirmation (--online):
  Per candidate, GET /rest/thread/<uuid> (adapter built for the candidate's
  export_via account):
    ENTRY_DELETED / ENTRY_EXPIRED / HTTP 404 → confirmed deletion: batch_state
      marks terminal deleted (note records the confirmation reason), and each
      of the thread's directories gets "remote_deleted": "<ISO time>" added to
      thread.json in place (idempotent: an existing key is neither rewritten
      nor overwritten);
    thread still exists → false positive: reported as-is (the index may not be
      fully refreshed; re-check after rerunning index), no state changed;
    other transport errors (5xx/network) → no state change; back off and leave
      for the next round;
    consecutive auth failures (401/403) reaching the limit → fail-fast abort
      (backoff cannot self-heal an expired cookie; spinning on would mis-mark
      live threads).
  Same throttle discipline as batch: 10–20s random interval between candidates,
  no concurrency, 429/5xx backed off by the transport layer.

Offline by default (dry-run semantics): only lists candidates and safe-skip
reasons; no network, no file changes.

cmd：sync-deleted —— 识别「远端已删除」线程并给本地归档打墓碑标记。

背景与本地归档保留原则：
  本仓库是 Perplexity 对话的唯一持久化备份——用户在远端（如 BOT 空间）删除
  对话后，本地归档必须原样保留（这正是仓库存在的理由）。本命令只做
  「识别 + 标记」（tombstone）：**绝不删除、不移动任何本地归档文件**，
  只改 batch_state 状态与 thread.json 的一个标记键。

终态语义区分（与 expired 并列）：
    expired = 导出时平台返回 ENTRY_EXPIRED（平台侧清除，约 3 个月窗口）；
    deleted = 已从导出账户 library 索引消失 + 在线验证确认（用户删除/远端移除）。
  两者均为终态：batch 增量计划（plan_incremental）对 deleted 与 expired 同等
  处理——终态不重试，--force 也不重导；batch_state 的 note 字段记录确认原因。

候选判定（离线，跨账户并集）：
  batch_state 中 status=ok 的线程，在**所有** index/library_*.json 账户索引的
  entryUUID 并集中均消失 → 疑似远端删除候选（任一索引含该 uuid 即视为存活）。
  并集判定的必要性：账户 B 拥有、经共享空间由 A 导出的线程（thread.json
  export_via=A）永远不会出现在 A 自己的索引里——单账户 diff 会把这批线程
  全部误报。全部索引缺失/不可读时安全跳过并提示先跑 index。
  候选的 account 字段取 thread.json export_via（缺失回退 --account），
  仅供 --online 验证时选择适配器账户（cookie 自动切换），不参与候选判定。

确认（--online）：
  逐候选 GET /rest/thread/<uuid>（按候选 export_via 账户构造适配器）：
    ENTRY_DELETED / ENTRY_EXPIRED / HTTP 404 → 确认删除：batch_state 标记终态
      deleted（note 记确认原因），并给该线程各目录的 thread.json 就地加
      "remote_deleted": "<ISO 时间>"（幂等：已有该键不重复写、不覆盖原时间）；
    线程仍存在 → 误报：如实报告（索引可能未刷新完整，重跑 index 后复核），
      不改任何状态；
    其他传输错误（5xx/网络）→ 不改状态，退避留待下轮；
    连续鉴权失败（401/403）达到上限 → fail-fast 中止（cookie 失效时退避无法
      自愈，空转会把活线程误标）。
  限频纪律同 batch：候选间 10–20s 随机间隔、无并发、429/5xx 由 transport 层退避。

默认离线（dry-run 语义）：只列出候选与安全跳过原因，不联网、不改任何文件。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..core.errors import (AuthTransportError, EntryDeletedError,
                           EntryExpiredError, TransportError)
from ..core.logging import get_logger
from ..core.state import BatchState
from ..core.throttle import Throttle
from ..sites.perplexity.fs_writer import FilesystemWriter

log = get_logger("cli")

# Same discipline as batch: abort once consecutive auth failures reach this count
# (backoff cannot self-heal an expired cookie)
# 与 batch 同一纪律：连续鉴权失败达到此次数即中止（cookie 失效时退避无法自愈）
_AUTH_FAIL_FAST = 3


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_all_index_uuids(out_root: Path) -> tuple[set | None, list[str]]:
    """Load the entryUUID union of all index/library_*.json files (cross-account liveness check).

    Returns (uuids, accounts): uuids is None when no usable index exists (all
    missing/unreadable; the caller skips safely); accounts is the list of account
    names whose indexes were read successfully (visible in logs).

    加载全部 index/library_*.json 的 entryUUID 并集（跨账户存活判定）。

    返回 (uuids, accounts)：uuids 为 None 表示没有任何可用索引（全缺失/全不可读，
    调用方安全跳过）；accounts 为成功读取的索引账户名列表（日志可见）。
    """
    idx_dir = Path(out_root) / "index"
    files = sorted(idx_dir.glob("library_*.json")) if idx_dir.exists() else []
    uuids: set = set()
    accounts: list[str] = []
    for p in files:
        try:
            doc = json.loads(p.read_text())
        except Exception as e:
            log.warning(f"[sync-deleted] 索引读取失败 {p}: {e}")
            continue
        accounts.append(p.stem[len("library_"):])
        uuids.update(t.get("entryUUID") for t in doc.get("threads", [])
                     if t.get("entryUUID"))
    if not accounts:
        return None, []
    return uuids, accounts


def find_candidates(out_root: Path, default_account: str) -> tuple[list[dict], list[dict]]:
    """Offline candidate detection (purely local, zero network): an ok thread missing
    from the union of **all** account indexes → candidate.

    Any index containing the uuid counts as alive (cross-account exported threads
    only appear in the owner account's index; a single-account diff would
    false-positive all of them — the 14 fake candidates seen in practice were
    exactly this). The candidate's account field comes from thread.json
    export_via (falls back to --account when missing); it only selects the
    adapter account for --online verification and plays no part in candidate
    detection.

    Returns (candidates, skipped):
      candidates = [{"uuid","title","lastUpdated","account","thread_dirs"}],
        sorted by lastUpdated descending (same list semantics as batch, stable
        output);
      skipped = [{"uuid","title","reason"}] — safely skipped when all indexes
        are missing/unreadable, with the reason recorded faithfully.

    离线候选检测（纯本地，零网络）：ok 线程在**所有**账户索引并集中均消失 → 候选。

    任一索引含该 uuid 即视为存活（跨账户导出线程只出现在所有者账户索引里，
    单账户 diff 会把它们全部误报——实测 14 条假候选即此因）。
    候选的 account 字段取 thread.json export_via（缺失回退 --account），仅供
    --online 验证时选择适配器账户，不参与候选判定。

    返回 (candidates, skipped)：
      candidates = [{"uuid","title","lastUpdated","account","thread_dirs"}]，
        按 lastUpdated 降序（与 batch 列表语义一致，输出稳定）；
      skipped = [{"uuid","title","reason"}]——全部索引缺失/不可读时安全跳过，
        如实记录原因。
    """
    out_root = Path(out_root)
    state = BatchState(out_root / "index" / "batch_state.json")
    ok_entries = sorted((u, st) for u, st in state.state.items()
                        if (st or {}).get("status") == "ok")
    uuids, accounts = _load_all_index_uuids(out_root)
    if uuids is None:
        return [], [{"uuid": u, "title": (st or {}).get("title") or "",
                     "reason": "无可用账户索引，先运行 index"}
                    for u, st in ok_entries]
    writer = FilesystemWriter(out_root)
    candidates: list[dict] = []
    for uuid, st in ok_entries:
        if uuid in uuids:
            continue
        thread_dirs = writer.find_thread_dirs(uuid)
        # export_via only selects the account for online verification (shared-space
        # threads may have been exported via another account); falls back to --account when missing
        # export_via 仅供在线验证选择账户（共享空间线程可能经他账户导出），缺失回退 --account
        acct = ""
        for d in thread_dirs:
            try:
                acct = json.loads((d / "thread.json").read_text()).get("export_via") or ""
            except Exception:
                continue
            if acct:
                break
        if not acct:
            acct = default_account
        candidates.append({"uuid": uuid, "title": st.get("title") or "",
                           "lastUpdated": st.get("lastUpdated"),
                           "account": acct, "thread_dirs": thread_dirs})
    candidates.sort(key=lambda c: c.get("lastUpdated") or "", reverse=True)
    return candidates, []


def mark_thread_json_remote_deleted(thread_dirs: list[Path], ts: str) -> int:
    """Add the remote_deleted key in place to each thread directory's thread.json
    (tombstone marker).

    Idempotent: directories already having the key are skipped (no rewrite, no
    overwriting the original timestamp); only this one key is added, all other
    fields stay as-is. Returns the number of directories actually written.
    Never deletes/moves any archive file.

    给线程各目录的 thread.json 就地加 remote_deleted 键（tombstone 标记）。

    幂等：已有该键的目录跳过（不重复写、不覆盖原时间）；只增这一个键，
    其余字段原样。返回实际写盘的目录数。绝不删除/移动任何归档文件。
    """
    n = 0
    for d in thread_dirs:
        tjp = Path(d) / "thread.json"
        if not tjp.exists():
            continue
        try:
            tj = json.loads(tjp.read_text())
        except Exception as e:
            log.warning(f"[sync-deleted] thread.json 读取失败 {tjp}: {e}")
            continue
        if tj.get("remote_deleted"):
            continue
        tj["remote_deleted"] = ts
        tjp.write_text(json.dumps(tj, ensure_ascii=False, indent=1))
        n += 1
    return n


def _confirm_deleted(state: BatchState, c: dict, note: str) -> None:
    """Confirmed deletion: mark terminal deleted in batch_state + stamp remote_deleted
    in place in thread.json.

    确认删除：batch_state 标记终态 deleted + thread.json 就地打 remote_deleted。"""
    state.mark_deleted(c["uuid"], c.get("lastUpdated"), c.get("title") or "", note)
    n = mark_thread_json_remote_deleted(c["thread_dirs"], _now_iso())
    # Persist per item: confirmed marks survive an interruption; reruns are idempotent
    # 逐条落盘：中断后已确认的不丢，重跑幂等
    state.save()
    if not n:
        log.warning(f"[sync-deleted] {c['uuid'][:8]} 未找到可标记的 thread.json"
                    f"（仅 batch_state 已标记 deleted）")


def cmd_sync_deleted(adapter_factory, account, out_root: Path, limit=None,
                     delay_min: float = 10.0, delay_max: float = 20.0,
                     online: bool = False):
    """Identify remotely deleted threads and mark them (semantics and discipline:
    see module docstring).

    adapter_factory: lazy adapter factory (signature adapter_factory(username,
    throttle=...)), built per candidate's exporting account (automatic
    multi-account cookie switching); never called in offline mode (zero network).

    识别远端已删除线程并打标记（语义与纪律见模块 docstring）。

    adapter_factory：惰性适配器工厂（签名为 adapter_factory(username, throttle=...)），
    按候选的导出账户构造（多账户 cookie 自动切换）；离线模式全程不调用（零网络）。
    """
    out_root = Path(out_root)
    candidates, skipped = find_candidates(out_root, account.username)
    for s in skipped:
        log.info(f"[sync-deleted] 安全跳过: {(s['title'] or s['uuid'][:8])[:45]}"
                 f" —— {s['reason']}")
    if limit:
        candidates = candidates[:limit]
    log.info(f"[sync-deleted] 疑似远端删除候选 {len(candidates)} 条"
             f"（安全跳过 {len(skipped)} 条）")
    for i, c in enumerate(candidates, 1):
        log.info(f"[sync-deleted 候选 {i}/{len(candidates)}] [{c['account']}] "
                 f"{c['uuid'][:8]} {(c['title'] or '')[:45]}")
    if not online:
        if candidates:
            log.info("[sync-deleted] 离线模式仅列出候选（dry-run），未联网、未改任何文件；"
                     "确认无误后加 --online 逐条在线验证")
        return

    state = BatchState(out_root / "index" / "batch_state.json")
    throttle = Throttle(delay_min, delay_max)
    # Lazily built per exporting account (cookie auto-switching is handled by the transport layer)
    # 按导出账户惰性构造（cookie 自动切换由 transport 层负责）
    adapters: dict = {}
    confirmed = false_pos = fail = auth_fails = 0
    for i, c in enumerate(candidates, 1):
        uuid, title, acct = c["uuid"], (c["title"] or "")[:45], c["account"]
        if acct not in adapters:
            adapters[acct] = adapter_factory(acct, throttle=throttle)
        adapter = adapters[acct]
        try:
            adapter.fetcher.get_thread(uuid)
        except EntryDeletedError:
            # Note: EntryDeletedError is a subclass of EntryExpiredError and must be caught first
            # 注意：EntryDeletedError 是 EntryExpiredError 子类，必须先于它捕获
            confirmed += 1
            # A response that reached the server proves the cookie is valid
            # 成功到达服务器的响应，证明 cookie 有效
            auth_fails = 0
            _confirm_deleted(state, c, "索引消失 + GET thread 返回 ENTRY_DELETED（用户/远端已删除）")
            log.info(f"[sync-deleted {i}/{len(candidates)}] 确认删除（ENTRY_DELETED），"
                     f"标记 deleted: {title}")
        except EntryExpiredError:
            confirmed += 1
            # A response that reached the server proves the cookie is valid
            # 成功到达服务器的响应，证明 cookie 有效
            auth_fails = 0
            _confirm_deleted(state, c, "索引消失 + GET thread 返回 ENTRY_EXPIRED（远端已删除）")
            log.info(f"[sync-deleted {i}/{len(candidates)}] 确认删除（ENTRY_EXPIRED），"
                     f"标记 deleted: {title}")
        except AuthTransportError as e:
            # Note: AuthTransportError is a subclass of TransportError and must be caught first
            # 注意：AuthTransportError 是 TransportError 子类，必须先于它捕获
            auth_fails += 1
            fail += 1
            log.warning(f"[sync-deleted] 鉴权失败（连续 {auth_fails}/{_AUTH_FAIL_FAST}）: "
                        f"{str(e)[:100]}")
            if auth_fails >= _AUTH_FAIL_FAST:
                state.save()
                raise SystemExit(
                    f"[sync-deleted][ERROR] 连续 {_AUTH_FAIL_FAST} 次鉴权失败（401/403）——"
                    f"cookie 很可能已失效，中止以免误标。请更新 cookie 后重试。")
        except TransportError as e:
            if "HTTP 404" in str(e):
                # Candidate already missing from the index + 404: two pieces of evidence
                # confirm deletion (the transient 404 of a thread newly created by
                # pplx-ask never becomes a candidate — it is neither in batch_state ok
                # nor archived)
                # 候选已索引消失 + 404：双重证据确认删除（pplx-ask 新建线程的瞬态
                # 404 不会成为候选——它既不在 batch_state  ok 里也没有归档）
                confirmed += 1
                auth_fails = 0
                _confirm_deleted(state, c, "索引消失 + GET thread 返回 HTTP 404（远端已删除）")
                log.info(f"[sync-deleted {i}/{len(candidates)}] 确认删除（404），"
                         f"标记 deleted: {title}")
            else:
                fail += 1
                log.warning(f"[sync-deleted {i}/{len(candidates)}] 验证失败"
                            f"（不改状态，留待下轮）: {str(e)[:100]}")
                throttle.backoff()
        except Exception as e:
            fail += 1
            log.warning(f"[sync-deleted {i}/{len(candidates)}] 验证异常"
                        f"（不改状态，留待下轮）: {str(e)[:100]}")
            throttle.backoff()
        else:
            # Thread still exists → false positive: change no state, report possible causes faithfully
            # 线程仍存在 → 误报：不改任何状态，如实报告可能原因
            false_pos += 1
            auth_fails = 0
            log.info(f"[sync-deleted {i}/{len(candidates)}] 线程仍存在——误报"
                     f"（索引可能未刷新完整，重跑 index --account {acct} 后复核）: {title}")
        if i < len(candidates):
            throttle.delay()
    state.save()
    log.info(f"[sync-deleted] 完成: 确认删除 {confirmed} / 误报 {false_pos} / "
             f"验证失败 {fail}（候选 {len(candidates)}）")
