"""Schema-versioned parsing of raw Perplexity JSON into domain models.

Key defense against schema changes: all field extraction is centralized in
parsers; missing/renamed fields degrade gracefully (blanked + no crash), so a
site redesign only requires changing this module. raw_*.json is dumped to disk
first, so parsing can be rerun offline.

Perplexity 原始 JSON → 领域模型的 schema 版本化解析。

抗数据结构变更的关键：所有字段提取集中在 parsers，字段缺失/改名时优雅降级
（置空 + 不崩），站点改版只需改本模块。raw_*.json 已先落盘，解析可离线重跑。
"""

from __future__ import annotations

import json
from typing import Optional

from ...core.models import Asset, Citation, Step, SubAgent, Turn


def _g(d: dict, *keys, default=None):
    """Multi-level safe field lookup (first hit wins), to survive field renames.

    多级安全取字段（任一命中即返回），用于应对字段改名。"""
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            return d[k]
    return default


def _loads(v):
    if isinstance(v, (dict, list)):
        return v
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return None
    return None


def to_int(v, default: int = 0) -> int:
    """Lenient int: None/empty string/non-numeric → default (sort keys must not raise).

    宽松 int：None/空串/非数字 → default（排序键不允许抛异常）。"""
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return default


def norm_source(s: dict) -> Citation:
    return Citation(
        name=str(_g(s, "name", "title", default="") or "")[:200],
        url=str(_g(s, "url", "link", default="") or ""),
        snippet=str(_g(s, "snippet", "text", default="") or "")[:500],
        timestamp=_g(s, "timestamp", "date"),
        category=str(_g(s, "category", "type", default="web") or "web"),
    )


def dedup_citations(turns: list[Turn]) -> list[Citation]:
    """Cross-turn citation aggregation: dedupe by url (first occurrence wins) + sort by name.
    export (adapter) and re-render share this one implementation, keeping the
    conv.citations count consistent with the sources.json written at export time
    (N-03: dual implementations inflated the re-render count).

    跨轮引文汇总：按 url 去重（首个出现者为准）+ 按 name 排序。
    export（adapter）与 re-render 共用同一实现，保证 conv.citations 计数
    与导出时写的 sources.json 一致（N-03：双实现导致 re-render 计数虚高）。"""
    seen = {}
    for t in turns:
        for c in t.citations:
            seen.setdefault(c.url, c)
    return sorted(seen.values(), key=lambda c: c.name)


def extract_answer(entry: dict, steps: list[Step]) -> str:
    """Extract a turn's final answer: FINAL.answer (JSON) → longest plan.goals description.

    提取一轮最终答案：FINAL.answer(JSON) → plan.goals 最长 description。"""
    for s in reversed(steps):
        if s.step_type != "FINAL":
            continue
        ans = (s.content or {}).get("answer")
        parsed = _loads(ans)
        if isinstance(parsed, dict):
            if "answer" in parsed:
                # "answer" key present: always prefer it unconditionally (short answers
                # are equally valid, e.g. "Answer skipped."); short answers used to be
                # dropped by a len>30 check, and the fallback then turned the answer
                # into an S3 URL / something off-topic
                # 有 answer 键：无条件优先采用（短答案同样合法，如 "Answer skipped."）；
                # 曾按 len>30 丢弃短答案再走兜底，导致答案变成 S3 URL / 答非所问
                direct = parsed["answer"]
                if isinstance(direct, str) and direct:
                    return direct
                # Empty answer: look for an earlier FINAL, but do not use the fallback
                # (the fallback would mistakenly pick a URL)
                # 空 answer：找更早的 FINAL，但不走兜底（兜底会误挑 URL）
                continue
            if "workflow_snapshots" not in parsed:
                texts: list[str] = []

                def collect(o):
                    if isinstance(o, str) and len(o) > 30:
                        texts.append(o)
                    elif isinstance(o, dict):
                        for v in o.values():
                            collect(v)
                    elif isinstance(o, list):
                        for x in o:
                            collect(x)

                collect(parsed)
                if texts:
                    return max(texts, key=len)
        elif isinstance(ans, str) and len(ans) > 30:
            return ans
    plan = _loads(entry.get("plan"))
    goals = (plan.get("goals") if isinstance(plan, dict) else None) or []
    cands = [g for g in goals if isinstance(g, dict) and len(g.get("description") or "") > 80]
    if cands:
        return max(cands, key=lambda g: len(g["description"]))["description"]
    return ""


def wf_block_answer(wf_block: dict) -> str:
    """Extract the final answer from a schematized workflow_block: the WORKFLOW_ITEM_TEXT
    with variant=="answer".

    text wins, otherwise join chunks (same semantics as render._chunks_text); take the
    last non-empty one. A computer plain FINAL is often a dict without an answer key
    (only workflow_snapshots) and gets skipped by the extract_answer guard, so the real
    answer only lands on the blocks side (observed in 65/486 computer turns).

    从 schematized workflow_block 提取最终答案：variant=="answer" 的 WORKFLOW_ITEM_TEXT。

    text 优先、否则 chunks 拼接（与 render._chunks_text 同义）；取最后一个非空。
    computer 的 plain FINAL 常为 dict 且无 answer 键（仅 workflow_snapshots），被
    extract_answer 守卫跳过，真实答案只落在 blocks 侧（实测 65/486 个 computer turn）。
    """
    out = ""
    for s in (wf_block or {}).get("steps") or []:
        if not isinstance(s, dict):
            continue
        for it in s.get("items") or []:
            if not isinstance(it, dict) or it.get("type") != "WORKFLOW_ITEM_TEXT":
                continue
            tp = (it.get("payload") or {}).get("text_payload") or {}
            if tp.get("variant") != "answer":
                continue
            txt = tp.get("text") or "".join(tp.get("chunks") or [])
            if txt.strip():
                out = txt
    return out


