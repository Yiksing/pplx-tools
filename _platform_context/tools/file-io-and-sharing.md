# 文件 I/O 与共享工具

## 文件操作分工

用**专用工具**而不是 bash 里的等价命令 —— 后者慢、贵、易错。

| 需求 | 专用工具 | 不要用 |
|---|---|---|
| 读文件 | `read` | cat / head / tail / sed |
| 编辑文件（原地替换字符串） | `edit` | sed / awk |
| 创建/覆盖文件 | `write` | cat heredoc / echo redirect |
| 找文件路径 | `glob` | find / ls |
| 搜文件内容 | `grep` | grep / rg |

- `read` 默认 2000 行，超大文件用 `offset` + `limit` 分批
- `edit` 的 `old_string` 必须唯一（除非 `replace_all=true`），不唯一就先扩上下文
- 二进制文件（.nc / .zip / .exe）**不能** 用 `read`

## 特殊文件类型的 `read` 行为

- **图片**：直接返回图像供 vision 分析
- **PDF**：提取文字 + 渲染页面预览（默认 20 页，用 offset/limit 翻页）
- **PPTX**：渲染幻灯片为图片（默认 20 页）

## 用户可见性（关键）

**用户默认看不到 workspace 里的任何文件**。要让用户看到必须：

- **`share_file`** —— 把 sandbox 文件发给用户
  - `name` 参数：起个人类可读标题；**更新已发过的资产用同一个 `name`** → UI 里出现
    版本切换
  - `should_validate=true`（默认）会检查文本换行、颜色对比等质量问题，agent 生成的
    资产建议开着
- **`upload_file`** —— 把文件传到 Space 文件库（**持久化**，其他成员也能看到）
  - Space 场景才用；单会话可分享用 share_file

**URL / 网页链接** 不算文件，直接写进回复文本就行（用户能点击）。

## Workspace 结构（会话级）

- 工作目录：`/home/user/workspace`（agent 用绝对路径）
- 沙盒规格：2 vCPU / 8 GB RAM / ~20 GB 磁盘
- `current_session_context/`：本会话被淘汰的历史轮次原样保存
- `past_session_contexts/`：跨会话 load_sessions 拉进来的历史
- `memory/`：用户的长期知识 wiki（"Brain"）+ notes + sessions —— **读之前先看
  `memory/knowledge/index.md`**
- `skills/<name>/`：本会话已 load 的 skill 副本
- `projects/<space_id>/knowledge/`：Space 级项目 wiki，与个人 memory 分开

## 本项目文件流转惯例

- **深研报告** 子代理写到 workspace → 主 agent read 后 `cp` 到 `/tmp/example_repo/Sessions/22_.../report/` → git commit + push
- **agent prompt** 主 agent 直接 write 到 `/tmp/example_repo/Sessions/22_.../prompts/` → commit + push
- **代码修改** 直接在 `/tmp/example_repo/` 里编辑 → commit + push
- **不 share_file 到用户** ——本项目所有产物走 git 仓库，用户在 GitHub 上看，比 chat 附件更持久

## 常见坑

- **markdown 里贴文件链接**：图片 `![](path)` 和文件 `[](path)` **在 chat 里不渲染**。
  要展示图片/文件只能 share_file
- **workspace 路径用 `file://`** 引用：不支持 —— 用 share_file 或写绝对路径到聊天正文
- **子代理产物**：子代理自己调 share_file 用户看不到，主 agent 必须自己再 share 一次
