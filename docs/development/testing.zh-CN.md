# 测试

测试套件位于 `tests/`（在 `pplx_export` 包之外），完全离线运行。API 形状的
输入是随仓库提交于 `tests/fixtures/` 的确定性模拟数据；测试不依赖在线服务，
也不依赖真实的用户级配置。

本页负责维护当前测试模块清单与贡献流程。回归设计见
[测试系统架构](testing-architecture.md)，输入数据契约见
[测试 fixtures](fixtures.md)。

## 运行测试

```bash
uv run pytest tests
```

pytest 是已声明的开发依赖。测试套件保证：

- **零网络**——模拟输入已入库；面向网络的路径由 fake、`tmp_path` 和
  `monkeypatch` 覆盖。
- **不读真实用户配置**——`tests/conftest.py` 会在导入任何生产模块前创建
  进程级临时配置并覆盖 `PPLX_EXPORT_CONFIG`。随后每项测试获得独立的
  `alice` / `bob` 占位配置，结束后恢复进程级占位配置。子进程回归还会验证：
  即使调用方配置不存在或已经损坏，测试收集也不会失败。
- **快速反馈**——本项目于 2026-07-25 从 32 个 `test_*.py` 模块观测到
  435 项测试；本地验证中的完整运行约为 13–25 秒。数量是带日期的仓库快照，
  会随开发增长。

常用选择：

| 命令 | 效果 |
|---|---|
| `uv run pytest tests` | 完整套件 |
| `uv run pytest tests/test_units.py` | 单个模块 |
| `uv run pytest tests -k snapshot` | node id 匹配 `snapshot` 的测试 |
| `uv run pytest tests -x -q` | 首次失败即停止，安静输出 |
| `uv run pytest --collect-only -q` | 刷新收集用例数量 |

## 当前模块清单

清单已于 **2026-07-27** 对照仓库同步：

<!-- audit:inventory test-modules -->

| 功能族 | 模块 | 用途 |
|---|---|---|
| 渲染快照 | `test_render_snapshots.py` | 重渲全部模拟的完整模式与精简场景 fixtures，并与已提交产物逐字节比对 |
| 核心与共享工具 | `test_units.py` | 状态、节流、规划、规范化、资产命名、模式判定、安全路径及跨领域回归 |
| 文档契约、skill 与本地化 | `test_agent_skills.py`<br/>`test_audit_docs.py`<br/>`test_translate_docs.py` | 仓库本地 skill 契约，以及针对只读文档审计器和机器翻译管线的隔离微型仓库测试 |
| 配置、认证与初始化 | `test_config_external.py`<br/>`test_cookie_profiles.py`<br/>`test_credential.py`<br/>`test_init.py` | 外置配置隔离、cookie 来源配置、凭证选择与初始化 |
| 渲染与工作流语义 | `test_interruptions.py`<br/>`test_stub_workflows.py`<br/>`test_answer_variants.py`<br/>`test_answer_variant_logging.py`<br/>`test_relations.py` | 工作流归属、中断状态、答案变体、审计日志与关系边 |
| 离线归档与索引维护 | `test_search_mode_backfill.py`<br/>`test_sync_deleted.py`<br/>`test_status.py` | 富化、续跑/幂等行为、跨账户删除判定、终态，以及离线状态账/变更报告的分层输出 |
| 评审回归 | 下表所列 17 个 `test_fix_*.py` 模块 | 源自评审发现的修复；模块名保留评审 lineage |

### 评审回归 lineage

评审编号解释回归测试为何存在，但不是测试套件的主架构。映射明确允许多对多：
一个模块可覆盖多个发现，一个发现也可能在既有专题模块中增加用例。

| Lineage | 专用模块 |
|---|---|
| N 轮评审 | `test_fix_n01_inline_assets.py`、`test_fix_n02_spaces_link.py`、`test_fix_n03_n12.py`、`test_fix_n04_cookies.py`、`test_fix_n05_n06_n09.py`、`test_fix_n07_usage_checkpoint.py`、`test_fix_n08_throttle_overflow.py`、`test_fix_n10_table_header.py`、`test_fix_n11_batch_total.py` |
| V3 轮评审 | `test_fix_v301_nested_sources_text.py`、`test_fix_v305_export_products.py` |
| V4 轮评审 | `test_fix_v401_thread_dir_migration.py`、`test_fix_v402_manifest_count.py`、`test_fix_v403_handle_assets_idempotency.py`、`test_fix_v405_ask_post_steps.py` |
| V5 轮评审 | `test_fix_v5_review.py`，以及既有专题模块中的定点增补 |
| V6 轮评审 | `test_fix_v6_atomic_writes.py` |
| Harness 轮评审 | `test_fix_h01_ci_residue_report.py` |

<!-- /audit:inventory test-modules -->

各模块的 docstring 仍是对应发现的旧行为、修正行为与回归边界的权威说明。

## 快照测试如何复用生产重渲路径

快照测试不会另行实现一套渲染器：

1. `tests/conftest.py` 中的 `render_fixture` 把 fixture 的模拟
   `raw_entries.json`、可选 `raw_blocks.json` 与 `thread.json` 复制到临时目录。
2. 它调用 `pplx_export.commands.rerender_cmd.rerender`，即
   `pplx-export re-render` 使用的同一函数。
3. `rendered` fixture 工厂返回新鲜输出与 fixture 中已提交的 `golden/` 目录。
4. 测试逐字节比较 `conversation.md` 和全部 `turns/turn_*.md`。

除字节相等外还有内容不变式：答案不得退化成空占位符 `(无)`，`{'type': ...`
一类 dict-repr 残留不得泄漏到渲染文本。

## 新增测试

- **既有逻辑**——向对应专题模块加测试。使用 `tmp_path`、fake 与
  `monkeypatch`；不得访问网络或真实 `~/.config`。
- **缺陷回归**——优先加入对应专题模块。仅当保留评审 lineage 明显改善可追溯性时，
  新建 `test_fix_<lineage>_<slug>.py`；不要假定一个发现对应一个模块。
- **渲染回归**——新增或精简一个模拟 fixture，用维护工具重生成 golden，
  再将其登记到 `test_render_snapshots.py` 或增加场景专用断言。

遵循相邻代码风格：类型标注、`from __future__ import annotations` 与双语模块
docstring。

## 另见

- [测试 fixtures](fixtures.md)——模拟输入、golden 产物与维护契约
- [测试系统架构](testing-architecture.md)——测试层次与回归保证
- [离线操作](../architecture/offline-operations.md)——快照测试复用的生产重渲路径
