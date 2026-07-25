# 外部连接器（External Connectors）工作流

Perplexity Computer 通过 `list_external_tools` / `describe_external_tools` /
`call_external_tool` 三个工具连接到用户已授权的第三方服务。

## 三步式工作流

1. **发现** `list_external_tools(queries=[...])` 搜索可用连接器
   - 多词查询要拆开：`["Microsoft email", "email"]` 而不是 `["Microsoft email"]`
   - 每次尽量并行多个 keyword
   - 用 `select:<source_id>` 精确抓取
2. **查 schema** `describe_external_tools(source_id=..., tool_names=[...])`
   - **必须先 describe 再 call**，否则不知道参数名
   - 例外：`connect` 空 schema 可直接调
3. **执行** `call_external_tool(source_id=..., tool_name=..., arguments={...})`

## 连接器状态

| 状态 | 处理 |
|---|---|
| CONNECTED | 直接用 |
| DISCONNECTED | 用相关时先调该连接器的 `connect` 工具，等用户在弹窗里连 |
| QUOTA_EXHAUSTED | 简短告知用户配额用完，跳过继续 |
| OUTDATED | 若只返回 `connect` 就先重连；若返回正常工具可用，遇到权限错再让重连 |

## CLI Hint（本项目关键）

某些连接器的 `list_external_tools` 结果会带 CLI hint —— **收到 hint 就走 bash + CLI**，
不用 connector 工具。本项目里：

- **GitHub** → 走 `bash + gh/git` + `api_credentials=["github"]`（详见 `github-cli.md`）
- 其他 CLI 化的服务参考各自 hint

## 本项目当前连接器状态（2026-07-16 快照）

| Source | Status | 用途 |
|---|---|---|
| `github_mcp_direct` | CONNECTED | 走 CLI，见 github-cli.md |
| `finance` | CONNECTED | 股票/宏观数据（本项目暂未用） |
| `opticodds` | CONNECTED | 体育赔率（本项目无关） |
| `taiga__pipedream` | DISCONNECTED | 项目管理（无需连接） |
| `gitlab__pipedream` | DISCONNECTED | 上游 sib4v2_corral 是 GitLab —— 但目前用**匿名 HTTPS clone** 就够，未连 |
| `google_docs__pipedream` | DISCONNECTED | 用户没用 |
| `bitbucket__pipedream` | DISCONNECTED | 无关 |
| `google_photos__pipedream` | DISCONNECTED | 无关 |
| `airweave__pipedream` | DISCONNECTED | 无关 |

## 关键约束

- **对任何"我拿不到 X"类问题都先 `list_external_tools`**，不要凭直觉说"没权限"
- 用户 @提到某数据源（`@Statista`、`@Notion`）视为明确请求 → 先搜连接器
- 应用 URL（比如 `notion.so/...`、`docs.google.com/...`）走 browser_task 前先查连接器
- **自定义 API 密钥**：若无内建连接器，`load_skill(name="custom-credentials")`
  开安全表单，让用户在会话里直接注册凭证，不通过聊天暴露 secret

## 本项目实际经验

- 示例模型/示例项目 数据链路里没有直接可用的连接器（都是学术/研究数据）
- GitHub 是**唯一常用**连接器，靠 CLI hint 走 bash
- 深研报告在核对 URL / DOI 时不用连接器，直接 `fetch_url` + `search_web`
