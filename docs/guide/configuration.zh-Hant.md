---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/configuration.zh-CN.md"
translation_source_sha256: "7b819e8d951b62560d6b4b90885f0ebf8e82ed0313bc56d655126c24cf75045f"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# 配置

pplx-export 把身份資料——帳戶註冊表（顯示名稱、登入 email、使用者 ID）與 BOT 空間——放在倉庫之外的使用者級 TOML 檔案中。本頁說明該檔案的位置、所有欄位、檔案缺失時的行為，以及註冊表如何驅動多帳戶 cookie 處理。

<a id="为什么配置外置在仓库之外" data-pplx-source-anchor="true"></a>
## 為什麼配置外置在倉庫之外

帳戶註冊表與 BOT 空間屬個人隱私資料，**絕不提交**進倉庫（`pplx_export/config.py:7-12`）。倉庫只附帶佔位範本 `config.example.toml`；真實值寫進你的私有副本。工具所需的其餘內容——站台網域、API URL、預設歸檔根目錄——都是程式碼常數（`pplx_export/config.py:50-58`），不屬於使用者配置。

TOML 只承載身份資料。cookie 來源與資料通路選擇是每次呼叫的 CLI 標誌，不是配置欄位——見 [CLI 標誌而非配置欄位](#cli-标志而非配置字段)。

<a id="位置与加载优先级" data-pplx-source-anchor="true"></a>
## 位置與載入優先級

`configure()`（`pplx_export/config.py:113`）按以下優先級解析配置路徑（`pplx_export/config.py:95-110`）：

| 優先級 | 來源 | 算明確指定 |
|---|---|---|
| 1 | `--config PATH` CLI 標誌 | 是 |
| 2 | 環境變數 `PPLX_EXPORT_CONFIG` | 是 |
| 3 | `~/.config/pplx-export/config.toml`（預設路徑） | 否 |

「明確」影響檔案缺失時的報錯行為——見 [配置缺失：降級模式](#配置缺失降级模式)。兩個 CLI 入口都會在參數解析後以 strict 模式重新載入（`pplx_export/cli.py:223`、`pplx_export/ask_cli.py:278`）；import 期載入（`pplx_export/config.py:174-179`）是容錯的，因此僅 import 套件不會因檔案缺失而失敗。

<a id="创建你的配置" data-pplx-source-anchor="true"></a>
## 建立你的配置

!!! tip "自動替代方案"
    `pplx-export init` 可自動產生該檔案——從瀏覽器 cookie 發現已登入帳戶，並以 0600 權限寫入 TOML。見 [pplx-export → init](pplx-export.md#init)。

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml
```

然後編輯該副本。範本全部為佔位符——照抄結構、替換每個值：

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

佔位風格：`alice`/`bob` 是虛構的帳戶使用者名稱，email 用 `example.com`，UUID 用全零的 `00000000-0000-4000-8000-…` 形式。真實檔案中表鍵**必須是實際帳戶使用者名稱**，即 thread URL 與 library 中出現的那個。

!!! warning "保持私有"
    真實配置含個人資料（email、使用者 ID）。建議權限 `0o600`；切勿提交進任何 git 倉庫（`config.example.toml:4-6`）。

<a id="字段参考" data-pplx-source-anchor="true"></a>
## 欄位參考

<a id="顶层" data-pplx-source-anchor="true"></a>
### 頂層

| 欄位 | 類型 | 含義 |
|---|---|---|
| `default_account` | string | 某個 `[accounts.<name>]` 表的鍵，`--account` 未給出時取用（`pplx_export/commands/common.py:84-85`）。為空/缺失 = 降級模式。 |
| `archive_root` | string | 可選。歸檔輸出根，作為 `--out` 的回退，日常命令可省略 `--out`。優先級：`--out` > `archive_root` > `./web_archive`（`pplx_export/config.py`，載入 `ARCHIVE_ROOT`；在 `cli.py` / `ask_cli.py` 解析）。`~` 會展開。 |
| `[models]`（表） | table | **機器託管，非手寫。** 可重新整理的模型目錄，由 `pplx-ask models --refresh` 寫入、`pplx-export init` 播種；覆蓋 `pplx_export/sites/perplexity/platform.py` 的釘死兜底。鍵：`last_refreshed`（UTC）、`source_version`、`auto_refresh`（bool）、`mode_defaults`、`council_defaults`、`search_models`，及完整 `[models.catalog]`（`id → {label, provider, mode}`）。請求讀取它（以 `platform.py` 兜底）；7 天 TTL 打重新整理提醒，或 `auto_refresh = true` 時自動重新整理。回寫經 `tomlkit`（執行時依賴）round-trip，保留你的其餘表與註解，保持 `0600`。 |

### `[accounts.<name>]`

每個帳戶一張表；`<name>` 是帳戶使用者名稱。註冊表載入進三張以使用者名稱為鍵的 dict：`ACCOUNT_DISPLAY_NAMES`、`ACCOUNT_EMAIL`、`ACCOUNT_UID`（`pplx_export/config.py:65-75`）。

| 欄位 | 類型 | 是否必需 | 含義 |
|---|---|---|---|
| `display_name` | string | 否 | 完整顯示名稱，用於歸檔目錄命名（`web_archive/<显示名>/…`）；缺省回退使用者名稱本身。見[歸檔佈局](archive-layout.md)。 |
| `email` | string | 建議 | 登入 email。transport 據此校驗 cookie 歸屬，防止「帳戶 B 的匯出帶著帳戶 A 的工作階段」（`pplx_export/config.py:69-72`）。不匹配時自動列舉瀏覽器中的帳戶工作階段令牌並切換——見 [多帳戶 cookie 模型](#多账户-cookie-模型)。 |
| `user_id` | string | `pplx-ask` 遙測需要 | 帳戶 uid，thread viewed 遙測所需（`pplx_export/config.py:73-75`）。可經 `GET /api/auth/linked-accounts` 查看，該介面返回每個已登入帳戶的 `user_id` / `email` / `display_name`——見 [API 認證](../reference/api/api-authentication.md)。 |

### `[bot_space]`

BOT 空間是 `pplx-ask` 發問完成後執行緒的集中收納處（`pplx_export/config.py:76-79`）。空間本身可經 `pplx-ask space-create` 實建（見 [pplx-ask](pplx-ask.md)），再登記到這裡。

| 欄位 | 類型 | 含義 |
|---|---|---|
| `uuid` | string | 空間 UUID。`pplx-ask` 把完成的執行緒移入此處（`pplx_export/ask_cli.py:156-158`）；為空則跳過移動步驟。 |
| `slug` | string | 空間的 URL slug。載入進 `BOT_SPACE_SLUG`（`pplx_export/config.py:79`）；執行時 CLI 不讀取它——fixture 維護工具消費它，據其構建身份替換對（`tests/scrub_fixtures.py:446-447`）。 |

<a id="cli-标志而非配置字段" data-pplx-source-anchor="true"></a>
### CLI 標誌而非配置欄位

TOML 沒有任何通路或 cookie 設定。這些按呼叫選擇：

| 關注點 | 設定位置 |
|---|---|
| 配置檔案路徑 | `--config PATH`，或 `PPLX_EXPORT_CONFIG` |
| cookie 來源 | `--cookies-from BROWSER` / `--cookies FILE` |
| 資料通路 | `--transport cookie\|webbridge`（僅 `pplx-export`；預設 `cookie`） |
| 跳過啟動帳戶校驗 | `--skip-auth-check`（兩個入口）——見[多帳戶 cookie 模型](#多账户-cookie-模型) |

完整標誌參考見 [pplx-export](pplx-export.md)。

<a id="配置缺失降级模式" data-pplx-source-anchor="true"></a>
## 配置缺失：降級模式

什麼都沒載入時，模組級註冊表保持為空、`LOADED_CONFIG_PATH` 為 `None`（`pplx_export/config.py:83-85`）。按場景的行為（`resolve_cli_account`，`pplx_export/commands/common.py:51-90`）：

| 場景 | 行為 |
|---|---|
| 預設路徑無配置，未給 `--account` | 降級模式：記錄 warning，命令以佔位帳戶（`username='default'`）執行；email 歸屬校驗跳過。日常離線命令不受影響（`pplx_export/commands/common.py:86-90`）。 |
| 無配置，明確 `--account` | `SystemExit`，給出查詢順序並指向 `config.example.toml`（`pplx_export/commands/common.py:67-74`）。 |
| 配置已載入，`--account` 未登記 | `SystemExit`，給出已載入檔案路徑，要求添加 `[accounts.<name>]`（`pplx_export/commands/common.py:77-82`）。 |
| 明確路徑（`--config` / 環境變數）不存在 | strict 模式拋 `ConfigError`（`pplx_export/config.py:140-146`）。 |
| 檔案存在但解析失敗 | 一律拋 `ConfigError`——配置損壞不應靜默降級（`pplx_export/config.py:147-150`）。 |
| 未給 `--account`，配置已載入 | 取 `default_account`（`pplx_export/commands/common.py:84-85`）。 |

「離線命令」的涵蓋範圍及降級執行與歸檔的互動，詳見[離線操作](../architecture/offline-operations.md)。

<a id="多账户-cookie-模型" data-pplx-source-anchor="true"></a>
## 多帳戶 cookie 模型

多個帳戶同登一個瀏覽器時，cookie 庫為**每個帳戶**各存一條工作階段 cookie，配置裡的 `email` 欄位告訴工具它需要哪一個：

- 每個已登入帳戶有一條 `__Secure-pplx.session.<uid>` cookie（`ACCOUNT_SESSION_PREFIX`，`pplx_export/core/cookies/loaders.py:171`）；`<uid>` 後綴即帳戶的 `user_id`。
- **目前活躍**帳戶就是令牌當前寫在 `__Secure-next-auth.session-token` 裡的那個（`ACTIVE_SESSION_COOKIE`，`pplx_export/core/cookies/loaders.py:172`）。切換帳戶 = 把目標帳戶的按帳戶 cookie 值寫進該 cookie——無需瀏覽器 UI（`pplx_export/core/cookies/loaders.py:180-187`）。
- 啟動時 transport 探測 `GET https://www.perplexity.ai/api/auth/session`，把返回的 email 與 `accounts.<name>.email` 比對（`pplx_export/commands/common.py:126-130`）。
- 不匹配時，`_try_switch_account`（`pplx_export/commands/common.py:190-215`）經 `list_account_tokens`（`pplx_export/core/cookies/loaders.py:175-206`，優先 `www.` 子網域上的條目）列舉瀏覽器中全部帳戶令牌，逐個寫進 `__Secure-next-auth.session-token` 試配，首個匹配即用它重建 transport。
- 全部不匹配時命令退出，列出兩個 email 並請你先在瀏覽器登入目標帳戶（`pplx_export/commands/common.py:142-145`）——見[故障排除](troubleshooting.md)。
- 未登記 `email` 的帳戶不做校驗直接放行，並 warning 請你自行確認瀏覽器登入的是正確帳戶（`pplx_export/commands/common.py:146-149`）。

完整切換流程與 session 端點語義見[提問與帳戶](../architecture/ask-and-accounts.md)與 [API 認證](../reference/api/api-authentication.md)。

**跳過校驗（`--skip-auth-check`）。** 上面的啟動工作階段探測，用幾秒（網路差時甚至
數分鐘）換來「帳戶 B 當 A 用」的歸屬保護。當你確定瀏覽器登入的就是目標帳戶時，
`--skip-auth-check`（`pplx-export` 與 `pplx-ask` 共用）會完全跳過這次探測、直接
開工（`pplx_export/commands/common.py`，`make_transport`）：

- 啟動時不發 `GET /api/auth/session`，網路抖動不再在首個真實請求前造成長時間
  靜默等待（現已有心跳）。
- 工具信任目前登入的帳戶；上面的啟動 email 歸屬校驗與多帳戶自動切換都不執行。
- **延遲安全網**：`batch` 中，通用匯出錯誤累計（3 次失敗）後，會做一次性帳戶
  校驗並告知結果——cookie 失效、帳戶與目標不符、或帳戶正常（說明報錯源於
  網路 / 速率限制而非鑑權）（`pplx_export/commands/common.py`，`report_account_status`；
  `pplx_export/commands/batch_cmd.py`）。
- **權衡**：延遲校驗能抓到 cookie 失效，但抓不到**帳戶有效但用錯**卻能無錯匯出
  的情況——用 `--skip-auth-check` 即由你自行確保登入的是目標帳戶。

適合在已知登入正確時做快速、無人值守的執行；若你依賴啟動歸屬保護或自動切換
帳戶，則不要用它。

<a id="cookie-缓存" data-pplx-source-anchor="true"></a>
## cookie 快取

校驗成功後，解析出的 cookie 會被快取，後續執行不再碰瀏覽器：

| 屬性 | 值 |
|---|---|
| 路徑 | `<归档根>/index/.cookies.json`——跟隨 `--out`（`pplx_export/commands/common.py:111`） |
| 新鮮期 | 12 小時（`CACHE_MAX_AGE_S = 12 * 3600`，`pplx_export/core/cookies/cache.py:22`）；過期或損壞的快取按無快取處理 |
| 內容 | `fetched_at`、`source`、`account_email`、`cookies`（`pplx_export/core/cookies/cache.py:62-66`） |
| 寫入 | 原子寫：暫存檔以 `0o600` 建立後 `os.replace`（`pplx_export/core/cookies/cache.py:49-67`） |
| Git | 已被 `.gitignore` 覆蓋（`**/index/.cookies.json`） |

cookie 解析順序（`cookies.resolve`，`pplx_export/core/cookies/loaders.py:270-302`）：明確 `--cookies-from` → 明確 `--cookies` 檔案 → 新鮮快取 → auto-detect 瀏覽器（edge → chrome → firefox → safari）。每次帳戶校驗成功後都會重新整理快取（`pplx_export/commands/common.py:150`）。

<a id="保护你的文件" data-pplx-source-anchor="true"></a>
## 保護你的檔案

- 對 `config.toml` 執行 `chmod 600`——它含個人資料（email、使用者 ID）。
- cookie 快取由工具以 `0o600` 寫入；工作階段 cookie 等於登入憑證。
- 如果你手工製作 `--cookies` 用的 cookie 檔案，同樣執行 `chmod 600`。

<a id="认证失败时" data-pplx-source-anchor="true"></a>
## 認證失敗時

cookie 過期、自動切換找不到的帳戶、瀏覽器鑰匙圈權限錯誤及其他認證失敗，見[故障排除](troubleshooting.md)。
