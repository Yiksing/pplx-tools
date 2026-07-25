"""Relations maintenance hook: rebuild conversation relation edges after export.

关系维护 Hook：导出后重建对话关系边。
"""

from __future__ import annotations

from pathlib import Path

from ..core.relations import build_edges, write_relations
from ..core.logging import get_logger
from .base import Hook

log = get_logger("relations")


class RelationsHook(Hook):
    name = "relations"

    def __init__(self, out_dir: Path):
        self.out_dir = Path(out_dir)
        self._conversations: list = []

    def add(self, conv):
        self._conversations.append(conv)

    def flush(self) -> Path:
        """Rebuild and persist relation edges (writes an empty file for an empty
        archive too, keeping the layout idempotent); returns the output directory.

        重建并落盘关系边（空档案也写空文件，保持幂等布局），返回输出目录。
        """
        edges = build_edges(self._conversations)
        out = write_relations(edges, self.out_dir / "relations")
        log.info(f"[relations] {len(edges)} 条关系边 → {out}")
        return out
