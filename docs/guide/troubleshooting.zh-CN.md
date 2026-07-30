# 故障排查

FAQ 格式：每条按 **问题 → 原因 → 修复** 组织。完整的错误语义参考（状态码、终态、
重试纪律）见[响应与错误](../reference/api/api-responses-errors.md)与
[限流与错误](../architecture/rate-limiting-errors.md)。

## 裸请求 API 遭遇 Cloudflare 403

**问题**：手工 `curl` / 脚本请求 `www.perplexity.ai` 的 REST 端点返回 403 和
Cloudflare 质询页——即使带上了从浏览器复制的 cookie——而同样的端点走工具却正常。

**原因**：Cloudflare 挡在站点前面，`cf_clearance` / `__cf_bm` 与浏览器的 TLS 指纹
绑定。裸客户端指纹不匹配，质询即触发。工具能过是因为用 Python `urllib` + 从浏览器
导入的 cookie + 桌面 Chrome `User-Agent`
（`pplx_export/core/http/cookie_transport.py:29`）。Cloudflare 在风控限流时也可能
403——那时响应带同样的质询形态。

**修复**：

- 不要绕过工具的 transport；用 `pplx-export` / `pplx-ask` 发起调用，不要写临时脚本。
- 工具内部把 HTTP 200 但非 JSON 的响应体（Cloudflare 过场页）归类为传输错误而非数据
  （`pplx_export/core/http/cookie_transport.py:133`）。
- 工具内若开始出现 403，先放慢节奏（见[限流](rate-limiting.md)）并刷新 cookie；
  持续质询则需在浏览器里重新登录。
- 注意 403 的两副面孔：Cloudflare 风控质询（放慢即可消退）与 API 级 403（cookie
  失效——立即抛出、不退避，见下一节）。设计页映射的是后者
  （[rate-limiting-errors.md](../architecture/rate-limiting-errors.md)）。

背景：[API 认证](../reference/api/api-authentication.md)。

## 401 错误 / cookie 过期

**问题**：命令因鉴权错误失败——`pplx-export` 抛 `AuthTransportError: 鉴权失败 401`，
或 `pplx-ask ask` 以 HTTP 401/403 的「更新 cookie」提示退出。

**原因**：会话 cookie 已过期或失效。`401`/`403` 被视为鉴权失败并立即抛出——不退避，
因为退避无法自愈死掉的会话（`pplx_export/core/http/cookie_transport.py:82`；
`pplx_export/core/errors.py:68`）。`batch` 在连续 3 次鉴权失败后还会 fail-fast，
避免死 cookie 烧穿整个队列。

**修复**：

1. 在浏览器里重新登录（或重新打开站点），让会话 cookie 续期。
2. 刷新工具的 cookie 缓存。`<out>/index/.cookies.json` 在 12 小时新鲜期内会被复用
   （`pplx_export/core/cookies/cache.py:22`），所以重新登录后二选一：
   - 带 `--cookies-from <browser>` 跑一次，强制从浏览器重新导入；或
   - 删除 `<out>/index/.cookies.json`，让下次运行自动重新导入。
3. 每次校验成功的运行都会重存缓存（`pplx_export/commands/common.py:150`），日常运行
   自行保持新鲜。

设置细节：[快速上手](getting-started.md) · [配置](configuration.md)。

## Linux cookie 解密

**问题**：在 Linux 上，auto-detect（或 `--cookies-from chrome` 等）读不到浏览器
cookie 库，尽管浏览器确实处于登录状态。

**机制**：Linux 上的 Chromium 系浏览器用保存在 OS keyring 中的密钥加密 cookie
数据库，运行时经 Secret Service D-Bus API 取出该密钥。`browser_cookie3` 通过纯
Python 的 `jeepney` 访问 D-Bus——它已随工具安装在 Linux 上，无需额外配置——
当没有任何 keyring 应答时回退到旧式 `peanuts` 口令，而该口令只能解开 Chrome
当初同样在无 keyring 环境下写入的 cookie。当 keyring 存在但 D-Bus 查询在传输层
本身失败时（如会话总线拒绝匿名访问），`browser_cookie3` 自身的兜底链不会生效；
工具识别该情形并绕过 keyring 重试一次，使用 Chromium 默认密码——即 Chromium
在无 keyring 可用时自己使用的密钥（`pplx_export/core/cookies/loaders.py:62-104`，
接入加载路径于 `loaders.py:136-153`）。Firefox 完全不涉及这些：其
`cookies.sqlite` 不加密。

