"""pplx-ask CLI: interactively query Perplexity (ask / models / mark-read / space-create).

Shares core with pplx-export (transport/cookies/state/logging/registry).
SSE streaming ask, auto-archiving, BOT space placement, read receipts — all verified
against the live API (docs/reference/api/api-rest-endpoints.md §3.9).

pplx-ask CLI：交互式查询 Perplexity（ask / models / mark-read / space-create）。

与 pplx-export 共享 core（transport/cookies/state/logging/registry）。
SSE 流式发问、自动归档、BOT 空间归属、已读回执——均经实测（docs/reference/api/api-rest-endpoints.md §3.9）。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
from pathlib import Path

from . import config as _cfg
from .commands.common import (add_common_args, make_transport,
                              resolve_cli_account, resolve_log_file, resolve_out_root)
from .commands.export_cmd import cmd_export
from .sites.perplexity.ask_api import (API_VERSION, COUNCIL_DEFAULT_MODELS, MODE_MODEL,
                                       MODELS_CONFIG_URL, build_envelope, create_space,
                                       fetch_models_config, mark_read, move_threads,
                                       refresh_models, send_view_telemetry, sse_ask)
from .sites.perplexity import platform as _plat
from .core.logging import get_logger, setup_logging
from .core.registry import get_adapter
from .sites.perplexity.fs_writer import FilesystemWriter

log = get_logger("ask-cli")


def _step_best_effort(name: str, fn) -> tuple[bool, str | None]:
    """Run non-core post-processing (move to BOT / read receipt / view telemetry):
    on failure, log a warning and return (False, error string); never block subsequent
    steps or auto-archiving (V4-05).

    执行非核心后处理（移入 BOT/已读回执/阅读遥测）：失败记 warning 并返回 (False, 错误串)，
    绝不阻断后续步骤与自动归档（V4-05）。"""
    try:
        fn()
        return True, None
    except Exception as e:
        log.warning(f"[ask] {name} 失败（best-effort，不影响归档）: {type(e).__name__}: {e}")
        return False, f"{type(e).__name__}: {e}"


def cmd_models(transport, *, refresh: bool = False, config_path=None):
    """List the full model table and per-mode defaults from models/config/v2;
    with refresh=True, also persist them into config.toml's [models] table.

    列出 models/config/v2 的模型总表与模式默认值；refresh=True 时并写入 config.toml 的 [models]。"""
    j = fetch_models_config(transport)
    models = j.get("models") or {}
    defaults = j.get("default_models") or {}
    council = j.get("agentic_research_compare_models") or []
    log.info("== 模式默认模型 ==")
    for m, mid in defaults.items():
        log.info(f"  {m:20} {mid}")
    log.info(f"== 委员会默认三模型 ==\n  {', '.join(council)}")
    log.info("== 可选模型（mode=search，搜索模式单选）==")
    for k, v in models.items():
        if v.get("mode") == "search":
            log.info(f"  {k:28} {v.get('label', ''):28} {v.get('provider', '')}")
    log.info("== 特殊模式（不可多选）==")
    for k, v in models.items():
        if v.get("mode") in ("research", "study", "agentic_research", "studio"):
            log.info(f"  {k:28} {v.get('label', ''):28} mode={v.get('mode')}")
    if refresh:
        if not config_path:
            raise SystemExit("[models][ERROR] 未加载用户级配置文件，无法写入 [models]——"
                             "请先 `pplx-export init` 或创建 config.toml 后重试")
        section = refresh_models(transport, config_path, raw=j)
        log.info(f"[models] 已刷新并写入 {config_path}"
                 f"（last_refreshed={section['last_refreshed']}，目录 {len(section['catalog'])} 个模型）")


def _resolve_space_uuid(adapter, slug_or_title: str) -> str:
    meta = adapter.get_space_meta(slug_or_title)
    # Fall back to list_user_collections when get_space_meta carries no uuid field
    # get_space_meta 未带 uuid 字段时退 list_user_collections
    if meta.get("uuid"):
        return meta["uuid"]
    j = adapter.transport.get_json("https://www.perplexity.ai/rest/collections/get_collection"
                                   f"?collection_slug={slug_or_title}&version={API_VERSION}&source=default",
                                   timeout=30)
    return j.get("uuid") or ""


def _models_days_old() -> float | None:
    """Days since config.toml [models].last_refreshed; None when missing/unparseable.

    距 config.toml [models].last_refreshed 的天数；缺失/无法解析时 None。
    """
    lr = _cfg.MODEL_CONFIG.get("last_refreshed")
    if not lr:
        return None
    try:
        import datetime as _dt
        t = _dt.datetime.strptime(lr, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
        return (_dt.datetime.now(_dt.timezone.utc) - t).total_seconds() / 86400.0
    except Exception:
        return None


def _maybe_refresh_models(transport) -> None:
    """7-day TTL: when a config file is loaded and its [models] snapshot is missing or
    stale, either auto-refresh (auto_refresh=true) or warn. No network in the default
    (warn) path; no-op in degraded mode (no config file → pinned fallback is used).

    7 天 TTL：已加载配置且 [models] 缺失/过期时，auto_refresh=true 则自动刷新，否则提醒。
    默认（提醒）路径不联网；降级（无配置）时空操作，直接用钉死兜底。
    """
    path = _cfg.LOADED_CONFIG_PATH
    if not path:
        return
    days = _models_days_old()
    if days is not None and days < _plat.MODELS_REFRESH_TTL_DAYS:
        return
    age = "尚无 [models] 缓存" if days is None else f"已 {days:.0f} 天未刷新"
    if _cfg.MODEL_CONFIG.get("auto_refresh"):
        log.info(f"[models] {age}，auto_refresh 已开——自动刷新中…")
        try:
            refresh_models(transport, path)
        except Exception as e:
            log.warning(f"[models] 自动刷新失败（继续用现值/兜底）: {e}")
    else:
        log.warning(f"[models] 模型表{age}（TTL {_plat.MODELS_REFRESH_TTL_DAYS} 天）——"
                    f"建议 `pplx-ask models --refresh`；或在 config.toml 的 [models] "
                    f"设 auto_refresh=true 自动刷新")


def cmd_ask(args, account, transport, writer, out_root: Path):
    _maybe_refresh_models(transport)
    adapter = get_adapter("perplexity", transport=transport)
    target_uuid = None
    if args.space and args.space != "home":
        target_uuid = _resolve_space_uuid(adapter, args.space)
        if not target_uuid:
            raise SystemExit(f"[ERROR] 空间 {args.space} 解析失败")
        log.info(f"[ask] 创建于空间 {args.space}（{target_uuid[:8]}），完成后移入 BOT")
    models = args.models.split(",") if args.models else None
    try:
        envelope = build_envelope(args.prompt, args.mode, models, target_uuid)
    except ValueError as e:
        raise SystemExit(f"[ERROR] {e}")
    mp = envelope["params"].get("model_preference")
    cmp = envelope["params"].get("compare_model_preferences")
    log.info(f"[ask] 模式={args.mode} model_preference={mp}" + (f" council={cmp}" if cmp else ""))

    state: dict = {}
    t0 = time.time()

    def on_event(ev: dict):
        if ev.get("backend_uuid") and not state.get("uuid"):
            state["uuid"] = ev["backend_uuid"]
            state["entry_uuid"] = ev.get("uuid") or ""
            state["frontend_context_uuid"] = ev.get("frontend_context_uuid") or ""
            log.info(f"[ask] 线程已创建: https://www.perplexity.ai/search/{ev['backend_uuid']}")
        st = ev.get("status")
        if st and st != state.get("status"):
            state["status"] = st
            log.info(f"[ask] {time.time() - t0:5.1f}s 状态: {st}")
        txt = ev.get("text") or ""
        if txt and len(txt) - state.get("txtlen", 0) > 200:
            state["txtlen"] = len(txt)
            log.info(f"[ask] {time.time() - t0:5.1f}s 生成中… {len(txt)} 字符")

    try:
        last = sse_ask(transport, envelope, on_event=on_event, timeout=args.timeout)
    except urllib.error.HTTPError as e:
        hint = {401: "鉴权失败：cookie 可能已失效，请更新 cookie",
                403: "鉴权失败：cookie 失效或被风控，请更新 cookie",
                429: "触发限流，请稍后重试"}.get(
                    e.code, "服务端错误，请稍后重试" if 500 <= e.code < 600 else "请重试")
        raise SystemExit(f"[ask][ERROR] SSE 请求失败 HTTP {e.code}：{hint}") from e
    except Exception as e:
        raise SystemExit(f"[ask][ERROR] SSE 请求失败: {type(e).__name__}: {e}") from e
    backend_uuid = state.get("uuid") or last.get("backend_uuid") or ""
    ctx = last.get("context_uuid") or ""
    final_status = state.get("status") or last.get("status") or ""
    if final_status != "COMPLETED":
        # Stream ended abnormally: do not move space, send telemetry, or export — avoid leaking half-finished state
        # 流异常结束：不移动空间、不发遥测、不导出，避免半成品状态外泄
        raise SystemExit(
            f"[ask][ERROR] 流异常结束（最终状态: {final_status or '未知'}），已中止后续动作"
            f"（不移入 BOT 空间、不发遥测、不导出）。"
            + (f"线程: https://www.perplexity.ai/search/{backend_uuid}" if backend_uuid else ""))
    log.info(f"[ask] 完成（{time.time() - t0:.0f}s）: {backend_uuid}")

    # Non-core post-processing steps are isolated as best-effort: any failure only logs a
    # warning, and archiving proceeds as usual (V4-05).
    # The JSON contract keeps boolean keys (true=executed and succeeded, false=not executed
    # or failed — compatible with the original `moved is not None` semantics; a failure must
    # never be represented by a truthy structure, or boolean consumers would misread it as success);
    # failure details are listed separately in step_errors (only failed steps appear).
    # 非核心后处理逐项隔离为 best-effort：任一失败只记 warning，归档照常执行（V4-05）。
    # JSON 契约保持布尔键（true=执行且成功，false=未执行或失败，与原 `moved is not None`
    # 语义兼容——失败绝不能用 truthy 结构表示，否则布尔消费方会误判成功）；
    # 失败详情单列 step_errors（仅失败步骤出现）。
    steps: dict = {"moved_to_bot": False, "mark_read": False, "telemetry": False}
    step_errors: dict = {}

    if ctx and _cfg.BOT_SPACE_UUID and target_uuid != _cfg.BOT_SPACE_UUID:
        def _move():
            r = move_threads(transport, [ctx], _cfg.BOT_SPACE_UUID)
            log.info(f"[ask] 已移入 BOT 空间: {json.dumps(r, ensure_ascii=False)[:100]}")
        ok, err = _step_best_effort("移入 BOT 空间", _move)
        steps["moved_to_bot"] = ok
        if err:
            step_errors["moved_to_bot"] = err

    if args.mark_read and ctx:
        def _mark():
            r = mark_read(transport, ctx, account.username, f"/search/{backend_uuid}")
            log.info(f"[ask] 已读回执: {json.dumps(r, ensure_ascii=False)[:100]}")
        ok, err = _step_best_effort("已读回执", _mark)
        steps["mark_read"] = ok
        if err:
            step_errors["mark_read"] = err

    # Human-like view telemetry (on by default; --no-telemetry disables): mimics real browsing timing
    # 人性化阅读遥测（默认开；--no-telemetry 关闭）：模拟真实浏览时序
    if not args.no_telemetry and ctx:
        def _telemetry():
            send_view_telemetry(transport, context_uuid=ctx,
                                account_username=account.username,
                                thread_path=f"/search/{backend_uuid}",
                                entry_uuid=state.get("entry_uuid") or "",
                                frontend_context_uuid=state.get("frontend_context_uuid") or "")
        ok, err = _step_best_effort("阅读遥测", _telemetry)
        steps["telemetry"] = ok
        if err:
            step_errors["telemetry"] = err

    exported = None
    if not args.no_export and backend_uuid:
        # Archiving is a core step: failures propagate as-is, never swallowed
        # 归档为核心步骤：失败如实向上抛出，不吞异常
        cmd_export(adapter, writer, backend_uuid, account, True, out_root)
        exported = "见上方 [export] 输出"
    print(json.dumps({"thread_uuid": backend_uuid,
                      "thread_url": f"https://www.perplexity.ai/search/{backend_uuid}",
                      "context_uuid": ctx, **steps, "step_errors": step_errors,
                      "exported": exported},
                     ensure_ascii=False))


def cmd_mark_read(args, account, transport):
    import re
    m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", args.target)
    if not m:
        raise SystemExit(f"[ERROR] 无法解析 UUID: {args.target}")
    uuid = m.group(1)
    th = transport.get_json(f"https://www.perplexity.ai/rest/thread/{uuid}"
                            f"?version={API_VERSION}&source=default", timeout=30)
    entries = th.get("entries") or []
    ctx = (entries[0].get("context_uuid") if entries else None) or uuid
    r = mark_read(transport, ctx, account.username, f"/search/{uuid}")
    print(json.dumps({"uuid": uuid, "context_uuid": ctx, "result": r}, ensure_ascii=False))


def cmd_space_create(args, transport):
    r = create_space(transport, args.title, args.description or "")
    print(json.dumps({"uuid": r.get("uuid"), "slug": r.get("slug"), "url": r.get("url")},
                     ensure_ascii=False))


def main():
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    ap = argparse.ArgumentParser(
        prog="pplx-ask",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="交互式查询 Perplexity（SSE 流式问答 + 自动归档 + BOT 空间 + 已读回执）",
        epilog="""示例:
  pplx-ask models                                  列出各模式可选模型
  pplx-ask ask "示例提问：某参数的时间分辨率？"      搜索模式发问（默认）
  pplx-ask ask "<长 prompt>" --mode council        模型委员会（默认三模型）
  pplx-ask ask "<prompt>" --mode council --models gpt55_thinking,claude48opusthinking
  pplx-ask ask "<prompt>" --mode deep-research     深度研究（固定 pplx_alpha）
  pplx-ask ask "<prompt>" --space my-research-xxx  在该空间创建，完成后移入 BOT
  pplx-ask ask "<prompt>" --mark-read              完成后发已读回执
  pplx-ask mark-read <thread_url|uuid>             单独发已读回执
  pplx-ask space-create "我的空间"                 创建空间

