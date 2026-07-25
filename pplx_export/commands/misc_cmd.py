"""cmd: relations / schedule — relation graph and incremental planning.

cmd：relations / schedule —— 关系图与增量计划。
"""

from __future__ import annotations

import json
from pathlib import Path

from ..core.logging import get_logger

log = get_logger("cli")


def cmd_relations(out_root: Path):
    """Rebuild the conversation relation graph from exported threads (purely offline,
    zero network).

    Reuses re-render's offline rebuild pipeline (load_archived_conversation) to
    reconstruct turns from raw_entries.json / raw_blocks.json — sub_agents,
    query_source, citations and other signals are filled in along the way, instead of
    stuffing conversation.md into a single-turn shell (a shell has no sub_agents, so
    subagent_of edges would never fire). The computer-mode answer fallback
    (wf_block_answer) backfills turn.answer at this layer for the references scan.
    Threads without raw data degrade to a thread.json + conversation.md shell
    (only same_space / bare-uuid edges can be detected).

    从已导出的线程重建对话关系图（纯离线，零网络）。

    复用 re-render 的离线重建管线（load_archived_conversation）从 raw_entries.json /
    raw_blocks.json 重建 turns——sub_agents、query_source、citations 等信号随之填充，
    不再用 conversation.md 塞单轮壳（壳无 sub_agents，subagent_of 永不触发）。
    computer 的答案兜底（wf_block_answer）在本层回填 turn.answer 供 references 扫描。
    无 raw 的线程退化为 thread.json + conversation.md 壳（仅 same_space/裸 uuid 可判）。
    """
    from ..core.models import Conversation, Turn, Space
    from ..hooks.relations_hook import RelationsHook
    from ..sites.perplexity import parsers
    from ..sites.perplexity.adapter import PerplexityAdapter
    from .rerender_cmd import load_archived_conversation
    hook = RelationsHook(out_root)
    # None-transport: reuse only sub_agents' pure data assembly (reads
    # conv._blocks/_plain, never touches the network)
    # None-transport：仅复用 sub_agents 的纯数据组装（读 conv._blocks/_plain，不触网）
    adapter = PerplexityAdapter(None)
    n = 0
    for tj in sorted(out_root.glob("*/*/*/thread.json")):
        conv = load_archived_conversation(tj.parent)
        if conv is None:
            try:
                d = json.loads(tj.read_text())
            except Exception:
                continue
            conv = Conversation(web_uuid=d.get("web_uuid", ""), psc_uuid=d.get("psc_uuid"),
                                title=d.get("title", ""), mode=d.get("mode", "search"),
                                author=d.get("author", ""))
            if d.get("space"):
                conv.space = Space(uuid=d["space"].get("uuid", ""), title=d["space"].get("title", ""),
                                   slug=d["space"].get("slug", ""))
            # No raw data: read conversation.md for bare-uuid detection in references
            # (legacy behavior fallback)
            # 无 raw：读 conversation.md 供 references 裸 uuid 检测（旧行为兜底）
            cm = tj.parent / "conversation.md"
            if cm.exists():
                conv.turns = [Turn(index=1, query=cm.read_text(errors="replace"), answer="")]
        else:
            # Sub-agent mapping (subagent_of edges; dst is the toolu_X run id)
            # 子代理映射（subagent_of 边；dst 为 toolu_X 运行 id）
            try:
                conv.sub_agents = adapter.sub_agents(conv)
            except Exception as e:
                log.warning(f"[relations] 子代理映射失败 {tj.parent.name}: {e}")
            # Computer answer fallback: extend the references scan surface with the
            # workflow_block-side answer
            # computer 答案兜底：references 扫描面补 workflow_block 侧答案
            for t in conv.turns:
                if not t.answer and t.wf_block:
                    t.answer = parsers.wf_block_answer(t.wf_block)
        hook.add(conv)
        n += 1
    out = hook.flush()
    log.info(f"[relations] {n} 个对话 → {out}")


def cmd_schedule(adapter, account, out_root: Path):
    """Compute the incremental plan and generate the cron snippet.

    计算增量计划并生成 cron 片段。
    """
    from ..hooks.scheduler import SchedulerHook
    sch = SchedulerHook(out_root / "index")
    plan = sch.plan(account, adapter)
    log.info(f"[schedule] 总 {plan['total']} 线程：新增 {plan['new']}、更新 {plan['updated']}")
    p = sch.write_cron_snippet(account, out_root)
    log.info(f"[schedule] cron 片段已写: {p}")
