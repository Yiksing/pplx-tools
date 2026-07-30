---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/pplx-export.zh-CN.md"
translation_source_sha256: "48e7ccd6cb7514e52bc54477c307019dd6be3a45e253b325799860dcf064baaf"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# pplx-export

`pplx-export` 是歸檔 CLI：從 Perplexity 拉取對話索引、把執行緒匯出到本地歸檔，並維護衍生檢視（空間索引、cron 片段）。本頁涵蓋採集側子命令——`index`、`space-index`、`export`、`batch`、`spaces`、`sync-space`、`schedule`——外加一次性初始化命令 `init`。補全/修復類子命令見 [maintenance-commands.zh-CN.md](maintenance-commands.md)；查詢 CLI 見 [pplx-ask.zh-CN.md](pplx-ask.md)。

<a id="通用选项" data-pplx-source-anchor="true"></a>
## 通用選項

所有子命令都接受這些參數（在 `pplx_export/commands/common.py` 中統一定義）：

| 參數 | 含義 | 預設值 |
|---|---|---|
| `--account NAME` | 目標帳戶。cookie 歸屬 email 與登記 email 不符時，自動列舉瀏覽器中的各帳戶工作階段令牌完成切換 | 使用者級配置的 `default_account` |
| `--config PATH` | 使用者級配置檔（帳戶註冊表）。優先級：`--config` > 環境變數 `PPLX_EXPORT_CONFIG` > `~/.config/pplx-export/config.toml` | 預設查找鏈 |
| `--skip-auth-check` | 跳過啟動時的帳戶歸屬工作階段探測、信任當前登入，避免網路差時開頭長時間等待；`batch` 在報錯累積時會做延遲帳戶校驗——見[配置](configuration.md) | 關閉 |
| `--site NAME` | 站點配接器 | `perplexity` |
| `--out DIR` | 歸檔輸出根目錄 | `--out` > 配置 `archive_root` > `./web_archive` |
| `--cookies-from BROWSER` | 從指定瀏覽器匯入 cookie（`edge`/`chrome`/`firefox`/`safari`/`brave`…） | — |
| `--cookies FILE` | Netscape cookie 檔案或 JSON cookie 檔案 | — |
| `--transport MODE` | `cookie` = cookie 直連請求；`webbridge` = 在瀏覽器頁面上下文內發 fetch | `cookie` |
| `-v`, `--verbose` | DEBUG 輸出（請求追蹤、內部判定）；可重複 | 關 |
| `--log-file [PATH]` | 全量日誌落盤；不帶值時自動落 `<out>/index/logs/<cmd>-<timestamp>.log` | 關 |

- `--cookies-from` / `--cookies` 與 `--transport webbridge` 互斥——bridge 運行在頁面上下文中，自動帶瀏覽器 cookie。
- `pplx-export --version` 列印套件版本並退出（僅頂層，非子命令參數）。
- 帳戶登記、cookie 來源與多帳戶切換見 [configuration.zh-CN.md](configuration.md)；各檔案落盤位置見 [archive-layout.zh-CN.md](archive-layout.md)。

## init

從瀏覽器 cookie 自動發現帳戶並寫入使用者級配置——手工複製 `config.example.toml` 之外的自動方案（見 [configuration.zh-CN.md](configuration.md)）。

| 參數 | 含義 | 預設值 |
|---|---|---|
| `--force` | 覆蓋已存在的配置檔 | 關（拒絕覆蓋） |
| `--create-bot-space [标题]` | 無空間標題匹配時經 API 建立 BOT 空間（對帳戶的一次寫操作）；附顯式標題時匹配與建立均用該標題，否則標題取自 `--bot-title`；不加此標誌則 `[bot_space]` 留空寫入 | 關 |
| `--bot-title TITLE` | 既用於匹配既有空間、也用於建立時命名的空間標題 | `BOT` |
| *（通用選項適用）* | cookie 來源標誌決定帳戶發現的位置；僅對 `init`，`--config` 是**寫入**路徑（跳過 strict 配置載入） | |

