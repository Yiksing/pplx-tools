# 增量同步

`pplx-export batch` 为高频运行而设计：每轮只导出新增或有变化的对话，自动修复
中断运行留下的缺口，且绝不重复触碰平台已下架的线程。「哪些已导出」的唯一权威
来源是 `index/batch_state.json`（`BatchState`，`pplx_export/core/state.py:63`），
每导完一个线程即更新——不另维护影子副本。

## 前置条件与基本用法

```bash
pplx-export index --account alice   # 先刷新 index/library_alice.json
pplx-export batch --account alice   # 增量导出（早停 + 断点续跑）
```

索引不存在时 `batch` 拒绝运行（`pplx_export/commands/batch_cmd.py:79-81`）。
`--limit N` 与 `--mode <mode>` 在规划之前过滤索引行；缺 `entryUUID` 的坏行
只告警跳过，不会让整个运行崩溃（`batch_cmd.py:95-100`）。

## 增量计划如何工作

1. **排序。** 索引行按 `lastUpdated` 从新到旧排序（`batch_cmd.py:89`）。
   全新对话与「续接的旧对话」（`lastUpdated` 变新、位置上移）都排在顶部——
   这个顺序正是早停安全的前提。
2. **分类。** `plan_incremental`（`pplx_export/hooks/incremental.py:36-87`）
   ——`batch` 与 `schedule` 共用的纯函数——为每一行指派恰好一个动作：

   | 动作 | 条件 | batch 的处理 |
   |---|---|---|
   | `new` | `batch_state` 中从未见过该 uuid | 导出 |
   | `updated` | `lastUpdated` 与记录值不同，或带 `--force` | 重导 |
   | `done` | 状态为 `ok` 且 `lastUpdated` 未变 | 跳过 |
   | `expired` | 之前导出时平台返回了 `ENTRY_EXPIRED` | 跳过——终态，永不重试 |
   | `deleted` | `sync-deleted` 已确认远端删除 | 跳过——终态，永不重试 |

3. **早停。** 默认（既不带 `--full` 也不带 `--force`）截掉尾部最长的终态
   连续段（`done` / `expired` / `deleted`），截掉条数记为 `n_stopped`
   （`incremental.py:83-87`）。列表从新到旧，未变条目之下必然更旧、也未变——
   继续扫描只是浪费时间。

   ```mermaid
   flowchart TD
       IDX["library 索引行<br/>按 lastUpdated 从新到旧排序"] --> PLAN["plan_incremental"]
       PLAN --> NEW["new → 导出"]
       PLAN --> UPD["updated → 重导"]
       PLAN --> DONE["done → 跳过"]
       PLAN --> TERM["expired / deleted → 跳过（终态）"]
       DONE --> STOP["早停：截掉尾部终态连续段"]
       TERM --> STOP
   ```

4. **执行。** 每导出一个线程立即打标记（`mark_ok` / `mark_error` /
   `mark_expired` / `mark_deleted`），且每项之后都落盘状态文件
   （`batch_cmd.py:154-201`）；`KeyboardInterrupt` 也会先保存再向上抛
   （`batch_cmd.py:158-161`）。写入是原子的——临时文件加 `os.replace`
   （`state.py:145-152`）——中断不会留下截断的 JSON。

## 中断后的缺口修复

早停绝不会掩埋缺口。失败（状态 `error`）或从未轮到的线程位于终态后缀
**之上**，下一轮会把它们重新规划为 `updated` / `new`，在到达早停点之前就
导出（`incremental.py:12-14`，`batch_cmd.py:206-208`）。配合逐项落盘，batch
运行可在任意时刻中断，直接重跑即可。

若 `batch_state.json` 本身损坏，不会被静默置空：原文件更名为
`batch_state.json.corrupt-<timestamp>`，已记录的终态不丢失、不做无谓重试
（`state.py:68-81`）。

## `--full` 与 `--force`

| 选项 | 效果 | 终态 | 适用场景 |
|---|---|---|---|
| *（默认）* | 对尾部终态连续段早停 | 跳过 | 每次常规 / 定时运行 |
| `--full` | 全量扫描，不早停；未变线程仍按 `done` 跳过 | 跳过 | 定期兜底，或怀疑档案有缺口时 |
| `--force` | 全部重导，包括未变线程 | 仍然排除——永不重试 | 管线修复后必须重新抓取 raw 数据时 |

终态被 `--force` 排除是有意设计：重试已过期或远端已删除的线程只会白费
请求与退避预算（`batch_cmd.py:120-127`）。

