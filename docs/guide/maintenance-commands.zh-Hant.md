---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/maintenance-commands.zh-CN.md"
translation_source_sha256: "ed280b2fa84c7dfed83da45f6fa05dbee6191c9ce3542ffaca92686cb1fab5fc"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="维护命令" data-pplx-source-anchor="true"></a>
# 維護命令

`pplx-export` 的維護類子命令負責讓既有歸檔保持健康：渲染層修復後重渲頁面、補全資產/積分用量/模式元數據、給遠端已刪除執行緒打墓碑標記、重建關係圖。多數命令離線優先；其線上階段遵循與 `batch` 相同的限頻紀律（見 [rate-limiting.zh-CN.md](rate-limiting.md)）。所有命令都接受[通用選項](pplx-export.md)（`--account`、`--out`、`--cookies-from`、`--transport` 等）。

- 本地歸檔保留原則：任何維護命令都不刪除、不移動已歸檔的執行緒內容——歸檔即備份。
- 離線命令（`re-render`、`relations`、`sync-space`、不帶 `--fetch-meta` 的 `spaces`，以及下文各命令的默認階段）完全不需要數據通路；見 [../architecture/offline-operations.zh-CN.md](../architecture/offline-operations.md)。

## re-render

從歸檔的原始 JSON（`raw_entries.json` / `raw_blocks.json`）重新生成 `conversation.md` 與 `turns/`——零網路，其餘檔案一律不動。

| 參數 | 含義 | 預設值 |
|---|---|---|
| `--limit N` | 只處理前 N 個執行緒目錄 | 全部 |
| `--dry-run` | 只列出將處理的目錄，不寫檔案 | 關 |
| `--thread-json` | 同時就地增刪 `thread.json` 的 `interruptions` 與 `answer_variants` 鍵 | 關 |

關鍵行為：

- 用與匯出相同的管線離線重建 turns：解析、按 `created_us` 排序、引文去重；computer/council 額外掛 workflow blocks、子代理映射與未消費後臺附錄。
- 只（重）寫 `conversation.md` 與 `turns/turn_*.md`；`sources*`、`assets/`、`report.md`、`thread.json` 保持原樣。編號高於當前輪數的殘留 `turn_*.md` 會被刪除——除此之外不動，未變檔案保留 mtime。
- `--thread-json` 僅在內容有變化時寫盤；`answer_variants` 新增/變化時告警 `ANSWER_VARIANT_DETECTED` 並追加登記 `index/answer_variants_log.jsonl`（冪等重跑不刷屏）。
- 沒有 `raw_entries.json` 的執行緒目錄跳過並計數。

```bash
pplx-export re-render --limit 20 --thread-json --dry-run
```

## assets-backfill

補救歸檔時未取得簽名 URL 的資產——三段式補救：補抓 blocks、離線內聯提取、可選線上重新整理。

| 參數 | 含義 | 預設值 |
|---|---|---|
| `--fetch-blocks` | 先補抓缺失的 `raw_blocks.json` 及其帶簽名 URL 資產（線上） | 關 |
| `--online` | 啟用缺失/失效資產的線上重新整理 | 關（僅離線內聯提取，零請求） |
| `--limit N` | 只處理前 N 個執行緒目錄 | 全部 |

關鍵行為：

- 默認階段（離線，零請求）：從 `raw_blocks.json` 提取內聯資產（`ASSET_DIFF` / `CODE_ASSET`）落盤為 `assets/files/*.md`，並把雲工作區句柄類（`DOC_FILE` / `CODE_FILE` / `UNKNOWN`——暫無下載通道）登記進 `assets/assets_manifest.json`。冪等：已知記錄按 uuid → file_handle 查重；同名多版本檔案追加 uuid 短前綴，重跑不衝突。
- `--fetch-blocks`（線上）：補抓 deep-research/computer/council/study 執行緒缺失的 `raw_blocks.json` 及其可下載資產；執行緒按帳戶目錄分組，每帳戶惰性構建配接器（cookie 自動切換），執行緒間隔 3s。
- `--online`：對 manifest 中 `downloaded_to` 缺失/失效的版本，經 `/rest/assets/<uuid>/data` 取新鮮簽名 URL（API 串行，間隔 3s），再從 CDN 重下（6 執行緒並發、無延遲——CDN 非 API）。404 `ASSET_NOT_FOUND` 置 `asset_expired` 終態標記；跨帳戶 403 換歸檔所屬帳戶重試一次。
- 每次寫回都把 manifest 的 `count` 重算為版本總數。

