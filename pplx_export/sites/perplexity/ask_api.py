"""Interactive queries: envelope assembly, SSE streaming Q&A, read receipts, space operations.

Moved from core/ask.py into the sites layer (all API shapes here are
Perplexity-specific); shares core (transport/state/logging) with pplx_export and
serves the pplx-ask CLI and other agents. All API shapes were verified against the
live platform (see docs/reference/api/api-rest-endpoints.md §3.9).

交互式查询：envelope 组装、SSE 流式问答、已读回执、空间操作。

由 core/ask.py 迁入 sites 层（全部为 Perplexity 专属 API 形态）；
与 pplx_export 共享 core（transport/state/logging），供 pplx-ask CLI 与其他 agent 调用。
所有 API 形态均经实测（见 docs/reference/api/api-rest-endpoints.md §3.9）。
"""

from __future__ import annotations

import json
import time
import uuid as uuidlib
from typing import Any, Iterator

from ... import config
from ...config import ACCOUNT_UID
from ...core.http.cookie_transport import CookieTransport, UA
from ...core.logging import get_logger
from . import platform as _plat
from .platform import API_VERSION, COUNCIL_DEFAULT_MODELS, MODE_MODEL

log = get_logger("ask")

ASK_URL = "https://www.perplexity.ai/rest/sse/perplexity_ask"
ANALYTICS_URL = "https://www.perplexity.ai/rest/event/analytics"
CREATE_COLLECTION_URL = "https://www.perplexity.ai/rest/collections/create_collection"
MOVE_THREADS_URL = "https://www.perplexity.ai/rest/collections/batch_move_threads"
MARK_VIEWED_URL = "https://www.perplexity.ai/rest/thread/mark_viewed"
MODELS_CONFIG_URL = (f"https://www.perplexity.ai/rest/models/config/v2"
                     f"?version={API_VERSION}&source=default")

# MODE_MODEL / COUNCIL_DEFAULT_MODELS are the pinned fallback baseline; the live
# defaults come from config.toml [models] (see _mode_model / _council_defaults).
# 模型默认的钉死兜底在 platform；线上默认取自 config.toml [models]（见下方解析）。

_BASE_PARAMS: dict[str, Any] = {
    "attachments": [], "language": "zh-CN", "timezone": "Europe/Stockholm",
    "search_focus": "internet", "sources": ["web"],
    "is_related_query": False, "is_sponsored": False,
    "prompt_source": "user", "is_incognito": False,
    "local_search_enabled": False, "use_schematized_api": True,
    "send_back_text_in_streaming_api": False,
    "supported_block_use_cases": list(_plat.SUPPORTED_BLOCK_USE_CASES),
    "client_coordinates": None, "mentions": [], "skip_search_enabled": True,
    "is_nav_suggestions_disabled": False, "source": "default",
    "always_search_override": False, "override_no_search": False,
    "should_ask_for_mcp_tool_confirmation": True, "supports_tool_approval_modal": True,
    "force_enable_browser_agent": False,
    "supported_features": list(_plat.SUPPORTED_FEATURES),
    "version": API_VERSION,
}


def _mode_model(mode: str) -> str:
    """Per-mode model_preference: config.toml [models] (via default_models) override,
    else the pinned platform fallback.

    每模式 model_preference：优先配置（经由 default_models），回退 platform 兜底。
    """
    defaults = config.MODEL_CONFIG.get("default_models") or {}
    # Map API mode name → CLI mode name, then look up the model ID
    # API 模式名 → CLI 模式名，再查 model ID
    for api_mode, cli_mode in _API_MODE_TO_CLI.items():
        if cli_mode == mode and api_mode in defaults:
            return defaults[api_mode]
    return MODE_MODEL[mode]


def _council_defaults() -> list[str]:
    """Council default compare models: config.toml override, else platform fallback.

    委员会默认对比模型：优先 config.toml，回退 platform 兜底。
    """
    return list(config.MODEL_CONFIG.get("council_defaults") or COUNCIL_DEFAULT_MODELS)