**矩阵**：

| 层面 | 情形 | 结果 |
|---|---|---|
| 浏览器 | Firefox | 零摩擦——`cookies.sqlite` 不加密 |
| 浏览器 | Chromium + keyring 可达 | 正常——经 Secret Service 取密钥 |
| 浏览器 | Chromium + 无 keyring | `peanuts` 路径——仅当 Chrome 当初也在无 keyring 下写入才有效 |
| 浏览器 | Chromium + keyring 不可达（D-Bus 层失败） | 工具自动用 Chromium 默认密码重试——可达性与 `peanuts` 路径相同 |
| 安装方式 | 原生包 | auto-detect（browser_cookie3 内置路径） |
| 安装方式 | snap / flatpak | auto-detect——内置 profile 注册表覆盖了 `~/snap/<name>/...` 与 `~/.var/app/<app-id>/...` 下的 profile（`pplx_export/core/cookies/profiles.py:37-67`） |
| 桌面环境 | GNOME | 通常开箱即用（gnome-keyring） |
| 桌面环境 | KDE | 在 KWallet 设置中勾选 **Use KWallet for the Secret Service interface** |
| 桌面环境 | 无头 / 最小化 | 无 D-Bus session 总线 → `peanuts` 路径 |
| 发行版 | Debian / Ubuntu | 安装 `libsecret-1-0` + `gnome-keyring` |
| 发行版 | Fedora / RHEL | 安装 `libsecret` + `gnome-keyring`；最小化 / server 安装常常完全没有 keyring——最常见的失败原因 |
| 发行版 | Arch | 机制相同，仅包名不同 |

沙箱安装无需额外参数：先探测原生路径，再按注册表以显式 `cookie_file=` 探测
snap/flatpak 的 cookie 数据库（`pplx_export/core/cookies/loaders.py:155-168`）。

**场景 → 推荐通道**：

| 场景 | 推荐通道 |
|---|---|
| 装有 Firefox | `--cookies-from firefox`——零摩擦 |
| 桌面 GNOME / KDE | auto-detect 即可 |
| snap / flatpak 浏览器 | auto-detect——注册表已覆盖；否则用浏览器扩展导出 `--cookies FILE` |
| 无头服务器 | `--cookies FILE`——通用兜底；最后手段为 `--transport webbridge` |

## 导出用了错误的账户（多账户）

**问题**：归档线程是用错误账户的会话抓取的——例如 `--account alice` 的运行实际以
`bob` 拉数据，或归档里出现不属于目标账户的线程。

**原因**：同一浏览器登录多个账户时，活跃的会话令牌
（`__Secure-next-auth.session-token`）可能属于另一个账户。若目标账户的 `email`
未在用户级配置中登记，工具无法识别，只能记一条 warning。

**工具的预防机制**（`pplx_export/commands/common.py:93`）：启动时 transport 调
`GET /api/auth/session`，把实时 email 与登记值比对。不匹配时自动枚举浏览器里各账户
的会话 cookie（`__Secure-pplx.session.<user_id>`），逐个替换活跃令牌并探测 session，
直到命中目标 email（`pplx_export/commands/common.py:190`；
`pplx_export/core/cookies/loaders.py:175`）。无令牌匹配时命令带清晰报错中止——绝不以错误
账户静默继续。

**修复**：

- 在 `[accounts.<name>]` 下登记每个账户的 `email`（见[配置](configuration.md)），
  并显式传 `--account`。
- 看启动日志行 `[auth] cookie 来源 …，当前账户: …`——它在抓取任何数据前报出实时
  会话 email。
