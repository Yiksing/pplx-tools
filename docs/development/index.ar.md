---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/index.md"
translation_source_sha256: "fc5f2fa607251be85bdc126f3701791c17d7330461b2ab49402ea485fcc961b7"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="maintainer-guide" data-pplx-source-anchor="true"></a>
# دليل المشرف

العقود وسير العمل لتغيير أدوات pplx دون إضعاف دقة الأرشيف أو عزل الاختبار.

<a id="choose-the-right-document" data-pplx-source-anchor="true"></a>
## اختر المستند المناسب

- [هندسة الاختبار](testing-architecture.md) — طبقات الاختبار، حدود الثقة، والضمانات التي توفرها اللقطات غير المتصلة.
- [ممارسات الاختبار](testing.md) — جرد الاختبار الحالي وسير عمل المساهم.
- [التركيبات واللقطات](fixtures.md) — مصدر البيانات المحاكاة، اصطلاحات الدليل، التوليد الذهبي، وفحوصات البقايا.

<a id="local-quality-loop" data-pplx-source-anchor="true"></a>
## حلقة الجودة المحلية

```bash
uv run python scripts/audit_docs.py
uv run python tests/scrub_fixtures.py --check
uv run pytest tests
uv run mkdocs build --strict
git diff --check
```

مدخلات التركيبات هي بيانات محاكاة حتمية. لا يتم نسخها من حسابات حية، أو استجابات API حية، أو `web_archive/`، أو أرشيفات خاصة.