另见 [`status`](maintenance-commands.md#status)：零网络输出状态账与按同一
`plan_incremental` 语义计算的变更计划（new/updated/早停数）。

`lastUpdated` 比较会对小数秒部分去尾零（`.18033Z` 与 `.180330Z` 判同；
`state.py:23-55`），因为平台偶发丢尾零——精确字符串比较会误判「已变化」，
导致重复导出。

## 终态：`expired` 与 `deleted`

| | `expired` | `deleted` |
|---|---|---|
| 含义 | 平台清除了该线程（约 3 个月保留窗口）；导出尝试返回 `ENTRY_EXPIRED` | 用户/远端删除，经 `sync-deleted` 确认 |
| 记录者 | `batch` 自身（`mark_expired`，`state.py:131-134`） | `pplx-export sync-deleted --online`（`mark_deleted`，`state.py:136-143`） |
| 重试？ | 永不——`--force` 也不 | 永不——`--force` 也不 |
| 证据 | `ENTRY_EXPIRED` 响应 | `note` 字段：索引消失 + `GET /rest/thread/<uuid>` → `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 |

### sync-deleted：确认远端删除

```bash
pplx-export sync-deleted --account alice            # 离线 dry-run：只列候选
pplx-export sync-deleted --account alice --online   # 逐候选在线验证
```

1. **候选判定（离线，零网络）。** `batch_state` 中状态为 `ok` 的线程，若在
   **所有** `index/library_*.json` 账户索引的 `entryUUID` 并集中均消失，即为
   疑似远端删除候选（`pplx_export/commands/sync_deleted_cmd.py:148-212`）。
   跨账户并集是必需的：`bob` 拥有、经共享空间由 `alice` 导出的线程永远不会
   出现在 `alice` 自己的索引里——单账户 diff 会把这批线程全部误报。当所有
   索引都不可用时，候选全部安全跳过并如实记录原因。
2. **默认 dry-run。** 不带 `--online` 只列出候选——不联网、不改任何文件。
3. **`--online` 确认。** 逐候选 `GET /rest/thread/<uuid>`，使用候选
   `thread.json` 里的 `export_via` 账户（cookie 自动切换）：

   | 结果 | 处置 |
   |---|---|
   | `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 | 确认：`batch_state` 标记终态 `deleted`（`note` 记录原因），并给该线程各目录的 `thread.json` 就地加 `remote_deleted` 时间戳 |
   | 线程仍存在 | 误报：如实报告（索引可能未刷新完整——重跑 `index` 后复核），不改任何状态 |
   | 5xx / 网络错误 | 不改状态，留待下轮 |
   | 连续 3 次 401/403 | fail-fast 中止——cookie 失效时退避无法自愈，空转会把活线程误标（`sync_deleted_cmd.py:333-337`） |

   确认标记逐条落盘：`--online` 运行中断不丢已确认项，重跑幂等
   （`sync_deleted_cmd.py:254-256`）。

## 墓碑原则

!!! warning "本地归档绝不删除"
    本仓库是已导出对话的备份档案（backup of record）。`sync-deleted` 只做
    「识别 + 标记」（tombstone）：**绝不删除、不移动任何归档文件**。确认只改
    两处——`batch_state` 的状态与 `thread.json` 的一个标记键：

    ```json
    "remote_deleted": "2026-07-23T10:20:30Z"
    ```

    该标记幂等：已有 `remote_deleted` 键既不重写也不覆盖原时间
    （`sync_deleted_cmd.py:215-244`）。

## 幂等与离线重渲

- 索引未变时重跑 `batch` 什么都不导：每行都分类为 `done`，运行停在早停点。
  状态写入原子、标记逐线程、重复确认删除不会重复打 `remote_deleted`。
- 归档保存了 raw API 负载（`raw_entries.json` / `raw_blocks.json`），渲染产物
  可随时零网络再生：

  ```bash
  pplx-export re-render                 # 全量重建 conversation.md + turns/
  pplx-export re-render --dry-run       # 只列出将处理的线程目录
  pplx-export re-render --thread-json   # 同时同步 interruptions / answer_variants 键
  ```

  `re-render` 用当前渲染器重新解析 raw JSON
  （`pplx_export/commands/rerender_cmd.py:105-190`）：重写 `conversation.md`
  与 `turns/turn_*.md`，删除编号高于当前轮数的残留轮文件，sources、assets、
  `report.md` 与 `thread.json` 原样不动。渲染层修复就是这样在零请求下铺到
  整个归档的。

## 另见

- [pplx-export.md](pplx-export.md) —— `batch` 完整命令参考（`--mode`、`--limit`、间隔参数）
- [maintenance-commands.md](maintenance-commands.md) —— `sync-deleted`、`re-render` 与各 backfill 命令
- [archive-layout.md](archive-layout.md) —— `batch_state.json` 与 `thread.json` 的位置
- [rate-limiting.md](rate-limiting.md) —— 线程间隔、退避、鉴权 fail-fast
- [../architecture/export-pipeline.md](../architecture/export-pipeline.md) —— 完整导出管线
- [../architecture/offline-operations.md](../architecture/offline-operations.md) —— 离线重建管线详解
- [../architecture/rate-limiting-errors.md](../architecture/rate-limiting-errors.md) —— 错误分类与终态处理
