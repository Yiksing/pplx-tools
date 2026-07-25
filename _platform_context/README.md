# _platform_context — Perplexity 平台能力快照

本目录存档 **Perplexity Computer 平台的 skill 与底层工具能力说明**，供后续 agent
（云端 Perplexity Computer 实例与本地 agent）了解平台能力边界。

## 来源与维护

- 本目录于 **2026-07-19** 复制自 [`example-research-repo`](https://github.com/example-org/example-research-repo)
  仓库的 `_platform_context/skills/` 与 `_platform_context/tools/`（该快照最后更新于 2026-07-16）。
- 源仓库的 `current_session_context/` 与 `past_session_contexts/` 未复制：前者是该项目的
  会话淘汰上下文，后者的主存档即本仓库（`past_session_contexts/`、`sessions/`）。
- **维护责任**：Perplexity Computer 云端代理在会话中加载了此处未存档的新 skill，
  或发现已存档内容有更新时，应同步更新本目录对应文件，并在本 README 末尾
  「修订记录」倒序追加一条。本地代理不负责维护本目录。
- 若本目录与源仓库版本冲突，以较新者为准并双向同步。

## 目录说明

- **`skills/`** —— 平台技能副本，快照式存档：
  - `deep-research/` —— 深度研究模式的强制委派规则（第一步必须 run_subagent(deep_research)）
  - `explore-past-context/` —— 跨会话 memory / session 检索
  - `research-assistant/` —— 分析师式深度研究骨架
  - `model-catalog/` —— 模型选择（含 model council 多模型合成格式）
  - `office/pptx/` —— PowerPoint 生成与编辑
  - `office/pdf/` + `office/pdf/libraries/` —— PDF 生成（ReportLab / pdfplumber /
    pypdfium2 / qpdf 等）与 form-filling
  - `design-foundations/` —— 通用视觉设计基础（配色/字体/图表）
  - `create-skill/` —— 制作新 Agent Skill 的元技能（agentskills.io 规范）
  - `custom-credentials/` —— 第三方 HTTPS API 的安全凭证表单流程
  - `sales/` `marketing/` `accounting/` `legal/` —— 业务向技能（售前/营销/会计/法务），
    仅作完整性快照存档

- **`tools/`** —— 平台级底层工具/子系统能力说明（非 skill，但 agent 频繁用到）：
  - `pplx-tool.md` —— Perplexity 内部工具 CLI（screenshot_page / publish_website /
    deploy_website / schedule_cron / start_server 等）调用规范
  - `github-cli.md` —— `gh` / `git` 通过 bash 调用的规范
  - `subagents.md` —— run_subagent / message_subagent / wait_for_subagents 用法，
    含 deep-research 委派 + model council + preload_skills 传递
  - `external-connectors.md` —— list/describe/call_external_tool 三步式，含 CLI hint
    判断（GitHub 就走 CLI，不走 MCP）
  - `wide-browse-and-search.md` —— 网页信息获取工具选择树
    （fetch_url / search_web / search_vertical / browser_task / wide_browse）
  - `file-io-and-sharing.md` —— read/write/edit/glob/grep 分工 + share_file 可见性约束

### `tools/` 适用范围（重要）

`tools/` 下的文档（尤其 `github-cli.md`、`pplx-tool.md`、`external-connectors.md`、
`subagents.md`）描述的是 **Perplexity Computer（云端代理）的能力与凭证机制**，
**仅适用于云端代理**。本地代理没有这些平台注入的凭证和工具，应直接用本机的
`git` / `bash` 等，不要照搬 `api_credentials` / `pplx-tool` 用法。
`file-io-and-sharing.md` 里的 `share_file` / workspace 路径约定也只对云端代理有效。

## 修订记录

### 2026-07-19
- 从 `example-research-repo` 仓库复制 `skills/` 与 `tools/`，建立本目录
  （源快照修订记录：2026-07-03 初始快照；2026-07-16 两次增补，含 deep-research、
  model-catalog、office/pdf、tools/ 目录及 6 个业务/元技能）
