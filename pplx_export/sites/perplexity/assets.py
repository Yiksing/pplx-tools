"""Perplexity asset download: direct signed-URL access + versioned naming on disk.

Perplexity 资产下载：签名 URL 直连 + 版本化命名落盘。
"""

from __future__ import annotations

import time
from pathlib import Path

from ...core.http.transport import Transport
from ...core.logging import get_logger
from ...core.models import Asset
from .normalize import safe_stem

log = get_logger("assets")

ASSET_TYPE_EXT = {
    "SLIDES": ".pptx", "DOC_FILE": ".md", "RESEARCH_REPORT": ".md", "PDF_FILE": ".pdf",
    "DOCX_FILE": ".docx", "XLSX_FILE": ".xlsx", "CODE_FILE": "", "AUDIO_FILE": ".mp3",
}
_KNOWN_EXT = ("md", "markdown", "pptx", "pdf", "docx", "xlsx", "csv", "py", "tex",
              "png", "jpg", "jpeg", "gif", "svg", "txt", "json", "html", "mp3",
              "r", "sh", "mmd", "yaml", "yml", "js", "sql", "zip")


class AssetDownloader:
    def __init__(self, transport: Transport, delay: float = 0.5):
        self.transport = transport
        self.delay = delay

    def dest_name(self, a: Asset) -> str:
        fname = a.filename or a.uuid
        stem, dot, ext = fname.rpartition(".")
        if dot and ext.lower() in _KNOWN_EXT:
            safe_ext = ext
        else:
            safe_ext = (ASSET_TYPE_EXT.get(a.asset_type or "") or ".bin").lstrip(".")
            stem = fname
        stem = safe_stem(stem)
        return f"{stem}_{a.version}.{safe_ext}" if a.n_versions > 1 else f"{stem}.{safe_ext}"

    @staticmethod
    def sniff_ext(data: bytes) -> str | None:
        """Sniff the real type by magic bytes, to correct wrong extensions (e.g. CHART is actually PNG/SVG).

        按魔数嗅探真实类型，用于纠正错误的扩展名（如 CHART 实为 PNG/SVG）。
        """
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return "png"
        if data[:3] == b"\xff\xd8\xff":
            return "jpg"
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return "gif"
        if data[:4] == b"%PDF":
            return "pdf"
        if data[:4] == b"PK\x03\x04":
            # OOXML container (docx/xlsx/pptx are all PK zip); refined by resolve_ext.
            # OOXML 容器（docx/xlsx/pptx 同为 PK zip），由 resolve_ext 细分
            return "zip"
        head = data[:512].lstrip().lower()
        if head.startswith(b"<svg") or b"<svg" in head[:200]:
            return "svg"
        if head.startswith(b"<?xml"):
            return "xml"
        return None

    @staticmethod
    def _ooxml_ext(a: Asset) -> str:
        """Refine PK zip containers: infer docx/xlsx/pptx from filename/asset_type; fall back to zip when undecidable.

        PK zip 容器细分：文件名/asset_type 推断 docx/xlsx/pptx，无法判断兜底 zip。
        """
        fname = (a.filename or "").lower()
        for e in ("docx", "xlsx", "pptx"):
            if fname.endswith("." + e):
                return e
        return {"DOCX_FILE": "docx", "XLSX_FILE": "xlsx", "SLIDES": "pptx"}.get(a.asset_type or "", "zip")

    def download_all(self, assets: list[Asset], dest_dir: Path) -> int:
        dest_dir.mkdir(parents=True, exist_ok=True)
        n_ok = 0
        used: set[str] = set()
        for a in assets:
            if not a.url:
                continue
            try:
                data = self.transport.download(a.url, timeout=120)
                # Decide the correct extension at download time: URL path > content magic > text/code type > asset_type fallback.
                # 下载时即确定正确扩展名：URL 路径 > 内容魔数 > 文本/代码类型 > asset_type 兜底
                dest = dest_dir / self._final_name(a, data)
                if dest.name in used:
                    # Same-batch name collision after safe_stem: append a short uuid suffix to avoid overwriting each other.
                    # safe_stem 后同批重名：追加 uuid 短缀，避免互相覆盖
                    stem, dot, ext = dest.name.rpartition(".")
                    dest = dest_dir / f"{stem}_{(a.uuid or 'x')[:8]}{dot}{ext}"
                dest.write_bytes(data)
                used.add(dest.name)
                a.downloaded_to = str(dest)
                n_ok += 1
            except Exception as e:
                log.warning(f"[assets] 下载失败 {a.filename}: {e}")
            time.sleep(self.delay)
        return n_ok

    def _final_name(self, a: Asset, data: bytes) -> str:
        """Determine the final filename (with the correct extension) at download time, avoiding later renames.

        下载时确定最终文件名（含正确扩展名），避免事后改名。
        """
        stem = self.dest_name(a).rsplit(".", 1)[0]
        ext = self.resolve_ext(a, data)
        if stem.lower().endswith("." + ext.lower()):
            # stem already carries the final extension (dest_name keeps the full
            # original name for unknown extensions); appending again would produce
            # double extensions like compile.sh.sh, timeline_chart.mmd_v1.mmd.
            # stem 已带最终扩展名（dest_name 对未知扩展名保留完整原名），不再拼接，
            # 否则出现 compile.sh.sh、timeline_chart.mmd_v1.mmd 双扩展名
            return stem
        return f"{stem}.{ext}"

    def resolve_ext(self, a: Asset, data: bytes) -> str:
        """Three-source extension decision: URL path > content magic > text/code type > asset_type fallback.

        三源判定扩展名：URL 路径 > 内容魔数 > 文本/代码类型 > asset_type 兜底。
        """
        # 1) Real extension in the URL path (e.g. .../model_structure.png?Policy=...).
        # 1) URL 路径中的真实扩展名（如 .../model_structure.png?Policy=...）
        import urllib.parse
        path = urllib.parse.urlparse(a.url or "").path.lower()
        for e in ("png", "jpg", "jpeg", "gif", "svg", "pdf", "pptx", "docx", "md", "csv", "txt", "py", "json", "html"):
            if path.endswith("." + e):
                return e
        # 2) Content magic bytes.
        # 2) 内容魔数
        m = self.sniff_ext(data)
        if m == "zip":
            m = self._ooxml_ext(a)
        if m:
            return m
        # 3) Text/code types (indistinguishable by magic): check the filename suffix or content traits.
        # 3) 文本/代码类型（魔数无法区分）：看文件名词尾或内容特征
        if self._is_text(data):
            fname = (a.filename or a.uuid or "")
            for e in ("R", "py", "sh", "mmd", "csv", "json", "html", "js", "sql", "yaml", "txt", "md"):
                if fname.lower().endswith("." + e.lower()):
                    return e
            head = data[:400].lstrip().lower()
            if head.startswith((b"<!doctype", b"<html")):
                return "html"
            if head.startswith((b"{", b"[")):
                return "json"
            if b"flowchart" in head or b"graph td" in head or b"graph lr" in head or b"sequenceDiagram" in data[:200]:
                return "mmd"
            if head.startswith(b"#!/bin/bash") or head.startswith(b"#!/bin/sh") or head.startswith(b"#!/usr/bin/env"):
                return "sh"
            return "txt"
        # 4) asset_type fallback.
        # 4) asset_type 兜底
        return (ASSET_TYPE_EXT.get(a.asset_type or "") or ".bin").lstrip(".")

    @staticmethod
    def _is_text(data: bytes) -> bool:
        try:
            data[:2000].decode("utf-8")
            return True
        except Exception:
            return False
