# pplx-export

`pplx-export` 是归档 CLI：从 Perplexity 拉取对话索引、把线程导出到本地归档，并维护派生视图（空间索引、cron 片段）。本页覆盖采集侧子命令——`index`、`space-index`、`export`、`batch`、`spaces`、`sync-space`、`schedule`——外加一次性初始化命令 `init`。补全/修复类子命令见 [maintenance-commands.zh-CN.md](maintenance-commands.zh-CN.md)；查询 CLI 见 [pplx-ask.zh-CN.md](pplx-ask.zh-CN.md)。

## 通用选项

所有子命令都接受这些参数（在 `pplx_export/commands/common.py` 中统一定义）：

| 参数 | 含义 | 默认值 |
|---|---|---|
| `--account NAME` | 目标账户。cookie 归属 email 与登记 email 不符时，自动枚举浏览器中的各账户会话令牌完成切换 | 用户级配置的 `default_account` |
| `--config PATH` | 用户级配置文件（账户注册表）。优先级：`--config` > 环境变量 `PPLX_EXPORT_CONFIG` > `~/.config/pplx-export/config.toml` | 默认查找链 |
| `--skip-auth-check` | 跳过启动时的账户归属会话探测、信任当前登录，避免网络差时开头长时间等待；`batch` 在报错累积时会做延迟账户校验——见[配置](configuration.md) | 关闭 |
| `--site NAME` | 站点适配器 | `perplexity` |
| `--out DIR` | 归档输出根目录 | `--out` > 配置 `archive_root` > `./web_archive` |
| `--cookies-from BROWSER` | 从指定浏览器导入 cookie（`edge`/`chrome`/`firefox`/`safari`/`brave`…） | — |
| `--cookies FILE` | Netscape cookie 文件或 JSON cookie 文件 | — |
| `--transport MODE` | `cookie` = cookie 直连请求；`webbridge` = 在浏览器页面上下文内发 fetch | `cookie` |
| `-v`, `--verbose` | DEBUG 输出（请求追踪、内部判定）；可重复 | 关 |
| `--log-file [PATH]` | 全量日志落盘；不带值时自动落 `<out>/index/logs/<cmd>-<timestamp>.log` | 关 |

- `--cookies-from` / `--cookies` 与 `--transport webbridge` 互斥——bridge 运行在页面上下文中，自动带浏览器 cookie。
- `pplx-export --version` 打印包版本并退出（仅顶层，非子命令参数）。
- 账户登记、cookie 来源与多账户切换见 [configuration.zh-CN.md](configuration.zh-CN.md)；各文件落盘位置见 [archive-layout.zh-CN.md](archive-layout.zh-CN.md)。

## init

从浏览器 cookie 自动发现账户并写入用户级配置——手工复制 `config.example.toml` 之外的自动方案（见 [configuration.zh-CN.md](configuration.zh-CN.md)）。

| 参数 | 含义 | 默认值 |
|---|---|---|
| `--force` | 覆盖已存在的配置文件 | 关（拒绝覆盖） |
| `--create-bot-space [标题]` | 无空间标题匹配时经 API 创建 BOT 空间（对账户的一次写操作）；附显式标题时匹配与创建均用该标题，否则标题取自 `--bot-title`；不加此标志则 `[bot_space]` 留空写入 | 关 |
| `--bot-title TITLE` | 既用于匹配既有空间、也用于创建时命名的空间标题 | `BOT` |
| *（通用选项适用）* | cookie 来源标志决定账户发现的位置；仅对 `init`，`--config` 是**写入**路径（跳过 strict 配置加载） | |

关键行为：

- 令牌枚举：从浏览器库收集各账户会话 cookie（`__Secure-pplx.session.<uid>`）；给出 `--cookies FILE` 时改扫该 cookie 文件（完整导出可能携带多个账户）。无可枚举令牌时，退化为仅探测当前活跃会话。
- 会话探测：每个令牌逐个请求 `GET /api/auth/session` 取得账户 email / 显示名；失败或未返回 email 的令牌 warning 跳过。
- 注册表装配：账户键由 email 本地部分派生（撞名加 `-2`/`-3`… 后缀）；`default_account` 取当前活跃账户，否则取首个发现的账户。
- BOT 空间：经 `list_user_collections` 按标题精确匹配（大小写不敏感）；无匹配时 `--create-bot-space [标题]` 当场创建（显式标题覆盖 `--bot-title`，匹配与创建均用之），否则 `[bot_space]` 留空。
- TOML 原子写入（临时文件 + 改名），权限 0600；已存在的文件不加 `--force` 绝不覆盖。命令结尾打印一行汇总 JSON：配置路径、账户键、默认账户、BOT 空间 uuid/slug。
- 模型播种（best-effort）：写完配置后，`init` 拉取 `models/config/v2` 播种机器托管的 `[models]` 表，让新配置即带当前模型默认/目录；失败则 warning 跳过（稍后用 `pplx-ask models --refresh` 刷新）。见[配置](configuration.md)。
- `--transport webbridge` 会被拒绝——页面上下文通道无法枚举各账户令牌。

