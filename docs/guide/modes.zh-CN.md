# 会话模式

Perplexity 会话有五种模式：`search` / `deep-research` / `computer` / `council` / `study`。
导出时按线程判定模式；它决定抓取哪些 API 响应、线程目录里落什么内容、以及线程进入
哪条[归档路径](archive-layout.zh-CN.md)（`<账户>/<模式>/…`）。判定结果记录在
`thread.json`（`mode` 键），并用于 `pplx-export batch --mode` 过滤。`pplx-ask`
也能以五种模式中的四种（除 `computer` 外）**创建**新线程——见 [pplx-ask](pplx-ask.zh-CN.md)。

## 五种模式一览

| 模式 | UI 名称 / 模型 | 轮次内容 | 引文 | 产物 | 抓取 schematized blocks |
|---|---|---|---|---|---|
| `search` | 「Best」（`pplx_pro`；labs 的 `STUDIO`/`pplx_beta` 也归入此） | Query + Answer，文本步骤 | 轮次级 + 全线程 `sources.*` | — | 否（无 `raw_blocks.json`） |
| `deep-research` | 「Deep research」（`pplx_alpha`，固定不可选） | 研究步骤，含 `RESEARCH_ANSWER` | 有 | `report.md`（完整报告） | 是 |
| `computer` | Computer（`pplx_asi_opus`、`pplx_asi_opus_thinking`） | 完整 `workflow_block`：旁白、工具调用、子代理 prompt/步骤、逐步引文 | 逐步 + 轮次 + 全线程 | `assets/` 多版本文件 + 子代理运行 | 是 |
| `council` | 模型委员会（`pplx_agentic_research`；默认三个模型） | `COUNCIL_RESEARCH` 步骤；各模型嵌套 `LLM_COUNCIL` 工作流折叠进 `<details>`（检索轮次、全部来源、完整单模型答案） | 单模型 + 聚合 | 多模型答案并排对比 | 是 |
| `study` | Study（`pplx_study`） | 经 blocks 提供步骤/引文（实测亦含资产） | 有 | 存在时有资产 | 是 |

## 模式如何判定

判别权威是平台自己的字段 **`entry.search_mode`**（`SEARCH_MODE_MAP`，
`normalize.py:50-59`），对全部 entries 遍历收集（`normalize.py:106-115`）。
已对官方模型配置（`GET /rest/models/config/v2`）验证：
`default_models.search=pplx_pro`（UI「Best」）、`default_models.research=pplx_alpha`
（UI「Deep research」），取值与会话模式一一对应：

| `search_mode` 取值 | 模式 |
|---|---|
| `ASI` | `computer` |
| `AGENTIC_RESEARCH` | `council` |
| `STUDY` | `study` |
| `RESEARCH` | `deep-research` |
| `SEARCH`、`STUDIO` | `search` |

冲突规则（`detect_mode`，`normalize.py:66-128`）：

- **线程内模式切换**（entries 不一致）：按特异性取最高——
  **computer > council > study > deep-research > search**（`_MODE_SPECIFICITY`，
  `normalize.py:63`）——并 `log.warning`。
- **与下游信号冲突**（步骤名 / `display_model`）：`search_mode` 胜出，
  `log.warning`（`normalize.py:120-123`）。
- **`search_mode` 完全缺失** → 走原链：URL 含 `/computer/tasks/` 或
  `metadata.mode == '4'` 或索引 mode ∈ `ASI`/`COMPUTER` → `computer`；存在
  `COUNCIL_RESEARCH` 步骤 → `council`；存在 `RESEARCH_ANSWER` 步骤 → `deep-research`；
  冗余信号 `display_model`（`DISPLAY_MODEL_MODE`，`normalize.py:32-37`）冲突时胜出；
  全部未命中 → 默认 `search`。
- **信号全灭不下 search 定论**：流水线仍兜底抓取 schematized blocks
  （`adapter.py:83-89`），平台字段漂移不会让 `raw_blocks.json` 静默丢失。

!!! note "为什么 `pplx_alpha` 不是判别依据"
    `pplx_alpha` 是 RESEARCH 专属模型——它是本分类器要判出的**目标**、而非判别证据，
    因此被刻意排除在映射表之外（`normalize.py:15-31` 注释）。

含全部分支的完整决策树：[导出流水线——模式判定](../architecture/export-pipeline.zh-CN.md)。

## 子代理负载的落点

computer/council 运行会产生后台子代理工作流。每个后台 `workflow_payload`
**恰好落在一个位置，绝不渲染两次**；用户层面的三个可能落点：

1. **锚定——落入发起轮次**：发起子代理的轮次携带相同 payload id，因此该运行内联渲染在
   这一轮的工作过程中（`turns/turn_NNNN.md`），含 prompt、步骤、答案与来源。
2. **stub 轮次——「子代理工作」小节**：10 秒完成窗口内的 `subagent_result` stub 轮次
   吸收该负载；答案不回填。
3. **线程附录——`conversation.md` 末尾**：剩余全部负载（中断的运行没有完成通知，前两级
   必然漏接）如实归档在「## 后台任务（未归入轮次）」之下——不做时间归属猜测，
   任何状态都接受。

匹配规则、数据结构与单次消费保证：
[子代理与中断](../architecture/subagents-interruptions.zh-CN.md)。

## 中断：非 COMPLETED 工作流

