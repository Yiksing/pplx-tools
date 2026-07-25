# 测试 fixtures

`tests/fixtures/` 为[测试套件](testing.md)提供确定性的、具有 API 结构的
**模拟数据**。输入用于模拟代表性线程与工作流结构；其渲染产物以 golden
快照形式随仓库提交。

## 来源契约

<!-- audit:contract fixture-source=simulated -->

当前已提交的 fixture 内容均为模拟数据：

- 新增或更新 fixture 时必须构造模拟数据；不得通过导入 `web_archive/`、
  用户账户数据、实时 API 响应或私人归档来填充。
- 已提交文件中的名称、身份、标识符、prompt、answer、工作流负载、路径与 URL
  均为测试用占位内容。
- JSON 只为覆盖解析器、渲染器、状态与关系行为而仿照生产响应和归档 schema。
- 仓库不提交占位符到私人标识符的反向映射。

**完整模式 fixture** 与**精简场景 fixture** 描述的是覆盖范围和输入形态，
不是数据来源；两者都是模拟数据。

## 目录契约

每个 fixture 目录包含具有原始响应形状的模拟输入；需要快照比对时还包含
一棵 `golden/` 树：

| 路径 | 作用 |
|---|---|
| `raw_entries.json` | 符合生产响应形状的模拟线程 entries |
| `raw_blocks.json` | 模拟 workflow blocks；该模式无 block 响应时缺失 |
| `thread.json` | 模拟的归档线程元数据 |
| `golden/conversation.md` + `golden/turns/turn_*.md` | 由模拟输入生成并逐字节比较的产物 |

当前确定性约定包括：

- 占位账户 `alice` / `bob`、示例身份、占位 BOT 空间与固定
  `read_write_token`；
- 带 `5cbeef00` 标记的 uuid5 派生标识符，保留模拟记录间有意建立的交叉引用；
- 带 `5crub0` 标记的定长模拟 `toolu_` 标识符；
- 通用 prompt、标题、工作流文本和文件路径；
- 已移除查询串的签名 URL。

这些约定便于发现意外混入的环境相关残留；并不表示模拟标识符来自线上对象。

## 清单

<!-- audit:inventory fixture-directories -->

### 完整模式 fixtures

每个受支持模式都有一组完整的模拟会话：

| Fixture | 覆盖 |
|---|---|
| `search_demo` | search，单轮；R 代码围栏与行内代码 |
| `deep_research_demo` | deep research；端到端数学定界符转换 |
| `computer_demo` | computer，七轮工作流渲染 |
| `council_demo` | council 模型委员会渲染及大型嵌套负载 |
| `study_demo` | study 模式渲染 |

### 精简场景 fixtures

这些是定点模拟负载，只保留某项回归需要的 entries 与关系。“精简”不表示
从真实线程提取。

| Fixture | 覆盖 |
|---|---|
| `scenario_computer_answer_fallback` | 普通 FINAL 路径不可用时从模式化 workflow block 恢复答案 |
| `scenario_subagent_fallback` | 无 background 匹配时渲染子代理标题及其自身条目 |
| `scenario_user_response` | `WORKFLOW_ITEM_USER_RESPONSE` 问答渲染 |
| `scenario_subagent_stub` | 无锚点 subagent-result 残桩的十秒关联窗口 |
| `scenario_workflow_item_nested` | 嵌套 `WORKFLOW_ITEM_WORKFLOW` 折叠块渲染 |
| `scenario_limit_interrupted` | 额度中断、归属瀑布、附录落位与禁止重复渲染 |
| `scenario_canceled` | `WORKFLOW_CANCELED` 标注 |

<!-- /audit:inventory fixture-directories -->

## 维护 fixtures

`tests/scrub_fixtures.py` 负责规范化模拟数据、通过生产离线渲染器重生成
golden，并执行残留门禁：

```bash
uv run python tests/scrub_fixtures.py
uv run python tests/scrub_fixtures.py --check
```

- **重生成**——每个 fixture 都在临时目录中通过
  `pplx_export.commands.rerender_cmd.rerender` 渲染；轮数不一致时中止。
- **确定性规范化**——占位文本、UUID、`toolu_` 值、token 与签名 URL
  均以幂等方式规范化。
- **安全输入不是数据来源**——可选的本地 `tests/scrub_pairs.local.json`
  与用户级账户配置只扩展替换和残留检查；不得把它们作为构造 fixture 场景的
  输入。
- **检查模式**——`--check` 不写文件；发现已配置残留、本地绝对路径或签名
  URL 凭证时失败。

修改模拟输入 JSON 或渲染器输出后运行维护工具；提交 fixture 变更前运行
`--check`。

## Golden 快照的权威边界

已提交的模拟 JSON 是输入真源。Golden Markdown 是衍生产物：由当前生产重渲
路径从模拟 JSON 重新生成，再提交用于字节级回归比对；不得把它作为独立真源
手工维护。

## 另见

- [测试](testing.md)——套件如何消费 fixtures
- [测试系统架构](testing-architecture.md)——回归层次与保证
- `tests/fixtures/README.zh-CN.md`——仓库内 fixture 清单
