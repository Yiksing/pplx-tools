# 测试 fixtures

> English version: [README.md](README.md)

本目录包含确定性的、具有 API 结构的**模拟数据**，以及由它生成的 golden
Markdown。内容完全自包含，不需要网络或私人账户数据。

完整维护与信任边界说明见
[`docs/development/fixtures.zh-CN.md`](../../docs/development/fixtures.zh-CN.md)。

## 来源契约

<!-- audit:contract fixture-source=simulated -->

所有已提交的 fixtures 都是模拟数据：

- 不从 `web_archive/`、用户账户、实时 API 响应或私人归档复制；
- 身份、标识符、prompt、answer、工作流负载、路径与 URL 均为测试用占位内容；
- 仿照生产的字段和关系只用于覆盖代码行为；
- fixture 契约不包含原始线程 id 或私人反向映射。

“完整模式”与“精简场景”描述覆盖范围和输入大小，不描述数据来源。

## 文件

| 路径 | 作用 |
|---|---|
| `raw_entries.json` | 符合生产响应形状的模拟线程 entries |
| `raw_blocks.json` | 相关模式使用的模拟 workflow blocks |
| `thread.json` | 模拟的归档线程元数据 |
| `golden/conversation.md` + `golden/turns/turn_*.md` | 用于字节级比对的生成预期 |

占位账户、uuid5/`5cbeef00`、`toolu_`/`5crub0`、token、文本与 URL
约定都是确定性的。它们保留模拟数据内部有意建立的关系，但不表示来自线上对象。

## 清单

<!-- audit:inventory fixture-directories -->

### 完整模式模拟会话

| Fixture | 覆盖 |
|---|---|
| `search_demo` | search，单轮；R 代码围栏与行内代码 |
| `deep_research_demo` | deep research；数学定界符转换 |
| `computer_demo` | computer，七轮工作流渲染 |
| `council_demo` | council 模型委员会渲染及大型嵌套负载 |
| `study_demo` | study 模式渲染 |

### 精简模拟场景

| Fixture | 覆盖 |
|---|---|
| `scenario_computer_answer_fallback` | 从模式化 workflow block 恢复答案 |
| `scenario_subagent_fallback` | 无 background 匹配时的子代理回退 |
| `scenario_user_response` | `WORKFLOW_ITEM_USER_RESPONSE` 渲染 |
| `scenario_subagent_stub` | 无锚点 subagent-result 残桩关联 |
| `scenario_workflow_item_nested` | 嵌套 workflow item 渲染 |
| `scenario_limit_interrupted` | 额度中断与归属瀑布行为 |
| `scenario_canceled` | 已取消工作流标注 |

<!-- /audit:inventory fixture-directories -->

## 重生成 golden 产物

```bash
uv run python tests/scrub_fixtures.py
uv run python tests/scrub_fixtures.py --check
```

第一条命令规范化模拟输入，并通过生产离线 `rerender` 路径重生成
`golden/`；第二条只执行残留门禁，不写文件。

用户级配置与可选的本地 `tests/scrub_pairs.local.json` 是替换/残留检查的
安全输入，不是 fixture 来源。它们不提供场景语义，也不会让已提交的模拟数据
成为本地账户数据的衍生物。

Golden Markdown 是衍生产物。测试场景变化时修改模拟 raw JSON，并通过重生成
更新 golden，不要把 golden 当成独立真源手工编辑。
