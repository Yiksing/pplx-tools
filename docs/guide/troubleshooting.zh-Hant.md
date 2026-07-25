---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/troubleshooting.zh-CN.md"
translation_source_sha256: "7257dc1ef6951872e07601249b586695343feae30b436b684f087cafe9e8da2d"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="故障排查" data-pplx-source-anchor="true"></a>
# 故障排除

FAQ 格式：每條按 **問題 → 原因 → 修復** 組織。完整的錯誤語義參考（狀態碼、終態、
重試紀律）見[回應與錯誤](../reference/api/api-responses-errors.md)與
[限流與錯誤](../architecture/rate-limiting-errors.md)。

<a id="裸请求-api-遭遇-cloudflare-403" data-pplx-source-anchor="true"></a>
## 裸請求 API 遭遇 Cloudflare 403

**問題**：手工 `curl` / 腳本請求 `www.perplexity.ai` 的 REST 端點返回 403 和
Cloudflare 質詢頁——即使帶上了從瀏覽器複製的 cookie——而同樣的端點走工具卻正常。

**原因**：Cloudflare 擋在站點前面，`cf_clearance` / `__cf_bm` 與瀏覽器的 TLS 指紋
綁定。裸客戶端指紋不匹配，質詢即觸發。工具能過是因為用 Python `urllib` + 從瀏覽器
導入的 cookie + 桌面 Chrome `User-Agent`
（`pplx_export/core/http/cookie_transport.py:29`）。Cloudflare 在風控限流時也可能
403——那時回應帶同樣的質詢形態。

**修復**：

- 不要繞過工具的 transport；用 `pplx-export` / `pplx-ask` 發起呼叫，不要寫臨時腳本。
- 工具內部把 HTTP 200 但非 JSON 的回應體（Cloudflare 過場頁）歸類為傳輸錯誤而非資料
  （`pplx_export/core/http/cookie_transport.py:133`）。
- 工具內若開始出現 403，先放慢節奏（見[限流](rate-limiting.md)）並重新整理 cookie；
  持續質詢則需在瀏覽器裡重新登入。
- 注意 403 的兩副面孔：Cloudflare 風控質詢（放慢即可消退）與 API 級 403（cookie
  失效——立即拋出、不退避，見下一節）。設計頁映射的是後者
  （[rate-limiting-errors.md](../architecture/rate-limiting-errors.md)）。

背景：[API 認證](../reference/api/api-authentication.md)。

<a id="401-错误-cookie-过期" data-pplx-source-anchor="true"></a>
## 401 錯誤 / cookie 過期

**問題**：命令因鑑權錯誤失敗——`pplx-export` 拋 `AuthTransportError: 鉴权失败 401`，
或 `pplx-ask ask` 以 HTTP 401/403 的「更新 cookie」提示退出。

**原因**：會話 cookie 已過期或失效。`401`/`403` 被視為鑑權失敗並立即拋出——不退避，
因為退避無法自癒死掉的會話（`pplx_export/core/http/cookie_transport.py:82`；
`pplx_export/core/errors.py:68`）。`batch` 在連續 3 次鑑權失敗後還會 fail-fast，
避免死 cookie 燒穿整個佇列。

**修復**：

1. 在瀏覽器裡重新登入（或重新開啟站點），讓會話 cookie 續期。
2. 重新整理工具的 cookie 快取。`<out>/index/.cookies.json` 在 12 小時新鮮期內會被複用
   （`pplx_export/core/cookies/cache.py:22`），所以重新登入後二選一：
   - 帶 `--cookies-from <browser>` 跑一次，強制從瀏覽器重新導入；或
   - 刪除 `<out>/index/.cookies.json`，讓下次執行自動重新導入。
3. 每次校驗成功的執行都會重存快取（`pplx_export/commands/common.py:150`），日常執行
   自行保持新鮮。