```bash
pplx-export init                          # 写入默认 ~/.config/pplx-export/config.toml
pplx-export init --create-bot-space [标题]  # 无标题匹配时创建 BOT 空间（可附自定义标题）
pplx-export init --config /path/to/config.toml --force   # 自定义路径，允许覆盖
```

## index

刷新账户对话列表主索引 `index/library_<account>.json`——其他所有命令的比对基线。

| 参数 | 含义 | 默认值 |
|---|---|---|
| `--full` | 全量翻页并整体重写索引；复位增量计数 | 增量 |

关键行为：

- **默认增量**：按最新翻页，遇到「连续一整页（`_STOP_RUN`）已知且未变」即停，把抓到的头部合并到既有索引上——更旧的行原样保留（不丢失）。首次运行或无既有索引时按全量。
- **`--full`** 全量翻页并整体重写索引；作为定期对账的前置。
- **增量路径的盲区**：旧线程的远端*删除*与*空间变更*不会出现在抓取的头部，因此看不到。删除权威仍是 `sync-deleted --online`。索引文档记录 `incremental_runs_since_full`；连续多次增量后会提醒你跑一次 `--full`（并配合 `sync-deleted --online`）。
- 保留 `search-mode-backfill` 写入的 `search_mode` 富化，按 `entryUUID` 合并回来。
- 在跑 `batch`、`sync-space`、`sync-deleted` 之前先跑它——它们的比对结果取决于索引的新鲜度。

```bash
pplx-export index --account alice          # 增量刷新
pplx-export index --account alice --full   # 全量对账前置
```

## sync

高频同步便捷入口：**增量 `index` + 增量 `batch`**，只关注对话。

| 参数 | 含义 | 默认值 |
|---|---|---|
| `--full` | 全量对账：全量 `index` + `batch` 全扫（并执行下方删除/空间步骤） | 关闭 |
| `--check-deleted` | 附带 `sync-deleted --online`：核验并标记远端已删除线程 | 关闭 |
| `--refresh-spaces` | 附带 `spaces --fetch-meta` 与 `sync-space` | 关闭 |
| `--limit N` / `--mode X` / `--delay-min` / `--delay-max` | 透传给 `batch` 阶段 | — |

关键行为：

- 默认只抓新增/更新的对话，**跳过删除检测与空间刷新**——高频同步下最省。
- 删除/空间对账为可选（`--check-deleted` / `--refresh-spaces`）或由 `--full` 一并完成。`index` 的计数（`incremental_runs_since_full`）是兜底：到期会提醒你做一次 `--full` 对账。

```bash
pplx-export sync --account alice                     # 只关注对话（快）
pplx-export sync --account alice --full              # 定期全量对账
pplx-export sync --account alice --check-deleted     # 顺带标记远端删除
```

## space-index

提取某空间「全部」会话列表——含共享空间其他成员的线程——写入 `index/space_<slug>.json`。

| 参数 | 含义 | 默认值 |
|---|---|---|
| `SPACE_URL`（位置参数） | 空间页面 URL | 必填 |
| `--transport webbridge` | 改用旧浏览器渲染路径代替 REST | `cookie`（REST 直连） |

关键行为：

- 默认走 REST 直连：经 cookie 通路调 `list_collection_threads`，offset 分页；行内含 `context_uuid` 与 `answer_preview`。
- `--transport webbridge` 时回退到滚动渲染空间页面、抓取行属性的旧路径——REST 结构变更时的备用通道。
- 行按 `lastUpdated` 从新到旧写盘。

```bash
pplx-export space-index "https://www.perplexity.ai/spaces/<space-slug>" --account alice
```

## export

导出单个线程（URL 或裸 UUID）到归档目录 `<out>/<account-folder>/<mode>/<thread-dir>/`。

| 参数 | 含义 | 默认值 |
|---|---|---|
| `THREAD`（位置参数） | 线程 URL 或 UUID | 必填 |
| `--force` | `lastUpdated` 未变也强制重导 | 关 |

关键行为：

- 归档副本已是最新时跳过、不写任何文件；`--force` 覆盖该检查。
- 线程在本地 library 索引中有行时，`lastUpdated` 取索引值（与 `batch` 同语义同格式），否则回退平台真值。
- 终态优雅登记，不抛 traceback：`ENTRY_DELETED` 在 `batch_state.json` 标记 `deleted`，`ENTRY_EXPIRED` 标记 `expired`——两种情况下本地已有归档都保持原样。
- 导出成功会把 `ok` 写进 `index/batch_state.json`，增量计划据此把该线程计为「已导出且未变」。
- 线程目录内的文件构成见 [archive-layout.zh-CN.md](archive-layout.zh-CN.md)；导出管线本身见 [../architecture/export-pipeline.zh-CN.md](../architecture/export-pipeline.zh-CN.md)。

```bash
pplx-export export "https://www.perplexity.ai/search/<thread-uuid>" --account alice
```

## batch

批量导出账户线程——日常主力命令，带增量早停与断点续跑。