未完成的工作流在其渲染处内联标注——工作过程标题、子代理标题与嵌套 `<details>`
摘要。三种标注（`parsers.classify_wf_status`，`parsers.py:262-283`）：

| 标注 | 条件 | 含义 |
|---|---|---|
| `⏸ 限额中断（内容截至中断点）` | `WORKFLOW_AWAITING_NEXT_STEPS` + `locked_reason=spending_limit_exceeded` | 额度耗尽，工作流中途停摆 |
| `⏸ 中断待续` | `WORKFLOW_AWAITING_NEXT_STEPS` 且无 `locked_reason` | 已中断，可在平台上继续 |
| `⛔ 已取消` | `WORKFLOW_CANCELED` | 用户或平台取消 |

- `COMPLETED` 永不标注（健康线程零 diff）；未知的未来状态值保持静默。
- 每个被标注的情形同时登记进 `thread.json.interruptions`，形如
  `{location, kind, headline, status}`——location 形如 `turn_0007`、
  `turn_0011/subagent`、`turn_0024/subagent_stub`、`background_unassigned`
  （`parsers.py:534-582`；健康线程不出现该键）。
- **续接无需特例**：在平台上继续被中断的线程后，其 `lastUpdated` 变化，下一次增量导出
  重新抓取，工作流完成后标注自然消失。见[增量同步](incremental-sync.zh-CN.md)。

实测状态取值与分布：[API 响应与错误](../reference/api/api-responses-errors.zh-CN.md)；
状态机：[子代理与中断](../architecture/subagents-interruptions.zh-CN.md)。

## 答案重写变体（answer_variants）

平台重写答案（A/B 实验）时，被替换的变体在 API 侧不可见——只返回被选中的答案，
落选的兄弟版本仅在 `entries[].side_by_side_metadata` 留下痕迹，且之后可能被平台清除
（死链已证实：403 `VIEW_THREAD_NOT_ALLOWED`）。工具让「发生过重写」可观测：

- **登记**：收窄判据命中写入 `thread.json.answer_variants`（`fs_writer.py:247-252`；
  无命中不出现该键），并追加到集中登记处 `index/answer_variants_log.jsonl`，
  按（线程, entry）去重，幂等（`variant_log.py:76`）。
- **告警**：每次在线命中输出单行可 grep 的 WARNING `ANSWER_VARIANT_DETECTED`，
  含完整定位字段（线程 uuid/uuid8、entry_uuid、sibling_uuid、selection_status、
  experiment_role）；`re-render` 离线重新登记，仅在内容新增或变化时告警，
  全库重跑不刷屏；batch 摘要追加 ⚠ 命中数。
- **人工补归档**：兄弟变体实测是死链，备选答案通常**无法经 API 恢复**。命中后请尽快
  人工确认备选答案（平台界面、自己的记录、截图）；拿到了就记录为线程目录内的
  `rewritten_answer_variant.md`；拿不到，`thread.json.answer_variants` 加 jsonl
  登记处就是最终可追溯记录。

检测链与离线重登记：[离线操作](../architecture/offline-operations.zh-CN.md)；字段语义与
死链证据：[API 响应与错误](../reference/api/api-responses-errors.zh-CN.md)。

## 渲染保真原则

无论哪种模式，渲染遵循同一份保真契约：

- **答案完整呈现，绝不截断**——旧的 `[:4000]` 截断会切断句子，已移除
  （`render.py:645-647`）。
- **表格绝不截断**——`WORKFLOW_ITEM_TABLE` 渲染全部行列，表头与单元格中的 `|`
  和换行被转义，Markdown 结构不破坏（`render.py:211-243`）。
- **引文完整**——三个收集通道（`entry.sources` + `FINAL.web_results` +
  `WORKFLOW_ITEM_SOURCES`），按 URL 去重汇入 `sources.*`；引用过的不丢。
- **API raw JSON 是内容边界**——渲染的一切都来自 `raw_entries.json` /
  `raw_blocks.json`；API 不返回的（如被替换的答案变体）无法渲染，转而通过登记键
  呈现，绝不臆造。
- **UI 折叠处，归档全展开**——web UI 藏在折叠与点击之后的细节（computer 工作流旁白与
  工具输入输出、council 单模型运行、子代理步骤）全部完整渲染；用 `<details>`
  折叠块保持文档大纲可读且不丢信息（`render.py:46`、`render.py:404-413`）。
- **结构健壮性**——代码围栏按内容定长（`_fence_for`，`render.py:28-43`），自带围栏的
  工具输出不会让配对翻转；LaTeX 分隔符规范化为 `$$` / `$`，代码段受保护
  （`normalize_math_delims`）。

保留的原始响应如何让这一切可离线重生成：
[导出流水线](../architecture/export-pipeline.zh-CN.md)与[离线操作](../architecture/offline-operations.zh-CN.md)。

## 另见

- [归档目录结构](archive-layout.zh-CN.md)——各模式文件的落点
- [pplx-ask](pplx-ask.zh-CN.md)——以各模式创建新线程
- [增量同步](incremental-sync.zh-CN.md)——续接线程的重抓
- [导出流水线](../architecture/export-pipeline.zh-CN.md)——完整模式判定决策树
- [子代理与中断](../architecture/subagents-interruptions.zh-CN.md)——归属瀑布与状态机
- [API 响应与错误](../reference/api/api-responses-errors.zh-CN.md)——字段实测取值
