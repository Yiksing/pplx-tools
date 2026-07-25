---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-graphql.md"
translation_source_sha256: "3963e26d58d8dc1ad0835fe715357592295f31dd7c3b7c3f1ca67854fa3c98a0"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-reference-graphql" data-pplx-source-anchor="true"></a>
# مرجع API: GraphQL

<a id="graphql-persisted-queries-apq" data-pplx-source-anchor="true"></a>
## GraphQL (استعلامات محفوظة / APQ)

- **نقطة النهاية**: `POST https://www.perplexity.ai/rest/perplexity_ask/graphql`
- **الشكل**: استعلام محفوظ — يحمل الجسم operationName + المتغيرات + تجزئة sha256 (لا حاجة لنص الاستعلام).
- **التنفيذ**: `pplx_export/sites/perplexity/graphql.py`.

<a id="librarythreadsrelayquery-list-first-page" data-pplx-source-anchor="true"></a>
### LibraryThreadsRelayQuery (قائمة الصفحة الأولى)
- sha256: `a5229c390a6a00f81764187a21885cff655670029355c663fe393cc6e98f9ebe`
- المتغيرات: `{includeSearchPreview:false, searchTerm:null, sortOrder:"NEWEST", statuses:null, threadTypes:null, sources:null, includeTemporary:null}`
- مسار الاستجابة: `data.viewer.recentGroup.threads{edges[].node, pageInfo{hasNextPage,endCursor}}`
- حقول العقدة (المستخدمة من قبل المحول): `name(title)`، `entryId(entryUUID)`، `slug(href)`، `mode`، `displayModel.modelID`،
  `updatedAt(lastUpdated)`، `status`، `space{spaceUuid,title,slug}`
- **عقد جانب الأرشفة (2026-07-22 V5-01)**: `lastUpdated` من `web_archive/**/thread.json` يساوي دائمًا هذا الحقل
  (مكتوب على القرص بدقة ISO كاملة، حرفيًا)؛ مقارنة التطابق للتصدير الدفعي/الفردي (`is_unchanged`) تعتمد عليه،
  وليس على تنسيق العرض لطبقة التقديم (`YYYY-MM-DD HH:MM UTC`).
- **إثراء جانب الأرشفة (2026-07-23)**: مفتاح `search_mode` لصفوف الفهرس (`index/library_*.json`) هو
  حقل إثراء من جانب الأرشفة — لا تحتوي عقدة هذا الاستعلام على search_mode؛ يتم ملؤه بواسطة `pplx-export search-mode-backfill`
  من بيانات مستوى الموضوع (`entries[].search_mode` من `GET /rest/thread/<uuid>`) (البيانات الخام المحلية أولاً،
  الاحتياطي عبر الإنترنت)؛ تحديث `index` يدمجها ويحافظ عليها بواسطة entryUUID. تصفية `batch --mode` تفضل التعيين الموثوق لهذا الحقل.

<a id="libraryrecentthreadspaginationquery-pagination" data-pplx-source-anchor="true"></a>
### LibraryRecentThreadsPaginationQuery (الترقيم)
- sha256: `4f6dfcb8e9d3c065aca20ca1e82ca7fe464aaffc1faefade295bb7e333199629`
- المتغيرات: متغيرات الصفحة الأولى + `{cursor, count}` (**أسماء المتغيرات هي cursor/count، وليس after/first**)
- نفس بنية الاستجابة أعلاه. عندما يكون `hasNextPage` صحيحًا ولكن `endCursor` فارغًا، توقف (وإلا تتكرر نفس الصفحة).

<a id="computer-dashboard-operation-group-extracted-from-route-chunk-2026-07-20-not-registered-on-the-server" data-pplx-source-anchor="true"></a>
### مجموعة عمليات لوحة تحكم Computer (مستخرجة من جزء المسار 2026-07-20، **غير مسجلة على الخادم**)

يحتوي جزء `ComputerDashboardPage-*.js` على نصوص استعلام Relay كاملة + معرفات محفوظة (طريقة الاستخراج في [§7](api-discovery-roadmap.md)).
الأساسيات الهيكلية: `viewer.threadGroup(type: RECENT|ARCHIVED|PINNED|NEEDS_ATTENTION|SCHEDULED|SPACE, filter:{modes:[COMPUTER]})`
— أي قائمة مواضيع مصفاة بواسطة threadGroup + mode؛ تحتوي العقدة على `contextUUID/entryId/readWriteToken/isPinned/isArchived/isUnread`.

| العملية | المعرف المحفوظ (أول 16 حرفًا) |
|---|---|
| ComputerDashboardRecentThreadsPaginationQuery | `d713e695c82e7927…` |
| ComputerDashboardArchivedThreadsPaginationQuery | `1e9bcdb45cd611ca…` |
| ComputerDashboardPinnedThreadsPaginationQuery | `814c1d1748157d57…` |
| ComputerDashboardNeedsAttentionThreadsPaginationQuery | `2363d5af84392787…` |
| ComputerDashboardScheduledThreadsPaginationQuery | `51b18409b05f2e43…` |
| ComputerDashboardSpaceThreadsPaginationQuery | `da08f207c2d8bbcd…` |
| ComputerDashboardThreadGroupsUpdatesRelaySubscription | `bcce76383fb03d7e…` (اشتراك WebSocket) |

**تم اختباره**: استدعاء `/rest/perplexity_ask/graphql` بهذه المعرفات يعيد `PERSISTED_QUERY_NOT_FOUND`
(غير مسجل في النشر الحالي — اختلاف الإصدار أو سياق لوحة التحكم مطلوب؛ يتم الاحتفاظ بنصوص الاستعلام الكاملة والمعرفات في ملاحظات استكشاف `/tmp`؛
إذا لزم الأمر، أرسل نص الاستعلام مباشرة أو أعد استخراجه من الحزمة الحية).

<a id="notes" data-pplx-source-anchor="true"></a>
### ملاحظات
- لم يتم ملاحظة أي استدعاءات graphql على صفحة مساحة الويب أو الصفحة الرئيسية (كلها تمر عبر /rest)؛ تم تأكيد graphql لقائمة /library ولوحة تحكم Computer.
- قد تتغير تجزئات sha256 مع إصدارات الواجهة الأمامية؛ وضع الفشل هو `PERSISTED_QUERY_NOT_FOUND` — ثم أعد الاستخراج من
  التقاط الشبكة للمتصفح (أداة WebBridge `network` مع تصفية `perplexity_ask/graphql`)، أو أعد الاستخراج من الحزمة الحية ([§7](api-discovery-roadmap.md)).

<a id="extracted-dashboard-connection-keys-relay-cache-keys-for-debugging" data-pplx-source-anchor="true"></a>
### مفاتيح اتصال لوحة التحكم المستخرجة (مفاتيح ذاكرة التخزين المؤقت Relay، لتصحيح الأخطاء)
`ComputerDashboard(Recent|Archived|Pinned|NeedsAttention|Scheduled|Space)Threads_viewer_threads`
