# 快速上手

从全新检出到第一份本地归档：安装两个命令、创建用户级配置、选择 cookie 通道，
并完成首次导出。

## 环境要求

- **Python ≥ 3.11**
- **[uv](https://docs.astral.sh/uv/)**——用于安装工具与运行测试
- **一个已登录 Perplexity 的桌面浏览器**——工具复用其会话 cookie；配置中不存放
  任何 token

cookie 解密使用 `browser_cookie3`。auto-detect 覆盖 Edge、Chrome、Firefox、
Safari；Brave、Chromium、Opera、Vivaldi 可经 `--cookies-from` 指定。

## 安装

无需克隆——直接从 git URL 安装：

```bash
uv tool install git+https://github.com/Yiksing/pplx-tools.git
# PyPI 镜像替代（如中国大陆网络环境）：
# uv tool install --index-url https://mirrors.aliyun.com/pypi/simple git+https://github.com/Yiksing/pplx-tools.git
```

从本地克隆安装（仓库根目录）：

```bash
uv tool install .            # 或开发模式：uv tool install --editable .
```

安装后得到两个命令：`pplx-export`（归档）与 `pplx-ask`（交互式查询）。验证：

```bash
pplx-export --version
pplx-export --help           # 总览（含示例）；每个子命令另有专属 --help
pplx-ask --help
```

`uvx --from . pplx-export` 可免安装单次运行。

## 创建用户级配置

账户注册表（显示名 / email / user_id）与 BOT 空间属个人隐私，**不入库**，外置为
TOML 文件。模板见仓库根目录 `config.example.toml`。

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml   # 含个人隐私，建议仅属主可读写
# 编辑填入真实账户值
```

1. 创建配置目录。
2. 把模板复制到默认路径。
3. `chmod 600`——文件含个人隐私，保持仅属主可读写。
4. 填写 `[accounts.<name>]`——键为账户用户名（即 thread URL / library 中的
   username）；设置 `display_name`、`email`、`user_id`，并选定 `default_account`。
5. 填写 `[bot_space]`——`pplx-ask` 发问完成后线程的集中收纳处（可经
   `pplx-ask space-create` 实建）。

**自动替代方案：**`pplx-export init` 可为你推导该文件——枚举浏览器中各账户
的会话 cookie，逐个探测 `/api/auth/session` 取得 email / 显示名，把
`default_account` 设为当前活跃账户，按标题匹配 BOT 空间，并以 0600 权限
原子写入 TOML（已存在的文件仅 `--force` 才覆盖）。

```bash
pplx-export init                     # 发现账户，写入默认配置路径
pplx-export init --create-bot-space [标题]  # 无标题匹配时创建 BOT 空间（可附自定义标题）
pplx-export init --bot-title TITLE   # 匹配/创建其他标题的空间（默认 BOT）
pplx-export init --config /path/to/config.toml   # 写入自定义路径
```

标志说明：`--force` 覆盖已存在的配置；`--create-bot-space [标题]` 在无标题匹配时
经 API 创建空间（对账户的一次写操作；附显式标题时匹配与创建均用该标题）；
`--bot-title TITLE` 同时用于匹配与创建。注意：与其他所有命令不同，`init` 的 `--config` 是**写入**路径而非
加载路径。完整说明见 [pplx-export → init](pplx-export.md#init)。

完整字段说明见[配置](configuration.md)。

**加载优先级**（从高到低）：

| # | 来源 |
|---|------|
| 1 | `--config PATH` |
| 2 | 环境变量 `PPLX_EXPORT_CONFIG` |
| 3 | `~/.config/pplx-export/config.toml`（默认） |

!!! note "配置缺失时"
    未指定 `--account` 的命令以降级模式运行——email 归属校验跳过并 warning
    （离线命令不受影响）；显式 `--account` 会报错并指向 `config.example.toml`。
    `--account` 未给时取配置中的 `default_account`。

## 选择 cookie 通道

凭证来自本机浏览器已登录的 Perplexity 会话 cookie，经 `browser_cookie3` 读取——
含多账户令牌枚举与自动切换。共四条通道：

| 通道 | 用法 | 说明 |
|------|------|------|
| auto-detect（默认） | 无需参数 | 先用 12h 新鲜缓存，再按 edge→chrome→firefox→safari 顺序探测浏览器库 |
| 指定浏览器 | `--cookies-from <browser>` | edge / chrome / firefox / safari / brave … |
| cookie 文件 | `--cookies /path/to/cookies.txt` | Netscape cookie 文件或导出的 JSON |
| WebBridge | `--transport webbridge` | 页面上下文 fetch——回退通道，需显式指定 |

Linux 下 snap 与 flatpak 安装的浏览器同样可 auto-detect——其 profile 路径已纳入
内置注册表。完整的 Linux 矩阵（keyring、桌面环境、发行版软件包）见
[故障排查 → Linux cookie 解密](troubleshooting.md#linux-cookie-解密)。

```bash
pplx-export export <thread_url>                                 # 默认：auto-detect 浏览器库
pplx-export export <thread_url> --cookies-from edge             # 指定从某个浏览器导入
pplx-export export <thread_url> --cookies /path/to/cookies.txt  # 用 cookie 文件
pplx-export export <thread_url> --transport webbridge           # WebBridge 页面上下文（显式回退）
```

取到 cookie 后会调用 `/api/auth/session` 打印当前账户邮箱，便于确认账户是否正确
——`--account` 与 cookie 账户不一致时请留意。transport/凭证设计详见
[发问与账户](../architecture/ask-and-accounts.md)。

## 首次运行

```bash
pplx-export index --account alice     # 拉取 library 索引
pplx-export export <thread_url>       # 导出单线程
pplx-export batch --account alice     # 批量（默认增量早停；--full 全量兜底）
pplx-export re-render --dry-run       # 离线重渲，零网络
```

1. **`index`** 拉取账户的 library 索引——`batch` 等账户级命令的入口。
2. **`export`** 端到端归档单个线程：将原始响应（`raw_*.json`）与 Markdown
   一并保留，之后可离线重渲。
3. **`batch`** 全库扫描：剩余线程全部已归档即提前停止（增量早停），断点续跑，
   `--full` 全量兜底。详见[增量同步](incremental-sync.md)。
4. **`re-render --dry-run`** 验证离线链路：仅凭本地 raw 文件重建
   `conversation.md` + `turns/`，零网络。去掉 `--dry-run` 才真正写盘。见
   [离线操作](../architecture/offline-operations.md)。

跑通之后，`pplx-ask ask "<prompt>"` 可流式发问并自动归档产生的线程——见
[pplx-ask](pplx-ask.md)。

## 归档落盘位置

归档默认写入 `./web_archive/`（`--out` 可覆盖）：每线程一个目录。

| 路径 | 内容 |
|------|------|
| `conversation.md`、`turns/` | 渲染后的对话 |
| `thread.json` | 线程元数据 + interruptions 登记 |
| `sources.md` / `sources.json` | 引文 |
| `report.md` | 深研 / 委员会 / study 报告 |
| `assets/` | 下载的资产（computer 模式） |
| `raw_*.json` | 保留的原始 API 响应——成功归档无需重抓即可离线重渲 |

完整目录约定见[归档布局](archive-layout.md)。

## 下一步

- 遇到问题？→ [故障排查](troubleshooting.md)
- 逐命令参考 → [pplx-export](pplx-export.md) ·
  [pplx-ask](pplx-ask.md) · [维护命令](maintenance-commands.md)
- 五种对话模式 → [模式](modes.md)
