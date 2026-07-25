---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-discovery-roadmap.md"
translation_source_sha256: "60c675dcc583c059cd489ea085f9c2923f9447f7bbafb0a7ac991fee9f8add08"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="endpoint-discovery-and-improvement-roadmap" data-pplx-source-anchor="true"></a>
# خريطة طريق اكتشاف نقاط النهاية وتحسينها

*جزء من مرجع واجهة برمجة تطبيقات الويب Perplexity — الخريطة الكاملة في [فهرس واجهة برمجة التطبيقات](index.md).*

<a id="known-unexplored-tbd-items" data-pplx-source-anchor="true"></a>
## العناصر المعروفة غير المستكشفة / المقرر تحديدها لاحقًا

- حقل الفرز `list_collection_threads` ودلالات `total_threads` الدقيقة
  (لقطة حساب نشط يوليو 2026: تم الإبلاغ عن 99 عنصرًا مقابل 27 عنصرًا من المستوى الأعلى).
- النطاق الكامل لقيم `threadAccess`/`access`/`user_permission` (عينة ملاحظة يوليو 2026:
  threadAccess 5 عادي، 1 مع 🔒؛ collection access 1؛
  permission 4 مالك / 2 يمكنه التحرير؛ بيانات الأصول تحمل أيضًا thread_access).
- أشكال المعلمات الصحيحة لـ `list_ask_threads`، `list_scheduled_computer_tasks` (GET مباشر يعيد 400).
- هياكل الاستجابة لـ `collections/*/request-access-info`، `spaces/<uuid>/recurring_tasks`، `assets/<id>/members`.
- سبب عدم تسجيل عمليات GraphQL في لوحة التحكم (PERSISTED_QUERY_NOT_FOUND): اختلاف الإصدار أو حصر السياق؛
  عند الحاجة، إعادة الاستخراج باستخدام التجزئات الحية من التقاط الشبكة.
- تقسيم العمل بين `frontend_uuid` مقابل `uuid` مقابل `context_uuid` في سلاسل الكمبيوتر.
- حقول إشارات API لسلاسل الفروع المشتركة عبر الحسابات (branch_of)
  (مؤشر الأصل / علامة الفرع) — تم تأكيد الآلية (نهاية
  [§3.3](api-rest-endpoints.md))؛ لا توجد نسخة مؤرشفة حتى 2026-07-23؛
  تحقق وسجل عند ظهور الأولى.

<a id="endpoint-discovery-method-frontend-bundle-static-analysis-zero-api-cost-established-2026-07-20" data-pplx-source-anchor="true"></a>
## طريقة اكتشاف نقطة النهاية: تحليل ثابت لحزمة الواجهة الأمامية (بتكلفة API صفرية؛ تم إنشاؤها في 2026-07-20)

تم اكتشاف **147 نقطة نهاية `/rest/`** في مسار واحد؛ الطريقة قابلة لإعادة الاستخدام (إعادة التشغيل بعد إعادة تصميم الواجهة الأمامية):

1. يشير إدخال تحميل الصفحة `_spa/assets/index.html-*.js` إلى `bootstrap-*.js` (يحتوي وقت التشغيل على جميع تعيينات الأجزاء)؛
2. استخراج 682 اسم ملف جزء (نمط `<name>-<hash8>.js`) من أداة التمهيد؛ تصفية المتعلقة بـ API حسب الاسم
   (client/api/thread/collection/space/computer…)؛
3. التنزيل مباشرة من CDN العام `https://pplx-next-static-public.perplexity.ai/_spa/assets/<chunk>.js`
   (لا حاجة لملف تعريف ارتباط)؛ وحدات المحور: `platform-core-*` (عميل API)، `spa-shell-*`، `spa-metadata-*`؛
4. `grep -o '/rest/[a-zA-Z0-9_/.$_{}-]*'` ينتج قائمة نقاط النهاية (147)؛
5. الأجزاء أيضًا تسرب أشكال الاستدعاء (مثل `format:'md'` و `file_content_64` للتصدير).
6. خرائط المصدر موجودة أيضًا: `https://pplx-static-sourcemaps.perplexity.ai/_spa/assets/<chunk>.js.map` (لم يتم استكشافها).

