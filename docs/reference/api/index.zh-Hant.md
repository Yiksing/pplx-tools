---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/reference/api/index.zh-CN.md"
translation_source_sha256: "6e3c3f3adb7e4fa7d731b9d510aacd07fb9c71885c4618222a12f066997cd316"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="web-api-参考" data-pplx-source-anchor="true"></a>
# Web API 參考

`pplx-export` 與 `pplx-ask` 所使用的 Perplexity REST 和 GraphQL 行為觀察記錄。

!!! warning "觀察到的介面，而非穩定性承諾"

    本區依據專案從 Web 應用、歸檔回應、前端 bundle 和當前實現中觀察到的行為整理，
    不是 Perplexity 官方 API 契約。修改聯網程式碼前，應重新驗證帶日期的觀察結論。

<a id="推荐阅读顺序" data-pplx-source-anchor="true"></a>
## 推薦閱讀順序

1. [認證模型](api-authentication.md)——會話 cookie、令牌、關聯帳戶與身份。
2. [GraphQL](api-graphql.md)——持久化查詢、APQ 識別碼與在用操作。
3. [REST 端點](api-rest-endpoints.md)——按用途分組的已觀察端點。
4. [回應與錯誤語義](api-responses-errors.md)——回應形態、解析紀律、終態和風控行為。
5. [發現方法與路線圖](api-discovery-roadmap.md)——端點發現方法和仍待確認的問題。

<a id="相关实现文档" data-pplx-source-anchor="true"></a>
## 相關實作文檔

- [pplx-ask 與多帳戶](../../architecture/ask-and-accounts.md)
- [限頻與錯誤處理](../../architecture/rate-limiting-errors.md)
- [故障排除](../../guide/troubleshooting.md)
