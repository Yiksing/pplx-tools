---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/development/index.zh-CN.md"
translation_source_sha256: "8708f914f56087b4180143beba883a20b4055715274a1f95823832bb5fd03b4b"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="维护者指南" data-pplx-source-anchor="true"></a>
# メンテナーガイド

アーカイブの忠実性やテストの分離性を損なわずに pplx-tools を変更するために必要な契約とワークフロー。

<a id="选择对应文档" data-pplx-source-anchor="true"></a>
## 関連ドキュメントの選択

- [テストアーキテクチャ](testing-architecture.md)——テストの階層、信頼境界、オフラインスナップショットが提供する保証。
- [テストプラクティス](testing.md)——現在のテストチェックリストとコントリビューターワークフロー。
- [フィクスチャとスナップショット](fixtures.md)——モックデータソース、ディレクトリ規則、ゴールデンファイル生成、残留チェック。

<a id="本地质量闭环" data-pplx-source-anchor="true"></a>
## ローカル品質フィードバックループ

```bash
uv run python scripts/audit_docs.py
uv run python tests/scrub_fixtures.py --check
uv run pytest tests
uv run mkdocs build --strict
git diff --check
```

フィクスチャ入力は決定論的なモックデータであり、実際のアカウント、リアルタイムAPIレスポンス、`web_archive/`、またはプライベートアーカイブから取得したものではありません。
