"""Domain models: dataclasses decoupled from any specific site's JSON structure.

parsers map raw site JSON into these objects; downstream layers (writer/renderer/relations)
depend only on this layer, so site data-structure changes only require parser changes
and do not affect other layers.

领域模型：与具体站点的 JSON 结构解耦的数据类。

parsers 负责把站点原始 JSON 映射为这些对象；下游（writer/renderer/relations）只依赖本层，
站点数据结构变更只需改 parsers，不影响其他层。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..config import ACCOUNT_DISPLAY_NAMES


@dataclass
class Account:
    username: str
    display_name: str = ""
    plan: str = ""

    @property
    def folder(self) -> str:
        return self.display_name or self.username


def author_folder(author_username: str) -> str:
    return ACCOUNT_DISPLAY_NAMES.get(author_username, author_username)


@dataclass
class Space:
    uuid: str = ""
    title: str = ""
    slug: str = ""
    emoji: str = ""
    n_threads: int = 0


@dataclass
class Citation:
    name: str = ""
    url: str = ""
    snippet: str = ""
    timestamp: Optional[str] = None
    category: str = "web"  # web | connector | attachment | ...
    # Which turn it appears in (1-based, optional)
    # 出现于第几轮（1-based，可空）
    turn_index: Optional[int] = None


@dataclass
class Asset:
    uuid: str = ""
    asset_type: str = ""          # DOC_FILE / SLIDES / RESEARCH_REPORT / ASSET_DIFF / ...
    filename: str = ""
    # Signed download URL (optional)
    # 签名下载 URL（可空）
    url: str = ""
    version: str = "v1"
    n_versions: int = 1
    created_at: Optional[str] = None
    final: Optional[bool] = None
    # Relative destination path (filled after download)
    # 相对落点（下载后填）
    downloaded_to: str = ""


@dataclass
class Step:
    step_type: str = ""           # INITIAL_QUERY / ASI_TOOL_INPUT / THOUGHT / SEARCH_WEB / ...
    content: dict = field(default_factory=dict)
    timestamp: str = ""
    tool_name: str = ""
    # workflow_block step title (computer)
    # workflow_block 步骤标题（computer）
    title: str = ""
    icon: str = ""
    step_id: str = ""


@dataclass
class SubAgent:
    # workflow_payload.id (toolu_X)
    # workflow_payload.id（toolu_X）
    sub_id: str = ""
    headline: str = ""
    # Joined from objective_chunks
    # objective_chunks 拼接
    prompt: str = ""
    steps: list[Step] = field(default_factory=list)
    answer: str = ""
    sources: list[Citation] = field(default_factory=list)
    # Real workflow status on the background side (filled by adapter; renderer annotates when not completed)
    # 后台侧真实 workflow status（adapter 填；非完成时渲染加注）
    status: str = ""
    # Interruption reason (spending_limit_exceeded etc., filled by adapter)
    # 中断原因（spending_limit_exceeded 等，adapter 填）
    locked_reason: str = ""
    # web_uuid of the sub-agent's own thread (background entry backend_uuid; optional)
    # 子代理自身线程的 web_uuid（后台 entry backend_uuid；可空）
    thread_uuid: str = ""


@dataclass
class Turn:
    index: int = 0
    uuid: str = ""
    # psc UUID (platform namespace)
    # psc UUID（平台命名空间）
    context_uuid: str = ""
    query: str = ""
    created_us: Optional[int] = None
    updated_us: Optional[int] = None
    author: str = ""
    steps: list[Step] = field(default_factory=list)
    answer: str = ""
    citations: list[Citation] = field(default_factory=list)
    sub_agents: list[SubAgent] = field(default_factory=list)
    # workflow_block for computer/council (attached by adapter)
    # computer/council 的 workflow_block（adapter 挂载）
    wf_block: Optional[dict] = None
    # Background nested workflow_payloads time-correlated to subagent_result stub turns
    # (attached by parsers; rendered as sub-agent blocks)
    # subagent_result 桩轮时间关联到的后台嵌套 workflow_payload（parsers 挂载；渲染为子代理块）
    stub_wfs: list[dict] = field(default_factory=list)
    # Turn-level extra info (report_info/locked_reason/wf_status, filled by parsers)
    # 轮级附加信息（report_info/locked_reason/wf_status，parsers 填）
    metadata: dict = field(default_factory=dict)


@dataclass
class Report:
    title: str = ""
    file_name: str = ""
    # Signed URL (optional)
    # 签名 URL（可空）
    url: str = ""
    content_md: str = ""


@dataclass
class Conversation:
    web_uuid: str = ""
    psc_uuid: Optional[str] = None
    url: str = ""
    title: str = ""
    mode: str = "search"          # search | deep-research | computer
    author: str = ""
    export_via: str = ""
    space: Optional[Space] = None
    last_updated: str = ""
    thread_access: Optional[int] = None
    turns: list[Turn] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    report: Optional[Report] = None
    metadata: dict = field(default_factory=dict)
    exported_at: str = ""
    # Attribution-waterfall level-3 fallback: background nested payloads not attributable to any turn
    # [{wp, locked_reason, updated, bg_uuid}]
    # (attached by parsers.collect_unconsumed_background; rendered by render as the appendix at the end of conversation.md)
    # 归属瀑布第三级兜底：未归入轮次的后台嵌套负载 [{wp, locked_reason, updated, bg_uuid}]
    # （parsers.collect_unconsumed_background 挂载；render 渲染为 conversation.md 末尾附录）
    unconsumed_bgs: list[dict] = field(default_factory=list)
    # Answer-rewrite variant registry (data source of thread.json.answer_variants;
    # extracted by parsers.collect_answer_variants from entries[].side_by_side_metadata with narrowed criteria,
    # attached by adapter.get_thread / offline re-render; empty on no match, writer omits the key — healthy threads show zero diff)
    # 答案重写变体登记（thread.json.answer_variants 数据源；
    # parsers.collect_answer_variants 从 entries[].side_by_side_metadata 收窄判据提取，
    # adapter.get_thread / 离线重渲挂载；无命中为空，writer 不写该键——健康线程零 diff）
    answer_variants: list[dict] = field(default_factory=list)
    # Conversation-level sub-agent run list (filled by adapter.sub_agents when cmd_relations rebuilds offline;
    # the export pipeline does not backfill this field — writer renders with a local sub_map, relations reads here)
    # 会话级子代理运行列表（cmd_relations 离线重建时由 adapter.sub_agents 填充；
    # 导出管线不回填本字段——writer 用局部 sub_map 渲染，relations 读这里）
    sub_agents: list[SubAgent] = field(default_factory=list)
    # Raw JSON fidelity (attached by adapter; writer persists raw_*.json, report/assets/sub_agents read from here)
    # schematized blocks response
    # 原始 JSON 保真（adapter 挂载；writer 落盘 raw_*.json、report/assets/sub_agents 取用）
    # schematized blocks 响应
    _blocks: Optional[dict] = field(default=None, repr=False)
    # plain thread response
    # plain thread 响应
    _plain: Optional[dict] = field(default=None, repr=False)

    @property
    def n_turns(self) -> int:
        return len(self.turns)


@dataclass
class RelationEdge:
    src_uuid: str
    dst_uuid: str
    kind: str                     # same_space/same_prompt/references/subagent_of
    # dst semantics depend on kind: same_space → "space:<slug>"; subagent_of → sub-agent run id
    # (toolu_X, not a thread uuid); same_prompt/references → in-library thread web_uuid
    # dst 语义随 kind 而定：same_space → "space:<slug>"；subagent_of → 子代理运行 id
    # （toolu_X，非线程 uuid）；same_prompt/references → 库内线程 web_uuid
    evidence: str = ""
