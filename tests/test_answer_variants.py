"""Answer-rewrite variant registration tests: narrowed side_by_side_metadata
criterion + thread.json.answer_variants.

Criterion (verified by a full-repo scan on 2026-07-23, hitting the single
true case precisely): sibling_uuid is non-empty AND (selection_status is
non-empty and not SELECTION_STATUS_UNSPECIFIED, OR experiment_role lacks the
[control] prefix). Control-group experiments ([control]… + UNSPECIFIED) and
healthy threads without the field are not registered — no hit means the
answer_variants key never appears (same contract as interruptions).

答案重写变体登记测试：side_by_side_metadata 收窄判据 + thread.json.answer_variants。

判据（2026-07-23 全库扫描验证，精确命中唯一真例）：
sibling_uuid 非空 且（selection_status 非空且非 SELECTION_STATUS_UNSPECIFIED，
或 experiment_role 无 [control] 前缀）。对照组实验（[control]… + UNSPECIFIED）
与无字段的健康线程不登记——无命中不出现 answer_variants 键（与 interruptions 同契约）。
"""

from __future__ import annotations

import json
from pathlib import Path

from pplx_export.commands.rerender_cmd import rerender
from pplx_export.sites.perplexity import parsers

# The true case's side_by_side_metadata values (measured in raw_entries.json)
# 真例的 side_by_side_metadata 取值（raw_entries.json 实测）
HIT_META = {
    "experiment_role": "override-default-model-class:qwen3_instruct-01f7f",
    "sibling_uuid": "5cbeef00-c5f1-54ce-9d99-4a8eaf78cba7",
    "experiment_override": {"override-default-model-class": "qwen3_instruct"},
    "selection_status": "SELECTED",
    "execution_log": {},
}


def _entry(uuid="00000000-0000-4000-8000-0000000000a9", meta=None, **kw):
    e = {"uuid": uuid, "query_str": "测试查询", "text": "[]",
         "created_us": 1779210819268018, "updated_us": 1779210872926590,
         "updated_datetime": "2026-05-19T17:14:42.309576Z"}
    if meta is not None:
        e["side_by_side_metadata"] = meta
    e.update(kw)
    return e


# ── Criterion units
# ── 判据单元 ─────────────────────────────────────────────────

def test_collect_answer_variants_hit():
    """Criterion hit → registered: SELECTED (not UNSPECIFIED) or a
    non-[control] role.

    命中判据 → 登记：SELECTED（非 UNSPECIFIED）或 非 [control] 角色。"""
    out = parsers.collect_answer_variants([_entry(meta=HIT_META)])
    assert len(out) == 1
    rec = out[0]
    assert rec["entry_uuid"] == "00000000-0000-4000-8000-0000000000a9"
    assert rec["sibling_uuid"] == "5cbeef00-c5f1-54ce-9d99-4a8eaf78cba7"
    assert rec["selection_status"] == "SELECTED"
    assert rec["experiment_role"] == "override-default-model-class:qwen3_instruct-01f7f"
    assert rec["experiment_override"] == {"override-default-model-class": "qwen3_instruct"}
    assert rec["entry_updated"] == "2026-05-19T17:14:42.309576Z", \
        "应记录 entry 更新时间（重写推动 lastUpdated 的时间佐证）"
    # Idempotent: repeated calls return identical results
    # 幂等：重复调用结果一致
    assert parsers.collect_answer_variants([_entry(meta=HIT_META)]) == out


def test_collect_answer_variants_non_control_role_alone_hits():
    """selection_status UNSPECIFIED with a non-[control] role also hits (the
    OR branch of the criterion).

    selection_status 为 UNSPECIFIED 但角色非 [control] 也命中（判据的「或」分支）。"""
    meta = {"sibling_uuid": "s1", "selection_status": "SELECTION_STATUS_UNSPECIFIED",
            "experiment_role": "override-default-model-class:gpt5_1"}
    out = parsers.collect_answer_variants([_entry(meta=meta)])
    assert len(out) == 1 and out[0]["sibling_uuid"] == "s1"


