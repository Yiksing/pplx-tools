"""Interruption/cancellation semantics tests: unified status classification,
attribution waterfall level 3 (thread appendix), render annotations, and the
interruption registry.

Scenario fixtures:
- scenario_limit_interrupted (f517734c trimmed: 3 entries + 6 background):
  limit interruption (locked_reason=spending_limit_exceeded +
  WORKFLOW_AWAITING_NEXT_STEPS) — workflow headline / subagent / stub-turn
  summary annotated with ⏸; the unconsumed 38-step「撰写2.2示例主题B」payload
  lands in the appendix.
- scenario_canceled (50c5ada6 trimmed: single entry): WORKFLOW_CANCELED
  annotated with ⛔.

中断/取消语义测试：统一状态分类、归属瀑布第三级（线程附录）、渲染标注、中断登记。

场景 fixture：
- scenario_limit_interrupted（f517734c 裁剪：3 entry + 6 background）：限额中断
  （locked_reason=spending_limit_exceeded + WORKFLOW_AWAITING_NEXT_STEPS）——
  工作过程标题/子代理/桩轮 summary 加注 ⏸；未消费的 38 步「撰写2.2示例主题B」落入附录。
- scenario_canceled（50c5ada6 裁剪：单 entry）：WORKFLOW_CANCELED 加注 ⛔。
"""

from __future__ import annotations

from datetime import datetime, timezone

from pplx_export.core.models import Conversation, SubAgent, Turn
from pplx_export.sites.perplexity import parsers


def _us(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1e6)


class _Turn:
    """The match/collect family only reads uuid/index/created_us; a lightweight stand-in suffices.

    match/collect 系列只读 uuid/index/created_us，轻量替身即可。"""

    def __init__(self, uuid, index, created_iso):
        self.uuid = uuid
        self.index = index
        self.created_us = _us(created_iso)


def _wp(wid, headline, status="WORKFLOW_COMPLETED", completed="2026-06-23T05:57:26+00:00", n_steps=1):
    steps = [{"status": "COMPLETED", "title": f"s{i}", "id": f"{wid}-s{i}",
              "items": [{"type": "WORKFLOW_ITEM_TEXT",
                         "payload": {"text_payload": {"text": "x", "chunks": ["x"]}}}]}
             for i in range(n_steps)]
    return {"id": wid, "headline": headline, "status": status,
            "steps": steps, "completed_at": completed}


def _bg(uuid, wp, locked=None, updated="2026-06-23T05:57:26.000000+00:00"):
    e = {"uuid": uuid, "entry_updated_datetime": updated, "is_background": True,
         "blocks": [{"workflow_block": {"status": wp["status"], "steps": [
             {"status": "COMPLETED", "title": "", "id": wp["id"] + ":workflow",
              "items": [{"type": "WORKFLOW_ITEM_WORKFLOW",
                         "payload": {"workflow_payload": wp}}]}]}}]}
    if locked:
        e["locked_reason"] = locked
    return e


def _stub_entry(uuid):
    return {"uuid": uuid, "trigger": "subagent_result", "blocks": []}


def _anchor_entry(uuid, wp):
    return {"uuid": uuid, "blocks": [{"workflow_block": {"status": "WORKFLOW_COMPLETED", "steps": [
        {"status": "COMPLETED", "tool_name": "run_subagent", "id": wp["id"] + ":workflow",
         "items": [{"type": "WORKFLOW_ITEM_WORKFLOW", "payload": {"workflow_payload": wp}}]}]}}]}


# ── Unified status classification ───────────────────────────
# ── 统一状态分类 ─────────────────────────────────────────────

def test_classify_wf_status_mapping():
    c = parsers.classify_wf_status
    assert c(None) == "completed" and c("") == "completed"
    assert c("COMPLETED") == "completed" and c("WORKFLOW_COMPLETED") == "completed"
    assert c("WORKFLOW_AWAITING_NEXT_STEPS", "spending_limit_exceeded") == "limit_interrupted"
    assert c("WORKFLOW_AWAITING_NEXT_STEPS") == "awaiting"
    assert c("WORKFLOW_AWAITING_NEXT_STEPS", "other_reason") == "awaiting"
    assert c("WORKFLOW_CANCELED") == "canceled"
    # canceled takes precedence over locked
    # canceled 优先于 locked
    assert c("WORKFLOW_CANCELED", "spending_limit_exceeded") == "canceled"
    assert c("WORKFLOW_SOME_FUTURE_STATUS") == "other"


