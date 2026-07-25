"""Periodic scheduling: register recurring incremental exports (via cron / system
timers or this framework's schedule subcommand).

Scheduling policy: periodic runs are incremental only (plan_incremental early stop),
avoiding full re-fetches.

周期调度：注册周期性增量导出（借助 cron/系统定时或本框架 schedule 子命令）。

调度策略：周期性只跑增量（plan_incremental 早停），避免全量重抓。
"""

from __future__ import annotations

import json
from pathlib import Path

from ..core.models import Account
from .base import Hook
from .incremental import IncrementalHook


class SchedulerHook(Hook):
    name = "scheduler"

    def __init__(self, index_dir: Path):
        self.index_dir = Path(index_dir)

    def plan(self, account: Account, adapter, full: bool = False) -> dict:
        """Compute this round's incremental plan (lists of new/updated threads).

        Early stop by default: the list is scanned newest-first and the trailing run
        of "exported and unchanged" entries is skipped wholesale (no full-library
        traversal); full=True forces a full comparison, for periodic backstop runs.

        计算本轮增量计划（新增/更新线程列表）。

        默认早停：列表从新到旧扫描，尾部「已导出且未变」的连续段整体跳过（不遍历全库）；
        full=True 强制全量比对，用于定期兜底。
        """
        threads = list(adapter.list_threads(account))
        inc = IncrementalHook(self.index_dir)
        actions, _ = inc.plan(threads, full=full)
        new = [t for t, k in actions if k == "new"]
        updated = [t for t, k in actions if k == "updated"]
        return {"total": len(threads), "new": len(new), "updated": len(updated),
                "full": full, "new_threads": new, "updated_threads": updated}

    def write_cron_snippet(self, account: Account, out_root: Path, cron: str = "17 3 * * *") -> Path:
        """Generate an incremental-export command snippet callable by system cron
        (batch is incremental with early stop by default).

        out_root is passed explicitly (V5-10: previously derived implicitly from
        out_path.parent.parent, which required the caller to happen to pass
        <out_root>/index/cron_snippet.txt — an implicit contract).
        The file is always written to <out_root>/index/cron_snippet.txt.

        生成一个可被系统 cron 调用的增量导出命令片段（batch 默认即增量早停）。

        out_root 显式传入（V5-10：此前由 out_path.parent.parent 隐式推导，
        依赖调用方恰好传 <out_root>/index/cron_snippet.txt，契约隐式）。
        落盘固定为 <out_root>/index/cron_snippet.txt。
        """
        # cron runs with an unpredictable cwd, so an absolute path is mandatory
        # cron 环境 cwd 不定，必须用绝对路径
        out_root = Path(out_root).resolve()
        out_path = out_root / "index" / "cron_snippet.txt"
        # F-07/F-14: quote paths and the account name uniformly against space breakage;
        # use an absolute path for pplx-export (cron's default PATH is usually just
        # /usr/bin:/bin and cannot find the uv tool install directory)
        # F-07/F-14：路径与账户名统一加引号防空格断裂；pplx-export 用绝对路径
        # （cron 默认 PATH 通常只有 /usr/bin:/bin，找不到 uv tool 安装目录）
        import shutil
        exe = shutil.which("pplx-export") or "pplx-export"
        cmd = (f"cd '{out_root.parent}' && '{exe}' batch "
               f"--account '{account.username}' --out '{out_root}'")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(f"{cron} {cmd}\n")
        return out_path