```bash
pplx-export assets-backfill --fetch-blocks --online --limit 30 --account alice
```

## usage-backfill

補全帳戶全部已歸檔執行緒的積分用量記錄（`credits/thread-usage`），寫入 `index/credit_usage_<account>.json`。

| 參數 | 含義 | 預設值 |
|---|---|---|
| `--limit N` | 只處理前 N 個執行緒 | 全部 |

關鍵行為：

- 每個已歸檔執行緒一次 GET（`thread_id` 取執行緒的 `psc_uuid`），間隔 3s；冪等——輸出檔案中已記錄的執行緒跳過。
- 403（`thread_usage_forbidden`，即跨帳戶執行緒）記為 `error` 且永不重試；其他失敗留待下輪。每處理 25 個執行緒中途落盤一次。
- 多帳戶：每個帳戶用 `--account` 各跑一次——cookie 在運行間自動切換。

```bash
pplx-export usage-backfill --account alice
```

## search-mode-backfill

給 `index/library_<account>.json` 的每一行補平台權威 `search_mode` 欄位，使 `batch --mode` 能精確過濾而不靠啟發式。

| 參數 | 含義 | 預設值 |
|---|---|---|
| `--limit N` | 只處理前 N 條待補行 | 全部 |
| `--offline` | 只做本地提取——本地無 raw 的行留待下輪，不聯網兜底 | 關 |
| `--delay-min SEC` | 聯網兜底執行緒間隨機間隔下限 | `10` |
| `--delay-max SEC` | 聯網兜底執行緒間隨機間隔上限 | `20` |

關鍵行為：

- 存平台原始值（`SEARCH` / `RESEARCH` / `ASI` / `AGENTIC_RESEARCH` / `STUDY` / `STUDIO`…）；執行緒內多值時按特異性 computer > council > study > deep-research > search 取最高。
- 本地優先：已歸檔執行緒從 `raw_entries.json` 提取，零網路——純本地可解時連 transport 都不構建（連 session 探測都沒有）。
- 僅本地無 raw 的行聯網兜底：`GET /rest/thread/<uuid>`，10–20s 隨機間隔；`expired` 終態的行跳過並如實記錄；線上新發現 expired/deleted 的執行緒標記進 `batch_state.json`，下輪免請求。
- 冪等可續跑：已有 `search_mode` 的行跳過，每 25 條中途落盤；之後 `index` 重新整理會保留富化結果（按 `entryUUID` 合併回來）。

```bash
pplx-export search-mode-backfill --account alice --offline
```

## sync-deleted

識別從遠端 library 消失的執行緒（用戶刪除或平台清除）並打墓碑標記——絕不刪除、不移動任何歸檔檔案。

| 參數 | 含義 | 預設值 |
|---|---|---|
| `--online` | 線上驗證候選 | 關（離線 dry-run：只列候選） |
| `--limit N` | 只處理前 N 條候選 | 全部 |
| `--delay-min SEC` | 候選間隨機間隔下限 | `10` |
| `--delay-max SEC` | 候選間隨機間隔上限 | `20` |

關鍵行為：

