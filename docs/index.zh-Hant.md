---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/index.zh-CN.md"
translation_source_sha256: "49d67dcdb3d8715b15c05689069b96ae47f030e3c8c86ece51558818b535fc14"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="perplexity-命令行工具集" data-pplx-source-anchor="true"></a>
# Perplexity 命令列工具集

<p class="homepage-scope-note" role="note">
  <strong>適用於現有訂閱，而非按量計費 API</strong>
</p>

Perplexity 對話記錄歸檔與互動查詢工具（`pplx-export` / `pplx-ask` 雙命令）。

透過瀏覽器 cookie 直連 Perplexity REST/GraphQL API，把對話（含步驟、引文、深研報告、
computer 資產、子代理工作流）完整歸檔為本地 Markdown + JSON。成功匯出會同時保留
原始回應與渲染產物，因此無需重抓即可離線重渲。

<a id="简介" data-pplx-source-anchor="true"></a>
## 簡介

除了歸檔歷史對話之外，本項目的目的更多是讓離數據更近、有更強算力的本地 agent
具備一定的 Perplexity Computer 能力。透過在工作循環中直接存取 Perplexity
深度研究模式生成的報告，本地 agent 可以利用高品質資訊更精確地調整程式碼中的關鍵
參數，同時更充分地利用現有的 Perplexity Max 訂閱。

> 截止至7月20日，Perplexity 並未提供類Unix環境中的官方 CLI
> 我們注意到官方於7月23日提供了Computer模式中所使用的pplx工具的公開發布版本；但該工具仍是按量計費的

但它並非 Computer 模式的完整替代。有兩項能力無法複製：

- 深度研究 skill 可自由指定模型；
- 模型委員會 skill 可指定多個不同模型分別深度研究、輸出報告並直接橫向比較。

倉庫中的 [`_platform_context/`](https://github.com/Yiksing/pplx-tools/tree/main/_platform_context)
目錄存檔了一些系統提示詞和運行規則，可幫助在本地近似 Computer 的部分工作流，
包括深度研究模式選擇和子代理模型選擇。

<a id="功能概览" data-pplx-source-anchor="true"></a>
## 功能概覽

<a id="pplx-export-归档你的-library" data-pplx-source-anchor="true"></a>
### `pplx-export` —— 歸檔你的 library

- library 索引與空間索引
- 單執行緒/批次匯出（增量早停 + 斷點續跑）
- 資產補救與用量補錄
- 對話關係圖
- 離線重渲（`re-render`，零網路）
- 週期增量 cron 片段

<a id="pplx-ask-在命令行发问" data-pplx-source-anchor="true"></a>
### `pplx-ask` —— 在命令列發問

- SSE 串流發問（search / deep-research / council / study 四模式）
- 完成後自動移入 BOT 空間、已讀回執
- 建立的執行緒自動歸檔——供其他 agent 呼叫檢索即時資訊

五種模式的產物邊界（引文/報告/資產/子代理）見[模式](guide/modes.md)；渲染保真
原則見[匯出管線](architecture/export-pipeline.md)。

!!! note "文件來源"

    MkDocs 站點中的多數頁面依據當前程式碼與測試生成或重建；部分頁面也保留了此前與
    agent 討論形成的設計背景、觀察記錄和決策。若文件表述與實現不一致，以當前程式碼
    和測試為準。

<a id="接下来去哪" data-pplx-source-anchor="true"></a>
## 接下來去哪

- **使用工具**——按任務閱讀[使用指南](guide/index.md)。
- **理解實現**——從[系統架構閱讀地圖](architecture/index.md)進入。
- **處理已觀察到的 Web 介面**——查閱 [Web API 參考](reference/api/index.md)。
- **安全修改專案**——遵循[維護者指南](development/index.md)。