def _norm_step(s: dict) -> Step:
    return Step(
        step_type=str(_g(s, "step_type", "type", default="") or ""),
        content=_g(s, "content", default={}) or {},
        timestamp=str(_g(s, "timestamp", default="") or ""),
        tool_name=str(_g(s, "tool_name", default="") or ""),
        title=str(_g(s, "title", default="") or ""),
        icon=str(_g(s, "icon", default="") or ""),
        step_id=str(_g(s, "id", "uuid", default="") or ""),
    )


def parse_turn(entry: dict, index: int = 0) -> Turn:
    raw_steps = _loads(entry.get("text")) or []
    steps = [_norm_step(s) for s in raw_steps if isinstance(s, dict)]
    citations: list[Citation] = []
    for s in (entry.get("sources") or []):
        if isinstance(s, dict):
            citations.append(norm_source(s))
    for st in steps:
        c = st.content or {}
        if st.step_type == "FINAL":
            aw = _loads(c.get("answer"))
            wr = (aw.get("web_results") if isinstance(aw, dict) else None) or []
            for x in wr:
                if isinstance(x, dict) and x.get("url"):
                    citations.append(norm_source(x))
        for it in (c.get("workflow_items") or []):
            if isinstance(it, dict) and it.get("type") == "WORKFLOW_ITEM_SOURCES":
                sp = (it.get("payload") or {}).get("sources_payload") or {}
                for x in (sp.get("sources") or []):
                    if isinstance(x, dict) and x.get("url"):
                        citations.append(norm_source(x))
    seen, uniq = set(), []
    for s in citations:
        if s.url and s.url not in seen:
            seen.add(s.url)
            uniq.append(s)
    report_info = None
    for st in steps:
        if st.step_type == "RESEARCH_ANSWER":
            c = st.content or {}
            report_info = {"title": c.get("title"), "file_name": c.get("file_name"), "url": c.get("url")}
    md = {"report_info": report_info} if report_info else {}
    if entry.get("locked_reason"):
        # Entry-level interruption reason (observed: spending_limit_exceeded)
        # entry 级中断原因（实测 spending_limit_exceeded）
        md["locked_reason"] = entry["locked_reason"]
    if entry.get("query_source"):
        # Originating channel (default/perplexity_tasks/scheduled/macos/...);
        # the relations same_prompt edge uses it to tell "scheduled-task rerun"
        # apart from "manual resend"
        # 发起渠道（default/perplexity_tasks/scheduled/macos/...）；
        # relations 的 same_prompt 边用它区分「定时任务重跑」与「人工重发」
        md["query_source"] = entry["query_source"]
    return Turn(
        index=index,
        uuid=str(_g(entry, "uuid", default="") or ""),
        context_uuid=str(_g(entry, "context_uuid", default="") or ""),
        query=str(_g(entry, "query_str", "query", default="") or ""),
        created_us=_g(entry, "created_us"),
        updated_us=_g(entry, "updated_us"),
        author=str(_g(entry, "author_username", default="") or ""),
        steps=steps,
        answer=extract_answer(entry, steps),
        citations=uniq,
        metadata=md,
    )


def attach_workflow_blocks(turns: list[Turn], blocks: dict | None) -> None:
    """Attach the schematized workflow_block to each turn by entry uuid (sites-layer duty).

    Rendering of computer/council (render._render_turn_body) and the answer fallback
    (_turn_answer) depend on turn.wf_block; previously attached by the writer at dump
    time, now centralized into adapter.get_thread / offline re-render. Also records the
    entry-level workflow status into turn.metadata["wf_status"] (source of truth for
    interruption tagging/registration).

    把 schematized workflow_block 按 entry uuid 挂到各轮（sites 层职责）。

    computer/council 的渲染（render._render_turn_body）与答案兜底（_turn_answer）依赖
    turn.wf_block；此前由 writer 落盘时挂载，现收归 adapter.get_thread / 离线重渲。
    同时把 entry 级 workflow status 记入 turn.metadata["wf_status"]（中断标注/登记真源）。
    """
    if not blocks:
        return
    wf_by_uuid = {}
    for e in blocks.get("entries", []):
        for b in (e.get("blocks") or []):
            if b.get("workflow_block"):
                wf_by_uuid[e.get("uuid")] = b["workflow_block"]
    for t in turns:
        t.wf_block = wf_by_uuid.get(t.uuid)
        if t.wf_block:
            t.metadata["wf_status"] = t.wf_block.get("status") or ""


