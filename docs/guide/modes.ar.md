---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/modes.md"
translation_source_sha256: "dda1cfaf9d60ef912d922e65babafb68ec80cd1cdf046d661960d0de47ab77ff"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="conversation-modes" data-pplx-source-anchor="true"></a>
# أوضاع المحادثة

تأتي محادثات Perplexity بخمسة أوضاع: `search` / `deep-research` / `computer` /
`council` / `study`. يتم اكتشاف الوضع لكل سلسلة أثناء التصدير؛ وهو يحدد استجابات API التي يتم جلبها، وما يصل إلى دليل السلسلة، و[مسار الأرشيف](archive-layout.md) الذي تحصل عليه السلسلة (`<account>/<mode>/…`). يتم تسجيل الوضع المكتشف في `thread.json` (مفتاح `mode`) ويستخدمه تصفية `pplx-export batch --mode`. يمكن لـ `pplx-ask` أيضًا *إنشاء* سلاسل جديدة في أربعة من الأوضاع الخمسة (جميعها باستثناء `computer`) — انظر [pplx-ask](pplx-ask.md).

<a id="the-five-modes-at-a-glance" data-pplx-source-anchor="true"></a>
## الأوضاع الخمسة في لمحة

| الوضع | اسم واجهة المستخدم / النموذج | محتوى الدور | الاستشهادات | المنتجات | الكتل المنظمة التي تم جلبها |
|---|---|---|---|---|---|
| `search` | "الأفضل" (`pplx_pro`؛ المعامل `STUDIO`/`pplx_beta` يتم تعيينها هنا أيضًا) | استعلام + إجابة، خطوات نصية | على مستوى الدور + على مستوى السلسلة `sources.*` | — | لا (`raw_blocks.json` غائب) |
| `deep-research` | "بحث عميق" (`pplx_alpha`، ثابت، لا محدد) | خطوات البحث بما في ذلك `RESEARCH_ANSWER` | نعم | `report.md` (تقرير كامل) | نعم |
| `computer` | Computer (`pplx_asi_opus`، `pplx_asi_opus_thinking`) | كامل `workflow_block`: سرد، استدعاءات أدوات، مطالبات/خطوات وكيل فرعي، استشهادات لكل خطوة | لكل خطوة + دور + سلسلة | ملفات ذات إصدارات في `assets/` + تشغيلات وكيل فرعي | نعم |
| `council` | مجلس النماذج (`pplx_agentic_research`؛ ثلاثة نماذج افتراضيًا) | خطوة `COUNCIL_RESEARCH`؛ سير عمل `LLM_COUNCIL` المتداخل لكل نموذج مطوي في `<details>` (جولات بحث، جميع المصادر، إجابة كاملة لكل نموذج) | لكل نموذج + مجمعة | إجابات كل نموذج مقارنة جنبًا إلى جنب | نعم |
| `study` | دراسة (`pplx_study`) | خطوات/استشهادات عبر الكتل (تم التحقق من احتوائها أيضًا على أصول) | نعم | الأصول عند وجودها | نعم |

<a id="how-the-mode-is-decided" data-pplx-source-anchor="true"></a>
## كيف يتم تحديد الوضع

سلطة الكشف هي الحقل الخاص بالمنصة **`entry.search_mode`**
(`SEARCH_MODE_MAP`، `normalize.py:50-59`)، الذي تم جمعه عبر جميع الإدخالات
(`normalize.py:106-115`). تم التحقق منه مقابل تكوين النموذج الرسمي
(`GET /rest/models/config/v2`): `default_models.search=pplx_pro` (واجهة المستخدم "الأفضل")،
`default_models.research=pplx_alpha` (واجهة المستخدم "بحث عميق")، والقيم تتطابق واحدًا لواحد مع
أوضاع المحادثة:

| قيمة `search_mode` | الوضع |
|---|---|
| `ASI` | `computer` |
| `AGENTIC_RESEARCH` | `council` |
| `STUDY` | `study` |
| `RESEARCH` | `deep-research` |
| `SEARCH`، `STUDIO` | `search` |

