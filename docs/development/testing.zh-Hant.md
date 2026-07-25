---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/development/testing.zh-CN.md"
translation_source_sha256: "8876379e1f59a425bc149713192064dc705e47ea0e86c3729cf30993a0261c18"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="测试" data-pplx-source-anchor="true"></a>
# 測試

測試套件位於 `tests/`（在 `pplx_export` 套件之外），完全離線執行。API 形狀的
輸入是隨倉庫提交於 `tests/fixtures/` 的確定性模擬資料；測試不依賴線上服務，
也不依賴真實的使用者層級設定。

本頁負責維護當前測試模組清單與貢獻流程。回歸設計見
[測試系統架構](testing-architecture.md)，輸入資料契約見
[測試 fixtures](fixtures.md)。

<a id="运行测试" data-pplx-source-anchor="true"></a>
## 執行測試

```bash
uv run pytest tests
```

pytest 是已宣告的開發依賴。測試套件保證：

- **零網路**——模擬輸入已入庫；面向網路的路徑由 fake、`tmp_path` 和
  `monkeypatch` 覆蓋。
- **不讀真實使用者設定**——`tests/conftest.py` 會在匯入任何生產模組前建立
  處理程序級臨時設定並覆蓋 `PPLX_EXPORT_CONFIG`。隨後每項測試獲得獨立的
  `alice` / `bob` 佔位設定，結束後恢復處理程序級佔位設定。子處理程序回歸還會驗證：
  即使呼叫方設定不存在或已經損壞，測試收集也不會失敗。
- **快速回饋**——本專案於 2026-07-25 從 32 個 `test_*.py` 模組觀測到
  435 項測試；本地驗證中的完整執行約為 13–25 秒。數量是帶日期的倉庫快照，
  會隨開發增長。

常用選擇：

| 命令 | 效果 |
|---|---|
| `uv run pytest tests` | 完整套件 |
| `uv run pytest tests/test_units.py` | 單一模組 |
| `uv run pytest tests -k snapshot` | node id 匹配 `snapshot` 的測試 |
| `uv run pytest tests -x -q` | 首次失敗即停止，安靜輸出 |
| `uv run pytest --collect-only -q` | 重新整理收集用例數量 |

<a id="当前模块清单" data-pplx-source-anchor="true"></a>
## 當前模組清單

清單已於 **2026-07-24** 對照倉庫同步：

<!-- audit:inventory test-modules -->

| 功能族 | 模組 | 用途 |
|---|---|---|
| 渲染快照 | `test_render_snapshots.py` | 重渲全部模擬的完整模式與精簡場景 fixtures，並與已提交產物逐位元組比對 |
| 核心與共享工具 | `test_units.py` | 狀態、節流、規劃、正規化、資產命名、模式判定、安全路徑及跨領域回歸 |
| 文件契約、skill 與本地化 | `test_agent_skills.py`<br/>`test_audit_docs.py`<br/>`test_translate_docs.py` | 倉庫本地 skill 契約，以及針對唯讀文件稽核器和機器翻譯管線的隔離微型倉庫測試 |
| 設定、認證與初始化 | `test_config_external.py`<br/>`test_cookie_profiles.py`<br/>`test_credential.py`<br/>`test_init.py` | 外置設定隔離、cookie 來源設定、憑證選擇與初始化 |
| 渲染與工作流程語意 | `test_interruptions.py`<br/>`test_stub_workflows.py`<br/>`test_answer_variants.py`<br/>`test_answer_variant_logging.py`<br/>`test_relations.py` | 工作流程歸屬、中斷狀態、答案變體、稽核日誌與關係邊 |
| 離線歸檔與索引維護 | `test_search_mode_backfill.py`<br/>`test_sync_deleted.py`<br/>`test_status.py` | 強化、續跑/等冪行為、跨帳戶刪除判定、終態，以及離線狀態帳/變更報告的分層輸出 |
| 審查回歸 | 下表所列 16 個 `test_fix_*.py` 模組 | 源自審查發現的修正；模組名保留審查 lineage |

<a id="评审回归-lineage" data-pplx-source-anchor="true"></a>
### 審查回歸 lineage

審查編號解釋回歸測試為何存在，但不是測試套件的主架構。對映明確允許多對多：
一個模組可覆蓋多個發現，一個發現也可能在既有專題模組中增加用例。

| Lineage | 專用模組 |
|---|---|
| N 輪審查 | `test_fix_n01_inline_assets.py`、`test_fix_n02_spaces_link.py`、`test_fix_n03_n12.py`、`test_fix_n04_cookies.py`、`test_fix_n05_n06_n09.py`、`test_fix_n07_usage_checkpoint.py`、`test_fix_n08_throttle_overflow.py`、`test_fix_n10_table_header.py`、`test_fix_n11_batch_total.py` |
| V3 輪審查 | `test_fix_v301_nested_sources_text.py`、`test_fix_v305_export_products.py` |
| V4 輪審查 | `test_fix_v401_thread_dir_migration.py`、`test_fix_v402_manifest_count.py`、`test_fix_v403_handle_assets_idempotency.py`、`test_fix_v405_ask_post_steps.py` |
| V5 輪審查 | `test_fix_v5_review.py`，以及既有專題模組中的定點增補 |

<!-- /audit:inventory test-modules -->

各模組的 docstring 仍是對應發現的舊行為、修正行為與回歸邊界的權威說明。

<a id="快照测试如何复用生产重渲路径" data-pplx-source-anchor="true"></a>
## 快照測試如何重複使用生產重渲路徑

快照測試不會另行實作一套渲染器：

1. `tests/conftest.py` 中的 `render_fixture` 把 fixture 的模擬
   `raw_entries.json`、可選 `raw_blocks.json` 與 `thread.json` 複製到暫存目錄。
2. 它呼叫 `pplx_export.commands.rerender_cmd.rerender`，即
   `pplx-export re-render` 使用的同一函式。
3. `rendered` fixture 工廠回傳新鮮輸出與 fixture 中已提交的 `golden/` 目錄。
4. 測試逐位元組比較 `conversation.md` 和全部 `turns/turn_*.md`。

除位元組相等外還有內容不變式：答案不得退化成空佔位符 `(无)`，`{'type': ...`
一類 dict-repr 殘留不得洩漏到渲染文字。

<a id="新增测试" data-pplx-source-anchor="true"></a>
## 新增測試

- **既有邏輯**——向對應專題模組加測試。使用 `tmp_path`、fake 與
  `monkeypatch`；不得存取網路或真實 `~/.config`。
- **缺陷回歸**——優先加入對應專題模組。僅當保留審查 lineage 明顯改善可追溯性時，
  新建 `test_fix_<lineage>_<slug>.py`；不要假定一個發現對應一個模組。
- **渲染回歸**——新增或精簡一個模擬 fixture，用維護工具重新產生 golden，
  再將其登記到 `test_render_snapshots.py` 或增加場景專用斷言。

遵循相鄰程式碼風格：型別標註、`from __future__ import annotations` 與雙語模組
docstring。

<a id="另见" data-pplx-source-anchor="true"></a>
## 另見

- [測試 fixtures](fixtures.md)——模擬輸入、golden 產物與維護契約
- [測試系統架構](testing-architecture.md)——測試層次與回歸保證
- [離線操作](../architecture/offline-operations.md)——快照測試重複使用的生產重渲路徑