# ── Unified workflow-status classification (one shared source of truth for render
# tagging / interruption registration / anomaly detection) ────────
# ── 工作流状态统一分类（渲染标注 / 中断登记 / 异常检测共用同一真源）────────

def classify_wf_status(status, locked_reason: str | None = None) -> str:
    """workflow status + locked_reason → completed/limit_interrupted/awaiting/canceled/other.

    Observed values (2026-07, docs/reference/api/api-responses-errors.md §5.1): WORKFLOW_COMPLETED;
    WORKFLOW_AWAITING_NEXT_STEPS (an entry carrying locked_reason=spending_limit_exceeded
    is a spending-limit interruption; without locked_reason it is awaiting continuation);
    WORKFLOW_CANCELED. Empty/COMPLETED counts as completed.

    workflow status + locked_reason → completed/limit_interrupted/awaiting/canceled/other。

    实测取值（2026-07，docs/reference/api/api-responses-errors.md §5.1）：WORKFLOW_COMPLETED；
    WORKFLOW_AWAITING_NEXT_STEPS（entry 带 locked_reason=spending_limit_exceeded 即限额中断，
    无 locked_reason 则为等待续跑）；WORKFLOW_CANCELED。空/COMPLETED 视为完成。
    """
    s = str(status or "").upper()
    if s in ("", "COMPLETED", "WORKFLOW_COMPLETED"):
        return "completed"
    if s == "WORKFLOW_AWAITING_NEXT_STEPS":
        return "limit_interrupted" if locked_reason == "spending_limit_exceeded" else "awaiting"
    if s == "WORKFLOW_CANCELED":
        return "canceled"
    return "other"


WF_STATUS_TAG = {
    "limit_interrupted": "⏸ 限额中断（内容截至中断点）",
    "awaiting": "⏸ 中断待续",
    "canceled": "⛔ 已取消",
}


def wf_status_tag(status, locked_reason: str | None = None) -> str:
    """Human-readable tag for non-completed workflows; completed/unknown statuses return
    empty (normal rendering is left undisturbed).

    非 completed 工作流的人类可读标注；completed/未知状态返回空（不打扰正常渲染）。"""
    return WF_STATUS_TAG.get(classify_wf_status(status, locked_reason), "")


def wf_subagent_payload(step: dict) -> Optional[dict]:
    for it in (step.get("items") or []):
        wp = (it.get("payload") or {}).get("workflow_payload")
        if wp and (wp.get("objective_chunks") or wp.get("is_background_anchor")):
            return wp
    return None


# ── subagent_result stub turns ↔ background subagent association ──────────────────
# ── subagent_result 桩轮 ↔ 后台子代理关联 ──────────────────

def _parse_iso_dt(s):
    """ISO time string → datetime (with tz); returns None on failure (sorting/comparison
    must not raise).

    ISO 时间串 → datetime（含 tz）；失败返回 None（排序/比较不允许抛异常）。"""
    if not s or not isinstance(s, str):
        return None
    from datetime import datetime
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _iter_wf_payloads(steps):
    """Iterate all nested workflow_payload in workflow steps (including recursive descent).

    遍历 workflow steps 全部嵌套 workflow_payload（含递归下钻）。"""
    for s in steps or []:
        if not isinstance(s, dict):
            continue
        for it in (s.get("items") or []):
            if not isinstance(it, dict):
                continue
            wp = (it.get("payload") or {}).get("workflow_payload")
            if wp:
                yield wp
                yield from _iter_wf_payloads(wp.get("steps"))


def _iter_top_wf_payloads(steps):
    """Take only top-level nested workflow_payload (no recursion). For attribution-waterfall
    candidates only: nested content renders wholesale with its parent payload
    (_render_nested_wf recurses), so parent and child both becoming candidates would
    double-count (appendix re-rendering / stub window mismatching a child payload).
    Current data has no second-level nesting; this is defensive.

    只取顶层嵌套 workflow_payload（不递归）。归属瀑布候选专用：
    嵌套内容随父负载整体渲染（_render_nested_wf 递归），父子同时成候选会
    双重计入（附录重复渲染/桩窗错配子负载）。当前数据无二层嵌套，此为防御。"""
    for s in steps or []:
        if not isinstance(s, dict):
            continue
        for it in (s.get("items") or []):
            if not isinstance(it, dict):
                continue
            wp = (it.get("payload") or {}).get("workflow_payload")
            if wp:
                yield wp


def _wf_steps_count(entry: dict) -> int:
    return sum(len((b.get("workflow_block") or {}).get("steps") or [])
               for b in (entry.get("blocks") or []))


def _anchored_payload_ids(blocks: dict | None) -> set:
    """Set of nested payload ids already anchored (= consumed) in main entries
    (shared by stub-window matching and the appendix fallback).

    主 entry 已锚定（=已消费）的嵌套 payload id 集合（桩窗匹配/附录兜底共用）。"""
    anchored: set[str] = set()
    for e in ((blocks or {}).get("entries") or []):
        for b in (e.get("blocks") or []):
            wf = b.get("workflow_block")
            if wf:
                for wp in _iter_wf_payloads(wf.get("steps")):
                    if wp.get("id"):
                        anchored.add(wp["id"])
    return anchored