قواعد التعارض (`detect_mode`، `normalize.py:66-128`):

- **تبديل الوضع داخل سلسلة واحدة** (الإدخالات غير متوافقة): خذ الأعلى حسب الخصوصية —
  **computer > council > study > deep-research > search** (`_MODE_SPECIFICITY`،
  `normalize.py:63`) — و `log.warning`.
- **التعارض مع الإشارات النهائية** (أسماء الخطوات / `display_model`): `search_mode` يفوز،
  `log.warning` (`normalize.py:120-123`).
- **`search_mode` غائب تمامًا** → السلسلة الأصلية: عنوان URL يحتوي على `/computer/tasks/` أو
  `metadata.mode == '4'` أو وضع الفهرس ∈ `ASI`/`COMPUTER` → `computer`؛ خطوة `COUNCIL_RESEARCH`
  → `council`؛ خطوة `RESEARCH_ANSWER` → `deep-research`؛ إشارة `display_model` زائدة
  (`DISPLAY_MODEL_MODE`، `normalize.py:32-37`) تفوز عند التعارض؛ لا شيء يضرب →
  `search` افتراضيًا.
- **غياب جميع الإشارات لا يعني الاستنتاج بالبحث**: لا يزال خط الأنابيب يجلب الكتل المنظمة
  (`adapter.py:83-89`) لذلك لا يمكن لانحراف حقل المنصة إسقاط `raw_blocks.json` بصمت.

!!! ملاحظة "لماذا `pplx_alpha` ليس إشارة كشف"
    `pplx_alpha` هو النموذج المخصص لـ RESEARCH — إنه *الهدف* الذي يجب على المصنف اكتشافه،
    وليس دليلاً على الكشف، لذلك تم استبعاده عمدًا من جدول التعيين
    (تعليق `normalize.py:15-31`).

شجرة القرار الكاملة مع كل فرع: [خط أنابيب التصدير — كشف الوضع](../architecture/export-pipeline.md).

<a id="where-sub-agent-payloads-land" data-pplx-source-anchor="true"></a>
## أين تصل حمولات الوكيل الفرعي

تشغيلات Computer/council تولد سير عمل وكيل فرعي في الخلفية. يتم عرض كل
`workflow_payload` في الخلفية في **مكان واحد بالضبط، أبدًا مرتين**؛ على مستوى المستخدم،
المواقع الثلاثة المحتملة هي:

1. **مرساة — داخل الدور البادئ**: الدور الذي بدأ الوكيل الفرعي يحمل معرف حمولة مطابق،
   لذلك يتم عرض التشغيل مضمنًا في عملية عمل ذلك الدور
   (`turns/turn_NNNN.md`)، مع المطالبة والخطوات والإجابة والمصادر.
2. **دور وهمي — قسم "子代理工作" (عمل الوكيل الفرعي)**: دور وهمي `subagent_result` ضمن
   نافذة إكمال مدتها 10 ثوانٍ يمتص الحمولة؛ لا يتم إعادة ملء الإجابة.
3. **ملحق السلسلة — نهاية `conversation.md`**: كل ما تبقى (التشغيلات المتقطعة لا تنتج
   إشعار إكمال، لذا فإن المستويين الأولين يفتقدانها بالضرورة) يتم أرشفته حرفيًا تحت
   "## 后台任务（未归入轮次）" (مهام الخلفية (غير المخصصة للأدوار)) — لا تخمين
   لإسناد الوقت، أي حالة مقبولة.

قواعد المطابقة، وهياكل البيانات، وضمانات الاستهلاك الفردي:
[الوكلاء الفرعيون والانقطاعات](../architecture/subagents-interruptions.md).

<a id="interruptions-non-completed-workflows" data-pplx-source-anchor="true"></a>
## الانقطاعات: سير العمل غير المكتمل

يتم شرح سير العمل الذي لم يكتمل مضمنًا أينما تم عرضه — في عناوين عملية العمل،
وعناوين الوكيل الفرعي، وملخصات `<details>` المتداخلة. الشروح الثلاثة
(`parsers.classify_wf_status`، `parsers.py:263-284`):

