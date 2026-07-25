"""V3-05 fix: close export-path test blind spots (third review round).

Three real feature paths that previously had zero assertions/references, all
with offline synthetic data:
1. Export-only products of FilesystemWriter.write_thread — the interruptions
   write branch of thread.json (fs_writer.py:70-73), sources.json/sources.md
   (:88-97), assets/assets_manifest.json written by write_thread itself
   (:128-139), and the report.md header (:117-126). Snapshot tests all go
   through the rerender path, so these products had no regression guard.
2. parsers.parse_space_meta: owner+contributor merge, permission label
   mapping, and the three-state failure detection via status==failed /
   _response_type ending with NOT_ALLOWED.
3. parsers.collect_handle_assets: registration with/without file_handle and
   rsplit fallback naming; exclusion when a download URL or a non-handle type
   is present.

No network: construct Conversation / raw dicts directly, call the real
functions, and assert.

V3-05 修复：补导出路径测试盲区（第三轮审查）。

三处此前零断言/零引用的真实功能路径，全部离线合成数据：
1. FilesystemWriter.write_thread 的导出专属产物——thread.json 的 interruptions
   写入分支（fs_writer.py:70-73）、sources.json/sources.md（:88-97）、
   write_thread 自身写的 assets/assets_manifest.json（:128-139）、report.md 头
   （:117-126）。快照测试全走 rerender 路径，这些产物此前无回归守护。
2. parsers.parse_space_meta：owner+contributor 合并、权限标签映射、
   status==failed / _response_type 以 NOT_ALLOWED 结尾的失败识别三态。
3. parsers.collect_handle_assets：有/无 file_handle 的登记与 rsplit 回退命名、
   有下载 URL 或非句柄类型的排除。

不触网：直接构造 Conversation / 原始 dict，调用真实函数断言。
"""

import json

from pplx_export.core.models import (
    Asset, Citation, Conversation, Report, Space, Turn)
from pplx_export.sites.perplexity.fs_writer import FilesystemWriter
from pplx_export.sites.perplexity.parsers import (
    collect_handle_assets, parse_space_meta)


# ── 1. write_thread export-only products
# ── 1. write_thread 导出专属产物 ────────────────────────────────────────────

def _cit(name, url, snippet=""):
    return Citation(name=name, url=url, snippet=snippet, timestamp="2026-07-20")


def _conv_with_interruption() -> Conversation:
    """Minimal interrupted thread: deep-research, 2 turns, turn 2 interrupted by
    a spending limit, with citations/report/assets.

    最小中断线程：deep-research，2 轮，第 2 轮限额中断，含引文/报告/资产。"""
    return Conversation(
        web_uuid="abcdef12-0000-0000-0000-000000000000",
        title="中断线程", mode="deep-research", author="tester",
        last_updated="2026-07-22T00:00:00Z",
        space=Space(uuid="s-uuid", title="团队空间", slug="team-space"),
        turns=[
            Turn(index=1, query="第一问", created_us=1700000000000001),
            Turn(index=2, query="第二问触发了限额中断", created_us=1700000000000002,
                 metadata={"wf_status": "WORKFLOW_AWAITING_NEXT_STEPS",
                           "locked_reason": "spending_limit_exceeded"}),
        ],
        citations=[_cit("来源甲", "https://a.example/1", "摘要甲"),
                   _cit("来源乙", "https://b.example/2")],
        report=Report(title="中断研究报告", file_name="report.pdf",
                      url="https://signed.example/r", content_md="报告正文第一段。"),
        # Two same-named versions (input out of order; manifest should sort by
        # created_at ascending) + another file
        # 同名两版本（输入乱序，manifest 应按 created_at 升序）+ 另一文件
        assets=[
            Asset(uuid="a2", asset_type="DOC_FILE", filename="plan.xlsx",
                  version="v2", created_at="1700000002",
                  downloaded_to="assets/plan_v2.xlsx"),
            Asset(uuid="a1", asset_type="DOC_FILE", filename="plan.xlsx",
                  version="v1", created_at="1700000001",
                  downloaded_to="assets/plan_v1.xlsx"),
            Asset(uuid="b1", asset_type="SLIDES", filename="z-slides.pptx",
                  version="v1", created_at="1700000003"),
        ],
    )


