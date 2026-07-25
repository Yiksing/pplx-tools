"""Unit tests: sites/perplexity/parsers.py (match_stub_workflows) and
sites/perplexity/render.py (recursion/dedup guards for nested WORKFLOW_ITEM_WORKFLOW rendering).

Matching semantics of match_stub_workflows (calibrated against real capture f517734c):
- stub turn = trigger=="subagent_result" with no workflow steps in blocks;
- candidates = workflow_payload nested at the top level of background_entries,
  excluding ids already anchored by the main entry;
- |background completion time − stub creation time| ≤ tol_s, paired globally in
  ascending time-delta order, each background consumed only once.

单元测试：sites/perplexity/parsers.py（match_stub_workflows）与
sites/perplexity/render.py（WORKFLOW_ITEM_WORKFLOW 嵌套渲染的递归/去重守卫）。

match_stub_workflows 的匹配语义（f517734c 实测标定）：
- 桩轮 = trigger=="subagent_result" 且 blocks 无任何 workflow steps；
- 候选 = background_entries 顶层嵌套 workflow_payload，排除主 entry 已锚定 id；
- |后台完成时间 − 桩创建时间| ≤ tol_s 全局按时间差升序配对，每个后台只消费一次。
"""

from __future__ import annotations

from datetime import datetime, timezone

from pplx_export.sites.perplexity import parsers
from pplx_export.sites.perplexity.render import render_wf_item


def _us(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1e6)


class _Turn:
    """match_stub_workflows only reads uuid/index/created_us; a lightweight stand-in suffices.

    match_stub_workflows 只读 uuid/index/created_us，轻量替身即可。"""

    def __init__(self, uuid, index, created_iso):
        self.uuid = uuid
        self.index = index
        self.created_us = _us(created_iso)


def _wp(wid, headline, completed, n_steps=1, with_answer=False):
    steps = []
    for i in range(n_steps):
        items = [{"type": "WORKFLOW_ITEM_TEXT",
                  "payload": {"text_payload": {"text": f"步骤{i}内容", "chunks": [f"步骤{i}内容"]}}}]
        steps.append({"status": "COMPLETED", "title": f"s{i}", "items": items, "id": f"{wid}-s{i}"})
    if with_answer:
        steps.append({"status": "COMPLETED", "title": "ans", "id": f"{wid}-ans",
                      "items": [{"type": "WORKFLOW_ITEM_TEXT",
                                 "payload": {"text_payload": {"variant": "answer", "text": "结论",
                                                              "chunks": ["结论"]}}}]})
    return {"id": wid, "headline": headline, "status": "WORKFLOW_COMPLETED",
            "steps": steps, "completed_at": completed}


def _bg(uuid, wp, updated="2026-06-23T05:57:26.000000+00:00"):
    return {"uuid": uuid, "entry_updated_datetime": updated, "is_background": True,
            "blocks": [{"workflow_block": {"status": "WORKFLOW_COMPLETED", "steps": [
                {"status": "COMPLETED", "title": "", "id": wp["id"] + ":workflow",
                 "items": [{"type": "WORKFLOW_ITEM_WORKFLOW",
                            "payload": {"workflow_payload": wp}}]}]}}]}


def _blocks(entries=(), backgrounds=()):
    return {"entries": list(entries), "background_entries": list(backgrounds)}


def _stub_entry(uuid, with_steps=False):
    blocks = []
    if with_steps:
        blocks = [{"workflow_block": {"steps": [{"id": "s1", "items": []}]}}]
    return {"uuid": uuid, "trigger": "subagent_result", "blocks": blocks}


def _anchor_entry(uuid, wid):
    wp_item = {"type": "WORKFLOW_ITEM_WORKFLOW",
               "payload": {"workflow_payload": {"id": wid, "headline": "已锚定",
                                                "objective_chunks": ["任务"], "steps": []}}}
    step = {"id": wid + ":workflow", "items": [wp_item]}
    return {"uuid": uuid, "trigger": None,
            "blocks": [{"workflow_block": {"steps": [step]}}]}


