"""V4-03 fix: collect_handle_assets filters double-empty candidates, keeping
backfill idempotent (fourth review round).

Background: asset candidates with both uuid and file_handle empty previously
also produced handle records; assets-backfill's known index only collects
truthy uuids, so records appended with an empty uuid could not be recognized
on the next run and were re-appended every time. After the fix, double-empty
candidates are filtered outright (having either one suffices for
registration, preserving the h3 case semantics "valid uuid without handle
can be registered").

Cases: double-empty filtered / uuid-only / handle-only still registered; then
the real cmd_assets_backfill collection flow runs twice over synthetic
raw_blocks, asserting zero manifest change (idempotent, no duplicate appends).

No network: all synthetic data, offline mode (adapter=None, online=False).

V4-03 修复：collect_handle_assets 过滤双空候选，保证 backfill 幂等（第四轮审查）。

背景：uuid 与 file_handle 双空的资产候选此前也产出句柄记录；assets-backfill 的
known 索引只收真值 uuid，追加分支写出的空 uuid 记录下次运行无法识别，会逐次
重复追加。修复后双空候选直接过滤（有其一即可登记，保持 h3 用例
「有效 uuid 无 handle 可登记」语义）。

用例：双空过滤 / 单有 uuid / 单有 handle 仍登记；再以合成 raw_blocks 连续两次
跑真实 cmd_assets_backfill 收集流程，断言 manifest 零变化（幂等，不重复追加）。

不触网：全部合成数据，offline 模式（adapter=None、online=False）。
"""

import json

from pplx_export.commands.assets_backfill_cmd import cmd_assets_backfill
from pplx_export.sites.perplexity.parsers import collect_handle_assets


# ── 1. Double-empty candidate filtering / single-identity registration
# ── 1. 双空候选过滤 / 单身份登记 ────────────────────────────────────────────

class TestHandleEmptyIdentityFiltered:
    def test_empty_uuid_and_handle_filtered(self):
        entries = [{"blocks": [{"unified_assets_block": {"assets": [
            # uuid and file_handle both empty (no preview_info) → no record produced
            # uuid 与 file_handle 双空（无 preview_info）→ 不产出记录
            {"asset_type": "DOC_FILE", "title": "no-identity.docx"},
            # uuid explicitly empty string + empty handle → filtered as well
            # uuid 显式空串 + 句柄空 → 同样过滤
            {"uuid": "", "asset_type": "CODE_FILE", "preview_info": [{}]},
            # uuid missing + preview_info without file_handle → filtered
            # uuid 缺失 + preview_info 无 file_handle → 过滤
            {"asset_type": "UNKNOWN", "preview_info": [{"foo": "bar"}]},
        ]}}]}]
        assert collect_handle_assets(entries) == []

    def test_uuid_only_still_registered(self):
        entries = [{"blocks": [{"unified_assets_block": {"assets": [
            # Valid uuid, no handle → registered (same semantics as the V3-05 h3 case)
            # 有效 uuid、无 handle → 登记（与 V3-05 h3 用例同语义）
            {"uuid": "u1", "asset_type": "DOC_FILE"},
        ]}}]}]
        out = collect_handle_assets(entries)
        assert out == [{"uuid": "u1", "asset_type": "DOC_FILE",
                        "filename": "", "file_handle": ""}]

    def test_handle_only_still_registered(self):
        entries = [{"blocks": [{"unified_assets_block": {"assets": [
            # No uuid, has file_handle → registered (filename falls back to rsplit naming)
            # 无 uuid、有 file_handle → 登记（filename 走 rsplit 回退命名）
            {"asset_type": "DOC_FILE",
             "preview_info": [{"file_handle": "ws/abc/notes.md"}]},
        ]}}]}]
        out = collect_handle_assets(entries)
        assert out == [{"uuid": "", "asset_type": "DOC_FILE",
                        "filename": "notes.md", "file_handle": "ws/abc/notes.md"}]


# ── 2. Two consecutive backfill collection runs stay idempotent
# ── 2. 连续两次 backfill 收集流程幂等 ───────────────────────────────────────

def _mk_thread(out_root, assets):
    td = out_root / "acct" / "computer" / "2026-01-01_t_abcd1234"
    td.mkdir(parents=True)
    (td / "raw_blocks.json").write_text(json.dumps(
        {"entries": [{"blocks": [{"unified_assets_block": {"assets": assets}}]}]},
        ensure_ascii=False))
    return td


def _run_backfill(out_root):
    cmd_assets_backfill(None, out_root, online=False, limit=None)


class TestBackfillIdempotent:
    def test_double_run_no_duplicate_records(self, tmp_path):
        td = _mk_thread(tmp_path, [
            {"uuid": "u1", "asset_type": "DOC_FILE",
             "preview_info": [{"file_handle": "ws/h/a.docx"}]},
            # Double-empty → pre-fix it was re-appended on every run (the known
            # index never sees an empty uuid); post-fix it produces nothing
            # 双空 → 修复前每次运行都重复追加（known 收不到空 uuid），修复后零产出
            {"asset_type": "DOC_FILE", "title": "ghost.docx"},
        ])
        _run_backfill(tmp_path)
        mp = td / "assets" / "assets_manifest.json"
        first = mp.read_text()
        files1 = json.loads(first)["files"]
        # First run: the double-empty candidate yields nothing; only 1 record registered
        # 首跑：双空候选不产出，仅 1 条登记
        assert len(files1) == 1
        assert files1[0]["versions"][0]["uuid"] == "u1"

        _run_backfill(tmp_path)
        # Second run: manifest byte-identical (no duplicate appends, no drift)
        # 二跑：manifest 逐字节不变（不重复追加、无 drift）
        assert mp.read_text() == first

        _run_backfill(tmp_path)
        assert mp.read_text() == first