class TestWriteThreadExportProducts:
    def test_thread_json_interruptions_branch(self, tmp_path):
        td = FilesystemWriter(tmp_path).write_thread(_conv_with_interruption())
        tj = json.loads((td / "thread.json").read_text())
        assert tj["web_uuid"] == "abcdef12-0000-0000-0000-000000000000"
        assert tj["n_turns"] == 2 and tj["n_sources"] == 2
        assert tj["space"] == {"uuid": "s-uuid", "title": "团队空间",
                               "slug": "team-space"}
        assert tj["report_info"] == {"title": "中断研究报告",
                                     "file_name": "report.pdf",
                                     "url": "https://signed.example/r"}
        # interruptions write branch: a non-completed turn-level workflow is
        # registered as one entry
        # interruptions 写入分支：非 completed 轮级工作流登记为一条
        inters = tj["interruptions"]
        assert len(inters) == 1
        assert inters[0]["location"] == "turn_0002"
        assert inters[0]["kind"] == "limit_interrupted"
        assert inters[0]["status"] == "WORKFLOW_AWAITING_NEXT_STEPS"

    def test_thread_json_no_interruptions_key_when_healthy(self, tmp_path):
        conv = Conversation(
            web_uuid="00000000-0000-0000-0000-000000000000",
            title="健康线程", mode="search", author="tester",
            last_updated="2026-07-22T00:00:00Z",
            turns=[Turn(index=1, query="q", created_us=1700000000000001)])
        td = FilesystemWriter(tmp_path).write_thread(conv)
        tj = json.loads((td / "thread.json").read_text())
        # A thread without interruptions has no interruptions key; with no
        # report/assets the corresponding files are not written
        # 无中断的线程不出现 interruptions 键；无报告/资产则不写对应文件
        assert "interruptions" not in tj
        assert tj["space"] is None and tj["report_info"] is None
        assert not (td / "report.md").exists()
        assert not (td / "assets" / "assets_manifest.json").exists()

    def test_sources_json_and_md(self, tmp_path):
        td = FilesystemWriter(tmp_path).write_thread(_conv_with_interruption())
        sj = json.loads((td / "sources.json").read_text())
        assert sj["count"] == 2
        assert [s["url"] for s in sj["sources"]] == [
            "https://a.example/1", "https://b.example/2"]
        assert sj["sources"][0] == {"name": "来源甲", "url": "https://a.example/1",
                                    "snippet": "摘要甲", "timestamp": "2026-07-20"}
        md = (td / "sources.md").read_text().splitlines()
        assert md[0] == "# 引文列表"
        assert "1. [来源甲](https://a.example/1)" in md
        assert "2. [来源乙](https://b.example/2)" in md

    def test_assets_manifest_counts_and_version_order(self, tmp_path):
        td = FilesystemWriter(tmp_path).write_thread(_conv_with_interruption())
        m = json.loads((td / "assets" / "assets_manifest.json").read_text())
        # Total asset count (versions counted independently)
        # 资产总数（版本独立计数）
        assert m["count"] == 3
        # Grouped by filename, filenames sorted: plan.xlsx (2 versions) before
        # z-slides.pptx
        # 按文件名分组、文件名排序：plan.xlsx（2 版本）在 z-slides.pptx 前
        assert [f["filename"] for f in m["files"]] == ["plan.xlsx", "z-slides.pptx"]
        plan = m["files"][0]
        assert plan["n_versions"] == 2
        # Input out of order (v2 first); manifest restores created_at ascending
        # 输入乱序（v2 在前），manifest 按 created_at 升序归位
        assert [v["uuid"] for v in plan["versions"]] == ["a1", "a2"]
        assert plan["versions"][0]["downloaded_to"] == "assets/plan_v1.xlsx"
        assert plan["versions"][1]["asset_type"] == "DOC_FILE"

    def test_report_md_header(self, tmp_path):
        td = FilesystemWriter(tmp_path).write_thread(_conv_with_interruption())
        md = (td / "report.md").read_text()
        assert md == "# 中断研究报告\n\n> 产物文件: report.pdf\n报告正文第一段。"


# ── 2. parse_space_meta ─────────────────────────────────────────────────────
# ── 2. parse_space_meta 空间元数据解析 ───────────────────────────────────────