def test_collect_answer_variants_control_excluded():
    """Control group ([control]… + UNSPECIFIED, the 6-case measured form in
    the full repo) is not registered.

    对照组（[control]… + UNSPECIFIED，全库 6 例实测形态）不登记。"""
    for role in ("[control]default-model-class:gpt41",
                 "[control]enable-serve-inhouse-model-over-gpt41mini:false"):
        meta = {"sibling_uuid": "s-control", "experiment_role": role,
                "selection_status": "SELECTION_STATUS_UNSPECIFIED"}
        assert parsers.collect_answer_variants([_entry(meta=meta)]) == [], role
    # [control] role but selection_status not UNSPECIFIED → still hits (SELECTED wins)
    # [control] 角色但 selection_status 非 UNSPECIFIED → 仍命中（SELECTED 优先）
    meta = {"sibling_uuid": "s2", "experiment_role": "[control]x:y",
            "selection_status": "SELECTED"}
    assert len(parsers.collect_answer_variants([_entry(meta=meta)])) == 1


def test_collect_answer_variants_negative():
    """No sibling_uuid / no field / non-dict input → no registration (healthy
    threads, zero diff).

    无 sibling_uuid / 无字段 / 非 dict 输入 → 无登记（健康线程零 diff）。"""
    assert parsers.collect_answer_variants(None) == []
    assert parsers.collect_answer_variants([]) == []
    assert parsers.collect_answer_variants([_entry()]) == [], "无 side_by_side_metadata"
    assert parsers.collect_answer_variants([_entry(meta={"selection_status": "SELECTED"})]) == [], \
        "无 sibling_uuid 不登记（判据前置条件）"
    assert parsers.collect_answer_variants([_entry(meta="not-a-dict"), "junk", None]) == []


# ── re-render --thread-json in-place add/remove
# ── re-render --thread-json 就地增删 ─────────────────────────

def _mk_thread(tmp_path: Path, entries, tj_extra=None) -> Path:
    d = tmp_path / "thread_x"
    d.mkdir()
    (d / "raw_entries.json").write_text(json.dumps(
        {"thread_metadata": {"title": "t"}, "entries": entries}, ensure_ascii=False))
    tj = {"web_uuid": "aaaaaaaabbbb", "psc_uuid": None, "title": "t", "mode": "search",
          "author": "u", "lastUpdated": "2026-05-19T17:14:42.309576Z"}
    tj.update(tj_extra or {})
    (d / "thread.json").write_text(json.dumps(tj, ensure_ascii=False, indent=1))
    return d


def test_rerender_thread_json_registers_and_idempotent(tmp_path):
    """Hit thread: re-render --thread-json adds answer_variants in place;
    reruns leave the content unchanged (idempotent).

    命中线程：re-render --thread-json 就地补 answer_variants；重跑内容不变（幂等）。"""
    d = _mk_thread(tmp_path, [_entry(meta=HIT_META)])
    assert rerender(d, update_thread_json=True)
    tj = json.loads((d / "thread.json").read_text())
    assert len(tj["answer_variants"]) == 1
    assert tj["answer_variants"][0]["sibling_uuid"] == \
        "5cbeef00-c5f1-54ce-9d99-4a8eaf78cba7"
    before = (d / "thread.json").read_text()
    assert rerender(d, update_thread_json=True)
    assert (d / "thread.json").read_text() == before, "幂等重跑 thread.json 不得有 diff"


def test_rerender_thread_json_healthy_no_key(tmp_path):
    """Healthy threads (control group / no field): the answer_variants key
    never appears; a stale key is removed.

    健康线程（对照组/无字段）：不出现 answer_variants 键；陈旧键被清除。"""
    control_meta = {"sibling_uuid": "s-c", "selection_status": "SELECTION_STATUS_UNSPECIFIED",
                    "experiment_role": "[control]default-model-class:gpt41"}
    d = _mk_thread(tmp_path, [_entry(meta=control_meta), _entry(uuid="e2")],
                   tj_extra={"answer_variants": [{"stale": True}]})
    assert rerender(d, update_thread_json=True)
    tj = json.loads((d / "thread.json").read_text())
    assert "answer_variants" not in tj, "无命中不出现该键（含清除陈旧键）"
    before = (d / "thread.json").read_text()
    assert rerender(d, update_thread_json=True)
    assert (d / "thread.json").read_text() == before