def match_stub_workflows(turns: list, blocks: dict | None, tol_s: float = 10.0) -> dict:
    """Greedy time-based matching of subagent_result stub turns ↔ unanchored background
    nested workflow_payload.

    Stub turn: trigger=="subagent_result" with no workflow steps in blocks (a
    zero-workflow notification turn rendered as Query(empty)/Answer(none)).
    Candidates: top-level nested payloads of background_entries (the subagent's own
    work record), excluding ids already anchored in main entries (their content is
    already rendered by sub_map on the originating turn, avoiding duplication).
    Matching: all candidates with |background completion time − stub creation time|
    ≤ tol_s are assigned to that stub in ascending time-difference order; each
    background payload is consumed only once (pairs are matched globally in ascending
    time-difference order; usually 1:1, but one stub may collect multiple agents).
    Completion time is payload.completed_at, falling back to the background entry
    update time when missing (interruption/limit scenarios).
    Returns {turn.index: [workflow_payload, ...]}.

    subagent_result 桩轮 ↔ 未锚定后台嵌套 workflow_payload 的时间贪心匹配。

    桩轮：trigger=="subagent_result" 且 blocks 中无任何 workflow steps
    （渲染为 Query(空)/Answer(无) 的零工作流通知轮）。
    候选：background_entries 顶层嵌套 payload（子代理自身工作记录），
    排除已在主 entry 锚定的 id（其内容已由 sub_map 在发起轮渲染，避免重复）。
    匹配：|后台完成时间 − 桩创建时间| ≤ tol_s 的全部候选按时间差升序归该桩，
    每个后台只被消费一次（全局按时间差升序配对，通常 1:1，可一桩多代理）。
    完成时间取 payload.completed_at，缺失退后台 entry 更新时间（中断/限额场景）。
    返回 {turn.index: [workflow_payload, ...]}。
    """
    if not blocks:
        return {}
    be_by_uuid = {e.get("uuid"): e for e in (blocks.get("entries") or [])}
    anchored = _anchored_payload_ids(blocks)
    # Stub turns (sorted by creation time)
    # 桩轮（按创建时间排序）
    stubs = []
    for t in turns:
        be = be_by_uuid.get(t.uuid)
        if not be or be.get("trigger") != "subagent_result" or _wf_steps_count(be) > 0:
            continue
        if not t.created_us:
            continue
        from datetime import datetime, timezone
        created = datetime.fromtimestamp(to_int(t.created_us) / 1e6, tz=timezone.utc)
        stubs.append((t.index, created))
    if not stubs:
        return {}
    # Unanchored background candidates (top-level payloads: nested content renders
    # wholesale with the parent payload; no descent, to prevent double counting)
    # 未锚定的后台候选（顶层 payload：嵌套随父负载整体渲染，不下钻防双重计入）
    cands = []  # (eff_dt, wp)
    for bg in (blocks.get("background_entries") or []):
        for b in (bg.get("blocks") or []):
            wf = b.get("workflow_block")
            if not wf:
                continue
            for wp in _iter_top_wf_payloads(wf.get("steps")):
                wid = wp.get("id")
                if not wid or wid in anchored:
                    continue
                eff = (_parse_iso_dt(wp.get("completed_at"))
                       or _parse_iso_dt(bg.get("entry_updated_datetime"))
                       or _parse_iso_dt(bg.get("updated_datetime")))
                if eff is not None:
                    cands.append((eff, wp))
    # Global pairing: all (|Δ|, stub, cand) in ascending order; each cand is consumed
    # only once, a stub may collect multiple
    # 全局配对：所有 (|Δ|, stub, cand) 升序，cand 只消费一次，stub 可收多个
    pairs = []
    for si, (tidx, created) in enumerate(stubs):
        for ci, (eff, wp) in enumerate(cands):
            delta = abs((created - eff).total_seconds())
            if delta <= tol_s:
                pairs.append((delta, si, ci))
    pairs.sort(key=lambda x: x[0])
    out: dict[int, list[dict]] = {}
    used_cand: set[int] = set()
    for delta, si, ci in pairs:
        if ci in used_cand:
            continue
        used_cand.add(ci)
        tidx = stubs[si][0]
        out.setdefault(tidx, []).append(cands[ci][1])
    return out


def attach_stub_workflows(turns: list, blocks: dict | None) -> None:
    """Attach the background nested workflow_payload matched to stub turns onto
    turn.stub_wfs (sites-layer duty).

    Called together with attach_workflow_blocks (adapter.get_thread / offline re-render);
    the render layer (render._work_process_computer) only reads turn.stub_wfs.

    把桩轮关联到的后台嵌套 workflow_payload 挂到 turn.stub_wfs（sites 层职责）。

    与 attach_workflow_blocks 同期调用（adapter.get_thread / 离线重渲）；
    渲染层（render._work_process_computer）只读 turn.stub_wfs。
    """
    matched = match_stub_workflows(turns, blocks)
    for t in turns:
        t.stub_wfs = matched.get(t.index, [])


# ── Attribution waterfall level 3: thread appendix of unconsumed background payloads
# + interruption registration/detection ─────────────
# ── 归属瀑布第三级：未消费后台负载的线程附录 + 中断登记/检测 ─────────────

