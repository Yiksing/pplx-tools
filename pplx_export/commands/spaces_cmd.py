"""cmd: space-index / spaces — space conversation lists and the space-view index.

cmd：space-index / spaces —— 空间会话列表与空间视图索引。
"""

from __future__ import annotations

import json
import os
import re as _re
import time
from pathlib import Path

from ..core.logging import get_logger

log = get_logger("cli")


def _best_thread_dir(out_root: Path, web_uuid: str) -> Path | None:
    """Pick the newest copy among candidate directories for the same UUID: read
    thread.json and take the one with the largest lastUpdated.

    V4-01: resumed threads may leave multiple date-stamped directories behind;
    previously the first glob hit on *_<uuid8> was taken, which could select an old
    copy. The migration mechanism (fs_writer.consolidate_uuid) is the primary
    defense; this is the backstop: even if duplicate directories still exist, the
    index points at the newest copy.
    V5-04: candidate directories get an exact web_uuid check (aligned with the uuid8
    collision defense in fs_writer.find_thread_dirs); directories with a missing /
    corrupt / mismatched thread.json are never candidates — better to link "not
    exported" than to link a different thread's directory.

    同 UUID 候选目录中选最新副本：读 thread.json 取 lastUpdated 最大者。

    V4-01：续接线程可能残留多日期目录，此前对 *_<uuid8> 第一个 glob 命中即
    break，可能选中旧副本。迁移机制（fs_writer.consolidate_uuid）是主防线，
    此处为兜底：即使重复目录仍存在，索引也指向最新副本。
    V5-04：候选目录补 web_uuid 全等校验（与 fs_writer.find_thread_dirs 的
    uuid8 撞名防御对齐）；thread.json 缺失/损坏/不符的目录一律不作候选——
    宁可链「未导出」不可错链异线程目录。
    """
    uuid8 = web_uuid[:8]
    best: Path | None = None
    best_lu = ""
    for p in sorted(out_root.glob(f"*/*/*_{uuid8}")):
        if not p.is_dir():
            continue
        try:
            tj = json.loads((p / "thread.json").read_text())
        except Exception:
            continue
        if (tj.get("web_uuid") or "") != web_uuid:
            continue
        lu = tj.get("lastUpdated") or ""
        if best is None or lu > best_lu:
            best, best_lu = p, lu
    return best


JS_ROWS = r"""
(() => {
  const rows = [...document.querySelectorAll("div[role=row]")];
  const out = rows.map(r => {
    const pk = Object.keys(r).find(k => k.startsWith("__reactProps"));
    if (!pk) return null;
    const seen = new WeakSet(); let t = null;
    const walk = (o, d) => {
      if (t || d > 8 || !o || typeof o !== "object" || seen.has(o)) return;
      seen.add(o);
      if (o.title && o.entryUUID && o.href) { t = o; return; }
      for (const k in o) { try { walk(o[k], d+1); } catch(e){} }
    };
    walk(r[pk], 0);
    if (!t) return null;
    const modeLabel = (r.querySelector("div[role=cell]") || {}).innerText || "";
    return {
      title: t.title, href: t.href, entryUUID: t.entryUUID,
      mode: t.mode || null, mode_label: modeLabel.trim(),
      lastUpdated: t.lastUpdated, threadCount: t.threadCount,
      displayModel: t.displayModel || null,
      authorName: t.authorName || null, authorUsername: t.authorUsername || null,
      threadAccess: t.threadAccess,
      collection: t.collection ? {uuid: t.collection.uuid, title: t.collection.title, slug: t.collection.slug} : null,
      nAssets: (t.assets || []).length, nAttachments: (t.attachments || []).length,
    };
  }).filter(Boolean);
  return JSON.stringify(out);
})()
"""

JS_SCROLL_BOTTOM = r"""
(() => {
  const cand = [...document.querySelectorAll("div")].filter(e =>
    e.scrollHeight > e.clientHeight + 100 && e.clientHeight > 150);
  for (const c of cand) {
    c.dispatchEvent(new WheelEvent("wheel", {deltaY: 1500, bubbles: true}));
    c.scrollTop = c.scrollHeight;
    c.dispatchEvent(new Event("scroll", {bubbles: true}));
  }
  window.scrollTo(0, document.body.scrollHeight);
  return JSON.stringify({rows: document.querySelectorAll("div[role=row]").length});
})()
"""