流程：SSE 流式发问 → 自动移入 BOT 空间 → 人性化阅读遥测 → 自动归档到 web_archive。
末尾输出机器可读 JSON（thread_url/context_uuid/归档路径），供其他 agent 消费。
""")
    add_common_args(ap)
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="<cmd>")

    p_models = sub.add_parser("models", help="列出各模式可选模型（models/config/v2 权威模型总表）")
    p_models.add_argument("--refresh", action="store_true",
                          help="把拉取到的模型目录写入 config.toml 的 [models] 表（含 last_refreshed，供离线/请求复用）")

    p_ask = sub.add_parser("ask", help="发问（SSE 流式，自动归档+BOT 空间+人性化遥测）",
                           description="向 Perplexity 发问：SSE 流式显示进度，完成后自动移入 BOT 空间、"
                                       "发送人性化阅读遥测、复用导出管线自动归档。末尾输出 JSON。")
    p_ask.add_argument("prompt", help="提问内容（长而有意义的 prompt 效果更好）")
    p_ask.add_argument("--mode", default="search",
                       choices=["search", "deep-research", "council", "study"],
                       help="search=普通搜索（可选模型）；deep-research=深度研究（固定模型）；"
                            "council=模型委员会（2-3 模型并行+综合）；study=逐步学习")
    p_ask.add_argument("--models", default=None,
                       help="council：逗号分隔 2-3 个模型 id（默认官方三模型 gpt55_thinking,"
                            "claude48opusthinking,gemini31pro_high）；search：单个模型 id")
    p_ask.add_argument("--space", default="home",
                       help="home=首页创建后移入 BOT；<slug>=在该空间创建后也移入 BOT")
    p_ask.add_argument("--mark-read", action="store_true", help="完成后发已读回执")
    p_ask.add_argument("--no-telemetry", action="store_true",
                       help="不发送人性化阅读遥测（默认发送：pane viewed/thread viewed/entry exited，随机时序）")
    p_ask.add_argument("--no-export", action="store_true", help="不自动归档")
    p_ask.add_argument("--timeout", type=int, default=600, help="SSE 流超时秒数（默认 600）")

    p_mr = sub.add_parser("mark-read", help="给线程发已读回执（mark_viewed，unread 立即翻转）")
    p_mr.add_argument("target", help="线程 URL 或 UUID")

    p_sc = sub.add_parser("space-create", help="创建空间（create_collection）")
    p_sc.add_argument("title")
    p_sc.add_argument("--description", default="")

    args = ap.parse_args()

    try:
        _cfg.configure(args.config)
    except _cfg.ConfigError as e:
        raise SystemExit(f"[config][ERROR] {e}")

    # Resolve the archive root: --out > user-config archive_root > default ./web_archive
    # 归档根解析：--out > 用户配置 archive_root > 默认 ./web_archive
    args.out = resolve_out_root(args.out)

    setup_logging(args.verbose, resolve_log_file(args.log_file, args.out, f"pplx-ask-{args.cmd}"))

    account = resolve_cli_account(args.account)
    transport, _src = make_transport(account, args.cookies_from, args.cookies, "cookie",
                                     out_root=args.out, skip_auth_check=args.skip_auth_check)
    writer = FilesystemWriter(args.out)

    if args.cmd == "models":
        cmd_models(transport, refresh=args.refresh, config_path=_cfg.LOADED_CONFIG_PATH)
    elif args.cmd == "ask":
        cmd_ask(args, account, transport, writer, args.out)
    elif args.cmd == "mark-read":
        cmd_mark_read(args, account, transport)
    elif args.cmd == "space-create":
        cmd_space_create(args, transport)


if __name__ == "__main__":
    main()
