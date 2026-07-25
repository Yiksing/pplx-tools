---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/index.md"
translation_source_sha256: "a64006f8b94ad04a3bc498468e674f3b8a22f27242c9bb7b8c5a9252019cc751"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="architecture-reading-map" data-pplx-source-anchor="true"></a>
# خريطة قراءة الهندسة المعمارية

مرجع على مستوى الآلية لأدوات pplx (`pplx-export` / `pplx-ask`):
التبعيات، خطوط الأنابيب، آلات الحالة، عقود البيانات، وحدود الموثوقية.
للاستخدام الموجه نحو المهام، ابدأ بـ [دليل المستخدم](../guide/index.md).

!!! note "النطاق ومصدر الحقيقة"

    تشرح هذه الصفحات هندسة `pplx_export/` للوكلاء والمهندسين الذين يحافظون على المشروع.
    تستخدم مراجع الأسطر `file.py:NN`، نسبة إلى `pplx_export/`.
    تم التحقق من الأوصاف مقابل المستودع في 2026-07-23 (`__version__ = "0.1.0"`،
    `pplx_export/__init__.py:31`)؛ يظل الكود الحالي والاختبارات موثوقة.

<a id="start-with-the-system-map" data-pplx-source-anchor="true"></a>
## ابدأ بخريطة النظام

- [نظرة عامة على الهندسة المعمارية](overview.md) — الطبقات، مسؤوليات الوحدات،
  ورسم بياني للتبعيات على مستوى الاستيراد.

<a id="follow-a-runtime-flow" data-pplx-source-anchor="true"></a>
## اتبع تدفق وقت التشغيل

- [خط أنابيب التصدير](export-pipeline.md) — الجلب، الاحتفاظ بالاستجابة الخام،
  اكتشاف الوضع، وعرض Markdown.
- [الوكلاء الفرعيون والمقاطعات](subagents-interruptions.md) — إسناد الحمولة
  ودلالات المقاطعة/الاستئناف.
- [pplx-ask والحسابات](ask-and-accounts.md) — الاستعلامات المتدفقة و
  تبديل ملفات تعريف الارتباط متعددة الحسابات.

<a id="understand-data-and-reliability" data-pplx-source-anchor="true"></a>
## فهم البيانات والموثوقية

- [نموذج البيانات وعقد الدليل](data-model.md) — النماذج، حدود الكتابة،
  وعقد الأرشيف على القرص.
- [تحديد المعدل ومعالجة الأخطاء](rate-limiting-errors.md) — التقييد،
  التراجع، الحالات النهائية، وتوجيه الأخطاء.
- [العمليات غير المتصلة بالإنترنت](offline-operations.md) — إعادة العرض بدون شبكة،
  إعادة بناء العلاقات، وخطوط أنابيب الصيانة المحلية.

<a id="related-references" data-pplx-source-anchor="true"></a>
## مراجع ذات صلة

- [مرجع Web API](../reference/api/index.md) — عقود REST/GraphQL المرصودة،
  دلالات الاستجابة، وملاحظات الاكتشاف.
- [دليل المشرف](../development/index.md) — هندسة الاختبار، سير عمل المساهم،
  وعقود المحاكاة الثابتة.