def collect_unconsumed_background(turns: list, blocks: dict | None) -> list[dict]:
    """Background nested payloads that are neither anchored nor consumed by the stub
    window (conversation.md appendix data source).

    Attribution waterfall (each payload lands in exactly one place, never rendered
    twice): ① main entry run_subagent anchor (adapter.sub_agents → render_wf_step) →
    ② subagent_result stub window 10s time association (match_stub_workflows) →
    ③ this function as the fallback. An interrupted background task produces no
    completion notification, so the first two levels necessarily miss it (observed:
    f517734c "撰写2.2河流", 38 steps); status is unrestricted
    (AWAITING/CANCELED/COMPLETED/future values) — anything unconsumed is archived here
    as-is. Returns [{wp, locked_reason, updated, bg_uuid}], preserving the original
    background_entries order.

    既未锚定也未被桩窗消费的后台嵌套负载（conversation.md 附录数据源）。

    归属瀑布（每条负载只落一处，绝不双渲染）：① 主 entry run_subagent 锚点
    （adapter.sub_agents → render_wf_step）→ ② subagent_result 桩窗 10s 时间关联
    （match_stub_workflows）→ ③ 本函数兜底。中断的后台任务不产生完成通知，
    前两级必然落空（实测 f517734c「撰写2.2河流」38 步）；状态不限
    （AWAITING/CANCELED/COMPLETED/未来取值），凡未消费者都在此如实归档。
    返回 [{wp, locked_reason, updated, bg_uuid}]，保持 background_entries 原序。
    """
    if not blocks:
        return []
    anchored = _anchored_payload_ids(blocks)
    consumed = {wp.get("id") for wps in match_stub_workflows(turns, blocks).values() for wp in wps}
    out: list[dict] = []
    for bg in (blocks.get("background_entries") or []):
        for b in (bg.get("blocks") or []):
            wf = b.get("workflow_block")
            if not wf:
                continue
            for wp in _iter_top_wf_payloads(wf.get("steps")):
                wid = wp.get("id")
                if not wid or wid in anchored or wid in consumed:
                    continue
                out.append({"wp": wp, "locked_reason": bg.get("locked_reason"),
                            "updated": (bg.get("entry_updated_datetime")
                                        or bg.get("updated_datetime") or ""),
                            "bg_uuid": bg.get("uuid") or ""})
    return out


def collect_interruptions(conv, sub_map: dict | None = None) -> list[dict]:
    """Thread interruption registry (thread.json.interruptions): non-completed workflows
    plus appendix-unassigned entries.

    Covers: turn-level workflows (turn.metadata wf_status/locked_reason), the actual
    background status of anchored subagents (observed in one thread: anchor side
    COMPLETED, background CANCELED), non-completed subagent payloads already matched
    to stub turns, and appendix-unassigned payloads (registered in any status —
    completed but stranded in raw is still worth surfacing).
    Each entry: {location, kind, headline, status}; see classify_wf_status for kind values.

    线程中断登记（thread.json.interruptions）：非 completed 工作流 + 附录未归入条目。

    覆盖：轮级 workflow（turn.metadata wf_status/locked_reason）、锚定子代理的后台
    实际状态（实测某线程：锚点侧 COMPLETED、后台 CANCELED）、桩轮已关联的非完成
    子代理负载、附录未归入负载（任何状态都登记——completed 但滞留 raw 同样值得可见）。
    每条 {location, kind, headline, status}；kind 取值见 classify_wf_status。
    """
    out: list[dict] = []
    for t in conv.turns:
        ws = t.metadata.get("wf_status")
        cls = classify_wf_status(ws, t.metadata.get("locked_reason"))
        if cls != "completed":
            out.append({"location": f"turn_{t.index:04d}", "kind": cls,
                        "headline": (t.query or "")[:80], "status": ws or ""})
        for s in (t.wf_block or {}).get("steps") or []:
            wp = wf_subagent_payload(s)
            if not wp:
                continue
            sid = wp.get("id") or (s.get("id") or "").removesuffix(":workflow")
            sub = (sub_map or {}).get(sid)
            if sub is None:
                continue
            cls3 = classify_wf_status(getattr(sub, "status", ""), getattr(sub, "locked_reason", ""))
            if cls3 != "completed":
                out.append({"location": f"turn_{t.index:04d}/subagent", "kind": cls3,
                            "headline": getattr(sub, "headline", "") or "",
                            "status": getattr(sub, "status", "") or ""})
        for wp in (t.stub_wfs or []):
            cls2 = classify_wf_status(wp.get("status"), t.metadata.get("locked_reason"))
            if cls2 != "completed":
                out.append({"location": f"turn_{t.index:04d}/subagent_stub", "kind": cls2,
                            "headline": wp.get("headline") or "", "status": wp.get("status") or ""})
    for it in (conv.unconsumed_bgs or []):
        wp = it["wp"]
        out.append({"location": "background_unassigned",
                    "kind": classify_wf_status(wp.get("status"), it.get("locked_reason")),
                    "headline": wp.get("headline") or "", "status": wp.get("status") or ""})
    return out


# ── Answer-rewrite variant registry (side_by_side_metadata) ──────────────────
# ── 答案重写变体登记（side_by_side_metadata）──────────────────