def build_envelope(prompt: str, mode: str = "search", models: list[str] | None = None,
                   target_collection_uuid: str | None = None) -> dict:
    """Assemble the perplexity_ask request body (verified parameter template).

    组装 perplexity_ask 请求体（实测参数模板）。
    """
    if mode not in MODE_MODEL:
        raise ValueError(f"未知模式 {mode}（支持 {sorted(MODE_MODEL)}）")
    p = dict(_BASE_PARAMS)
    p["mode"] = "copilot"
    p["query_source"] = "home"
    p["frontend_uuid"] = str(uuidlib.uuid4())
    p["frontend_context_uuid"] = str(uuidlib.uuid4())
    p["time_from_first_type"] = 0.0
    if mode == "council":
        if models is not None and not (2 <= len(models) <= 3):
            raise ValueError(f"council 模式需 2-3 个模型（逗号分隔），收到 {len(models)} 个: "
                             f"{','.join(models)}")
        p["model_preference"] = _mode_model("council")
        p["compare_model_preferences"] = list(models or _council_defaults())[:3]
    elif mode == "search" and models:
        p["model_preference"] = models[0]
    else:
        p["model_preference"] = _mode_model(mode)
    if target_collection_uuid:
        p["target_collection_uuid"] = target_collection_uuid
        p["target_thread_access_level"] = 1
    return {"params": p, "query_str": prompt}


# API mode name (models/config/v2) → our CLI mode name, for default_models mapping.
# API 模式名（models/config/v2）→ 本工具 CLI 模式名，用于 default_models 映射。
_API_MODE_TO_CLI = {
    "search": "search", "pro": "search", "research": "deep-research",
    "deep research": "deep-research", "agentic_research": "council",
    "study": "study", "studio": "study",
}


def fetch_models_config(transport) -> dict:
    """GET /rest/models/config/v2 (raw payload) via the given transport.

    经给定 transport GET /rest/models/config/v2（原始负载）。
    """
    return transport.get_json(MODELS_CONFIG_URL, timeout=30)


def refresh_models(transport, config_path, *, raw: dict | None = None,
                   auto_refresh: bool | None = None) -> dict:
    """Fetch models/config/v2 (or use a pre-fetched `raw`), write the raw response as
    models_cache.json alongside the config, stamp last_refreshed into config.toml's
    [models] table, and update config.MODEL_CONFIG in memory. Returns the loaded section.

    拉取 models/config/v2（或复用已取的 `raw`），把原始响应写入 config 旁的
    models_cache.json，在 config.toml 的 [models] 盖上 last_refreshed，并同步
    内存 config.MODEL_CONFIG。
    """
    raw = raw if raw is not None else fetch_models_config(transport)
    if auto_refresh is None:
        auto_refresh = bool(config.MODEL_CONFIG.get("auto_refresh", False))

    # 1. Write full raw response to models_cache.json (atomic, 0600)
    # 1. 将完整原始响应写入 models_cache.json（原子写入，权限 0600）
    config.write_models_cache(raw)

    # 2. Extract frontend-visible fields into MODEL_CONFIG
    # 2. 提取前端可见字段到 MODEL_CONFIG
    defaults = raw.get("default_models") or {}
    council = raw.get("agentic_research_compare_models") or []
    section = {
        "last_refreshed": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_version": API_VERSION,
        "auto_refresh": auto_refresh,
        "default_models": defaults,
        "council_defaults": list(council) or list(COUNCIL_DEFAULT_MODELS),
        "search_config": raw.get("search_config") or [],
        "computer_config": raw.get("computer_config") or [],
    }

    # 3. Update config.toml [models] with metadata only
    # 3. 仅用元数据更新 config.toml [models]
    config.write_models_section(config_path, {
        "last_refreshed": section["last_refreshed"],
        "source_version": section["source_version"],
        "auto_refresh": section["auto_refresh"],
    })

    # 4. Sync in-memory MODEL_CONFIG
    # 4. 同步内存中的 MODEL_CONFIG
    config.MODEL_CONFIG.clear()
    config.MODEL_CONFIG.update(section)
    return section


def _parse_sse(raw: bytes) -> dict | None:
    data_lines = []
    for ln in raw.decode("utf-8", "replace").splitlines():
        if ln.startswith("data:"):
            data_lines.append(ln[5:].strip())
    if not data_lines:
        return None
    try:
        return json.loads("".join(data_lines))
    except Exception:
        return None


