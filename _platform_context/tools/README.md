# Platform Tools 参考（Perplexity Computer）

本目录归档**平台级工具/子系统**的能力说明，与 `../skills/` 里的技能片段互补。技能是流程指南，
本目录是"底层能力清单"—— agent 在本项目里频繁用到的、非 skill 化的能力。

内容基于本会话（2026-07 示例项目-示例链 主线）系统提示 + 会话经验整理，未来 agent 可以此为
基线，若发现新版本平台指令与之冲突，以最新系统提示为准。

## 索引

- **`pplx-tool.md`** —— Perplexity 内部工具 CLI（screenshot_page / save_image /
  publish_website / deploy_website / schedule_cron / save_custom_skill / start_server
  等）的调用规范
- **`github-cli.md`** —— GitHub `gh` / `git` 通过 bash 调用的规范（本项目用来 push
  仓库、审 PR、跨机器同步 commit 的主要通道）
- **`subagents.md`** —— run_subagent / message_subagent / wait_for_subagents 的
  用法约定，含 deep-research 强制委派、model-council 多模型评议、preload_skills 传递
- **`external-connectors.md`** —— list_external_tools / describe_external_tools /
  call_external_tool 三步式外部连接器工作流，与 CLI hint（比如 GitHub 就走 CLI）判断标准
- **`wide-browse-and-search.md`** —— wide_browse（20+ 站点批量浏览需 confirm_action）、
  search_web / search_vertical / fetch_url / browser_task 的选择树
- **`file-io-and-sharing.md`** —— read / write / edit / glob / grep / bash 的分工，
  share_file 用户可见性约束，upload_file 空间文件持久化

## 编辑约定

若平台后续版本新增 skill 或工具，按下列规则更新：

- **新增 skill** → 拷贝到 `../skills/<name>/` 保留完整目录结构
- **新增底层工具** → 在本目录建 `<tool>.md`，并把它加进上面的索引
- **修订** → 在文件末尾加"## 修订记录"区段，按日期倒序追加，不删旧内容