class TestMatchStubWorkflows:
    def test_basic_match(self):
        """An unanchored background within the window matches the stub turn.

        窗内未锚定后台匹配到桩轮。"""
        turns = [_Turn("stub1", 1, "2026-06-23T05:57:25.783235+00:00")]
        blocks = _blocks(entries=[_stub_entry("stub1")],
                         backgrounds=[_bg("bg1", _wp("toolu_a", "子代理A",
                                                     "2026-06-23T05:57:25.200000+00:00"))])
        out = parsers.match_stub_workflows(turns, blocks)
        assert [wp["headline"] for wp in out[1]] == ["子代理A"]

    def test_anchored_excluded(self):
        """Ids already anchored by the main entry stay out of stub matching
        (content is rendered by sub_map in the initiating turn).

        主 entry 已锚定的 id 不参与桩匹配（内容由 sub_map 在发起轮渲染）。"""
        turns = [_Turn("stub1", 1, "2026-06-23T05:57:25.783235+00:00")]
        blocks = _blocks(
            entries=[_stub_entry("stub1"), _anchor_entry("main1", "toolu_anch")],
            backgrounds=[_bg("bg1", _wp("toolu_anch", "已锚定子代理",
                                        "2026-06-23T05:57:25.200000+00:00"))])
        assert parsers.match_stub_workflows(turns, blocks) == {}

    def test_out_of_window_unmatched(self):
        """A background outside the tolerance window does not match.

        超出容差窗的后台不匹配。"""
        turns = [_Turn("stub1", 1, "2026-06-23T05:57:25.783235+00:00")]
        blocks = _blocks(entries=[_stub_entry("stub1")],
                         backgrounds=[_bg("bg1", _wp("toolu_a", "太早",
                                                     "2026-06-23T05:47:25.000000+00:00"))])
        assert parsers.match_stub_workflows(turns, blocks) == {}

    def test_consume_once(self):
        """The same background is consumed only once, by the nearest stub.

        同一后台只被最近的桩消费一次。"""
        turns = [_Turn("stub1", 1, "2026-06-23T05:57:25.000000+00:00"),
                 _Turn("stub2", 2, "2026-06-23T05:57:29.000000+00:00")]
        blocks = _blocks(entries=[_stub_entry("stub1"), _stub_entry("stub2")],
                         backgrounds=[_bg("bg1", _wp("toolu_a", "唯一后台",
                                                     "2026-06-23T05:57:24.500000+00:00"))])
        out = parsers.match_stub_workflows(turns, blocks)
        # stub1 at Δ0.5s wins; stub2 at Δ4.5s misses out
        # Δ0.5s 的 stub1 赢得，Δ4.5s 的 stub2 落空
        assert list(out) == [1]

    def test_multi_per_stub(self):
        """One stub, multiple agents: every unanchored background in the same
        window goes to that stub.

        一桩多代理：同窗多个未锚定后台全归该桩。"""
        turns = [_Turn("stub1", 1, "2026-06-23T05:57:25.000000+00:00")]
        blocks = _blocks(entries=[_stub_entry("stub1")],
                         backgrounds=[
                             _bg("bg1", _wp("toolu_a", "后台A", "2026-06-23T05:57:24.500000+00:00")),
                             _bg("bg2", _wp("toolu_b", "后台B", "2026-06-23T05:57:25.500000+00:00"))])
        out = parsers.match_stub_workflows(turns, blocks)
        assert sorted(wp["headline"] for wp in out[1]) == ["后台A", "后台B"]

    def test_completed_at_fallback_to_entry_updated(self):
        """Without completed_at (interrupted/quota-limited), fall back to the
        background entry's update time.

        无 completed_at（中断/限额）时退后台 entry 更新时间。"""
        turns = [_Turn("stub1", 1, "2026-06-23T05:57:25.000000+00:00")]
        wp = _wp("toolu_a", "中断子代理", None)
        blocks = _blocks(entries=[_stub_entry("stub1")],
                         backgrounds=[_bg("bg1", wp, updated="2026-06-23T05:57:25.500000+00:00")])
        out = parsers.match_stub_workflows(turns, blocks)
        assert [w["headline"] for w in out[1]] == ["中断子代理"]

    def test_non_stub_subagent_result_ignored(self):
        """trigger==subagent_result with workflow steps of its own is not a stub.

        trigger==subagent_result 但自身有 workflow steps 的不是桩。"""
        turns = [_Turn("e1", 1, "2026-06-23T05:57:25.000000+00:00")]
        blocks = _blocks(entries=[_stub_entry("e1", with_steps=True)],
                         backgrounds=[_bg("bg1", _wp("toolu_a", "后台A",
                                                     "2026-06-23T05:57:24.500000+00:00"))])
        assert parsers.match_stub_workflows(turns, blocks) == {}

    def test_no_blocks(self):
        assert parsers.match_stub_workflows([_Turn("s", 1, "2026-06-23T05:57:25+00:00")], None) == {}