def test_wf_status_tag_labels():
    t = parsers.wf_status_tag
    assert t("WORKFLOW_COMPLETED") == "" and t(None) == "", "COMPLETED 不应加注（零 diff 保证）"
    assert t("WORKFLOW_FUTURE") == "", "未知状态不加注（按现状输出原枚举串）"
    assert t("WORKFLOW_AWAITING_NEXT_STEPS", "spending_limit_exceeded") == "⏸ 限额中断（内容截至中断点）"
    assert t("WORKFLOW_AWAITING_NEXT_STEPS") == "⏸ 中断待续"
    assert t("WORKFLOW_CANCELED") == "⛔ 已取消"


# ── Attribution waterfall level 3: appendix collection ───────
# ── 归属瀑布第三级：附录收集 ──────────────────────────────────

def test_collect_unconsumed_background_waterfall():
    """Waterfall priority: anchored/stub-window payloads never enter the appendix; unconsumed payloads enter it exactly once.

    瀑布优先级：锚定/桩窗负载不进附录；未消费负载进附录且只进一次。"""
    anchored = _wp("toolu_anchor", "已锚定")
    stubbed = _wp("toolu_stub", "桩窗命中", completed="2026-06-23T05:57:25+00:00")
    orphan = _wp("toolu_orphan", "无人认领", status="WORKFLOW_AWAITING_NEXT_STEPS",
                 completed="", n_steps=3)
    blocks = {"entries": [_anchor_entry("e1", anchored), _stub_entry("e2")],
              "background_entries": [_bg("b1", anchored), _bg("b2", stubbed),
                                     # Interrupted payload has empty completion time → falls back to background update time;
                                     # only a >10s gap from stub creation time escapes stub-window consumption (stranded → appendix)
                                     # 中断负载的完成时间为空 → 退后台更新时间；
                                     # 与桩创建时间差 >10s 才不被桩窗消费（滞留→附录）
                                     _bg("b3", orphan, locked="spending_limit_exceeded",
                                         updated="2026-06-23T06:11:49.000000+00:00")]}
    turns = [_Turn("e1", 1, "2026-06-23T05:50:00Z"), _Turn("e2", 2, "2026-06-23T05:57:26Z")]
    out = parsers.collect_unconsumed_background(turns, blocks)
    assert [i["wp"]["id"] for i in out] == ["toolu_orphan"], \
        "附录应只收既未锚定也未被桩窗消费的负载"
    assert out[0]["locked_reason"] == "spending_limit_exceeded"
    assert out[0]["updated"], "附录条目应带后台 entry 更新时间（时间范围用）"
    # Idempotent: repeated calls return identical results; no double consumption with match_stub_workflows
    # 幂等：重复调用结果一致；且与 match_stub_workflows 不重复消费
    assert parsers.collect_unconsumed_background(turns, blocks) == out
    matched = parsers.match_stub_workflows(turns, blocks)
    consumed = {w.get("id") for v in matched.values() for w in v}
    assert consumed == {"toolu_stub"} and not (consumed & {i["wp"]["id"] for i in out})


def test_collect_unconsumed_background_empty():
    assert parsers.collect_unconsumed_background([], None) == []
    assert parsers.collect_unconsumed_background([], {"entries": []}) == []


def test_waterfall_top_level_only():
    """Two-level nesting defense: when a parent payload contains a child payload, the waterfall
    collects only the parent (the child renders with the parent as a whole, preventing double counting).
    Current data has no two-level nesting; this is structural protection against platform changes.

    二层嵌套防御：父负载含子负载时瀑布只收父（子随父整体渲染，防双重计入）。
    当前数据无二层嵌套，此为面向平台变更的结构性防护。"""
    child = _wp("toolu_child", "子负载")
    parent = _wp("toolu_parent", "父负载")
    parent["steps"].append({"status": "COMPLETED", "title": "", "id": "x",
                            "items": [{"type": "WORKFLOW_ITEM_WORKFLOW",
                                       "payload": {"workflow_payload": child}}]})
    blocks = {"entries": [], "background_entries": [_bg("b1", parent)]}
    out = parsers.collect_unconsumed_background([], blocks)
    assert [i["wp"]["id"] for i in out] == ["toolu_parent"], \
        "嵌套子负载不得独立成附录条目（随父负载渲染）"
    # Stub-window candidates likewise take only the top level
    # 桩窗候选同理只取顶层
    matched = parsers.match_stub_workflows(
        [_Turn("s1", 1, "2026-06-23T05:57:26Z")],
        {"entries": [_stub_entry("s1")], "background_entries": [_bg("b1", parent)]})
    assert {w.get("id") for v in matched.values() for w in v} == {"toolu_parent"}


# ── Interruption registry and anomaly detection ──────────────
# ── 中断登记与异常检测 ────────────────────────────────────────

