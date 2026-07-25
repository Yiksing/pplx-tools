# 测试架构

`pplx_export` 测试体系完全离线，使用已入库的模拟数据，并以快照锁定渲染器
行为。本页说明架构与保证；当前模块清单归
[测试](../development/testing.md)维护，fixture 细节归
[测试 fixtures](../development/fixtures.md)维护。

小节沿用[架构总览](../architecture/overview.md)中的编号。

---

## 测试体系

使用 `uv run pytest tests` 运行套件。测试数量以当前运行结果报告，不作为
架构常量。

### 层次

| 层次 | 代表模块 | 契约 |
|---|---|---|
| 纯单元行为 | `test_units.py`、凭证/cookie/配置测试 | 以模拟输入隔离函数、类、校验与规范化 |
| 组件语义 | 中断、残桩工作流、答案变体与 relations 测试 | 在零网络条件下覆盖解析器、渲染器、状态与索引代码的协作 |
| 离线命令与状态行为 | backfill、删除同步、初始化与评审回归 | 对临时目录和 fake transport 运行命令路径 |
| 渲染快照 | `test_render_snapshots.py` | 将具有 API 形状的模拟 JSON 送入生产重渲路径，并将全部 Markdown 与已提交 golden 逐字节比对 |

N、V3、V4、V5 等评审编号是跨层次的可追溯元数据，不定义独立的运行架构，
与测试模块也不必一一对应。

### 快照数据流

1. 模拟 fixture 提供 `raw_entries.json`、可选 `raw_blocks.json` 与
   `thread.json`。
2. `tests/conftest.py::render_fixture` 将这些文件复制进 `tmp_path`。
3. Fixture 调用 `commands.rerender_cmd.rerender`，即生产离线重建路径。
4. 新生成的 `conversation.md` 与 `turns/turn_*.md` 和已提交的
   `golden/` 产物逐字节比较。

Golden 是生成的预期结果，不是独立数据源。任何改变产物字节的渲染器修改都会
使快照套件失败，直到修改经过审查并有意重生成 golden。

### 隔离与信任边界

- **Fixture 来源**——所有已提交的 fixture 输入都是模拟数据，不从线上账户、
  实时 API 响应、`web_archive/` 或私人归档复制。
- **网络边界**——测试使用 fake 与离线路径；已入库 fixtures 不需要凭证或网络。
- **配置边界**——autouse fixture 安装占位账户配置，开发者真实
  `~/.config` 不决定测试结果。
- **文件系统边界**——命令与迁移行为在 `tmp_path` 下运行，不以用户归档为测试目标。
- **残留边界**——`tests/scrub_fixtures.py --check` 在不修改文件的前提下拒绝
  已配置的环境相关字符串、本地绝对路径与签名 URL 凭证。

单元断言、组件语义、命令状态测试与字节级快照共同保护局部逻辑和端到端重渲契约。
