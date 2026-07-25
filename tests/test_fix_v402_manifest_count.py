"""V4-02 fix: unify the count contract of assets_manifest.json as total version count (fourth review round).

Background: FilesystemWriter.write_thread writes count=len(conv.assets) (total
version count, with same-name versions counted independently), while the three
write-back paths of assets-backfill (_merge_manifest / offline write-back /
online download write-back) all rewrote count as len(files) (file-group count),
leaving 13 manifests across the archive distorted. After the fix, the three
paths share manifest_version_count / _write_manifest, and count is always
Σ len(versions).

Also closes the residual V4-03 idempotency gap: registration records of
handle-only assets (empty uuid, only file_handle) were previously invisible
to the known index, so repeated backfill runs appended duplicates each time;
after the fix the known index dedupes in uuid → file_handle order.

No network: all synthetic data; the online path uses a fake adapter/transport.

V4-02 修复：assets_manifest.json 的 count 契约统一为版本总数（第四轮审查）。

背景：FilesystemWriter.write_thread 写 count=len(conv.assets)（版本总数，同名
多版本独立计数），而 assets-backfill 的三条写回路径（_merge_manifest / 离线写回 /
在线下载写回）都把 count 改写为 len(files)（文件组数），全库 13 个 manifest 失真。
修复后三条路径共用 manifest_version_count / _write_manifest，count 恒为 Σ len(versions)。

附带闭合 V4-03 残余幂等缺口：handle-only 资产（uuid 为空、仅有 file_handle）的
登记记录此前 known 索引收不到，backfill 重复运行逐次重复追加；修复后 known 索引
按 uuid → file_handle 顺序查重。

不触网：全部合成数据；在线路径用 fake adapter/transport。
"""

import json
from pathlib import Path

from pplx_export.commands import assets_backfill_cmd as abc
from pplx_export.core.models import Asset, Conversation, Turn
from pplx_export.sites.perplexity.fs_writer import FilesystemWriter


def _total_versions(m):
    return sum(len(f.get("versions") or []) for f in m.get("files") or [])


def _seed_manifest(td, files):
    """Write a seed manifest with writer semantics (count = total version count).

    写入 writer 语义的种子 manifest（count=版本总数）。"""
    mp = td / "assets" / "assets_manifest.json"
    mp.parent.mkdir(parents=True, exist_ok=True)
    m = {"count": sum(len(f["versions"]) for f in files), "files": files}
    mp.write_text(json.dumps(m, ensure_ascii=False, indent=1))
    return mp


_MULTI_VERSION_FILES = [
    {"filename": "plan.xlsx", "n_versions": 2,
     "versions": [{"uuid": "a1", "asset_type": "DOC_FILE", "version": "v1",
                   "created_at": "1700000001", "downloaded_to": "assets/plan_v1.xlsx"},
                  {"uuid": "a2", "asset_type": "DOC_FILE", "version": "v2",
                   "created_at": "1700000002", "downloaded_to": "assets/plan_v2.xlsx"}]},
    {"filename": "z-slides.pptx", "n_versions": 1,
     "versions": [{"uuid": "b1", "asset_type": "SLIDES", "version": "v1",
                   "created_at": "1700000003", "downloaded_to": None}]},
]


def _mk_thread(out_root, name="2026-01-01_t_abcd1234", assets=None):
    td = out_root / "acct" / "computer" / name
    td.mkdir(parents=True)
    (td / "raw_blocks.json").write_text(json.dumps(
        {"entries": ([{"blocks": [{"unified_assets_block": {"assets": assets}}]}]
                     if assets is not None else [])},
        ensure_ascii=False))
    return td


# ── 0. The contract function itself ───────────────────────────────────────
# ── 0. 契约函数本身 ─────────────────────────────────────────────────────────

class TestManifestVersionCount:
    def test_count_is_total_versions_not_file_groups(self):
        m = {"count": 0, "files": _MULTI_VERSION_FILES}
        assert abc.manifest_version_count(m) == 3
        # File-group count and total version count must be distinguishable
        # 文件组数与版本总数必须可区分
        assert len(m["files"]) == 2

    def test_empty_manifest(self):
        assert abc.manifest_version_count({"count": 0, "files": []}) == 0
        assert abc.manifest_version_count({}) == 0


# ── 1. All three write-back paths produce count = total version count ─────
# ── 1. 三条写回路径 count 均为版本总数 ──────────────────────────────────────