設定細節：[快速上手](getting-started.md) · [設定](configuration.md)。

## Linux cookie 解密

**問題**：在 Linux 上，auto-detect（或 `--cookies-from chrome` 等）讀不到瀏覽器
cookie 庫，儘管瀏覽器確實處於登入狀態。

**機制**：Linux 上的 Chromium 系瀏覽器用保存在 OS keyring 中的金鑰加密 cookie
資料庫，執行時經 Secret Service D-Bus API 取出該金鑰。`browser_cookie3` 透過純
Python 的 `jeepney` 存取 D-Bus——它已隨工具安裝在 Linux 上，無需額外設定——
當沒有任何 keyring 應答時回退到舊式 `peanuts` 口令，而該口令只能解開 Chrome
當初同樣在無 keyring 環境下寫入的 cookie。Firefox 完全不涉及這些：其
`cookies.sqlite` 不加密。

**矩陣**：

| 層面 | 情形 | 結果 |
|---|---|---|
| 瀏覽器 | Firefox | 零摩擦——`cookies.sqlite` 不加密 |
| 瀏覽器 | Chromium + keyring 可達 | 正常——經 Secret Service 取金鑰 |
| 瀏覽器 | Chromium + 無 keyring | `peanuts` 路徑——僅當 Chrome 當初也在無 keyring 下寫入才有效 |
| 安裝方式 | 原生套件 | auto-detect（browser_cookie3 內建路徑） |
| 安裝方式 | snap / flatpak | auto-detect——內建 profile 註冊表覆蓋了 `~/snap/<name>/...` 與 `~/.var/app/<app-id>/...` 下的 profile（`pplx_export/core/cookies/profiles.py:37-67`） |
| 桌面環境 | GNOME | 通常開箱即用（gnome-keyring） |
| 桌面環境 | KDE | 在 KWallet 設定中勾選 **Use KWallet for the Secret Service interface** |
| 桌面環境 | 無頭 / 最小化 | 無 D-Bus session 匯流排 → `peanuts` 路徑 |
| 發行版 | Debian / Ubuntu | 安裝 `libsecret-1-0` + `gnome-keyring` |
| 發行版 | Fedora / RHEL | 安裝 `libsecret` + `gnome-keyring`；最小化 / server 安裝常常完全沒有 keyring——最常見的失敗原因 |
| 發行版 | Arch | 機制相同，僅套件名不同 |

沙箱安裝無需額外參數：先探測原生路徑，再按註冊表以顯式 `cookie_file=` 探測
snap/flatpak 的 cookie 資料庫（`pplx_export/core/cookies/loaders.py:89-101`）。

**場景 → 推薦通道**：

| 場景 | 推薦通道 |
|---|---|
| 裝有 Firefox | `--cookies-from firefox`——零摩擦 |
| 桌面 GNOME / KDE | auto-detect 即可 |
| snap / flatpak 瀏覽器 | auto-detect——註冊表已覆蓋；否則用瀏覽器擴充功能匯出 `--cookies FILE` |
| 無頭伺服器 | `--cookies FILE`——通用兜底；最後手段為 `--transport webbridge` |

<a id="导出用了错误的账户多账户" data-pplx-source-anchor="true"></a>
## 匯出用了錯誤的帳戶（多帳戶）

**問題**：歸檔執行緒是用錯誤帳戶的會話抓取的——例如 `--account alice` 的執行實際以
`bob` 拉資料，或歸檔裡出現不屬於目標帳戶的執行緒。

**原因**：同一瀏覽器登入多個帳戶時，活躍的會話權杖
（`__Secure-next-auth.session-token`）可能屬於另一個帳戶。若目標帳戶的 `email`
未在使用者級設定中登記，工具無法識別，只能記一條 warning。

