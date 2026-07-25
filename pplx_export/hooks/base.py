"""Hook abstraction: extension points for the export / incremental / relations /
scheduling stages.

Lifecycle event methods (on_new_thread etc.) and HookChain were removed after never
being triggered; the base class keeps its minimal form and subclasses provide
domain-specific methods (plan/add/flush) as needed.

Hook 抽象：导出/增量/关系/调度各阶段的扩展点。

生命周期事件方法（on_new_thread 等）与 HookChain 因零触发已删除；
基类保留最小形态，子类按需提供领域方法（plan/add/flush）。
"""

from __future__ import annotations

import abc


class Hook(abc.ABC):
    name = "abstract"
