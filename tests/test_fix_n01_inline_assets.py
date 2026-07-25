"""N-01 regression test: same-name multi-version on-disk conflicts for inline
assets (ASSET_DIFF/CODE_ASSET).

Old logic: the N inline versions of one (filename, inline_kind) shared a single
dest; only the 1st was written to disk, yet the manifest claimed all N landed at
that dest (content loss + false reporting).
After the fix: multi-versions get distinct on-disk names via uuid short suffix
(aligned with download_all's _{uuid[:8]} guard), downloaded_to is set only after
an actual write, existing manifests with a shared dest are repaired and the stale
file removed, single-version entries are not renamed, and everything is idempotent.
Fully offline: tmp_path + directly constructed raw_blocks.json, no network.

N-01 回归测试：内联资产（ASSET_DIFF/CODE_ASSET）同名多版本落盘冲突。

旧逻辑：同一 (filename, inline_kind) 的 N 条内联版本共用同一 dest，
仅第 1 条写盘，manifest 却声称 N 条均落在该 dest（内容丢失 + 误报）。
修复后：多版本按 uuid 短缀区分落盘名（对齐 download_all 的 _{uuid[:8]} 防护）、
downloaded_to 只在确实写盘后设置、存量共享 dest 的 manifest 被修正并清理旧文件、
单版本条目不改名、整体幂等。
全离线：tmp_path + 直接构造 raw_blocks.json，不打网络。
"""

from __future__ import annotations

import json
from pathlib import Path

from pplx_export.commands.assets_backfill_cmd import cmd_assets_backfill

TD = "t001_测试线程_t001"


def _code_asset(uuid: str, filename: str, content: str) -> dict:
    return {"asset_type": "CODE_ASSET", "uuid": uuid,
            "download_info": [{"text_content": content, "filename": filename}]}


def _make_thread(out_root: Path, assets: list[dict]) -> Path:
    d = out_root / "Acc" / "computer" / TD
    d.mkdir(parents=True)
    doc = {"thread_metadata": {}, "background_entries": [],
           "entries": [{"blocks": [{"unified_assets_block": {"assets": assets}}]}]}
    (d / "raw_blocks.json").write_text(json.dumps(doc, ensure_ascii=False))
    return d


def _run(out_root: Path) -> None:
    # Fully offline: adapter=None, online=False (the offline path never touches transport)
    # 纯离线：adapter=None、online=False（离线路径不触碰 transport）
    cmd_assets_backfill(None, out_root, online=False, limit=None)


def _manifest(td: Path) -> dict:
    return json.loads((td / "assets" / "assets_manifest.json").read_text())