| 参数 | 含义 | 默认值 |
|---|---|---|
| `--force` | 重导全部线程（终态除外） | 关 |
| `--full` | 全量扫描：未变线程仍跳过，但不早停 | 关 |
| `--limit N` | 只处理列表前 N 条（从新到旧） | 全部 |
| `--mode MODE` | 只导出 `search` / `deep-research` / `computer` / `council` / `study` 线程 | 全部模式 |
| `--delay-min SEC` | 线程间随机间隔下限 | `10` |
| `--delay-max SEC` | 线程间随机间隔上限 | `20` |

关键行为：

- 依赖 `index/library_<account>.json`——先跑 `index`。
- 默认**增量早停**：列表从新到旧排序，尾部「已导出且未变」的连续段整体截掉；上次中断留下的缺口（error/未导）位于终态后缀之上，仍会被修复。`--full` 关闭早停（定期兜底或怀疑档案有缺口时用）；`--force` 重导除终态外的全部线程，终态永不重试。完整语义见 [incremental-sync.zh-CN.md](incremental-sync.zh-CN.md)。
- `--mode` 过滤：索引行带 `search_mode`（`search-mode-backfill` 富化的平台权威字段）时经 `SEARCH_MODE_MAP` 精确匹配——该路径下 `--mode search` 不再混入 deep-research/council/study 线程。无 `search_mode` 的行回落索引字段启发式：`computer` = mode `COMPUTER`；`deep-research` = displayModel `pplx_alpha`；`council` = `pplx_agentic_research`；`study` = `pplx_study`；`search` = 其余 mode 为 `SEARCH` 的行（含上述三类——要精确排除请用对应模式单独导）。
- 每导完一个线程就把状态写进 `index/batch_state.json`——可随时中断重跑。
- 鉴权快速失败：连续 3 次 401/403 即中止（cookie 失效时退避无法自愈，空转只会让数百线程各失败一遍）。
- 节奏：线程间随机间隔 `--delay-min`–`--delay-max`；429/5xx 由传输层退避。详见 [rate-limiting.zh-CN.md](rate-limiting.zh-CN.md)。
- 命中重写答案变体的线程会登记进 `index/answer_variants_log.jsonl` 并告警，需尽快人工处置（见 [../reference/api/api-responses-errors.zh-CN.md](../reference/api/api-responses-errors.zh-CN.md)）。

```bash
pplx-export batch --account bob --mode deep-research --limit 50
```

## spaces

从本地 library 索引重建空间视图索引——每空间一个 Markdown 页面，外加 `spaces.json` 注册表。

| 参数 | 含义 | 默认值 |
|---|---|---|
| `--fetch-meta` | 重建前先刷新所有者/成员元数据 | 关 |

关键行为：

- 不带 `--fetch-meta` 时纯本地（零网络）：跨所有 `library_*.json` 按空间 slug 聚合线程，含参与账户统计与指向已导出线程目录的反链。
- 输出落到当前工作目录的 `./spaces/`——请在包含 `web_archive/` 的目录下运行，空间页里的反链才能正确解析。
- `--fetch-meta` 先经 `get_collection` 刷新各空间所有者/成员缓存（每空间 1 次请求，间隔 3s）到 `index/space_meta.json`；当前账户无权查看的空间，自动换可见账户重试（cookie 自动切换）。

```bash
pplx-export spaces --fetch-meta --account alice
```

## sync-space

把已归档 `thread.json` 的 `space` 字段与当前索引对齐——纯本地，零网络。

| 参数 | 含义 | 默认值 |
|---|---|---|
| *（仅通用选项；只有 `--out` 起作用）* | | |

关键行为：

- 前置：先跑 `index`——刷新后的 `library_*.json` 是当前空间归属的真源。
- 逐线程比对空间 slug，有差异则就地 patch `thread.json`；前 30 条变更会记入日志。
- 有任何变更后，自动联动重建 `spaces/` 索引。

```bash
pplx-export index --account alice && pplx-export sync-space
```

## schedule

计算本轮增量导出计划，并生成可被系统 cron 直接调用的命令片段。

| 参数 | 含义 | 默认值 |
|---|---|---|
| *（仅通用选项）* | | |

关键行为：

- 拉取实时索引，按总数/新增/更新报告计划，用的是与 `batch` 相同的早停纯函数（`plan_incremental`）——见 [incremental-sync.zh-CN.md](incremental-sync.zh-CN.md)。
- 写 `<out>/index/cron_snippet.txt`，内容为一条 `17 3 * * *` 行，形如 `cd '<archive-parent>' && '<abs-path-to-pplx-export>' batch --account '<account>' --out '<abs-archive-root>'`——路径用绝对路径并加引号，因为 cron 的 cwd 与 PATH 不可预测。可执行文件路径经 `shutil.which` 解析，解析失败时回退为裸命令名 `pplx-export`。
- 定时跑批按设计只跑增量；`batch --full` 作为定期兜底手动执行。

```bash
pplx-export schedule --account alice
```