- 审计既有归档：每个线程的 `thread.json` 带 `export_via` 字段，记录执行导出的账户
  （`pplx_export/sites/perplexity/fs_writer.py:229`）。`pplx-export sync-deleted`
  也用该字段选择在线验证的账户。

机制深究：[API 认证](../reference/api/api-authentication.md) ·
[发问与账户](../architecture/ask-and-accounts.md)。

## 「找不到配置文件」——降级模式

**问题**：启动 warning 提示未找到用户级配置文件、命令以降级模式运行；或显式
`--account alice` 报错并指向 `config.example.toml`。

**原因**：三个查找位置都没有配置文件——`--config PATH`、环境变量
`PPLX_EXPORT_CONFIG`、默认 `~/.config/pplx-export/config.toml`
（`pplx_export/config.py:113`）。两种相关但不同的情形：**显式指定**的配置路径不
存在会抛 `ConfigError`；配置损坏（无法解析）一律抛 `ConfigError`——坏配置绝不
静默降级。

**降级模式的影响**：

- 账户注册表为空，cookie 归属校验跳过并 warning，命令以占位账户 `default` 运行
  （`pplx_export/commands/common.py:51`）。显式 `--account` 则直接报错。
- `pplx-ask ask` 跳过自动移入 BOT 空间（结果 JSON 中 `moved_to_bot` 保持 `false`），
  遥测携带空 user id；发问与归档本身照常工作。
- 归档落在按用户名回退的账户目录下。

**修复**：把 `config.example.toml` 复制为 `~/.config/pplx-export/config.toml`，填好
`[accounts.<name>]`（`display_name` / `email` / `user_id`）、`[bot_space]` 与
`default_account` —— 见[配置](configuration.md)。

## ENTRY_EXPIRED 与 ENTRY_DELETED 的区别

**问题**：导出或增量同步某线程时报告 `ENTRY_EXPIRED` 或 `ENTRY_DELETED`，且该线程
再也无法抓取。

**原因**：两者都以 `GET /rest/thread/<uuid>` 的 HTTP 400 返回、错误码不同，且同为
终态——线程在平台上已不存在：

| 错误码 | 含义 | 工具映射 | 终态 |
|---|---|---|---|
| `ENTRY_EXPIRED` | 平台清除了该线程（约 3 个月保留期） | `EntryExpiredError`（`pplx_export/core/errors.py:24`） | `expired` |
| `ENTRY_DELETED` | 线程被用户 / 远端主动删除（`DELETE /rest/thread/delete_thread_by_entry_uuid` 的下游表现） | `EntryDeletedError`，`EntryExpiredError` 的子类（`pplx_export/core/errors.py:30`） | `deleted` |

**对归档意味着什么**：

- 两种状态都永不重试——增量同步不会，加 `--force` 也不会。终态标记存在
  `<out>/index/batch_state.json`。
- 工具**绝不删除或移动本地归档**——仓库副本即备份。导出命令登记终态后优雅退出
  （`pplx_export/commands/export_cmd.py:51`）。
- 子类关系是刻意设计：只认识 `EntryExpiredError` 的既有路径仍会把 `ENTRY_DELETED`
  当终态处理；感知子类的路径（batch / export / sync-deleted / search-mode-backfill）
  则精确归类为 `deleted`。
- 实践要点：及时导出。过了约 3 个月的清除期，产物 / 报告源链接也不可恢复地过期。

相关：[增量同步](incremental-sync.md) · [响应与错误](../reference/api/api-responses-errors.md)。

## 无法下载的资产（`toolu_` 句柄）

**问题**：`assets/assets_manifest.json` 中部分条目的版本被标记
`"no_download_channel": true`，且 `assets/files/` 下没有对应文件。

**原因**：`toolu_` 前缀的 cloud-workspace 句柄（无 URL 形态的 DOC_FILE /
CODE_FILE / UNKNOWN）没有 API 下载通道：`GET /rest/assets/<asset_uuid>/data` 对它们返回 404
`ASSET_NOT_FOUND`，`file-repository/download` 拒绝 `file:repo/...` 句柄（400）。
这是**已知的归档完整性边界**，不是导出缺陷。`pplx-export assets-backfill` 会把这些
版本标记为 `no_download_channel` 并跳过
（`pplx_export/commands/assets_backfill_cmd.py:355`）。