def _snapshot(td: Path) -> dict:
    """Snapshot of every file under assets/ (manifest included), for idempotence comparison.

    assets/ 下全部文件（含 manifest）内容快照，用于幂等比对。"""
    root = td / "assets"
    return {str(p.relative_to(root)): p.read_text()
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_same_name_multi_version_no_overwrite(tmp_path):
    # Three versions of the same script.py: land as 3 uuid-short-suffix files, each content intact
    # 同一 script.py 的 3 个版本：落 3 个 uuid 短缀文件，内容各自完整
    assets = [_code_asset(f"u{i}abcdefgh", "script.py", f"# version {i}\nprint({i})")
              for i in (1, 2, 3)]
    td = _make_thread(tmp_path, assets)
    _run(tmp_path)

    files_dir = td / "assets" / "files"
    names = sorted(p.name for p in files_dir.iterdir())
    assert names == [f"script.py.code_u{i}abcdef.md" for i in (1, 2, 3)]
    for i in (1, 2, 3):
        assert (files_dir / f"script.py.code_u{i}abcdef.md").read_text() \
            == f"# version {i}\nprint({i})"

    # manifest: 3 records, 3 mutually distinct downloaded_to values, all pointing to real files
    # manifest：3 条记录、3 个互不相同的 downloaded_to，且指向真实文件
    m = _manifest(td)
    dests = [v["downloaded_to"] for f in m["files"] for v in f["versions"]]
    assert len(dests) == 3 and len(set(dests)) == 3
    for d in dests:
        assert Path(d).exists()


def test_shared_uuid_prefix_extended(tmp_path):
    # Synthetic uuids sharing the first 8 chars (observed: two edit_toolu_01… uuids
    # both start with "edit_too"): on short-prefix collision the suffix is extended
    # char by char, and the two versions land in two distinct files
    # 合成 uuid 共享前 8 位（实测 edit_toolu_01… 两组 uuid 前 8 位同为 "edit_too"）：
    # 短前缀冲突时逐位加长，两版本落两个不同文件
    assets = [_code_asset("edit_toolu_01H5F4Xy", "main.tex", "% v1"),
              _code_asset("edit_toolu_01LbFJj1", "main.tex", "% v2")]
    td = _make_thread(tmp_path, assets)
    _run(tmp_path)

    files_dir = td / "assets" / "files"
    names = sorted(p.name for p in files_dir.iterdir())
    assert names == ["main.tex.code_edit_toolu_01H.md",
                     "main.tex.code_edit_toolu_01L.md"]
    assert (files_dir / "main.tex.code_edit_toolu_01H.md").read_text() == "% v1"
    assert (files_dir / "main.tex.code_edit_toolu_01L.md").read_text() == "% v2"
    m = _manifest(td)
    dests = [v["downloaded_to"] for f in m["files"] for v in f["versions"]]
    assert len(set(dests)) == 2


def test_downloaded_to_matches_actual_write(tmp_path):
    # downloaded_to must point to a file that actually holds that version's content (no more sharing/false reporting)
    # downloaded_to 必须指向确实包含该版本内容的文件（不再共享/误报）
    assets = [_code_asset(f"v{i}abcdefgh", "a.py", f"content-{i}") for i in (1, 2)]
    td = _make_thread(tmp_path, assets)
    _run(tmp_path)

    m = _manifest(td)
    for f in m["files"]:
        for v in f["versions"]:
            p = Path(v["downloaded_to"])
            assert p.exists(), f"downloaded_to 指向不存在文件: {p}"
            # The inline content for that version's uuid did land in this file
            # 该版本 uuid 对应的内联内容确实落在此文件中
            uuid = v["uuid"]
            expect = next(a["download_info"][0]["text_content"]
                          for a in assets if a["uuid"] == uuid)
            assert p.read_text() == expect


def test_legacy_shared_dest_repaired(tmp_path):
    # Legacy repair: two extracted_inline versions in the manifest share one old dest
    # (the old on-disk file holds only version 1's content) — after rerun, both versions
    # land separately, the manifest is fixed, and the unreferenced old shared file is removed
    # 存量修复：manifest 中两个 extracted_inline 版本共享同一旧 dest
    # （磁盘旧文件只有第 1 版内容）——重跑后两版分别落盘、manifest 修正、
    # 不再被引用的旧共享文件被清理
    assets = [_code_asset(f"w{i}abcdefgh", "script.py", f"# v{i}") for i in (1, 2)]
    td = _make_thread(tmp_path, assets)
    files_dir = td / "assets" / "files"
    files_dir.mkdir(parents=True)
    legacy = files_dir / "script.py.code.md"
    # Old bug: only version 1 was written
    # 旧 bug：只落第 1 版
    legacy.write_text("# v1")
    old_manifest = {"count": 2, "files": [
        {"filename": "script.py", "n_versions": 1,
         "versions": [{"uuid": "w1abcdefgh", "asset_type": "CODE_ASSET",
                       "filename": "script.py", "version": "inline",
                       "extracted_inline": True, "downloaded_to": str(legacy)}]},
        {"filename": "script.py", "n_versions": 1,
         "versions": [{"uuid": "w2abcdefgh", "asset_type": "CODE_ASSET",
                       "filename": "script.py", "version": "inline",
                       "extracted_inline": True, "downloaded_to": str(legacy)}]}]}
    (td / "assets" / "assets_manifest.json").write_text(json.dumps(old_manifest))

    _run(tmp_path)

    assert not legacy.exists(), "失效共享旧文件未清理"
    assert (files_dir / "script.py.code_w1abcdef.md").read_text() == "# v1"
    assert (files_dir / "script.py.code_w2abcdef.md").read_text() == "# v2"
    m = _manifest(td)
    dests = {v["uuid"]: v["downloaded_to"] for f in m["files"] for v in f["versions"]}
    assert dests["w1abcdefgh"].endswith("script.py.code_w1abcdef.md")
    assert dests["w2abcdefgh"].endswith("script.py.code_w2abcdef.md")
    assert str(legacy) not in dests.values()


def test_single_version_not_renamed(tmp_path):
    # A single version keeps the original name; with a correct manifest + file already
    # in place, a rerun changes nothing (no gratuitous rename/rewrite)
    # 单版本沿用原名；且预置正确 manifest + 文件时重跑零变化（不无谓改名/改写）
    assets = [_code_asset("s1abcdefgh", "solo.py", "# solo")]
    td = _make_thread(tmp_path, assets)
    _run(tmp_path)
    assert (td / "assets" / "files" / "solo.py.code.md").exists()
    assert _manifest(td)["files"][0]["versions"][0]["downloaded_to"] \
        .endswith("solo.py.code.md")

    snap1 = _snapshot(td)
    # Second pass: content already correct, expect zero changes
    # 第二遍：内容已正确，应零变化
    _run(tmp_path)
    assert _snapshot(td) == snap1


def test_rerun_idempotent(tmp_path):
    # Multi-version scenario run twice back to back: second pass changes nothing (files and manifest byte-identical)
    # 多版本场景连跑两遍：第二遍零变化（文件与 manifest 字节级一致）
    assets = [_code_asset(f"i{i}abcdefgh", "script.py", f"# v{i}") for i in (1, 2, 3)]
    assets.append(_code_asset("j1abcdefgh", "other.py", "# other"))
    td = _make_thread(tmp_path, assets)
    _run(tmp_path)
    snap1 = _snapshot(td)
    _run(tmp_path)
    assert _snapshot(td) == snap1
