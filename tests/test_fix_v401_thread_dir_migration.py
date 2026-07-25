"""V4-01 regression tests: automatic migration/merge of same-UUID multi-date directories for continued threads.

Before the fix: thread_dir_for built directories from the lastUpdated date, so a
continued thread was written to a new directory and the old one was not migrated
(3 dual-directory UUIDs once remained across the archive); the spaces index broke
on the first glob hit for *_<uuid8>, potentially pointing at the stale copy.
After the fix: before composing a new directory, the write path searches the whole
archive by uuid8 for an existing directory of the same UUID and auto-migrates it
(union of files; same-name conflicts always keep the target side/keeper — no more
mtime arbitration since V5-02; the old directory is deleted only after sha256
verification passes); spaces reads thread.json from the candidate directories and
picks the one with the maximum lastUpdated (since V5-04 candidates must match
web_uuid exactly).

Fully offline: synthetic Conversation / temp directories, no network access.

V4-01 回归测试：续接线程同 UUID 多日期目录的自动迁移合并。

修复前：thread_dir_for 用 lastUpdated 日期组目录，线程被继续后写入新目录、
旧目录不迁移（全库曾残留 3 个双目录 UUID）；spaces 索引对 *_<uuid8> 第一个
glob 命中即 break，可能指向旧副本。
修复后：写入路径在组成新目录前按 uuid8 全库查找同 UUID 既有目录并自动迁移
（文件并集、同名冲突恒保留目标方/keeper——V5-02 起不再按 mtime 裁决、
sha256 校验通过才删旧目录）；spaces 从候选目录读 thread.json 选 lastUpdated
最大者（V5-04 起候选须 web_uuid 全等）。

全离线：合成 Conversation / 临时目录，不触网。
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from pplx_export.commands.spaces_cmd import cmd_spaces
from pplx_export.core.models import Conversation, Turn
from pplx_export.sites.perplexity.fs_writer import FilesystemWriter

UUID = "abcdef12-3456-7890-abcd-ef1234567890"


def _conv(last_updated: str, n_turns: int) -> Conversation:
    """Minimal synthetic thread: fixed UUID/title/author/mode; only lastUpdated and turn count vary.

    最小合成线程：固定 UUID/标题/作者/模式，只变 lastUpdated 与轮数。"""
    return Conversation(
        web_uuid=UUID, title="续接线程", mode="search", author="tester",
        last_updated=last_updated,
        turns=[Turn(index=i + 1, query=f"第{i + 1}问", created_us=1700000000000000 + i)
               for i in range(n_turns)],
    )


def _dirs(out_root: Path) -> list[Path]:
    return sorted(p for p in out_root.glob(f"*/*/*_{UUID[:8]}") if p.is_dir())


class TestAutoMigration:
    def test_continued_thread_migrates_old_dir(self, tmp_path):
        """Same UUID, different dates: on re-export the old directory is auto-merged into the new canonical one and deleted.

        同 UUID 不同日期：再次导出时旧目录自动合并进新规范目录并删除。"""
        w = FilesystemWriter(tmp_path)
        d1 = w.write_thread(_conv("2026-07-13T05:44:22Z", 2))
        assert d1.name.startswith("2026-07-13_")
        # Files unique to the old directory (e.g. downloaded assets) must survive the migration
        # 旧目录独有文件（如下载过的资产）必须在迁移后保留
        stray = d1 / "assets" / "files" / "old_only.txt"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text("旧目录独有的资产")

        d2 = w.write_thread(_conv("2026-07-20T20:48:00Z", 3))

        assert d2.name.startswith("2026-07-20_") and d2.is_dir()
        assert not d1.exists(), "旧日期目录应被迁移删除"
        assert _dirs(tmp_path) == [d2], "一个 UUID 应只剩一个目录"
        # Asset union: files unique to the old directory are merged into the new one, content identical
        # 资产并集：旧目录独有文件并入新目录，内容一致
        assert (d2 / "assets" / "files" / "old_only.txt").read_text() == "旧目录独有的资产"
        # raw/thread.json follows the new export
        # raw/thread.json 以新导出为准
        tj = json.loads((d2 / "thread.json").read_text())
        assert tj["lastUpdated"] == "2026-07-20T20:48:00Z" and tj["n_turns"] == 3
        assert len(list((d2 / "turns").glob("turn_*.md"))) == 3

    def test_migration_idempotent(self, tmp_path):
        """Migration is idempotent: repeated exports / repeated consolidate produce no duplicate directories and no errors.

        迁移幂等：重复导出/重复 consolidate 不产生重复目录、不报错。"""
        w = FilesystemWriter(tmp_path)
        w.write_thread(_conv("2026-07-13T05:44:22Z", 2))
        d2 = w.write_thread(_conv("2026-07-20T20:48:00Z", 3))
        # Re-export of the same state: directory unchanged, nothing added
        # 同状态重导：目录不变、无新增
        assert w.write_thread(_conv("2026-07-20T20:48:00Z", 3)) == d2
        assert _dirs(tmp_path) == [d2]
        # Run archive-wide consolidation again: no duplicates, empty list
        # 再跑全库合并：无重复，空列表
        assert w.consolidate_uuid(UUID) == []
        assert _dirs(tmp_path) == [d2]

    def test_consolidate_conflict_always_keeps_keeper(self, tmp_path):
        """Same-name conflicts **always keep the keeper** (the side with max lastUpdated), regardless of mtime (V5-02):
        newer mtime != newer content (re-render refreshes the mtime of all md files in every directory while the
        content still comes from the old raw); the consolidate path has no subsequent overwrite, so old content must
        never override the keeper via a newer mtime; unique files are unioned and preserved.

        同名冲突**恒保留 keeper**（lastUpdated 最大方），与 mtime 无关（V5-02）：
        mtime 新 ≠ 内容新（re-render 会刷新全部目录 md 的 mtime 而内容仍来自旧 raw），
        consolidate 路径无后续覆写，绝不允许旧内容靠新 mtime 覆盖 keeper；独有文件并集保留。"""
        w = FilesystemWriter(tmp_path)
        d1 = w.write_thread(_conv("2026-07-13T05:44:22Z", 2))
        d2 = w.write_thread(_conv("2026-07-20T20:48:00Z", 3))
        # The previous step auto-migrated; recreate the dual-directory scenario:
        # 上一步已自动迁移，重建双目录场景：
        assert _dirs(tmp_path) == [d2]
        # Manually resurrect an old-date directory containing: a unique file + a conflicting
        # same-name file whose mtime is artificially bumped
        # 手工复活一个旧日期目录，内含：独有文件 + 同名但「mtime 被人为调新」的冲突文件
        d_old = d2.parent / d2.name.replace("2026-07-20_", "2026-07-13_")
        (d_old / "assets" / "files").mkdir(parents=True)
        (d_old / "thread.json").write_text(json.dumps(
            {"web_uuid": UUID, "lastUpdated": "2026-07-13T05:44:22Z"}, ensure_ascii=False))
        (d_old / "assets" / "files" / "legacy.bin").write_text("旧目录独有")
        conflict_old = d_old / "notes.txt"
        conflict_old.write_text("旧目录的内容（mtime 人为调新，模拟 re-render 刷新）")
        conflict_new = d2 / "notes.txt"
        conflict_new.write_text("keeper 的内容（语义更新，必须胜出）")
        # mtime: the old directory's conflicting file is newer (1 hour in the future) —
        # before the fix it would wrongly win because of this
        # mtime：旧目录的冲突文件更新（未来 1 小时）——修复前会因此误胜
        future = conflict_new.stat().st_mtime + 3600
        os.utime(conflict_old, (future, future))

        removed = w.consolidate_uuid(UUID)

        assert removed == [d_old]
        assert not d_old.exists() and d2.is_dir()
        assert (d2 / "assets" / "files" / "legacy.bin").read_text() == "旧目录独有"
        assert conflict_new.read_text() == "keeper 的内容（语义更新，必须胜出）", \
            "冲突必须恒保留 keeper，与 mtime 无关"


class TestConflictWarningLog:
    """Per-file conflict visibility (risk point 4, option B): always keeping the target side on same-name
    conflicts is a heuristic, so the theoretical "keeper side actually has older content but is kept"
    scenario must surface a warning-level log for the user to notice.

    冲突逐文件可见（风险点 4 方案 B）：同名冲突恒保留目标方是启发式，
    理论上的「keeper 侧内容更旧被保留」场景必须有 warning 级日志让用户可察觉。"""

    def _two_dirs_with_conflicts(self, tmp_path: Path, conflict_names: list[str]):
        """Synthesize a keeper (new-date directory) + a manually resurrected old-date directory; conflict_names exist on both sides with different content.

        合成 keeper（新日期目录）+ 手工复活的旧日期目录，conflict_names 双方同名异内容。"""
        w = FilesystemWriter(tmp_path)
        d2 = w.write_thread(_conv("2026-07-20T20:48:00Z", 3))
        # Auto-migration has already converged to a single directory; recreate the dual-directory scenario
        # 自动迁移已收敛为单目录，重建双目录场景
        assert _dirs(tmp_path) == [d2]
        d_old = d2.parent / d2.name.replace("2026-07-20_", "2026-07-13_")
        d_old.mkdir(parents=True)
        (d_old / "thread.json").write_text(json.dumps(
            {"web_uuid": UUID, "lastUpdated": "2026-07-13T05:44:22Z"}, ensure_ascii=False))
        for name in conflict_names:
            (d_old / name).parent.mkdir(parents=True, exist_ok=True)
            (d_old / name).write_text(f"旧目录的 {name}")
            (d2 / name).parent.mkdir(parents=True, exist_ok=True)
            (d2 / name).write_text(f"keeper 的 {name}")
        return w, d_old, d2

    @staticmethod
    def _migrate_warnings(caplog) -> list[str]:
        return [r.getMessage() for r in caplog.records
                if r.levelno >= logging.WARNING and "[migrate]" in r.getMessage()]

    def test_conflict_logs_warning_with_filenames(self, tmp_path, caplog, monkeypatch):
        """A conflict produces a warning containing the conflicting files' relative paths, both directory names, and the "target side kept" wording.

        冲突时产生 warning：含冲突文件相对路径、两个目录名、「已保留目标方」文案。"""
        # setup_logging sets the root logger's propagate to False; ensure caplog can capture here
        # setup_logging 会把根 logger propagate 置 False，此处确保 caplog 能捕获
        monkeypatch.setattr(logging.getLogger("pplx_export"), "propagate", True)
        w, d_old, d2 = self._two_dirs_with_conflicts(
            tmp_path, ["notes.txt", "assets/files/dup.bin"])

        with caplog.at_level(logging.WARNING, logger="pplx_export.cli"):
            removed = w.consolidate_uuid(UUID)

        assert removed == [d_old]
        warns = self._migrate_warnings(caplog)
        assert len(warns) == 1, f"应恰好一条冲突 warning: {warns}"
        msg = warns[0]
        assert "notes.txt" in msg and os.path.join("assets", "files", "dup.bin") in msg
        assert d_old.name in msg and d2.name in msg
        assert "已保留目标方" in msg
        # No warning when there are no conflicts (zero alerts on the healthy path): run the idempotent merge once more
        # 无冲突时不应有 warning（健康路径零告警）：再跑一次幂等合并
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="pplx_export.cli"):
            assert w.consolidate_uuid(UUID) == []
        assert self._migrate_warnings(caplog) == []

    def test_conflict_log_truncates_over_20(self, tmp_path, caplog, monkeypatch):
        """When there are more than 20 conflicting files, only the first 20 are listed along with the total count.

        冲突文件 >20 个时只列前 20 个并给出总数。"""
        monkeypatch.setattr(logging.getLogger("pplx_export"), "propagate", True)
        # 25 + thread.json = 26 conflicts
        # 25 个 + thread.json = 26 个冲突
        names = [f"f{i:02d}.txt" for i in range(1, 26)]
        w, d_old, d2 = self._two_dirs_with_conflicts(tmp_path, names)

        with caplog.at_level(logging.WARNING, logger="pplx_export.cli"):
            w.consolidate_uuid(UUID)

        warns = self._migrate_warnings(caplog)
        assert len(warns) == 1
        msg = warns[0]
        assert "26 个同名文件冲突" in msg and "仅列前 20 个" in msg
        assert "f01.txt" in msg and "f20.txt" in msg
        assert "f21.txt" not in msg and "thread.json" not in msg


class TestSpacesSelectsNewest:
    def test_spaces_link_picks_max_last_updated(self, tmp_path, monkeypatch):
        """Multiple candidate directories for the same UUID: the spaces index link points to the one with the max thread.json lastUpdated.

        同 UUID 多候选目录：spaces 索引链接指向 thread.json lastUpdated 最大者。"""
        out_root = tmp_path / "web_archive"
        idx = out_root / "index"
        idx.mkdir(parents=True)
        (idx / "library_acc.json").write_text(json.dumps({
            "account": "acc",
            "threads": [{
                "entryUUID": UUID, "title": "续接线程", "authorUsername": "acc",
                "mode_label": "SEARCH", "lastUpdated": "2026-07-20T20:48:00Z",
                "collection": {"uuid": "cuuid", "title": "测试空间", "slug": "sp-Abc123"},
            }],
        }, ensure_ascii=False))
        # Two date directories: glob sorting puts the old one first (before the fix, breaking on the first hit would pick the old one)
        # 两个日期目录：glob 排序旧目录在前（修复前第一个命中即 break 会选旧）
        for date, lu in (("2026-07-13", "2026-07-13T05:44:22Z"),
                         ("2026-07-20", "2026-07-20T20:48:00Z")):
            d = out_root / "Tester" / "search" / f"{date}_续接线程_{UUID[:8]}"
            d.mkdir(parents=True)
            (d / "thread.json").write_text(json.dumps(
                {"web_uuid": UUID, "lastUpdated": lu}, ensure_ascii=False))
        monkeypatch.chdir(tmp_path)
        cmd_spaces(out_root)

        md = (tmp_path / "spaces" / "sp-Abc123.md").read_text(encoding="utf-8")
        links = re.findall(r"\[已导出\]\(([^)]+)\)", md)
        assert len(links) == 1
        assert "2026-07-20_" in links[0], f"应指向 lastUpdated 最大者: {links[0]}"
        target = Path(os.path.normpath(tmp_path / "spaces" / links[0]))
        assert target.is_dir(), f"反链不可达: {links[0]}"
