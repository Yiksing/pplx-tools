"""N-02 regression: the relative depth of the exported backlinks in
spaces/*.md (the "已导出" links) is correct and reachable.

Pre-fix the link was `Path('../../') / p.relative_to(out_root.parent)` — one
extra `../` made every backlink 404; the fix uses `os.path.relpath(p,
spaces_dir)` instead. Builds a temporary out_root (with index/library_*.json
and a fake exported thread directory), chdirs into the temporary repo root
(spaces_dir being CWD-relative is a documented decision), and verifies that
each generated relative link is reachable and exactly one `../` deep.
Fully offline: tmp_path + monkeypatch.chdir.

N-02 回归测试：spaces/*.md「已导出」反链相对层级正确、可达。

修复前链接为 `Path('../../') / p.relative_to(out_root.parent)`，多一层
`../` 导致全部反链 404；修复后改用 `os.path.relpath(p, spaces_dir)`。
构造临时 out_root（含 index/library_*.json 与假导出线程目录），chdir 到
临时仓库根（spaces_dir 为 CWD 相对是文档化决策），验证生成的相对链接
逐条可达、且层级恰为一层 `../`。全离线：tmp_path + monkeypatch.chdir。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from pplx_export.commands.spaces_cmd import cmd_spaces

UUID = "abcdef12-3456-7890-abcd-ef1234567890"
SLUG = "test-space-AbC123"


def _make_repo(root: Path, out_name: str = "web_archive") -> Path:
    """Build a temporary repo root: out_root/index/library_*.json + one
    exported thread directory.

    构造临时仓库根：out_root/index/library_*.json + 一个已导出线程目录。"""
    out_root = root / out_name
    idx = out_root / "index"
    idx.mkdir(parents=True)
    (idx / "library_acc.json").write_text(json.dumps({
        "account": "acc",
        "threads": [{
            "entryUUID": UUID,
            "title": "测试线程",
            "authorUsername": "acc",
            "mode_label": "SEARCH",
            "lastUpdated": "2026-07-22T00:00:00Z",
            "collection": {"uuid": "cuuid", "title": "测试空间", "slug": SLUG},
        }],
    }, ensure_ascii=False))
    # Exported thread directory: name ends with _<uuid8> (aligned with cmd_spaces'
    # glob pattern); since V5-04 candidate dirs must hold a thread.json whose
    # web_uuid matches exactly (same as a real archive)
    # 导出线程目录：命名以 _<uuid8> 结尾（对齐 cmd_spaces 的 glob 模式）；
    # V5-04 起候选目录须有 web_uuid 全等的 thread.json（与真实归档一致）
    td = out_root / "Acc" / "search" / f"2026-07-22_测试线程_{UUID[:8]}"
    td.mkdir(parents=True)
    (td / "thread.json").write_text(json.dumps(
        {"web_uuid": UUID, "lastUpdated": "2026-07-22T00:00:00Z"}, ensure_ascii=False))
    return out_root


def _exported_links(md_path: Path) -> list[str]:
    return re.findall(r"\[已导出\]\(([^)]+)\)", md_path.read_text(encoding="utf-8"))


def test_spaces_link_reachable(tmp_path, monkeypatch):
    """Default web_archive layout: the generated backlinks are reachable
    relative to spaces/ ("[已导出]" links).

    默认 web_archive 布局：生成的 [已导出] 链接相对 spaces/ 可达。"""
    out_root = _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    cmd_spaces(out_root)

    md = Path("spaces") / f"{SLUG}.md"
    assert md.exists()
    links = _exported_links(md)
    assert len(links) == 1
    # Exactly one level of ../ (pre-fix it was ../../ and every link 404'd)
    # 层级恰为一层 ../（修复前为 ../../ 全部 404）
    assert links[0].startswith("../") and not links[0].startswith("../../")
    target = Path(os.path.normpath(Path("spaces") / links[0]))
    assert target.is_dir(), f"反链不可达: {links[0]}"


def test_spaces_link_robust_to_out_root(tmp_path, monkeypatch):
    """With a non-default --out name, relpath still yields reachable links
    (the old hard-coded ../../ would be wrong here too).

    --out 非默认名时 relpath 仍生成可达链接（旧硬编码 ../../ 同样会错）。"""
    out_root = _make_repo(tmp_path, out_name="custom_out")
    monkeypatch.chdir(tmp_path)
    cmd_spaces(out_root)

    links = _exported_links(Path("spaces") / f"{SLUG}.md")
    assert len(links) == 1
    assert links[0].startswith("../custom_out/")
    target = Path(os.path.normpath(Path("spaces") / links[0]))
    assert target.is_dir(), f"反链不可达: {links[0]}"


def test_spaces_skips_index_rows_missing_entry_uuid(tmp_path, monkeypatch):
    """Malformed library rows are skipped instead of crashing the whole space rebuild.

    畸形 library 行会被跳过，而不是使整个空间索引重建崩溃。"""
    out_root = _make_repo(tmp_path)
    lib = out_root / "index" / "library_acc.json"
    doc = json.loads(lib.read_text())
    doc["threads"].append({
        "title": "缺 UUID 行",
        "authorUsername": "acc",
        "mode_label": "SEARCH",
        "lastUpdated": "2026-07-23T00:00:00Z",
        "collection": {"uuid": "cuuid", "title": "测试空间", "slug": SLUG},
    })
    lib.write_text(json.dumps(doc, ensure_ascii=False))
    monkeypatch.chdir(tmp_path)

    cmd_spaces(out_root)

    links = _exported_links(Path("spaces") / f"{SLUG}.md")
    assert len(links) == 1
    assert "缺 UUID 行" not in (Path("spaces") / f"{SLUG}.md").read_text()
