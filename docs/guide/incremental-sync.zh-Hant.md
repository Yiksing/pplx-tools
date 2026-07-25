---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/incremental-sync.zh-CN.md"
translation_source_sha256: "ca6b70d4ac1b77d992fbc2d801238b670a1652dcf4ffc577e52d3f09fd404fee"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# 增量同步

`pplx-export batch` 為高頻運行而設計：每輪只導出新增或有變化的對話，自動修復
中斷運行的缺口，且絕不重複觸碰平台已下架的執行緒。「哪些已導出」的唯一權威
來源是 `index/batch_state.json`（`BatchState`，`pplx_export/core/state.py:63`），
每導完一個執行緒即更新——不另維護影子副本。

<a id="前置条件与基本用法" data-pplx-source-anchor="true"></a>
## 前置條件與基本用法

```bash
pplx-export index --account alice   # 先刷新 index/library_alice.json
pplx-export batch --account alice   # 增量导出（早停 + 断点续跑）
```

索引不存在時 `batch` 拒絕運行（`pplx_export/commands/batch_cmd.py:79-81`）。
`--limit N` 與 `--mode <mode>` 在規劃之前過濾索引行；缺 `entryUUID` 的壞行
只告警跳過，不會讓整個運行崩潰（`batch_cmd.py:95-100`）。

<a id="增量计划如何工作" data-pplx-source-anchor="true"></a>
## 增量計劃如何工作

1. **排序。** 索引行按 `lastUpdated` 從新到舊排序（`batch_cmd.py:89`）。
   全新對話與「續接的舊對話」（`lastUpdated` 變新、位置上移）都排在頂部——
   這個順序正是早停安全的前提。
2. **分類。** `plan_incremental`（`pplx_export/hooks/incremental.py:36-87`）
   ——`batch` 與 `schedule` 共用的純函數——為每一行指派恰好一個動作：

   | 動作 | 條件 | batch 的處理 |
   |---|---|---|
   | `new` | `batch_state` 中從未見過該 uuid | 導出 |
   | `updated` | `lastUpdated` 與記錄值不同，或帶 `--force` | 重導 |
   | `done` | 狀態為 `ok` 且 `lastUpdated` 未變 | 跳過 |
   | `expired` | 之前導出時平台返回了 `ENTRY_EXPIRED` | 跳過——終態，永不重試 |
   | `deleted` | `sync-deleted` 已確認遠端刪除 | 跳過——終態，永不重試 |

3. **早停。** 預設（既不帶 `--full` 也不帶 `--force`）截掉尾部最長的終態
   連續段（`done` / `expired` / `deleted`），截掉條數記為 `n_stopped`
   （`incremental.py:83-87`）。列表從新到舊，未變條目之下必然更舊、也未變——
   繼續掃描只是浪費時間。

   ```mermaid
   flowchart TD
       IDX["library 索引行<br/>按 lastUpdated 从新到旧排序"] --> PLAN["plan_incremental"]
       PLAN --> NEW["new → 导出"]
       PLAN --> UPD["updated → 重导"]
       PLAN --> DONE["done → 跳过"]
       PLAN --> TERM["expired / deleted → 跳过（终态）"]
       DONE --> STOP["早停：截掉尾部终态连续段"]
       TERM --> STOP
   ```

4. **執行。** 每導出一個執行緒立即打標記（`mark_ok` / `mark_error` /
   `mark_expired` / `mark_deleted`），且每項之後都落盤狀態檔案
   （`batch_cmd.py:154-201`）；`KeyboardInterrupt` 也會先儲存再向上拋
   （`batch_cmd.py:158-161`）。寫入是原子的——臨時檔案加 `os.replace`
   （`state.py:145-152`）——中斷不會留下截斷的 JSON。

<a id="中断后的缺口修复" data-pplx-source-anchor="true"></a>
## 中斷後的缺口修復

早停絕不會掩埋缺口。失敗（狀態 `error`）或從未輪到的執行緒位於終態後綴
**之上**，下一輪會把它們重新規劃為 `updated` / `new`，在到達早停點之前就
導出（`incremental.py:12-14`，`batch_cmd.py:206-208`）。配合逐項落盤，batch
運行可在任意時刻中斷，直接重跑即可。

若 `batch_state.json` 本身損壞，不會被靜默置空：原檔案更名為
`batch_state.json.corrupt-<timestamp>`，已記錄的終態不遺失、不做無謂重試
（`state.py:68-81`）。

<a id="-full-与-force" data-pplx-source-anchor="true"></a>
## `--full` 與 `--force`

| 選項 | 效果 | 終態 | 適用場景 |
|---|---|---|---|
| *（預設）* | 對尾部終態連續段早停 | 跳過 | 每次常規 / 定時運行 |
| `--full` | 全量掃描，不早停；未變執行緒仍按 `done` 跳過 | 跳過 | 定期兜底，或懷疑檔案有缺口時 |
| `--force` | 全部重導，包括未變執行緒 | 仍然排除——永不重試 | 管線修復後必須重新抓取 raw 資料時 |

終態被 `--force` 排除是有意設計：重試已過期或遠端已刪除的執行緒只會白費
請求與退避預算（`batch_cmd.py:120-127`）。

