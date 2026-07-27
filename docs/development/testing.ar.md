---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/development/testing.md"
translation_source_sha256: "a552c25a28367f384140a2e5cc2e9fa2a8546034b668772f5df79133d4995648"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="testing" data-pplx-source-anchor="true"></a>
# الاختبار

توجد مجموعة الاختبارات في `tests/`، خارج حزمة `pplx_export`، وتعمل
بدون اتصال بالإنترنت بالكامل. مدخلاتها المشكلة مثل واجهة برمجة التطبيقات هي بيانات محاكاة حتمية ملتزمة
تحت `tests/fixtures/`؛ لا تعتمد الاختبارات على خدمات حية أو تكوين
حقيقي على مستوى المستخدم.

تمتلك هذه الصفحة قائمة وحدات الاختبار الحالية وسير عمل المساهم.
لتصميم الانحدار، راجع
[هندسة نظام الاختبار](testing-architecture.md). لعقد بيانات الإدخال، راجع
[تركيبات الاختبار](fixtures.md).

<a id="running-the-tests" data-pplx-source-anchor="true"></a>
## تشغيل الاختبارات

```bash
uv run pytest tests
```

pytest هو تبعية تطوير معلنة. تضمن المجموعة:

- **صفر شبكة** — المدخلات المحاكاة ملتزمة؛ المسارات المتصلة بالشبكة
  مغطاة بمحاكيات، `tmp_path`، و `monkeypatch`.
- **لا تكوين مستخدم حقيقي** — قبل استيراد أي وحدة إنتاج،
  `tests/conftest.py` ينشئ تكوينًا مؤقتًا محليًا للعملية ويتجاوز
  `PPLX_EXPORT_CONFIG`. ثم يتلقى كل اختبار تكوينه الخاص `alice` / `bob` ويعيد التكوين المحلي للعملية
  بعد ذلك. تتحقق انحدارات العملية الفرعية من أن التكوين المفقود أو المعطل للمتصل
  لا يمكنه كسر جمع الاختبار.
- **ردود فعل سريعة** — في 2026-07-25، لاحظ المشروع 435 اختبارًا تم جمعها
  من 32 وحدة `test_*.py` وتم تشغيل المجموعة الكاملة في حوالي 13–25 ثانية
  عبر عمليات التحقق المحلية.
  الأعداد هي لقطة مستودع مؤرخة وستزداد.

اختيارات مفيدة:

| الأمر | التأثير |
|---|---|
| `uv run pytest tests` | المجموعة الكاملة |
| `uv run pytest tests/test_units.py` | وحدة واحدة |
| `uv run pytest tests -k snapshot` | اختبارات يتطابق معرف العقدة الخاص بها مع `snapshot` |
| `uv run pytest tests -x -q` | التوقف عند أول فشل، إخراج هادئ |
| `uv run pytest --collect-only -q` | تحديث عدد الحالات المجمعة |

<a id="current-module-inventory" data-pplx-source-anchor="true"></a>
## قائمة الوحدات الحالية

القائمة متزامنة مع المستودع بتاريخ **2026-07-27**:

<!-- audit:inventory test-modules -->

| العائلة الوظيفية | الوحدات | الغرض |
|---|---|---|
| لقطات العرض | `test_render_snapshots.py` | إعادة عرض جميع تركيبات الوضع الكامل والسيناريو المخفض المحاكاة، ثم مقارنة المنتجات الملتزمة بايت مقابل بايت |
| الأدوات الأساسية والمشتركة | `test_units.py` | الحالة، التقييد، التخطيط، التطبيع، تسمية الأصول، كشف الوضع، المسارات الآمنة، وانحدارات شاملة |
| عقود التوثيق، المهارات، والتعريب | `test_agent_skills.py`<br/>`test_audit_docs.py`<br/>`test_translate_docs.py` | عقود المهارات المحلية للمستودع بالإضافة إلى اختبارات المستودع المصغر المعزولة لمدقق التوثيق للقراءة فقط وخط أنابيب الترجمة الآلية |
| التكوين، المصادقة، والإقلاع | `test_config_external.py`<br/>`test_cookie_profiles.py`<br/>`test_credential.py`<br/>`test_init.py` | عزل التكوين الخارجي، ملفات تعريف مصدر الكوكيز، اختيار بيانات الاعتماد، والتهيئة |
| دلالات العرض وسير العمل | `test_interruptions.py`<br/>`test_stub_workflows.py`<br/>`test_answer_variants.py`<br/>`test_answer_variant_logging.py`<br/>`test_relations.py` | إسناد سير العمل، حالات المقاطعة، متغيرات الإجابة، تسجيل التدقيق، وحواف العلاقة |
| صيانة الأرشيف والمؤشر دون اتصال | `test_search_mode_backfill.py`<br/>`test_sync_deleted.py`<br/>`test_status.py` | الإثراء، سلوك الاستئناف/عدم التكرار، كشف الحذف عبر الحسابات، الحالات النهائية، ومستويات تقرير الحساب/التغيير للحالة دون اتصال |
| انحدارات المراجعة | 16 وحدة `test_fix_*.py` مدرجة أدناه | إصلاحات مستمدة من نتائج المراجعة؛ تحتفظ أسماء الوحدات بنسب المراجعة |

