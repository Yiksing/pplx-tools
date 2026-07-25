"""cmd: re-render — offline re-rendering of conversation.md and turns/ from raw JSON
(zero network).

Used to regenerate archives after renderer fixes (answer extraction, math delimiter
normalization, etc.); sources, assets, report.md and other files are left untouched;
thread.json is untouched by default, and with --thread-json only the interruptions /
answer_variants keys are added or removed in place (written only when content
changes).
(Formerly tools/re_render_conversation.py, absorbed here; stray prints funneled into
the central logger.)

cmd：re-render —— 从 raw JSON 离线重渲 conversation.md 与 turns/（零网络）。

用于渲染层修复后的归档再生（答案提取、公式分隔符规范化等），不动 sources、
assets、report.md 等其他文件；thread.json 默认不动，--thread-json 时仅就地
增删 interruptions / answer_variants 键（内容有变才写盘）。
（原 tools/re_render_conversation.py 收编；stray print 收敛到中央 logger。）
"""

from __future__ import annotations

import json
from pathlib import Path

from ..core.logging import get_logger
from ..core.models import Conversation
from ..sites.perplexity import parsers, variant_log
from ..sites.perplexity.adapter import PerplexityAdapter
from ..sites.perplexity.render import render_conversation, render_turn

log = get_logger("cli")


def load_archived_conversation(thread_dir: Path) -> Conversation | None:
    """Rebuild a Conversation offline from thread.json + raw_entries.json /
    raw_blocks.json (zero network, no writes).

    The offline rebuild pipeline shared by re-render and relations: turn parsing /
    sorting by created_us / numbering, _plain/_blocks attachment, and conv.citations
    aggregation (same implementation as export); computer/council additionally attach
    workflow_block, subagent_result stub-turn association, and the unconsumed-
    background appendix.
    Returns None when raw_entries.json is missing (the caller degrades on its own).

    从 thread.json + raw_entries.json/raw_blocks.json 离线重建 Conversation（零网络，不写盘）。

    re-render 与 relations 共用的离线重建管线：turns 解析/按 created_us 排序/编号、
    _plain/_blocks 挂载、conv.citations 汇总（与 export 同实现）；computer/council
    额外挂 workflow_block、subagent_result 桩轮关联与未消费后台附录。
    无 raw_entries.json 返回 None（调用方自行降级）。
    """
    thread_dir = Path(thread_dir)
    re_path = thread_dir / "raw_entries.json"
    if not re_path.exists():
        return None
    doc = json.loads(re_path.read_text())
    turns = [parsers.parse_turn(e, i + 1) for i, e in enumerate(doc.get("entries") or [])]
    turns = sorted(turns, key=lambda t: parsers.to_int(t.created_us))
    for i, t in enumerate(turns, 1):
        t.index = i
    tj = {}
    tjp = thread_dir / "thread.json"
    if tjp.exists():
        tj = json.loads(tjp.read_text())
    conv = Conversation(
        web_uuid=tj.get("web_uuid", ""), psc_uuid=tj.get("psc_uuid"),
        title=tj.get("title", ""), mode=tj.get("mode", "search"),
        author=tj.get("author", ""), turns=turns,
        metadata=doc.get("thread_metadata") or {},
    )
    if tj.get("space"):
        from ..core.models import Space
        conv.space = Space(uuid=tj["space"].get("uuid", ""), title=tj["space"].get("title", ""),
                           slug=tj["space"].get("slug", ""))
    # Citation aggregation: shares the dedup implementation with the export path
    # (adapter), so the "引文: N" header in conversation.md matches sources.json.count (N-03)
    # 引文汇总：与 export 路径（adapter）共用同一去重实现，
    # 保证 conversation.md 头「引文: N」与 sources.json.count 一致（N-03）
    conv.citations = parsers.dedup_citations(turns)
    # Rewritten-answer variant registration: same implementation as
    # adapter.get_thread (the data source of thread.json.answer_variants)
    # 答案重写变体登记：与 adapter.get_thread 同实现（thread.json.answer_variants 数据源）
    conv.answer_variants = parsers.collect_answer_variants(doc.get("entries"))
    # Restore blocks/plain offline: the workflow_block for computer mode and the
    # sub-agent mapping (sub_agents never touches the network — the adapter is built
    # in None-transport mode, reusing only its pure data assembly methods)
    # 离线还原 blocks/plain：computer 的 workflow_block 与子代理映射（sub_agents 不触网，
    # adapter 以 None-transport 模式构造，仅复用其纯数据组装方法）
    conv._plain = doc
    rb_path = thread_dir / "raw_blocks.json"
    conv._blocks = json.loads(rb_path.read_text()) if rb_path.exists() else None
    if conv.mode in ("computer", "council") and conv._blocks:
        parsers.attach_workflow_blocks(turns, conv._blocks)
        # Time-based association between subagent_result stub turns and background
        # sub-agent records (rendered as sub-agent blocks)
        # subagent_result 桩轮 ↔ 后台子代理记录的时间关联（渲染为子代理块）
        parsers.attach_stub_workflows(turns, conv._blocks)
        # Third level of the attribution waterfall: unconsumed background payloads ->
        # appendix at the end of conversation.md
        # 归属瀑布第三级：未消费的后台负载 → conversation.md 末尾附录
        conv.unconsumed_bgs = parsers.collect_unconsumed_background(turns, conv._blocks)
    return conv


