"""Normalization helpers: mode detection, math-delimiter normalization, slug/filename cleaning.

规范化辅助：模式识别、公式分隔符规范化、slug/文件名清洗。
"""

from __future__ import annotations

import re

from ...core.logging import get_logger
from ...core.models import Turn

log = get_logger("normalize")

# Redundant display_model → mode detection signal (backs up step-name detection: it
# still works if the platform renames steps). Only values verified unambiguous are
# included. pplx_alpha is deliberately excluded: it is the RESEARCH-only model
# (verified via the official GET /rest/models/config/v2:
# default_models.research=pplx_alpha, UI name "Deep research") — it is the target this
# classifier must detect, not evidence for detection. The earlier statistic "121
# search threads use pplx_alpha" was actually a misclassification by this classifier
# itself (RESEARCH sessions judged as search when the search_mode signal was missing)
# and cannot be used in reverse as evidence that "pplx_alpha is a common plain-search
# model".
# display_model → 模式 的冗余判别信号（与步骤名判别互备：平台改步骤名时仍能识别）。
# 只收录实测无歧义的取值。pplx_alpha 刻意未收录：它是 RESEARCH 专属模型
# （官方 GET /rest/models/config/v2 实测 default_models.research=pplx_alpha，
# UI 名「Deep research」），是本分类器要判出的目标、而非判别依据——
# 早前「121 个 search 线程使用 pplx_alpha」的统计样本实为本分类器自身误判
# （缺 search_mode 信号时把 RESEARCH 会话判成了 search），不能反过来当作
# 「pplx_alpha 是普通 search 常用模型」的证据。
DISPLAY_MODEL_MODE = {
    "pplx_agentic_research": "council",
    "pplx_asi_opus": "computer",
    "pplx_asi_opus_thinking": "computer",
    "pplx_study": "study",
}

# entry.search_mode → mode: the platform-authoritative field, highest-priority signal.
# Verified against the official model config (GET /rest/models/config/v2):
# default_models.search=pplx_pro (UI "Best"), default_models.research=pplx_alpha
# (UI "Deep research"); search_mode values map 1:1 to conversation modes (archive
# verification: 147 SEARCH-entry + pplx_alpha threads are 100% search_mode=RESEARCH;
# 157 pure pplx_pro threads are all SEARCH).
# entry.search_mode → 模式：平台权威字段，最高优先级信号。官方模型配置实测
# （GET /rest/models/config/v2）：default_models.search=pplx_pro（UI「最佳」）、
# default_models.research=pplx_alpha（UI「Deep research」），search_mode 取值与
# 会话模式一一对应（归档验证：147 个 SEARCH 入口+pplx_alpha 线程 100% search_mode=
# RESEARCH；157 个纯 pplx_pro 线程全部 SEARCH）。
SEARCH_MODE_MAP = {
    "ASI": "computer",
    "AGENTIC_RESEARCH": "council",
    "STUDY": "study",
    "RESEARCH": "deep-research",
    "SEARCH": "search",
    # pplx_beta (labs); the UI groups it under search, not a separate mode.
    # pplx_beta（labs），UI 归在 search 侧，不算独立模式
    "STUDIO": "search",
}

# On intra-thread mode switching/mixing (entries disagree on search_mode), take the highest specificity.
# 线程内模式切换/混合（多条 entry search_mode 不一致）时按特异性取最高。
_MODE_SPECIFICITY = ("computer", "council", "study", "deep-research", "search")