<a id="review-regression-lineage" data-pplx-source-anchor="true"></a>
### نسب انحدار المراجعة

تشرح معرفات المراجعة سبب وجود انحدار؛ إنها ليست الهندسة الأساسية لمجموعة الاختبارات.
التعيين متعدد إلى متعدد عمدًا: قد تغطي وحدة واحدة عدة نتائج، وقد تضيف النتيجة أيضًا حالات إلى
وحدة موضوعية موجودة.

| النسب | الوحدات المخصصة |
|---|---|
| مراجعة N | `test_fix_n01_inline_assets.py`, `test_fix_n02_spaces_link.py`, `test_fix_n03_n12.py`, `test_fix_n04_cookies.py`, `test_fix_n05_n06_n09.py`, `test_fix_n07_usage_checkpoint.py`, `test_fix_n08_throttle_overflow.py`, `test_fix_n10_table_header.py`, `test_fix_n11_batch_total.py` |
| مراجعة V3 | `test_fix_v301_nested_sources_text.py`, `test_fix_v305_export_products.py` |
| مراجعة V4 | `test_fix_v401_thread_dir_migration.py`, `test_fix_v402_manifest_count.py`, `test_fix_v403_handle_assets_idempotency.py`, `test_fix_v405_ask_post_steps.py` |
| مراجعة V5 | `test_fix_v5_review.py`، بالإضافة إلى إضافات مركزة للوحدات الموضوعية الموجودة |
| مراجعة V6 | `test_fix_v6_atomic_writes.py` |

<!-- /audit:inventory test-modules -->

تظل تعليقات الوحدة التوثيقية هي التفسير الموثوق للسلوك القديم لكل نتيجة، والسلوك المصحح، وحدود الانحدار.

<a id="how-snapshot-tests-reuse-the-production-re-render-path" data-pplx-source-anchor="true"></a>
## كيف تعيد اختبارات اللقطات استخدام مسار إعادة العرض للإنتاج

لا تنفذ اختبارات اللقطات عارضًا موازيًا:

1. `render_fixture` في `tests/conftest.py` ينسخ `raw_entries.json` المحاكاة للتركيبة، و `raw_blocks.json` الاختياري، و `thread.json` إلى دليل مؤقت.
2. يستدعي `pplx_export.commands.rerender_cmd.rerender`، نفس الدالة المستخدمة بواسطة `pplx-export re-render`.
3. يعيد مصنع التركيبة `rendered` الإخراج الجديد ودليل `golden/` الملتزم للتركيبة.
4. تقارن الاختبارات `conversation.md` وكل `turns/turn_*.md` بايت مقابل بايت.

تكمل الثوابت المحتوى مساواة البايت: يجب ألا تنهار الإجابات إلى العنصر النائب `(无)` الفارغ، ويجب ألا تتسرب بقايا تمثيل القاموس مثل `{'type': ...` إلى النص المعروض.

<a id="adding-a-test" data-pplx-source-anchor="true"></a>
## إضافة اختبار

- **منطق موجود** — أضف اختبارًا إلى الوحدة الموضوعية المطابقة. استخدم
  `tmp_path`، والمحاكيات، و `monkeypatch`؛ لا تصل أبدًا إلى الشبكة أو `~/.config` الحقيقي.
- **انحدار خطأ** — فضل الوحدة الموضوعية المطابقة. أنشئ وحدة
  `test_fix_<lineage>_<slug>.py` عندما يحتفظ الاحتفاظ بنسب المراجعة بشكل جوهري
  بإمكانية التتبع؛ لا تفترض وحدة واحدة لكل نتيجة.
- **انحدار عرض** — أضف أو قلل تركيبة محاكاة، وأعد إنشاء منتجاتها الذهبية باستخدام أداة الصيانة، ثم سجلها في
  `test_render_snapshots.py` أو أضف تأكيدات خاصة بالسيناريو.

اتبع النمط المجاور: تعليقات الأنواع،
`from __future__ import annotations`، وتعليقات الوحدة ثنائية اللغة.

<a id="see-also" data-pplx-source-anchor="true"></a>
## انظر أيضًا

- [تركيبات الاختبار](fixtures.md) — المدخلات المحاكاة، المنتجات الذهبية، وعقد الصيانة
- [هندسة نظام الاختبار](testing-architecture.md) — طبقات الاختبار وضمانات الانحدار
- [العمليات دون اتصال](../architecture/offline-operations.md) — مسار إعادة العرض للإنتاج المستخدم بواسطة اختبارات اللقطات