def collect_answer_variants(entries: list | None) -> list[dict]:
    """Answer-rewrite variant registry (thread.json.answer_variants): narrowed-criterion
    hit list over entries[].side_by_side_metadata.

    Criterion (verified 2026-07-23 by scanning all 2442 entries in the corpus; precisely
    hits the single true instance): `sibling_uuid` non-empty, AND (`selection_status`
    non-empty and not SELECTION_STATUS_UNSPECIFIED, OR `experiment_role` without the
    `[control]` prefix). Control-group experiments (`[control]…` + UNSPECIFIED, 6 cases
    in the corpus) are not registered — with no hit the key does not appear, so healthy
    threads produce zero diff. Each entry: {entry_uuid, sibling_uuid, selection_status,
    experiment_role, ...}; sibling_uuid points to the other replaced answer variant
    (its body is not in the thread API response; a dead link pending online forensics).

    答案重写变体登记（thread.json.answer_variants）：entries[].side_by_side_metadata
    收窄判据命中清单。

    判据（2026-07-23 全库 2442 条 entry 扫描验证，精确命中唯一真例）：
    `sibling_uuid` 非空，且（`selection_status` 非空且非 SELECTION_STATUS_UNSPECIFIED，
    或 `experiment_role` 无 `[control]` 前缀）。对照组实验（`[control]…` +
    UNSPECIFIED，全库 6 例）不登记——无命中不出现该键，健康线程零 diff。
    每条 {entry_uuid, sibling_uuid, selection_status, experiment_role, ...}；
    sibling_uuid 指向被替换的另一答案变体（其本体不在线程 API 响应中，死链待在线取证）。
    """
    out: list[dict] = []
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        meta = e.get("side_by_side_metadata")
        if not isinstance(meta, dict):
            continue
        sibling = str(meta.get("sibling_uuid") or "")
        if not sibling:
            continue
        status = str(meta.get("selection_status") or "")
        role = str(meta.get("experiment_role") or "")
        specified = bool(status) and status != "SELECTION_STATUS_UNSPECIFIED"
        if not (specified or not role.startswith("[control]")):
            continue
        rec = {"entry_uuid": str(e.get("uuid") or ""), "sibling_uuid": sibling,
               "selection_status": status, "experiment_role": role}
        override = meta.get("experiment_override")
        if override:
            rec["experiment_override"] = override
        # selection time-related fields (carried over when present in raw; no time keys
        # observed inside metadata so far — the entry-level updated_datetime serves as
        # time evidence that "the rewrite bumped lastUpdated")
        # selection 时间类字段（raw 有则带上；当前观测的 metadata 内无时间键，
        # entry 级 updated_datetime 为「重写推动 lastUpdated」的时间佐证）
        for k, v in meta.items():
            if any(t in k for t in ("time", "date", "_us", "_at")) and k not in rec:
                rec[k] = v
        if e.get("updated_datetime"):
            rec["entry_updated"] = e["updated_datetime"]
        out.append(rec)
    return out


def scan_wf_anomalies(blocks: dict | None) -> list[dict]:
    """Anomaly detection (for adapter warnings): scan all workflow_block in blocks
    (main + background) and return the non-completed list [{location, kind, status}].
    Shares classify_wf_status with rendering/registration.

    异常检测（adapter 告警用）：扫描 blocks 全部 workflow_block（主 + 后台），
    返回非 completed 清单 [{location, kind, status}]。与渲染/登记共用 classify_wf_status。"""
    out: list[dict] = []
    for side, entries in (("entry", (blocks or {}).get("entries") or []),
                          ("background", (blocks or {}).get("background_entries") or [])):
        for e in entries:
            for b in (e.get("blocks") or []):
                wf = b.get("workflow_block")
                if not wf:
                    continue
                cls = classify_wf_status(wf.get("status"), e.get("locked_reason"))
                if cls != "completed":
                    out.append({"location": f"{side}:{(e.get('uuid') or '')[:8]}",
                                "kind": cls, "status": wf.get("status") or ""})
    return out


ASSET_FILE_KEYS = ("doc_file", "slide_file", "research_report", "pdf_file", "docx_file",
                   "code_file", "xlsx_file", "audio_file", "chart", "quiz", "model_3d", "app")


def _asset_file_obj(a: dict) -> dict:
    for k in ASSET_FILE_KEYS:
        v = a.get(k)
        if isinstance(v, dict) and v:
            return v
    return {}


def asset_download_url(a: dict) -> Optional[str]:
    fobj = _asset_file_obj(a)
    if fobj.get("url"):
        return fobj["url"]
    for key in ("download_info", "preview_info"):
        for item in (a.get(key) or []):
            if isinstance(item, dict) and (item.get("url") or item.get("s3_url")):
                return item.get("url") or item.get("s3_url")
    return None


def asset_filename(a: dict) -> Optional[str]:
    fobj = _asset_file_obj(a)
    return fobj.get("filename") or fobj.get("file_name") or fobj.get("name") or a.get("title")