def _nested_item(wid, depth_payload=None, headline="嵌套X", with_answer=True):
    items = [{"type": "WORKFLOW_ITEM_TEXT",
              "payload": {"text_payload": {"text": "工作内容", "chunks": ["工作内容"]}}}]
    if with_answer:
        items.append({"type": "WORKFLOW_ITEM_TEXT",
                      "payload": {"text_payload": {"variant": "answer", "text": "结论", "chunks": ["结论"]}}})
    if depth_payload is not None:
        items.append(depth_payload)
    wp = {"id": wid, "headline": headline, "steps": [{"title": "s", "items": items, "id": wid + "-s"}]}
    return {"type": "WORKFLOW_ITEM_WORKFLOW", "payload": {"workflow_payload": wp}}


class TestRenderWfItemWorkflow:
    def test_details_block(self):
        """A non-anchor nested payload renders as a <details> collapsible block;
        the embedded answer is folded into a conclusion.

        非锚点嵌套负载渲染为 <details> 折叠块，内嵌 answer 收为结论。"""
        out = render_wf_item(_nested_item("toolu_x"))
        assert out.startswith("<details>")
        assert "🧩 嵌套工作流：嵌套X（1 步骤 · 有结论）" in out
        assert "**结论：**" in out and out.rstrip().endswith("</details>")

    def test_anchor_skipped(self):
        """Subagent anchors (objective_chunks / is_background_anchor) are not
        rendered here (the sub_map path handles them).

        子代理锚点（objective_chunks / is_background_anchor）不在此渲染（sub_map 路径负责）。"""
        it = _nested_item("toolu_x")
        it["payload"]["workflow_payload"]["objective_chunks"] = ["任务"]
        assert render_wf_item(it) == ""
        it2 = _nested_item("toolu_x")
        it2["payload"]["workflow_payload"]["is_background_anchor"] = True
        assert render_wf_item(it2) == ""

    def test_council_skipped(self):
        """LLM_COUNCIL nesting is rendered by the council_research branch.

        LLM_COUNCIL 嵌套由 council_research 分支渲染。"""
        it = _nested_item("toolu_x")
        it["payload"]["workflow_payload"]["mode"] = "LLM_COUNCIL"
        assert render_wf_item(it) == ""

    def test_empty_payload_keeps_placeholder(self):
        """An empty payload without embedded steps keeps the placeholder behavior.

        无内嵌 steps 的空负载保持占位行为。"""
        it = {"type": "WORKFLOW_ITEM_WORKFLOW",
              "payload": {"workflow_payload": {"id": "toolu_x", "headline": "空", "steps": []}}}
        assert render_wf_item(it) == "（WORKFLOW_ITEM_WORKFLOW）"

    def test_recursion_depth_limit(self):
        """Recursion depth is capped at 2 levels: the 3rd-level nest is
        truncated to a limit placeholder.

        递归深度限 2 层：第 3 层嵌套截断为上限占位。"""
        lvl3 = _nested_item("toolu_l3", headline="第三层")
        lvl2 = _nested_item("toolu_l2", depth_payload=lvl3, headline="第二层")
        lvl1 = _nested_item("toolu_l1", depth_payload=lvl2, headline="第一层")
        out = render_wf_item(lvl1)
        assert "第一层" in out and "第二层" in out, "前两层应正常展开"
        assert "已达递归上限" in out, "第三层应被深度限制截断"

    def test_self_reference_guard(self):
        """Id-set dedup: a self-referencing payload does not recurse forever.

        id 集合去重：自引用负载不无限递归。"""
        it = _nested_item("toolu_self")
        # Self-reference
        # 自引用
        it["payload"]["workflow_payload"]["steps"][0]["items"].append(it)
        out = render_wf_item(it)
        assert "已达递归上限" in out
