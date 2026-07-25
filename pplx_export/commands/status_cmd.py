"""cmd: status — archive state summary and change report (zero network, read-only).

Reads only local files: index/library_<account>.json (index rows) and
index/batch_state.json (BatchState). Change classification reuses
hooks.incremental.plan_incremental — the same pure function batch/schedule use, so
the "new/updated/done/expired/deleted" semantics never drift apart.

Output is tiered by the standard -v count flag: INFO prints the compact summary;
-v adds new/updated/error thread titles; -vv adds done/expired/deleted details;
-vvv prints everything untruncated plus index fields and state-only records.
--json emits the full machine-readable report on stdout.

cmd: status——归档状态账与变更报告（零网络，只读）。

只读本地文件：index/library_<account>.json（索引行）与 index/batch_state.json
（BatchState）。变更分类复用 hooks.incremental.plan_incremental——与
batch/schedule 共用的纯函数，五态语义永不漂移。

输出按既有 -v 计数标志分级：默认 INFO 摘要；-v 加 new/updated/error 标题；
-vv 加 done/expired/deleted 明细；-vvv 全量（不截断 + 索引字段 + state-only
记录）。--json 经 stdout 输出机器可读全量报告。
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from ..core.logging import get_logger
from ..core.state import BatchState
from ..hooks.incremental import plan_incremental

log = get_logger("cli")

# Detail tiers by verbosity count (v/vv/vvv)
# 明细级别（对应 -v/-vv/-vvv）
_TIER1_ACTIONS = ("new", "updated", "error")
_TIER2_ACTIONS = ("done", "expired", "deleted")


def _library_files(out_root: Path) -> list[tuple[str, Path, float]]:
    """Enumerate per-account library files as (username, path, mtime).

    枚举各账户 library 文件，返回（用户名, 路径, mtime）。
    """
    index_dir = Path(out_root) / "index"
    if not index_dir.is_dir():
        raise SystemExit(f"[status][ERROR] 未找到索引目录 {index_dir}——"
                         f"请先运行 pplx-export index --account <account>")
    files = sorted(index_dir.glob("library_*.json"))
    if not files:
        raise SystemExit(f"[status][ERROR] {index_dir} 下没有 library_*.json——"
                         f"请先运行 pplx-export index --account <account>")
    return [(f.stem.removeprefix("library_"), f, f.stat().st_mtime) for f in files]


def _first_line(title: str, limit: int | None) -> str:
    """First line of a title, truncated to `limit` chars when given.

    标题首行；给 limit 时按字符数截断（空标题回退占位符）。
    """
    line = (title or "").strip().splitlines()[0] if (title or "").strip() else "(无标题)"
    if limit and len(line) > limit:
        return line[: limit - 1] + "…"
    return line


def _fmt_mtime(ts: float) -> str:
    """Format a file mtime for the freshness note.

    格式化文件 mtime（索引新鲜度提示用）。
    """
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _thread_title(thread: dict, state: BatchState) -> str:
    """Title for an index row: the state record wins (it is what the export wrote),
    falling back to the index row's own title.

    索引行标题：state 记录优先（导出时写入者），缺省回退索引行自带标题。
    """
    rec = state.get(thread.get("entryUUID") or "")
    return rec.get("title") or thread.get("title") or ""


def cmd_status(args, out_root: Path):
    """Print the archive state summary and the incremental change report.

    输出归档状态账与增量变更报告。
    """
    out_root = Path(out_root)
    libs = _library_files(out_root)
    if args.account:
        wanted = args.account
        libs = [x for x in libs if x[0] == wanted]
        if not libs:
            have = ", ".join(u for u, _, _ in _library_files(out_root))
            raise SystemExit(f"[status][ERROR] 无账户 {wanted} 的 library 文件（现有: {have}）")
    state = BatchState(out_root / "index" / "batch_state.json")
    verbose = args.verbose or 0

    report_accounts = []
    all_idx: set = set()
    for username, lib_path, mtime in libs:
        rows = json.loads(lib_path.read_text()).get("threads", [])
        full_actions, _ = plan_incremental(rows, state, full=True)
        _, n_stopped = plan_incremental(rows, state)
        counts = Counter(action for _, action in full_actions)
        idx_uuids = {t.get("entryUUID") for t in rows}
        all_idx |= idx_uuids
        n_error = sum(1 for u in idx_uuids
                      if (state.get(u) or {}).get("status") == "error")

        log.info(f"[status] 账户 {username}：索引 {len(rows)}（{_fmt_mtime(mtime)}）｜ "
                 f"ok {counts.get('done', 0)} + expired {counts.get('expired', 0)} + "
                 f"deleted {counts.get('deleted', 0)} + error {n_error} ｜ "
                 f"变更 new {counts.get('new', 0)} / updated {counts.get('updated', 0)} / "
                 f"早停 {n_stopped}")

        acct = {"username": username, "index_mtime": _fmt_mtime(mtime),
                "index_count": len(rows),
                "state": {"ok": counts.get("done", 0),
                          "expired": counts.get("expired", 0),
                          "deleted": counts.get("deleted", 0), "error": n_error},
                "changes": {"new": counts.get("new", 0),
                            "updated": counts.get("updated", 0),
                            "n_stopped": n_stopped},
                "threads": []}

        for thread, action in full_actions:
            uuid = thread.get("entryUUID") or ""
            title = _thread_title(thread, state)
            limit = None if verbose >= 3 else 60
            if action in _TIER1_ACTIONS and verbose >= 1:
                log.debug(f"[status][{action}] {uuid[:8]} {_first_line(title, limit)}")
            elif action in _TIER2_ACTIONS and verbose >= 2:
                rec = state.get(uuid) or {}
                extra = (f" lastUpdated={rec.get('lastUpdated')}"
                         f" exported_at={rec.get('exported_at')}") if rec else ""
                log.debug(f"[status][{action}] {uuid[:8]} {_first_line(title, limit)}{extra}")
            if verbose >= 3:
                extra = (f" mode={thread.get('mode')} search_mode={thread.get('search_mode')}"
                         f" lastUpdated={thread.get('lastUpdated')}")
                log.debug(f"[status][{action}] {uuid[:8]} {_first_line(title, None)}{extra}")
            acct["threads"].append({"uuid": uuid, "action": action,
                                    "title": title, "lastUpdated": thread.get("lastUpdated")})

        # Error records are not plan actions (plan treats them as "updated"); emit them
        # separately so -v shows what will actually be retried
        # error 记录在 plan 中并入 updated，单独输出让 -v 能看到真正会重试的对象
        if verbose >= 1:
            for u in sorted(idx_uuids):
                rec = state.get(u) or {}
                if rec.get("status") == "error":
                    log.debug(f"[status][error] {u[:8]} {_first_line(rec.get('title') or '', limit)}"
                              f"（上次导出失败，将作为 updated 重导）")
        report_accounts.append(acct)

    # state-only records: in batch_state but absent from every account's index
    # (excluding terminal states) — remote-deletion candidates for sync-deleted
    # state-only 记录：state 有而所有账户索引均无（终态除外）——sync-deleted 的候选参考
    state_only = [u for u in state.state
                  if u not in all_idx
                  and (state.get(u) or {}).get("status") not in ("expired", "deleted")]
    if state_only and verbose >= 3:
        for u in state_only:
            rec = state.get(u) or {}
            log.debug(f"[status][state-only] {u[:8]} {_first_line(rec.get('title') or '', None)}"
                      f"（索引中不存在——可能已被远端删除，可用 sync-deleted 对账）")

    totals = Counter((rec or {}).get("status") for rec in state.state.values())
    log.info(f"[status] 全局 batch_state：{totals.get('ok', 0)} ok + "
             f"{totals.get('expired', 0)} expired + {totals.get('deleted', 0)} deleted + "
             f"{totals.get('error', 0)} error")

    report = {"accounts": report_accounts,
              "state_only": [{"uuid": u, "title": (state.get(u) or {}).get("title") or ""}
                             for u in state_only],
              "totals": {"ok": totals.get("ok", 0), "expired": totals.get("expired", 0),
                         "deleted": totals.get("deleted", 0), "error": totals.get("error", 0)}}
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
