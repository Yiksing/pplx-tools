# 归档目录结构

`pplx-export` 下载的所有内容都落在同一棵输出树中——默认为 `./web_archive/`
（可用 `--out` 覆盖）。本页是这棵树的导读：每个目录与文件是什么、`thread.json`
携带哪些键、以及会话跨天续接时工具如何保证一个线程只有一个目录。全部内容均由工具生成；
机制细节见[数据模型与目录契约](../architecture/data-model.zh-CN.md)与[导出流水线](../architecture/export-pipeline.zh-CN.md)。

## 输出目录树

```
web_archive/
├── alice/                                # 每账户一个文件夹（作者显示名）
│   ├── search/                           # 模式：search | deep-research | computer | council | study
│   │   └── 2026-07-18_quantum-computing-survey_1a2b3c4d/   # 每线程一个目录
│   │       ├── thread.json               # 元数据 + 可选登记键
│   │       ├── conversation.md           # 简版：逐轮 Query/Answer
│   │       ├── turns/
│   │       │   ├── turn_0001.md          # 完整版：完整工作过程细节
│   │       │   └── ...
│   │       ├── sources.json              # 全线程引文（按 url 去重）
│   │       ├── sources.md
│   │       ├── report.md                 # deep-research 报告（有才存在）
│   │       ├── raw_entries.json          # plain API 响应，原样落盘（恒存在）
│   │       ├── raw_blocks.json           # schematized API 响应（search 无此文件）
│   │       └── assets/
│   │           ├── assets_manifest.json  # 多版本清单
│   │           └── files/                # 已下载的资产文件体
│   ├── deep-research/ ...
│   └── computer/ ...
├── index/                                # 状态文件与索引（见下）
├── relations/                            # edges.jsonl + graph.md（由 `pplx-export relations` 重建）
├── crosscheck/                           # 交叉核验报告（人工/评审产物）
└── bob/ ...
```

## 线程目录

每个线程恰好对应一个目录，由 `thread_dir_for`（`fs_writer.py:58-72`）计算：

```
<账户显示名>/<模式>/<YYYY-MM-DD>_<标题slug>_<uuid8>/
```

| 组成 | 来源 | 说明 |
|---|---|---|
| `<账户显示名>` | 线程作者，经 `author_folder` → `_safe_folder` 清洗（`fs_writer.py:40-51`） | 路径分隔符与 Windows 非法字符（`:*?"<>\|`）替换为 `_`；`.`/`..` 被拒绝（防共享空间路径穿越）；其余字符——包括空格——原样保留 |
| `<模式>` | `detect_mode` | 五种模式之一，见[会话模式](modes.zh-CN.md) |
| `<YYYY-MM-DD>` | `thread.json` 的 `lastUpdated` 日期前缀 | 平台侧最后更新日期，**不是**导出日期——续接的线程更新后它会变（见下文迁移） |
| `<标题slug>` | `slugify(title)`（`normalize.py:261-263`） | 最长 40 字符，非单词字符 → `-`，空标题 → `untitled` |
| `<uuid8>` | `web_uuid[:8]` | 线程 UUID 前 8 位——目录的身份锚点 |

## 线程目录内的文件

### thread.json——元数据与登记信息

由 `write_thread`（`fs_writer.py:224-253`）写入。恒存在的键：

| 键 | 内容 |
|---|---|
| `web_uuid` | web entryUUID——线程 URL 中的 UUID，线程的身份 |
| `psc_uuid` | 平台 `context_uuid`（可空；取首个非空轮次的值）——空间索引使用的双重 ID |
| `url` | 线程规范 URL |
| `title` | 线程标题 |
| `mode` | 判定出的模式（`search` / `deep-research` / `computer` / `council` / `study`） |
| `author` | 作者账户显示名 |
| `export_via` | 执行导出的账户用户名——对经他账户导出的共享空间线程尤其重要 |
| `space` | `{"uuid", "title", "slug"}` 或 `null` |
| `lastUpdated` | 平台最后更新时间戳（增量同步的机器比较契约） |
| `threadAccess` | 平台访问标志 |
| `n_turns` | 轮次数 |
| `n_sources` | 全线程引文数 |
| `metadata` | API 响应中的 `thread_metadata`，原样保留 |
| `report_info` | `{"title", "file_name", "url"}` 或 `null` |
| `exported_at` | 导出时间（UTC ISO 8601） |