def test_collect_interruptions_and_scan():
    conv = Conversation()
    t = Turn(index=2, query="测试查询",
             metadata={"wf_status": "WORKFLOW_AWAITING_NEXT_STEPS",
                       "locked_reason": "spending_limit_exceeded"})
    t.stub_wfs = [{"id": "w1", "headline": "桩窗子代理", "status": "WORKFLOW_CANCELED"}]
    conv.turns = [t]
    conv.unconsumed_bgs = [{"wp": {"id": "w2", "headline": "附录负载", "status": "WORKFLOW_COMPLETED"},
                            "locked_reason": None}]
    out = parsers.collect_interruptions(conv)
    assert {"location": "turn_0002", "kind": "limit_interrupted",
            "headline": "测试查询", "status": "WORKFLOW_AWAITING_NEXT_STEPS"} in out
    assert {"location": "turn_0002/subagent_stub", "kind": "canceled",
            "headline": "桩窗子代理", "status": "WORKFLOW_CANCELED"} in out
    # Appendix entries are registered in any status (completed but stranded in raw is still worth showing)
    # 附录条目任何状态都登记（completed 但滞留 raw 也值得可见）
    assert {"location": "background_unassigned", "kind": "completed",
            "headline": "附录负载", "status": "WORKFLOW_COMPLETED"} in out
    # Healthy thread: no interruption entries (fs_writer omits the interruptions key accordingly)
    # 健康线程：无中断条目（fs_writer 据此省略 interruptions 键）
    healthy = Conversation(turns=[Turn(index=1, metadata={"wf_status": "WORKFLOW_COMPLETED"})])
    assert parsers.collect_interruptions(healthy) == []


def test_collect_interruptions_anchored_subagent():
    """Anchored subagent (run_subagent ↔ background): registered even when the background's
    actual status is not completed (observed in a real thread: anchor side COMPLETED,
    background CANCELED; the rendering was annotated, but the registry missed it).

    锚定子代理（run_subagent ↔ 后台）：后台实际状态非 completed 也登记
    （实测某线程：锚点侧 COMPLETED、后台 CANCELED，渲染已标注，登记曾漏）。"""
    conv = Conversation()
    t = Turn(index=3, query="锚定子代理测试")
    t.wf_block = {"steps": [
        {"id": "abc123:workflow", "tool_name": "run_subagent", "items": [
            {"type": "WORKFLOW_ITEM_WORKFLOW",
             "payload": {"workflow_payload": {"id": "sub-1", "objective_chunks": ["做任务"]}}}]}]}
    conv.turns = [t]
    sub = SubAgent(sub_id="sub-1", headline="锚定任务", status="WORKFLOW_CANCELED")
    out = parsers.collect_interruptions(conv, {"sub-1": sub})
    assert {"location": "turn_0003/subagent", "kind": "canceled",
            "headline": "锚定任务", "status": "WORKFLOW_CANCELED"} in out
    # Not registered when sub_map is omitted (no mapping offline) or the subagent is completed
    # 不传 sub_map（离线无映射）或子代理 completed 时不登记
    assert parsers.collect_interruptions(conv) == []
    ok = SubAgent(sub_id="sub-1", headline="锚定任务", status="WORKFLOW_COMPLETED")
    assert parsers.collect_interruptions(conv, {"sub-1": ok}) == []


def test_scan_wf_anomalies():
    blocks = {
        "entries": [
            {"uuid": "aaaa1111", "blocks": [{"workflow_block": {"status": "WORKFLOW_COMPLETED"}}]},
            {"uuid": "bbbb2222", "locked_reason": "spending_limit_exceeded",
             "blocks": [{"workflow_block": {"status": "WORKFLOW_AWAITING_NEXT_STEPS"}}]},
        ],
        "background_entries": [
            {"uuid": "cccc3333", "blocks": [{"workflow_block": {"status": "WORKFLOW_CANCELED"}}]},
        ],
    }
    out = parsers.scan_wf_anomalies(blocks)
    kinds = {(a["location"], a["kind"]) for a in out}
    assert kinds == {("entry:bbbb2222", "limit_interrupted"), ("background:cccc3333", "canceled")}
    assert parsers.scan_wf_anomalies(None) == []


# ── Scenario: limit interruption (f517734c trimmed) ──────────
# ── 场景：限额中断（f517734c 裁剪）──────────────────────────

