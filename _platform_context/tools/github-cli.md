# GitHub CLI 使用参考

> **适用范围：仅 Perplexity Computer（云端代理）**。本文描述的 `api_credentials=["github"]`
> 凭证注入、`git-agent-proxy.perplexity.ai` 代理 origin、以及「禁止运行 `gh auth status`」
> 规则都是平台给云端代理注入的，**本地代理不适用**。本地代理直接用本机的 `git` 与
> GitHub PAT/SSH，走本机配置即可，不要照搬本文的 credential 写法。

**本项目版本管理与仓库交互的唯一通道（云端代理侧）**。所有 示例模型v2 / 示例项目 相关代码变更、Sessions/
文档 push 都走这条路径。

## 关键结论

- GitHub connector（`github_mcp_direct`）**不使用 MCP 工具**，只是暴露一条 notice：
  > "GitHub is available via the `gh` and `git` CLIs. Use the bash tool with
  > `api_credentials=[\"github\"]` instead of connector tools. Credentials are
  > pre-configured — do not run `gh auth status`."
- 所以本项目所有 github 调用形如：
  ```bash
  bash 工具, api_credentials=["github"], command="git push origin main"
  ```
- **不要** 运行 `gh auth status` / `gh auth login` 或以任何方式打印/检查 token —— 平
  台明确禁止

## 本仓库的实际使用模式

**仓库地址**（example-org 镜像，实际 origin 是平台代理）：
- 用户可见：`https://github.com/example-org/example-research-repo`
- push origin 走：`https://git-agent-proxy.perplexity.ai/example-org/example-research-repo.git`

**Git 作者身份**（每个 sandbox 都要重设）：
```bash
git config user.name  "example-user"
git config user.email "yiksing@users.noreply.github.com"
```

**推送惯用命令**：
```bash
cd /tmp/example_repo
git add <files>
git commit -m "<type>(<scope>): <中文标题>

<多行中文正文，含变更原因、影响面、引用文献 DOI>"
git push origin main
```

## 私有仓库创建

`gh repo create` 默认 `--private`，除非用户明确要 public（本项目所有仓库都是私有）。

## 常见操作

| 需求 | 命令 |
|---|---|
| 拉最新 | `cd /tmp/example_repo && git fetch origin && git pull --ff-only origin main` |
| 单文件历史 | `git log --oneline -- <path>` |
| 单文件 blame | `git blame <path> -L <start>,<end>` |
| 查 PR | `gh pr list --repo example-org/example-research-repo` |
| 拿远端文件（不 clone） | `gh api repos/example-org/<repo>/contents/<path> --jq .content \| base64 -d` |
| 大规模 clone | `git clone https://git-agent-proxy.perplexity.ai/example-org/<repo>.git /tmp/<local>` |

## 本项目约定（AGENTS.md 要求）

- **所有 agent 产出**（包括 subagent prompt、深研报告、审计说明）都必须 push 仓库
- commit message **中文**，遵循 conventional commits 前缀（feat/fix/docs/build/refactor/test/chore）
- 深研报告放 `Sessions/<N>_.../report/`，agent prompt 放 `Sessions/<N>_.../prompts/`
- 敏感代码修改（.F90 / .py 涉及物理量）commit body 必须给**引用文献 DOI**

## 与 GitLab 的交互（上游 示例模型v2）

- 上游是 `https://gitlab.com/kdhaynes/sib4v2_corral` （HTTPS 匿名可 clone）
- GitLab connector 是 DISCONNECTED，本项目暂不接。若要比对上游最新版：
  ```bash
  git clone https://gitlab.com/kdhaynes/sib4v2_corral.git /tmp/sib4v2_upstream
  cd /tmp/sib4v2_upstream && git log -1 --format="%H %s"
  ```
- 当前 pinned 版本：master @ `4f231c4c2439645e2a11c22a9ddda6444384cdc2`