<a id="appendix-147-endpoints-grouped-by-category-archive-relevance-marked" data-pplx-source-anchor="true"></a>
### ملحق: 147 نقطة نهاية مجمعة حسب الفئة (تم وضع علامة على الصلة بالأرشفة)

- **thread**: `/rest/thread/{entry_uuid_or_slug}`، `/rest/thread/export`★، `/rest/thread/{uuid}/members`،
  `/rest/thread/list_recent`، `/rest/thread/list_ask_threads`، `/rest/thread/list_pinned_ask_threads`،
  `/rest/thread/list_scheduled_computer_tasks`، `/rest/thread/request-access-info/{uuid}`
- **collections/spaces**★: راجع الجدول الكامل في [§3.3](api-rest-endpoints.md) (يشمل batch_move/batch_remove، list_user_collections، request-access-info،
  recurring_tasks، pins/threads، scheduled_threads)
- **assets**★: `/rest/assets/{asset_id}/data`، `/rest/assets/{asset_id}/members`،
  `/rest/assets/{asset_id}/published-access`، `/rest/assets/sites/{site_id}/publish-info`
- **analytics**: `/rest/analytics/computer/usage`، `/rest/analytics/computer/usage/members`
  (كلاهما 403 NOT_ORG_MEMBER — حسابات المؤسسات فقط)
- **models/skills**: `/rest/models/config(/v2)`، `/rest/skills`، `/rest/skills/selectable`،
  `/rest/skills/grants`، `/rest/skills/submissions(/source)`
- **files/uploads**: `/rest/file-repository/*` (list/download/get-file-upload-urls/delete-files…)،
  `/rest/files/list(/list-infinite/list-errors)`، `/rest/uploads/(batch_)create_upload_url(s)`،
  `/rest/connectors/attachments/upload`
- **tasks/computer**: `/rest/tasks/`، `/rest/tasks/{task_id}`، `/rest/tasks/shortcuts/mentions`،
  `/rest/tasks/shortcuts/paste/{copy_token}`، `/rest/computer/asset`، `/rest/computer/menu`،
  `/rest/computer/onboarding_cards`
- **user/auth**: `/rest/user/settings`، `/rest/user/get_user_ai_profile`، `/rest/user/promotions`،
  `/rest/user/site-instructions`، `/rest/auth/get_special_profile`، `/rest/visitor/*`
- **billing/stripe**: `/rest/billing/*` (credits/paypal/subscription…)، `/rest/stripe/*`
- **enterprise/org**: `/rest/enterprise/*`، `/rest/organizations/{id}/credit-limits*`،
  `/rest/pplx-api/v2/enterprise-api-org`
- **sse**: `/rest/sse/attachment_processing/subscribe`، `/rest/sse/index_files`،
  `/rest/sse/perplexity_terminate`، `/rest/sse/related-queries/{entry_uuid}`
- **verticals** (غير ذات صلة بالأرشفة): `/rest/finance/*`، `/rest/sports/*`، `/rest/travel/hotels/{slug}`،
  `/rest/health-assistant/*`، `/rest/article/{uuid_or_slug}`
- **misc**: `/rest/pins`، `/rest/rate-limit/(all|status)`، `/rest/notifications/web-push/*`،
  `/rest/attribution/*`، `/rest/homepage-widgets/upsell`، `/rest/ntp/upsell/`، `/rest/sidebar/upsell/`،
  `/rest/incentives/comet-activation`، `/rest/connector-service/usage`

(★ = ذات صلة مباشرة بالأرشفة)

<a id="endpoint-tool-capability-status-and-roadmap" data-pplx-source-anchor="true"></a>
## حالة قدرة نقطة النهاية → الأداة وخريطة الطريق

تمت مزامنة حالة التنفيذ أدناه مع الكود الحالي ومجموعة الاختبارات
في **2026-07-24**. يحتفظ دليل API بتاريخ ونطاق الملاحظة الحية الأصلية
أو التحليل الثابت؛ لم يقم هذا التزامن الوثائقي بإعادة فحص نقاط النهاية الخاصة. إحصائيات الحساب/الأرشيف هي لقطات، وليست ضمانات على مستوى المنصة.

معاني الحالة:

