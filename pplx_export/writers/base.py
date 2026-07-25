"""Writer abstraction: the output persistence interface.

Writer 抽象：输出落盘接口。
"""

from __future__ import annotations

import abc
from pathlib import Path

from ..core.models import Conversation
# Public-API alias import (F-13; previously imported the private name)
# 公开 API 别名导入（F-13，原导入私有名）
from ..core.state import norm_ts as _norm_ts


class Writer(abc.ABC):
    @abc.abstractmethod
    def thread_dir_for(self, conv: Conversation) -> Path:
        """The on-disk directory for a conversation (callers need it before writing:
        as the destination for asset downloads and for idempotency checks).

        对话的落盘目录（调用方在写盘前也需要：资产下载落点、幂等判断）。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def write_thread(self, conv: Conversation, adapter=None) -> Path:
        """Persist one conversation and return its directory. adapter may be None:
        online-dependent parts (reports, sub-agents) are skipped then.

        落盘一个对话，返回其目录。adapter 可空：为空时报告/子代理等需在线的部分跳过。
        """
        raise NotImplementedError

    def is_unchanged(self, conv: Conversation, thread_dir: Path) -> bool:
        """Idempotency check: already exported and lastUpdated unchanged.

        幂等判断：已导出且 lastUpdated 未变。
        """
        import json
        tj = thread_dir / "thread.json"
        if not tj.exists():
            return False
        try:
            old = json.loads(tj.read_text())
            # Compare after normalization: fractional seconds are stripped
            # (.18033Z vs .180330Z trailing-zero differences once caused duplicate exports)
            # 归一化后比较：去掉小数秒（.18033Z vs .180330Z 尾零差曾导致重复导出）
            return bool(old.get("lastUpdated")) and _norm_ts(old["lastUpdated"]) == _norm_ts(conv.last_updated)
        except Exception:
            return False