def cmd_space_index(adapter, space_url: str, out_root: Path, bridge=None):
    """Extract a space's "All" conversation list (including other members' threads
    in shared spaces).

    REST-direct by default (list_collection_threads, cookie, offset pagination,
    includes context_uuid); when bridge is given, the legacy browser-rendering path
    is used (fallback in case the REST structure changes).

    提取某空间「全部」会话列表（含共享空间他方成员线程）。

    默认 REST 直连（list_collection_threads，cookie，offset 分页，含 context_uuid）；
    bridge 非空时走旧浏览器渲染路径（备用，REST 结构变更时兜底）。
    """
    slug = space_url.rstrip("/").split("/")[-1]
    if bridge is None:
        rows = []
        for t in adapter.list_collection_threads(slug):
            uuid = t.get("uuid") or ""
            mode = (t.get("mode") or "").upper() or None
            rows.append({
                "title": t.get("title") or t.get("query_str") or "",
                "href": f"/computer/tasks/{uuid}" if mode in ("ASI", "COMPUTER") else f"/search/{uuid}",
                "entryUUID": uuid,
                "mode": mode,
                "mode_label": t.get("mode") or "",
                "lastUpdated": t.get("last_query_datetime"),
                "authorName": t.get("author_name"),
                "authorUsername": t.get("author_username"),
                "threadAccess": t.get("thread_access"),
                "context_uuid": t.get("context_uuid"),
                "answer_preview": (t.get("answer_preview") or "")[:200],
            })
        rows = sorted(rows, key=lambda x: x.get("lastUpdated") or "", reverse=True)
        view = "全部（REST list_collection_threads，含共享成员线程）"
    else:
        collected: dict = {}
        bridge.navigate(space_url, wait=5)
        last = -1
        stale = 0
        for _ in range(40):
            bridge.evaluate(JS_SCROLL_BOTTOM)
            time.sleep(2)
            for r in bridge.evaluate(JS_ROWS) or []:
                if isinstance(r, dict) and (r.get("href") or "").startswith(("/search/", "/computer/")):
                    collected[r["entryUUID"]] = r
            if len(collected) == last:
                stale += 1
                if stale >= 4:
                    break
            else:
                stale = 0
                last = len(collected)
        rows = sorted(collected.values(), key=lambda x: x.get("lastUpdated") or "", reverse=True)
        view = "全部（浏览器渲染，含共享成员线程）"
    doc = {"space_url": space_url, "space_slug": slug, "view": view,
           "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "count": len(rows), "threads": rows}
    safe_slug = _re.sub(r"[^\w.-]+", "_", slug)[:60]
    p = out_root / "index" / f"space_{safe_slug}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    log.info(f"[space-index] {len(rows)} 条 → {p}")



def cmd_sync_space(out_root: Path, rebuild_spaces: bool = True) -> int:
    """Sync the space field of archived thread.json files (purely local, zero
    network).

    Prerequisite: run `pplx-export index` first to refresh library_*.json with the
    latest space ownership.
    This command compares the space slug in the index against thread.json and
    patches in place on divergence.
    Returns the number of changed threads.

    同步已归档 thread.json 的 space 字段（纯本地，零网络）。

    前置：先跑 `pplx-export index` 刷新 library_*.json 拿到最新空间归属。
    本命令对比索引与 thread.json 中的 space slug，有差异则就地 patch。
    返回变更线程数。
    """
    idx_dir = out_root / "index"
    # 1. Build the uuid -> space mapping from the index
    # 1. 从索引构建 uuid → space 映射
    uuid_space: dict[str, dict | None] = {}
    for f in idx_dir.glob("library_*.json"):
        doc = json.loads(f.read_text())
        for t in doc.get("threads", []):
            uuid = t.get("entryUUID") or ""
            if not uuid:
                continue
            sp = t.get("collection") or t.get("space") or None
            # None = no space
            # None = 无空间
            uuid_space[uuid] = sp

    if not uuid_space:
        log.info("[sync-space] 索引为空，请先跑 pplx-export index")
        return 0

    # 2. Scan all thread.json files
    # 2. 扫描所有 thread.json
    patched = 0
    scanned = 0
    changes: list[str] = []
    for tj in out_root.rglob("thread.json"):
        # Skip non-thread files under index/
        # 跳过 index/ 下的非线程文件
        if "index" in tj.parts:
            continue
        scanned += 1
        try:
            data = json.loads(tj.read_text())
        except Exception:
            continue
        uuid = data.get("web_uuid") or ""
        if uuid not in uuid_space:
            continue
        new_sp = uuid_space[uuid]
        old_sp = data.get("space")
        # Compare slugs (the core identifier)
        # 比较 slug（核心标识）
        old_slug = (old_sp or {}).get("slug") if old_sp else None
        new_slug = (new_sp or {}).get("slug") if new_sp else None
        if old_slug == new_slug:
            continue
        # patch
        # 就地修补
        data["space"] = (
            {"uuid": new_sp.get("uuid", ""), "title": new_sp.get("title", ""),
             "slug": new_sp.get("slug", "")}
            if new_sp else None
        )
        tj.write_text(json.dumps(data, ensure_ascii=False, indent=1))
        patched += 1
        title = (data.get("title") or "")[:40]
        changes.append(f"  {uuid[:8]} {title}: {old_slug or '(无)'} → {new_slug or '(无)'}")

    log.info(f"[sync-space] 扫描 {scanned} 个 thread.json，空间变更 {patched} 个")
    for c in changes[:30]:
        log.info(c)
    if len(changes) > 30:
        log.info(f"  …及其余 {len(changes) - 30} 个")

    # 3. Rebuild the spaces/ index alongside
    # 3. 联动重建 spaces/ 索引
    if rebuild_spaces and patched > 0:
        log.info("[sync-space] 联动重建 spaces/ 索引…")
        cmd_spaces(out_root)

    return patched


def cmd_spaces(out_root: Path, adapter=None, fetch_meta: bool = False, adapter_for=None,
               current_account: str = ""):
    """Rebuild the space-view index.

    Participating accounts (thread author distribution) are aggregated purely
    locally; owner/members come from the web_archive/index/space_meta.json cache
    (refreshed via get_collection first when --fetch-meta is given).
    adapter_for(account) retries with an account that can see the space when the
    current account has no access (e.g. B's private spaces).

    重建空间视图索引。

    参与账户（线程作者分布）纯本地聚合；所有者/成员来自
    web_archive/index/space_meta.json 缓存（--fetch-meta 时先经 get_collection 刷新）。
    adapter_for(account) 用于「当前账户无权查看」时改用可见账户重试（如 B 私有空间）。
    """
    idx_dir = out_root / "index"
    threads = []
    for f in idx_dir.glob("library_*.json"):
        doc = json.loads(f.read_text())
        for t in doc.get("threads", []):
            t = dict(t)
            t["_account"] = doc.get("account")
            threads.append(t)
    by_space: dict[str, dict] = {}
    for t in threads:
        c = t.get("collection") or t.get("space") or {}
        slug = c.get("slug") or "_no_space"
        by_space.setdefault(slug, {})[t["entryUUID"]] = t

    # Metadata cache: refreshed first with --fetch-meta (1 request per space,
    # rate-limited interval)
    # 元数据缓存：--fetch-meta 时先刷新（每空间 1 次请求，限频间隔）
    meta_path = idx_dir / "space_meta.json"
    meta_cache: dict = {}
    if meta_path.exists():
        try:
            meta_cache = json.loads(meta_path.read_text())
        except Exception:
            meta_cache = {}
    if fetch_meta:
        if adapter is None:
            raise SystemExit("[ERROR] --fetch-meta 需要数据通路")
        slugs = sorted(s for s in by_space if s != "_no_space")
        for i, slug in enumerate(slugs, 1):
            try:
                meta = adapter.get_space_meta(slug)
                if meta.get("error") and adapter_for:
                    # Current account has no access: retry with an account that can
                    # see the space (cookies switch automatically)
                    # 当前账户无权查看：改用「可见该空间的账户」重试（自动切换 cookie）
                    vis = {t.get("_account") for t in by_space[slug].values()} - {current_account}
                    for acct in sorted(a for a in vis if a):
                        try:
                            meta2 = adapter_for(acct).get_space_meta(slug)
                            if not meta2.get("error"):
                                meta = meta2
                                log.info(f"  ↳ 当前账户无权查看，已用 {acct} 取得")
                                break
                        except Exception:
                            continue
                meta_cache[slug] = meta
                o = meta.get("owner") or {}
                tag = o.get("username") or f"（{meta.get('error') or '?'}）"
                log.info(f"[space-meta {i}/{len(slugs)}] {slug[:45]} ← 所有者 {tag}")
            except Exception as e:
                meta_cache.setdefault(slug, {"slug": slug, "error": str(e)[:200]})
                log.info(f"[space-meta {i}/{len(slugs)}] {slug[:45]} 失败: {str(e)[:80]}")
            if i < len(slugs):
                time.sleep(3.0)
        meta_path.write_text(json.dumps(meta_cache, ensure_ascii=False, indent=1))
        log.info(f"[space-meta] {len(slugs)} 个空间 → {meta_path}")

    spaces_dir = Path("spaces")
    spaces_dir.mkdir(exist_ok=True)
    registry = []
    for slug, tmap in sorted(by_space.items()):
        ts = list(tmap.values())
        c = (ts[0].get("collection") or ts[0].get("space") or {})
        title = c.get("title") or slug
        safe = "".join(ch if ch.isalnum() or ch in ".-_" else "_" for ch in slug)[:60]
        # Participating-account aggregation (thread author distribution + visible accounts)
        # 参与账户聚合（线程作者分布 + 可见账户）
        authors: dict[str, int] = {}
        visible: set[str] = set()
        for t in ts:
            au = t.get("authorUsername") or t.get("_account") or "?"
            authors[au] = authors.get(au, 0) + 1
            if t.get("_account"):
                visible.add(t["_account"])
        participants = [{"account": a, "n_threads": n}
                        for a, n in sorted(authors.items(), key=lambda x: -x[1])]
        meta = meta_cache.get(slug) or {}
        owner = meta.get("owner") or {}
        members = meta.get("members") or []
        registry.append({"slug": slug, "title": title, "n_threads": len(ts), "file": f"{safe}.md",
                         "participants": participants, "visible_to": sorted(visible),
                         "owner": owner or None, "contributors": meta.get("contributors"),
                         "access": meta.get("access"), "max_contributors": meta.get("max_contributors")})
        head = [f"# 空间索引：{title}", ""]
        if owner.get("username"):
            perm = {4: "所有者", 3: "可管理", 2: "可编辑", 1: "可查看"}
            ml = [f"{m.get('username')}（{m.get('permission_label') or perm.get(m.get('permission'), '?')}）"
                  for m in members]
            head.append(f"> 所有者: **{owner['username']}** ｜ 成员: {'、'.join(ml)}"
                        + (f"（上限 {meta['max_contributors']}）" if meta.get("max_contributors") else ""))
        elif meta.get("error"):
            head.append(f"> 所有者: （未取得：{meta['error']}）")
        part_txt = "、".join(f"{p['account']} ×{p['n_threads']}" for p in participants)
        head.append(f"> 参与账户: {part_txt} ｜ slug: `{slug}` ｜ 线程数: {len(ts)}")
        head += ["", "| 线程 | 作者 | 模式 | 更新时间 | UUID | 导出位置 |", "|---|---|---|---|---|---|"]
        lines = head
        for t in sorted(ts, key=lambda x: x.get("lastUpdated") or "", reverse=True):
            uuid = t.get("entryUUID", "")
            mode = t.get("mode_label") or t.get("mode") or ""
            author = t.get("authorUsername") or t.get("_account") or ""
            lu = (t.get("lastUpdated") or "")[:10]
            title_t = (t.get("title") or "").replace("|", "｜").replace("\n", " ")[:50]
            link = "未导出"
            best = _best_thread_dir(out_root, uuid)
            if best is not None:
                # N-02: use relpath relative to spaces_dir (the previous '../../' was
                # one level too many and broke backlinks with 404)
                # N-02：相对 spaces_dir 用 relpath（此前 '../../' 多一层导致反链 404）
                link = f"[已导出]({os.path.relpath(best, spaces_dir)})"
            lines.append(f"| {title_t} | {author} | {mode} | {lu} | `{uuid[:8]}` | {link} |")
        (spaces_dir / f"{safe}.md").write_text("\n".join(lines) + "\n")
    (spaces_dir / "spaces.json").write_text(json.dumps(
        {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "count": len(registry), "spaces": registry}, ensure_ascii=False, indent=1))
    log.info(f"[spaces] {len(registry)} 个空间索引 → {spaces_dir}")