- **تم التنفيذ** — مسار CLI حالي أو مسار إنتاج يستخدم نقطة النهاية للقدرة المذكورة.
- **جزئي** — نقطة النهاية قيد الاستخدام، لكن القدرة النهائية في خريطة الطريق لا تزال غير مكتملة.
- **تم الاختبار، غير مدمج** — تم ملاحظة سلوك API الحي، لكن لا يوجد مسار أداة يستهلكه.
- **مخطط له** — يوجد دليل، لكن التنفيذ لم يبدأ بعد.
- **محظور** — يوجد مانع معروف من المنبع أو البروتوكول يمنع التنفيذ.
- **مغلق** — دليل يدحض الاستخدام المقترح أو يضعه خارج النطاق.

<a id="capability-status-matrix" data-pplx-source-anchor="true"></a>
### مصفوفة حالة القدرة

| نقطة النهاية / العملية | أساس التحقق | التكامل الحالي | الحالة | الفجوة المتبقية |
|---|---|---|---|---|
| `collections/get_collection` | ملاحظة حية + الكود الحالي | `spaces --fetch-meta` يبني فهرس مالك/عضو المساحة | **تم التنفيذ** | — |
| `collections/list_collection_threads` | ملاحظة حية + الكود الحالي | `space-index` يستخدم REST افتراضيًا مع تعيين معرف مزدوج context_uuid؛ WebBridge هو احتياطي | **تم التنفيذ** | ترتيب الفرز ودلالات `total_threads` الدقيقة لا تزال مقررة لاحقًا |
| `assets/<uuid>/data` | تم اختباره حيًا 2026-07-20 + الكود الحالي | `assets-backfill --online` يقوم بتحديث عناوين URL الموقعة لمعرفات الأصول الحقيقية | **تم التنفيذ** | مقابض مساحة العمل السحابية `toolu_` خارج تغطية نقطة النهاية هذه |
| `LibraryThreadsRelayQuery` واستعلام الترقيم | تم التقاط APQ + الكود الحالي | `index`/`batch` يوفران فهرسة كاملة وإيقاف مبكر تدريجي | **تم التنفيذ** | استعلامات تصفية وضع لوحة التحكم لا تزال محظورة بشكل منفصل |
| `collections/list_user_collections` | تمت ملاحظته حيًا يوليو 2026 + الكود الحالي | `init` يستخدم تطابق عنوان دقيق لاكتشاف مساحة BOT | **جزئي** | بناء سجل مساحة حساب موثوق لاكتشاف المساحة الجديدة وإعادة بناء `spaces` |
| `credits/thread-usage` | تم اختباره حيًا 2026-07-20 + الكود الحالي | `usage-backfill` يكتب `index/credit_usage_<account>.json` | **جزئي** | تحديد ما إذا كان سيتم إثراء `thread.json` و/أو صفوف فهرس المكتبة دون تكرار السلطة |
| `models/config/v2` | تم اختباره حيًا 2026-07-21 + الكود الحالي | `pplx-ask models` يسرد النماذج/الافتراضيات؛ يتم التحقق من ثوابت التطبيع مقابلها | **جزئي** | الاحتفاظ ببيانات عرض النموذج المستقرة في سجلات الأرشيف/الفهرس إذا كانت مفيدة |
| `POST /rest/thread/export` | تم اختبار md/pdf/docx حيًا 2026-07-20 | لا يوجد تكامل CLI | **تم الاختبار، غير مدمج** | الأرشفة متعددة التنسيقات والتوفيق بين Markdown الرسمي |
| `rate-limit/status` | ملاحظة تحميل الصفحة؛ دلالات الاستجابة غير مستكشفة | لا شيء | **مخطط له** | التحقق من صحة الدلالات قبل استخدامه للتحكم التكيفي في المعدل |
| `file-repository/list-files` | تحليل ثابت للواجهة الأمامية فقط | لا شيء | **مخطط له** | التحقق مما إذا كان يمكنه تعداد/إنقاذ مقابض `toolu_`؛ سجلت لقطة أرشيف يوليو 2026 270 مقبضًا بدون قناة تنزيل |
| `pins`، `tasks/{id}` | تحليل ثابت للواجهة الأمامية / ملاحظات تحميل الصفحة | لا شيء | **مخطط له** | إثراء حالة التثبيت ومدة مهمة الكمبيوتر |
| `thread/<uuid>/members` | تم اختباره حيًا يوليو 2026 | لا شيء | **مخطط له** | حواف المشاركة على مستوى السلسلة للرسم البياني للعلاقات |
| لوحة التحكم GraphQL `threadGroup` + مرشحات الوضع | الاستدعاءات المباشرة أعادت `PERSISTED_QUERY_NOT_FOUND` | لا شيء | **محظور** | استرداد تجزئات الاستعلام المستمرة الحية أو إنشاء السياق المطلوب |
| `related_queries` / `sse/related-queries` | تحقيقات الطب الشرعي على مستوى الأرشيف تم البت فيها 2026-07-23 | لا ينتج عن عمد حواف علاقة | **مغلق** | إعادة الفتح فقط إذا أنشأ دليل جديد هوية سلسلة قابلة للحل |