| الشرح | الشرط | المعنى |
|---|---|---|
| `⏸ 限额中断（内容截至中断点）` (مقيد بالحد — المحتوى يتوقف عند نقطة الانقطاع) | `WORKFLOW_AWAITING_NEXT_STEPS` + `locked_reason=spending_limit_exceeded` | تم استنفاد حد الإنفاق؛ توقف سير العمل في منتصف التشغيل |
| `⏸ 中断待续` (مقاطع، في انتظار الاستمرار) | `WORKFLOW_AWAITING_NEXT_STEPS` بدون `locked_reason` | مقاطع، يمكن متابعته على المنصة |
| `⛔ 已取消` (ملغي) | `WORKFLOW_CANCELED` | تم الإلغاء بواسطة المستخدم أو المنصة |

- `COMPLETED` لا يتم شرحه أبدًا (السلاسل السليمة تحصل على فرق صفري)؛ قيم الحالة المستقبلية غير المعروفة
  تبقى صامتة.
- يتم أيضًا تسجيل كل حالة مشروحة في `thread.json.interruptions` كـ
  `{location, kind, headline, status}` — المواقع تبدو مثل `turn_0007`،
  `turn_0011/subagent`، `turn_0024/subagent_stub`، `background_unassigned`
  (`parsers.py:535-583`؛ المفتاح غائب في السلاسل السليمة).
- **الاستئناف لا يحتاج إلى حالة خاصة**: عندما تواصل سلسلة مقاطعة على المنصة،
  يتغير `lastUpdated` الخاص بها، ويعيد التصدير المتزايد التالي جلبها، وتختفي الشروح
  بمجرد اكتمال سير العمل. انظر
  [المزامنة المتزايدة](incremental-sync.md).

قيم الحالة المرصودة وتوزيعها: [استجابات API والأخطاء](../reference/api/api-responses-errors.md)؛
آلة الحالة: [الوكلاء الفرعيون والانقطاعات](../architecture/subagents-interruptions.md).

<a id="answer-rewrite-variants-answer_variants" data-pplx-source-anchor="true"></a>
## متغيرات إعادة كتابة الإجابة (answer_variants)

عندما تعيد المنصة كتابة إجابة (تجارب A/B)، يكون المتغير المستبدل غير مرئي في
API — يتم إرجاع الإجابة المحددة فقط، بينما يترك المتغير الخاسر أثرًا في
`entries[].side_by_side_metadata` وقد يتم حذفه لاحقًا (تم تأكيد روابط المتغيرات الميتة:
403 `VIEW_THREAD_NOT_ALLOWED`). تجعل الأداة "حدثت إعادة كتابة" قابلة للملاحظة:

- **التسجيل**: تتم كتابة النتائج ذات المعايير الضيقة إلى `thread.json.answer_variants`
  (`fs_writer.py:247-252`؛ المفتاح غائب بدون نتائج) وتُلحق بالسجل المركزي
  `index/answer_variants_log.jsonl`، مع إزالة التكرار حسب (السلسلة، الإدخال) وكونها عديمة التأثير
  (`variant_log.py:76`).
- **التنبيهات**: سطر تحذير WARNING واحد قابل للبحث `ANSWER_VARIANT_DETECTED` مع حقول تحديد كاملة
  (thread uuid/uuid8، entry_uuid، sibling_uuid، selection_status، experiment_role) في
  كل نتيجة عبر الإنترنت؛ `re-render` يعيد التسجيل دون اتصال ويحذر فقط عند إضافة محتوى أو
  تغييره، لذا تبقى عمليات إعادة التشغيل عبر المكتبة هادئة؛ يلحق الملخص الدفعي عدد النتائج ⚠.