可选键——没有相应内容时不出现：

| 键 | 何时写入 | 内容 |
|---|---|---|
| `interruptions` | 存在非 completed 工作流（`fs_writer.py:242-244`） | `{location, kind, headline, status}` 列表；见[会话模式——中断标注](modes.zh-CN.md) |
| `answer_variants` | 检出答案重写变体（`fs_writer.py:247-252`） | 收窄判据的 `side_by_side_metadata` 定位字段；见[会话模式——答案重写变体](modes.zh-CN.md) |
| `remote_deleted` | `pplx-export sync-deleted --online` 确认远端删除 | 墓碑时间戳，就地写入，幂等（已有值不覆盖；`sync_deleted_cmd.py:215-244`）——本地归档本身保留 |

### conversation.md——简版

`render_conversation`（`render.py:641`）：标题头（模式 / 作者 / 轮次 / 引文数），
随后每轮一对 `### Query` + `### Answer`，答案完整呈现；存在时末尾附线程级后台任务附录。
这是首先该打开的文件；逐轮工作过程在 `turns/` 中。

### turns/turn_NNNN.md——完整版

`render_turn`（`render.py:596`）：每轮一个文件（`turn_0001.md` …），含完整工作
过程——步骤、工具调用、子代理运行、表格、本轮引文。线程轮数缩减时，只删除编号过高的
旧 `turn_*.md`，未变文件保留 mtime（`fs_writer.py:287-301`）。

### sources.json / sources.md

全线程引文，按 URL 去重（`fs_writer.py:270-278`）。`sources.json` 为
`{"count", "sources": [{"name", "url", "snippet", "timestamp"}]}`；`sources.md`
是同一列表的编号 Markdown 链接版。

### report.md

deep-research 的报告产物，仅在线程携带报告时写入（`fs_writer.py:308-316`）：
报告标题、原始产物文件名，随后是完整报告 Markdown。

### raw_entries.json / raw_blocks.json——原始保真

API 响应在任何解析**之前**原样落盘（`fs_writer.py:257-266`）：

- `raw_entries.json`——plain 响应：`{"thread_metadata", "entries", "background_entries"}`，
  恒存在。
- `raw_blocks.json`——schematized 响应，结构同上。`search` 线程无此文件（不抓 blocks）；
  其余四种模式均抓取，且当全部模式判别信号缺失时也兜底抓取。

这两个文件是整个归档的保真锚点：解析、渲染、登记信息都能由它们离线重建，零网络。
见[离线操作](../architecture/offline-operations.zh-CN.md)。

### assets/——产物与清单

可下载产物（computer 模式文件及 API 列出的其他资产）经 CloudFront 签名 URL 下载进
`assets/files/`；扩展名在下载时按 URL 路径、内容魔数或资产类型判定。
`assets/assets_manifest.json`（`fs_writer.py:320-330`）记录每个版本：

```json
{"count": 2, "files": [{"filename": "analysis.xlsx", "n_versions": 2,
  "versions": [{"uuid": "…", "asset_type": "XLSX_FILE", "version": "v1",
                "created_at": "…", "downloaded_to": "…"}]}]}
```

`count` 恒为**版本总数**（Σ `len(versions)`），不是文件组数——文件组数请用 `len(files)`。

## index/ 层

`web_archive/index/` 存放工具托管的状态与索引——勿手改：

