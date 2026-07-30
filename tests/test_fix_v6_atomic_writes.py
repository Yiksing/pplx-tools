"""V6-M1 regression tests: atomic writes for archive products (fsio.atomic_write_text).

Before the fix: fs_writer / rerender / sync-deleted / sync-space / backfill wrote
thread.json, raw_*.json and rendered markdown with bare write_text — a killed
process or a full disk could leave a truncated file; a truncated thread.json
fails the V5-03 identity check and detaches the directory from auto-migration,
and a truncated raw file loses the highest source of truth.
After the fix: every archive writer goes through core.fsio.atomic_write_text
(hidden same-directory temp file + os.replace) — any failure before the final
replace leaves the pre-existing target byte-identical, and no temp residue
survives a successful write.

Fully offline: synthetic Conversation / temp directories, no network access.

V6-M1 回归测试：归档产物原子写（fsio.atomic_write_text）。

修复前：fs_writer / rerender / sync-deleted / sync-space / backfill 用裸
write_text 写 thread.json、raw_*.json 与渲染 markdown——进程被杀或磁盘满
可能留下截断文件；截断的 thread.json 会使 V5-03 身份核验拒认目录、脱离
自动迁移，截断的 raw 文件直接损失最高真源层。
修复后：全部归档写入方经 core.fsio.atomic_write_text（同目录隐藏临时文件 +
os.replace）——最终替换前的任何失败都保持既有目标字节不变，成功写入后
无临时残留。

全离线：合成 Conversation / 临时目录，不触网。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pplx_export.core import fsio
from pplx_export.core.fsio import atomic_write_bytes, atomic_write_text
from pplx_export.core.models import Asset, Conversation, Turn
from pplx_export.sites.perplexity.assets import AssetDownloader
from pplx_export.sites.perplexity.fs_writer import FilesystemWriter

UUID = "abcdef12-3456-7890-abcd-ef1234567890"


def _conv(n_turns: int = 2) -> Conversation:
    """Minimal synthetic thread (same shape as the V4-01 test helper).

    最小合成线程（与 V4-01 测试助手同构）。"""
    return Conversation(
        web_uuid=UUID, title="原子写测试线程", mode="search", author="tester",
        last_updated="2026-07-26T00:00:00Z",
        turns=[Turn(index=i + 1, query=f"第{i + 1}问", created_us=1700000000000000 + i)
               for i in range(n_turns)],
    )


class TestAtomicWriteText:
    def test_roundtrip_creates_parents_no_tmp_left(self, tmp_path):
        """Normal write: parent directories are created, content matches, no temp residue.

        正常写入：自建父目录、内容一致、无临时残留。"""
        p = tmp_path / "sub" / "deeper" / "thread.json"
        atomic_write_text(p, '{"web_uuid": "x"}')
        assert p.read_text() == '{"web_uuid": "x"}'
        assert list(tmp_path.rglob("*.tmp")) == [], "原子写后不应残留 tmp 文件"

    def test_replace_failure_keeps_original_intact(self, tmp_path, monkeypatch):
        """os.replace raising leaves the pre-existing target byte-identical.

        os.replace 抛错时既有目标保持字节不变。"""
        p = tmp_path / "thread.json"
        p.write_text("原始完整内容")

        def _boom(src, dst):
            raise OSError("simulated crash at replace")

        monkeypatch.setattr(fsio.os, "replace", _boom)
        with pytest.raises(OSError, match="simulated crash"):
            atomic_write_text(p, "新内容（不应生效）")
        assert p.read_text() == "原始完整内容"

    def test_tmp_write_failure_keeps_original_intact(self, tmp_path, monkeypatch):
        """A failure while writing the temp file never touches the target.

        临时文件写入中途失败绝不触碰目标文件。"""
        p = tmp_path / "thread.json"
        p.write_text("原始完整内容")
        real_write_text = Path.write_text

        def _partial(self, text, *args, **kwargs):
            if self.name.endswith(".tmp"):
                # Simulate disk-full truncation mid-write
                # 模拟磁盘满导致的写一半截断
                real_write_text(self, text[: len(text) // 2], *args, **kwargs)
                raise OSError("simulated disk full")
            return real_write_text(self, text, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", _partial)
        with pytest.raises(OSError, match="disk full"):
            atomic_write_text(p, "新内容（不应生效）" * 10)
        assert p.read_text() == "原始完整内容"

    def test_stale_tmp_residue_is_reused(self, tmp_path):
        """A crash residue temp file is simply replaced by the next write of the same target.

        崩溃残留的临时文件会被下次同目标写入直接复用覆盖。"""
        p = tmp_path / "thread.json"
        (tmp_path / ".thread.json.tmp").write_text("上次崩溃的残留")
        atomic_write_text(p, "新内容")
        assert p.read_text() == "新内容"
        assert not (tmp_path / ".thread.json.tmp").exists()


class TestAtomicWriteBytes:
    def test_replace_failure_keeps_original_intact(self, tmp_path, monkeypatch):
        """Binary archive products use the same replace-boundary guarantee as text.

        二进制归档产物与文本归档产物使用同一替换边界保证。"""
        p = tmp_path / "assets" / "files" / "report.md"
        p.parent.mkdir(parents=True)
        p.write_bytes(b"ORIGINAL_COMPLETE")

        def _boom(src, dst):
            raise OSError("simulated crash at replace")

        monkeypatch.setattr(fsio.os, "replace", _boom)
        with pytest.raises(OSError, match="simulated crash"):
            atomic_write_bytes(p, b"NEW_COMPLETE")
        assert p.read_bytes() == b"ORIGINAL_COMPLETE"

    def test_tmp_write_failure_keeps_original_intact(self, tmp_path, monkeypatch):
        """A partial temp-file write cannot truncate an existing asset.

        临时文件写到一半失败不能截断既有资产。"""
        p = tmp_path / "report.md"
        p.write_bytes(b"ORIGINAL_COMPLETE")
        real_write_bytes = Path.write_bytes

        def _partial(self, data):
            if self.name.endswith(".tmp"):
                real_write_bytes(self, data[:3])
                raise OSError("simulated disk full")
            return real_write_bytes(self, data)

        monkeypatch.setattr(Path, "write_bytes", _partial)
        with pytest.raises(OSError, match="disk full"):
            atomic_write_bytes(p, b"NEW_COMPLETE")
        assert p.read_bytes() == b"ORIGINAL_COMPLETE"

    def test_asset_download_failure_keeps_existing_file_intact(
        self,
        tmp_path,
        monkeypatch,
    ):
        """AssetDownloader must not corrupt a previously archived asset when disk write fails.

        AssetDownloader 写盘失败时不得破坏此前已归档资产。"""
        dest_dir = tmp_path / "assets" / "files"
        dest_dir.mkdir(parents=True)
        existing = dest_dir / "report.md"
        existing.write_bytes(b"ORIGINAL_COMPLETE")

        class FakeTransport:
            def download(self, url, timeout=120):
                return b"NEW_COMPLETE"

        real_write_bytes = Path.write_bytes

        def _partial(self, data):
            if self.name.endswith(".tmp"):
                real_write_bytes(self, data[:3])
                raise OSError("simulated disk full")
            return real_write_bytes(self, data)

        monkeypatch.setattr(Path, "write_bytes", _partial)
        asset = Asset(
            uuid="asset-1",
            asset_type="RESEARCH_REPORT",
            filename="report.md",
            url="https://example.invalid/report.md",
        )
        n_ok = AssetDownloader(FakeTransport(), delay=0).download_all([asset], dest_dir)
        assert n_ok == 0
        assert asset.downloaded_to == ""
        assert existing.read_bytes() == b"ORIGINAL_COMPLETE"


class TestWriterLeavesNoResidue:
    def test_write_thread_products_complete_and_no_tmp(self, tmp_path):
        """write_thread produces all products with zero temp residue; hidden temp
        names are invisible to the archive globs.

        write_thread 产出全部产物且零临时残留；隐藏临时名对归档 glob 不可见。"""
        w = FilesystemWriter(tmp_path)
        d = w.write_thread(_conv(2))
        assert json.loads((d / "thread.json").read_text())["web_uuid"] == UUID
        assert (d / "conversation.md").exists()
        assert len(list((d / "turns").glob("turn_*.md"))) == 2
        assert list(tmp_path.rglob("*.tmp")) == [], "归档树内不应有任何 tmp 残留"
        # The hidden temp name must never be picked up as an archive file
        # 隐藏临时名绝不能被当作归档文件捕获
        assert list(tmp_path.glob("*/*/*/thread.json")) == [d / "thread.json"]

    def test_write_thread_idempotent_rerun_no_residue(self, tmp_path):
        """Re-export of the same state stays idempotent and residue-free.

        同状态重导保持幂等且无残留。"""
        w = FilesystemWriter(tmp_path)
        d1 = w.write_thread(_conv(2))
        before = (d1 / "conversation.md").read_text()
        assert w.write_thread(_conv(2)) == d1
        assert (d1 / "conversation.md").read_text() == before
        assert list(tmp_path.rglob("*.tmp")) == []


class TestRerenderNoResidue:
    def test_rerender_leaves_no_tmp(self, rendered, tmp_path):
        """The offline re-render pipeline also leaves zero temp residue.

        离线重渲管线同样零临时残留。"""
        work, _ = rendered("search_demo")
        assert list(work.rglob("*.tmp")) == []
        assert (work / "conversation.md").exists()
