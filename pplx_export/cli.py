"""pplx_export CLI: init / index / space-index / export / batch / spaces / sync-space / relations /
status / re-render / schedule / assets-backfill / usage-backfill / search-mode-backfill /
sync-deleted / debug-js.

Command implementations are split into the `commands/` package (common shared layer +
per-command modules); this file holds only the argparse definitions and dispatch.
Usage:
  pplx-export index --account alice
  pplx-export export <thread_url|uuid> [--account alice]
  pplx-export batch --account bob [--limit N] [--mode X] [--full|--force]
  pplx-export <cmd> --help     show subcommand-specific help

pplx_export CLI：init / index / space-index / export / batch / spaces / sync-space / relations /
status / re-render / schedule / assets-backfill / usage-backfill / search-mode-backfill /
sync-deleted / debug-js。

命令实现已拆至 `commands/` 包（common 公共层 + 各 cmd 模块）；本文件仅 argparse 定义与分发。
用法：
  pplx-export index --account alice
  pplx-export export <thread_url|uuid> [--account alice]
  pplx-export batch --account bob [--limit N] [--mode X] [--full|--force]
  pplx-export <cmd> --help     查看子命令专属帮助
"""

from __future__ import annotations

import argparse
import sys

from . import config as _cfg
from .commands.common import (_account, add_common_args, make_transport,
                              resolve_cli_account, resolve_log_file, resolve_out_root)
from .commands.index_cmd import cmd_index
from .commands.export_cmd import cmd_export
from .commands.batch_cmd import cmd_batch
from .commands.spaces_cmd import cmd_space_index, cmd_spaces, cmd_sync_space
from .commands.assets_backfill_cmd import cmd_assets_backfill
from .commands.usage_backfill_cmd import cmd_usage_backfill
from .commands.misc_cmd import cmd_relations, cmd_schedule
from .commands.rerender_cmd import cmd_rerender
from .commands.search_mode_backfill_cmd import cmd_search_mode_backfill
from .commands.sync_deleted_cmd import cmd_sync_deleted
from .commands.init_cmd import cmd_init
from .commands.status_cmd import cmd_status
# Reserved: WebBridge last-resort credential chain (not wired in)
# 预留：WebBridge 兜底凭证链（未接线）
from .core.auth import CredentialProvider  # noqa: F401
from .core.http.bridge_transport import WebBridgeTransport
# Reserved: cookie fallback channel (not wired in)
# 预留：cookie 降级通道（未接线）
from .core.http.fallback import FallbackTransport  # noqa: F401
from .core.logging import get_logger, setup_logging
from .core.registry import get_adapter
from .core.throttle import Throttle
from .sites.perplexity.fs_writer import FilesystemWriter

log = get_logger("cli")