<a id="active-roadmap" data-pplx-source-anchor="true"></a>
### خريطة الطريق النشطة

<a id="p0-official-export-integration" data-pplx-source-anchor="true"></a>
#### P0 — تكامل التصدير الرسمي

- **الأرشفة متعددة التنسيقات**: الاحتفاظ اختياريًا بمنتجات PDF/DOCX التي يتم إرجاعها بواسطة
  `POST /rest/thread/export`.
- **التوفيق بين العارض**: مقارنة Markdown الرسمي للسلسلة الكاملة مع
  `conversation.md` كإشارة تراجع مستقلة.

<a id="p1-space-discovery" data-pplx-source-anchor="true"></a>
#### P1 — اكتشاف المساحة

- ترقية `list_user_collections` من بحث عنوان BOT إلى سجل مساحة موثوق على مستوى الحساب
  يُستخدم لاكتشاف المساحة الجديدة وإعادة بناء `spaces`.

<a id="p2-metadata-risk-control-and-asset-rescue" data-pplx-source-anchor="true"></a>
#### P2 — البيانات الوصفية، التحكم في المخاطر، وإنقاذ الأصول

- تحديد وتوثيق حدود السلطة لاستخدام الرصيد: الاحتفاظ بـ `credit_usage_<account>.json` المخصص،
  أو أيضًا إثراء `thread.json` / صفوف المكتبة.
- إضافة بيانات عرض النموذج، حالة التثبيت، مدة مهمة الكمبيوتر، وعلاقات مشاركة السلسلة
  فقط حيث تكون دلالات نقطة النهاية مستقرة.
- التحقق من صحة `rate-limit/status` قبل تصميم التحكم التكيفي في المعدل.
- اختبار `file-repository/list-files` كمسار إنقاذ محتمل لـ `toolu_` قبل
  إضافة أي تغيير في الأرشيف.

<a id="p3-blocked-discovery" data-pplx-source-anchor="true"></a>
#### P3 — الاكتشاف المحظور

- إعادة التقاط تجزئات الاستعلام المستمرة GraphQL للوحة التحكم فقط إذا أصبحت الفهرسة التدريجية حسب الوضع
  ذات قيمة كافية لتبرير تكلفة الصيانة.

<a id="closed-decisions-not-adopted" data-pplx-source-anchor="true"></a>
### القرارات المغلقة / غير المعتمدة

- **التصدير الرسمي كمصدر تقرير**: تم دحضه. تعيد نقطة النهاية Markdown السلسلة الكاملة
  بدون نص التقرير؛ تظل سلسلة URL الموقعة المصدر الرسمي لـ `report.md`
  ([§3.6](api-rest-endpoints.md)).
- **العلاقات من `related_queries`**: تم دحضها 2026-07-23. معرفات العناصر ليست
  معرفات سلسلة ونصوص التوصية لم يتم حلها إلى استعلامات مؤرشفة؛
  لا يتم بناء حواف علاقة ([§4](api-responses-errors.md)).
- `analytics/computer/usage(/members)`: تمت ملاحظته كمؤسسة فقط
  (`403 NOT_ORG_MEMBER`) للحسابات المختبرة.
- `thread/request-access-info`: تم اختباره كمرتبط بانضمام المؤسسة، وليس إشارة
  `threadAccess`.
- تظل الفروع الرأسية للفوترة/Stripe/المؤسسات والمالية/الرياضية خارج نطاق أداة الأرشيف.

---

*تكمل هذه الوثيقة [pplx_export/README.md](https://github.com/Yiksing/pplx-tools/blob/main/pplx_export/README.md) (هندسة الأداة) و [overview.md](../../architecture/overview.md) (تصميم النظام).*
