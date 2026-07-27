"""cmd: assets-backfill — remediation for unsigned-URL assets (blocks re-fetch + inline extraction + online refresh).

cmd：assets-backfill —— 无签名 URL 资产补救（补抓 blocks + 内联提取 + 在线刷新）。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..core.fsio import atomic_write_text
from ..core.logging import get_logger
from ..core.models import Asset
from ..sites.perplexity import parsers as px
from ..sites.perplexity.assets import AssetDownloader
from ..sites.perplexity.normalize import safe_stem

log = get_logger("cli")

# Modes that carry schematized blocks (search has no blocks and is out of re-fetch scope)
# 需有 schematized blocks 的模式（search 无 blocks，不在补抓范围）
_BLOCKS_MODES = ("deep-research", "computer", "council", "study")


def manifest_version_count(manifest: dict) -> int:
    """Single source of truth for the manifest contract (V4-02): count is always the
    total number of versions Σ len(versions), same semantics as the
    count=len(conv.assets) written by FilesystemWriter.write_thread.
    For the number of file groups use len(manifest["files"]) — the two must not be conflated.

    manifest 契约唯一真源（V4-02）：count 恒为版本总数 Σ len(versions)，

    与 FilesystemWriter.write_thread 写出的 count=len(conv.assets) 同语义。
    文件组数请用 len(manifest["files"])，二者不可混用。
    """
    return sum(len(f.get("versions") or []) for f in manifest.get("files") or [])


def _write_manifest(manifest_path: Path, manifest: dict) -> None:
    """Unified write-back: recompute count (total number of versions) per the contract, then persist.

    统一写回：先按契约重算 count（版本总数），再落盘。
    """
    manifest["count"] = manifest_version_count(manifest)
    atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=1))


def _index_manifest(manifest: dict) -> tuple[dict, dict]:
    """Index of known records: uuid → (file group, version) and file_handle → (file group, version).

    Dedup order is uuid → file_handle (V4-03 residual gap): handle-only records have
    an empty uuid, so indexing by uuid alone makes repeated backfill runs re-append
    the same registration on every run.

    已知记录索引：uuid → (file组, version) 与 file_handle → (file组, version)。

    查重按 uuid → file_handle 顺序（V4-03 残余缺口）：handle-only 记录 uuid 为空，
    仅按 uuid 索引时 backfill 重复运行会逐次重复追加同一登记。
    """
    by_uuid: dict = {}
    by_handle: dict = {}
    for f in manifest.get("files", []):
        for v in f.get("versions", []):
            if v.get("uuid"):
                by_uuid[v["uuid"]] = (f, v)
            if v.get("file_handle"):
                by_handle[v["file_handle"]] = (f, v)
    return by_uuid, by_handle


def _find_known(by_uuid: dict, by_handle: dict, uuid: str, file_handle: str):
    """Dedup lookup in uuid → file_handle order; returns (file group, version) or None.

    按 uuid → file_handle 顺序查重，返回 (file组, version) 或 None。
    """
    if uuid and uuid in by_uuid:
        return by_uuid[uuid]
    if file_handle and file_handle in by_handle:
        return by_handle[file_handle]
    return None


def _merge_manifest(thread_dir: Path, assets: list) -> None:
    """Merge download results into assets/assets_manifest.json (same schema as the writer; dedup-update by uuid).

    把下载结果并入 assets/assets_manifest.json（writer 同款 schema；按 uuid 去重更新）。
    """
    manifest_path = thread_dir / "assets" / "assets_manifest.json"
    manifest = (json.loads(manifest_path.read_text())
                if manifest_path.exists() else {"count": 0, "files": []})
    known, _ = _index_manifest(manifest)
    changed = False
    for a in assets:
        if a.uuid in known:
            f, v = known[a.uuid]
            if a.downloaded_to and not v.get("downloaded_to"):
                v["downloaded_to"] = a.downloaded_to
                changed = True
            continue
        rec = {"uuid": a.uuid, "asset_type": a.asset_type, "version": a.version,
               "created_at": a.created_at, "downloaded_to": a.downloaded_to or None}
        manifest["files"].append({"filename": a.filename or a.uuid,
                                  "n_versions": a.n_versions, "versions": [rec]})
        known[a.uuid] = (manifest["files"][-1], rec)
        changed = True
    if changed:
        _write_manifest(manifest_path, manifest)


def _fetch_missing_blocks(adapter, out_root: Path, limit, adapter_for_dir=None) -> None:
    """Re-fetch missing raw_blocks.json (deep-research/computer/council/study) and their
    signed-URL assets.

    Absorbed from tools/backfill_deep_research_blocks.py: transport now uses the
    standard cookie path (was WebBridge), and asset registration is unified to the
    assets_manifest.json schema (the old assets_download.json 4-field mini-schema is
    retired — nothing in the repo reads it).
    Multi-account: threads are grouped by the first segment of the thread directory
    (the account folder), lazily creating per-account adapters via adapter_for_dir
    (make_transport automatically enumerates browser tokens to switch), finishing all
    threads in one pass; when adapter_for_dir is None, fall back to the single adapter
    (cross-account 403s are recorded as failures — idempotent and resumable).

    补抓缺失的 raw_blocks.json（deep-research/computer/council/study）及其带签名 URL 资产。

    原 tools/backfill_deep_research_blocks.py 收编：transport 改用标准 cookie 通路
    （原 WebBridge），资产登记统一为 assets_manifest.json schema（原 assets_download.json
    4 字段小 schema 废弃——全库无读取方）。
    多账户：按线程目录首段（账户文件夹）分组，经 adapter_for_dir 惰性创建各账户
    适配器（make_transport 自动枚举浏览器令牌切换），一轮跑完全部线程；
    adapter_for_dir 为 None 时退回单适配器（403 跨账户按失败记录，幂等可续）。
    """
    targets = []
    for tj in sorted(out_root.glob("*/*/*/thread.json")):
        td = tj.parent
        if (td / "raw_blocks.json").exists():
            continue
        try:
            mode = json.loads(tj.read_text()).get("mode") or ""
        except Exception:
            continue
        if mode in _BLOCKS_MODES:
            targets.append(td)
    if limit:
        targets = targets[:limit]
    log.info(f"[fetch-blocks] 待补抓 {len(targets)} 个线程（缺 raw_blocks.json）")
    # Group by account directory: one adapter per group, processing all accounts' threads in one pass
    # 按账户目录分组：一组一个适配器，一轮处理所有账户的线程
    groups: dict[str, list] = {}
    for td in targets:
        try:
            folder = td.relative_to(out_root).parts[0]
        except ValueError:
            folder = ""
        groups.setdefault(folder, []).append(td)
    adapters: dict[str, object] = {}

    def _adapter_for(folder: str):
        if folder not in adapters:
            adapters[folder] = adapter_for_dir(folder) if adapter_for_dir else adapter
        return adapters[folder]

    ok = fail = 0
    i = 0
    for folder, tds in groups.items():
        ad = _adapter_for(folder)
        if adapter_for_dir and tds:
            log.info(f"[fetch-blocks] 账户目录「{folder}」: {len(tds)} 个线程")
        dl = AssetDownloader(ad.transport, delay=0.5)
        for td in tds:
            i += 1
            try:
                tj = json.loads((td / "thread.json").read_text())
                uuid = tj.get("web_uuid") or td.name.rsplit("_", 1)[-1]
                blocks = ad.fetcher.get_thread_blocks(uuid)
                atomic_write_text(td / "raw_blocks.json", json.dumps(
                    {"thread_metadata": blocks["metadata"], "entries": blocks["entries"],
                     "background_entries": blocks["background_entries"]}, ensure_ascii=False))
                assets = px.collect_downloadable_assets(blocks["entries"])
                n_new = 0
                if assets:
                    files_dir = td / "assets" / "files"
                    existing = {p.name for p in files_dir.glob("*")} if files_dir.exists() else set()
                    for a in assets:
                        dest = files_dir / dl.dest_name(a)
                        if dest.name in existing:
                            continue
                        try:
                            data = ad.transport.download(a.url, timeout=120)
                            if dest.suffix == ".bin":
                                # dest_name cannot sniff content before download; fix the
                                # extension by magic bytes after download
                                # (observed: a study-thread CHART is actually a PNG named .bin)
                                # dest_name 在下载前无法嗅探内容；下载后按魔数纠扩展名
                                # （实测 study 线程 CHART 实为 PNG 被命名 .bin）
                                real = dl.resolve_ext(a, data)
                                if real and real != "bin":
                                    dest = dest.with_suffix(f".{real}")
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            dest.write_bytes(data)
                            a.downloaded_to = str(dest)
                            n_new += 1
                        except Exception as e:
                            log.warning(f"[fetch-blocks] 资产下载失败 {a.filename}: {e}")
                        time.sleep(0.5)
                    _merge_manifest(td, assets)
                ok += 1
                log.info(f"[fetch-blocks {i}/{len(targets)}] {td.name[:45]} "
                         f"blocks {len(blocks['entries'])} 轮，新资产 {n_new}")
            except Exception as e:
                fail += 1
                log.warning(f"[fetch-blocks] {td.name[:45]}: {str(e)[:100]}")
            if i < len(targets):
                time.sleep(3.0)
    log.info(f"[fetch-blocks] 完成。ok={ok} fail={fail} / 共 {len(targets)}")


def cmd_assets_backfill(adapter, out_root: Path, online: bool, limit, adapter_for=None,
                        fetch_blocks: bool = False):
    """Remediation for unsigned-URL assets (assets-backfill).

    Offline (default, zero requests): extract inline assets (ASSET_DIFF/CODE_ASSET)
    from raw_blocks and write them to disk; cloud-workspace handle kinds
    (DOC_FILE/CODE_FILE/UNKNOWN, no download channel yet) are registered in the manifest.
    --fetch-blocks: first re-fetch missing raw_blocks.json (limited to _BLOCKS_MODES)
    and their assets (online).
    --online: for manifest assets whose downloaded_to is missing/stale and that have a
    real uuid, fetch a fresh signed URL via /rest/assets/<uuid>/data and re-download
    (API rate-limited at 3s, CDN downloads concurrent).
    404 ASSET_NOT_FOUND is recorded as the asset_expired terminal state; cross-account
    403s are retried with the owning account via adapter_for.

    无签名 URL 资产补救（assets-backfill）。

    离线（默认，零请求）：从 raw_blocks 提取内联资产（ASSET_DIFF/CODE_ASSET）落盘；
    云工作区句柄类（DOC_FILE/CODE_FILE/UNKNOWN，暂无下载通道）登记 manifest。
    --fetch-blocks：先补抓缺失的 raw_blocks.json（限 _BLOCKS_MODES）及其资产（在线）。
    --online：对 manifest 中 downloaded_to 缺失/失效且有真 uuid 的资产，
    经 /rest/assets/<uuid>/data 取新鲜签名 URL 重下（API 限频 3s、CDN 下载并发）。
    404 ASSET_NOT_FOUND 记 asset_expired 终态；403 跨账户经 adapter_for 换账户重试。
    """
    if fetch_blocks:
        if adapter is None:
            raise SystemExit("[ERROR] --fetch-blocks 需要数据通路")
        _fetch_missing_blocks(adapter, out_root, limit, adapter_for_dir=adapter_for)
    thread_dirs = sorted({p.parent for p in out_root.glob("*/*/*/raw_blocks.json")})
    if limit:
        thread_dirs = thread_dirs[:limit]
    downloader = AssetDownloader(adapter.transport if adapter else None) if online else None
    # (Asset, version record, files_dir, manifest, manifest_path)
    # (Asset, version记录, files_dir, manifest, manifest_path)
    jobs: list = []
    inline_n = handle_n = refresh_ok = refresh_fail = 0
    for td in thread_dirs:
        try:
            doc = json.loads((td / "raw_blocks.json").read_text())
        except Exception:
            continue
        entries = doc.get("entries") or []
        inline = px.collect_inline_assets(entries)
        handles = px.collect_handle_assets(entries)
        files_dir = td / "assets" / "files"
        manifest_path = td / "assets" / "assets_manifest.json"
        manifest = (json.loads(manifest_path.read_text())
                    if manifest_path.exists() else {"count": 0, "files": []})
        by_uuid, by_handle = _index_manifest(manifest)
        # N-01 legacy fix: record the old destinations pointed to by extracted_inline
        # versions before fixing; after processing, clean up shared old files no longer
        # referenced by any version (multiple versions of the same file once shared one dest)
        # N-01 存量修复：记录修复前 extracted_inline 版本指向的旧落点，
        # 处理完后清理不再被任何版本引用的共享旧文件（同文件多版本曾共用同一 dest）
        old_inline_dests = {v["downloaded_to"]
                            for f in manifest.get("files", [])
                            for v in f.get("versions", [])
                            if v.get("extracted_inline") and v.get("downloaded_to")}
        changed = False
        # Group same-name inline assets: repeated edits of the same file produce multiple
        # inline versions with independent uuids
        # 同名内联资产分组：同一文件多次编辑产生多条独立 uuid 的内联版本
        same_name: dict[str, list] = {}
        for a in inline:
            key = f"{safe_stem(a['filename'])}.{a['inline_kind']}"
            same_name.setdefault(key, []).append(a["uuid"] or "x")
        # De-conflict uuids within a group via short prefixes: mirrors download_all's
        # _{uuid[:8]} duplicate-name guard, but synthetic uuids may share the first 8
        # chars (observed: two edit_toolu_01… groups both starting with "edit_too") —
        # on collision lengthen digit by digit until unique within the group;
        # deterministic naming keeps runs idempotent
        # 组内 uuid 短前缀去冲突：对齐 download_all 的 _{uuid[:8]} 重名防护，
        # 但合成 uuid 可能共享前 8 位（实测 edit_toolu_01… 两组uuid前8位同为
        # "edit_too"）——冲突时逐位加长直至组内唯一，确定性命名保证幂等
        suffix_of: dict[str, str] = {}
        for uuids in same_name.values():
            if len(uuids) > 1:
                for u in uuids:
                    n = 8
                    while n < len(u) and sum(1 for o in uuids if o[:n] == u[:n]) > 1:
                        n += 1
                    suffix_of[u] = u[:n]
        for a in inline:
            # N-01 fix: same-name multi-version assets get a uuid short prefix appended
            # to distinguish on-disk names; single versions keep the original name, and
            # entries already correctly on disk are not renamed.
            # N-01 修复：同名多版本追加 uuid 短前缀区分落盘名；单版本沿用原名，
            # 已正确落盘的条目不改名。
            stem = f"{safe_stem(a['filename'])}.{a['inline_kind']}"
            suffix = suffix_of.get(a["uuid"] or "x")
            if suffix is not None:
                dest = files_dir / f"{stem}_{suffix}.md"
            else:
                dest = files_dir / f"{stem}.md"
            # Ensure the write succeeds first (written only when missing or content
            # differs), then register downloaded_to — no more false reports of
            # "skipped the write yet claimed on disk"
            # 先确保写盘成功（不存在或内容不符才写），再登记 downloaded_to——
            # 不再出现「跳过写盘却声称已落盘」的误报
            try:
                if not dest.exists() or dest.read_text() != a["content"]:
                    atomic_write_text(dest, a["content"])
            except Exception as e:
                log.warning(f"[backfill] 内联资产写盘失败 {td.name[:30]}/{dest.name}: {e}")
                continue
            if a["uuid"] in by_uuid:
                f, v = by_uuid[a["uuid"]]
                if v.get("downloaded_to") == str(dest) and v.get("extracted_inline"):
                    # Already correctly on disk and registered; zero change
                    # 已正确落盘登记，零变化
                    continue
                # manifest already has a record but the destination is missing/wrong
                # (including a shared old dest): write back the correct destination
                # manifest 已有记录但落点缺失/错误（含共享旧 dest）：回写正确落点
                v["downloaded_to"] = str(dest)
                v["extracted_inline"] = True
                if not v.get("filename") or v["filename"] == a["uuid"]:
                    v["filename"] = a["filename"]
                    f["filename"] = a["filename"]
                inline_n += 1
                changed = True
            else:
                manifest["files"].append({
                    "filename": a["filename"], "n_versions": 1,
                    "versions": [{"uuid": a["uuid"], "asset_type": a["asset_type"],
                                  "filename": a["filename"], "version": "inline",
                                  "extracted_inline": True, "downloaded_to": str(dest)}]})
                if a["uuid"]:
                    by_uuid[a["uuid"]] = (manifest["files"][-1],
                                          manifest["files"][-1]["versions"][0])
                inline_n += 1
                changed = True
        for h in handles:
            hit = _find_known(by_uuid, by_handle, h["uuid"], h["file_handle"])
            if hit is not None:
                f, v = hit
                if v.get("no_download_channel"):
                    continue
                v["no_download_channel"] = True
                if h["file_handle"] and not v.get("file_handle"):
                    v["file_handle"] = h["file_handle"]
                    by_handle[h["file_handle"]] = (f, v)
                if not v.get("filename") or v["filename"] == h["uuid"]:
                    v["filename"] = h["filename"]
                    f["filename"] = h["filename"]
                handle_n += 1
                changed = True
            else:
                manifest["files"].append({
                    "filename": h["filename"], "n_versions": 1,
                    "versions": [{"uuid": h["uuid"], "asset_type": h["asset_type"],
                                  "filename": h["filename"], "version": "v1",
                                  "no_download_channel": True, "file_handle": h["file_handle"]}]})
                new_rec = manifest["files"][-1]["versions"][0]
                if h["uuid"]:
                    by_uuid[h["uuid"]] = (manifest["files"][-1], new_rec)
                if h["file_handle"]:
                    by_handle[h["file_handle"]] = (manifest["files"][-1], new_rec)
                handle_n += 1
                changed = True
        if changed and old_inline_dests:
            # N-01 legacy cleanup: after same-name multi-version assets switch to
            # uuid-suffixed destinations, the old shared dest is no longer referenced
            # by any version — only delete definitively stale old shared files inside
            # this thread's files_dir
            # N-01 存量清理：同名多版本改用 uuid 短缀落盘后，旧的共享 dest 不再被
            # 任何版本引用——仅删除本线程 files_dir 内确定失效的旧共享文件
            referenced = {v.get("downloaded_to")
                          for f in manifest.get("files", [])
                          for v in f.get("versions", [])}
            for d in old_inline_dests - referenced:
                p = Path(d)
                try:
                    if p.exists() and p.parent == files_dir:
                        p.unlink()
                        log.info(f"[backfill] 清理失效共享落盘 {td.name[:30]}/{p.name}")
                except Exception as e:
                    log.warning(f"[backfill] 清理失效共享落盘失败 {p.name}: {e}")
        if online and adapter is not None:
            # Phase 1 (inside this loop): fetch metadata serially (API rate-limited at 3s),
            # collecting download jobs
            # The thread dir's first segment relative to out_root is the account directory
            # name (correct even for absolute/nested --out)
            # 阶段 1（本循环内）：串行取元数据（API 限频 3s），收集待下载任务
            # 线程目录相对 out_root 的第一段即账户目录名（绝对/嵌套 --out 也取对）
            try:
                td_account = td.relative_to(out_root).parts[0]
            except ValueError:
                td_account = ""
            for f in manifest.get("files", []):
                for v in f.get("versions", []):
                    uuid = v.get("uuid") or ""
                    if (not uuid or uuid.startswith("toolu_") or v.get("extracted_inline")
                            or v.get("no_download_channel") or v.get("asset_expired")):
                        continue
                    if v.get("downloaded_to") and Path(v["downloaded_to"]).exists():
                        continue
                    try:
                        data = adapter.get_asset_data(uuid)
                        urls = data.get("download_urls") or []
                        if not urls:
                            refresh_fail += 1
                            continue
                        rec = Asset(uuid=uuid, asset_type=v.get("asset_type") or "",
                                    filename=v.get("filename") or urls[0].get("filename") or uuid,
                                    url=urls[0]["url"], version=v.get("version") or "v1",
                                    n_versions=f.get("n_versions") or 1)
                        jobs.append((rec, v, files_dir, manifest, manifest_path))
                        log.info(f"[backfill-meta] {td.name[:32]} {uuid[:8]} 取得新签名 URL")
                    except Exception as e:
                        msg = str(e)
                        if "404" in msg or "ASSET_NOT_FOUND" in msg:
                            # Purged by the platform: terminal state, no more retries
                            # 平台已清除：终态，不再重试
                            v["asset_expired"] = True
                            changed = True
                        elif ("403" in msg or "ASSET_ACCESS_DENIED" in msg) and adapter_for:
                            # Cross-account asset: retry once with the account that owns the archive
                            # 跨账户资产：换归档所属账户重试一次
                            try:
                                data = adapter_for(td_account).get_asset_data(uuid)
                                urls = data.get("download_urls") or []
                                if urls:
                                    rec = Asset(uuid=uuid, asset_type=v.get("asset_type") or "",
                                                filename=v.get("filename") or urls[0].get("filename") or uuid,
                                                url=urls[0]["url"], version=v.get("version") or "v1",
                                                n_versions=f.get("n_versions") or 1)
                                    jobs.append((rec, v, files_dir, manifest, manifest_path))
                                else:
                                    refresh_fail += 1
                            except Exception as e2:
                                refresh_fail += 1
                                log.warning(f"[backfill] {td.name[:35]} {uuid[:8]} 换账户仍失败: {str(e2)[:60]}")
                        else:
                            refresh_fail += 1
                            log.warning(f"[backfill] {td.name[:35]} {uuid[:8]}: {msg[:80]}")
                    time.sleep(3.0)
        if changed:
            _write_manifest(manifest_path, manifest)

    # Phase 2: parallelize CloudFront downloads (CDN, not API — relaxation approved by the user; delay=0, 6 threads)
    # 阶段 2：CloudFront 下载并发化（CDN 非 API，用户批准放宽；delay=0、6 线程）
    if online and jobs:
        from concurrent.futures import ThreadPoolExecutor
        dl = AssetDownloader(adapter.transport, delay=0)

        def _one(job):
            rec, v, files_dir, m, mp = job
            try:
                dl.download_all([rec], files_dir)
                return v, rec.downloaded_to or None, m, mp
            except Exception:
                return v, None, m, mp

        touched: dict = {}
        with ThreadPoolExecutor(max_workers=6) as ex:
            for n, (v, dest, m, mp) in enumerate(ex.map(_one, jobs), 1):
                if dest:
                    v["downloaded_to"] = dest
                    touched[str(mp)] = (m, mp)
                    refresh_ok += 1
                    log.info(f"[backfill-dl {n}/{len(jobs)}] {Path(dest).name[:60]}")
                else:
                    refresh_fail += 1
        for m, mp in touched.values():
            m["count"] = manifest_version_count(m)
            atomic_write_text(mp, json.dumps(m, ensure_ascii=False, indent=1))
    log.info(f"[backfill] 内联提取 {inline_n}，句柄登记 {handle_n}"
          + (f"，在线刷新 ok={refresh_ok} fail={refresh_fail}" if online else "")
          + f"（遍历 {len(thread_dirs)} 线程）")