def main():
    # Line buffering: progress output stays visible in real time even when piped or backgrounded
    # 行缓冲：管道/后台运行时进度输出也实时可见
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    from . import __version__

    common = add_common_args(argparse.ArgumentParser(add_help=False),
                             with_site=True, with_transport=True)

    ap = argparse.ArgumentParser(
        prog="pplx-export",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="pplx-export — Perplexity 对话导出与归档工具",
        epilog="""示例:
  pplx-export sync --account alice           高频同步：增量 index + 增量 batch（只关注对话）
  pplx-export sync --account alice --full    全量对账（含删除/空间的兜底前置：全量 index + batch 全扫）
  pplx-export index --account alice          刷新对话列表索引（默认增量，--full 全量重写）
  pplx-export batch --account bob            增量批量导出（早停 + 断点续跑）
  pplx-export batch --account alice --full   全量扫描（定期兜底 / 怀疑档案有缺口）
  pplx-export export <线程URL>               导出单个线程
  pplx-export spaces                         重建空间索引
  pplx-export relations                      重建对话关系图

多账户: cookie 归属与 --account 登记 email 不符时，自动枚举浏览器中的
账户会话令牌完成切换，无需手动操作浏览器。
运行时预算: 网络不稳时单命令可因退避持续数分钟（单次退避封顶 300s）；
默认档即有「退避倒计时/仍在等待响应」心跳，等待≠卡死；多账户请逐账户
依次调用，勿用 && 串联进带超时的外层任务；命令幂等，中断后直接重跑即可
（增量早停跳过已完成部分）。
子命令帮助: pplx-export <cmd> --help
""")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="<cmd>")

    p_init = sub.add_parser("init", parents=[common],
                            help="初始化用户级配置（自动探测账户生成 config.toml）",
                            description="从浏览器 cookie 自动发现账户并生成用户级 config.toml"
                                        "（0600 权限原子写入；已存在需 --force 覆盖）。BOT 空间按标题"
                                        " BOT 匹配，无匹配时 --create-bot-space 实建（对账户的一次写操作）")
    p_init.add_argument("--force", action="store_true",
                        help="覆盖已存在的 config.toml")
    p_init.add_argument("--create-bot-space", nargs="?", const="", default=None, metavar="TITLE",
                        help="无匹配空间时自动创建（账户写操作）；可附标题，省略时取 --bot-title")
    p_init.add_argument("--bot-title", default="BOT", metavar="TITLE",
                        help="BOT 空间标题：用于匹配既有空间，以及 --create-bot-space 创建时命名（默认 BOT）")

    p_idx = sub.add_parser("index", parents=[common],
                           help="刷新账户对话列表索引（默认增量，--full 全量）",
                           description="刷新账户对话列表索引 → index/library_<account>.json。"
                                       "默认增量：按最新翻页，遇到「连续一整页已知且未变」即停，"
                                       "新增/更新行合并进既有库（旧行原样保留）。增量看不到旧线程"
                                       "的远端删除与空间变更——删除以 sync-deleted --online 为准，"
                                       "连续增量次数到阈值会提醒做一次 --full 全量对账。")
    p_idx.add_argument("--full", action="store_true",
                       help="全量翻页并整体重写库（复位增量计数；配合 sync-deleted --online "
                            "可完成删除/空间对账）")

    p_si = sub.add_parser("space-index", parents=[common],
                          help="提取空间「全部」会话列表（默认 REST 直连，浏览器备用）",
                          description="提取某空间「全部」会话列表（含共享成员线程）：默认经"
                                      " list_collection_threads cookie 直连（含 context_uuid）；"
                                      "--transport webbridge 时回退旧浏览器渲染路径")
    p_si.add_argument("target", metavar="SPACE_URL", help="空间页面 URL")

    p_ex = sub.add_parser("export", parents=[common],
                          help="导出单个线程",
                          description="导出单个线程（URL 或 UUID）")
    p_ex.add_argument("target", metavar="THREAD", help="线程 URL 或 UUID")
    p_ex.add_argument("--force", action="store_true", help="lastUpdated 未变也强制重导")

    p_b = sub.add_parser("batch", parents=[common],
                         help="批量导出（增量早停 + 断点续跑）",
                         description="批量导出账户线程。默认增量早停：列表从新到旧，跳过尾部"
                                     "「已导出且未变」的连续段；中断/失败留下的缺口由下次运行"
                                     "自动修复——重跑即补缺，随时中断都安全。")
    p_b.add_argument("--force", action="store_true",
                     help="重导全部线程（expired 平台已清除的终态除外）")
    p_b.add_argument("--full", action="store_true",
                     help="全量扫描（未变线程跳过但不早停）；用于定期兜底或怀疑档案有缺口时")
    p_b.add_argument("--limit", type=int, default=None, metavar="N",
                     help="只处理列表前 N 条（从新到旧）")
    p_b.add_argument("--mode", default=None,
                     choices=["search", "deep-research", "computer", "council", "study"],
                     help="只导出指定模式的线程。索引行有 search_mode（search-mode-backfill "
                          "富化的平台权威字段）时经 SEARCH_MODE_MAP 精确匹配（--mode search "
                          "不再混入 deep-research/council/study）；无 search_mode 的行回落 "
                          "索引字段启发式：computer=Computer 任务（mode=COMPUTER）；"
                          "deep-research=深度研究（displayModel=pplx_alpha）；"
                          "council=委员会（displayModel=pplx_agentic_research）；"
                          "study=学习（displayModel=pplx_study）；"
                          "search=其余搜索线程（索引 mode=SEARCH，含上述三类——"
                          "精确排除请用对应模式单独导）")
    p_b.add_argument("--delay-min", type=float, default=10.0, metavar="SEC",
                     help="线程间随机间隔下限（默认 10）")
    p_b.add_argument("--delay-max", type=float, default=20.0, metavar="SEC",
                     help="线程间随机间隔上限（默认 20）")

    p_sync = sub.add_parser("sync", parents=[common],
                            help="高频同步：增量 index + 增量 batch（只关注对话）",
                            description="高频同步便捷入口：先增量刷新索引，再增量批量导出——"
                                        "默认只关注对话，跳过删除检测与空间刷新（高频导出下最省）。"
                                        "--full 做全量对账（全量 index + batch 全扫）；"
                                        "--check-deleted 附带 sync-deleted --online 标记远端删除；"
                                        "--refresh-spaces 附带 spaces --fetch-meta + sync-space。"
                                        "增量默认下的删除/空间兜底：库文档记录距上次全量的增量次数，"
                                        "到期提醒你跑一次 --full（或 --check-deleted）。")
    p_sync.add_argument("--full", action="store_true",
                        help="全量对账：全量 index + batch 全扫（未变跳过但不早停）")
    p_sync.add_argument("--check-deleted", action="store_true",
                        help="附带 sync-deleted --online：核验并标记远端已删除线程")
    p_sync.add_argument("--refresh-spaces", action="store_true",
                        help="附带 spaces --fetch-meta 与 sync-space：刷新空间归属/元数据")
    p_sync.add_argument("--limit", type=int, default=None, metavar="N",
                        help="batch 只处理列表前 N 条（从新到旧）")
    p_sync.add_argument("--mode", default=None,
                        choices=["search", "deep-research", "computer", "council", "study"],
                        help="只导出指定模式（语义同 batch --mode）")
    p_sync.add_argument("--delay-min", type=float, default=10.0, metavar="SEC",
                        help="线程间随机间隔下限（默认 10）")
    p_sync.add_argument("--delay-max", type=float, default=20.0, metavar="SEC",
                        help="线程间随机间隔上限（默认 20）")

    p_smb = sub.add_parser("search-mode-backfill", parents=[common],
                           help="给 library 索引补 search_mode（本地 raw 优先，联网兜底，幂等）",
                           description="给 index/library_<account>.json 各行补 search_mode 键"
                                       "（存平台原始值；线程内多值按特异性 computer>council>study>"
                                       "deep-research>search 取最高）。本地优先：已归档线程从 "
                                       "raw_entries.json 提取（零网络）；仅本地无 raw 的行联网"
                                       "兜底（GET /rest/thread/<uuid>，10–20s 随机间隔）；"
                                       "batch_state 中 expired 终态线程跳过并如实记录。"
                                       "幂等可续跑；index 刷新自动保留本命令的富化结果")
    p_smb.add_argument("--limit", type=int, default=None, metavar="N",
                       help="只处理前 N 条待补行")
    p_smb.add_argument("--offline", action="store_true",
                       help="只做本地提取：本地无 raw 的行留待下轮，不联网兜底")
    p_smb.add_argument("--delay-min", type=float, default=10.0, metavar="SEC",
                       help="联网兜底线程间随机间隔下限（默认 10）")
    p_smb.add_argument("--delay-max", type=float, default=20.0, metavar="SEC",
                       help="联网兜底线程间随机间隔上限（默认 20）")

    p_sd = sub.add_parser("sync-deleted", parents=[common],
                          help="识别远端已删除线程并打标记（默认离线 dry-run 只列候选）",
                          description="识别「远端已删除」线程：batch_state 中 ok 的线程在所有"
                                      " index/library_*.json 账户索引并集中均消失 → 候选（任一索引"
                                      "含有即存活——跨账户导出线程只出现在所有者账户索引里）。"
                                      "默认离线 dry-run 只列候选（零网络、不改任何文件）；--online "
                                      "逐候选 GET /rest/thread/<uuid> 验证（ENTRY_DELETED/ENTRY_EXPIRED/"
                                      "404 → 确认，账户取 thread.json export_via），"
                                      "确认的标记 batch_state 终态 deleted（与 expired 并列，终态不重试、"
                                      "--force 也不重导）并给 thread.json 就地加 remote_deleted 时间戳"
                                      "（幂等）。本地归档保留原则：绝不删除/移动任何归档文件，只打标记")
    p_sd.add_argument("--online", action="store_true",
                      help="在线验证候选（默认离线 dry-run 只列候选）")
    p_sd.add_argument("--limit", type=int, default=None, metavar="N",
                      help="只处理前 N 条候选")
    p_sd.add_argument("--delay-min", type=float, default=10.0, metavar="SEC",
                      help="在线验证候选间随机间隔下限（默认 10）")
    p_sd.add_argument("--delay-max", type=float, default=20.0, metavar="SEC",
                      help="在线验证候选间随机间隔上限（默认 20）")

    p_sp = sub.add_parser("spaces", parents=[common],
                          help="重建空间索引（含参与账户；--fetch-meta 刷新所有者/成员）",
                          description="从本地索引重建空间视图索引（spaces/ 目录）；"
                                      "--fetch-meta 经 get_collection 刷新各空间所有者/成员缓存")
    p_sp.add_argument("--fetch-meta", action="store_true",
                      help="重建前先抓取各空间的所有者/成员元数据（每空间 1 次请求，间隔 3s）")
    sub.add_parser("sync-space", parents=[common],
                   help="同步已归档 thread.json 的空间归属（纯本地，零网络）",
                   description="对比 library 索引与已归档 thread.json 的 space 字段，"
                               "有差异则就地 patch（前置：先跑 index 刷新索引）；"
                               "变更后自动联动重建 spaces/ 索引")
    sub.add_parser("relations", parents=[common],
                   help="重建对话关系图",
                   description="从已导出线程重建对话关系图（web_archive/relations/，只读本地文件）")
    p_st = sub.add_parser("status", parents=[common],
                          help="归档状态账与变更报告（零网络只读）",
                          description="输出归档状态账（ok/expired/deleted/error）与增量变更计划"
                                      "（new/updated/早停）。默认 INFO 摘要；-v/-vv/-vvv 逐级输出"
                                      "明细标题（五态/时间/索引字段/state-only 记录）")
    p_st.add_argument("--json", action="store_true",
                      help="机器可读全量报告（stdout 单行 JSON，忽略 -v 级别）")
    p_rr = sub.add_parser("re-render", parents=[common],
                          help="离线重渲 conversation.md 与 turns/（零网络）",
                          description="从 raw_entries.json/raw_blocks.json 离线重渲 conversation.md 与 "
                                      "turns/（渲染层修复后的归档再生）；不动其他文件")
    p_rr.add_argument("--limit", type=int, default=None, metavar="N",
                      help="只处理前 N 个线程目录")
    p_rr.add_argument("--dry-run", action="store_true",
                      help="只列出将处理的线程目录，不写文件")
    p_rr.add_argument("--thread-json", action="store_true",
                      help="同时就地增删 thread.json.interruptions 键（内容有变才写盘）")
    p_ab = sub.add_parser("assets-backfill", parents=[common],
                          help="资产补救（补抓 blocks + 内联提取 + 可选在线刷新）",
                          description="无签名 URL 资产补救：离线从 raw_blocks 提取内联资产"
                                      "（ASSET_DIFF/CODE_ASSET）并登记句柄类；--online 时经"
                                      " /rest/assets/<uuid>/data 刷新缺失/失效资产（限频 3s）")
    p_ab.add_argument("--fetch-blocks", action="store_true",
                      help="先补抓缺失的 raw_blocks.json（deep-research/computer/council）"
                           "及其带签名 URL 资产（在线，每线程间隔 3s）")
    p_ab.add_argument("--online", action="store_true",
                      help="启用在线刷新（默认仅离线内联提取，零请求）")
    p_ab.add_argument("--limit", type=int, default=None, metavar="N",
                      help="只处理前 N 个线程目录")
    sub.add_parser("schedule", parents=[common],
                   help="计算增量计划并生成 cron 片段",
                   description="计算本轮增量导出计划（早停），并生成可被系统 cron 调用的命令片段")
    p_ub = sub.add_parser("usage-backfill", parents=[common],
                          help="补全积分用量记录（credits/thread-usage，幂等）",
                          description="补全账户全部线程的积分用量记录 → index/credit_usage_<account>.json；"
                                      "跨账户请先跑一个账户再换 --account 跑另一个（自动切换 cookie）")
    p_ub.add_argument("--limit", type=int, default=None, metavar="N",
                      help="只处理前 N 个线程")

    p_dj = sub.add_parser("debug-js", parents=[common],
                          help="在当前页面上下文执行 JS（调试）",
                          description="经 WebBridge 在当前页面上下文执行一段 JS 代码（调试用）")
    p_dj.add_argument("target", metavar="JS代码", help="要在页面上下文执行的 JS 代码")

    args = ap.parse_args()

    # init writes the config instead of loading it — skip the strict load
    # init 是写配置而非加载——跳过 strict 加载
    if args.cmd != "init":
        try:
            _cfg.configure(args.config)
        except _cfg.ConfigError as e:
            raise SystemExit(f"[config][ERROR] {e}")

    # Resolve the archive root: --out > user-config archive_root > default ./web_archive
    # 归档根解析：--out > 用户配置 archive_root > 默认 ./web_archive
    args.out = resolve_out_root(args.out)

    setup_logging(args.verbose, resolve_log_file(args.log_file, args.out, args.cmd))

    if args.cookies_from and args.transport == "webbridge":
        raise SystemExit("[ERROR] --cookies-from 与 --transport webbridge 互斥，请只选其一")
    if args.cookies and args.transport == "webbridge":
        raise SystemExit("[ERROR] --cookies 与 --transport webbridge 互斥（webbridge 走浏览器"
                         "页面上下文，cookie 文件不生效），请只选其一")

    if args.cmd == "init":
        # init must work without any prior config — dispatch before account resolution
        # init 不依赖既有配置——置于账户解析之前
        cmd_init(args)
        return

    account = resolve_cli_account(args.account)
    writer = FilesystemWriter(args.out)

    # relations / re-render / sync-space only touch local files — fully offline, no transport/adapter needed;
    # spaces without --fetch-meta is likewise purely local (rebuilds the space view from local indexes, V5-08 exemption)
    # relations / re-render / sync-space 只操作本地文件，纯离线，无需 transport/adapter；
    # spaces 不带 --fetch-meta 时同样纯本地（从本地索引重建空间视图，V5-08 豁免）
    if args.cmd == "relations":
        cmd_relations(args.out)
        return
    if args.cmd == "status":
        cmd_status(args, args.out)
        return
    if args.cmd == "re-render":
        cmd_rerender(args.out, args.limit, args.dry_run, args.thread_json)
        return
    if args.cmd == "sync-space":
        cmd_sync_space(args.out)
        return
    if args.cmd == "spaces" and not args.fetch_meta:
        cmd_spaces(args.out)
        return
    if args.cmd == "search-mode-backfill":
        # Lazy adapter: zero network when everything resolves locally (not even a session probe)
        # 惰性适配器：本地全解时零网络（连 session 探测都不发）
        def _adapter_factory(throttle=None):
            t, _ = make_transport(account, args.cookies_from, args.cookies,
                                  args.transport, throttle=throttle, out_root=args.out,
                                  skip_auth_check=args.skip_auth_check)
            return get_adapter(args.site, transport=t)
        cmd_search_mode_backfill(_adapter_factory, account, args.out, limit=args.limit,
                                 delay_min=args.delay_min, delay_max=args.delay_max,
                                 online=not args.offline)
        return
    if args.cmd == "sync-deleted":
        # Lazy adapter: zero network in offline dry-run; with --online, built per candidate's exporting account (cookie switches automatically)
        # 惰性适配器：离线 dry-run 零网络；--online 时按候选导出账户构造（cookie 自动切换）
        def _adapter_factory(username=None, throttle=None):
            t, _ = make_transport(_account(username or account.username),
                                  args.cookies_from, args.cookies,
                                  args.transport, throttle=throttle, out_root=args.out,
                                  skip_auth_check=args.skip_auth_check)
            return get_adapter(args.site, transport=t)
        cmd_sync_deleted(_adapter_factory, account, args.out, limit=args.limit,
                         delay_min=args.delay_min, delay_max=args.delay_max,
                         online=args.online)
        return

    # batch: share one Throttle between the transport and batch layers so backoff counting stays unified (success resets it)
    # batch：共享 Throttle 给传输层与批量层，退避计数不分裂（成功会清零）
    batch_throttle = Throttle(args.delay_min, args.delay_max) if args.cmd in ("batch", "sync") else None
    transport, source = make_transport(account, args.cookies_from, args.cookies, args.transport,
                                       throttle=batch_throttle, out_root=args.out,
                                       skip_auth_check=args.skip_auth_check)
    adapter = get_adapter(args.site, transport=transport)
    # debug-js depends on browser rendering; space-index uses the browser only with explicit --transport webbridge (default REST)
    # debug-js 依赖浏览器渲染；space-index 仅显式 --transport webbridge 时走浏览器（默认 REST）
    bridge = WebBridgeTransport() if args.cmd == "debug-js" or args.transport == "webbridge" else None

    if args.cmd == "index":
        cmd_index(adapter, account, args.out, full=args.full)
    elif args.cmd == "space-index":
        cmd_space_index(adapter, args.target, args.out, bridge=bridge)
    elif args.cmd == "export":
        cmd_export(adapter, writer, args.target, account, args.force, args.out)
    elif args.cmd == "batch":
        cmd_batch(adapter, writer, account, args.out, args.limit, args.mode, args.force,
                  args.delay_min, args.delay_max, full=args.full, throttle=batch_throttle,
                  verify_on_errors=args.skip_auth_check)
    elif args.cmd == "sync":
        # High-frequency conversation sync: incremental index + incremental batch.
        # Deletion detection and space refresh are skipped by default (opt in with
        # --check-deleted / --refresh-spaces, or run --full for a reconciliation).
        # 高频对话同步：增量 index + 增量 batch。默认跳过删除检测与空间刷新
        # （--check-deleted / --refresh-spaces 显式开启，或 --full 做全量对账）。
        cmd_index(adapter, account, args.out, full=args.full)
        cmd_batch(adapter, writer, account, args.out, args.limit, args.mode, False,
                  args.delay_min, args.delay_max, full=args.full, throttle=batch_throttle,
                  verify_on_errors=args.skip_auth_check)
        if args.check_deleted or args.full:
            def _sync_adapter_factory(username=None, throttle=None):
                t, _ = make_transport(_account(username or account.username),
                                      args.cookies_from, args.cookies, args.transport,
                                      throttle=throttle, out_root=args.out,
                                      skip_auth_check=args.skip_auth_check)
                return get_adapter(args.site, transport=t)
            cmd_sync_deleted(_sync_adapter_factory, account, args.out, limit=None,
                             delay_min=args.delay_min, delay_max=args.delay_max, online=True)
        if args.refresh_spaces or args.full:
            def _sync_spaces_adapter_for(acct_username):
                t, _ = make_transport(_account(acct_username), args.cookies_from, args.cookies,
                                      args.transport, out_root=args.out,
                                      skip_auth_check=args.skip_auth_check)
                return get_adapter(args.site, transport=t)
            cmd_spaces(args.out, adapter=adapter, fetch_meta=True,
                       adapter_for=_sync_spaces_adapter_for, current_account=account.username)
            cmd_sync_space(args.out)
        if not (args.check_deleted or args.refresh_spaces or args.full):
            log.info("[sync] 已完成对话增量同步；本次跳过删除检测与空间刷新"
                     "（用 --check-deleted / --refresh-spaces 开启，或 --full 做全量对账）")
    elif args.cmd == "spaces":
        def adapter_for(acct_username):
            t, _ = make_transport(_account(acct_username), args.cookies_from, args.cookies,
                                  args.transport, out_root=args.out,
                                  skip_auth_check=args.skip_auth_check)
            return get_adapter(args.site, transport=t)
        cmd_spaces(args.out, adapter=adapter, fetch_meta=args.fetch_meta,
                   adapter_for=adapter_for, current_account=account.username)
    elif args.cmd == "assets-backfill":
        folder2user = {v: k for k, v in _cfg.ACCOUNT_DISPLAY_NAMES.items()}

        def adapter_for_dir(folder):
            t, _ = make_transport(_account(folder2user.get(folder, folder)),
                                  args.cookies_from, args.cookies, args.transport,
                                  out_root=args.out,
                                  skip_auth_check=args.skip_auth_check)
            return get_adapter(args.site, transport=t)
        cmd_assets_backfill(adapter, args.out, args.online, args.limit,
                            adapter_for=adapter_for_dir, fetch_blocks=args.fetch_blocks)
    elif args.cmd == "schedule":
        cmd_schedule(adapter, account, args.out)
    elif args.cmd == "usage-backfill":
        cmd_usage_backfill(adapter, account, args.out, args.limit)
    elif args.cmd == "debug-js":
        import json as _json
        print(_json.dumps(bridge.evaluate(args.target), ensure_ascii=False, indent=1)[:5000])


if __name__ == "__main__":
    main()
