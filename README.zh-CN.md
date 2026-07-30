# Perplexity 命令行工具集（适用于现有订阅而非按量计费 API）

[English README](README.md)

Perplexity 对话记录导出与交互查询工具（`pplx-export` / `pplx-ask` 双命令）。
通过浏览器 cookie 直连 Perplexity REST/GraphQL API，把对话（含步骤、引文、深研报告、
computer 资产、子代理工作流）完整归档为本地 Markdown + JSON。成功导出会同时保留
原始响应与渲染产物，因此无需重抓即可离线重渲。

## 目的

除了归档历史对话之外，本项目的目的更多是让离数据更近、有更强算力的本地 agent 具备一定的 Perplexity Computer 能力，通过loop中直接访问Perplexity深度研究模式所产出的报告，获取高质量信息，以更精确地调整代码中的关键参数，同时也能更充分地利用现有的 Perplexity Max 订阅。

> 截止至7月20日，Perplexity 并未提供类Unix环境中的官方 CLI
> 我们注意到官方于7月23日提供了Computer模式中所使用的pplx工具的公开发布版本；但该工具仍是按量计费的

但它并非 Computer 模式的完整替代。有两项能力无法复制：

- 深度研究 skill 可自由指定模型；
- 模型委员会 skill 可指定多个不同模型分别深度研究、输出报告并直接横向比较。

仓库中‘/_platform_context’路径下提供了一些可能符合 Computer模式所需的系统提示词，包括深度研究模式的选择、子代理模型选择等规则。相信用户能够于本地Agent讨论出相近的工作流。

## 功能概览

- **`pplx-export`**：library 索引、单线程/批量导出（增量早停 + 断点续跑）、
  资产与用量补录、离线重渲（零网络）。
- **`pplx-ask`**：SSE 流式发问（search / deep-research / council / study
  四模式），完成后自动归档。
- **保留原始响应的归档**：成功导出会保留原始 API 响应，无需重抓即可离线重生成
  渲染产物。

## 安装

需要 Python ≥ 3.11 与 [uv](https://docs.astral.sh/uv/)：

```bash
uv tool install git+https://github.com/Yiksing/pplx-tools.git
# PyPI 镜像替代（如中国大陆网络环境）：
# uv tool install --index-url https://mirrors.aliyun.com/pypi/simple git+https://github.com/Yiksing/pplx-tools.git
```

从本地克隆安装：

```bash
uv tool install .            # 或开发模式：uv tool install --editable .
```

## 用户级配置（账户 / BOT 空间）

账户注册表与 BOT 空间外置为 TOML 配置（模板见根目录
[`config.example.toml`](config.example.toml)）：

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml   # 含个人隐私，建议仅属主可读写
# 编辑填入真实账户值
```

加载优先级：`--config PATH` > 环境变量 `PPLX_EXPORT_CONFIG` > 默认
`~/.config/pplx-export/config.toml`。

也可以让 `pplx-export init` 自动生成配置：它从浏览器会话 cookie 中发现已登录
账户，按标题匹配 BOT 空间，再以仅属主可读写权限写入 TOML。相关标志：`--force`
（覆盖已存在的文件）、`--create-bot-space [标题]`（无标题匹配时创建空间，可附显式标题）、
`--bot-title TITLE`（匹配/创建所用的空间标题，默认 `BOT`）。

## 快速上手

```bash
pplx-export index --account <用户名>      # 拉取 library 索引
pplx-export export <thread_url>           # 导出单线程
pplx-export batch --account <用户名>      # 批量（默认增量早停；--full 全量兜底）
pplx-export re-render --dry-run           # 离线重渲，零网络
pplx-ask ask "<prompt>"                   # 流式发问并自动归档
```

## 文档

完整文档（使用指南、设计文档、开发文档）：

- 本地预览：`uv run mkdocs serve`
- 文档源码：[`docs/`](docs/README.md)

MkDocs 站点中的多数页面依据当前代码与测试生成或重建；部分页面也保留了此前与
agent 讨论形成的设计背景、观察记录和决策。若文档表述与实现不一致，以当前代码
和测试为准。

## 质量门禁与自动化

每个 pull request 和会触发 Actions 的普通 `main` 推送都会运行
[`quality.yml`](.github/workflows/quality.yml)。其中的 `validate` job 会检查依赖
锁文件、审计文档契约、检查模拟 fixtures 是否残留敏感信息、运行离线测试套件，
并严格构建全部已配置的 MkDocs 语言版本。在 pull request 中，文档问题还会针对
拟议更改显示为 GitHub annotations。Pull request、普通推送与手动质量检查都会
显式提供提交基点，用于强制检查中英文是否成对变更。

[`scripts/audit_docs.py`](scripts/audit_docs.py) 提供确定性的仓库文档自动审查：
检查中英双语对应关系、本地链接与源码引用、测试与 fixture 清单、模拟 fixture
来源契约，以及机器翻译配置和 manifest。审计器与翻译管线分别由
`tests/test_audit_docs.py` 和 `tests/test_translate_docs.py` 中的隔离单元测试覆盖。

出于成本考量，所有非英文/非简体中文的生成页面自 2026-07-30 起冻结维护。
远端 [`translate-docs.yml`](.github/workflows/translate-docs.yml) 工作流已手动
禁用，因此英文和简体中文是继续维护的文档来源。冻结的生成页面仍保留在站点中，
渲染时会提示不再维护，并引导读者参考对应的英文或简体中文来源。本地检查仍会
验证冻结文件和 manifest 未被破坏，但规范来源变化时不再要求刷新这些页面。

> `main` 当前没有分支保护或仓库 ruleset。这些机制属于工作流门禁，不会阻止有
> 权限的用户直接推送；后续可在不改变验证命令的情况下启用分支保护。

## 测试

```bash
uv run pytest        # 全离线（快照 fixture 已入库，零网络）
```

## License

[GPL-3.0](LICENSE)
