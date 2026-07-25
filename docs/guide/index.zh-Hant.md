---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/index.zh-CN.md"
translation_source_sha256: "36473d77356f8d36bd928e79c8c3584fc1e4e8a7c0e269b00dbb63bef56b458c"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

# 使用指南

面向任務的 `pplx-export` 與 `pplx-ask` 安裝、配置和運行文檔。

<a id="开始使用" data-pplx-source-anchor="true"></a>
## 開始使用

- [快速上手](getting-started.md)——安裝命令、初始化配置並執行首次匯出。
- [配置](configuration.md)——帳戶、cookie 來源、輸出根目錄和 BOT 空間。

<a id="命令参考" data-pplx-source-anchor="true"></a>
## 命令參考

- [pplx-export](pplx-export.md)——索引、單線程匯出與批量歸檔。
- [pplx-ask](pplx-ask.md)——search、deep-research、council 和 study 流式發問。
- [維護命令](maintenance-commands.md)——重渲、補錄、關係圖與同步操作。

<a id="归档与同步" data-pplx-source-anchor="true"></a>
## 歸檔與同步

- [歸檔結構](archive-layout.md)——檔案、索引、狀態和保留的原始回應。
- [會話模式](modes.md)——各支援模式的產物邊界。
- [增量同步](incremental-sync.md)——早停、檢查點和斷點續跑語義。

<a id="运行与排错" data-pplx-source-anchor="true"></a>
## 運行與排錯

- [限頻紀律](rate-limiting.md)——安全請求節奏與排程。
- [故障排查](troubleshooting.md)——常見故障及恢復路徑。

需要理解實現機制時，繼續閱讀[系統架構閱讀地圖](../architecture/index.md)。