class TestParseSpaceMeta:
    DOC = {
        "slug": "team-space", "title": "团队空间", "access": 1,
        "max_contributors": 10,
        "owner_user": {"username": "alice", "email": "a@x.com",
                       "name": "Alice", "permission": 4},
        "contributor_users": [
            {"username": "bob", "permission": 2},
            {"username": "carol", "permission": 3},
            {"username": "dave", "permission": 1},
        ],
    }

    def test_owner_plus_contributors_merged(self):
        m = parse_space_meta(self.DOC)
        assert m["error"] is None
        assert m["slug"] == "team-space" and m["title"] == "团队空间"
        assert m["access"] == 1 and m["max_contributors"] == 10
        # members = owner + contributors (owner first)
        # members = owner + contributors（owner 在前）
        assert [u["username"] for u in m["members"]] == [
            "alice", "bob", "carol", "dave"]

    def test_permission_label_mapping(self):
        m = parse_space_meta(self.DOC)
        labels = {u["username"]: u["permission_label"] for u in m["members"]}
        assert labels == {"alice": "所有者", "bob": "可编辑",
                          "carol": "可管理", "dave": "可查看"}

    def test_failed_by_status(self):
        m = parse_space_meta({"status": "failed",
                              "_response_type": "VIEW_COLLECTION_NOT_ALLOWED"})
        assert m["error"] == "VIEW_COLLECTION_NOT_ALLOWED"

    def test_failed_by_response_type_suffix(self):
        # No status field; failure detected solely from _response_type ending
        # with NOT_ALLOWED
        # 无 status 字段，仅凭 _response_type 以 NOT_ALLOWED 结尾判失败
        m = parse_space_meta({"_response_type": "VIEW_COLLECTION_NOT_ALLOWED"})
        assert m["error"] == "VIEW_COLLECTION_NOT_ALLOWED"

    def test_failed_without_response_type(self):
        assert parse_space_meta({"status": "failed"})["error"] == "FAILED"

    def test_normal_response_no_error(self):
        assert parse_space_meta({"slug": "s"})["error"] is None

    def test_missing_fields_degrade(self):
        m = parse_space_meta({})
        assert m["error"] is None
        assert m["slug"] == "" and m["members"] == []
        assert m["owner"] == {"username": "", "email": "", "name": "",
                              "permission": None, "permission_label": ""}
        # emoji can fall back to appearance.emoji
        # emoji 可从 appearance.emoji 兜底
        assert parse_space_meta({"appearance": {"emoji": "🤖"}})["emoji"] == "🤖"
        # Non-dict input does not raise
        # 非 dict 输入不抛错
        assert parse_space_meta(None)["members"] == []


# ── 3. collect_handle_assets ────────────────────────────────────────────────
# ── 3. collect_handle_assets 句柄资产收集 ────────────────────────────────────

class TestCollectHandleAssets:
    def test_registration_and_rsplit_fallback_naming(self):
        entries = [{"blocks": [{"unified_assets_block": {"assets": [
            # Has handle, no filename field → rsplit fallback names it from the
            # handle's last segment
            # 有句柄、无文件名字段 → rsplit 回退取句柄末段命名
            {"uuid": "h1", "asset_type": "DOC_FILE",
             "preview_info": [{"file_handle": "ws/abc/report final.docx"}]},
            # Has handle and title → filename takes precedence over the handle
            # 有句柄且有 title → 文件名优先于句柄
            {"uuid": "h2", "asset_type": "CODE_FILE", "title": "script.py",
             "preview_info": [{"file_handle": "ws/abc/xyz"}]},
            # No handle, no filename → empty-string fallback; missing asset_type
            # → UNKNOWN
            # 无句柄无文件名 → 空串兜底；asset_type 缺失 → UNKNOWN
            {"uuid": "h3"},
        ]}}]}]
        out = collect_handle_assets(entries)
        assert [r["uuid"] for r in out] == ["h1", "h2", "h3"]
        assert out[0] == {"uuid": "h1", "asset_type": "DOC_FILE",
                          "filename": "report final.docx",
                          "file_handle": "ws/abc/report final.docx"}
        assert out[1]["filename"] == "script.py"
        assert out[1]["file_handle"] == "ws/abc/xyz"
        assert out[2] == {"uuid": "h3", "asset_type": "UNKNOWN",
                          "filename": "", "file_handle": ""}

    def test_plan_block_path_also_scanned(self):
        entries = [{"blocks": [{"plan_block": {"steps": [{"assets": [
            {"uuid": "p1", "asset_type": "DOC_FILE",
             "preview_info": [{"file_handle": "ws/h/p.md"}]},
        ]}]}}]}]
        out = collect_handle_assets(entries)
        assert len(out) == 1
        assert out[0]["filename"] == "p.md"

    def test_excludes_downloadable_and_non_handle_types(self):
        entries = [{"blocks": [{"unified_assets_block": {"assets": [
            # Has a download URL (doc_file.url) → goes through the download
            # channel, not registered as a handle asset
            # 有下载 URL（doc_file.url）→ 走下载通道，不登记为句柄资产
            {"uuid": "d1", "asset_type": "DOC_FILE",
             "doc_file": {"url": "https://signed.example/y.pdf",
                          "filename": "y.pdf"}},
            # Non-handle type (RESEARCH_REPORT not in DOC_FILE/CODE_FILE/UNKNOWN/None)
            # → skipped
            # 非句柄类型（RESEARCH_REPORT 不在 DOC_FILE/CODE_FILE/UNKNOWN/None）→ 跳过
            {"uuid": "r1", "asset_type": "RESEARCH_REPORT",
             "preview_info": [{"file_handle": "ws/h/r.md"}]},
        ]}}]}]
        assert collect_handle_assets(entries) == []