def detect_mode(metadata: dict, idx_thread: dict | None, url: str, turns: list[Turn],
                entries: list[dict] | None = None) -> str:
    """Detect the thread mode: computer / council / deep-research / study / search.

    Signal priority:
    1. entry.search_mode (platform-authoritative field, any() over all entries; mapping
       in SEARCH_MODE_MAP). Multi-value conflicts resolve to the highest specificity
       computer>council>study>deep-research>search with a log.warning; on conflicts
       with downstream signals (step names / display_model), search_mode wins with a
       log.warning.
    2. When search_mode is entirely absent, the original chain applies: URL/metadata
       (computer) and step names (COUNCIL_RESEARCH→council, RESEARCH_ANSWER→
       deep-research) as primary signals, plus any entry's display_model
       (DISPLAY_MODEL_MODE, via any() rather than only entries[0] — the first entry of
       a mixed thread may not represent the whole) as a redundant signal; when the two
       signals conflict, display_model wins with a log.warning.

    识别线程模式：computer / council / deep-research / study / search。

    信号优先级：
    1. entry.search_mode（平台权威字段，any 遍历全部 entries，映射见
       SEARCH_MODE_MAP）。线程内多值冲突按特异性 computer>council>study>
       deep-research>search 取最高并 log.warning；与下游信号（步骤名/
       display_model）冲突时 search_mode 优先并 log.warning。
    2. search_mode 全灭时走原链：URL/元数据（computer）、步骤名
       （COUNCIL_RESEARCH→council、RESEARCH_ANSWER→deep-research）为主信号，
       任一 entry 的 display_model（DISPLAY_MODEL_MODE，any() 遍历而非仅
       entries[0]——混合线程首条未必代表整体）为冗余信号，两信号冲突时以
       display_model 为准并 log.warning。
    """
    m = str((metadata or {}).get("mode", ""))
    gmode = ((idx_thread or {}).get("mode") or "").upper()
    step_mode = ""
    if "/computer/tasks/" in url or m == "4" or gmode in ("ASI", "COMPUTER"):
        step_mode = "computer"
    elif any(s.step_type == "COUNCIL_RESEARCH" for t in turns for s in t.steps):
        step_mode = "council"
    elif any(s.step_type == "RESEARCH_ANSWER" for t in turns for s in t.steps):
        step_mode = "deep-research"
    dm_mode = ""
    sm_modes: set[str] = set()
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        dm = (e.get("display_model") or "")
        if not dm_mode and dm in DISPLAY_MODEL_MODE:
            dm_mode = DISPLAY_MODEL_MODE[dm]
        sm = (e.get("search_mode") or "").upper()
        if sm in SEARCH_MODE_MAP:
            sm_modes.add(SEARCH_MODE_MAP[sm])
    if sm_modes:
        sm_mode = next(x for x in _MODE_SPECIFICITY if x in sm_modes)
        if len(sm_modes) > 1:
            log.warning(f"[normalize] 线程内模式切换：search_mode 命中 {sorted(sm_modes)}，按特异性采 {sm_mode}")
        for sig_name, sig in (("步骤名", step_mode), ("display_model", dm_mode)):
            if sig and sig != sm_mode:
                log.warning(f"[normalize] 模式判别冲突：{sig_name}={sig} vs search_mode={sm_mode}，采 search_mode")
        return sm_mode
    if dm_mode:
        if step_mode and step_mode != dm_mode:
            log.warning(f"[normalize] 模式判别冲突：步骤名={step_mode} vs display_model={dm_mode}，采 display_model")
        return dm_mode
    return step_mode or "search"


def aggregate_search_mode(entries: list[dict] | None) -> str:
    """Thread-level search_mode aggregation (for search-mode-backfill): returns the platform **raw value**.

    entries[].search_mode is mapped via SEARCH_MODE_MAP, then the highest specificity
    computer>council>study>deep-research>search wins (same rule as detect_mode's
    search_mode branch), and one platform raw value corresponding to that top mode
    (e.g. RESEARCH / STUDY / ASI) is written back; for multiple raw values of equal
    specificity, the first seen wins; when nothing matches (missing/unknown values),
    returns "".

    线程级 search_mode 聚合（search-mode-backfill 用）：返回平台**原始值**。

    entries[].search_mode 经 SEARCH_MODE_MAP 映射后按特异性
    computer>council>study>deep-research>search 取最高（与 detect_mode 的
    search_mode 分支同一规则），写回该最高模式对应的一个平台原始值
    （如 RESEARCH / STUDY / ASI）；同特异性多原始值取先见者；全部未命中
    （缺失/未知值）返回 ""。
    """
    best_rank = len(_MODE_SPECIFICITY)
    best_raw = ""
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        sm = (e.get("search_mode") or "").upper()
        mode = SEARCH_MODE_MAP.get(sm)
        if mode is None:
            continue
        r = _MODE_SPECIFICITY.index(mode)
        if r < best_rank:
            best_rank, best_raw = r, sm
    return best_raw


_FENCE_TOKEN_RE = re.compile(r"`{3,}")
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def _split_code_segments(md: str) -> list[tuple[str, bool]]:
    """Split into (segment, is_code) by fence semantics.

    Any 3+ backtick run at any position is a fence boundary (official sources contain
    irregular forms like inline `:```r` openings or ``` immediately followed by
    Chinese, which line-start checks would miss); opening records length N and the
    next boundary of length ≥ N closes it (4+-backtick fences pair correctly, embedded
    ``` does not truncate early). If unclosed, the remainder is treated as code —
    unclosed fences coming from the source itself (raw model output) keep the original
    protective behavior unchanged.

    按围栏语义切分 (segment, is_code)。

    任意位置的 3+ 反引号都是围栏边界（官方源有 `:```r` 行内开围栏、```紧接中文
    等不规范写法，行首判定会漏）；开启记录长度 N，≥N 的下一个边界关闭（4+ 反引号
    围栏正确配对，内嵌 ``` 不会提前截断）。未闭合则余下全部视为代码——源内容自带
    的未闭合围栏（模型原始输出）保持原有保护行为不变。
    """
    segs: list[tuple[str, bool]] = []
    pos = 0
    fence_len = 0
    for m in _FENCE_TOKEN_RE.finditer(md):
        n = len(m.group(0))
        if not fence_len:
            if m.start() > pos:
                segs.append((md[pos:m.start()], False))
            fence_len = n
            pos = m.start()
        elif n >= fence_len:
            segs.append((md[pos:m.end()], True))
            fence_len = 0
            pos = m.end()
    if pos < len(md):
        segs.append((md[pos:], fence_len > 0))
    return segs