**工具的預防機制**（`pplx_export/commands/common.py:93`）：啟動時 transport 調
`GET /api/auth/session`，把即時 email 與登記值比對。不匹配時自動列舉瀏覽器裡各帳戶
的會話 cookie（`__Secure-pplx.session.<user_id>`），逐個替換活躍權杖並探測 session，
直到命中目標 email（`pplx_export/commands/common.py:190`；
`pplx_export/core/cookies/loaders.py:108`）。無權杖匹配時命令帶清晰報錯中止——絕不以錯誤
帳戶靜默繼續。

**修復**：

- 在 `[accounts.<name>]` 下登記每個帳戶的 `email`（見[設定](configuration.md)），
  並顯式傳 `--account`。
- 看啟動日誌行 `[auth] cookie 来源 …，当前账户: …`——它在抓取任何資料前報出即時
  會話 email。
- 稽核既有歸檔：每個執行緒的 `thread.json` 帶 `export_via` 欄位，記錄執行匯出的帳戶
  （`pplx_export/sites/perplexity/fs_writer.py:229`）。`pplx-export sync-deleted`
  也用該欄位選擇線上驗證的帳戶。

機制深究：[API 認證](../reference/api/api-authentication.md) ·
[發問與帳戶](../architecture/ask-and-accounts.md)。

<a id="找不到配置文件降级模式" data-pplx-source-anchor="true"></a>
## 「找不到設定檔」——降級模式

**問題**：啟動 warning 提示未找到使用者級設定檔、命令以降級模式執行；或顯式
`--account alice` 報錯並指向 `config.example.toml`。

**原因**：三個查詢位置都沒有設定檔——`--config PATH`、環境變數
`PPLX_EXPORT_CONFIG`、預設 `~/.config/pplx-export/config.toml`
（`pplx_export/config.py:113`）。兩種相關但不同的情形：**顯式指定**的設定路徑不
存在會拋 `ConfigError`；設定損壞（無法解析）一律拋 `ConfigError`——壞設定絕不
靜默降級。

**降級模式的影響**：

- 帳戶註冊表為空，cookie 歸屬校驗跳過並 warning，命令以佔位帳戶 `default` 執行
  （`pplx_export/commands/common.py:51`）。顯式 `--account` 則直接報錯。
- `pplx-ask ask` 跳過自動移入 BOT 空間（結果 JSON 中 `moved_to_bot` 保持 `false`），
  遙測攜帶空 user id；發問與歸檔本身照常工作。
- 歸檔落在按使用者名稱回退的帳戶目錄下。

**修復**：把 `config.example.toml` 複製為 `~/.config/pplx-export/config.toml`，填好
`[accounts.<name>]`（`display_name` / `email` / `user_id`）、`[bot_space]` 與
`default_account` —— 見[設定](configuration.md)。

<a id="entry_expired-与-entry_deleted-的区别" data-pplx-source-anchor="true"></a>
## ENTRY_EXPIRED 與 ENTRY_DELETED 的區別

**問題**：匯出或增量同步某執行緒時報告 `ENTRY_EXPIRED` 或 `ENTRY_DELETED`，且該執行緒
再也無法抓取。

**原因**：兩者都以 `GET /rest/thread/<uuid>` 的 HTTP 400 返回、錯誤碼不同，且同為
終態——執行緒在平台上已不存在：

| 錯誤碼 | 含義 | 工具映射 | 終態 |
|---|---|---|---|
| `ENTRY_EXPIRED` | 平台清除了該執行緒（約 3 個月保留期） | `EntryExpiredError`（`pplx_export/core/errors.py:24`） | `expired` |
| `ENTRY_DELETED` | 執行緒被使用者 / 遠端主動刪除（`DELETE /rest/thread/delete_thread_by_entry_uuid` 的下游表現） | `EntryDeletedError`，`EntryExpiredError` 的子類（`pplx_export/core/errors.py:30`） | `deleted` |

**對歸檔意味著什麼**：

- 兩種狀態都永不重試——增量同步不會，加 `--force` 也不會。終態標記存在
  `<out>/index/batch_state.json`。