**修复**：

- 目前无可下载——该标记即对此边界的有意记录。
- 内容往往有内联留存：子代理的页面抽取文本与步骤负载保存在线程的 raw JSON
  （`raw_entries.json` / `raw_blocks.json`）和渲染出的 `turns/` 里——先查那里。
- `file-repository/list-files` 已被跟踪为潜在的未来救援路径，见
  [API 发现路线图](../reference/api/api-discovery-roadmap.md)。

manifest 布局：[归档布局](archive-layout.md)。

## 命令看似卡住 / 长时间无输出

**症状**：`index` / `batch` / `export` 看似停住；外层任务管理器可能把它
当「超时」杀掉。

**原因**：几乎总是退避或在途请求等待，不是卡死。429 / 5xx / 网络错误时
传输层在尝试之间休眠——单次等待封顶 300 s（`pplx_export/core/throttle.py`，
`Throttle.backoff`）。

**现在你会看到（默认档，无需 `-v`）**：等待会以 INFO 心跳呈现。退避先打
一条起始行，随后每约 10 s 打一次倒计时（`Throttle.heartbeat_interval`）；
单个请求在响应前卡住会打「仍在等待响应」；`pplx-ask` 在深研 / 联席静默期间
会打「仍在等待响应流」：

```
22:27:24 [auth] 正在校验账户 cookie（来源 cache）…
22:27:40 退避 ~51s（连续失败 1 次，网络异常重试中）
22:27:50 仍在等待重试，剩余 ~41s
22:28:00 仍在等待重试，剩余 ~31s
```

总等待时长不变——心跳只是让它可见；随时中断都安全（状态原子落盘，下次
运行自动补缺）。`-v` / `--log-file` 仍会附带完整 DEBUG 请求追踪。

**跳过启动探测**：`index` / `batch` 会以一次会话探测开头，它遵循同样的
退避规则，所以网络差时第一段等待可能正是这一步账户校验。传
`--skip-auth-check` 可跳过它、直接开工，信任当前登录账户——见
[配置](configuration.md)。

**反模式**：把 CLI 包进带短硬超时的任务管理器（agent 后台任务、
`timeout(1)` 式 cron 包装）的同时还用 `&&` 串联多账户——第一个账户的
退避级联会烧光整个超时，后面的账户根本不会跑。一次调用一个账户、
留足预算：见[调用方运行时预算](rate-limiting.md#调用方运行时预算)。

## 日志在哪里？

**控制台**：默认 INFO 级进度；`-v` / `--verbose` 切到 DEBUG（请求追踪、内部判定）；
warning 与 error 始终显示。

**文件**：传 `--log-file` 落盘全量 DEBUG 流（`pplx_export/core/logging.py:45`）：

- `--log-file` 不带值时落 `<out>/index/logs/<cmd>-<timestamp>.log`
  （`pplx_export/commands/common.py:218`）—— 例如 `pplx-ask-ask-20260723-120000.log`。
- `--log-file PATH` 写到指定路径。

**其他有助于诊断的状态文件**（均在 `<out>/index/` 下）：

| 文件 | 内容 |
|---|---|
| `.cookies.json` | cookie 缓存（12 小时新鲜期；0o600 原子写入——属登录等价凭证，注意保密） |
| `batch_state.json` | 逐线程导出状态，含 `expired` / `deleted` 终态标记 |
| `answer_variants_log.jsonl` | 答案重写变体登记处 |
| `library_*.json` | 各账户的 library 索引快照 |

## 参见

- [快速上手](getting-started.md) —— 首次设置与 cookie 导入
- [配置](configuration.md) —— 账户、BOT 空间、降级模式
- [pplx-ask](pplx-ask.md) —— 交互式查询 CLI
- [pplx-export](pplx-export.md) —— 归档 CLI
- [限流](rate-limiting.md) —— 节奏与退避纪律
