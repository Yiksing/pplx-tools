"""Incremental capture: export only new/changed conversations by lastUpdated diff.

The single source of truth for state is ``index/batch_state.json`` (``BatchState``) —
cmd_batch writes it after every successfully exported thread, so the "exported and
unchanged" verdict reuses it directly instead of maintaining a separate copy.

Incremental core: the pure function ``plan_incremental`` (shared by cmd_batch and
SchedulerHook.plan). After sorting the list by lastUpdated (newest first), new
conversations and "resumed old conversations" (whose lastUpdated moved them to the
top) both sit at the head; skipping the trailing run of "exported and unchanged"
entries (early stop) is safe because older threads are necessarily unchanged too.
Gap safety: error/unexported threads left by an interrupted or failed previous run
sit above the terminal-state suffix and are not skipped. ``full=True`` forces a full
scan, for periodic backstop runs or when archive gaps are suspected.

增量捕获：按 lastUpdated 差异只导新增/变更的对话。

状态唯一来源是 ``index/batch_state.json``（``BatchState``）——cmd_batch 每导出成功
一个线程就写入，因此「已导出且未变」的判定直接复用它，不另维护副本。

增量核心：``plan_incremental`` 纯函数（cmd_batch 与 SchedulerHook.plan 共用）。
列表按 lastUpdated 从新到旧排序后，新对话与「续接的旧对话」（lastUpdated
变新、位置上移）都排在顶部；跳过尾部「已导出且未变」的连续段即可（早停）——更旧的
线程必然也未变。缺口安全：上次运行中断/失败留下的 error/未导线程位于终态后缀之上，
不会被跳过。``full=True`` 强制全量扫描，用于定期兜底或怀疑档案有缺口时。
"""

from __future__ import annotations

from pathlib import Path

from ..core.state import BatchState
from .base import Hook


def plan_incremental(threads: list[dict], state: BatchState, *,
                     full: bool = False, force: bool = False) -> tuple[list[tuple[dict, str]], int]:
    """Compute the incremental export plan (pure function; terminal-state semantics
    follow ``BatchState.is_terminal``).

    Input order does not matter (sorted internally by lastUpdated, newest first).
    Returns (actions, n_stopped):
      actions = [(thread, action)], action in
        "new" (never exported) / "updated" (lastUpdated changed, or force re-export) /
        "done" (exported and unchanged) / "expired" (terminal state cleared by the
        platform; not retried even with --force) /
        "deleted" (terminal state confirmed remotely deleted by sync-deleted; handled
        exactly like expired — terminal states are not retried and not re-exported
        even with --force);
      by default (neither full nor force) early stop applies: the longest trailing
      terminal-state suffix is trimmed, and n_stopped is the trimmed count;
      full=True disables early stop (done/expired/deleted are returned one by one so
      the caller can log each).

    计算增量导出计划（纯函数；终态语义以 ``BatchState.is_terminal`` 为准）。

    threads 顺序不限（内部按 lastUpdated 从新到旧排序）。
    返回 (actions, n_stopped)：
      actions = [(thread, action)]，action ∈
        "new"（从未导出）/ "updated"（lastUpdated 变了，或 force 重导）/
        "done"（已导出且未变）/ "expired"（平台已清除的终态，--force 也不重试）/
        "deleted"（远端已删除的终态，sync-deleted 确认；与 expired 同等处理，
        终态不重试、--force 也不重导）；
      默认（非 full 非 force）执行早停：截掉尾部最长终态后缀，n_stopped 为截掉条数；
      full=True 不早停（done/expired/deleted 逐项返回，供调用方逐条记日志）。
    """
    ordered = sorted(threads, key=lambda t: t.get("lastUpdated") or "", reverse=True)
    actions: list[tuple[dict, str]] = []
    for t in ordered:
        uuid = t.get("entryUUID")
        lu = t.get("lastUpdated")
        if state.is_expired(uuid):
            actions.append((t, "expired"))
        elif state.is_deleted(uuid):
            actions.append((t, "deleted"))
        elif not force and state.is_done(uuid, lu):
            actions.append((t, "done"))
        elif not state.is_known(uuid):
            actions.append((t, "new"))
        else:
            actions.append((t, "updated"))
    n_stopped = 0
    if not full and not force:
        while actions and actions[-1][1] in ("done", "expired", "deleted"):
            actions.pop()
            n_stopped += 1
    return actions, n_stopped


class IncrementalHook(Hook):
    name = "incremental"

    def __init__(self, index_dir: Path):
        self.state = BatchState(Path(index_dir) / "batch_state.json")

    def plan(self, threads: list[dict], *, full: bool = False, force: bool = False):
        """Thin shell over the incremental plan (delegates to plan_incremental).

        增量计划薄壳（委托 plan_incremental）。
        """
        return plan_incremental(threads, self.state, full=full, force=force)