def collect_downloadable_assets(blocks_entries: list[dict]) -> list[Asset]:
    by_name: dict[str, list[Asset]] = {}
    for a in _iter_asset_candidates(blocks_entries):
        url = asset_download_url(a)
        if not url:
            continue
        name = asset_filename(a) or a.get("uuid")
        rec = Asset(
            uuid=a.get("uuid") or "",
            asset_type=a.get("asset_type") or ("RESEARCH_REPORT" if a.get("research_report") else ""),
            filename=name or "",
            url=url,
            created_at=a.get("created_at"),
        )
        by_name.setdefault(name or a.get("uuid") or "unknown", []).append(rec)
    out: list[Asset] = []
    for name, versions in by_name.items():
        versions.sort(key=lambda x: to_int(x.created_at))
        for i, v in enumerate(versions, 1):
            v.version = f"v{i}"
            v.n_versions = len(versions)
            out.append(v)
    return out


PERMISSION_LABEL = {4: "所有者", 3: "可管理", 2: "可编辑", 1: "可查看"}


def parse_space_meta(doc: dict) -> dict:
    """get_collection response → space metadata (missing fields degrade to None/[], no raising).

    Observed fields (2026-07-20): owner_user{username,email,name,permission=4},
    contributor_users[{username,email,name,permission=2=可编辑}], access, max_contributors.

    get_collection 响应 → 空间元数据（缺字段降级为 None/[]，不抛错）。

    实测字段（2026-07-20）：owner_user{username,email,name,permission=4}、
    contributor_users[{username,email,name,permission=2=可编辑}]、access、max_contributors。
    """
    doc = doc if isinstance(doc, dict) else {}

    def _user(u: dict | None) -> dict:
        u = u if isinstance(u, dict) else {}
        perm = u.get("permission")
        return {"username": u.get("username") or "", "email": u.get("email") or "",
                "name": u.get("name") or "", "permission": perm,
                "permission_label": PERMISSION_LABEL.get(perm, str(perm) if perm is not None else "")}

    contributors = [_user(u) for u in (doc.get("contributor_users") or []) if isinstance(u, dict)]
    # Failure response: status=="failed" (e.g. VIEW_COLLECTION_NOT_ALLOWED — the current
    # account has no permission to view this space)
    # 失败响应：status=="failed"（如 VIEW_COLLECTION_NOT_ALLOWED——当前账户无权查看该空间）
    error = None
    if doc.get("status") == "failed" or str(doc.get("_response_type") or "").endswith("NOT_ALLOWED"):
        error = doc.get("_response_type") or "FAILED"
    return {
        "slug": doc.get("slug") or "",
        "error": error,
        "title": doc.get("title") or "",
        "emoji": doc.get("emoji") or (doc.get("appearance") or {}).get("emoji") or "",
        "owner": _user(doc.get("owner_user")),
        "contributors": contributors,
        "members": [ _user(doc.get("owner_user")) ] + contributors if doc.get("owner_user") else contributors,
        "access": doc.get("access"),
        "max_contributors": doc.get("max_contributors"),
        # Filled in by the caller
        # 由调用方填
        "fetched_at": None,
    }


def _iter_asset_candidates(blocks_entries: list[dict]):
    """Iterate asset candidates in unified_assets_block / plan_block (same source as
    collect_downloadable_assets).

    遍历 unified_assets_block / plan_block 中的资产候选（与 collect_downloadable_assets 同源）。"""
    for e in blocks_entries:
        for b in (e.get("blocks") or []):
            ua = b.get("unified_assets_block")
            candidates = (ua.get("assets") or []) if ua else []
            if not ua:
                for s in ((b.get("plan_block") or {}).get("steps") or []):
                    candidates.extend(s.get("assets") or [])
            for a in candidates:
                if isinstance(a, dict):
                    yield a


def _rebuild_diff_text(asset_diff: dict) -> str:
    """asset_diff.files[].lines[] → unified diff text.

    asset_diff.files[].lines[] → unified diff 文本。"""
    out = []
    for f in (asset_diff.get("files") or []):
        fname = f.get("filename") or f.get("display_path") or "?"
        out.append(f"--- a/{fname}\n+++ b/{fname}")
        for ln in (f.get("lines") or []):
            kind = ln.get("kind")
            text = ln.get("text") or ""
            prefix = {"ADD": "+", "REMOVE": "-", "CONTEXT": " "}.get(kind, " ")
            out.append(prefix + text)
    return "\n".join(out)


def collect_inline_assets(blocks_entries: list[dict]) -> list[dict]:
    """Collect inline content assets (ASSET_DIFF / CODE_ASSET) — content lives inside
    the block, no URL needed.

    Yields {uuid, asset_type, filename, created_at, inline_kind, content}; entries
    without content are skipped.

    收集内联内容资产（ASSET_DIFF / CODE_ASSET）——内容在块内，无需 URL。

    产出 {uuid, asset_type, filename, created_at, inline_kind, content}；无内容的跳过。
    """
    out = []
    for a in _iter_asset_candidates(blocks_entries):
        t = a.get("asset_type") or ""
        if t == "ASSET_DIFF":
            ad = a.get("asset_diff") or {}
            content = _rebuild_diff_text(ad)
            fname = ad.get("title") or (ad.get("files") or [{}])[0].get("filename") or a.get("uuid")
            kind = "diff"
        elif t == "CODE_ASSET":
            dis = [d for d in (a.get("download_info") or []) if isinstance(d, dict) and d.get("text_content")]
            content = dis[0]["text_content"] if dis else ((a.get("code") or {}).get("script") or "")
            fname = (dis[0].get("filename") if dis else None) or a.get("title") or a.get("uuid")
            kind = "code"
        else:
            continue
        if not (content or "").strip():
            continue
        out.append({"uuid": a.get("uuid") or "", "asset_type": t,
                    "filename": fname or "untitled", "created_at": a.get("created_at"),
                    "inline_kind": kind, "content": content})
    return out