def post_stream(transport: CookieTransport, url: str, payload: dict,
                timeout: int = 600) -> Iterator[dict]:
    """POST and yield SSE data JSON event by event (event: message stream).

    POST 并逐事件产出 SSE data JSON（event: message 流）。
    """
    import urllib.request
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "text/event-stream")
    # Duck-typed transports (test fakes) may lack the new attributes: fall back to
    # the generic module UA and no hints, mirroring the getattr throttle pattern below
    # 鸭型 transport（测试伪对象）可能缺新属性：回退通用模块 UA、无 hints，
    # 与下方 throttle 的 getattr 容错风格一致
    req.add_header("User-Agent", getattr(transport, "_ua", None) or UA)
    for k, v in getattr(transport, "_client_hints", {}).items():
        req.add_header(k, v)
    if transport._cookie_header:
        req.add_header("Cookie", transport._cookie_header)
    import re as _re
    import threading
    _BLANK = _re.compile(rb"\r?\n\r?\n")
    # Idle heartbeat: deep-research/council streams can be silent for minutes (open
    # timeout is 600s), so surface a still-waiting note at default verbosity when no
    # chunk has arrived for an interval. The watchdog only logs; active streaming
    # (frequent chunks) keeps idle low and stays quiet.
    # 空闲心跳：深研/联席流可静默数分钟（open 超时 600s），无 chunk 到达超过一个间隔时
    # 在默认档提示仍在等待。看门狗只打日志；活跃流（频繁 chunk）空闲低，保持安静。
    interval = getattr(getattr(transport, "throttle", None), "heartbeat_interval", 10.0)
    last = [time.monotonic()]
    stop = threading.Event()

    def _beat():
        while not stop.wait(interval):
            idle = time.monotonic() - last[0]
            if idle >= interval:
                try:
                    log.info(f"[ask] 仍在等待响应流…（已空闲 {idle:.0f}s；深研/联席可能持续数分钟）")
                except Exception:
                    pass

    if interval and interval > 0:
        threading.Thread(target=_beat, daemon=True).start()
    try:
        with transport._opener.open(req, timeout=timeout) as r:
            buf = b""
            while True:
                chunk = r.read1(8192) if hasattr(r, "read1") else r.read(8192)
                last[0] = time.monotonic()
                if not chunk:
                    break
                buf += chunk
                while True:
                    # Blank line separating events (\r\n compatible).
                    # 事件分隔空行（兼容 \r\n）
                    m = _BLANK.search(buf)
                    if not m:
                        break
                    raw, buf = buf[:m.start()], buf[m.end():]
                    ev = _parse_sse(raw)
                    if ev is not None:
                        yield ev
            if buf.strip():
                ev = _parse_sse(buf)
                if ev is not None:
                    yield ev
    finally:
        stop.set()


def sse_ask(transport: CookieTransport, envelope: dict,
            on_event=None, timeout: int = 600) -> dict:
    """Streaming ask: per-event callback (on_event(ev)); returns the final event dict.

    流式发问：逐事件回调（on_event(ev)），返回最终事件字典。
    """
    last: dict = {}
    for ev in post_stream(transport, ASK_URL, envelope, timeout=timeout):
        last = ev
        if on_event:
            on_event(ev)
        if ev.get("final_sse_message"):
            break
    return last


def move_threads(transport: CookieTransport, context_uuids: list[str], to_collection_uuid: str) -> dict:
    """batch_move_threads: move threads into the target space (context_uuid dimension).

    batch_move_threads：把线程移入目标空间（context_uuid 维度）。
    """
    return transport.post_json(
        f"{MOVE_THREADS_URL}?version={API_VERSION}&source=default",
        {"context_uuids": context_uuids, "new_collection_uuid": to_collection_uuid}, timeout=30)


def create_space(transport: CookieTransport, title: str, description: str = "") -> dict:
    """create_collection: create a space (verified endpoint and fields).

    create_collection：创建空间（实测端点与字段）。
    """
    return transport.post_json(
        f"{CREATE_COLLECTION_URL}?version={API_VERSION}&source=default",
        {"title": title, "description": description, "emoji": "1f4c1",
         "appearance": None, "instructions": "", "access": 1}, timeout=30)


def mark_read(transport: CookieTransport, context_uuid: str, account_username: str = "",
              thread_path: str = "") -> dict:
    """Read receipt: `POST /rest/thread/mark_viewed` (verified to flip unread; returns {"status":"success"}).

    Note: the analytics "thread viewed" event does **not** flip unread (ruled out by
    repeated tests on 2026-07-21); the real read receipt is this endpoint, whose body
    is a context_uuids list (batch-capable).

    已读回执：`POST /rest/thread/mark_viewed`（实测翻转 unread，返回 {"status":"success"}）。

    注意：analytics 的 "thread viewed" 事件**不翻转** unread（2026-07-21 多次实测排除）；
    真正的已读回执是本端点，body 为 context_uuids 列表（可批量）。
    """
    return transport.post_json(
        f"{MARK_VIEWED_URL}?version={API_VERSION}&source=default",
        {"context_uuids": [context_uuid]}, timeout=30)