關鍵行為：

- 令牌列舉：從瀏覽器庫收集各帳戶工作階段 cookie（`__Secure-pplx.session.<uid>`）；給出 `--cookies FILE` 時改掃該 cookie 檔案（完整匯出可能攜帶多個帳戶）。無可列舉令牌時，退化為僅探測當前活躍工作階段。
- 工作階段探測：每個令牌逐個請求 `GET /api/auth/session` 取得帳戶 email / 顯示名；失敗或未返回 email 的令牌 warning 跳過。
- 註冊表裝配：帳戶鍵由 email 本地部分派生（撞名加 `-2`/`-3`… 後綴）；`default_account` 取當前活躍帳戶，否則取首個發現的帳戶。
- BOT 空間：經 `list_user_collections` 按標題精確匹配（大小寫不敏感）；無匹配時 `--create-bot-space [标题]` 當場建立（顯式標題覆蓋 `--bot-title`，匹配與建立均用之），否則 `[bot_space]` 留空。
- TOML 原子寫入（暫存檔 + 改名），權限 0600；已存在的檔案不加 `--force` 絕不覆蓋。命令結尾列印一行彙總 JSON：配置路徑、帳戶鍵、預設帳戶、BOT 空間 uuid/slug。
- 模型播種（best-effort）：寫完配置後，`init` 拉取 `models/config/v2` 播種機器託管的 `[models]` 表，讓新配置即帶當前模型預設/目錄；失敗則 warning 跳過（稍後用 `pplx-ask models --refresh` 重新整理）。見[配置](configuration.md)。
- `--transport webbridge` 會被拒絕——頁面上下文通道無法列舉各帳戶令牌。

```bash
pplx-export init                          # 写入默认 ~/.config/pplx-export/config.toml
pplx-export init --create-bot-space [标题]  # 无标题匹配时创建 BOT 空间（可附自定义标题）
pplx-export init --config /path/to/config.toml --force   # 自定义路径，允许覆盖
```

## index

重新整理帳戶對話列表主索引 `index/library_<account>.json`——其他所有命令的比對基線。

| 參數 | 含義 | 預設值 |
|---|---|---|
| `--full` | 全量翻頁並整體重寫索引；復位增量計數 | 增量 |

關鍵行為：

- **預設增量**：按最新翻頁，遇到「連續一整頁（`_STOP_RUN`）已知且未變」即停，把抓到的頭部合併到既有索引上——更舊的行原樣保留（不丟失）。首次執行或無既有索引時按全量。
- **`--full`** 全量翻頁並整體重寫索引；作為定期對帳的前置。
- **增量路徑的盲區**：舊執行緒的遠端*刪除*與*空間變更*不會出現在抓取的頭部，因此看不到。刪除權威仍是 `sync-deleted --online`。索引文件記錄 `incremental_runs_since_full`；連續多次增量後會提醒你跑一次 `--full`（並配合 `sync-deleted --online`）。
- 保留 `search-mode-backfill` 寫入的 `search_mode` 富化，按 `entryUUID` 合併回來。
- 在跑 `batch`、`sync-space`、`sync-deleted` 之前先跑它——它們的比對結果取決於索引的新鮮度。

```bash
pplx-export index --account alice          # 增量刷新
pplx-export index --account alice --full   # 全量对账前置
```

## sync

高頻同步便捷入口：**增量 `index` + 增量 `batch`**，只關注對話。

| 參數 | 含義 | 預設值 |
|---|---|---|
| `--full` | 全量對帳：全量 `index` + `batch` 全掃（並執行下方刪除/空間步驟） | 關閉 |
| `--check-deleted` | 附帶 `sync-deleted --online`：核驗並標記遠端已刪除執行緒 | 關閉 |
| `--refresh-spaces` | 附帶 `spaces --fetch-meta` 與 `sync-space` | 關閉 |
| `--limit N` / `--mode X` / `--delay-min` / `--delay-max` | 透傳給 `batch` 階段 | — |

關鍵行為：