- **إعادة الأرشفة اليدوية**: المتغيرات الشقيقة هي روابط ميتة تجريبيًا، لذا لا يمكن
  **عادةً استرداد الإجابة البديلة عبر API**. عند وجود نتيجة، قم بتأكيد الإجابة البديلة
  يدويًا على الفور (واجهة مستخدم المنصة، سجلاتك الخاصة، لقطات الشاشة)؛ إذا حصلت عليها، سجلها كـ
  `rewritten_answer_variant.md` داخل دليل السلسلة. إذا لم تحصل عليها، فإن
  `thread.json.answer_variants` بالإضافة إلى سجل jsonl هما السجل النهائي القابل للتتبع.

سلسلة الكشف وإعادة التسجيل دون اتصال: [العمليات دون اتصال](../architecture/offline-operations.md)؛
دلالات الحقل وأدلة الروابط الميتة: [استجابات API والأخطاء](../reference/api/api-responses-errors.md).

<a id="rendering-fidelity-principles" data-pplx-source-anchor="true"></a>
## مبادئ دقة العرض

بغض النظر عن الوضع، يتبع العرض نفس عقد الدقة:

- **الإجابات كاملة، غير مقطوعة أبدًا** — تمت إزالة الحد القديم `[:4000]` لأنه كان يقطع
  الجمل في منتصفها (`render.py:645-647`).
- **الجداول غير مقطوعة أبدًا** — `WORKFLOW_ITEM_TABLE` يعرض كل صف وعمود، مع هروب
  `|` والأسطر الجديدة في الرؤوس والخلايا بحيث يبقى هيكل Markdown سليمًا
  (`render.py:211-243`).
- **الاستشهادات الكاملة** — ثلاث قنوات جمع (`entry.sources` + `FINAL.web_results` +
  `WORKFLOW_ITEM_SOURCES`)، مع إزالة التكرار حسب URL في `sources.*`؛ لا يتم إسقاط أي شيء تم الاستشهاد به.
- **JSON الخام لـ API هو حدود المحتوى** — كل ما يتم عرضه يأتي من
  `raw_entries.json` / `raw_blocks.json`؛ ما لا يعيده API (مثل متغير إجابة مستبدل)
  لا يمكن عرضه، ويتم إظهاره من خلال السجلات بدلاً من اختراعه.
- **طي واجهة المستخدم، توسيع الأرشيف** — التفاصيل التي تخفيها واجهة المستخدم خلف الطيات والنقرات
  (سرد سير عمل computer وإدخال/إخراج الأداة، تشغيلات council لكل نموذج، خطوات الوكيل الفرعي) يتم
  عرضها بالكامل؛ كتل `<details>` تحافظ على مخطط المستند قابلاً للقراءة دون فقدان
  المعلومات (`render.py:46`، `render.py:404-413`).
- **المتانة الهيكلية** — يتم تحديد حجم أسوار الكود حسب محتواها (`_fence_for`،
  `render.py:28-43`) بحيث لا يمكن لمخرجات الأداة التي تحتوي على أسوارها الخاصة قلب الاقتران، ويتم
  تطبيع محددات LaTeX إلى `$$` / `$` مع حماية مقاطع الكود
  (`normalize_math_delims`).

كيف تجعل الاستجابات الخام المحتجزة كل هذا قابلاً لإعادة التوليد دون اتصال:
[خط أنابيب التصدير](../architecture/export-pipeline.md) و[العمليات دون اتصال](../architecture/offline-operations.md).

<a id="see-also" data-pplx-source-anchor="true"></a>
## انظر أيضًا

- [تخطيط الأرشيف](archive-layout.md) — أين توجد ملفات كل وضع
- [pplx-ask](pplx-ask.md) — إنشاء سلاسل جديدة في كل وضع
- [المزامنة المتزايدة](incremental-sync.md) — إعادة جلب السلاسل المستمرة
- [خط أنابيب التصدير](../architecture/export-pipeline.md) — شجرة قرار كشف الوضع الكاملة
- [الوكلاء الفرعيون والانقطاعات](../architecture/subagents-interruptions.md) — شلال الإسناد وآلة الحالة
- [استجابات API والأخطاء](../reference/api/api-responses-errors.md) — قيم الحقول المرصودة
