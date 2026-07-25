# 配置

pplx-export 把身份数据——账户注册表（显示名、登录 email、用户 ID）与 BOT 空间——放在仓库之外的用户级 TOML 文件中。本页说明该文件的位置、全部字段、文件缺失时的行为，以及注册表如何驱动多账户 cookie 处理。

## 为什么配置外置在仓库之外

账户注册表与 BOT 空间属个人隐私数据，**绝不提交**进仓库（`pplx_export/config.py:7-12`）。仓库只附带占位模板 `config.example.toml`；真实值写进你的私有副本。工具所需的其余内容——站点域名、API URL、默认归档根——都是代码常量（`pplx_export/config.py:50-58`），不属于用户配置。

TOML 只承载身份数据。cookie 来源与数据通路选择是每次调用的 CLI 标志，不是配置字段——见 [CLI 标志而非配置字段](#cli-标志而非配置字段)。

## 位置与加载优先级

`configure()`（`pplx_export/config.py:113`）按以下优先级解析配置路径（`pplx_export/config.py:95-110`）：

| 优先级 | 来源 | 算显式指定 |
|---|---|---|
| 1 | `--config PATH` CLI 标志 | 是 |
| 2 | 环境变量 `PPLX_EXPORT_CONFIG` | 是 |
| 3 | `~/.config/pplx-export/config.toml`（默认路径） | 否 |

「显式」影响文件缺失时的报错行为——见 [配置缺失：降级模式](#配置缺失降级模式)。两个 CLI 入口都会在参数解析后以 strict 模式重新加载（`pplx_export/cli.py:223`、`pplx_export/ask_cli.py:278`）；import 期加载（`pplx_export/config.py:174-179`）是容错的，因此仅 import 包不会因文件缺失而失败。

## 创建你的配置

!!! tip "自动替代方案"
    `pplx-export init` 可自动生成该文件——从浏览器 cookie 发现已登录账户，并以 0600 权限写入 TOML。见 [pplx-export → init](pplx-export.md#init)。

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml
```

然后编辑该副本。模板全部为占位符——照抄结构、替换每个值：

```toml
# --account 未给出时使用的默认账户（对应下方 [accounts.<名>] 的键）
default_account = "alice"

# 账户注册表：键 = 账户用户名（thread URL / library 中的 username）
[accounts.alice]
# 完整显示名：用于归档目录命名（web_archive/<显示名>/…）
display_name = "Alice Example"
# 登录 email：校验 cookie 归属
email = "alice@example.com"
# 账户 uid（thread viewed 遥测需要）
user_id = "00000000-0000-4000-8000-0000000000aa"

[accounts.bob]
display_name = "Bob Example"
email = "bob@example.com"
user_id = "00000000-0000-4000-8000-0000000000bb"

# BOT 空间：pplx-ask 发问完成后线程的集中收纳处
[bot_space]
uuid = "00000000-0000-4000-8000-0000000000b0"
slug = "bot-EXAMPLE"
```

占位风格：`alice`/`bob` 是虚构的账户用户名，email 用 `example.com`，UUID 用全零的 `00000000-0000-4000-8000-…` 形式。真实文件中表键**必须是实际账户用户名**，即 thread URL 与 library 中出现的那个。

!!! warning "保持私有"
    真实配置含个人数据（email、用户 ID）。建议权限 `0o600`；切勿提交进任何 git 仓库（`config.example.toml:4-6`）。

## 字段参考

### 顶层

| 字段 | 类型 | 含义 |
|---|---|---|
| `default_account` | string | 某个 `[accounts.<name>]` 表的键，`--account` 未给出时取用（`pplx_export/commands/common.py:84-85`）。为空/缺失 = 降级模式。 |

### `[accounts.<name>]`

每个账户一张表；`<name>` 是账户用户名。注册表加载进三张以用户名为键的 dict：`ACCOUNT_DISPLAY_NAMES`、`ACCOUNT_EMAIL`、`ACCOUNT_UID`（`pplx_export/config.py:65-75`）。

| 字段 | 类型 | 是否必需 | 含义 |
|---|---|---|---|
| `display_name` | string | 否 | 完整显示名，用于归档目录命名（`web_archive/<显示名>/…`）；缺省回退用户名本身。见[归档布局](archive-layout.md)。 |
| `email` | string | 建议 | 登录 email。transport 据此校验 cookie 归属，防止「账户 B 的导出带着账户 A 的会话」（`pplx_export/config.py:69-72`）。不匹配时自动枚举浏览器中的账户会话令牌并切换——见 [多账户 cookie 模型](#多账户-cookie-模型)。 |
| `user_id` | string | `pplx-ask` 遥测需要 | 账户 uid，thread viewed 遥测所需（`pplx_export/config.py:73-75`）。可经 `GET /api/auth/linked-accounts` 查看，该接口返回每个已登录账户的 `user_id` / `email` / `display_name`——见 [API 认证](../reference/api/api-authentication.md)。 |

### `[bot_space]`

BOT 空间是 `pplx-ask` 发问完成后线程的集中收纳处（`pplx_export/config.py:76-79`）。空间本身可经 `pplx-ask space-create` 实建（见 [pplx-ask](pplx-ask.md)），再登记到这里。

| 字段 | 类型 | 含义 |
|---|---|---|
| `uuid` | string | 空间 UUID。`pplx-ask` 把完成的线程移入此处（`pplx_export/ask_cli.py:156-158`）；为空则跳过移动步骤。 |
| `slug` | string | 空间的 URL slug。加载进 `BOT_SPACE_SLUG`（`pplx_export/config.py:79`）；运行时 CLI 不读取它——fixture 维护工具消费它，据其构建身份替换对（`tests/scrub_fixtures.py:446-447`）。 |

### CLI 标志而非配置字段

TOML 没有任何通路或 cookie 设置。这些按调用选择：

| 关注点 | 设置位置 |
|---|---|
| 配置文件路径 | `--config PATH`，或 `PPLX_EXPORT_CONFIG` |
| cookie 来源 | `--cookies-from BROWSER` / `--cookies FILE` |
| 数据通路 | `--transport cookie\|webbridge`（仅 `pplx-export`；默认 `cookie`） |

完整标志参考见 [pplx-export](pplx-export.md)。

## 配置缺失：降级模式

什么都没加载时，模块级注册表保持为空、`LOADED_CONFIG_PATH` 为 `None`（`pplx_export/config.py:83-85`）。按场景的行为（`resolve_cli_account`，`pplx_export/commands/common.py:51-90`）：

| 场景 | 行为 |
|---|---|
| 默认路径无配置，未给 `--account` | 降级模式：记录 warning，命令以占位账户（`username='default'`）运行；email 归属校验跳过。日常离线命令不受影响（`pplx_export/commands/common.py:86-90`）。 |
| 无配置，显式 `--account` | `SystemExit`，给出查找顺序并指向 `config.example.toml`（`pplx_export/commands/common.py:67-74`）。 |
| 配置已加载，`--account` 未登记 | `SystemExit`，给出已加载文件路径，要求添加 `[accounts.<name>]`（`pplx_export/commands/common.py:77-82`）。 |
| 显式路径（`--config` / 环境变量）不存在 | strict 模式抛 `ConfigError`（`pplx_export/config.py:140-146`）。 |
| 文件存在但解析失败 | 一律抛 `ConfigError`——配置损坏不应静默降级（`pplx_export/config.py:147-150`）。 |
| 未给 `--account`，配置已加载 | 取 `default_account`（`pplx_export/commands/common.py:84-85`）。 |

「离线命令」的涵盖范围及降级运行与归档的交互，详见[离线操作](../architecture/offline-operations.md)。

## 多账户 cookie 模型

多个账户同登一个浏览器时，cookie 库为**每个账户**各存一条会话 cookie，配置里的 `email` 字段告诉工具它需要哪一个：

- 每个已登录账户有一条 `__Secure-pplx.session.<uid>` cookie（`ACCOUNT_SESSION_PREFIX`，`pplx_export/core/cookies/loaders.py:104`）；`<uid>` 后缀即账户的 `user_id`。
- **当前活跃**账户就是令牌当前写在 `__Secure-next-auth.session-token` 里的那个（`ACTIVE_SESSION_COOKIE`，`pplx_export/core/cookies/loaders.py:105`）。切换账户 = 把目标账户的按账户 cookie 值写进该 cookie——无需浏览器 UI（`pplx_export/core/cookies/loaders.py:113-120`）。
- 启动时 transport 探测 `GET https://www.perplexity.ai/api/auth/session`，把返回的 email 与 `accounts.<name>.email` 比对（`pplx_export/commands/common.py:126-130`）。
- 不匹配时，`_try_switch_account`（`pplx_export/commands/common.py:190-215`）经 `list_account_tokens`（`pplx_export/core/cookies/loaders.py:108-139`，优先 `www.` 子域上的条目）枚举浏览器中全部账户令牌，逐个写进 `__Secure-next-auth.session-token` 试配，首个匹配即用它重建 transport。
- 全部不匹配时命令退出，列出两个 email 并请你先在浏览器登录目标账户（`pplx_export/commands/common.py:142-145`）——见[故障排查](troubleshooting.md)。
- 未登记 `email` 的账户不做校验直接放行，并 warning 请你自行确认浏览器登录的是正确账户（`pplx_export/commands/common.py:146-149`）。

完整切换流程与 session 端点语义见[提问与账户](../architecture/ask-and-accounts.md)与 [API 认证](../reference/api/api-authentication.md)。

## cookie 缓存

校验成功后，解析出的 cookie 会被缓存，后续运行不再碰浏览器：

| 属性 | 值 |
|---|---|
| 路径 | `<归档根>/index/.cookies.json`——跟随 `--out`（`pplx_export/commands/common.py:111`） |
| 新鲜期 | 12 小时（`CACHE_MAX_AGE_S = 12 * 3600`，`pplx_export/core/cookies/cache.py:22`）；过期或损坏的缓存按无缓存处理 |
| 内容 | `fetched_at`、`source`、`account_email`、`cookies`（`pplx_export/core/cookies/cache.py:62-66`） |
| 写入 | 原子写：临时文件以 `0o600` 创建后 `os.replace`（`pplx_export/core/cookies/cache.py:49-67`） |
| Git | 已被 `.gitignore` 覆盖（`**/index/.cookies.json`） |

cookie 解析顺序（`cookies.resolve`，`pplx_export/core/cookies/loaders.py:203-235`）：显式 `--cookies-from` → 显式 `--cookies` 文件 → 新鲜缓存 → auto-detect 浏览器（edge → chrome → firefox → safari）。每次账户校验成功后都会刷新缓存（`pplx_export/commands/common.py:150`）。

## 保护你的文件

- 对 `config.toml` 执行 `chmod 600`——它含个人数据（email、用户 ID）。
- cookie 缓存由工具以 `0o600` 写入；会话 cookie 等价于登录凭证。
- 如果你手工制作 `--cookies` 用的 cookie 文件，同样执行 `chmod 600`。

## 认证失败时

cookie 过期、自动切换找不到的账户、浏览器钥匙串权限错误及其他认证失败，见[故障排查](troubleshooting.md)。
