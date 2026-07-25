---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/archive-layout.zh-CN.md"
translation_source_sha256: "87d25ea40af1217fcbcddafae7c173aebca9a6669c09a8f77ccb2e8eee557782"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="归档目录结构" data-pplx-source-anchor="true"></a>
# 歸檔目錄結構

`pplx-export` 下載的所有內容都落在同一棵輸出樹中——預設為 `./web_archive/`
（可用 `--out` 覆蓋）。本頁是這棵樹的導讀：每個目錄與檔案是什麼、`thread.json`
攜帶哪些鍵、以及工作階段跨天續接時工具如何保證一個執行緒只有一個目錄。全部內容均由工具產生；
機制細節見[資料模型與目錄契約](../architecture/data-model.md)與[匯出管線](../architecture/export-pipeline.md)。

<a id="输出目录树" data-pplx-source-anchor="true"></a>
## 輸出目錄樹

```
web_archive/
├── alice/                                # 每账户一个文件夹（作者显示名）
│   ├── search/                           # 模式：search | deep-research | computer | council | study
│   │   └── 2026-07-18_quantum-computing-survey_1a2b3c4d/   # 每线程一个目录
│   │       ├── thread.json               # 元数据 + 可选登记键
│   │       ├── conversation.md           # 简版：逐轮 Query/Answer
│   │       ├── turns/
│   │       │   ├── turn_0001.md          # 完整版：完整工作过程细节
│   │       │   └── ...
│   │       ├── sources.json              # 全线程引文（按 url 去重）
│   │       ├── sources.md
│   │       ├── report.md                 # deep-research 报告（有才存在）
│   │       ├── raw_entries.json          # plain API 响应，原样落盘（恒存在）
│   │       ├── raw_blocks.json           # schematized API 响应（search 无此文件）
│   │       └── assets/
│   │           ├── assets_manifest.json  # 多版本清单
│   │           └── files/                # 已下载的资产文件体
│   ├── deep-research/ ...
│   └── computer/ ...
├── index/                                # 状态文件与索引（见下）
├── relations/                            # edges.jsonl + graph.md（由 `pplx-export relations` 重建）
├── crosscheck/                           # 交叉核验报告（人工/评审产物）
└── bob/ ...
```

<a id="线程目录" data-pplx-source-anchor="true"></a>
## 執行緒目錄

每個執行緒恰好對應一個目錄，由 `thread_dir_for`（`fs_writer.py:58-72`）計算：

```
<账户显示名>/<模式>/<YYYY-MM-DD>_<标题slug>_<uuid8>/
```

| 組成 | 來源 | 說明 |
|---|---|---|
| `<账户显示名>` | 執行緒作者，經 `author_folder` → `_safe_folder` 清洗（`fs_writer.py:40-51`） | 路徑分隔符與 Windows 非法字元（`:*?"<>\|`）替換為 `_`；`.`/`..` 被拒絕（防共享空間路徑穿越）；其餘字元——包括空格——原樣保留 |
| `<模式>` | `detect_mode` | 五種模式之一，見[工作階段模式](modes.md) |
| `<YYYY-MM-DD>` | `thread.json` 的 `lastUpdated` 日期前綴 | 平台側最後更新日期，**不是**匯出日期——續接的執行緒更新後它會變（見下文遷移） |
| `<标题slug>` | `slugify(title)`（`normalize.py:261-263`） | 最長 40 字元，非單詞字元 → `-`，空標題 → `untitled` |
| `<uuid8>` | `web_uuid[:8]` | 執行緒 UUID 前 8 位——目錄的身分錨點 |

<a id="线程目录内的文件" data-pplx-source-anchor="true"></a>
## 執行緒目錄內的檔案

<a id="threadjson元数据与登记信息" data-pplx-source-anchor="true"></a>
### thread.json——元資料與登記資訊

由 `write_thread`（`fs_writer.py:224-253`）寫入。恆存在的鍵：

| 鍵 | 內容 |
|---|---|
| `web_uuid` | web entryUUID——執行緒 URL 中的 UUID，執行緒的身分 |
| `psc_uuid` | 平台 `context_uuid`（可空；取首個非空輪次的值）——空間索引使用的雙重 ID |
| `url` | 執行緒規範 URL |
| `title` | 執行緒標題 |
| `mode` | 判定出的模式（`search` / `deep-research` / `computer` / `council` / `study`） |
| `author` | 作者帳戶顯示名 |
| `export_via` | 執行匯出的帳戶使用者名稱——對經他帳戶匯出的共享空間執行緒尤其重要 |
| `space` | `{"uuid", "title", "slug"}` 或 `null` |
| `lastUpdated` | 平台最後更新時間戳（增量同步的機器比較契約） |
| `threadAccess` | 平台存取標誌 |
| `n_turns` | 輪次數 |
| `n_sources` | 全執行緒引文數 |
| `metadata` | API 回應中的 `thread_metadata`，原樣保留 |
| `report_info` | `{"title", "file_name", "url"}` 或 `null` |
| `exported_at` | 匯出時間（UTC ISO 8601） |

