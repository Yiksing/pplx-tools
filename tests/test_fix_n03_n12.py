"""N-03 / N-12 regression: shared citation-dedup implementation + turns/ leftover cleanup.

N-03 (originally rerender_cmd.py:44-45 vs adapter.py:90-94): re-render did not dedup
citations by url, so the citation count in the conversation.md header disagreed with
sources.json.count (the export-path dedup count); 146 mismatches among 454 threads
observed. Fix: parsers.dedup_citations as a shared pure function, called by both
adapter and rerender (aligned behavior: dedup by url, first occurrence wins, sort by name).

N-12 (the turns/ writes in fs_writer.py / rerender_cmd.py): overwrite-only, so stale
turn_NNNN.md files lingered when the turn count shrank. Fix: before writing, delete old
files numbered above the current turn count (without wiping the directory, preserving
the mtime of unchanged files).

Fully offline: synthesize a minimal raw_entries.json, then run rerender / write_thread;
no network access.

N-03 / N-12 回归：引文去重共享实现 + turns/ 残留清理。

N-03（原 rerender_cmd.py:44-45 vs adapter.py:90-94）：re-render 不按 url 去重引文，
conversation.md 头「引文: N」与 sources.json.count（export 路径去重计数）不一致，
实测 454 线程中 146 个 mismatch。修复：parsers.dedup_citations 共享纯函数，
adapter 与 rerender 都调用它（行为对齐：按 url 去重、首个出现者为准、按 name 排序）。

N-12（fs_writer.py / rerender_cmd.py 写 turns/ 处）：只覆写不清理，轮数缩减时
旧 turn_NNNN.md 残留。修复：写前删除编号高于当前轮数的旧文件（不清空目录，
保留未变文件 mtime）。

全离线：合成最小 raw_entries.json 后跑 rerender / write_thread，不触网。
"""

import json
import re

from pplx_export.commands.rerender_cmd import rerender
from pplx_export.core.models import Conversation, Turn
from pplx_export.sites.perplexity import parsers
from pplx_export.sites.perplexity.fs_writer import FilesystemWriter
from pplx_export.sites.perplexity.parsers import dedup_citations, norm_source


def _cit(name: str, url: str):
    return norm_source({"name": name, "url": url})


def _turn(*cits):
    return Turn(citations=list(cits))


class TestN03DedupCitations:
    def test_dedup_by_url_keeps_first(self):
        t1 = _turn(_cit("a", "u1"), _cit("b", "u2"))
        # Same url, different name: first occurrence wins
        # 同 url 不同 name：首个出现者为准
        t2 = _turn(_cit("c", "u1"))
        out = dedup_citations([t1, t2])
        assert [c.url for c in out] == ["u1", "u2"]
        assert out[0].name == "a"

    def test_sorted_by_name(self):
        out = dedup_citations([_turn(_cit("zzz", "u1"), _cit("aaa", "u2"))])
        assert [c.name for c in out] == ["aaa", "zzz"]

    def test_cross_turn_duplicates_removed(self):
        t1 = _turn(_cit("s1", "u1"), _cit("s2", "u2"))
        t2 = _turn(_cit("s1", "u1"), _cit("s3", "u3"))
        assert len(dedup_citations([t1, t2])) == 3

    def test_empty(self):
        assert dedup_citations([]) == []
        assert dedup_citations([_turn()]) == []


def _entry(i, sources):
    """Minimal search-turn entry: query + FINAL answer + sources.

    最小 search 轮 entry：query + FINAL 答案 + sources。"""
    return {
        "uuid": f"e{i}",
        "query_str": f"q{i}",
        "created_us": 1700000000000000 + i,
        "updated_us": 1700000000000000 + i,
        "author_username": "tester",
        "sources": sources,
        "text": json.dumps([{
            "step_type": "FINAL",
            "content": {"answer": json.dumps(
                {"answer": f"第 {i} 轮答案，长度足够通过提取守卫。"},
                ensure_ascii=False)},
        }], ensure_ascii=False),
    }


