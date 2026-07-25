---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/development/fixtures.zh-CN.md"
translation_source_sha256: "a34e1db385d79a8f56c92b6dfccfd6c90c76ec38feef5af63c4393418d02dc81"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="测试-fixtures" data-pplx-source-anchor="true"></a>
# 測試 fixtures

`tests/fixtures/` 為[測試套件](testing.md)提供確定性的、具有 API 結構的
**模擬資料**。輸入用於模擬代表性執行緒與工作流結構；其渲染產物以 golden
快照形式隨倉庫提交。

<a id="来源契约" data-pplx-source-anchor="true"></a>
## 來源契約

<!-- audit:contract fixture-source=simulated -->

當前已提交的 fixture 內容均為模擬資料：

- 新增或更新 fixture 時必須構造模擬資料；不得透過匯入 `web_archive/`、
  使用者帳戶資料、即時 API 回應或私人歸檔來填充。
- 已提交檔案中的名稱、身分、識別碼、prompt、answer、工作流負載、路徑與 URL
  均為測試用佔位內容。
- JSON 只為覆蓋解析器、渲染器、狀態與關係行為而仿照生產回應和歸檔 schema。
- 倉庫不提交佔位符到私人識別碼的反向對映。

**完整模式 fixture** 與**精簡場景 fixture** 描述的是覆蓋範圍和輸入型態，
不是資料來源；兩者都是模擬資料。

<a id="目录契约" data-pplx-source-anchor="true"></a>
## 目錄契約

每個 fixture 目錄包含具有原始回應形狀的模擬輸入；需要快照比對時還包含
一棵 `golden/` 樹：

| 路徑 | 作用 |
|---|---|
| `raw_entries.json` | 符合生產回應形狀的模擬執行緒 entries |
| `raw_blocks.json` | 模擬 workflow blocks；該模式無 block 回應時缺失 |
| `thread.json` | 模擬的歸檔執行緒元資料 |
| `golden/conversation.md` + `golden/turns/turn_*.md` | 由模擬輸入生成並逐位元組比較的產物 |

當前確定性約定包括：

- 佔位帳戶 `alice` / `bob`、範例身分、佔位 BOT 空間與固定
  `read_write_token`；
- 帶 `5cbeef00` 標記的 uuid5 衍生識別碼，保留模擬記錄間有意建立的交叉引用；
- 帶 `5crub0` 標記的定長模擬 `toolu_` 識別碼；
- 通用 prompt、標題、工作流文字和檔案路徑；
- 已移除查詢字串的簽名 URL。

這些約定便於發現意外混入的環境相關殘留；並不表示模擬識別碼來自線上物件。

<a id="清单" data-pplx-source-anchor="true"></a>
## 清單

<!-- audit:inventory fixture-directories -->

### 完整模式 fixtures

每個受支援模式都有一組完整的模擬會話：

| Fixture | 覆蓋 |
|---|---|
| `search_demo` | search，單輪；R 程式碼圍欄與行內程式碼 |
| `deep_research_demo` | deep research；端到端數學定界符轉換 |
| `computer_demo` | computer，七輪工作流渲染 |
| `council_demo` | council 模型委員會渲染及大型巢狀負載 |
| `study_demo` | study 模式渲染 |

<a id="精简场景-fixtures" data-pplx-source-anchor="true"></a>
### 精簡場景 fixtures

這些是定點模擬負載，只保留某項迴歸需要的 entries 與關係。「精簡」不表示
從真實執行緒提取。

| Fixture | 覆蓋 |
|---|---|
| `scenario_computer_answer_fallback` | 普通 FINAL 路徑不可用時從模式化 workflow block 恢復答案 |
| `scenario_subagent_fallback` | 無 background 匹配時渲染子代理標題及其自身條目 |
| `scenario_user_response` | `WORKFLOW_ITEM_USER_RESPONSE` 問答渲染 |
| `scenario_subagent_stub` | 無錨點 subagent-result 殘樁的十秒關聯視窗 |
| `scenario_workflow_item_nested` | 巢狀 `WORKFLOW_ITEM_WORKFLOW` 折疊區塊渲染 |
| `scenario_limit_interrupted` | 額度中斷、歸屬瀑布、附錄落位與禁止重複渲染 |
| `scenario_canceled` | `WORKFLOW_CANCELED` 標註 |

<!-- /audit:inventory fixture-directories -->

<a id="维护-fixtures" data-pplx-source-anchor="true"></a>
## 維護 fixtures

`tests/scrub_fixtures.py` 負責正規化模擬資料、透過生產離線渲染器重新產生
golden，並執行殘留門禁：

```bash
uv run python tests/scrub_fixtures.py
uv run python tests/scrub_fixtures.py --check
```

- **重新產生**——每個 fixture 都在臨時目錄中透過
  `pplx_export.commands.rerender_cmd.rerender` 渲染；輪數不一致時中止。
- **確定性正規化**——佔位文字、UUID、`toolu_` 值、token 與簽名 URL
  均以冪等方式正規化。
- **安全輸入不是資料來源**——可選的本地 `tests/scrub_pairs.local.json`
  與使用者級帳戶設定只擴充取代和殘留檢查；不得把它們作為構造 fixture 場景的
  輸入。
- **檢查模式**——`--check` 不寫檔案；發現已設定殘留、本地絕對路徑或簽名
  URL 憑證時失敗。

修改模擬輸入 JSON 或渲染器輸出後執行維護工具；提交 fixture 變更前執行
`--check`。

<a id="golden-快照的权威边界" data-pplx-source-anchor="true"></a>
## Golden 快照的權威邊界

已提交的模擬 JSON 是輸入真源。Golden Markdown 是衍生產物：由當前生產重渲
路徑從模擬 JSON 重新產生，再提交用於位元組級迴歸比對；不得把它作為獨立真源
手工維護。

<a id="另见" data-pplx-source-anchor="true"></a>
## 另見

- [測試](testing.md)——套件如何消費 fixtures
- [測試系統架構](testing-architecture.md)——迴歸層次與保證
- `tests/fixtures/README.zh-CN.md`——倉庫內 fixture 清單