# ── Human-like telemetry (mimics real reading behavior) ──────
# ── 人性化遥测（伪装真实阅读行为）──────────────────────────────
_DEVICE_POOL = [
    {"hardwareConcurrency": 10, "architecture": 127, "colorDepth": 30, "screenSize": "1920x1243"},
    {"hardwareConcurrency": 8, "architecture": 127, "colorDepth": 24, "screenSize": "1512x982"},
    {"hardwareConcurrency": 12, "architecture": 127, "colorDepth": 30, "screenSize": "1920x1080"},
]


def _telemetry_event(name: str, data: dict, account_username: str, thread_path: str,
                     device: dict, visitor_id: str) -> dict:
    """Assemble a telemetry event following the real browser schema (matches the verified events in §3.9).

    按浏览器真实 schema 组装遥测事件（与 §3.9 实测事件一致）。
    """
    uid = ACCOUNT_UID.get(account_username, "")
    return {"event_name": name, "event_data": {
        **data, "scopeData": {}, "isStandaloneApp": False,
        "timestamp": int(time.time() * 1000), "isBrowserExtension": False,
        "timeZone": "Europe/Stockholm", "isPro": True, "userId": uid, "orgId": "none",
        "deviceInfo": device, "web_platform": "web"},
        "url": thread_path or "/", "referrer": "", "language": "zh-CN",
        "screen": device.get("screenSize", "1920x1243"), "hostname": "www.perplexity.ai",
        "device_info": device, "is_arc_browser": False, "visitor_id": visitor_id}


def send_view_telemetry(transport: CookieTransport, *, context_uuid: str,
                        account_username: str, thread_path: str = "",
                        entry_uuid: str = "", frontend_context_uuid: str = "",
                        visitor_id: str = "000b814b-530c-4305-9",
                        dwell_ms: tuple[int, int] = (12000, 45000),
                        verbose: bool = True) -> dict:
    """Send reading telemetry (randomized) following real browser timing, mimicking human reading behavior.

    Sequence (as verified): ask context pane viewed → thread viewed → ask context pane
    viewed → thread entry exited (with random timeOnEntryMs). Random 0.6–2.4s pauses
    between events. The device is picked randomly from the device pool. The read
    receipt (mark_viewed) is handled separately by mark_read.

    按真实浏览器时序发送阅读遥测（随机化），伪装人类阅读行为。

    序列（与实测一致）：ask context pane viewed → thread viewed → ask context pane viewed
    → thread entry exited（含随机 timeOnEntryMs）。事件间随机停顿 0.6–2.4s。
    device 从设备池随机选取。已读回执（mark_viewed）由 mark_read 单独负责。
    """
    import random
    uid = ACCOUNT_UID.get(account_username, "")
    device = random.choice(_DEVICE_POOL)
    sent = []

    def fire(name, data, pause):
        ev = _telemetry_event(name, data, account_username, thread_path, device, visitor_id)
        r = transport.post_json(ANALYTICS_URL, ev, timeout=20)
        sent.append(name)
        if verbose:
            log.info(f"[telemetry] {name} → {r.get('accepted_events', '?')}")
        time.sleep(pause)

    fire("ask context pane viewed",
         {"pane_mode": "rail", "is_read_only": False}, random.uniform(0.6, 1.4))
    fire("thread viewed",
         {"authorId": uid, "authorUsername": account_username, "isThreadCreator": True,
          "contextUUID": context_uuid}, random.uniform(0.8, 2.2))
    fire("ask context pane viewed",
         {"pane_mode": "rail", "context_uuid": context_uuid, "is_read_only": False},
         random.uniform(1.0, 2.4))
    if entry_uuid:
        dwell = random.randint(*dwell_ms)
        fire("thread entry exited",
             {"entryUUID": entry_uuid, "frontendContextUUID": frontend_context_uuid,
              "timeOnEntryMs": dwell}, 0)
    return {"sent": sent, "dwell_ms": dwell_ms if entry_uuid else None}