def _write_thread(dst, entries, title="t"):
    """Synthesize a minimal thread directory (search mode, no raw_blocks.json).

    合成最小线程目录（search 模式，无 raw_blocks.json）。"""
    dst.mkdir(parents=True, exist_ok=True)
    doc = {"thread_metadata": {"title": title}, "entries": entries}
    (dst / "raw_entries.json").write_text(json.dumps(doc, ensure_ascii=False))
    (dst / "thread.json").write_text(json.dumps({
        "web_uuid": "00000000-0000-0000-0000-000000000000",
        "title": title, "mode": "search", "author": "tester"}, ensure_ascii=False))


# Cross-turn duplicate-citation fixture: 4 citations after per-turn dedup,
# 3 after cross-turn dedup (u1 repeats across both turns)
# 跨轮重复引文素材：逐轮去重后共 4 条，跨轮去重后 3 条（u1 在两轮中重复）
ENTRIES = [
    _entry(1, [{"name": "b-src", "url": "u2"}, {"name": "a-src", "url": "u1"}]),
    _entry(2, [{"name": "a-src", "url": "u1"}, {"name": "c-src", "url": "u3"}]),
]


class TestN03ExportRerenderConsistent:
    def test_conversation_header_count_matches_dedup(self, tmp_path):
        turns = [parsers.parse_turn(e, i + 1) for i, e in enumerate(ENTRIES)]
        # The fixture really has cross-turn duplicates: undeduped 4 > deduped 3
        # (otherwise the test cannot discriminate)
        # 素材确有跨轮重复：不去重 4 条 > 去重 3 条（否则测试无区分度）
        assert sum(len(t.citations) for t in turns) == 4
        # Export path (the adapter shares this function)
        # export 路径（adapter 共用此函数）
        expected = len(parsers.dedup_citations(turns))
        assert expected == 3

        d = tmp_path / "thread"
        _write_thread(d, ENTRIES)
        assert rerender(d)
        head = (d / "conversation.md").read_text()[:400]
        n = int(re.search(r"引文: (\d+)", head).group(1))
        # Citation count in the rerender output == export-path dedup count
        # (pre-N-03: n would be 4)
        # rerender 产物的引文计数 == export 路径去重计数（N-03 前：n 会是 4）
        assert n == expected


class TestN12TurnsCleanup:
    def test_stale_turn_files_removed_on_shrink(self, tmp_path):
        d = tmp_path / "thread"
        _write_thread(d, ENTRIES)
        assert rerender(d)
        turns_dir = d / "turns"
        assert sorted(p.name for p in turns_dir.glob("turn_*.md")) == [
            "turn_0001.md", "turn_0002.md"]
        # Simulate stale leftovers from before the turn count shrank
        # (high-numbered turn files)
        # 模拟轮数缩减前的旧产物残留（高编号 turn 文件）
        (turns_dir / "turn_0003.md").write_text("残留")
        (turns_dir / "turn_0004.md").write_text("残留")
        assert rerender(d)
        assert sorted(p.name for p in turns_dir.glob("turn_*.md")) == [
            "turn_0001.md", "turn_0002.md"]

    def test_non_numeric_turn_files_untouched(self, tmp_path):
        d = tmp_path / "thread"
        _write_thread(d, ENTRIES)
        assert rerender(d)
        # Non-numeric suffix: not produced by this tool, leave untouched
        # 非数字编号：不属本工具产物，不动
        odd = d / "turns" / "turn_notes.md"
        odd.write_text("手工备注")
        assert rerender(d)
        assert odd.exists()

    def test_fs_writer_cleans_stale_turns(self, tmp_path):
        conv = Conversation(
            web_uuid="abcdef12-0000-0000-0000-000000000000",
            title="t", mode="search", author="tester",
            last_updated="2026-07-22T00:00:00Z",
            turns=[Turn(index=1, query="q1", created_us=1700000000000001),
                   Turn(index=2, query="q2", created_us=1700000000000002)],
        )
        w = FilesystemWriter(tmp_path)
        # adapter=None: subagent mapping is empty, purely local
        # adapter=None：子代理映射为空，纯本地
        td = w.write_thread(conv)
        stale = td / "turns" / "turn_0003.md"
        stale.write_text("残留")
        # Re-export the same thread: the leftovers should be cleaned up
        # 重导同一线程：残留应被清理
        td = w.write_thread(conv)
        assert not stale.exists()
        assert sorted(p.name for p in (td / "turns").glob("turn_*.md")) == [
            "turn_0001.md", "turn_0002.md"]
