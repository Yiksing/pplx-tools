---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/development/testing-architecture.zh-CN.md"
translation_source_sha256: "7e7e01902d3e8e45e0929e728479bc7adbd556f2b2706972fecec4a9b9f5b77f"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="测试架构" data-pplx-source-anchor="true"></a>
# 測試架構

`pplx_export` 測試體系完全離線，使用已入庫的模擬資料，並以快照鎖定渲染器
行為。本頁說明架構與保證；當前模組清單歸
[測試](../development/testing.md)維護，fixture 細節歸
[測試 fixtures](../development/fixtures.md)維護。

小節沿用[架構總覽](../architecture/overview.md)中的編號。

---

<a id="测试体系" data-pplx-source-anchor="true"></a>
## 測試體系

使用 `uv run pytest tests` 運行套件。測試數量以當前運行結果報告，不作為
架構常數。

<a id="层次" data-pplx-source-anchor="true"></a>
### 層次

| 層次 | 代表模組 | 契約 |
|---|---|---|
| 純單元行為 | `test_units.py`、憑證/cookie/配置測試 | 以模擬輸入隔離函式、類別、校驗與正規化 |
| 元件語意 | 中斷、殘樁工作流、答案變體與 relations 測試 | 在零網路條件下覆蓋解析器、渲染器、狀態與索引程式碼的協作 |
| 離線命令與狀態行為 | backfill、刪除同步、初始化與評審回歸 | 對臨時目錄和 fake transport 執行命令路徑 |
| 渲染快照 | `test_render_snapshots.py` | 將具有 API 形狀的模擬 JSON 送入生產重渲路徑，並將全部 Markdown 與已提交 golden 逐位元組比對 |

N、V3、V4、V5 等評審編號是跨層次的可追溯元資料，不定義獨立的執行架構，
與測試模組也不必一一對應。

<a id="快照数据流" data-pplx-source-anchor="true"></a>
### 快照資料流

1. 模擬 fixture 提供 `raw_entries.json`、可選 `raw_blocks.json` 與
   `thread.json`。
2. `tests/conftest.py::render_fixture` 將這些檔案複製進 `tmp_path`。
3. Fixture 呼叫 `commands.rerender_cmd.rerender`，即生產離線重建路徑。
4. 新產生的 `conversation.md` 與 `turns/turn_*.md` 和已提交的
   `golden/` 產物逐位元組比較。

Golden 是產生的預期結果，不是獨立資料來源。任何改變產物位元組的渲染器修改都會
使快照套件失敗，直到修改經過審查並有意重新產生 golden。

<a id="隔离与信任边界" data-pplx-source-anchor="true"></a>
### 隔離與信任邊界

- **Fixture 來源**——所有已提交的 fixture 輸入都是模擬資料，不從線上帳戶、
  即時 API 回應、`web_archive/` 或私人歸檔複製。
- **網路邊界**——測試使用 fake 與離線路徑；已入庫 fixtures 不需要憑證或網路。
- **配置邊界**——autouse fixture 安裝佔位帳戶配置，開發者真實
  `~/.config` 不決定測試結果。
- **檔案系統邊界**——命令與遷移行為在 `tmp_path` 下執行，不以使用者歸檔為測試目標。
- **殘留邊界**——`tests/scrub_fixtures.py --check` 在不修改檔案的前提下拒絕
  已配置的環境相關字串、本機絕對路徑與簽名 URL 憑證。

單元斷言、元件語意、命令狀態測試與位元組級快照共同保護局部邏輯和端到端重渲契約。
