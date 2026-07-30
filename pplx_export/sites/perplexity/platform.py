"""Perplexity wire-protocol constants — the single source, human-pinned.

⚠ These are coupled to this package's parser/renderer and the platform's request
contract; they are NOT user configuration and are NOT auto-refreshed. When
Perplexity changes its web API (version bump, new block types, new capabilities),
update EVERY constant in the "protocol contract" section below together, and
re-verify parsers.py / render.py and the API reference (docs/reference/api/).
Do not scatter these literals elsewhere — import from here.

VERIFIED: 2026-07-21 against docs/reference/api/api-rest-endpoints.md §3.9
(WebBridge network capture + cookie-direct requests).

Perplexity wire 协议常量——唯一来源，人工钉死。

⚠ 这些与本包 parser/renderer 及平台请求契约强耦合，非用户配置、不自动刷新。
平台 Web API 变更（version、块类型、能力）时，须在同一改动里一并更新下方
「协议契约」区全部常量，并重验 parsers.py / render.py 与 docs/reference/api/。
不要把这些字面量散落别处——一律从此处 import。
"""

from __future__ import annotations

# ── Protocol contract (pinned; bump in lockstep with parser/renderer/wire) ──
# ── 协议契约（钉死；随 parser/renderer/wire 一并升级）──────────────────
API_VERSION = "2.18"

# ask envelope (POST /rest/sse/perplexity_ask body): the full browser-UI block
# capability the client declares it can render. Superset that mirrors real
# browser traffic (§3.9). Declaring more than parsers/render handle risks
# receiving block shapes the archive cannot faithfully render.
# ask 信封（POST body）：客户端声明可渲染的完整浏览器 UI 块能力，镜像真实浏览器流量。
SUPPORTED_BLOCK_USE_CASES = [
    "answer_modes", "media_items", "knowledge_cards", "inline_entity_cards",
    "place_widgets", "finance_widgets", "sports_widgets", "news_widgets",
    "shopping_widgets", "jobs_widgets", "search_result_widgets", "inline_images",
    "inline_assets", "placeholder_cards", "diff_blocks", "inline_knowledge_cards",
    "entity_group_v2", "refinement_filters", "canvas_mode", "maps_preview",
    "answer_tabs", "price_comparison_widgets", "preserve_latex",
    "generic_onboarding_widgets", "in_context_suggestions", "pending_followups",
    "inline_claims", "unified_assets", "workflow_steps", "workflow_widgets",
    "navigation_results", "background_agents",
]

SUPPORTED_FEATURES = ["browser_agent_permission_banner_v1.1"]

# thread read (GET /rest/thread/<uuid>?with_schematized_response=true): the
# narrow schematized set the exporter's parser actually needs — kept in step
# with parsers.py's block handling, deliberately smaller than the ask superset.
# 线程读取（GET）：导出器 parser 真正需要的窄集，与 parsers.py 的块处理同步，
# 刻意小于 ask 超集。
SCHEMATIZED_BLOCK_USE_CASES = [
    "workflow_steps", "unified_assets", "asset_diff_assets", "write_delta",
    "bash_delta", "run_subagent_delta", "background_agents", "markdown",
]


def schematized_query() -> str:
    """Build the repeated-key query fragment for a schematized thread read.

    构造 schematized 线程读取的重复键查询片段。
    """
    return "&".join(f"supported_block_use_cases={u}" for u in SCHEMATIZED_BLOCK_USE_CASES)


# How long a config.toml [models] snapshot is considered fresh before the CLI
# reminds (or, when auto_refresh is enabled, refreshes) it.
# config.toml [models] 快照被视为新鲜的时长；超过则 CLI 提醒（auto_refresh 时自动刷新）。
MODELS_REFRESH_TTL_DAYS = 7

# ── Model fallback baseline (overridden by config.toml [models]; refreshable) ──
# Not a protocol contract: model ids are pure server-side data, decoupled from
# our parser/renderer, so they are safe to refresh. These values are the
# last maintainer-verified defaults and serve as the offline/first-run fallback.
# ── 模型保底基线（被 config.toml [models] 覆盖；可刷新）──────────────
# 非协议契约：模型 id 是纯服务端数据，与 parser/renderer 解耦，可安全刷新。
# 此处为维护者最近核验的默认值，作为离线/首次运行的兜底。
MODE_MODEL = {
    "search": "pplx_pro",
    "deep-research": "pplx_alpha",
    "council": "pplx_agentic_research",
    "study": "pplx_study",
}
# Re-verified 2026-07-30 against /rest/models/config/v2 (council defaults drift often —
# this is the single most volatile fallback; config.toml [models] overrides it).
# 2026-07-30 对 /rest/models/config/v2 重验（委员会默认最易变——本项是最易漂移的兜底；
# config.toml [models] 会覆盖它）。
COUNCIL_DEFAULT_MODELS = ["gpt56_sol_thinking", "claude50opusthinking", "gemini31pro_high"]