- 候選判定離線且跨帳戶：`batch_state` 狀態為 `ok` 的執行緒在**所有** `index/library_*.json` 的 `entryUUID` 並集中均消失才成為候選——任一索引含有即視為存活，因此經共享空間跨帳戶匯出的執行緒不會誤報。無任何可用索引時全部安全跳過，並提示先跑 `index`。
- 默認離線 dry-run：只列候選與安全跳過原因——零網路、不改任何檔案。
- `--online` 按候選 `thread.json` 的 `export_via` 帳戶逐條 `GET /rest/thread/<uuid>` 驗證（cookie 逐候選自動切換）。
- `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 確認 → `batch_state` 標記終態 `deleted`（與 `expired` 同語義：永不重試，`--force` 也不重導；見 [incremental-sync.zh-CN.md](incremental-sync.md)），並給該執行緒各 `thread.json` 就地加 `remote_deleted` 時間戳（冪等——已有該鍵不覆蓋）。
- 執行緒仍存在 → 誤報：如實報告並提示重跑 `index`，不改任何狀態。傳輸錯誤退避留待下輪；連續 3 次鑑權失敗即中止，避免誤標活執行緒。

```bash
pplx-export sync-deleted
pplx-export sync-deleted --online --limit 20
```

第一行只列候選（離線 dry-run）；第二行線上驗證並給確認的執行緒打標記。

## status

輸出歸檔狀態帳與增量變更計劃——零網路、唯讀。回答「歸檔現狀如何、下一次 `batch` 會做什麼」，全程不觸網。

| 參數 | 含義 | 預設值 |
|---|---|---|
| `--account X` | 只報告一個帳戶 | 全部有 `index/library_*.json` 的帳戶 |
| `--json` | 機器可讀全量報告（stdout 單行 JSON，忽略 -v 級別） | 關（人讀日誌行） |

關鍵行為：

- 數據源全本地：`index/library_*.json`（各帳戶索引行）與 `index/batch_state.json`（匯出狀態唯一真源）。變更分類復用與 `batch`/`schedule` 相同的 `plan_incremental` 純函數，`new`/`updated`/`done`/`expired`/`deleted` 語義與 `batch` 的計算完全一致。
- 默認 INFO 輸出：每帳戶一行摘要（索引條數與新鮮度、`ok/expired/deleted/error` 狀態計數、`new/updated` 變更計數、早停數），末尾一行全局 `batch_state` 狀態帳（如 `559 ok + 13 expired + 12 deleted`）。
- 明細級別直接掛既有 `-v` 計數標誌：`-v` 加 new/updated/error 執行緒標題（首行、60 字元截斷）；`-vv` 加 done/expired/deleted 執行緒並附 `lastUpdated`/`exported_at`；`-vvv` 全量不截斷並附索引 `mode`/`search_mode` 欄位與 state-only 列表（`batch_state` 有而所有帳戶索引均無的記錄——疑似遠端刪除，可經 [sync-deleted](#sync-deleted) 對帳）。
- 守衛：`index/` 或 library 檔案缺失 → 報錯指向 `pplx-export index`；`batch_state.json` 缺失按空狀態處理（全部判 new）。無需用戶級 config——帳戶名從 library 檔名列舉。
- `--json` 經 stdout 輸出全量報告（accounts/changes/threads/state_only/totals 單行 JSON）——與 `pplx-ask` 相同的契約風格。

```bash
pplx-export status                 # 全部账户摘要
pplx-export status -vv             # 五态线程明细
pplx-export status --account alice --json
```

## relations

從已匯出執行緒重建對話關係圖 → 歸檔根下 `relations/edges.jsonl`，外加人讀摘要 `relations/graph.md`。

| 參數 | 含義 | 預設值 |
|---|---|---|
| *（僅通用選項；只有 `--out` 起作用）* | | |

關鍵行為：

- 純離線、零網路、對歸檔唯讀：復用 re-render 的離線重建管線（`raw_entries.json` / `raw_blocks.json`），`sub_agents`、`query_source`、引文等訊號都可用於邊檢測。
- 無 raw 數據的執行緒退化為 `thread.json` + `conversation.md` 殼——只能觸發 `same_space` 與裸 uuid 引用邊。

```bash
pplx-export relations
```

## debug-js

經本機 WebBridge 守護行程（`127.0.0.1:10086`）在當前瀏覽器頁面上下文執行一段 JavaScript，並以 JSON 列印結果——除錯用逃生艙。

| 參數 | 含義 | 預設值 |
|---|---|---|
| `JS代码`（位置參數） | 要在頁面上下文執行的 JavaScript 程式碼 | 必填 |

關鍵行為：

- 要求 WebBridge 守護行程可達，且瀏覽器中已打開目標 Perplexity 頁面；程式碼片段在頁面自身工作階段中執行。
- 列印的 JSON 截斷到 5000 字元。

```bash
pplx-export debug-js 'document.title'
```