可選鍵——沒有相應內容時不出現：

| 鍵 | 何時寫入 | 內容 |
|---|---|---|
| `interruptions` | 存在非 completed 工作流程（`fs_writer.py:242-244`） | `{location, kind, headline, status}` 列表；見[工作階段模式——中斷標註](modes.md) |
| `answer_variants` | 偵測到答案重寫變體（`fs_writer.py:247-252`） | 收窄判據的 `side_by_side_metadata` 定位欄位；見[工作階段模式——答案重寫變體](modes.md) |
| `remote_deleted` | `pplx-export sync-deleted --online` 確認遠端刪除 | 墓碑時間戳，就地寫入，等冪（已有值不覆蓋；`sync_deleted_cmd.py:215-244`）——本地歸檔本身保留 |

<a id="conversationmd简版" data-pplx-source-anchor="true"></a>
### conversation.md——簡版

`render_conversation`（`render.py:641`）：標題頭（模式 / 作者 / 輪次 / 引文數），
隨後每輪一對 `### Query` + `### Answer`，答案完整呈現；存在時末尾附執行緒級後台任務附錄。
這是首先該開啟的檔案；逐輪工作過程在 `turns/` 中。

### turns/turn_NNNN.md——完整版

`render_turn`（`render.py:596`）：每輪一個檔案（`turn_0001.md` …），含完整工作
過程——步驟、工具呼叫、子代理執行、表格、本輪引文。執行緒輪數縮減時，只刪除編號過高的
舊 `turn_*.md`，未變檔案保留 mtime（`fs_writer.py:287-301`）。

### sources.json / sources.md

全執行緒引文，按 URL 去重（`fs_writer.py:270-278`）。`sources.json` 為
`{"count", "sources": [{"name", "url", "snippet", "timestamp"}]}`；`sources.md`
是同一列表的編號 Markdown 連結版。

### report.md

deep-research 的報告產物，僅在執行緒攜帶報告時寫入（`fs_writer.py:308-316`）：
報告標題、原始產物檔名，隨後是完整報告 Markdown。

### raw_entries.json / raw_blocks.json——原始保真

API 回應在任何解析**之前**原樣落盤（`fs_writer.py:257-266`）：

- `raw_entries.json`——plain 回應：`{"thread_metadata", "entries", "background_entries"}`，
  恆存在。
- `raw_blocks.json`——schematized 回應，結構同上。`search` 執行緒無此檔案（不抓 blocks）；
  其餘四種模式均抓取，且當全部模式判別訊號缺失時也兜底抓取。

這兩個檔案是整個歸檔的保真錨點：解析、渲染、登記資訊都能由它們離線重建，零網路。
見[離線操作](../architecture/offline-operations.md)。

<a id="assets产物与清单" data-pplx-source-anchor="true"></a>
### assets/——產物與清單

可下載產物（Computer 模式檔案及 API 列出的其他資產）經 CloudFront 簽名 URL 下載進
`assets/files/`；副檔名在下載時按 URL 路徑、內容魔數或資產類型判定。
`assets/assets_manifest.json`（`fs_writer.py:320-330`）記錄每個版本：

```json
{"count": 2, "files": [{"filename": "analysis.xlsx", "n_versions": 2,
  "versions": [{"uuid": "…", "asset_type": "XLSX_FILE", "version": "v1",
                "created_at": "…", "downloaded_to": "…"}]}]}
```

`count` 恆為**版本總數**（Σ `len(versions)`），不是檔案組數——檔案組數請用 `len(files)`。

<a id="index-层" data-pplx-source-anchor="true"></a>
## index/ 層

`web_archive/index/` 存放工具託管的狀態與索引——勿手改：

