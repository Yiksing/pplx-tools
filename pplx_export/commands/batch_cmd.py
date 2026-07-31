"""cmd: batch — bulk export (incremental early stop + resumable checkpoints).

cmd：batch —— 批量导出（增量早停 + 断点续跑）。
"""

from __future__ import annotations

import json
from pathlib import Path

from ..core.errors import AuthTransportError, EntryDeletedError, EntryExpiredError
from ..core.logging import get_logger
from ..core.models import Space
from ..core.state import BatchState
from ..core.throttle import Throttle
from ..hooks.incremental import plan_incremental
from ..sites.perplexity import variant_log
from ..sites.perplexity.fs_writer import FilesystemWriter
from ..sites.perplexity.normalize import SEARCH_MODE_MAP
from .common import report_account_status, update_last_export, maybe_auto_commit

log = get_logger("cli")

# Library index observations (2026-07): deep-research threads have mode=SEARCH and
# displayModel=pplx_alpha; computer threads have mode=COMPUTER; council threads have
# displayModel=pplx_agentic_research; study threads have displayModel=pplx_study;
# all remaining search threads have mode=SEARCH with other displayModel values.
# library 索引实测（2026-07）：深度研究线程 mode=SEARCH、displayModel=pplx_alpha；
# computer 线程 mode=COMPUTER；council 线程 displayModel=pplx_agentic_research；
# study 线程 displayModel=pplx_study；其余搜索线程 mode=SEARCH + 其他 displayModel。
_MODE_FILTER = {"computer": "COMPUTER", "search": "SEARCH"}
# Modes distinguished by displayModel (their index mode is SEARCH in all cases, so
# only displayModel can filter them)
# 按 displayModel 区分的模式（索引 mode 均为 SEARCH，只能靠 displayModel 过滤）
_MODE_DISPLAY_FILTER = {"deep-research": "pplx_alpha",
                        "council": "pplx_agentic_research",
                        "study": "pplx_study"}

# Abort the batch after this many consecutive auth failures (401/403): when the
# cookie has expired, backoff cannot heal itself and spinning on would only make
# hundreds of threads each fail once (hours of wasted time).
# 连续鉴权失败（401/403）达到此次数即中止 batch：cookie 失效时退避无法自愈，
# 空转只会让数百线程各失败一遍（数小时）。
_AUTH_FAIL_FAST = 3


def index_row_matches_mode(t: dict, mode_filter: str) -> bool:
    """Whether an index row matches the --mode filter: the authoritative search_mode
    wins when present, otherwise fall back to the legacy heuristics.

    - When the row carries search_mode (the platform's raw value enriched by
      search-mode-backfill), it is mapped through SEARCH_MODE_MAP to a canonical mode
      for an exact match (e.g. RESEARCH->deep-research, STUDIO->search) — on the
      authoritative path, --mode search no longer pulls in deep-research / council /
      study threads (which is exactly the point of the enrichment);
    - Without search_mode, fall back to the displayModel/mode heuristics, behaving
      exactly as before the enrichment (--mode search still matches broadly on index
      mode=SEARCH, including the three sub-mode thread kinds).

    索引行是否命中 --mode 过滤：search_mode 权威优先，缺失回落旧启发式。

    - 行内有 search_mode（search-mode-backfill 富化的平台原始值）时经
      SEARCH_MODE_MAP 映射为规范模式精确匹配（如 RESEARCH→deep-research、
      STUDIO→search）——权威路径下 --mode search 不再混入 deep-research/
      council/study 线程（这正是富化的目的）；
    - 无 search_mode 时回落 displayModel/mode 启发式，行为与富化前完全一致
      （--mode search 仍按索引 mode=SEARCH 宽匹配，含三类子模式线程）。
    """
    sm = (t.get("search_mode") or "").upper()
    if sm in SEARCH_MODE_MAP:
        return SEARCH_MODE_MAP[sm] == mode_filter
    if mode_filter in _MODE_DISPLAY_FILTER:
        return t.get("displayModel") == _MODE_DISPLAY_FILTER[mode_filter]
    return (t.get("mode") or "").upper() == _MODE_FILTER.get(mode_filter,
                                                            mode_filter.upper())


