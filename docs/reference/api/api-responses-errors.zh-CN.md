# API 响应结构与错误语义

*本文是 Perplexity Web API 参考的一部分——全图见 [API 索引](index.md)。*

## 响应结构要点（解析纪律）

- **成功归档保留原始数据**：`raw_entries.json`（plain）与
  `raw_blocks.json`（schematized，实际抓取时）会和渲染产物一并保存，
  解析/渲染可离线重跑（`pplx-export re-render`），不重抓。
- **字段提取集中** `sites/perplexity/parsers.py`（schema 漂移只改一处）。
- 模式的识别（`normalize.detect_mode`，决策树见 [export-pipeline.md](../../architecture/export-pipeline.md)）：最高优先级信号为
  任一 entry 的 **`search_mode`** 字段（映射见 [§3.9](api-rest-endpoints.md) 末）；全灭时回退——computer = URL
  `/computer/tasks/` 或 metadata.mode=="4" 或索引 mode∈{ASI,COMPUTER}；council = 存在
  COUNCIL_RESEARCH 步骤；deep-research = 存在 RESEARCH_ANSWER 步骤（按内容，不依赖中文标签）；
  其余 search。
- computer 的 UI 全部折叠——**一律以 API 的 entries/blocks 为准**，不用 UI 文本做内容边界。
- 子代理双通道（2026-07-19 探明）：prompt 在 schematized `workflow_payload.objective_chunks`；
  步骤/结论在 plain `background_entries`；经 `workflow_payload.id`（`toolu_X`）关联。
- `WORKFLOW_ITEM_SOURCES` 项除 `sources_payload.sources`（链接列表）外常携带 `text_payload`
  （子代理对页面的提取正文/对比表，全库实测 450 处，408 处在 background 嵌套负载内）；
  同一内容会同时出现在 plain 后台 entry 的 `text` 内嵌步骤 JSON 与 schematized 嵌套负载中——
  锚定子代理经 plain 路径渲染即已保留正文（2026-07-22 全库核对 408/408 无缺失）。
- **`related_queries` / `related_query_items`（2026-07-23 定案）**：每条 entry 携带的
  **下一问 prompt 推荐**——平台为已完成答案生成的追问建议；`related_queries` 为推荐文本数组，
  `related_query_items` 为结构化项（含 uuid/upsell_type 等）。取证结论：item 的 uuid
  **不是线程 uuid**（与全库线程 uuid 交叉 0/988），推荐文本与其他线程 query 零重合——
  **暂不可解析为线程间关系**；存在「预分配线程 uuid（点击后物化）」的未验证假设。
  数据天然保留在归档 `raw_entries.json`（某归档库过半线程命中），无需额外采集动作；
  relations 图不为它建边。

## 错误与风控语义

| 现象 | 含义/处置 |
|---|---|
| 403（带 cf 挑战页） | Cloudflare 拦截（TLS 指纹/频控）——退避；urllib+浏览器 cookie 一般不触发 |
| 401 / API 层 403（无 cf 挑战页） | 会话 cookie 过期/失效——工具立即抛出、不退避；batch 连续 3 次鉴权失败即 fail-fast（需更新 cookie） |
| 429 | 频控——指数退避（工具已实现） |
| 5xx（500/502/503/504） | 服务端瞬态错误（504 常见于 Cloudflare 超时）——退避重试（工具已实现） |
| ENTRY_EXPIRED | 平台已清除（约 3 个月）——终态，不重试 |
| ENTRY_DELETED | 用户/远端已删除（同为 HTTP 400，code 不同）——终态 `deleted`，不重试 |
| `_response_type: VIEW_COLLECTION_NOT_ALLOWED`（HTTP 200） | 当前账户无权查看该空间——换可见账户重试 |
| `error_code: VIEW_THREAD_NOT_ALLOWED`（HTTP 403） | 当前账户无权查看该线程（2026-07-23 实测：sibling 变体 uuid 探测；对象存在但不可访问，非「不存在」） |
| `status:"failed"` 空数据 | 同上类（get_collection 的失败形态） |

**限频纪律（防封号，用户明确要求）**：批量线程间随机 10–20s、无并发、429/403 退避、5xx 退避重试；
翻页 ≥3s；schematized 补抓 ≥4s；空间元数据抓取 ≥3s。单线程导出 = 1–2 请求 ≈ 打开一次页面。

### 中断语义实测取值（2026-07-22，分类真源 `parsers.classify_wf_status`）

`locked_reason` 字段：出现于 `thread_metadata` / `entries[]` / `background_entries[]`
（plain 与 schematized 两侧都有）。实测唯一取值：

| locked_reason | 含义 | 实测分布 |
|---|---|---|
| `spending_limit_exceeded` | 限额中断（额度耗尽，工作流停在中断点） | 全档恰好 1 个线程（raw_entries 与 raw_blocks 两侧均有标记） |

workflow 状态字段（`workflow_block.status` 与嵌套 `workflow_payload.status` 同一枚举）实测取值：

| status | 语义 | 渲染标注（COMPLETED 不加注） |
|---|---|---|
| `WORKFLOW_COMPLETED` | 正常完成 | — |
| `WORKFLOW_AWAITING_NEXT_STEPS` | 等待下一步；配合 `locked_reason=spending_limit_exceeded` 即**限额中断**（内容截至中断点），无 locked_reason 则为中断待续 | `⏸ 限额中断（内容截至中断点）` / `⏸ 中断待续` |
| `WORKFLOW_CANCELED` | 已取消（用户/平台中止） | `⛔ 已取消` |

- `WORKFLOW_CANCELED` 实测 19 处（16 主 + 3 嵌套），分布 7 个 computer 线程
  （a5e8f481/cfca382d/f2e5957d/8417b02a/2dc5716d/356f833e/ed3714ff）。
