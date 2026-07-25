"""Render snapshot regression: fixture raw JSON → normalize → parse → render
end-to-end, compared byte-for-byte against the archive's current products
(golden snapshots).

Covers all five modes (search / deep-research / computer / council / study)
plus five trimmed defect scenarios (computer answer fallback, sub-agent
fallback, USER_RESPONSE Q&A pairs, subagent_result stub-turn association,
nested WORKFLOW_ITEM_WORKFLOW collapsed rendering).

渲染快照回归：fixture 原始 JSON → normalize → parse → render 全链路，
与归档现行产物（golden snapshot）逐字节比对。

覆盖五种模式（search / deep-research / computer / council / study）+ 五个裁剪缺陷场景
（computer 答案兜底、子代理 fallback、USER_RESPONSE 问答对、subagent_result 桩轮关联、
嵌套 WORKFLOW_ITEM_WORKFLOW 折叠渲染）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

# Full-thread snapshots: golden is the archive's current conversation.md + turns/
# (products of the batch-2 full-repo re-render)
# 全线程快照：golden 为归档现行 conversation.md + turns/（批次 2 全档重渲染后的产物）
FULL = [
    "search_demo",
    "deep_research_demo",
    "computer_demo",
    "council_demo",
    "study_demo",
]

# Trimmed scenarios: golden is the archive's corresponding turn files (turn
# numbers rewritten to 1)
# 裁剪场景：golden 为归档对应轮文件（轮号已改写为 1）
SCENARIOS = [
    "scenario_computer_answer_fallback",
    "scenario_subagent_fallback",
    "scenario_user_response",
    "scenario_subagent_stub",
    "scenario_workflow_item_nested",
]

# dict-repr residue signature: a Python dict literal (e.g. {'type': '...')
# appearing in rendered text
# dict repr 残留特征：渲染文本里出现 Python 字典字面量（如 {'type': '...'）
DICT_REPR_RE = re.compile(r"\{'[a-z_]+':")


@pytest.mark.parametrize("name", FULL)
def test_full_thread_byte_identical(rendered, name):
    """End-to-end re-render is byte-identical to the archive golden
    (conversation.md + all turns/).

    全链路重渲与归档 golden 逐字节一致（conversation.md + 全部 turns/）。"""
    work, golden = rendered(name)
    assert (work / "conversation.md").read_text() == (golden / "conversation.md").read_text(), \
        f"{name}: conversation.md 与归档不一致"
    gturns = sorted((golden / "turns").glob("turn_*.md"))
    rturns = sorted((work / "turns").glob("turn_*.md"))
    assert len(rturns) == len(gturns), f"{name}: 轮数 {len(rturns)} != golden {len(gturns)}"
    for r, g in zip(rturns, gturns):
        assert r.read_text() == g.read_text(), f"{name}: {g.name} 与归档不一致"


@pytest.mark.parametrize("name", FULL)
def test_full_thread_content_invariants(rendered, name):
    """Content invariants: answers are never the empty placeholder
    ("(无)"); no dict-repr residue.

    内容不变式：答案非「(无)」、无 dict repr 残留。"""
    work, _ = rendered(name)
    cm = (work / "conversation.md").read_text()
    assert "### Answer\n(无)" not in cm, f"{name}: 存在空答案轮"
    assert not DICT_REPR_RE.search(cm), f"{name}: conversation.md 有 dict repr 残留"
    for t in sorted((work / "turns").glob("turn_*.md")):
        assert not DICT_REPR_RE.search(t.read_text()), f"{name}: {t.name} 有 dict repr 残留"


def test_deep_research_math_delims_end_to_end(rendered):
    """Math delimiters: a thread whose raw contains \\( renders body text as
    $$, with no \\( \\[ residue.

    公式分隔符：raw 含 \\( 的线程渲染后正文为 $$，无 \\( \\[ 残留。"""
    raw = (FIXTURES / "deep_research_demo" / "raw_entries.json").read_text()
    assert "\\(" in raw, "fixture 前提失效：raw 应含 \\( 以覆盖分隔符转换"
    work, _ = rendered("deep_research_demo")
    cm = (work / "conversation.md").read_text()
    assert cm.count("$$") >= 2, "公式块未渲染为 $$"
    assert "\\(" not in cm and "\\[" not in cm, "正文残留 \\( 或 \\["


@pytest.mark.parametrize("name", SCENARIOS)
def test_scenario_turn_byte_identical(rendered, name):
    """Trimmed scenarios: re-render is byte-identical to golden (as many turn
    files as golden has).

    裁剪场景：重渲与 golden 逐字节一致（golden 有几个轮文件就比几个）。"""
    work, golden = rendered(name)
    for g in sorted(golden.glob("turn_*.md")):
        assert (work / "turns" / g.name).read_text() == g.read_text(), \
            f"{name}: {g.name} 与 golden 不一致"


def test_scenario_subagent_stub(rendered):
    """subagent_result stub turn: time-associates unanchored background
    sub-agents and renders their work records.

    Anchored exclusion (anchored backgrounds are not re-rendered), no match
    outside the window, and no answer backfill (stays (无)).

    subagent_result 桩轮：时间关联到未锚定后台子代理并渲染其工作记录。

    锚定排除（已锚定的后台不重复渲染）、窗口外不匹配、答案不回填（仍为 (无)）。
    """
    work, _ = rendered("scenario_subagent_stub")
    turn = (work / "turns" / "turn_0002.md").read_text()
    assert "## 子代理工作（1 个）" in turn, "桩轮未渲染子代理工作段"
    assert "🤖 子代理：示例补充研究（合成）" in turn, "匹配到的后台子代理未渲染"
    assert "**结论：**" in turn and "这是子代理结论段落（示例文本）" in turn, "子代理结论缺失"
    assert "**引文：**" in turn and "示例水文数据库（合成）" in turn, "子代理引文缺失"
    assert "已锚定子代理" not in turn, "已锚定的后台子代理被重复渲染"
    assert "窗口外子代理" not in turn, "时间窗口外的后台子代理被误匹配"
    assert turn.rstrip().endswith("## Answer\n\n(无)"), "桩轮答案不应回填，仍为 (无)"


def test_scenario_workflow_item_nested(rendered):
    """WORKFLOW_ITEM_WORKFLOW nested payload: rendered as a <details>
    collapsed block (conclusion + citations + surrounding text unbroken).

    WORKFLOW_ITEM_WORKFLOW 嵌套负载：渲染为 <details> 折叠块（结论+引文+前后文不断裂）。"""
    work, _ = rendered("scenario_workflow_item_nested")
    turn = (work / "turns" / "turn_0001.md").read_text()
    assert "（WORKFLOW_ITEM_WORKFLOW）" not in turn, "嵌套负载仍为占位符"
    assert "<details>" in turn and "</details>" in turn, "嵌套负载未渲染为折叠块"
    assert "🧩 嵌套工作流：示例分析工具外壳封装（3 步骤 · 有结论 · 引文 2）" in turn
    assert "**结论：**" in turn and "这是子代理结论段落（示例文本）" in turn, "内嵌 answer 未渲染为结论"
    assert turn.index("嵌套工作流执行前（示例）。") < turn.index("<details>") < turn.index("嵌套工作流执行后（示例）。"), \
        "嵌套折叠块未落在前后文之间"


def test_scenario_computer_answer_fallback(rendered):
    """computer answer fallback: when plain FINAL has no answer, recover it
    from the workflow_block variant=answer.

    computer 答案兜底：plain FINAL 无答案时从 workflow_block variant=answer 找回。"""
    work, _ = rendered("scenario_computer_answer_fallback")
    cm = (work / "conversation.md").read_text()
    assert "### Answer\n(无)" not in cm, "答案兜底失败：渲染为 (无)"
    assert "已完成推送（示例）" in cm, "找回的答案文本不符合预期"


def test_scenario_subagent_fallback(rendered):
    """Sub-agent fallback: with no background match, render the headline + the
    step's own items (summary not lost).

    子代理 fallback：无 background 匹配时渲染标题 + step 自身 items（总结不丢）。"""
    work, _ = rendered("scenario_subagent_fallback")
    turn = (work / "turns" / "turn_0001.md").read_text()
    assert "🤖 子代理：" in turn, "子代理步骤标题未渲染"
    assert "**子代理结论：**" not in turn, "无 background 匹配不应出现子代理结论（那是匹配路径的产物）"
    assert "全部完成（示例）" in turn, "子代理总结 TEXT（step 自身 items）丢失"


def test_scenario_user_response(rendered):
    """USER_RESPONSE Q&A pairs: 4 questions and 4 answers fully rendered; the
    empty-query turn is marked (空).

    USER_RESPONSE 问答对：4 问 4 答完整渲染，空 query 轮标记为 (空)。"""
    work, _ = rendered("scenario_user_response")
    turn = (work / "turns" / "turn_0001.md").read_text()
    assert turn.count("**问：**") == 4 and turn.count("**答：**") == 4, "问答对数量不符"
    cm = (work / "conversation.md").read_text()
    assert "### Query\n(空)" in cm, "空 query 轮未按预期标记"
