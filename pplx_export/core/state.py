"""Batch export state: resume from checkpoint.

批量导出状态：断点续跑。"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from .logging import get_logger

log = get_logger("state")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm_ts(s: str | None) -> str:
    """Normalize lastUpdated: strip trailing zeros only in the fractional-seconds part
    (.18033Z and .180330Z compare equal).
    The platform occasionally drops trailing zeros; exact string comparison would
    falsely judge "changed" and cause duplicate exports; but .100Z and .900Z are
    different instants and must compare unequal (V4-04: the original implementation
    removed the entire fractional part, falsely judging different fractions as equal too).

    Known trade-off (V5-09, intentionally kept): all-zero fraction vs no fraction
    compare unequal (.000000Z → .0Z ≠ whole second without fraction) — numerically the
    same instant, but the misjudgment direction is "unequal" (at worst one redundant
    re-export) rather than "equal" (which could skip a needed export), the safe
    direction. Do not "optimize" it back to equal.

    归一化 lastUpdated：只对小数秒部分去尾零（.18033Z 与 .180330Z 判同）。
    平台偶发丢尾零，字符串精确比较会误判为「已变化」导致重复导出；
    但 .100Z 与 .900Z 是不同时间点，必须判不等（V4-04：原实现整段删除小数秒，
    把不同的小数秒也误判为相同）。

    已知取舍（V5-09，有意保留）：全零小数与无小数判不等
    （.000000Z → .0Z ≠ 无小数的整秒），数值上虽是同一时刻——误判方向是
    「不等」（至多冗余重导一次）而非「相等」（可能跳过需要的导出），
    属安全方向。勿为「优化」而改回判等。"""
    if not s:
        return ""
    s = s.strip()
    m = re.search(r"\.(\d+)", s)
    if not m:
        return s
    # All-zero fraction keeps one digit as the floor (.000000Z → .0Z)
    # 全零小数保底保留一位（.000000Z → .0Z）
    frac = m.group(1).rstrip("0") or "0"
    return s[: m.start(1)] + frac + s[m.end(1):]


# Public alias (F-13): cross-module users such as writers/base.py should import norm_ts (the private name may be refactored/renamed)
# 公开别名（F-13）：writers/base.py 等跨模块使用请 import norm_ts（私有名可被重构改名）
norm_ts = _norm_ts


class BatchState:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.state: dict = {}
        if self.path.exists():
            try:
                self.state = json.loads(self.path.read_text())
            except Exception:
                # Do not silently blank on corruption: back up the original file, so the 13 expired
                # terminal states are not lost and then needlessly retried
                # 损坏不静默置空：备份原文件，避免 13 条 expired 终态丢失后被无谓重试
                bak = self.path.with_name(f"{self.path.name}.corrupt-{int(time.time())}")
                try:
                    self.path.rename(bak)
                except OSError as e:
                    # Backup failure must leave a trace (F-15: was a silent pass; the corruption cause may be a recoverable I/O error)
                    # 备份失败要有痕迹（F-15：原静默 pass，损坏原因可能是可恢复的 I/O 错误）
                    log.warning(f"[state] 损坏状态文件备份失败 {self.path}: {e}")
                self.state = {}

    def get(self, uuid: str) -> dict:
        return self.state.get(uuid) or {}

    def is_done(self, uuid: str, last_updated: str | None) -> bool:
        st = self.state.get(uuid) or {}
        return (st.get("status") == "ok" and bool(last_updated)
                and _norm_ts(st.get("lastUpdated")) == _norm_ts(last_updated))

    def is_expired(self, uuid: str) -> bool:
        """Confirmed purged by the platform (ENTRY_EXPIRED). Terminal; never retried in any mode.

        已确认被平台清除（ENTRY_EXPIRED）。终态，任何模式都不重试。"""
        return (self.state.get(uuid) or {}).get("status") == "expired"

    def is_deleted(self, uuid: str) -> bool:
        """Confirmed remotely deleted (sync-deleted: disappeared from index + online verification;
        user deletion / remote removal).
        A terminal state on par with expired; never retried in any mode. Semantic distinction:
        expired = platform returned ENTRY_EXPIRED during export (platform purge);
        deleted = actively deleted by user/remote, then confirmed via index diff + online check.

        已确认远端删除（sync-deleted：索引消失 + 在线验证；用户删除/远端移除）。
        与 expired 并列的终态，任何模式都不重试。语义区分：expired=导出时平台返回
        ENTRY_EXPIRED（平台清除）；deleted=用户/远端主动删除后经索引 diff + 在线确认。"""
        return (self.state.get(uuid) or {}).get("status") == "deleted"

    def is_terminal(self, uuid: str, last_updated: str | None) -> bool:
        """Terminal (no re-export needed): exported and lastUpdated unchanged, or confirmed expired/remotely deleted (no retry).

        终态（无需再导）：已导出且 lastUpdated 未变，或已确认过期/远端删除（不重试）。"""
        if self.is_expired(uuid) or self.is_deleted(uuid):
            return True
        return self.is_done(uuid, last_updated)

    def is_known(self, uuid: str) -> bool:
        """Whether processed before (any status).

        是否处理过（任意状态）。"""
        return uuid in self.state

    def mark_ok(self, uuid: str, last_updated: str | None, title: str = ""):
        self.state[uuid] = {"status": "ok", "lastUpdated": last_updated,
                            "title": title[:80], "exported_at": _now_iso()}

    def mark_error(self, uuid: str, last_updated: str | None, title: str, error: str):
        self.state[uuid] = {"status": "error", "lastUpdated": last_updated,
                            "title": title[:80], "error": error[:300], "failed_at": _now_iso()}

    def mark_expired(self, uuid: str, last_updated: str | None, title: str = "",
                     note: str = ""):
        self.state[uuid] = {"status": "expired", "lastUpdated": last_updated,
                            "title": title[:80], "note": note, "expired_at": _now_iso()}

    def mark_deleted(self, uuid: str, last_updated: str | None, title: str = "",
                     note: str = ""):
        """Mark the remotely-deleted terminal state (note records the confirmation reason,
        e.g. "disappeared from index + GET thread returned 404").

        标记远端已删除终态（note 记录确认原因，如「索引消失 + GET thread 返回 404」）。"""
        self.state[uuid] = {"status": "deleted", "lastUpdated": last_updated,
                            "title": title[:80], "note": note, "deleted_at": _now_iso()}

    def save(self):
        """Atomic write: write a temp file then replace; interruption/full disk leaves no truncated JSON.

        原子写入：先写临时文件再替换，中断/磁盘满不会留下截断 JSON。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1))
        os.replace(tmp, self.path)

    def counts(self) -> dict:
        from collections import Counter
        return dict(Counter(v.get("status") for v in self.state.values()))