| 檔案 | 寫入方 | 語義 |
|---|---|---|
| `library_<account>.json` | `pplx-export index`（`index_cmd.py:17-43`） | 帳戶全量執行緒索引（GraphQL）；batch / 排程 / 空間索引的輸入 |
| `batch_state.json` | `BatchState`（`state.py`） | 可續傳檢查點：uuid → 狀態（ok/error/expired/deleted）+ lastUpdated；原子寫；損壞檔案自動備份為 `.corrupt-<ts>` |
| `.cookies.json` | cookie 快取（`common.py:111`、`common.py:150`） | 12 小時新鮮度的 cookie 快取，含來源與帳戶信箱；先以 `0o600` 寫暫存檔再原子替換（工作階段憑證僅擁有者可讀） |
| `space_<slug>.json` | `pplx-export space-index`（`spaces_cmd.py:106-167`） | 單空間執行緒列表，含 `context_uuid` 雙重 ID 映射 |
| `space_meta.json` | `pplx-export spaces --fetch-meta`（`spaces_cmd.py:299-330`） | 空間 owner/member 快取，重建時復用 |
| `credit_usage_<account>.json` | `pplx-export usage-backfill`（`usage_backfill_cmd.py:17`） | 逐執行緒額度用量（等冪、可續傳，每 25 條落盤一次） |
| `cron_snippet.txt` | `pplx-export schedule`（`scheduler.py:48-78`） | cron 呼叫片段（絕對路徑） |
| `answer_variants_log.jsonl` | `variant_log.append_registry`（`variant_log.py:76`） | 答案重寫變體集中登記處，按（執行緒, entry）去重，等冪 |
| `logs/` | `--log-file`（`common.py:218-229`） | 完整 DEBUG 日誌 |

<a id="spaces-层" data-pplx-source-anchor="true"></a>
## spaces/ 層

`pplx-export spaces` 聚合 `index/library_*.json` 重建空間索引（`spaces_cmd.py:259-389`）：
每個空間一個 `<slug>.md`（參與帳戶聚合、owner/member 頭、執行緒表、匯出位置回鏈），
外加 `spaces.json` 註冊表。

!!! note "輸出位置"
    `spaces/` 相對於當前工作目錄寫出（`spaces_cmd.py:332`）——**不**跟隨 `--out`。
    勿手改：下次重建會覆蓋。

<a id="跨天续接按-uuid-身份的目录迁移" data-pplx-source-anchor="true"></a>
## 跨天續接：按 UUID 身分的目錄遷移

目錄名內嵌 `lastUpdated` 日期，因此隔天續接一個執行緒時，樸素計算會得出**新**目錄。
writer 按 UUID 身分防止重複（`thread_dir_for`，`fs_writer.py:58-72`）：

1. **查找**：`find_thread_dirs`（`fs_writer.py:74-105`）全庫搜尋以 `_<uuid8>` 結尾的
   目錄——跨帳戶、跨模式。候選目錄僅當其 `thread.json` 存在、可解析且 `web_uuid`
   全等時才被接受；缺失、損壞或不符的目錄一律不動（寧可漏遷，不可誤併）。
2. **合併**：`_merge_into`（`fs_writer.py:107-178`）把舊目錄併入新目錄——檔案取並集
   （舊目錄獨有檔案不丟）；同名同內容跳過；同名衝突**恆保留目標方**（語義更新的一方），
   且逐條記錄日誌。每個複製檔案經 sha256 校驗後才刪除舊目錄；任何失敗都讓舊目錄
   原樣保留，重試等冪。
3. **清理歷史重複**：`consolidate_uuid`（`fs_writer.py:180-209`）全庫合併同一 UUID 的
   重複日期目錄，保留 `lastUpdated` 最大者——這是舊版本遺留重複目錄的兜底手段。

同樣的 UUID 嚴格度也保護空間索引回鏈：`thread.json` 缺失/損壞/不符的候選目錄
一律不被連結。

<a id="可手改与工具托管" data-pplx-source-anchor="true"></a>
## 可手改與工具託管

- **工具託管（勿手改）**：執行緒目錄內的一切，以及 `index/`、`spaces/`、`relations/`。
  內容有問題就改工具再重新產生——渲染修復走 `pplx-export re-render`，資料修復走對應的
  backfill 命令（見[維護命令](maintenance-commands.md)）——讓每個產物都可從 raw
  復現。
- **可手改**：文件與 `web_archive/crosscheck/` 評審報告。一個使用者級例外：人工搶救回的
  備選答案可記錄為執行緒目錄內的 `rewritten_answer_variant.md`——見
  [工作階段模式——答案重寫變體](modes.md)。

<a id="另见" data-pplx-source-anchor="true"></a>
## 另見

- [工作階段模式](modes.md)——五種模式及各自產物
- [增量同步](incremental-sync.md)——`lastUpdated` 如何驅動重導
- [維護命令](maintenance-commands.md)——re-render、backfill、sync-deleted
- [資料模型與目錄契約](../architecture/data-model.md)——底層 dataclass
- [匯出管線](../architecture/export-pipeline.md)——這些檔案如何寫出
- [離線操作](../architecture/offline-operations.md)——從 `raw_*.json` 重建一切