def rerender(thread_dir: Path, update_thread_json: bool = False,
             out_root: Path | None = None) -> bool:
    """Re-render a single thread directory; returns False when raw_entries.json is
    missing.
    With update_thread_json=True, the thread.json interruptions / answer_variants
    keys are added or removed in place (written only when content changes); newly
    added or changed answer_variants registrations raise a warning
    (ANSWER_VARIANT_DETECTED) and are appended to index/answer_variants_log.jsonl —
    idempotent reruns do not spam.

    重渲单个线程目录；无 raw_entries.json 返回 False。
    update_thread_json=True 时就地增删 thread.json.interruptions / answer_variants
    （内容有变才写）；answer_variants 登记新增/变化时告警（ANSWER_VARIANT_DETECTED）
    + 追加 index/answer_variants_log.jsonl，幂等重跑不刷屏。
    """
    thread_dir = Path(thread_dir)
    # Archive root: prefer the caller-supplied value, otherwise walk three levels up
    # per the layout <out>/<account>/<mode>/<thread dir>
    # 归档根：优先调用方传入，否则按布局 <out>/<账户>/<模式>/<线程目录> 上推三级
    out_root = Path(out_root) if out_root else thread_dir.parent.parent.parent
    re_path = thread_dir / "raw_entries.json"
    cm_path = thread_dir / "conversation.md"
    if not re_path.exists():
        return False
    conv = load_archived_conversation(thread_dir)
    turns = conv.turns
    tj = {}
    tjp = thread_dir / "thread.json"
    if tjp.exists():
        tj = json.loads(tjp.read_text())
    sub_map = {}
    if conv._blocks:
        try:
            sub_map = {s.sub_id: s for s in PerplexityAdapter(None).sub_agents(conv)}
        except Exception as e:
            log.warning(f"[re-render] 子代理映射失败 {thread_dir.name}: {e}")
    if update_thread_json and tjp.exists():
        # Add/remove thread.json interruptions / answer_variants in place
        # (write_thread writes these two keys only during real exports); all other
        # fields are kept as-is (round-trip with indent=1 verified byte-identical);
        # no write when content is unchanged, avoiding mtime/diff noise in unrelated
        # threads.
        # 就地增删 thread.json.interruptions / answer_variants（write_thread 只在真实
        # 导出时写这两个键）：其余字段原样（round-trip indent=1 已验证字节一致）；
        # 内容无变化不写盘，避免无关线程产生 mtime/diff 噪音。
        inters = parsers.collect_interruptions(conv, sub_map)
        if inters:
            tj["interruptions"] = inters
        else:
            tj.pop("interruptions", None)
        old_variants = tj.get("answer_variants")
        if conv.answer_variants:
            tj["answer_variants"] = conv.answer_variants
        else:
            tj.pop("answer_variants", None)
        # Offline path: warn + centrally register only when registrations are added
        # or changed (idempotent reruns do not spam)
        # 离线路径：仅登记内容新增/变化时告警 + 集中登记（幂等重跑不刷屏）
        if conv.answer_variants and conv.answer_variants != old_variants:
            variant_log.warn_detections(conv.web_uuid, conv.title, conv.answer_variants)
            variant_log.append_registry(out_root, conv.web_uuid, conv.title,
                                        conv.answer_variants, source="offline")
        new_tj = json.dumps(tj, ensure_ascii=False, indent=1)
        if tjp.read_text() != new_tj:
            tjp.write_text(new_tj)
    cm_path.write_text(render_conversation(conv, sub_map))
    turns_dir = thread_dir / "turns"
    turns_dir.mkdir(exist_ok=True)
    # N-12 fix: delete stale turn_*.md files numbered above the current turn count
    # (left over when the turn count shrinks).
    # Only high-numbered leftovers are deleted, not the whole directory — unchanged
    # files keep their mtime, reducing diff noise.
    # N-12 修复：删除编号高于当前轮数的旧 turn_*.md（轮数缩减时残留）。
    # 只删高编号残留、不清空整个目录——保留未变文件的 mtime，减少 diff 噪音。
    for p in turns_dir.glob("turn_*.md"):
        try:
            stale = int(p.stem[5:]) > len(turns)
        except ValueError:
            # Leave files with non-numeric numbering untouched
            # 非数字编号文件不动
            continue
        if stale:
            p.unlink()
    for t in turns:
        (turns_dir / f"turn_{t.index:04d}.md").write_text(render_turn(t, conv.mode, sub_map))
    return True


def cmd_rerender(out_root: Path, limit, dry_run: bool = False, update_thread_json: bool = False):
    """Offline re-render of all thread directories (--limit takes the first N,
    --dry-run only lists directories without writing files).

    离线重渲全部线程目录（--limit 取前 N 个，--dry-run 只列目录不写文件）。
    """
    dirs = sorted({p.parent for p in out_root.glob("*/*/*/raw_entries.json")})
    if limit:
        dirs = dirs[:limit]
    done = skipped = 0
    for d in dirs:
        if dry_run:
            log.info(f"[re-render][dry] {d}")
            continue
        if rerender(d, update_thread_json=update_thread_json, out_root=out_root):
            done += 1
        else:
            skipped += 1
    log.info(f"[re-render] 重渲 conversation.md + turns/: {done} 个线程（跳过 {skipped}）"
             + ("，已同步 thread.json.interruptions" if update_thread_json else ""))