- 預設只抓新增/更新的對話，**跳過刪除檢測與空間重新整理**——高頻同步下最省。
- 刪除/空間對帳為可選（`--check-deleted` / `--refresh-spaces`）或由 `--full` 一併完成。`index` 的計數（`incremental_runs_since_full`）是兜底：到期會提醒你做一次 `--full` 對帳。

```bash
pplx-export sync --account alice                     # 只关注对话（快）
pplx-export sync --account alice --full              # 定期全量对账
pplx-export sync --account alice --check-deleted     # 顺带标记远端删除
```

## space-index

提取某空間「全部」工作階段列表——含共享空間其他成員的執行緒——寫入 `index/space_<slug>.json`。

| 參數 | 含義 | 預設值 |
|---|---|---|
| `SPACE_URL`（位置參數） | 空間頁面 URL | 必填 |
| `--transport webbridge` | 改用舊瀏覽器渲染路徑代替 REST | `cookie`（REST 直連） |

關鍵行為：

- 預設走 REST 直連：經 cookie 通路調 `list_collection_threads`，offset 分頁；行內含 `context_uuid` 與 `answer_preview`。
- `--transport webbridge` 時回退到滾動渲染空間頁面、抓取行屬性的舊路徑——REST 結構變更時的備用通道。
- 行按 `lastUpdated` 從新到舊寫盤。

```bash
pplx-export space-index "https://www.perplexity.ai/spaces/<space-slug>" --account alice
```

## export

匯出單個執行緒（URL 或裸 UUID）到歸檔目錄 `<out>/<account-folder>/<mode>/<thread-dir>/`。

| 參數 | 含義 | 預設值 |
|---|---|---|
| `THREAD`（位置參數） | 執行緒 URL 或 UUID | 必填 |
| `--force` | `lastUpdated` 未變也強制重導 | 關 |

關鍵行為：

- 歸檔副本已是最新時跳過、不寫任何檔案；`--force` 覆蓋該檢查。
- 執行緒在本機 library 索引中有行時，`lastUpdated` 取索引值（與 `batch` 同語義同格式），否則回退平台真值。
- 終態優雅登記，不拋 traceback：`ENTRY_DELETED` 在 `batch_state.json` 標記 `deleted`，`ENTRY_EXPIRED` 標記 `expired`——兩種情況下本機已有歸檔都保持原樣。
- 匯出成功會把 `ok` 寫進 `index/batch_state.json`，增量計劃據此把該執行緒計為「已匯出且未變」。
- 執行緒目錄內的檔案構成見 [archive-layout.zh-CN.md](archive-layout.md)；匯出管線本身見 [../architecture/export-pipeline.zh-CN.md](../architecture/export-pipeline.md)。

```bash
pplx-export export "https://www.perplexity.ai/search/<thread-uuid>" --account alice
```

## batch

批次匯出帳戶執行緒——日常主力命令，帶增量早停與斷點續跑。

| 參數 | 含義 | 預設值 |
|---|---|---|
| `--force` | 重導全部執行緒（終態除外） | 關 |
| `--full` | 全量掃描：未變執行緒仍跳過，但不早停 | 關 |
| `--limit N` | 只處理列表前 N 條（從新到舊） | 全部 |
| `--mode MODE` | 只匯出 `search` / `deep-research` / `computer` / `council` / `study` 執行緒 | 全部模式 |
| `--delay-min SEC` | 執行緒間隨機間隔下限 | `10` |
| `--delay-max SEC` | 執行緒間隨機間隔上限 | `20` |

關鍵行為：

