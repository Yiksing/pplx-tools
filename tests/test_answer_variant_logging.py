"""Tests for ANSWER_VARIANT_DETECTED detection logging and the centralized registry.

Contract (user requirement 2026-07-23: "emit a dedicated log for these
answer_variants issues, so the next occurrence can be quickly located and a
choice made ... keeping backup answers from being deleted by the platform"):
- Log: single-line WARNING with the uniform grep-able marker
  ANSWER_VARIANT_DETECTED, carrying all locating fields (full thread uuid +
  uuid8, title, entry_uuid, sibling_uuid, selection_status, experiment_role)
  plus handling guidance;
- Registry: <out>/index/answer_variants_log.jsonl, dedup-idempotent by
  (web_uuid, entry_uuid);
- The online path alerts on every actual fetch hit; offline re-render alerts
  only when registered content is added/changed.

ANSWER_VARIANT_DETECTED 检测日志与集中登记测试。

契约（用户 2026-07-23 需求：「为此类涉及 answer_variants 的问题抛出特定日志，
便于下次再遇到时能快速定位和选择……避免备选回答被平台删除」）：
- 日志：WARNING 级单行，统一可 grep 标记 ANSWER_VARIANT_DETECTED，含全部定位字段
  （thread 全量 uuid + uuid8、标题、entry_uuid、sibling_uuid、selection_status、
  experiment_role）与处置指引；
- 登记：<out>/index/answer_variants_log.jsonl 按 (web_uuid, entry_uuid) 去重幂等；
- 在线路径每次实际抓取命中都告警；离线 re-render 仅登记内容新增/变化时告警。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pplx_export.commands.rerender_cmd import rerender
from pplx_export.sites.perplexity import variant_log

WEB_UUID = "5cbeef00-7332-5e9c-89f3-81b29b68a472"
REC = {"entry_uuid": "00000000-0000-4000-8000-0000000000a9",
       "sibling_uuid": "5cbeef00-c5f1-54ce-9d99-4a8eaf78cba7",
       "selection_status": "SELECTED",
       "experiment_role": "override-default-model-class:qwen3_instruct-01f7f"}


class _Capture(logging.Handler):
    """Capture handler attached directly to the pplx_export.variants logger
    (root has propagate=False, so caplog does not apply).

    直接挂到 pplx_export.variants logger 的捕获器（root propagate=False，caplog 不适用）。"""

    def __init__(self):
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def _capture_variants() -> _Capture:
    h = _Capture()
    logging.getLogger("pplx_export.variants").addHandler(h)
    return h


def _release(h: _Capture):
    logging.getLogger("pplx_export.variants").removeHandler(h)


# ── Log marker and fields
# ── 日志标记与字段 ────────────────────────────────────────────

def test_warn_detections_marker_and_fields():
    h = _capture_variants()
    try:
        variant_log.warn_detections(WEB_UUID, "调研一下示例主题是否对学生提供资助", [REC])
    finally:
        _release(h)
    assert len(h.messages) == 1, "每条命中恰好一行 WARNING"
    line = h.messages[0]
    assert variant_log.MARKER in line, "必须含统一可 grep 标记"
    assert f"thread={WEB_UUID}" in line and "uuid8=5cbeef00" in line
    assert "调研一下示例主题是否对学生提供资助" in line
    assert f"entry={REC['entry_uuid']}" in line
    assert f"sibling={REC['sibling_uuid']}" in line
    assert "selection_status=SELECTED" in line
    assert "experiment_role=override-default-model-class:qwen3_instruct-01f7f" in line
    assert "人工补录" in line, "应含人工补录处置指引"
    assert "docs/reference/api/api-responses-errors.md §5.2" in line, "应含文档小节指引"
    assert "\n" not in line, "告警必须为单行（可 grep）"


def test_warn_detections_empty_is_silent():
    h = _capture_variants()
    try:
        variant_log.warn_detections(WEB_UUID, "t", [])
        variant_log.warn_detections(WEB_UUID, "t", None)
    finally:
        _release(h)
    assert h.messages == []


# ── jsonl centralized registry: dedup idempotence
# ── jsonl 集中登记：去重幂等 ───────────────────────────────────

def test_append_registry_dedup_and_first_seen(tmp_path):
    n1 = variant_log.append_registry(tmp_path, WEB_UUID, "标题", [REC], source="online")
    assert n1 == 1
    p = tmp_path / "index" / "answer_variants_log.jsonl"
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    j = json.loads(lines[0])
    assert j["web_uuid"] == WEB_UUID and j["uuid8"] == "5cbeef00"
    assert j["entry_uuid"] == REC["entry_uuid"]
    assert j["sibling_uuid"] == REC["sibling_uuid"]
    assert j["selection_status"] == "SELECTED"
    assert j["source"] == "online" and j["detected_at"]
    first_seen = j["detected_at"]
    # Re-registering: same thread+entry is not appended; detected_at keeps the first-seen value
    # 重复登记：同 thread+entry 不追加，detected_at 保留首见
    n2 = variant_log.append_registry(tmp_path, WEB_UUID, "标题", [REC], source="offline")
    assert n2 == 0
    lines2 = p.read_text(encoding="utf-8").splitlines()
    assert len(lines2) == 1 and json.loads(lines2[0])["detected_at"] == first_seen
    # A new entry in the same thread (another variant) appends normally
    # 同线程新 entry（另一条变体）正常追加
    rec2 = dict(REC, entry_uuid="aaaaaaaa-0000-0000-0000-000000000000")
    n3 = variant_log.append_registry(tmp_path, WEB_UUID, "标题", [REC, rec2], source="online")
    assert n3 == 1 and len(p.read_text(encoding="utf-8").splitlines()) == 2
    # Empty hits do not write the file
    # 空命中不写文件
    assert variant_log.append_registry(tmp_path / "other", WEB_UUID, "t", [], "online") == 0
    assert not (tmp_path / "other" / "index" / "answer_variants_log.jsonl").exists()


# ── Offline re-render: alert only on additions/changes
# ── 离线 re-render：仅新增/变化时告警 ─────────────────────────

HIT_META = {
    "experiment_role": "override-default-model-class:qwen3_instruct-01f7f",
    "sibling_uuid": "5cbeef00-c5f1-54ce-9d99-4a8eaf78cba7",
    "selection_status": "SELECTED",
}


def _mk_hit_thread(tmp_path: Path) -> Path:
    d = tmp_path / "web_archive" / "bob" / "search" / f"2026-05-19_t_{WEB_UUID[:8]}"
    d.mkdir(parents=True)
    (d / "raw_entries.json").write_text(json.dumps({
        "thread_metadata": {"title": "t"},
        "entries": [{"uuid": REC["entry_uuid"], "query_str": "q", "text": "[]",
                     "created_us": 1779210819268018, "updated_us": 1779210872926590,
                     "side_by_side_metadata": HIT_META}]}, ensure_ascii=False))
    (d / "thread.json").write_text(json.dumps(
        {"web_uuid": WEB_UUID, "psc_uuid": None, "title": "t", "mode": "search",
         "author": "u", "lastUpdated": "2026-05-19T17:14:42.309576Z"},
        ensure_ascii=False, indent=1))
    return d


def test_rerender_alerts_only_on_change(tmp_path):
    d = _mk_hit_thread(tmp_path)
    out_root = tmp_path / "web_archive"
    jsonl = out_root / "index" / "answer_variants_log.jsonl"
    h = _capture_variants()
    try:
        # First run: new registration → alert + jsonl registry entry (source=offline)
        # 首次：登记新增 → 告警 + jsonl 登记（source=offline）
        assert rerender(d, update_thread_json=True, out_root=out_root)
        assert len(h.messages) == 1 and variant_log.MARKER in h.messages[0]
        j = json.loads(jsonl.read_text(encoding="utf-8").splitlines()[0])
        assert j["source"] == "offline" and j["web_uuid"] == WEB_UUID
        # Idempotent rerun: no content change → no new alert, no jsonl append
        # 幂等重跑：内容无变化 → 不再告警、jsonl 不追加
        assert rerender(d, update_thread_json=True, out_root=out_root)
        assert len(h.messages) == 1, "幂等重跑不得重复告警"
        assert len(jsonl.read_text(encoding="utf-8").splitlines()) == 1, "jsonl 不得追加"
        # Raw signal gone (platform-side rollback/field revamp) → key cleared, still no alert
        # raw 信号消失（平台侧回滚/字段改版）→ 键被清除，同样不告警
        doc = json.loads((d / "raw_entries.json").read_text())
        del doc["entries"][0]["side_by_side_metadata"]
        (d / "raw_entries.json").write_text(json.dumps(doc, ensure_ascii=False))
        assert rerender(d, update_thread_json=True, out_root=out_root)
        assert len(h.messages) == 1
        tj = json.loads((d / "thread.json").read_text())
        assert "answer_variants" not in tj
    finally:
        _release(h)


def test_rerender_preexisting_key_is_silent(tmp_path):
    """thread.json already holds the same registration (e.g. a pre-existing
    exported thread) → offline re-render stays silent: zero alerts, zero appends.

    thread.json 已有相同登记（如已导出过的存量线程）→ 离线重渲零告警零追加。"""
    d = _mk_hit_thread(tmp_path)
    # Simulate pre-existing state: run once so thread.json gets the registration written
    # 模拟存量：先跑一次让 thread.json 写入登记
    assert rerender(d, update_thread_json=True, out_root=tmp_path / "web_archive")
    # Clear the registry
    # 清登记处
    (tmp_path / "web_archive" / "index" / "answer_variants_log.jsonl").unlink()
    h = _capture_variants()
    try:
        assert rerender(d, update_thread_json=True, out_root=tmp_path / "web_archive")
    finally:
        _release(h)
    assert h.messages == [], "登记内容未变化时离线重渲必须静默"
    assert not (tmp_path / "web_archive" / "index" / "answer_variants_log.jsonl").exists()