- 工具**絕不刪除或移動本地歸檔**——倉庫副本即備份。匯出命令登記終態後優雅退出
  （`pplx_export/commands/export_cmd.py:51`）。
- 子類關係是刻意設計：只認識 `EntryExpiredError` 的既有路徑仍會把 `ENTRY_DELETED`
  當終態處理；感知子類的路徑（batch / export / sync-deleted / search-mode-backfill）
  則精確歸類為 `deleted`。
- 實踐要點：及時匯出。過了約 3 個月的清除期，產物 / 報告來源連結也不可恢復地過期。

相關：[增量同步](incremental-sync.md) · [回應與錯誤](../reference/api/api-responses-errors.md)。

<a id="无法下载的资产toolu_-句柄" data-pplx-source-anchor="true"></a>
## 無法下載的資產（`toolu_` 句柄）

**問題**：`assets/assets_manifest.json` 中部分條目的版本被標記
`"no_download_channel": true`，且 `assets/files/` 下沒有對應檔案。

**原因**：`toolu_` 前綴的 cloud-workspace 句柄（無 URL 形態的 DOC_FILE /
CODE_FILE / UNKNOWN）沒有 API 下載通道：`GET /rest/assets/<asset_uuid>/data` 對它們返回 404
`ASSET_NOT_FOUND`，`file-repository/download` 拒絕 `file:repo/...` 句柄（400）。
這是**已知的歸檔完整性邊界**，不是匯出缺陷。`pplx-export assets-backfill` 會把這些
版本標記為 `no_download_channel` 並跳過
（`pplx_export/commands/assets_backfill_cmd.py:356`）。

**修復**：

- 目前無可下載——該標記即是對此邊界的有意記錄。
- 內容往往有內聯留存：子代理的頁面抽取文字與步驟負載儲存在執行緒的 raw JSON
  （`raw_entries.json` / `raw_blocks.json`）和渲染出的 `turns/` 裡——先查那裡。
- `file-repository/list-files` 已被追蹤為潛在的未來救援路徑，見
  [API 發現路線圖](../reference/api/api-discovery-roadmap.md)。

manifest 佈局：[歸檔佈局](archive-layout.md)。

<a id="日志在哪里" data-pplx-source-anchor="true"></a>
## 日誌在哪裡？

**主控台**：預設 INFO 級進度；`-v` / `--verbose` 切到 DEBUG（請求追蹤、內部判定）；
warning 與 error 始終顯示。

**檔案**：傳 `--log-file` 落盤全量 DEBUG 流（`pplx_export/core/logging.py:45`）：

- `--log-file` 不帶值時落 `<out>/index/logs/<cmd>-<timestamp>.log`
  （`pplx_export/commands/common.py:218`）—— 例如 `pplx-ask-ask-20260723-120000.log`。
- `--log-file PATH` 寫到指定路徑。

**其他有助於診斷的狀態檔案**（均在 `<out>/index/` 下）：

| 檔案 | 內容 |
|---|---|
| `.cookies.json` | cookie 快取（12 小時新鮮期；0o600 原子寫入——屬登入等價憑證，注意保密） |
| `batch_state.json` | 逐執行緒匯出狀態，含 `expired` / `deleted` 終態標記 |
| `answer_variants_log.jsonl` | 答案重寫變體登記處 |
| `library_*.json` | 各帳戶的 library 索引快照 |

<a id="参见" data-pplx-source-anchor="true"></a>
## 參見

- [快速上手](getting-started.md) —— 首次設定與 cookie 導入
- [設定](configuration.md) —— 帳戶、BOT 空間、降級模式
- [pplx-ask](pplx-ask.md) —— 互動式查詢 CLI
- [pplx-export](pplx-export.md) —— 歸檔 CLI
- [限流](rate-limiting.md) —— 節奏與退避紀律