def collect_handle_assets(blocks_entries: list[dict]) -> list[dict]:
    """Collect assets that only carry a cloud-workspace handle (DOC_FILE/CODE_FILE/UNKNOWN
    with no download URL).

    Yields {uuid, asset_type, filename, file_handle} — for registration only (no API
    download channel yet; observed 404).

    收集仅含云工作区句柄的资产（DOC_FILE/CODE_FILE/UNKNOWN 且无下载 URL）。

    产出 {uuid, asset_type, filename, file_handle}——登记用（暂无 API 下载通道，实测 404）。
    """
    out = []
    for a in _iter_asset_candidates(blocks_entries):
        if a.get("asset_type") not in ("DOC_FILE", "CODE_FILE", "UNKNOWN", None):
            continue
        if asset_download_url(a):
            continue
        handle = ""
        for item in (a.get("preview_info") or []):
            if isinstance(item, dict) and item.get("file_handle"):
                handle = item["file_handle"]
                break
        uuid = a.get("uuid") or ""
        # V4-03: a candidate with both uuid and file_handle empty has no identity to
        # register — backfill's known index only accepts truthy uuids; an empty-string
        # record would not be recognized on the next run and would get re-appended
        # every time
        # V4-03：uuid 与 file_handle 双空的候选无任何身份可登记——backfill 的
        # known 索引只收真值 uuid，空串记录下次运行无法识别，会逐次重复追加
        if not uuid and not handle:
            continue
        out.append({"uuid": uuid, "asset_type": a.get("asset_type") or "UNKNOWN",
                    "filename": asset_filename(a) or (handle.rsplit("/", 1)[-1] if handle else ""),
                    "file_handle": handle})
    return out


def parse_council_items(wf_block: dict) -> list[SubAgent]:
    """Council: extract each model's nested LLM_COUNCIL workflow from the items of the
    council_research step.

    Each workflow contains model/headline/steps; within steps, query groups (QUERIES)
    and that group's sources (SOURCES) alternate in order, ending with the model's
    answer (WORKFLOW_ITEM_TEXT variant=answer). The round association (query→sources)
    is encoded as a Step with step_type="COUNCIL_ROUND"
    (content={"queries": [...], "sources": [Citation,...]}). Mapped to SubAgent
    (model→sub_id).

    委员会：从 council_research 步的 items 提取每个模型的嵌套 LLM_COUNCIL 工作流。

    每个工作流含 model/headline/steps；steps 内按序交替出现检索词组（QUERIES）与
    该组的来源（SOURCES），最后是该模型答案（WORKFLOW_ITEM_TEXT variant=answer）。
    轮次关联（query→sources）编码为 step_type="COUNCIL_ROUND" 的 Step
    （content={"queries": [...], "sources": [Citation,...]}）。映射为 SubAgent（model→sub_id）。
    """
    out: list[SubAgent] = []
    for step in (wf_block.get("steps") or []):
        for it in (step.get("items") or []):
            wp = (it.get("payload") or {}).get("workflow_payload") or {}
            if wp.get("mode") != "LLM_COUNCIL":
                continue
            sub = SubAgent(sub_id=wp.get("model") or "",
                           headline=wp.get("headline") or wp.get("model") or "")
            cur_queries: list[str] = []
            for s in (wp.get("steps") or []):
                for item in (s.get("items") or []):
                    if not isinstance(item, dict):
                        continue
                    tp = item.get("type")
                    pl = item.get("payload") or {}
                    if tp == "WORKFLOW_ITEM_TEXT":
                        tpp = pl.get("text_payload") or {}
                        txt = tpp.get("text") or "".join(tpp.get("chunks") or [])
                        if tpp.get("variant") == "answer" and txt:
                            sub.answer = txt
                    elif tp == "WORKFLOW_ITEM_QUERIES":
                        qs = (pl.get("queries_payload") or {}).get("queries") or []
                        cur_queries = [q if isinstance(q, str) else (q.get("query") or "")
                                       for q in qs]
                        cur_queries = [q for q in cur_queries if q]
                    elif tp == "WORKFLOW_ITEM_SOURCES":
                        srcs = [norm_source(x) for x in
                                ((pl.get("sources_payload") or {}).get("sources") or [])
                                if isinstance(x, dict) and x.get("url")]
                        sub.sources.extend(srcs)
                        if cur_queries or srcs:
                            sub.steps.append(Step(
                                step_type="COUNCIL_ROUND",
                                content={"queries": cur_queries, "sources": srcs}))
                        cur_queries = []
            out.append(sub)
    return out