class TestMergeManifestCount:
    def test_merge_appends_and_counts_versions(self, tmp_path):
        """Path 1: _merge_manifest (merges --fetch-blocks download results).

        路径一：_merge_manifest（--fetch-blocks 下载结果并入）。"""
        td = _mk_thread(tmp_path)
        mp = _seed_manifest(td, json.loads(json.dumps(_MULTI_VERSION_FILES)))
        new = Asset(uuid="c1", asset_type="RESEARCH_REPORT", filename="rep.pdf",
                    version="v1", created_at="1700000004",
                    downloaded_to="assets/rep.pdf")
        abc._merge_manifest(td, [new])
        m = json.loads(mp.read_text())
        assert len(m["files"]) == 3
        # Before the fix this would have been written as 3
        # 修复前会被写成 3
        assert m["count"] == 4 == _total_versions(m)

    def test_merge_idempotent_recount(self, tmp_path):
        """_merge_manifest only fills downloaded_to for already-registered uuids; count semantics unchanged.

        _merge_manifest 对已登记 uuid 只补 downloaded_to，count 语义不变。"""
        td = _mk_thread(tmp_path)
        mp = _seed_manifest(td, json.loads(json.dumps(_MULTI_VERSION_FILES)))
        dup = Asset(uuid="b1", asset_type="SLIDES", filename="z-slides.pptx",
                    version="v1", created_at="1700000003",
                    downloaded_to="assets/z-slides.pptx")
        abc._merge_manifest(td, [dup])
        m = json.loads(mp.read_text())
        assert len(m["files"]) == 2
        assert m["count"] == 3 == _total_versions(m)


class TestOfflineBackfillCount:
    def test_offline_writeback_keeps_version_total(self, tmp_path):
        """Path 2: offline write-back (_write_manifest after handle registration).

        路径二：离线写回（句柄登记后 _write_manifest）。"""
        td = _mk_thread(tmp_path, assets=[
            {"uuid": "h1", "asset_type": "DOC_FILE",
             "preview_info": [{"file_handle": "ws/h/a.docx"}]},
        ])
        mp = _seed_manifest(td, json.loads(json.dumps(_MULTI_VERSION_FILES)))
        abc.cmd_assets_backfill(None, tmp_path, online=False, limit=None)
        m = json.loads(mp.read_text())
        # 1 new file group added
        # 新增 1 个文件组
        assert len(m["files"]) == 3
        # Before the fix this would have been written as 3
        # 修复前会被写成 3
        assert m["count"] == 4 == _total_versions(m)
        # The versions array is left untouched
        # 版本数组未被改动
        plan = next(f for f in m["files"] if f["filename"] == "plan.xlsx")
        assert [v["uuid"] for v in plan["versions"]] == ["a1", "a2"]


class _FakeTransport:
    def download(self, url, timeout=120):
        return b"%PDF-1.4 fake-bytes"


class _FakeAdapter:
    def __init__(self):
        self.transport = _FakeTransport()

    def get_asset_data(self, uuid):
        return {"download_urls": [{"url": "https://cdn.example/rep.pdf",
                                   "filename": "rep.pdf"}]}


class TestOnlineBackfillCount:
    def test_online_writeback_keeps_version_total(self, tmp_path, monkeypatch):
        """Path 3: online refresh write-back (recount of touched manifests after phase-2 downloads).

        路径三：在线刷新写回（阶段 2 下载后 touched manifest 重算 count）。"""
        monkeypatch.setattr(abc.time, "sleep", lambda *a, **k: None)
        files = json.loads(json.dumps(_MULTI_VERSION_FILES))
        # b1 has no file on disk → becomes an online-refresh target
        # entries is empty: zero changes in the offline phase
        # b1 无落盘 → 成为在线刷新对象
        # entries 为空：离线阶段零变化
        td = _mk_thread(tmp_path)
        mp = _seed_manifest(td, files)
        abc.cmd_assets_backfill(_FakeAdapter(), tmp_path, online=True, limit=None)
        m = json.loads(mp.read_text())
        # Before the fix this would have been written as 2
        # 修复前会被写成 2
        assert m["count"] == 3 == _total_versions(m)
        v = m["files"][1]["versions"][0]
        assert v["downloaded_to"]
        assert Path(v["downloaded_to"]).exists()


# ── 2. count semantics unchanged after the writer → backfill relay ────────
# ── 2. writer → backfill 接力后 count 语义不变 ─────────────────────────────