- 注意：主 entry 锚点 payload 的 status 可能滞后（实测锚点 COMPLETED 而后台实际 CANCELED）——
  子代理真实状态以后台侧 `workflow_block.status` 为准。
- 中断的后台任务不产生 subagent_result 完成通知；未消费的后台负载由线程附录兜底
  （见 [subagents-interruptions.md](../../architecture/subagents-interruptions.md)「归属瀑布」）。
- computer 模式空答案（2026-07 双重证实，不可恢复）：computer 模式下部分轮次的答案为空，
  因为服务端本来就没有答案——API 重抓得到的数据与归档完全一致，且在 UI 上展开
  「已完成 N 步骤」折叠条触发零数据请求（纯客户端渲染，UI 与 API 同源），API 无法补救。
  这类空答案轮次中只有一部分与 `locked_reason=spending_limit_exceeded` 相关，其余在服务端没有任何原因标记。

### `side_by_side_metadata`：答案重写变体信号（2026-07-23 定案）

字段路径：`entries[].side_by_side_metadata`（plain `/rest/thread/<uuid>` 响应）。
平台对同一条 query 生成多版答案（A/B 实验或重写）时，在当前生效 entry 上留下的
唯一痕迹——**被替换的变体本体（文本/步骤/引文）不在线程 API 响应中**（真例
b2d2632b：响应仅 1 条 entry、1 个 FINAL，变体 2 完全不可见）。

观测到的键与取值（b2d2632b raw 为证，全库 2442 条 entry 扫描）：

```json
{
  "experiment_role": "override-default-model-class:qwen3_instruct-01f7f",
  "sibling_uuid": "00000000-0000-5000-8000-000000000000",
  "experiment_override": {"override-default-model-class": "qwen3_instruct"},
  "selection_status": "SELECTED",
  "execution_log": {}
}
```

| 键 | 语义（观测/假设） |
|---|---|
| `sibling_uuid` | 指向同 query 的**兄弟答案变体**（另一版 entry/context 标识）。全库 7 线程命中；**在线取证（2026-07-23）确认为死链**：双账户 `GET /rest/thread/<sibling_uuid>` 均 403 `VIEW_THREAD_NOT_ALLOWED`（非 404/ENTRY_EXPIRED——服务端识别为存在但无权查看的对象），浏览器（属主账户）打开 `/search/<sibling_uuid>` 被 SPA 重定向回首页——被替换变体不可经 sibling_uuid 恢复 |
| `selection_status` | `SELECTED` = 本 entry 的答案是被选中展示的一版；对照组实例均为 `SELECTION_STATUS_UNSPECIFIED` |
| `experiment_role` | 实验角色。对照组带 `[control]` 前缀（全库 6 例：`[control]default-model-class:gpt41` 等）；真例无前缀（`override-default-model-class:qwen3_instruct-01f7f`，即模型覆盖实验的实验组） |
| `experiment_override` | 实验覆盖参数（如 `override-default-model-class: qwen3_instruct`）；仅实验组实例观测到 |
| `execution_log` | 观测值为空对象，语义未明 |

**收窄判据**（区分「真实重写并保留双版本」与「常规 A/B 对照」）：
`sibling_uuid` 非空 且（`selection_status` 非空且非 `SELECTION_STATUS_UNSPECIFIED`，
或 `experiment_role` 无 `[control]` 前缀）→ 全库 2442 条 entry 中**仅命中 b2d2632b 一条**
（已确认的唯一真例；precision/recall 在本库均为 1，样本量 1 不能外推保证）。

工具行为：`parsers.collect_answer_variants` 提取命中条目，`adapter.get_thread`
log.warning 告警 + 写入 `thread.json.answer_variants`（无命中不出现该键）；
`re-render --thread-json` 就地增删（幂等）。时间佐证：真例 entry `created→updated`
差 53.66 s（17:13 生成后重写/选定），且重写推动了线程级 `lastUpdated`（增量重导
能触发重抓，但重抓到的响应仍只含当前生效答案，旧变体不可恢复）。

**检测日志与处置流程（2026-07-23，`sites/perplexity/variant_log.py`）**：

- **日志标记**：命中即 WARNING 级单行，统一可 grep 标记 `ANSWER_VARIANT_DETECTED`，
  含全部定位字段与处置指引，形如：
  `ANSWER_VARIANT_DETECTED thread=<全量uuid> uuid8=<8位> title="…" entry=<entry_uuid> sibling=<sibling_uuid> selection_status=SELECTED experiment_role=… | 处置：…`
  在线路径（`adapter.get_thread`）每次实际抓取命中都输出；离线 `re-render`
  **仅在登记内容新增/变化时**输出（幂等重跑不刷屏）；`batch` 末尾摘要另透出一行
  命中计数提醒（不破坏现有摘要格式）。
- **集中登记处**：`<out>/index/answer_variants_log.jsonl`（**入库文件**，不在
  gitignore 的 `logs/` 之下）——每行一条 JSON（detected_at / source=online|offline /
  web_uuid / uuid8 / title / entry_uuid / sibling_uuid / selection_status /
  experiment_role），按 (web_uuid, entry_uuid) 去重，重复导出/重渲不无限追加，
  detected_at 保留首见时间。
- **命中后建议动作**：sibling 已实证多为死链（见上表），备选答案通常**无法经 API
  补救**——尽快人工确认备选答案是否仍可获取（平台会话侧/用户记忆/截图），可获取则
  补录为线程目录下的 `rewritten_answer_variant.md` 同款人工文件；不可获取则以 `thread.json.answer_variants` +
  jsonl 登记作为最终可追溯痕迹。
