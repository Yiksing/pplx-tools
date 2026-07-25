# 系统架构阅读地图

pplx-tools（`pplx-export` / `pplx-ask`）的机制层参考：依赖关系、运行管线、
状态机、数据契约与可靠性边界。面向任务的说明请从[使用指南](../guide/index.md)开始。

!!! note "范围与事实来源"

    本区面向接手维护项目的 agent 与工程师，解释 `pplx_export/` 的系统架构。
    行号引用使用 `file.py:NN`，均相对 `pplx_export/`。页面内容于
    2026-07-23 对照仓库核实（`__version__ = "0.1.0"`，
    `pplx_export/__init__.py:31`）；当前代码和测试仍是最终事实来源。

## 从系统地图开始

- [架构总览](overview.md)——分层结构、模块职责与真实 import 依赖图。

## 沿运行流程阅读

- [导出管线](export-pipeline.md)——抓取、原始响应保留、模式识别与 Markdown
  渲染。
- [子代理与中断](subagents-interruptions.md)——后台产物归属与中断/续跑语义。
- [pplx-ask 与多账户](ask-and-accounts.md)——流式发问和多账户 cookie 切换。

## 理解数据与可靠性

- [数据模型与目录契约](data-model.md)——模型、写入边界和磁盘归档契约。
- [限频与错误处理](rate-limiting-errors.md)——节流、退避、终态与错误分流。
- [离线运维机制](offline-operations.md)——零网络重渲、关系图重建和本地维护管线。

## 相关参考

- [Web API 参考](../reference/api/index.md)——已观察到的 REST/GraphQL 契约、响应语义与
  发现记录。
- [维护者指南](../development/index.md)——测试架构、贡献者工作流和模拟 fixture 契约。