class TestWriterBackfillRelay:
    def test_writer_then_backfill_count_semantics(self, tmp_path):
        conv = Conversation(
            web_uuid="abcdef12-0000-0000-0000-000000000000",
            title="接力线程", mode="computer", author="tester",
            last_updated="2026-07-22T00:00:00Z",
            turns=[Turn(index=1, query="q", created_us=1700000000000001)],
            assets=[
                Asset(uuid="a2", asset_type="DOC_FILE", filename="plan.xlsx",
                      version="v2", created_at="1700000002",
                      downloaded_to="assets/plan_v2.xlsx"),
                Asset(uuid="a1", asset_type="DOC_FILE", filename="plan.xlsx",
                      version="v1", created_at="1700000001",
                      downloaded_to="assets/plan_v1.xlsx"),
                Asset(uuid="b1", asset_type="SLIDES", filename="z-slides.pptx",
                      version="v1", created_at="1700000003"),
            ])
        td = FilesystemWriter(tmp_path).write_thread(conv)
        mp = td / "assets" / "assets_manifest.json"
        m0 = json.loads(mp.read_text())
        # writer contract: total version count
        # writer 契约：版本总数
        assert m0["count"] == 3 == _total_versions(m0)
        assert len(m0["files"]) == 2

        # backfill relay: add one handle asset (raw_blocks fetched later by a follow-up run)
        # backfill 接力：补一个句柄资产（raw_blocks 由后续补抓而来）
        (td / "raw_blocks.json").write_text(json.dumps({"entries": [
            {"blocks": [{"unified_assets_block": {"assets": [
                {"uuid": "h1", "asset_type": "DOC_FILE",
                 "preview_info": [{"file_handle": "ws/h/a.docx"}]}]}}]}]},
            ensure_ascii=False))
        abc.cmd_assets_backfill(None, tmp_path, online=False, limit=None)
        m1 = json.loads(mp.read_text())
        assert len(m1["files"]) == 3
        # Semantics unchanged: still total version count
        # 语义不变：仍是版本总数
        assert m1["count"] == 4 == _total_versions(m1)


# ── 3. Two consecutive backfill runs do not duplicate handle-only assets (residual V4-03 gap)
# ── 3. handle-only 资产连续两次 backfill 不重复追加（V4-03 残余缺口）─────────

class TestHandleOnlyIdempotent:
    def test_handle_only_double_run_no_duplicate(self, tmp_path):
        td = _mk_thread(tmp_path, assets=[
            # Empty uuid, only file_handle — previously invisible to the known index,
            # so each run appended a duplicate
            # uuid 为空、仅有 file_handle —— 修复前 known 索引收不到，逐次重复追加
            {"asset_type": "DOC_FILE",
             "preview_info": [{"file_handle": "ws/abc/notes.md"}]},
        ])
        mp = td / "assets" / "assets_manifest.json"
        abc.cmd_assets_backfill(None, tmp_path, online=False, limit=None)
        first = mp.read_text()
        files1 = json.loads(first)["files"]
        assert len(files1) == 1
        v = files1[0]["versions"][0]
        assert v["uuid"] == "" and v["file_handle"] == "ws/abc/notes.md"
        assert v["no_download_channel"] is True

        abc.cmd_assets_backfill(None, tmp_path, online=False, limit=None)
        # Second run: zero changes
        # 二跑：零变化
        assert mp.read_text() == first

        abc.cmd_assets_backfill(None, tmp_path, online=False, limit=None)
        # Third run: still zero changes
        # 三跑：仍零变化
        assert mp.read_text() == first

    def test_handle_only_merges_into_uuid_record(self, tmp_path):
        """The same handle later reappears with a uuid: matches the old record by file_handle, no new file group.

        同一句柄后来带上 uuid 出现：按 file_handle 命中旧记录，不新增文件组。"""
        td = _mk_thread(tmp_path, assets=[
            {"asset_type": "DOC_FILE",
             "preview_info": [{"file_handle": "ws/abc/notes.md"}]},
        ])
        abc.cmd_assets_backfill(None, tmp_path, online=False, limit=None)
        # The same file appears again, this time with a uuid
        # 同一文件再次出现，这次带 uuid
        (td / "raw_blocks.json").write_text(json.dumps({"entries": [
            {"blocks": [{"unified_assets_block": {"assets": [
                {"uuid": "u9", "asset_type": "DOC_FILE",
                 "preview_info": [{"file_handle": "ws/abc/notes.md"}]}]}}]}]},
            ensure_ascii=False))
        abc.cmd_assets_backfill(None, tmp_path, online=False, limit=None)
        m = json.loads((td / "assets" / "assets_manifest.json").read_text())
        # No duplicate append
        # 不重复追加
        assert len(m["files"]) == 1
        assert m["count"] == 1 == _total_versions(m)