另見 [`status`](maintenance-commands.md#status)：零網路輸出狀態帳與按同一
`plan_incremental` 語義計算的變更計劃（new/updated/早停數）。

`lastUpdated` 比較會對小數秒部分去尾零（`.18033Z` 與 `.180330Z` 判同；
`state.py:23-55`），因為平台偶發丟尾零——精確字串比較會誤判「已變化」，
導致重複導出。

<a id="终态expired-与-deleted" data-pplx-source-anchor="true"></a>
## 終態：`expired` 與 `deleted`

| | `expired` | `deleted` |
|---|---|---|
| 含義 | 平台清除了該執行緒（約 3 個月保留視窗）；導出嘗試返回 `ENTRY_EXPIRED` | 使用者/遠端刪除，經 `sync-deleted` 確認 |
| 記錄者 | `batch` 自身（`mark_expired`，`state.py:131-134`） | `pplx-export sync-deleted --online`（`mark_deleted`，`state.py:136-143`） |
| 重試？ | 永不——`--force` 也不 | 永不——`--force` 也不 |
| 證據 | `ENTRY_EXPIRED` 響應 | `note` 欄位：索引消失 + `GET /rest/thread/<uuid>` → `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 |

<a id="sync-deleted确认远端删除" data-pplx-source-anchor="true"></a>
### sync-deleted：確認遠端刪除

```bash
pplx-export sync-deleted --account alice            # 离线 dry-run：只列候选
pplx-export sync-deleted --account alice --online   # 逐候选在线验证
```

1. **候選判定（離線，零網路）。** `batch_state` 中狀態為 `ok` 的執行緒，若在
   **所有** `index/library_*.json` 帳戶索引的 `entryUUID` 並集中均消失，即為
   疑似遠端刪除候選（`pplx_export/commands/sync_deleted_cmd.py:148-212`）。
   跨帳戶並集是必需的：`bob` 擁有、經共享空間由 `alice` 導出的執行緒永遠不會
   出現在 `alice` 自己的索引裡——單帳戶 diff 會把這批執行緒全部誤報。當所有
   索引都不可用時，候選全部安全跳過並如實記錄原因。
2. **預設 dry-run。** 不帶 `--online` 只列出候選——不聯網、不改任何檔案。
3. **`--online` 確認。** 逐候選 `GET /rest/thread/<uuid>`，使用候選
   `thread.json` 裡的 `export_via` 帳戶（cookie 自動切換）：

   | 結果 | 處置 |
   |---|---|
   | `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 | 確認：`batch_state` 標記終態 `deleted`（`note` 記錄原因），並給該執行緒各目錄的 `thread.json` 就地加 `remote_deleted` 時間戳 |
   | 執行緒仍存在 | 誤報：如實報告（索引可能未刷新完整——重跑 `index` 後複核），不改任何狀態 |
   | 5xx / 網路錯誤 | 不改狀態，留待下輪 |
   | 連續 3 次 401/403 | fail-fast 中止——cookie 失效時退避無法自癒，空轉會把活執行緒誤標（`sync_deleted_cmd.py:333-337`） |

   確認標記逐條落盤：`--online` 運行中斷不丟已確認項，重跑冪等
   （`sync_deleted_cmd.py:254-256`）。

<a id="墓碑原则" data-pplx-source-anchor="true"></a>
## 墓碑原則

!!! warning "本地歸檔絕不刪除"
    本倉庫是已導出對話的備份檔案（backup of record）。`sync-deleted` 只做
    「識別 + 標記」（tombstone）：**絕不刪除、不移動任何歸檔檔案**。確認只改
    兩處——`batch_state` 的狀態與 `thread.json` 的一個標記鍵：

    ```json
    "remote_deleted": "2026-07-23T10:20:30Z"
    ```

    該標記冪等：已有 `remote_deleted` 鍵既不重寫也不覆蓋原時間
    （`sync_deleted_cmd.py:215-244`）。

<a id="幂等与离线重渲" data-pplx-source-anchor="true"></a>
## 冪等與離線重渲

- 索引未變時重跑 `batch` 什麼都不導：每行都分類為 `done`，運行停在早停點。
  狀態寫入原子、標記逐執行緒、重複確認刪除不會重複打 `remote_deleted`。
- 歸檔儲存了 raw API 負載（`raw_entries.json` / `raw_blocks.json`），渲染產物
  可隨時零網路再生：

  ```bash
  pplx-export re-render                 # 全量重建 conversation.md + turns/
  pplx-export re-render --dry-run       # 只列出将处理的线程目录
  pplx-export re-render --thread-json   # 同时同步 interruptions / answer_variants 键
  ```

  `re-render` 用當前渲染器重新解析 raw JSON
  （`pplx_export/commands/rerender_cmd.py:105-190`）：重寫 `conversation.md`
  與 `turns/turn_*.md`，刪除編號高於當前輪數的殘留輪檔案，sources、assets、
  `report.md` 與 `thread.json` 原樣不動。渲染層修復就是這樣在零請求下鋪到
  整個歸檔的。

<a id="另见" data-pplx-source-anchor="true"></a>
## 另見

- [pplx-export.md](pplx-export.md) —— `batch` 完整命令參考（`--mode`、`--limit`、間隔參數）
- [maintenance-commands.md](maintenance-commands.md) —— `sync-deleted`、`re-render` 與各 backfill 命令
- [archive-layout.md](archive-layout.md) —— `batch_state.json` 與 `thread.json` 的位置
- [rate-limiting.md](rate-limiting.md) —— 執行緒間隔、退避、鑑權 fail-fast
- [../architecture/export-pipeline.md](../architecture/export-pipeline.md) —— 完整導出管線
- [../architecture/offline-operations.md](../architecture/offline-operations.md) —— 離線重建管線詳解
- [../architecture/rate-limiting-errors.md](../architecture/rate-limiting-errors.md) —— 錯誤分類與終態處理