def cmd_batch(adapter, writer: FilesystemWriter, account, out_root: Path, limit, mode_filter, force,
              delay_min, delay_max, full=False, throttle: Throttle | None = None,
              verify_on_errors: bool = False):
    lib = out_root / "index" / f"library_{account.username}.json"
    if not lib.exists():
        raise SystemExit(f"[ERROR] 索引不存在，先运行 index: {lib}")
    doc = json.loads(lib.read_text())
    threads = doc.get("threads", [])
    if mode_filter:
        threads = [t for t in threads if index_row_matches_mode(t, mode_filter)]
    # Newest first: new conversations and resumed ones (lastUpdated moved newer) both
    # sit at the top, which is what makes early stop safe
    # 从新到旧：新对话与续接对话（lastUpdated 变新）都在顶部，早停才安全
    threads = sorted(threads, key=lambda t: t.get("lastUpdated") or "", reverse=True)
    if limit:
        threads = threads[:limit]
    # Tolerate bad entries: index rows missing entryUUID are skipped with a warning
    # instead of crashing the whole batch
    # 坏条目容错：缺 entryUUID 的索引行跳过 + warning，不崩整个 batch
    valid = []
    for t in threads:
        if t.get("entryUUID"):
            valid.append(t)
        else:
            log.warning(f"[batch] 索引条目缺 entryUUID，跳过: {(t.get('title') or str(t))[:60]}")
    state = BatchState(out_root / "index" / "batch_state.json")
    # Shared Throttle: the same instance as the transport layer's
    # (CookieTransport.throttle), so backoff counting never splits
    # 共享 Throttle：与传输层（CookieTransport.throttle）同一实例，退避计数不分裂
    throttle = throttle or Throttle(delay_min, delay_max)
    # Incremental plan (the pure function shared with scheduling): by default, early
    # stop trims the trailing run of terminal states
    # 增量计划（与调度共用的纯函数）：默认早停截掉尾部终态连续段
    actions, n_stopped = plan_incremental(valid, state, full=full, force=force)
    ok = skip = fail = auth_fails = variant_threads = 0
    # One-time deferred account check guard (only used when verify_on_errors is set by
    # --skip-auth-check): run the check the first time generic errors accumulate.
    # 一次性延迟账户校验标记（仅 --skip-auth-check 置 verify_on_errors 时用）：
    # 通用错误首次累积到阈值时校验一次。
    deferred_checked = False
    # total accounting (N-11): counts only the actually iterated actions plus the
    # early-stopped tail n_stopped (equal to len(valid)) — rows dropped for missing
    # entryUUID are excluded, so [batch i/total] matches the final ok+skip+fail
    # total 口径（N-11）：只计实际迭代的 actions + 早停尾段 n_stopped（等于 len(valid)），
    # 不含缺 entryUUID 被丢弃的行——保证 [batch i/total] 与末尾 ok+skip+fail 对得上
    total = len(actions) + n_stopped
    for i, (t, action) in enumerate(actions, 1):
        uuid = t.get("entryUUID")
        lu = t.get("lastUpdated")
        if action in ("expired", "deleted"):
            # Terminal states cleared by the platform / deleted remotely: never
            # retried, even with --force (a retry would only waste requests and backoff)
            # 平台已清除 / 远端已删除的终态：--force 也不重试（重试只会白费请求与退避）
            skip += 1
            reason = "已过期终态" if action == "expired" else "远端已删除终态"
            log.info(f"[batch {i}/{total}] {reason}，跳过: {(t.get('title') or '')[:45]}")
            continue
        if action == "done":
            skip += 1
            log.info(f"[batch {i}/{total}] 跳过: {(t.get('title') or '')[:45]}")
            continue
        log.info(f"[batch {i}/{total}] 导出: [{(t.get('mode') or '?')}] {(t.get('title') or '')[:55]}")
        try:
            url = (f"https://www.perplexity.ai/computer/tasks/{uuid}"
                   if (t.get("mode") or "").upper() in ("ASI", "COMPUTER")
                   else f"https://www.perplexity.ai/search/{uuid}")
            # Pass the index row as idx_thread (V5-01): lastUpdated uses the platform
            # index's updatedAt (microsecond ISO), sharing semantics and format with
            # batch_state / incremental early stop; space and mode redundancy signals
            # come from the same source
            # idx_thread 传入索引行（V5-01）：lastUpdated 用平台索引 updatedAt（微秒 ISO），
            # 与 batch_state/增量早停同一语义同一格式；space/模式冗余信号同源
            conv = adapter.get_thread(uuid, url=url, idx_thread=t)
            conv.export_via = account.username
            conv.author = conv.author or account.folder
            if getattr(conv, "answer_variants", None):
                variant_threads += 1
            if conv.space is None and t.get("space"):
                sp = t["space"]
                conv.space = Space(uuid=sp.get("uuid", ""), title=sp.get("title", ""), slug=sp.get("slug", ""))
            thread_dir = writer.thread_dir_for(conv)
            conv.assets = adapter.get_assets(conv, dest_dir=thread_dir / "assets" / "files")
            writer.write_thread(conv, adapter=adapter)
            state.mark_ok(uuid, lu, t.get("title") or "")
            ok += 1
            auth_fails = 0
            throttle.reset()
        except KeyboardInterrupt:
            state.save()
            log.info(f"\n[batch] 中断。ok={ok} skip={skip} fail={fail}")
            raise
        except Exception as e:
            if isinstance(e, EntryDeletedError):
                # Note: EntryDeletedError is a subclass of EntryExpiredError and must
                # be caught first
                # 注意：EntryDeletedError 是 EntryExpiredError 子类，必须先于它捕获
                state.mark_deleted(uuid, lu, t.get("title") or "",
                                   "ENTRY_DELETED（用户/远端已删除，不可恢复）")
                skip += 1
                # A response that reached the server (proving the cookie is valid):
                # reset the auth-failure counter
                # 成功到达服务器的响应（证明 cookie 有效）：重置鉴权计数
                auth_fails = 0
                log.info(f"[batch {i}/{total}] 远端已删除（ENTRY_DELETED），标记终态跳过")
            elif isinstance(e, EntryExpiredError):
                state.mark_expired(uuid, lu, t.get("title") or "",
                                   "ENTRY_EXPIRED（平台已清除，不可恢复）")
                skip += 1
                # expired is also a response that reached the server (proving the
                # cookie is valid): reset the auth-failure counter (F-12)
                # expired 是成功到达服务器的响应（证明 cookie 有效）：重置鉴权计数（F-12）
                auth_fails = 0
                log.info(f"[batch {i}/{total}] 已过期（平台已清除），标记跳过")
            elif isinstance(e, AuthTransportError):
                auth_fails += 1
                state.mark_error(uuid, lu, t.get("title") or "", str(e))
                fail += 1
                log.warning(f"[batch] 鉴权失败（连续 {auth_fails}/{_AUTH_FAIL_FAST}）: "
                            f"{str(e)[:100]}")
                if auth_fails >= _AUTH_FAIL_FAST:
                    state.save()
                    raise SystemExit(
                        f"[batch][ERROR] 连续 {_AUTH_FAIL_FAST} 次鉴权失败（401/403）——"
                        f"cookie 很可能已失效，中止批量以免空转。请更新 cookie 后重试。")
            else:
                auth_fails = 0
                state.mark_error(uuid, lu, t.get("title") or "", str(e))
                fail += 1
                log.warning(f"[batch] 失败: {str(e)[:120]}（退避）")
                throttle.backoff()
                if verify_on_errors and not deferred_checked and fail >= 3:
                    # --skip-auth-check was used: after several generic failures, verify
                    # the account once so the user learns whether it's auth vs network,
                    # and abort if it's a confirmed auth/account problem (avoid 空转).
                    # 用了 --skip-auth-check：多次通用失败后校验一次账户，区分鉴权还是网络；
                    # 确认是鉴权/账户问题则中止（避免空转）。
                    deferred_checked = True
                    if report_account_status(adapter.transport, account):
                        state.save()
                        raise SystemExit(
                            "[batch][ERROR] 回退校验确认鉴权/账户问题（cookie 失效或账户不符）——"
                            "已中止批量以免空转。请更新 cookie / 切换账户后重试。")
        state.save()
        if i < len(actions):
            d = throttle.delay()
            log.info(f"[batch] 间隔 {d:.1f}s")
    if n_stopped:
        # Early stop: everything beyond (older) is in a terminal state; gaps
        # (error/unexported) sit above the terminal suffix and are not skipped
        # 早停：其后（更旧）全部终态；缺口（error/未导）位于终态后缀之上，不会被跳过
        skip += n_stopped
        log.info(f"[batch] 已是最后更新状态，其后 {n_stopped} 条均无需导出——增量早停 "
                 f"(ok={ok} skip={skip} fail={fail}；--full 可强制全量)")
    state.save()
    log.info(f"[batch] 完成。ok={ok} skip={skip} fail={fail} / 共 {total}")
    # Commit unconditionally: even ok=0 leaves index refresh metadata (config.toml
    # [index_state] + library rewrite) that should be committed; no changes → no-op.
    # 无条件提交：即使 ok=0 也会留下索引刷新元数据（config.toml [index_state] +
    # library 重写）需要提交；无变更则 no-op。
    update_last_export()
    maybe_auto_commit(out_root, account=account.username)
    if variant_threads:
        # Rewritten-answer variant hit reminder (kept separate from the summary
        # format above): alternative answers may be cleaned up by the platform, and
        # siblings have been empirically shown to be mostly dead links (not
        # recoverable via the API), so manual handling is needed as soon as possible
        # 重写答案变体命中提醒（不破坏上方摘要格式）：备选答案或将被平台清理，
        # sibling 已实证多为死链（API 不可补救），需第一时间人工处置
        log.warning(f"[batch] ⚠ 本次 {variant_threads} 个线程命中 {variant_log.MARKER}"
                    f"（重写答案变体）——请尽快人工确认备选答案并补录；"
                    f"登记见 index/answer_variants_log.jsonl，流程见 docs/reference/api/api-responses-errors.md §5.2")
