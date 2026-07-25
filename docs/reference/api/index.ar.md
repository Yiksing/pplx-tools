---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/index.md"
translation_source_sha256: "ca4f72f6b2dd481ccfbaebc2b4a1c807271077753873ce318b60d94c60f54228"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="web-api-reference" data-pplx-source-anchor="true"></a>
# مرجع واجهة برمجة التطبيقات (API) للويب

سلوك REST وGraphQL المرصود المستخدم من قبل Perplexity و
`pplx-export` و `pplx-ask`.

!!! warning "واجهة مرصودة، وليست ضمان استقرار"

    تصف هذه الصفحات السلوك الذي رصده المشروع من تطبيق الويب،
    والاستجابات المؤرشفة، وحزم الواجهة الأمامية، والتنفيذ الحالي.
    وهي ليست عقد API رسمي لـ Perplexity. يجب إعادة التحقق من
    الملاحظات المؤرخة قبل تغيير الكود الموجه للشبكة.

<a id="reading-order" data-pplx-source-anchor="true"></a>
## ترتيب القراءة

1. [نموذج المصادقة](api-authentication.md) — ملفات تعريف الارتباط للجلسة، الرموز المميزة،
   الحسابات المرتبطة، والهوية.
2. [GraphQL](api-graphql.md) — الاستعلامات المحفوظة، معرفات APQ،
   والعمليات المستخدمة.
3. [نقاط نهاية REST](api-rest-endpoints.md) — نقاط النهاية المرصودة مجمعة حسب
   الغرض.
4. [الاستجابات ودلالات الأخطاء](api-responses-errors.md) — أشكال الاستجابة،
   قواعد التحليل، الحالات النهائية، وسلوك التحكم في المخاطر.
5. [طرق الاكتشاف وخريطة الطريق](api-discovery-roadmap.md) — كيفية العثور على نقاط النهاية
   وأي شكوك لا تزال قائمة.

<a id="related-implementation-documents" data-pplx-source-anchor="true"></a>
## مستندات التنفيذ ذات الصلة

- [pplx-ask والحسابات](../../architecture/ask-and-accounts.md)
- [تحديد المعدل ومعالجة الأخطاء](../../architecture/rate-limiting-errors.md)
- [استكشاف الأخطاء وإصلاحها](../../guide/troubleshooting.md)
