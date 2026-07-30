"""Filesystem writer: persists conversations in the web_archive layout.

Directory: <account display name>/<mode>/<YYYY-MM-DD>_<title slug>_<uuid8>/
  thread.json / conversation.md / turns/ / report.md / sources.json / sources.md /
  raw_entries.json / raw_blocks.json / assets/(manifest + files)

filesystem writer：按 web_archive 布局落盘对话。

目录：<账户显示名>/<模式>/<YYYY-MM-DD>_<标题slug>_<uuid8>/
  thread.json / conversation.md / turns/ / report.md / sources.json / sources.md /
  raw_entries.json / raw_blocks.json / assets/(manifest + files)
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ...core.fsio import atomic_write_text
from ...core.logging import get_logger
from ...core.models import Conversation, author_folder
from ...writers.base import Writer
from . import parsers, render, variant_log
from .normalize import slugify

log = get_logger("cli")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _safe_folder(name: str) -> str:
    """Make the author directory name safe: strip path separators, reject . / ..
    segments (prevents path traversal via other users' usernames in shared spaces),
    and replace characters illegal on Windows filesystems (:*?"<>|) to avoid
    cross-platform OSError; all other characters (including spaces) are kept to
    preserve the existing archive layout (e.g. "Alice Example").

    作者目录名消毒：去路径分隔符、拒绝 . / .. 段（防共享空间他人用户名路径穿越），
    并替换 Windows 文件系统非法字符（:*?"<>|）防跨平台 OSError；
    其余字符（含空格）保留，维持既有归档布局（如「Alice Example」）。"""
    s = re.sub(r'[\\/:*?"<>|]+', "_", name or "").strip()
    return s if s and s not in (".", "..") else "unknown"


class FilesystemWriter(Writer):
    def __init__(self, out_root: Path):
        self.out_root = Path(out_root)

    def thread_dir_for(self, conv: Conversation) -> Path:
        date_prefix = (conv.last_updated or _now_iso())[:10]
        folder = _safe_folder(author_folder(conv.author or "unknown"))
        canonical = (self.out_root / folder / conv.mode /
                     f"{date_prefix}_{slugify(conv.title)}_{conv.web_uuid[:8]}")
        # V4-01: when a continued thread's lastUpdated date changes, a new directory
        # would be computed; first search the whole archive by uuid8 for existing
        # (old-date) directories with the same UUID and auto-migrate/merge them,
        # preventing multiple directories per UUID.
        # V4-01：续接线程 lastUpdated 日期变化会算出新目录，先按 uuid8 全库查找
        # 同 UUID 的既有（旧日期）目录并自动迁移合并，杜绝一 UUID 多目录。
        for old in self.find_thread_dirs(conv.web_uuid):
            if old != canonical:
                self._merge_into(old, canonical)
        return canonical

    def find_thread_dirs(self, web_uuid: str) -> list[Path]:
        """Search the whole archive for thread directories of the same UUID by uuid8
        directory suffix (cross-account/cross-mode, defensive).

        Identity check (V5-03): directories whose thread.json is missing, corrupt, or
        has a mismatched web_uuid (including missing/empty) are never accepted — the
        same strictness as uuid8-collision defense: better to skip a migration (the old
        directory remains; a manual consolidate can follow) than to mis-merge (a
        different thread's directory gets merged and deleted).

        按 uuid8 目录后缀全库查找同 UUID 的线程目录（含跨账户/跨模式，防御性）。

        身份核验（V5-03）：thread.json 缺失、损坏或 web_uuid 不符（含缺失/为空）
        的目录一律不认——与 uuid8 撞名防御同一严格度，宁可漏迁（旧目录残留，
        下次可人工 consolidate）不可误并（异线程目录被合并删除）。
        """
        suffix = f"_{web_uuid[:8]}"
        out = []
        for p in sorted(self.out_root.glob(f"*/*/*{suffix}")):
            if not (p.is_dir() and p.name.endswith(suffix)):
                continue
            tj = p / "thread.json"
            if not tj.exists():
                continue
            try:
                wu = json.loads(tj.read_text()).get("web_uuid") or ""
            except Exception:
                continue
            if wu != web_uuid:
                continue
            out.append(p)
        return out

    def _merge_into(self, old: Path, new: Path) -> None:
        """Safely merge the old directory's contents into the new one, then delete the
        old directory (date-directory migration for continued threads with the same UUID).

        Merge rules: union of files (files unique to the old directory are all kept —
        no asset loss); same name + same content → skip; same-name conflicts **always
        keep the target side (new/keeper)** (V5-02: previously decided by mtime, but
        "newer mtime ≠ newer content" — re-render refreshes md mtimes across all
        directories while content still comes from each one's old raw, and the
        consolidate path has no subsequent overwrite, so old content could permanently
        clobber the keeper; the target side is the semantically newer one on both call
        paths: thread_dir_for's canonical is the freshly fetched export destination,
        consolidate_uuid's keeper has the max lastUpdated).
        Copy first and verify sha256 file by file; only delete the old directory when
        all checks pass — any failure leaves the old directory intact; retries are
        idempotent.

        把旧目录内容安全合并进新目录后删除旧目录（同 UUID 续接线程的日期目录迁移）。

        合并规则：文件取并集（旧目录独有文件全部保留，资产不丢）；
        同名同内容跳过；同名冲突**恒保留目标方（new/keeper）**（V5-02：
        此前按 mtime 裁决，但「mtime 新 ≠ 内容新」——re-render 会刷新全部目录
        md 文件的 mtime 而内容仍来自各自旧 raw，consolidate 路径无后续覆写，
        旧内容可能永久覆盖 keeper；目标方在两条调用路径中都是语义更新的一方：
        thread_dir_for 的 canonical 是刚抓取的新导出落点，consolidate_uuid 的
        keeper 是 lastUpdated 最大者）。
        先复制并逐文件 sha256 校验，全部通过才删旧目录——任何一步失败旧目录
        原样保留，重试幂等。
        """
        copied: list[tuple[Path, Path]] = []
        # Relative paths of same-name conflict files (target side always kept; per-file visible).
        # 同名冲突文件的相对路径（恒保留目标方，逐文件可见）
        conflicts: list[str] = []
        n_skip = 0
        for src in sorted(old.rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(old)
            dst = new / rel
            if dst.exists():
                if _sha256(src) == _sha256(dst):
                    # Same content: no copy needed.
                    # 同内容：无需复制
                    n_skip += 1
                    continue
                # Same-name conflict: always keep the target side (new/keeper, semantically newer).
                # 同名冲突：恒保留目标方（new/keeper，语义更新）
                conflicts.append(str(rel))
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append((src, dst))
        if conflicts:
            # Conflicts are per-file visible: the target side winning is a heuristic
            # (semantically newer); the theoretical case of older content being kept
            # must be noticeable to the user. For very many conflicts, list only the
            # first 20 plus the total count.
            # 冲突逐文件可见：目标方胜出是启发式（语义更新），内容更旧被保留的理论
            # 场景须让用户可察觉；冲突极多时只列前 20 个并给出总数
            shown = conflicts[:20]
            more = "（仅列前 20 个）" if len(conflicts) > 20 else ""
            log.warning(f"[migrate] {old.name} → {new.name}：{len(conflicts)} 个同名文件冲突，"
                        f"已保留目标方（new/keeper）：{', '.join(shown)}{more}")
        # Copy verification: deleting the old directory is allowed only when everything matches.
        # 复制验证：全部一致才允许删除旧目录
        for src, dst in copied:
            if _sha256(src) != _sha256(dst):
                raise RuntimeError(
                    f"[migrate] 复制校验失败: {src} → {dst}（旧目录保留未删，可重试）")
        shutil.rmtree(old)
        log.info(f"[migrate] {old} → {new}：并入 {len(copied)} 个文件"
                 f"（同内容跳过 {n_skip}，冲突保留目标方 {len(conflicts)}），旧目录已删除")

    def consolidate_uuid(self, web_uuid: str) -> list[Path]:
        """Merge multiple date directories of the same UUID archive-wide: keep the one
        with the max lastUpdated, merge the others into it, then delete them.

        Returns the list of merged-and-deleted old directories; empty list when there
        are no duplicates (idempotent). Used for one-off cleanup of historical
        duplicate directories (the normal export path auto-migrates via thread_dir_for).

        全库合并同 UUID 的多日期目录：保留 lastUpdated 最大者，其余并入后删除。

        返回被合并删除的旧目录列表；无重复时返回空列表（幂等）。
        用于历史遗留重复目录的一次性清理（正常导出路径由 thread_dir_for 自动迁移）。
        """
        dirs = self.find_thread_dirs(web_uuid)
        if len(dirs) <= 1:
            return []

        def _lu(p: Path) -> str:
            try:
                return json.loads((p / "thread.json").read_text()).get("lastUpdated") or ""
            except Exception:
                return ""

        keeper = max(dirs, key=_lu)
        removed = []
        for p in dirs:
            if p != keeper:
                self._merge_into(p, keeper)
                removed.append(p)
        return removed

    def write_thread(self, conv: Conversation, adapter=None) -> Path:
        thread_dir = self.thread_dir_for(conv)
        conv.exported_at = _now_iso()
        (thread_dir / "turns").mkdir(parents=True, exist_ok=True)
        (thread_dir / "assets").mkdir(exist_ok=True)

        # Sub-agent mapping (computer workflow_block was already attached to turns by adapter.get_thread; writer only reads).
        # 子代理映射（computer workflow_block 已由 adapter.get_thread 挂到 turn，writer 只读）
        sub_map = {}
        if adapter is not None:
            for sub in adapter.sub_agents(conv):
                sub_map[sub.sub_id] = sub

        # thread.json
        # thread.json（线程元数据）
        thread_json = {
            "web_uuid": conv.web_uuid, "psc_uuid": conv.psc_uuid, "url": conv.url,
            "title": conv.title, "mode": conv.mode, "author": conv.author,
            "export_via": conv.export_via, "space": (
                {"uuid": conv.space.uuid, "title": conv.space.title, "slug": conv.space.slug}
                if conv.space else None),
            "lastUpdated": conv.last_updated, "threadAccess": conv.thread_access,
            "n_turns": conv.n_turns, "n_sources": len(conv.citations),
            "metadata": conv.metadata,
            "report_info": (
                {"title": conv.report.title, "file_name": conv.report.file_name, "url": conv.report.url}
                if conv.report else None),
            "exported_at": conv.exported_at,
        }
        # Interruption registry: non-completed workflows + unassigned appendix background payloads (threads without interruptions omit this key).
        # 中断登记：非 completed 工作流 + 附录未归入后台负载（无中断的线程不出现该键）
        inters = parsers.collect_interruptions(conv, sub_map)
        if inters:
            thread_json["interruptions"] = inters
        # Answer-rewrite variant registry: narrowed side_by_side_metadata criteria hit (threads without hits omit this key).
        # 答案重写变体登记：side_by_side_metadata 收窄判据命中（无命中的线程不出现该键）
        if conv.answer_variants:
            thread_json["answer_variants"] = conv.answer_variants
            # Central registry: index/answer_variants_log.jsonl (deduped by thread+entry, idempotent).
            # 集中登记处：index/answer_variants_log.jsonl（按 thread+entry 去重，幂等）
            variant_log.append_registry(self.out_root, conv.web_uuid, conv.title,
                                        conv.answer_variants, source="online")
        atomic_write_text(thread_dir / "thread.json",
                          json.dumps(thread_json, ensure_ascii=False, indent=1))

        # raw (full fidelity)
        # raw（完整保真）
        plain = conv._plain
        if plain is not None:
            atomic_write_text(thread_dir / "raw_entries.json", json.dumps(
                {"thread_metadata": plain.get("metadata"), "entries": plain.get("entries"),
                 "background_entries": plain.get("background_entries")}, ensure_ascii=False))
        blocks = conv._blocks
        if blocks is not None:
            atomic_write_text(thread_dir / "raw_blocks.json", json.dumps(
                {"thread_metadata": blocks.get("metadata"), "entries": blocks.get("entries"),
                 "background_entries": blocks.get("background_entries")}, ensure_ascii=False))

        # sources
        # sources（引文）
        src_list = conv.citations
        atomic_write_text(thread_dir / "sources.json", json.dumps(
            {"count": len(src_list), "sources": [
                {"name": c.name, "url": c.url, "snippet": c.snippet, "timestamp": c.timestamp}
                for c in src_list]}, ensure_ascii=False, indent=1))
        lines = ["# 引文列表", ""]
        for i, c in enumerate(src_list, 1):
            lines.append(f"{i}. [{c.name or c.url}]({c.url})")
        atomic_write_text(thread_dir / "sources.md", "\n".join(lines) + "\n")

        # conversation.md (compact version)
        # conversation.md（简版）
        atomic_write_text(thread_dir / "conversation.md",
                          render.render_conversation(conv, sub_map))

        # turns/ (full version)
        # turns/（完整版）
        turns_dir = thread_dir / "turns"
        # N-12 fix: delete stale turn_*.md files numbered above the current turn count
        # (leftovers when the turn count shrinks). Only high-numbered leftovers are
        # removed, not the whole directory — unchanged files keep their mtime, reducing
        # diff noise.
        # N-12 修复：删除编号高于当前轮数的旧 turn_*.md（轮数缩减时残留）。
        # 只删高编号残留、不清空整个目录——保留未变文件的 mtime，减少 diff 噪音。
        for p in turns_dir.glob("turn_*.md"):
            try:
                stale = int(p.stem[5:]) > len(conv.turns)
            except ValueError:
                # Leave non-numeric filenames untouched.
                # 非数字编号文件不动
                continue
            if stale:
                p.unlink()
        for t in conv.turns:
            atomic_write_text(turns_dir / f"turn_{t.index:04d}.md",
                              render.render_turn(t, conv.mode, sub_map))

        # report.md (deep-research)
        # report.md（deep-research）
        if conv.report:
            md = conv.report.content_md
            if not md and adapter is not None:
                md = adapter.get_report(conv)
            if md:
                head = [f"# {conv.report.title or '研究报告'}", ""]
                if conv.report.file_name:
                    head += [f"> 产物文件: {conv.report.file_name}", ""]
                atomic_write_text(thread_dir / "report.md", "\n".join(head) + md)

        # assets manifest + list of downloaded files
        # assets manifest + 已下载文件清单
        if conv.assets:
            by_name: dict[str, list] = {}
            for a in conv.assets:
                by_name.setdefault(a.filename or a.uuid, []).append(a)
            manifest = [{"filename": n, "n_versions": len(vs),
                         "versions": [{"uuid": a.uuid, "asset_type": a.asset_type, "version": a.version,
                                       "created_at": a.created_at, "downloaded_to": a.downloaded_to}
                                      for a in sorted(vs, key=lambda x: parsers.to_int(x.created_at))]}
                        for n, vs in sorted(by_name.items())]
            atomic_write_text(thread_dir / "assets" / "assets_manifest.json", json.dumps(
                {"count": len(conv.assets), "files": manifest}, ensure_ascii=False, indent=1))

        return thread_dir
