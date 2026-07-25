# 维护命令

`pplx-export` 的维护类子命令负责让既有归档保持健康：渲染层修复后重渲页面、补全资产/积分用量/模式元数据、给远端已删除线程打墓碑标记、重建关系图。多数命令离线优先；其在线阶段遵循与 `batch` 相同的限频纪律（见 [rate-limiting.zh-CN.md](rate-limiting.zh-CN.md)）。所有命令都接受[通用选项](pplx-export.zh-CN.md)（`--account`、`--out`、`--cookies-from`、`--transport` 等）。

- 本地归档保留原则：任何维护命令都不删除、不移动已归档的线程内容——归档即备份。
- 离线命令（`re-render`、`relations`、`sync-space`、不带 `--fetch-meta` 的 `spaces`，以及下文各命令的默认阶段）完全不需要数据通路；见 [../architecture/offline-operations.zh-CN.md](../architecture/offline-operations.zh-CN.md)。

## re-render

从归档的原始 JSON（`raw_entries.json` / `raw_blocks.json`）重新生成 `conversation.md` 与 `turns/`——零网络，其余文件一律不动。

| 参数 | 含义 | 默认值 |
|---|---|---|
| `--limit N` | 只处理前 N 个线程目录 | 全部 |
| `--dry-run` | 只列出将处理的目录，不写文件 | 关 |
| `--thread-json` | 同时就地增删 `thread.json` 的 `interruptions` 与 `answer_variants` 键 | 关 |

关键行为：

- 用与导出相同的管线离线重建 turns：解析、按 `created_us` 排序、引文去重；computer/council 额外挂 workflow blocks、子代理映射与未消费后台附录。
- 只（重）写 `conversation.md` 与 `turns/turn_*.md`；`sources*`、`assets/`、`report.md`、`thread.json` 保持原样。编号高于当前轮数的残留 `turn_*.md` 会被删除——除此之外不动，未变文件保留 mtime。
- `--thread-json` 仅在内容有变化时写盘；`answer_variants` 新增/变化时告警 `ANSWER_VARIANT_DETECTED` 并追加登记 `index/answer_variants_log.jsonl`（幂等重跑不刷屏）。
- 没有 `raw_entries.json` 的线程目录跳过并计数。

```bash
pplx-export re-render --limit 20 --thread-json --dry-run
```

## assets-backfill

补救归档时未取得签名 URL 的资产——三段式补救：补抓 blocks、离线内联提取、可选在线刷新。

| 参数 | 含义 | 默认值 |
|---|---|---|
| `--fetch-blocks` | 先补抓缺失的 `raw_blocks.json` 及其带签名 URL 资产（在线） | 关 |
| `--online` | 启用缺失/失效资产的在线刷新 | 关（仅离线内联提取，零请求） |
| `--limit N` | 只处理前 N 个线程目录 | 全部 |

关键行为：

- 默认阶段（离线，零请求）：从 `raw_blocks.json` 提取内联资产（`ASSET_DIFF` / `CODE_ASSET`）落盘为 `assets/files/*.md`，并把云工作区句柄类（`DOC_FILE` / `CODE_FILE` / `UNKNOWN`——暂无下载通道）登记进 `assets/assets_manifest.json`。幂等：已知记录按 uuid → file_handle 查重；同名多版本文件追加 uuid 短前缀，重跑不冲突。
- `--fetch-blocks`（在线）：补抓 deep-research/computer/council/study 线程缺失的 `raw_blocks.json` 及其可下载资产；线程按账户目录分组，每账户惰性构建适配器（cookie 自动切换），线程间隔 3s。
- `--online`：对 manifest 中 `downloaded_to` 缺失/失效的版本，经 `/rest/assets/<uuid>/data` 取新鲜签名 URL（API 串行，间隔 3s），再从 CDN 重下（6 线程并发、无延迟——CDN 非 API）。404 `ASSET_NOT_FOUND` 置 `asset_expired` 终态标记；跨账户 403 换归档所属账户重试一次。
- 每次写回都把 manifest 的 `count` 重算为版本总数。

```bash
pplx-export assets-backfill --fetch-blocks --online --limit 30 --account alice
```

## usage-backfill

补全账户全部已归档线程的积分用量记录（`credits/thread-usage`），写入 `index/credit_usage_<account>.json`。

| 参数 | 含义 | 默认值 |
|---|---|---|
| `--limit N` | 只处理前 N 个线程 | 全部 |

关键行为：

- 每个已归档线程一次 GET（`thread_id` 取线程的 `psc_uuid`），间隔 3s；幂等——输出文件中已记录的线程跳过。
- 403（`thread_usage_forbidden`，即跨账户线程）记为 `error` 且永不重试；其他失败留待下轮。每处理 25 个线程中途落盘一次。
- 多账户：每个账户用 `--account` 各跑一次——cookie 在运行间自动切换。

```bash
pplx-export usage-backfill --account alice
```

## search-mode-backfill

给 `index/library_<account>.json` 的每一行补平台权威 `search_mode` 字段，使 `batch --mode` 能精确过滤而不靠启发式。

| 参数 | 含义 | 默认值 |
|---|---|---|
| `--limit N` | 只处理前 N 条待补行 | 全部 |
| `--offline` | 只做本地提取——本地无 raw 的行留待下轮，不联网兜底 | 关 |
| `--delay-min SEC` | 联网兜底线程间随机间隔下限 | `10` |
| `--delay-max SEC` | 联网兜底线程间随机间隔上限 | `20` |

关键行为：

