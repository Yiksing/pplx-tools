"""Regression tests for relations: same_prompt (identical first query) /
references (thread links) / subagent_of (offline reconstruction).

Fully offline: unit tests use synthetic Conversation objects; integration tests
use tmp_path synthetic thread directories plus real raw from fixtures/
(the nested LLM_COUNCIL sub-agents of council_demo).

relations 回归测试：same_prompt（首问全等）/ references（线程链接）/ subagent_of（离线重建）。

全离线：单元测试用合成 Conversation；集成测试用 tmp_path 合成线程目录 +
fixtures/ 真实 raw（council_demo 的嵌套 LLM_COUNCIL 子代理）。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from pplx_export.commands.misc_cmd import cmd_relations
from pplx_export.core.models import Citation, Conversation, Space, SubAgent, Turn
from pplx_export.core.relations import (EVID_MANUAL, EVID_SCHEDULED, build_edges,
                                        normalize_query)
from pplx_export.sites.perplexity import parsers

FIXTURES = Path(__file__).parent / "fixtures"

U1 = "aaaaaaaa-1111-4000-8000-000000000001"
U2 = "bbbbbbbb-2222-4000-8000-000000000002"
U3 = "cccccccc-3333-4000-8000-000000000003"
U4 = "dddddddd-4444-4000-8000-000000000004"


def mkconv(uuid: str, query: str = "q", qs: str | None = None, created_us: int = 1,
           answer: str = "", citations: list[Citation] | None = None,
           subs: list[SubAgent] | None = None, space: Space | None = None) -> Conversation:
    md = {"query_source": qs} if qs else {}
    t = Turn(index=1, query=query, created_us=created_us, answer=answer,
             citations=citations or [], metadata=md)
    return Conversation(web_uuid=uuid, turns=[t], sub_agents=subs or [], space=space)


# ------------------------------------------------------------ normalize_query
# ------------------------------------------------------ normalize_query 查询归一化

class TestNormalizeQuery:
    def test_case_whitespace_trailing_punct(self):
        assert normalize_query("  What is  示例模型?\n") == normalize_query("what is 示例模型？ ")
        assert normalize_query("A  B\nC。") == "a b c"

    def test_full_width_folded_by_nfkc(self):
        assert normalize_query("Ｗｈａｔ？") == "what"

    def test_empty_and_punct_only(self):
        assert normalize_query("") == ""
        assert normalize_query(" ？？？  ") == ""


# ---------------------------------------------------------------- same_prompt
# ------------------------------------------------------------ same_prompt 首问全等

class TestSamePrompt:
    def test_cluster_of_three_chains_not_clique(self):
        """3-thread cluster → 2 chronological chain edges (k-1), not a 3-edge clique.

        3 线程簇 → 2 条时序链式边（k-1），而非两两全连接 3 条。"""
        convs = [
            mkconv(U3, "什么是示例模型？一句话回答。", created_us=300),
            mkconv(U1, "什么是示例模型？一句话回答。", created_us=100),
            # Identical after normalization
            # 归一化后全等
            mkconv(U2, "什么是示例模型?一句话回答", created_us=200),
        ]
        edges = [e for e in build_edges(convs) if e.kind == "same_prompt"]
        assert len(edges) == 2
        assert (edges[0].src_uuid, edges[0].dst_uuid) == (U1, U2)
        assert (edges[1].src_uuid, edges[1].dst_uuid) == (U2, U3)

    def test_evidence_scheduled_vs_manual(self):
        """Both ends with query_source=perplexity_tasks → perplexity_tasks; otherwise manual_resend.

        两端 query_source 均 perplexity_tasks → perplexity_tasks；否则 manual_resend。"""
        sched = [mkconv(U1, "本周科学进展？", qs="perplexity_tasks", created_us=1),
                 mkconv(U2, "本周科学进展？", qs="perplexity_tasks", created_us=2)]
        e = next(e for e in build_edges(sched) if e.kind == "same_prompt")
        assert EVID_SCHEDULED in e.evidence

        mixed = [mkconv(U1, "本周科学进展？", qs="perplexity_tasks", created_us=1),
                 mkconv(U2, "本周科学进展？", qs="default", created_us=2)]
        e = next(e for e in build_edges(mixed) if e.kind == "same_prompt")
        assert EVID_MANUAL in e.evidence

        no_qs = [mkconv(U1, "本周科学进展？", created_us=1),
                 mkconv(U2, "本周科学进展？", created_us=2)]
        e = next(e for e in build_edges(no_qs) if e.kind == "same_prompt")
        assert EVID_MANUAL in e.evidence

    def test_singleton_and_empty_query_no_edge(self):
        convs = [mkconv(U1, "unique question", created_us=1),
                 mkconv(U2, "", created_us=2), mkconv(U3, " ？？ ", created_us=3)]
        assert not [e for e in build_edges(convs) if e.kind == "same_prompt"]

    def test_query_source_parsed_from_raw_entry(self):
        """parse_turn lands entry.query_source into Turn.metadata (the source of
        truth for same_prompt classification).

        parse_turn 把 entry.query_source 落入 Turn.metadata（same_prompt 分类真源）。"""
        t = parsers.parse_turn({"query_str": "q", "query_source": "perplexity_tasks",
                                "text": "[]", "created_us": 1})
        assert t.metadata["query_source"] == "perplexity_tasks"
        t2 = parsers.parse_turn({"query_str": "q", "text": "[]", "created_us": 1})
        assert "query_source" not in t2.metadata


# ---------------------------------------------------------------- references
# ------------------------------------------------------------ references 线程链接

class TestReferences:
    def test_citation_url_thread_link(self):
        target = mkconv(U2, "other")
        src = mkconv(U1, "src", citations=[
            Citation(name="t", url=f"https://www.perplexity.ai/search/{U2}")])
        edges = [e for e in build_edges([src, target]) if e.kind == "references"]
        assert len(edges) == 1
        assert (edges[0].src_uuid, edges[0].dst_uuid) == (U1, U2)
        assert "thread link" in edges[0].evidence

    def test_answer_text_computer_tasks_link(self):
        target = mkconv(U2, "other")
        src = mkconv(U1, "src",
                     answer=f"详见之前的分析 https://www.perplexity.ai/computer/tasks/{U2} 。")
        edges = [e for e in build_edges([src, target]) if e.kind == "references"]
        assert len(edges) == 1 and edges[0].dst_uuid == U2

    def test_bare_uuid_still_detected(self):
        target = mkconv(U2, "other")
        src = mkconv(U1, "src", answer=f"前文 {U2} 已述")
        edges = [e for e in build_edges([src, target]) if e.kind == "references"]
        assert len(edges) == 1 and "uuid mentioned" in edges[0].evidence

    def test_unarchived_and_self_link_ignored(self):
        src = mkconv(U1, "src", answer=(
            # U4 not archived
            # U4 未归档
            f"https://www.perplexity.ai/search/{U4} "
            # Self-reference
            # 自引
            f"https://www.perplexity.ai/search/{U1}"))
        assert not [e for e in build_edges([src]) if e.kind == "references"]

    def test_link_and_bare_uuid_dedup_to_single_edge(self):
        """Same (src,dst) hit by both signals yields a single edge with merged evidence.

        同一 (src,dst) 被两种信号命中只出一条边，evidence 合并。"""
        target = mkconv(U2, "other")
        src = mkconv(U1, "src", answer=(
            f"https://www.perplexity.ai/search/{U2} 即 {U2}"))
        edges = [e for e in build_edges([src, target]) if e.kind == "references"]
        assert len(edges) == 1
        assert "thread link" in edges[0].evidence and "uuid mentioned" in edges[0].evidence

    def test_subagent_sources_scanned(self):
        target = mkconv(U2, "other")
        sub = SubAgent(sub_id="toolu_X", sources=[
            Citation(name="s", url=f"https://www.perplexity.ai/thread/{U2}")])
        src = mkconv(U1, "src", subs=[sub])
        edges = [e for e in build_edges([src, target]) if e.kind == "references"]
        assert len(edges) == 1 and edges[0].dst_uuid == U2


# --------------------------------------------------------------- subagent_of
# ---------------------------------------------------------- subagent_of 离线重建

class TestSubagentOf:
    def test_conversation_level_subs_produce_edges(self):
        sub = SubAgent(sub_id="toolu_01ABC", headline="调研示例主题")
        edges = [e for e in build_edges([mkconv(U1, "q", subs=[sub])])
                 if e.kind == "subagent_of"]
        assert len(edges) == 1
        assert edges[0].src_uuid == U1
        # dst keeps run-id semantics, not a thread uuid
        # dst 保持运行 id 语义，非线程 uuid
        assert edges[0].dst_uuid == "toolu_01ABC"
        assert "调研示例主题" in edges[0].evidence

    def test_archived_subagent_thread_noted_in_evidence(self):
        """The sub-agent's background thread happens to be archived → noted in
        evidence; dst stays toolu_X (no fabricated dst swap).

        子代理后台线程恰已归档 → evidence 注明，dst 仍为 toolu_X（不虚构换 dst）。"""
        sub = SubAgent(sub_id="toolu_01ABC", headline="h", thread_uuid=U2)
        edges = [e for e in build_edges([mkconv(U1, "q", subs=[sub]), mkconv(U2, "q2")])
                 if e.kind == "subagent_of"]
        assert edges[0].dst_uuid == "toolu_01ABC"
        assert U2 in edges[0].evidence

    def test_turn_level_subs_and_dedup(self):
        sub = SubAgent(sub_id="toolu_DUP", headline="h")
        conv = mkconv(U1, "q", subs=[sub])
        # Same sub at both entry levels yields only one edge
        # 同一 sub 两级入口只出一条边
        conv.turns[0].sub_agents.append(sub)
        edges = [e for e in build_edges([conv]) if e.kind == "subagent_of"]
        assert len(edges) == 1


# ------------------------------------------------- Integration: cmd_relations (tmp_path)
# ------------------------------------------------- 集成：cmd_relations（tmp_path）

def _write_thread(root: Path, uuid: str, query: str, qs: str | None,
                  created_us: int, citation_url: str | None = None) -> Path:
    d = root / "acct" / "search" / f"2026-01-0{created_us}_t_{uuid[:8]}"
    d.mkdir(parents=True)
    (d / "thread.json").write_text(json.dumps(
        {"web_uuid": uuid, "title": "t", "mode": "search", "author": "acct",
         "space": {"uuid": "sp", "title": "S", "slug": "s-slug"}}, ensure_ascii=False))
    entry = {"uuid": f"e{created_us}", "query_str": query, "created_us": created_us,
             "text": "[]", "sources": []}
    if qs:
        entry["query_source"] = qs
    if citation_url:
        entry["sources"] = [{"name": "c", "url": citation_url}]
    (d / "raw_entries.json").write_text(json.dumps(
        {"thread_metadata": {"title": "t"}, "entries": [entry]}, ensure_ascii=False))
    return d


class TestCmdRelationsIntegration:
    def test_same_prompt_and_references_end_to_end(self, tmp_path):
        """Two real-layout thread directories: identical first query (scheduled
        task) + citation cross-link → two edge kinds in edges.jsonl.

        两个真实布局线程目录：首问全等（定时任务）+ 引文互链 → edges.jsonl 两类边。"""
        q = "本周最重要的科学进展是什么？"
        _write_thread(tmp_path, U1, q, "perplexity_tasks", 1)
        _write_thread(tmp_path, U2, q + " ", "perplexity_tasks", 2,
                      citation_url=f"https://www.perplexity.ai/search/{U1}")
        cmd_relations(tmp_path)
        edges = [json.loads(x) for x in
                 (tmp_path / "relations" / "edges.jsonl").read_text().splitlines()]
        by_kind = {}
        for e in edges:
            by_kind.setdefault(e["kind"], []).append(e)
        # same_prompt: U1→U2 chain edge, scheduled-task evidence
        # same_prompt：U1→U2 链式边，定时任务证据
        sp = by_kind["same_prompt"]
        assert len(sp) == 1 and sp[0]["src"] == U1 and sp[0]["dst"] == U2
        assert EVID_SCHEDULED in sp[0]["evidence"]
        # references: U2's citation URL points to U1
        # references：U2 的引文 URL 指向 U1
        ref = by_kind["references"]
        assert len(ref) == 1 and ref[0]["src"] == U2 and ref[0]["dst"] == U1
        # same_space: both threads in the same space
        # same_space：两线程同空间
        assert len(by_kind["same_space"]) == 2
        # graph.md summary contains the new sections
        # graph.md 摘要含新分区
        gm = (tmp_path / "relations" / "graph.md").read_text()
        assert "same_prompt" in gm and "references" in gm

    def test_subagent_of_from_real_fixture(self, tmp_path):
        """council fixture (nested LLM_COUNCIL) yields subagent_of edges via
        offline reconstruction.

        council fixture（嵌套 LLM_COUNCIL）经离线重建产出 subagent_of 边。"""
        src = FIXTURES / "council_demo"
        d = tmp_path / "acct" / "council" / "2026-07-21_t_5cbeef00"
        d.mkdir(parents=True)
        for f in ("raw_entries.json", "raw_blocks.json", "thread.json"):
            shutil.copy2(src / f, d / f)
        cmd_relations(tmp_path)
        edges = [json.loads(x) for x in
                 (tmp_path / "relations" / "edges.jsonl").read_text().splitlines()]
        sub_edges = [e for e in edges if e["kind"] == "subagent_of"]
        # Three-model council
        # 三模型委员会
        assert len(sub_edges) == 3
        assert all(e["src"] == "5cbeef00-e1a2-5b90-b22f-ca7af5c90eda" for e in sub_edges)
        assert {e["dst"] for e in sub_edges} == {
            "gpt55_thinking", "claude48opusthinking", "gemini31pro_high"}