| 文件 | 写入方 | 语义 |
|---|---|---|
| `library_<account>.json` | `pplx-export index`（`index_cmd.py:17-43`） | 账户全量线程索引（GraphQL）；batch / 调度 / 空间索引的输入 |
| `batch_state.json` | `BatchState`（`state.py`） | 可续传检查点：uuid → 状态（ok/error/expired/deleted）+ lastUpdated；原子写；损坏文件自动备份为 `.corrupt-<ts>` |
| `.cookies.json` | cookie 缓存（`common.py:111`、`common.py:150`） | 12 小时新鲜度的 cookie 缓存，含来源与账户邮箱；先以 `0o600` 写临时文件再原子替换（会话凭据仅所有者可读） |
| `space_<slug>.json` | `pplx-export space-index`（`spaces_cmd.py:106-167`） | 单空间线程列表，含 `context_uuid` 双重 ID 映射 |
| `space_meta.json` | `pplx-export spaces --fetch-meta`（`spaces_cmd.py:299-330`） | 空间 owner/member 缓存，重建时复用 |
| `credit_usage_<account>.json` | `pplx-export usage-backfill`（`usage_backfill_cmd.py:17`） | 逐线程额度用量（幂等、可续传，每 25 条落盘一次） |
| `cron_snippet.txt` | `pplx-export schedule`（`scheduler.py:47-77`） | cron 调用片段（绝对路径） |
| `answer_variants_log.jsonl` | `variant_log.append_registry`（`variant_log.py:76`） | 答案重写变体集中登记处，按（线程, entry）去重，幂等 |
| `logs/` | `--log-file`（`common.py:218-229`） | 完整 DEBUG 日志 |

## spaces/ 层

`pplx-export spaces` 聚合 `index/library_*.json` 重建空间索引（`spaces_cmd.py:259-389`）：
每个空间一个 `<slug>.md`（参与账户聚合、owner/member 头、线程表、导出位置回链），
外加 `spaces.json` 注册表。

!!! note "输出位置"
    `spaces/` 相对于当前工作目录写出（`spaces_cmd.py:332`）——**不**跟随 `--out`。
    勿手改：下次重建会覆盖。

## 跨天续接：按 UUID 身份的目录迁移

目录名内嵌 `lastUpdated` 日期，因此隔天续接一个线程时，朴素计算会得出**新**目录。
writer 按 UUID 身份防止重复（`thread_dir_for`，`fs_writer.py:58-72`）：

1. **查找**：`find_thread_dirs`（`fs_writer.py:74-105`）全库搜索以 `_<uuid8>` 结尾的
   目录——跨账户、跨模式。候选目录仅当其 `thread.json` 存在、可解析且 `web_uuid`
   全等时才被接受；缺失、损坏或不符的目录一律不动（宁可漏迁，不可误并）。
2. **合并**：`_merge_into`（`fs_writer.py:107-178`）把旧目录并入新目录——文件取并集
   （旧目录独有文件不丢）；同名同内容跳过；同名冲突**恒保留目标方**（语义更新的一方），
   且逐条记录日志。每个复制文件经 sha256 校验后才删除旧目录；任何失败都让旧目录
   原样保留，重试幂等。
3. **清理历史重复**：`consolidate_uuid`（`fs_writer.py:180-209`）全库合并同一 UUID 的
   重复日期目录，保留 `lastUpdated` 最大者——这是旧版本遗留重复目录的兜底手段。

同样的 UUID 严格度也保护空间索引回链：`thread.json` 缺失/损坏/不符的候选目录
一律不被链接。

## 可手改与工具托管

- **工具托管（勿手改）**：线程目录内的一切，以及 `index/`、`spaces/`、`relations/`。
  内容有问题就改工具再重生成——渲染修复走 `pplx-export re-render`，数据修复走对应的
  backfill 命令（见[维护命令](maintenance-commands.zh-CN.md)）——让每个产物都可从 raw
  复现。
- **可手改**：文档与 `web_archive/crosscheck/` 评审报告。一个用户级例外：人工抢救回的
  备选答案可记录为线程目录内的 `rewritten_answer_variant.md`——见
  [会话模式——答案重写变体](modes.zh-CN.md)。

## 另见

- [会话模式](modes.zh-CN.md)——五种模式及各自产物
- [增量同步](incremental-sync.zh-CN.md)——`lastUpdated` 如何驱动重导
- [维护命令](maintenance-commands.zh-CN.md)——re-render、backfill、sync-deleted
- [数据模型与目录契约](../architecture/data-model.zh-CN.md)——底层 dataclass
- [导出流水线](../architecture/export-pipeline.zh-CN.md)——这些文件如何写出
- [离线操作](../architecture/offline-operations.zh-CN.md)——从 `raw_*.json` 重建一切