- 存平台原始值（`SEARCH` / `RESEARCH` / `ASI` / `AGENTIC_RESEARCH` / `STUDY` / `STUDIO`…）；线程内多值时按特异性 computer > council > study > deep-research > search 取最高。
- 本地优先：已归档线程从 `raw_entries.json` 提取，零网络——纯本地可解时连 transport 都不构建（连 session 探测都没有）。
- 仅本地无 raw 的行联网兜底：`GET /rest/thread/<uuid>`，10–20s 随机间隔；`expired` 终态的行跳过并如实记录；在线新发现 expired/deleted 的线程标记进 `batch_state.json`，下轮免请求。
- 幂等可续跑：已有 `search_mode` 的行跳过，每 25 条中途落盘；之后 `index` 刷新会保留富化结果（按 `entryUUID` 合并回来）。

```bash
pplx-export search-mode-backfill --account alice --offline
```

## sync-deleted

识别从远端 library 消失的线程（用户删除或平台清除）并打墓碑标记——绝不删除、不移动任何归档文件。

| 参数 | 含义 | 默认值 |
|---|---|---|
| `--online` | 在线验证候选 | 关（离线 dry-run：只列候选） |
| `--limit N` | 只处理前 N 条候选 | 全部 |
| `--delay-min SEC` | 候选间随机间隔下限 | `10` |
| `--delay-max SEC` | 候选间随机间隔上限 | `20` |

关键行为：

- 候选判定离线且跨账户：`batch_state` 状态为 `ok` 的线程在**所有** `index/library_*.json` 的 `entryUUID` 并集中均消失才成为候选——任一索引含有即视为存活，因此经共享空间跨账户导出的线程不会误报。无任何可用索引时全部安全跳过，并提示先跑 `index`。
- 默认离线 dry-run：只列候选与安全跳过原因——零网络、不改任何文件。
- `--online` 按候选 `thread.json` 的 `export_via` 账户逐条 `GET /rest/thread/<uuid>` 验证（cookie 逐候选自动切换）。
- `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 确认 → `batch_state` 标记终态 `deleted`（与 `expired` 同语义：永不重试，`--force` 也不重导；见 [incremental-sync.zh-CN.md](incremental-sync.zh-CN.md)），并给该线程各 `thread.json` 就地加 `remote_deleted` 时间戳（幂等——已有该键不覆盖）。
- 线程仍存在 → 误报：如实报告并提示重跑 `index`，不改任何状态。传输错误退避留待下轮；连续 3 次鉴权失败即中止，避免误标活线程。

```bash
pplx-export sync-deleted
pplx-export sync-deleted --online --limit 20
```

第一行只列候选（离线 dry-run）；第二行在线验证并给确认的线程打标记。

## status

输出归档状态账与增量变更计划——零网络、只读。回答「归档现状如何、下一次 `batch` 会做什么」，全程不触网。

| 参数 | 含义 | 默认值 |
|---|---|---|
| `--account X` | 只报告一个账户 | 全部有 `index/library_*.json` 的账户 |
| `--json` | 机器可读全量报告（stdout 单行 JSON，忽略 -v 级别） | 关（人读日志行） |

关键行为：

- 数据源全本地：`index/library_*.json`（各账户索引行）与 `index/batch_state.json`（导出状态唯一真源）。变更分类复用与 `batch`/`schedule` 相同的 `plan_incremental` 纯函数，`new`/`updated`/`done`/`expired`/`deleted` 语义与 `batch` 的计算完全一致。
- 默认 INFO 输出：每账户一行摘要（索引条数与新鲜度、`ok/expired/deleted/error` 状态计数、`new/updated` 变更计数、早停数），末尾一行全局 `batch_state` 状态账（如 `559 ok + 13 expired + 12 deleted`）。
- 明细级别直接挂既有 `-v` 计数标志：`-v` 加 new/updated/error 线程标题（首行、60 字符截断）；`-vv` 加 done/expired/deleted 线程并附 `lastUpdated`/`exported_at`；`-vvv` 全量不截断并附索引 `mode`/`search_mode` 字段与 state-only 列表（`batch_state` 有而所有账户索引均无的记录——疑似远端删除，可经 [sync-deleted](#sync-deleted) 对账）。
- 守卫：`index/` 或 library 文件缺失 → 报错指向 `pplx-export index`；`batch_state.json` 缺失按空状态处理（全部判 new）。无需用户级 config——账户名从 library 文件名枚举。
- `--json` 经 stdout 输出全量报告（accounts/changes/threads/state_only/totals 单行 JSON）——与 `pplx-ask` 相同的契约风格。

```bash
pplx-export status                 # 全部账户摘要
pplx-export status -vv             # 五态线程明细
pplx-export status --account alice --json
```

## relations

从已导出线程重建对话关系图 → 归档根下 `relations/edges.jsonl`，外加人读摘要 `relations/graph.md`。

| 参数 | 含义 | 默认值 |
|---|---|---|
| *（仅通用选项；只有 `--out` 起作用）* | | |

关键行为：

- 纯离线、零网络、对归档只读：复用 re-render 的离线重建管线（`raw_entries.json` / `raw_blocks.json`），`sub_agents`、`query_source`、引文等信号都可用于边检测。
- 无 raw 数据的线程退化为 `thread.json` + `conversation.md` 壳——只能触发 `same_space` 与裸 uuid 引用边。

```bash
pplx-export relations
```

## debug-js

经本机 WebBridge 守护进程（`127.0.0.1:10086`）在当前浏览器页面上下文执行一段 JavaScript，并以 JSON 打印结果——调试用逃生舱。

| 参数 | 含义 | 默认值 |
|---|---|---|
| `JS代码`（位置参数） | 要在页面上下文执行的 JavaScript 代码 | 必填 |

关键行为：

- 要求 WebBridge 守护进程可达，且浏览器中已打开目标 Perplexity 页面；代码片段在页面自身会话中执行。
- 打印的 JSON 截断到 5000 字符。

```bash
pplx-export debug-js 'document.title'
```