- 依賴 `index/library_<account>.json`——先跑 `index`。
- 預設**增量早停**：列表從新到舊排序，尾部「已匯出且未變」的連續段整體截掉；上次中斷留下的缺口（error/未導）位於終態後綴之上，仍會被修復。`--full` 關閉早停（定期兜底或懷疑檔案有缺口時用）；`--force` 重導除終態外的全部執行緒，終態永不重試。完整語義見 [incremental-sync.zh-CN.md](incremental-sync.md)。
- `--mode` 過濾：索引行帶 `search_mode`（`search-mode-backfill` 富化的平台權威欄位）時經 `SEARCH_MODE_MAP` 精確匹配——該路徑下 `--mode search` 不再混入 deep-research/council/study 執行緒。無 `search_mode` 的行回落索引欄位啟發式：`computer` = mode `COMPUTER`；`deep-research` = displayModel `pplx_alpha`；`council` = `pplx_agentic_research`；`study` = `pplx_study`；`search` = 其餘 mode 為 `SEARCH` 的行（含上述三類——要精確排除請用對應模式單獨導）。
- 每導完一個執行緒就把狀態寫進 `index/batch_state.json`——可隨時中斷重跑。
- 鑑權快速失敗：連續 3 次 401/403 即中止（cookie 失效時退避無法自癒，空轉只會讓數百執行緒各失敗一遍）。
- 節奏：執行緒間隨機間隔 `--delay-min`–`--delay-max`；429/5xx 由傳輸層退避。詳見 [rate-limiting.zh-CN.md](rate-limiting.md)。
- 命中重寫答案變體的執行緒會登記進 `index/answer_variants_log.jsonl` 並告警，需儘快人工處置（見 [../reference/api/api-responses-errors.zh-CN.md](../reference/api/api-responses-errors.md)）。

```bash
pplx-export batch --account bob --mode deep-research --limit 50
```

## spaces

從本機 library 索引重建空間檢視索引——每空間一個 Markdown 頁面，外加 `spaces.json` 註冊表。

| 參數 | 含義 | 預設值 |
|---|---|---|
| `--fetch-meta` | 重建前先重新整理擁有者/成員元資料 | 關 |

關鍵行為：

- 不帶 `--fetch-meta` 時純本機（零網路）：跨所有 `library_*.json` 按空間 slug 聚合執行緒，含參與帳戶統計與指向已匯出執行緒目錄的反鏈。
- 輸出落到當前工作目錄的 `./spaces/`——請在包含 `web_archive/` 的目錄下執行，空間頁裡的反鏈才能正確解析。
- `--fetch-meta` 先經 `get_collection` 重新整理各空間擁有者/成員快取（每空間 1 次請求，間隔 3s）到 `index/space_meta.json`；當前帳戶無權檢視的空間，自動換可見帳戶重試（cookie 自動切換）。

```bash
pplx-export spaces --fetch-meta --account alice
```

## sync-space

把已歸檔 `thread.json` 的 `space` 欄位與當前索引對齊——純本機，零網路。

| 參數 | 含義 | 預設值 |
|---|---|---|
| *（僅通用選項；只有 `--out` 起作用）* | | |

關鍵行為：

- 前置：先跑 `index`——重新整理後的 `library_*.json` 是當前空間歸屬的真源。
- 逐執行緒比對空間 slug，有差異則就地 patch `thread.json`；前 30 條變更會記入日誌。
- 有任何變更後，自動聯動重建 `spaces/` 索引。

```bash
pplx-export index --account alice && pplx-export sync-space
```

## schedule

計算本輪增量匯出計劃，並生成可被系統 cron 直接呼叫的命令片段。

| 參數 | 含義 | 預設值 |
|---|---|---|
| *（僅通用選項）* | | |

關鍵行為：

- 拉取即時索引，按總數/新增/更新報告計劃，用的是與 `batch` 相同的早停純函數（`plan_incremental`）——見 [incremental-sync.zh-CN.md](incremental-sync.md)。
- 寫 `<out>/index/cron_snippet.txt`，內容為一條 `17 3 * * *` 行，形如 `cd '<archive-parent>' && '<abs-path-to-pplx-export>' batch --account '<account>' --out '<abs-archive-root>'`——路徑用絕對路徑並加引號，因為 cron 的 cwd 與 PATH 不可預測。可執行檔路徑經 `shutil.which` 解析，解析失敗時回退為裸命令名 `pplx-export`。
- 定時跑批按設計只跑增量；`batch --full` 作為定期兜底手動執行。

```bash
pplx-export schedule --account alice
```