def _normalize_math_segment(seg: str) -> str:
    # Empty citation markers \[\] (content-free citation-placeholder residue in
    # official answers): remove first, otherwise the \[...\] rule mis-pairs adjacent
    # markers into a math block (\[\]\[\] → $$ garbage).
    # 空引用标记 \[\]（官方答案里的引文占位残留，无内容）：先移除，
    # 否则 \[...\] 规则会把相邻标记对误匹为数学块（\[\]\[\] → $$ 垃圾）
    seg = re.sub(r"\\\[\\\]", "", seg)
    seg = re.sub(r"\\\[([\s\S]+?)\\\]", lambda m: "$$\n" + m.group(1).strip() + "\n$$", seg)
    seg = re.sub(r"\\\(([\s\S]+?)\\\)", lambda m: "$" + m.group(1).strip() + "$", seg)
    # Mixed residue: \( ... $ (opens with \(, closes with a single $).
    # 混合残留：\( ... $（开 \( 闭单个 $）
    seg = re.sub(r"\\\(([^$\n]+?)\$(?!\$)", lambda m: "$" + m.group(1).strip() + "$", seg)
    # Mixed residue: $ ... \) (opens with $, closes with \)).
    # 混合残留：$ ... \)（开 $ 闭 \)）
    seg = re.sub(r"\$([^$\n]+?)\\\)", lambda m: "$" + m.group(1).strip() + "$", seg)
    # Mixed residue: opens with \( but closes with a full-width right paren.
    # 混合残留：\( ... \）（开 \( 闭全角 ））
    seg = re.sub(r"\\\(([^$\n]+?)\\）", lambda m: "$" + m.group(1).strip() + "$", seg)
    return seg


def _normalize_prose(seg: str) -> str:
    """Prose segment: strip inline code, normalize math delimiters, then splice the inline code back verbatim.

    散文段：剥离行内 code 后做公式规范化，行内 code 原样拼回。
    """
    out, pos = [], 0
    for m in _INLINE_CODE_RE.finditer(seg):
        out.append(_normalize_math_segment(seg[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(_normalize_math_segment(seg[pos:]))
    return "".join(out)


def normalize_math_delims(md: str) -> str:
    r"""Unify the LaTeX delimiters of official markdown to the Markdown-standard $$ / $.

    Handles: \[ \] → $$; \( \) → $; empty citation markers \[\] removed outright;
    and mixed residue from official sources: \( ... $, $ ... \), \( ... \） → $.
    Fenced (including 4+ backticks) / inline code segments are preserved verbatim
    (code may contain real \(...\) text).

    官方 markdown 的 LaTeX 分隔符统一为 Markdown 标准的 $$ / $。

    处理：\[ \] → $$；\( \) → $；空引用标记 \[\] 直接移除；
    以及官方源的混合残留：\( ... $、$ ... \)、\( ... \） → $。
    fenced（含 4+ 反引号）/行内代码段原样保留（代码里可能有真实的 \(...\) 文本）。
    """
    if not md:
        return md
    segs = _split_code_segments(md)
    return "".join(seg if is_code else _normalize_prose(seg)
                   for seg, is_code in segs)


def slugify(title: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^\w一-鿿-]+", "-", (title or "").strip())[:maxlen].strip("-")
    return s or "untitled"


def safe_stem(name: str) -> str:
    return re.sub(r"[^\w一-鿿.-]+", "_", name or "file")


def ts_us_to_iso(us) -> str:
    """Human-readable display format (for render headers): minute precision. For
    machine comparison (the lastUpdated contract) use ts_us_to_iso_full — despite the
    ISO name this is a display format; never use it for idempotency/index comparison.

    人类可读显示格式（渲染头部用）：分钟精度。机器比较（lastUpdated 契约）
    请用 ts_us_to_iso_full——本函数名为 ISO 实为 display，勿用于幂等/索引比较。"""
    from datetime import datetime, timezone
    try:
        return datetime.fromtimestamp(int(us) / 1e6, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return ""


def ts_us_to_iso_full(us) -> str:
    """Microseconds us → true ISO 8601 UTC (second precision, Z suffix): the same
    format family as the platform index updatedAt; serves as the fallback for
    machine-comparison fields such as thread.json.lastUpdated (V5-01).

    微秒 us → 真 ISO 8601 UTC（秒级，Z 后缀）：与平台索引 updatedAt 同族格式，
    供 thread.json.lastUpdated 等机器比较字段兜底使用（V5-01）。"""
    from datetime import datetime, timezone
    try:
        return datetime.fromtimestamp(int(us) / 1e6, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return ""
