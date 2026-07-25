# pplx-tool CLI 参考

Perplexity Computer 内部工具通过 `pplx-tool` 命令行分发。agent 用 `bash` 调用，
credential 用 `api_credentials` 字段注入，不直接暴露 token。

## 通用规则

- **首次使用前** 每个工具都要先跑 `pplx-tool <name> --describe`（credential `pplx-tool`）
  拿到 JSON 输入 schema，严格照 schema 传参
- **执行时** 用 `api_credentials=["pplx-tool:<tool>"]`（子命令级 scope 更小，安全）
- **一次 bash 只跑一个可执行 pplx-tool 调用**，不要串联
- 参数从 stdin 传 JSON，用 quoted heredoc 保证 shell 不改写内容：
  ```bash
  pplx-tool schedule_cron <<'JSON'
  {"cron": "0 9 * * *", "objective": "..."}
  JSON
  ```

## 常用子工具

| 子命令 | 用途 |
|---|---|
| `screenshot_page` | 截取网页保存到 workspace；返回文件路径。用户看不到，需要再调 `share_file` 才可见 |
| `save_image` | 从 URL 下载图片存到 Files 区，用户可下载 |
| `publish_website` | 部署到永久 pplx.app 子域；**调用前必须先** `load_skill(name="website-building/website-publishing")`。更新已发布站点传 site_id |
| `deploy_website` | 打包 workspace 里的 web 项目上传 S3，出私有链接。同 `project_path` 重跑就是更新 |
| `schedule_cron` | 一次性/周期任务。`run_at` 用用户本地时区，`cron` 用 UTC。**cron 频率最低 1 小时**（有编程 trigger 时 5 分钟），单会话上限 15 个 |
| `start_server` | 后台起服务，自动杀端口冲突进程 + poll 端口就绪。比 `bash(background=true)` 稳 |
| `save_custom_skill` | 保存/更新 skill 库。跨 user/space/org scope，重名冲突就换名或改更新模式 |

## 本项目实际用到的场景

- 目前**本项目主要走 `bash` + `gh`/`git`**，没用到 pplx-tool 的绝大多数子工具
- 如果后面要发**科研结果 dashboard 页**（比如全球 CHK1-6 出图站点），才会用
  `publish_website`；届时必须先 load website-building/website-publishing skill
- 定时跑批（比如每天检查本地代理进度）可用 `schedule_cron`，但要注意用户明确不希望
  agent 频繁打扰 → 只在用户显式请求时才建
