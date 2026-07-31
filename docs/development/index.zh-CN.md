# 维护者指南

在不削弱归档保真度或测试隔离性的前提下修改 pplx-tools 所需的契约与工作流。

## 选择对应文档

- [测试体系架构](testing-architecture.md)——测试分层、信任边界和离线快照提供的
  保证。
- [测试实践](testing.md)——当前测试清单与贡献者工作流。
- [Fixtures 与快照](fixtures.md)——模拟数据来源、目录约定、golden 生成和残留检查。

## 提交约定

- 每个提交只聚焦一个关注点。提交信息准确描述 diff 的实际改动——不多也不少。
- 跨关注点的工作拆分为独立提交。例如质量门禁改动、代理边界改动（skills、
  `AGENTS.md`）和文档批量更新各自作为单独的提交落盘。
- 规范文档页面与其 `.zh-CN.md` 对应文件属于同一关注点，按文档配对契约放在
  同一提交内。
- 每个提交都能独立通过 `uv run pytest -q`，保持历史可审阅、可二分定位。

## 本地质量闭环

```bash
uv run python scripts/audit_docs.py
uv run python tests/scrub_fixtures.py --check
uv run pytest tests
uv run mkdocs build --strict
git diff --check
```

Fixture 输入是确定性的模拟数据，不来自真实账户、实时 API 响应、`web_archive/`
或任何私有归档。