def test_scenario_limit_interrupted_annotations(rendered):
    """Limit-interruption annotations: workflow headline / subagent headline / stub-turn summary
    annotated; COMPLETED not annotated.

    限额中断标注：工作过程标题 / 子代理标题 / 桩轮 summary 三处加注；COMPLETED 不加注。"""
    work, golden = rendered("scenario_limit_interrupted")
    t1 = (work / "turns" / "turn_0001.md").read_text()
    assert "## 工作过程（10 步骤 · WORKFLOW_AWAITING_NEXT_STEPS · ⏸ 限额中断（内容截至中断点））" in t1
    # Anchored subagent annotated via the background side's true status (anchor side may lag; bg's AWAITING used here)
    # 锚定子代理经后台侧真实状态加注（锚点侧状态可能滞后，此处取 bg 的 AWAITING）
    assert "### 步骤 9 · 🤖 子代理：撰写2.2示例主题B · ⏸ 限额中断（内容截至中断点）" in t1
    # COMPLETED subagent (section-2.3 example topic C) is not annotated
    # COMPLETED 子代理（撰写2.3示例主题C）不加注
    assert "### 步骤 10 · 🤖 子代理：撰写2.3示例主题C\n" in t1
    t2 = (work / "turns" / "turn_0002.md").read_text()
    assert "🤖 子代理：撰写2.2示例主题B（2 步骤 · 无结论 · ⏸ 限额中断（内容截至中断点））" in t2, \
        "桩轮关联的 AWAITING 负载应在 summary 加注"
    t3 = (work / "turns" / "turn_0003.md").read_text()
    assert "🤖 子代理：撰写2.5示例主题D（5 步骤 · 无结论）" in t3
    assert "⏸" not in t3 and "⛔" not in t3, "COMPLETED 桩窗负载不应加注"
    # golden byte-for-byte (turns + conversation.md)
    # golden 逐字节（turns + conversation.md）
    for g in sorted((golden).glob("turn_*.md")):
        assert (work / "turns" / g.name).read_text() == g.read_text(), f"{g.name} 与 golden 不一致"
    assert (work / "conversation.md").read_text() == (golden / "conversation.md").read_text()


def test_scenario_limit_interrupted_appendix(rendered):
    """Thread appendix: collects only unconsumed payloads — the 38-step
    「撰写2.2示例主题B」; anchored/stub-window payloads excluded; no double rendering.

    线程附录：只收未消费负载（38 步「撰写2.2示例主题B」）；锚定/桩窗负载不进；不双渲染。"""
    work, _ = rendered("scenario_limit_interrupted")
    cm = (work / "conversation.md").read_text()
    assert "## 后台任务（未归入轮次）" in cm, "附录段缺失"
    appendix = cm[cm.index("## 后台任务（未归入轮次）"):]
    assert "🤖 后台任务：撰写2.2示例主题B（38 步骤 · 无结论 · ⏸ 限额中断（内容截至中断点））" in appendix
    assert "locked_reason: `spending_limit_exceeded`" in appendix
    assert "2035-12-26 01:24:56 → 2035-12-26 01:38:37" in appendix, "附录应含时间范围"
    # Waterfall priority: anchored (topics 2.1/2.3) and stub-window (2-step/5-step/0-step payloads) do not enter the appendix
    # 瀑布优先级：锚定（撰写2.1/2.3）与桩窗（2 步/5 步/0 步负载）不进附录
    assert "撰写2.1示例主题A" not in appendix
    assert "撰写2.3示例主题C" not in appendix
    assert "撰写2.5示例主题D" not in appendix
    assert appendix.count("<details>") == 1, "附录应只含 1 条未消费负载"
    # No double rendering: the 38-step payload appears only once thread-wide (the appendix); turns/ must not contain it (appendix is thread-level)
    # 不双渲染：38 步负载全线程只出现一次（附录），turns/ 不得出现（附录属线程级）
    assert cm.count("38 步骤") == 1
    for t in (work / "turns").glob("turn_*.md"):
        assert "## 后台任务（未归入轮次）" not in t.read_text()
        assert "38 步骤" not in t.read_text()


# ── Scenario: canceled (50c5ada6 trimmed) ────────────────────
# ── 场景：已取消（50c5ada6 裁剪）─────────────────────────────

def test_scenario_canceled(rendered):
    """WORKFLOW_CANCELED: workflow headline annotated with ⛔; the answer is not backfilled for the interruption (original text kept).

    WORKFLOW_CANCELED：工作过程标题加注 ⛔；答案不为中断回填（仍原文）。"""
    work, golden = rendered("scenario_canceled")
    t1 = (work / "turns" / "turn_0001.md").read_text()
    assert "## 工作过程（0 步骤 · WORKFLOW_CANCELED · ⛔ 已取消）" in t1
    assert "## Answer\n\nAnswer skipped." in t1
    assert "后台任务（未归入轮次）" not in (work / "conversation.md").read_text(), \
        "无未消费负载时不应出现附录段"
    assert (work / "turns" / "turn_0001.md").read_text() == (golden / "turn_0001.md").read_text()
    assert (work / "conversation.md").read_text() == (golden / "conversation.md").read_text()
