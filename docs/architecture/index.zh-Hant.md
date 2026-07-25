---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/architecture/index.zh-CN.md"
translation_source_sha256: "11e03bf1d56e3cd6e14277369f8369ceba6af4385ecb25765fe3c05980c9c5c6"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="系统架构阅读地图" data-pplx-source-anchor="true"></a>
# 系統架構閱讀地圖

pplx-tools（`pplx-export` / `pplx-ask`）的機制層參考：依賴關係、運行管線、
狀態機、資料契約與可靠性邊界。面向任務的說明請從[使用指南](../guide/index.md)開始。

!!! note "範圍與事實來源"

    本區面向接手維護專案的 agent 與工程師，解釋 `pplx_export/` 的系統架構。
    行號引用使用 `file.py:NN`，均相對 `pplx_export/`。頁面內容於
    2026-07-23 對照倉庫核實（`__version__ = "0.1.0"`，
    `pplx_export/__init__.py:31`）；當前程式碼和測試仍是最終事實來源。

<a id="从系统地图开始" data-pplx-source-anchor="true"></a>
## 從系統地圖開始

- [架構總覽](overview.md)——分層結構、模組職責與真實 import 依賴圖。

<a id="沿运行流程阅读" data-pplx-source-anchor="true"></a>
## 沿運行流程閱讀

- [匯出管線](export-pipeline.md)——抓取、原始回應保留、模式識別與 Markdown
  渲染。
- [子代理與中斷](subagents-interruptions.md)——後台產物歸屬與中斷/續跑語義。
- [pplx-ask 與多帳戶](ask-and-accounts.md)——串流發問和多帳戶 cookie 切換。

<a id="理解数据与可靠性" data-pplx-source-anchor="true"></a>
## 理解資料與可靠性

- [資料模型與目錄契約](data-model.md)——模型、寫入邊界和磁碟歸檔契約。
- [限頻與錯誤處理](rate-limiting-errors.md)——節流、退避、終態與錯誤分流。
- [離線運維機制](offline-operations.md)——零網路重渲、關係圖重建和本地維護管線。

<a id="相关参考" data-pplx-source-anchor="true"></a>
## 相關參考

- [Web API 參考](../reference/api/index.md)——已觀察到的 REST/GraphQL 契約、回應語義與
  發現記錄。
- [維護者指南](../development/index.md)——測試架構、貢獻者工作流和模擬 fixture 契約。
