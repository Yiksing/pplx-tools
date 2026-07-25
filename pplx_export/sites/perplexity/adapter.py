"""Perplexity site adapter: assembles GraphQL/REST data into domain models.

Perplexity 站点适配器：把 GraphQL/REST 数据组装为领域模型。
"""

from __future__ import annotations

import time
from typing import Iterator, Optional

from ...core.logging import get_logger
from ...core.models import Account, Conversation, RelationEdge, Report, Space, SubAgent, Turn
from ...core.http.transport import Transport
from ..base import SiteAdapter
from . import parsers, variant_log
from .assets import AssetDownloader
from .graphql import GraphQLClient
from .normalize import detect_mode, normalize_math_delims, ts_us_to_iso, ts_us_to_iso_full
from .rest import ThreadFetcher

log = get_logger("adapter")


class PerplexityAdapter(SiteAdapter):
    site_id = "perplexity"

    def __init__(self, transport: Transport, page_delay: float = 3.0, asset_delay: float = 0.5,
                 blocks_delay: float = 4.0):
        self.transport = transport
        # Wait before fetching schematized blocks (originally hardcoded 4.0s).
        # 抓 schematized blocks 前的等待（原硬编码 4.0s）
        self.blocks_delay = blocks_delay
        self.graphql = GraphQLClient(transport)
        self.fetcher = ThreadFetcher(transport, page_delay=page_delay)
        self.downloader = AssetDownloader(transport, delay=asset_delay)

    # ── Listing ────────────────────────────────────────────
    # ── 列表 ───────────────────────────────────────────────
    def list_threads(self, account: Account, **kwargs) -> Iterator[dict]:
        for node in self.graphql.list_threads():
            yield {
                "title": node.get("name"),
                "entryUUID": node.get("entryId"),
                "href": node.get("slug"),
                "mode": node.get("mode"),
                "displayModel": (node.get("displayModel") or {}).get("modelID"),
                "lastUpdated": node.get("updatedAt"),
                "status": node.get("status"),
                "space": (node.get("space") or {}) and {
                    "uuid": node["space"].get("spaceUuid"),
                    "title": node["space"].get("title"),
                    "slug": node["space"].get("slug"),
                } or None,
            }

    # ── Single thread ──────────────────────────────────────
    # ── 单线程 ─────────────────────────────────────────────
    def get_thread(self, uuid: str, idx_thread: dict | None = None, **kwargs) -> Conversation:
        plain = self.fetcher.get_thread(uuid)
        turns = [parsers.parse_turn(e, i + 1) for i, e in enumerate(plain["entries"])]
        turns = sorted(turns, key=lambda t: parsers.to_int(t.created_us))
        for i, t in enumerate(turns, 1):
            t.index = i
        # The redundant display_model check for study/council/computer is merged into detect_mode (any() over entries).
        # study/council/computer 的 display_model 冗余判别已并入 detect_mode（any 遍历 entries）
        mode = detect_mode(plain["metadata"], idx_thread, kwargs.get("url", ""), turns,
                           entries=plain.get("entries"))

        # Both computer and deep-research get a supplementary schematized-blocks fetch
        # (workflow structure + citations + assets + sub-agents); council needs it too
        # (the nested LLM_COUNCIL workflows live there); study blocks were verified to
        # contain steps/citations/assets (3900ab2c, 31 turns + assets, confirmed by a
        # supplementary fetch on 2026-07-22); search does not (simple query+answer).
        # When all detection signals are silent (no step-name hit and no display_model
        # on any entry), do not conclude "search" — fetch blocks as a fallback: better
        # to over-fetch than to let raw_blocks.json silently go missing after a
        # platform field change.
        # computer 与 deep-research 均补抓 schematized 块（workflow 结构 + 引文 + 资产 + 子代理）；
        # council 同样需要（嵌套 LLM_COUNCIL 工作流在其中）；study 实测 blocks 含步骤/引文/资产
        # （3900ab2c 31 轮+资产，2026-07-22 补抓证实）；search 无需（简单 query+answer）。
        # 判别信号全灭（步骤名未命中且所有 entry 无 display_model）时不做 search 定论，
        # 兜底也抓 blocks——宁可多抓，避免平台改字段后 raw_blocks.json 静默不落盘。
        entries = plain.get("entries") or []
        uncertain = (mode == "search" and bool(entries)
                     and all(not (e.get("display_model") or "") for e in entries))
        blocks = None
        if mode in ("computer", "deep-research", "council", "study") or uncertain:
            time.sleep(self.blocks_delay)
            blocks = self.fetcher.get_thread_blocks(uuid)

        conv = Conversation(
            web_uuid=uuid,
            url=kwargs.get("url", ""),
            mode=mode,
            turns=turns,
            metadata=plain["metadata"],
        )
        conv.title = (plain["metadata"].get("title") or (idx_thread or {}).get("title") or "untitled").strip()
        conv.psc_uuid = next((t.context_uuid for t in turns if t.context_uuid), None)
        # lastUpdated contract (V5-01): prefer the platform index updatedAt
        # (microsecond ISO; idx_thread is passed in by batch/export from the local
        # index); without an index row, fall back to true ISO (second precision, Z
        # suffix) — no longer the minute-precision display format of ts_us_to_iso
        # (reserved for render headers).
        # lastUpdated 契约（V5-01）：优先平台索引 updatedAt（微秒 ISO，idx_thread
        # 由 batch/export 从本地索引传入）；无索引行时兜底为真 ISO（秒级 Z 后缀），
        # 不再用 ts_us_to_iso 的分钟级 display 格式（那是渲染头部专用）。
        conv.last_updated = (idx_thread or {}).get("lastUpdated") or ts_us_to_iso_full(
            turns[-1].updated_us if turns else None)
        conv.author = (idx_thread or {}).get("authorUsername") or (turns[0].author if turns else "")
        sp = (idx_thread or {}).get("collection") or (idx_thread or {}).get("space")
        if sp:
            conv.space = Space(uuid=sp.get("uuid", ""), title=sp.get("title", ""), slug=sp.get("slug", ""))
        # Citation aggregation (shares one implementation with re-render; see parsers.dedup_citations).
        # 引文汇总（与 re-render 共用同一实现，见 parsers.dedup_citations）
        conv.citations = parsers.dedup_citations(turns)
        # Report.
        # 报告
        rep_info = next((t.metadata["report_info"] for t in turns if t.metadata.get("report_info")), None)
        if rep_info:
            conv.report = Report(title=rep_info.get("title") or "", file_name=rep_info.get("file_name") or "",
                                 url=rep_info.get("url") or "")
        # Used by assets/report/sub_agents.
        # 供 assets/report/sub_agents 使用
        conv._blocks = blocks
        # Used by sub-agents (full steps from background_entries).
        # 供子代理（background_entries 完整步骤）使用
        conv._plain = plain
        # Interruption/cancellation visibility: warn on any locked_reason / non-COMPLETED workflow (thread + location).
        # 中断/取消可见性：发现 locked_reason / 非 COMPLETED 工作流即告警（线程+位置）
        anomalies = parsers.scan_wf_anomalies(blocks)
        if anomalies:
            log.warning(f"[wf] {uuid}「{conv.title}」非完成工作流 {len(anomalies)} 处: "
                        + "; ".join(f"{a['location']}:{a['kind']}" for a in anomalies[:12]))
        # Answer-rewrite variant registry: warn + write thread.json on narrowed
        # side_by_side_metadata criteria hits (replaced variants are invisible on the
        # API side; the registry makes "a rewrite happened" observable; since 2026-07-23).
        # 答案重写变体登记：side_by_side_metadata 收窄判据命中即告警 + 写入 thread.json
        # （被替换变体在 API 侧不可见，登记使「重写发生过」可观测；2026-07-23 起）
        conv.answer_variants = parsers.collect_answer_variants(plain.get("entries"))
        if conv.answer_variants:
            # Online path: warn on every actual-fetch hit (single
            # ANSWER_VARIANT_DETECTED line, grep-able; alternate answers may be purged
            # by the platform, so manual action is needed at once).
            # 在线路径：每次实际抓取命中都告警（ANSWER_VARIANT_DETECTED 单行，
            # 可 grep；备选答案或将被平台清理，需第一时间人工处置）
            variant_log.warn_detections(uuid, conv.title, conv.answer_variants)
        # Attach workflow_block of computer/council to each turn (writer only reads; rendering and answer fallback depend on it).
        # computer/council 的 workflow_block 挂到各轮（writer 只读不挂；渲染与答案兜底依赖）
        if mode in ("computer", "council"):
            parsers.attach_workflow_blocks(turns, blocks)
            # Time-based association of subagent_result stub turns with background sub-agent records (rendered as sub-agent blocks).
            # subagent_result 桩轮 ↔ 后台子代理记录的时间关联（渲染为子代理块）
            parsers.attach_stub_workflows(turns, blocks)
            # Attribution waterfall level 3: unconsumed background payloads → appendix at the end of conversation.md.
            # 归属瀑布第三级：未消费的后台负载 → conversation.md 末尾附录
            conv.unconsumed_bgs = parsers.collect_unconsumed_background(turns, blocks)
        return conv

    # ── Report ─────────────────────────────────────────────
    # ── 报告 ───────────────────────────────────────────────
    def get_report(self, conversation: Conversation, **kwargs) -> Optional[str]:
        blocks = conversation._blocks
        if blocks is None or conversation.report is None:
            return None
        assets = parsers.collect_downloadable_assets(blocks["entries"])
        fname = conversation.report.file_name
        # Exact file_name match first (newest version within the group); fall back to
        # the RESEARCH_REPORT type only when no exact match. The old version took the
        # first hit by ascending created_at and once grabbed a 0-byte draft/fragment.
        # 先按 file_name 精确匹配（同组取最新版本），无精确匹配再退到 RESEARCH_REPORT 类型；
        # 旧版按 created_at 升序取第一个命中，曾拿到 0 字节过程稿/残篇
        exact = [a for a in assets if fname and a.filename == fname]
        rest = [a for a in assets if a.asset_type == "RESEARCH_REPORT" and a not in exact]
        key = lambda a: parsers.to_int(a.created_at)
        for a in sorted(exact, key=key, reverse=True) + sorted(rest, key=key, reverse=True):
            try:
                data = self.transport.download(a.url, timeout=120)
            except Exception as e:
                log.warning(f"[report] 下载失败 {a.filename} ({a.version}): {e}")
                continue
            if not data or not data.strip():
                # Empty draft/fragment: try the next candidate.
                # 空过程稿/残篇：试下一个候选
                continue
            md = data.decode("utf-8", errors="replace")
            sniff = AssetDownloader.sniff_ext(data)
            if sniff:
                log.warning(f"[report] 报告内容疑似二进制（{sniff}），跳过 {a.filename} ({a.version})")
                continue
            return normalize_math_delims(md)
        return None

    # ── Assets ─────────────────────────────────────────────
    # ── 资产 ───────────────────────────────────────────────
    def get_assets(self, conversation: Conversation, dest_dir=None, **kwargs) -> list:
        blocks = conversation._blocks
        if blocks is None:
            return []
        assets = parsers.collect_downloadable_assets(blocks["entries"])
        if dest_dir is not None:
            self.downloader.download_all(assets, dest_dir)
        return assets

    # ── Sub-agents ─────────────────────────────────────────
    # ── 子代理 ─────────────────────────────────────────────
    def sub_agents(self, conversation: Conversation) -> list[SubAgent]:
        blocks = conversation._blocks
        if blocks is None:
            return []
        # Council: nested LLM_COUNCIL workflows (one SubAgent per model, sub_id=model).
        # 委员会：嵌套 LLM_COUNCIL 工作流（每模型一个 SubAgent，sub_id=model）
        council: list[SubAgent] = []
        for e in blocks.get("entries") or []:
            for b in (e.get("blocks") or []):
                wf = b.get("workflow_block")
                if wf:
                    council.extend(parsers.parse_council_items(wf))
        if council:
            return council
        plain_bg = (conversation._plain or {}).get("background_entries") or []
        plain_by_uuid = {be.get("uuid"): be for be in plain_bg}
        schem_bg = blocks.get("background_entries") or []
        bg_by_id = {}
        # sid → real background-side workflow status/locked_reason (anchor-side status may lag).
        # sid → 后台侧真实 workflow status/locked_reason（锚点侧状态可能滞后）
        bg_meta_by_id = {}
        for be in schem_bg:
            sid = None
            wf_status = ""
            for b in (be.get("blocks") or []):
                wf = b.get("workflow_block") or {}
                for s in (wf.get("steps") or []):
                    if s.get("tool_name") == "run_subagent" and s.get("id"):
                        sid = s["id"]
                        wf_status = wf.get("status") or ""
                        break
                if sid:
                    break
            if sid:
                plain = plain_by_uuid.get(be.get("uuid")) or be
                bg_by_id[sid] = plain
                bg_meta_by_id[sid] = {"status": wf_status,
                                      "locked_reason": be.get("locked_reason") or ""}
        out = []
        for e in blocks.get("entries") or []:
            for b in (e.get("blocks") or []):
                for s in ((b.get("workflow_block") or {}).get("steps") or []):
                    wp = parsers.wf_subagent_payload(s)
                    if not wp:
                        continue
                    sid = wp.get("id") or (s.get("id") or "").removesuffix(":workflow")
                    prompt = "".join(wp.get("objective_chunks") or [])
                    bg = bg_by_id.get(sid)
                    sub = SubAgent(sub_id=sid, headline=wp.get("headline") or s.get("title") or "",
                                   prompt=prompt)
                    meta = bg_meta_by_id.get(sid)
                    if meta:
                        sub.status = meta["status"]
                        sub.locked_reason = meta["locked_reason"]
                    if bg:
                        # The sub-agent's own thread.
                        # 子代理自身线程
                        sub.thread_uuid = str(bg.get("backend_uuid") or "")
                        t = parsers.parse_turn(bg)
                        sub.steps = t.steps
                        sub.answer = t.answer
                        sub.sources = t.citations
                    out.append(sub)
        return out

    # ── Space metadata ─────────────────────────────────────
    # ── 空间元数据 ──────────────────────────────────────────
    def get_space_meta(self, slug: str, **kwargs) -> dict:
        """Space owner/members (get_collection, direct cookie access, no browser needed).

        空间所有者/成员（get_collection，cookie 直连，无需浏览器）。
        """
        meta = parsers.parse_space_meta(self.fetcher.get_collection(slug))
        meta["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return meta

    # ── Space thread list (direct cookie access, replaces the browser-based space-index) ──
    # ── 空间线程列表（cookie 直连，替代浏览器版 space-index）────────
    def list_collection_threads(self, slug: str, page_delay: float = 3.0, **kwargs) -> Iterator[dict]:
        """list_collection_threads: all threads of a space (including shared members), offset-paginated (20 per page).

        Each item carries uuid(=entryUUID)/context_uuid/author_username/title/mode/last_query_datetime, etc.

        list_collection_threads：空间全部线程（含共享成员），offset 分页（每页 20）。

        每项含 uuid(=entryUUID)/context_uuid/author_username/title/mode/last_query_datetime 等。
        """
        import urllib.parse
        offset = 0
        while True:
            j = self.transport.get_json(
                "https://www.perplexity.ai/rest/collections/list_collection_threads"
                f"?collection_slug={urllib.parse.quote(slug, safe='')}&offset={offset}"
                "&version=2.18&source=default", timeout=30)
            items = j if isinstance(j, list) else (j.get("threads") or [])
            if not items:
                break
            for t in items:
                yield t
            if not items[0].get("has_next_page"):
                break
            offset += len(items)
            time.sleep(page_delay)

    # ── Asset metadata (refresh for expired/missing signed URLs) ──
    # ── 资产元数据（过期/缺失签名 URL 刷新）────────────────
    def get_asset_data(self, asset_uuid: str, **kwargs) -> dict:
        """Asset metadata: fresh signed URLs + owning thread (/rest/assets/<uuid>/data, verified 200).

        Returns {download_urls, entry_uuid, thread_access, asset_type}; cloud-workspace
        handles with the toolu_ prefix get a 404 from the platform (no download channel).

        资产元数据：新鲜签名 URL + 关联线程（/rest/assets/<uuid>/data，已实测 200）。

        返回 {download_urls, entry_uuid, thread_access, asset_type}；
        toolu_ 前缀的云工作区句柄该平台返回 404（无下载通道）。
        """
        import urllib.parse
        j = self.transport.get_json(
            "https://www.perplexity.ai/rest/assets/"
            f"{urllib.parse.quote(asset_uuid, safe='')}/data?version=2.18&source=default",
            timeout=30)
        urls = []
        ad = j.get("asset_data") or {}
        for d in (ad.get("download_info") or []):
            if isinstance(d, dict) and d.get("url"):
                urls.append({"url": d["url"], "filename": d.get("filename") or "",
                             "is_exportable": d.get("is_exportable")})
        for key in parsers.ASSET_FILE_KEYS:
            fo = ad.get(key)
            if isinstance(fo, dict) and fo.get("url"):
                urls.append({"url": fo["url"], "filename": fo.get("filename") or fo.get("name") or "",
                             "is_exportable": True})
        return {"download_urls": urls, "entry_uuid": j.get("entry_uuid") or "",
                "thread_access": j.get("thread_access"), "asset_type": j.get("asset_type") or ""}

    # ── Relations ──────────────────────────────────────────
    # ── 关系 ───────────────────────────────────────────────
    def relations(self, conversation: Conversation) -> list[RelationEdge]:
        # Space co-occurrence/citation relations are built centrally by core.relations; no site-side edges to extract yet.
        # 空间共现/引用关系由 core.relations 统一建；站点侧暂无可提取边
        return []
