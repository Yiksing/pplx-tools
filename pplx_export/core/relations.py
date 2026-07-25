"""Conversation relation graph: builds relation edges between exported conversations.

Edge types (RelationEdge.kind, **4 currently implemented**):
  same_space      same space (same conversation collection); dst = "space:<slug>"
  same_prompt     **normalized exact equality of first queries** across threads
                  (scheduled-task reruns / manual resends of the same prompt);
                  dst = in-library thread web_uuid
  references      the answer text or citation URLs reference another in-library thread
                  (perplexity.ai/search|thread|computer/tasks/<uuid> links,
                  and bare in-library thread uuids appearing in body text);
                  dst = in-library thread web_uuid
  subagent_of     main thread → sub-agent execution; **dst is the sub-agent run id
                  (toolu_X), not a thread uuid** (sub-agent background threads are
                  usually not archived); in council mode the "sub-agents" are
                  committee model slots, dst is the model slot name (e.g. gpt55_thinking).
                  If a sub-agent background thread happens to be archived too
                  (SubAgent.thread_uuid hits an in-library uuid), evidence notes it,
                  but dst keeps its semantics — no fabricated relation.

same_prompt normalization rules (normalize_query, applied before the equality check):
  1. NFKC compatibility decomposition (full-width → half-width, compatibility chars normalized)
  2. Strip leading/trailing whitespace + casefold case folding
  3. Collapse consecutive whitespace (incl. newlines) into a single space
  4. Strip sentence-final punctuation (Chinese/English stops/question/exclamation/colon/semicolon/ellipsis)
Measured on the full library of 565 archived threads, this rule yields 21 clusters (2026-07-22).

same_prompt edge shape: **chronological chain edges within a cluster by first-query time
(first-turn created_us)** (t1→t2→t3…), not pairwise full connection. Rationale:
scheduled-task clusters can reach 19+ members; full connection is O(k²)
(19 members = 171 edges) and would flood graph.md; chain k-1 edges preserve temporal
semantics (each rerun references the previous one) while avoiding the explosion.
evidence distinguishes two classes:
  perplexity_tasks  both ends' first-query query_source is perplexity_tasks (scheduled-task rerun)
  manual_resend     everything else (manual resend; incl. missing/mixed origin channels)

Not implemented (no corresponding data feed; honestly marked, no filler):
  related_query (platform related-conversation recommendation slot, not collected),
  branch_of (shared-conversation branch, not exposed by the platform),
  continues (in-thread continuation/follow-up, not a cross-thread edge).

Output: web_archive/relations/edges.jsonl + graph.md (human-readable summary).

对话关系图：从已导出的对话中建立对话间关系边。

边类型（RelationEdge.kind，**当前实现产出 4 种**）：
  same_space      同一空间（同一对话集合）；dst = "space:<slug>"
  same_prompt     跨线程**首问归一化全等**（定时任务重跑 / 人工重发同一 prompt）；
                  dst = 库内线程 web_uuid
  references      答案文本或引文 URL 中引用了库内其他线程
                  （perplexity.ai/search|thread|computer/tasks/<uuid> 链接，
                  以及正文中出现的库内线程裸 uuid）；dst = 库内线程 web_uuid
  subagent_of     主线程 → 子代理执行；**dst 是子代理运行 id（toolu_X）而非线程
                  uuid**（子代理后台线程通常不入库）；council 模式的"子代理"是
                  委员会模型槽位，dst 为模型槽位名（如 gpt55_thinking）。
                  若子代理后台线程恰好也已归档（SubAgent.thread_uuid 命中库内
                  uuid），evidence 会附带注明，但 dst 保持原语义，不虚构关联。

same_prompt 归一化规则（normalize_query，全等判定前套用）：
  1. NFKC 兼容分解（全角→半角、兼容字符归一）
  2. 去首尾空白 + casefold 大小写折叠
  3. 连续空白（含换行）折叠为单个空格
  4. 去句末标点（中英句读/问叹/冒号分号/省略号）
实测该规则在全库 565 个已归档线程上得到 21 个簇（2026-07-22）。

same_prompt 边形态：**簇内按首问时间（首 turn created_us）链式连边**
（t1→t2→t3…），而非两两全连接。理由：定时任务簇可达 19+ 成员，全连接
O(k²)（19 成员 = 171 边）会淹没 graph.md；链式 k-1 边既保留时序语义
（每次重跑引用上一次），又避免爆炸。evidence 区分两类：
  perplexity_tasks  边两端首问 query_source 均为 perplexity_tasks（定时任务重跑）
  manual_resend     其余（人工重发；含发起渠道缺失/混合的情况）

未实现（无对应数据接入，如实标注，不凑数）：
  related_query（平台相关对话推荐位，未采集）、branch_of（共享会话分支，
  平台未暴露）、continues（同线程内续接/追问，非跨线程边）。

输出：web_archive/relations/edges.jsonl + graph.md（人读摘要）。
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from .models import Conversation, RelationEdge

# Perplexity thread link shapes: /search/<uuid>, /thread/<uuid>, /computer/tasks/<uuid>
# Perplexity 线程链接形态：/search/<uuid>、/thread/<uuid>、/computer/tasks/<uuid>
_THREAD_LINK_RE = re.compile(
    r"perplexity\.ai/(?:search|thread|computer/tasks)/"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE)
# Bare uuid in body text (may appear in uppercase form, F-17)
# 正文裸 uuid（可能含大写形式，F-17）
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                      re.IGNORECASE)
_TRAILING_PUNCT = " \t.,!?;:。，！？；：…、"

# same_prompt evidence classification
# Scheduled-task rerun
# same_prompt evidence 分类
# 定时任务重跑
EVID_SCHEDULED = "perplexity_tasks"
# Manual resend
# 人工重发
EVID_MANUAL = "manual_resend"


def normalize_query(q: str) -> str:
    """First-query normalization (rules in module docstring); empty/pure-punctuation normalizes to the empty string (excluded from clustering).

    首问归一化（规则见模块 docstring）；空/纯标点归一为空串（不参与聚类）。"""
    q = unicodedata.normalize("NFKC", q or "").strip().casefold()
    q = re.sub(r"\s+", " ", q)
    return q.strip(_TRAILING_PUNCT).strip()


def _first_turn(conv: Conversation):
    """First turn (smallest created_us; the offline rebuild pipeline has sorted and numbered turns, so turns[0] is the first query).

    首 turn（created_us 最小；离线重建管线已排序并编号，turns[0] 即首问）。"""
    return conv.turns[0] if conv.turns else None


def _same_prompt_edges(conversations: list[Conversation]) -> list[RelationEdge]:
    clusters: dict[str, list[Conversation]] = defaultdict(list)
    for c in conversations:
        t = _first_turn(c)
        if t is None:
            continue
        key = normalize_query(t.query)
        if key:
            clusters[key].append(c)
    edges: list[RelationEdge] = []
    for key, members in clusters.items():
        if len(members) < 2:
            continue
        # Chronological chaining: first-query created_us ascending, None→0 fallback, uuid tiebreak for determinism
        # 时序链式：首问 created_us 升序，None→0 兜底，uuid 决胜保证确定性
        members.sort(key=lambda c: ((c.turns[0].created_us or 0), c.web_uuid))
        for prev, nxt in zip(members, members[1:]):
            qs_prev = prev.turns[0].metadata.get("query_source") or ""
            qs_next = nxt.turns[0].metadata.get("query_source") or ""
            cls = (EVID_SCHEDULED if qs_prev == qs_next == "perplexity_tasks"
                   else EVID_MANUAL)
            edges.append(RelationEdge(
                src_uuid=prev.web_uuid, dst_uuid=nxt.web_uuid, kind="same_prompt",
                evidence=f"same first query ({cls}): {key[:80]}"))
    return edges


def _reference_texts(conv: Conversation):
    """references scan surface: each turn's answer text + each turn's/sub-agent's citation URLs (yielded one by one).

    computer answers often live on the workflow_block side (turn.answer empty) — the caller
    (cmd_relations, commands layer) backfills turn.answer via parsers.wf_block_answer before
    passing conversations in; the core layer does not depend back on sites.

    references 扫描面：各轮答案文本 + 各轮/子代理引文 URL（逐一 yield）。

    computer 的答案常在 workflow_block 侧（turn.answer 为空）——调用方
    （cmd_relations，commands 层）在传入前已用 parsers.wf_block_answer 兜底
    回填 turn.answer，core 层不反向依赖 sites。"""
    for t in conv.turns:
        if t.answer:
            yield t.answer
        for cit in t.citations:
            if cit.url:
                yield cit.url
    for sub in conv.sub_agents:
        if sub.answer:
            yield sub.answer
        for cit in sub.sources:
            if cit.url:
                yield cit.url


def _reference_edges(conversations: list[Conversation],
                     by_uuid: dict[str, Conversation]) -> list[RelationEdge]:
    # Aggregate evidence by (src, dst); both signals (link / bare uuid) hitting the same pair yield only one edge
    # 按 (src, dst) 聚合证据，两种信号（链接 / 裸 uuid）命中同一对只出一条边
    found: dict[tuple[str, str], set[str]] = defaultdict(set)
    for c in conversations:
        for text in _reference_texts(c):
            for m in _THREAD_LINK_RE.finditer(text):
                other = m.group(1).lower()
                if other != c.web_uuid and other in by_uuid:
                    found[(c.web_uuid, other)].add("thread link in answer/citation")
        bare_text = "\n".join(t.query + "\n" + t.answer for t in c.turns)
        for other in {u.lower() for u in _UUID_RE.findall(bare_text)}:
            if other != c.web_uuid and other in by_uuid:
                found[(c.web_uuid, other)].add("uuid mentioned in content")
    return [RelationEdge(src_uuid=src, dst_uuid=dst, kind="references",
                         evidence="; ".join(sorted(evs)))
            for (src, dst), evs in sorted(found.items())]


def build_edges(conversations: list[Conversation]) -> list[RelationEdge]:
    edges: list[RelationEdge] = []
    by_uuid = {c.web_uuid: c for c in conversations}
    # same_space: conversations in the same space are associated (recorded against the space instead of fully connected edges, to avoid explosion)
    # same_space：同空间的对话两两关联（记录到空间而非全连边，避免爆炸）
    space_groups: dict[str, list[str]] = defaultdict(list)
    for c in conversations:
        if c.space and c.space.slug:
            space_groups[c.space.slug].append(c.web_uuid)
    for slug, uuids in space_groups.items():
        for u in uuids:
            edges.append(RelationEdge(src_uuid=u, dst_uuid=f"space:{slug}",
                                      kind="same_space", evidence=f"member of {slug}"))
    # same_prompt: normalized first-query exact equality (chronological chain edges)
    # same_prompt：首问归一化全等（时序链式连边）
    edges.extend(_same_prompt_edges(conversations))
    # subagent_of: sub-agent executions of the main thread (dst = toolu_X run id, see module docstring);
    # dual entry points: conversation-level list (filled by cmd_relations offline rebuild) + turn-level list (future pipeline)
    # subagent_of：主线程的子代理执行（dst = toolu_X 运行 id，见模块 docstring）；
    # 会话级列表（cmd_relations 离线重建填充）+ 轮级列表（未来管线）双入口
    for c in conversations:
        subs = list(c.sub_agents)
        for t in c.turns:
            subs.extend(t.sub_agents)
        seen_subs: set[str] = set()
        for sub in subs:
            if not sub.sub_id or sub.sub_id in seen_subs:
                continue
            seen_subs.add(sub.sub_id)
            evidence = sub.headline
            if sub.thread_uuid and sub.thread_uuid in by_uuid:
                note = f"子代理线程已归档: {sub.thread_uuid}"
                evidence = f"{evidence}（{note}）" if evidence else note
            edges.append(RelationEdge(src_uuid=c.web_uuid, dst_uuid=sub.sub_id,
                                      kind="subagent_of", evidence=evidence))
    # references: in-library thread links in answers/citations + bare uuids in body text
    # references：答案/引文中的库内线程链接 + 正文裸 uuid
    edges.extend(_reference_edges(conversations, by_uuid))
    return edges


def write_relations(edges: list[RelationEdge], out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"src": e.src_uuid, "dst": e.dst_uuid, "kind": e.kind, "evidence": e.evidence},
                        ensure_ascii=False) for e in edges]
    (out_dir / "edges.jsonl").write_text("\n".join(lines) + "\n")
    # graph.md summary
    # graph.md 摘要
    by_kind: dict[str, int] = defaultdict(int)
    for e in edges:
        by_kind[e.kind] += 1
    md = ["# 对话关系图", "", f"边数: {len(edges)}", "", "| 关系类型 | 数量 |", "|---|---|"]
    for k, n in sorted(by_kind.items(), key=lambda x: -x[1]):
        md.append(f"| {k} | {n} |")
    # Related conversations per space
    # 每个空间的相关对话
    md += ["", "## 空间共现（same_space）", ""]
    spaces: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        if e.kind == "same_space":
            spaces[e.dst_uuid].append(e.src_uuid)
    for slug, uuids in sorted(spaces.items()):
        md.append(f"- `{slug}`: {len(uuids)} 个对话")
    # same_prompt clusters (chain edges folded back into clusters for display)
    # same_prompt 簇（链式边还原为簇展示）
    md += ["", "## 首问全等簇（same_prompt，时序链式连边）", ""]
    chains: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        if e.kind == "same_prompt":
            chains[e.evidence].append(f"{e.src_uuid[:8]}→{e.dst_uuid[:8]}")
    for ev, links in sorted(chains.items(), key=lambda x: -len(x[1])):
        md.append(f"- {len(links) + 1} 线程 `{ev}`：{'，'.join(links)}")
    # references / subagent_of details
    # references / subagent_of 明细
    md += ["", "## 引用（references）", ""]
    for e in edges:
        if e.kind == "references":
            md.append(f"- `{e.src_uuid[:8]}` → `{e.dst_uuid[:8]}`（{e.evidence}）")
    md += ["", "## 子代理（subagent_of，dst 为 toolu_X 运行 id）", ""]
    for e in edges:
        if e.kind == "subagent_of":
            md.append(f"- `{e.src_uuid[:8]}` → `{e.dst_uuid}`（{e.evidence}）")
    (out_dir / "graph.md").write_text("\n".join(md) + "\n")
    return out_dir
