---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/development/index.zh-CN.md"
translation_source_sha256: "8708f914f56087b4180143beba883a20b4055715274a1f95823832bb5fd03b4b"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="维护者指南" data-pplx-source-anchor="true"></a>
# 維護者指南

在不削弱歸檔保真度或測試隔離性的前提下修改 pplx-tools 所需的契約與工作流。

<a id="选择对应文档" data-pplx-source-anchor="true"></a>
## 選擇對應文件

- [測試體系架構](testing-architecture.md)——測試分層、信任邊界和離線快照提供的
  保證。
- [測試實踐](testing.md)——當前測試清單與貢獻者工作流。
- [Fixtures 與快照](fixtures.md)——模擬數據來源、目錄約定、golden 生成和殘留檢查。

<a id="本地质量闭环" data-pplx-source-anchor="true"></a>
## 本地品質閉環

```bash
uv run python scripts/audit_docs.py
uv run python tests/scrub_fixtures.py --check
uv run pytest tests
uv run mkdocs build --strict
git diff --check
```

Fixture 輸入是確定性的模擬數據，不來自真實帳戶、即時 API 回應、`web_archive/`
或任何私有歸檔。
