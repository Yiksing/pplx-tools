---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-rest-endpoints.md"
translation_source_sha256: "f1eb76feaffc48d910b988b54e4bcfcaa8b52a65502495399536392e4da7d146"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-reference-rest-endpoints" data-pplx-source-anchor="true"></a>
# مرجع API: نقاط النهاية REST

<a id="rest-endpoints-grouped-by-purpose" data-pplx-source-anchor="true"></a>
## نقاط النهاية REST (مجمعة حسب الغرض)

اتفاقية: `?version=2.18&source=default` هي سلسلة الاستعلام الشائعة (مطلوبة بواسطة معظم نقاط النهاية).

<a id="thread-content-main-export-path" data-pplx-source-anchor="true"></a>
### محتوى المحادثة (مسار التصدير الرئيسي)
| نقطة النهاية | ملاحظات |
|---|---|
| `GET /rest/thread/<uuid>` | **استجابة عادية**: `entries[]` (لكل دورة؛ `text` يحتوي على جميع نصوص الخطوات)، `background_entries[]` (**سير عمل الوكيل الفرعي الكامل**)، `thread_metadata`. يدعم ترقيم الصفحات `?cursor=` (`has_next_page`/`next_cursor`) |
| `GET /rest/thread/<uuid>?with_schematized_response=true&with_parent_info=true&limit=100&offset=0&from_first=false&<SCHEMATIZED_USE_CASES>` | **استجابة منظمة**: `entries[].blocks[]` (`workflow_block`/`unified_assets_block`/`plan_block`/`markdown`)، بما في ذلك مطالبات الوكيل الفرعي (`workflow_payload.objective_chunks`)، وعناوين URL الموقعة للأصول، ومحتويات الملفات. حالات الاستخدام في `rest.py:SCHEMATIZED_USE_CASES` (workflow_steps/unified_assets/asset_diff_assets/write_delta/bash_delta/run_subagent_delta/background_agents/markdown) |
| `GET /rest/thread/list_recent` | قائمة المحادثات الحديثة (الشريط الجانبي الرئيسي؛ يتضمن حقل `unread`) |
| **`POST /rest/thread/mark_viewed`** | **إيصال القراءة (تم اكتشافه في 2026-07-21)**: النص `{"context_uuids": ["<thread context_uuid>"]}` → `{"status":"success"}`؛ يتم تغيير حالة غير المقروء على الفور. تستدعي الواجهة الأمامية نقطة النهاية هذه عند فتح محادثة من الشريط الجانبي. ملاحظة: حدث التحليلات "تم عرض المحادثة" **لا يغير** حالة غير المقروء (تم استبعاده من خلال اختبارات متكررة) |
| `GET /rest/thread/<uuid>/members` | **أعضاء المشاركة على مستوى المحادثة** (تم اختباره): `{"owner": {username,email,name,image}, "members": [...]}` |
| `GET /rest/thread/request-access-info/<uuid>` | يُرجع `{"will_request_org_join": bool, "org_display_name": str|null}` — متعلق بانضمام المؤسسة، **غير مرتبط بدلالات الوصول إلى المحادثة** (تم استبعاده عن طريق الاختبار) |
| `GET /rest/thread/list_ask_threads`, `/rest/thread/list_scheduled_computer_tasks` | موجود في التحليل الثابت؛ اختبار GET المباشر أعاد 400 (شكل المعلمة غير محدد) |

<a id="asset-metadata-discovered-2026-07-20-lifesaver-for-expired-assets" data-pplx-source-anchor="true"></a>
### بيانات الأصول الوصفية (تم اكتشافها في 2026-07-20، **منقذ للحياة للأصول منتهية الصلاحية**)

- **`GET /rest/assets/<asset_uuid>/data`** → بيانات وصفية كاملة للأصل (تم اختباره وأعاد 200):
  - `asset_data.<type>.url` و `asset_data.download_info[].url`: **عناوين URL موقعة حديثة من CloudFront** —
    إذا كان عنوان URL الموقع الأصلي قد انتهت صلاحيته في وقت الأرشفة، يمكن إعادة جلب عنوان التنزيل باستخدام asset_uuid
    (بشرط ألا تكون المنصة قد حذفت الأصل)؛
  - يُرجع أيضًا `entry_uuid`/`context_uuid`/`source_thread_path`/`thread_access`/`is_owner`/`has_owning_space`
    (سلسلة البحث العكسي من الأصل إلى المحادثة)؛
  - حقول مثل `signed_url: null`, `read_write_token`, `allow_remix`.
- **حدود قابلية التطبيق (تم اختبارها)**: معرفات uuid الحقيقية للأصول تعمل؛ **معالجات مساحة العمل السحابية المسبوقة بـ `toolu_` (DOC_FILE/CODE_FILE
  بدون نموذج URL) تُرجع 404 ASSET_NOT_FOUND**؛ `file-repository/download` يتطلب عنوان URL حقيقي ولا يقبل
  معالجات `file:repo/...` (400 فشل في التحليل). لا توجد قناة تنزيل API لأصول نوع toolu بعد.
- ذات صلة: `/rest/assets/<id>/members`, `/rest/assets/<id>/published-access` (موجود في التحليل الثابت، غير مُختبر).
- تم التنفيذ: توفر الأداة `pplx-export assets-backfill` (استخراج مضمن + تحديث عبر الإنترنت عبر نقطة النهاية هذه؛ راجع ملاحظة الأدوات المنفذة في [§4](api-responses-errors.md)).

- **ENTRY_EXPIRED**: المحادثات/القطع الأثرية الأقدم من ~3 أشهر يتم حذفها بواسطة المنصة؛ تُرجع الطلبات نص خطأ محدد — الأداة تضع علامة عليها كنهائية ولا تعيد المحاولة.
- **حذف المحادثة (2026-07-23 WebBridge + بحث القطعة، تم اختباره)**:
  `DELETE /rest/thread/delete_thread_by_entry_uuid`, النص `{entry_uuid, read_write_token}`,
  النجاح `200 {"status":"success"}`; الحذف المتكرر هو عملية غير مؤثرة، لا يزال يُرجع 200; حذف uuid غير موجود → 404 `THREAD_NOT_FOUND`;
  **الحصول على `read_write_token` (تم التحقق منه عمليًا في نفس اليوم)**: أول `entries[].read_write_token` غير فارغ
  في استجابة `GET /rest/thread/<uuid>` يعمل (10/10 عمليات حذف نجحت على محادثات حية)؛
  **يجب أن تذهب عمليات الكتابة إلى نطاق www** (نطاق apex يُرجع 301 لـ DELETE). لا يوجد استعلام GraphQL، ولا نقطة نهاية للحذف الجماعي
  (الحذف الجماعي في واجهة المستخدم هو حلقة لكل عنصر في الواجهة الأمامية). الحذف هو تدمير على مستوى المحادثة، غير قابل للاسترداد؛ تختفي المحادثة تلقائيًا من مساحاتها
  (لا حاجة إلى `batch_remove_collection_threads` أولاً).
  خيار ناعم: `POST /rest/thread/batch_archive_threads` / `batch_unarchive_threads`
  (النص `{context_uuids:[...]}`; تحليل ثابت فقط، غير مُختبر).
- **ENTRY_DELETED**: بعد حذف محادثة، يُرجع `GET /rest/thread/<uuid>` HTTP 400 `ENTRY_DELETED`
  (نفس 400 مثل ENTRY_EXPIRED ولكن برمز مختلف) — الأداة تُسقطه إلى `EntryDeletedError`
  (فئة فرعية من `EntryExpiredError`); batch_state يحدد الحالة النهائية `deleted`.
- يحمل كل إدخال دورة `context_uuid` (= معرف uuid للمنصة `past_session_contexts` — المفتاح لتعيين مساحة الاسم ثنائية المعرف).

<a id="spaces-collections" data-pplx-source-anchor="true"></a>
### المساحات (المجموعات)
| نقطة النهاية | ملاحظات |
|---|---|
| `GET /rest/collections/get_collection?collection_slug=<slug>` | **بيانات المساحة الوصفية**: `uuid/title/emoji/access/max_contributors`, `owner_user{username,email,name,permission}`, `contributor_users[]`, `user_permission`. قيم الأذونات الملاحظة: 4=مالك، 2=يمكن التحرير. عندما لا يكون للحساب الحالي حق الوصول للعرض: `status:"failed"` + `_response_type:"VIEW_COLLECTION_NOT_ALLOWED"` (HTTP لا يزال 200) |
| `POST /rest/collections/create_collection` | **إنشاء مساحة** (2026-07-21 التقاط WebBridge، تم اختباره): النص `{"title","description","emoji":"1f4c1","appearance":null,"instructions":"","access":1}` → يُرجع المجموعة الكاملة (uuid/الرابط المختصر/url/صلاحية المستخدم=4). تم إنشاء مساحة BOT بهذه الطريقة |
| `GET /rest/collections/list_collection_threads?collection_slug=<slug>` | **قائمة محادثات المساحة (طلب ملفات تعريف الارتباط المباشر؛ يمكن أن يحل محل فهرس المساحة المستند إلى المتصفح)**: الاستجابة عبارة عن مصفوفة؛ كل عنصر يحتوي على `uuid`(=entryUUID), `context_uuid`, `frontend_uuid`, `author_username`, `title`, `mode`, `last_query_datetime`, `thread_access`, `answer_preview`، إلخ. **الترقيم: `&offset=N` (20 لكل صفحة)**; `has_next_page` موجود على كل عنصر; `total_threads` يقرأ عاليًا (يشمل المحادثات الفرعية للحاسوب؛ لوحظ 99 مقابل 27 على المستوى الأعلى) |
| `POST /rest/collections/batch_move_threads` | **نقل المحادثات إلى مساحة** (تم اختباره بنجاح): النص `{"context_uuids": [...], "new_collection_uuid": "<uuid>"}` — **استخدم context_uuid، وليس entryUUID** |
| `POST /rest/collections/batch_remove_collection_threads` | إزالة مجمعة من مساحة (النص `{items:[{collection_uuid,...}]}`; غير مُختبر) |
| `GET /rest/collections/list_user_collections` | **قائمة مساحات الحساب الحالي** (تم اختباره، 16 عنصرًا): كل منها يحتوي على `uuid/title/emoji/access/contributor_users/is_invited/is_pinned/can_share_threads/file_count/has_next_page`، إلخ. — أغنى من list_recent |
| `GET /rest/collections/list_recent` | المساحات الحديثة للحساب الحالي (`title/uuid/emoji/is_pinned/link`; تم اختباره، 5 عناصر) |
| `GET /rest/collections/{uuid_or_slug}/request-access-info` | معلومات طلب الوصول إلى المساحة (غير مُختبر) |
| `GET /rest/collections/<uuid>/join-requests` | طلبات الانضمام (لم يتم استكشافها) |
| `GET /rest/spaces/<uuid>/tasks` | يُرجع `{"tasks":[]}` — لوحظ فارغًا؛ يُشتبه في أنها مهام مجدولة/حاسوبية للمساحة، وليست قائمة محادثات |
| `GET /rest/spaces/<uuid>/recurring_tasks` | المهام المتكررة (غير مُختبر) |
| `GET /rest/spaces/<uuid>/pins/threads`, `/scheduled_threads` | المحادثات المثبتة/المجدولة في المساحة (تُستدعى عند تحميل الصفحة؛ لم يتم استكشافها) |

- **التفرع عبر الحسابات (branch_of; معرفة مؤكدة من المستخدم 2026-07-23)**: يمكن "متابعة" محادثة تمت مشاركتها عبر مساحة بواسطة حساب عضو آخر في محادثة فرعية **تكون مرئية فقط لذلك الحساب ويواصلها** — بعد مشاركة محادثة الحساب A عبر مساحة،
  يمكن لـ B متابعتها في فرع خاص بـ B. لا يحتوي الأرشيف على مثيل بعد؛ لم يتم تنفيذ حواف العلاقات بعد؛ سيتم التحقق من حقول إشارة API للمحادثة الفرعية
  (المؤشر الأصلي / علامة الفرع) وتسجيلها عند ظهور المثيل الأول.

<a id="account-session" data-pplx-source-anchor="true"></a>
### الحساب / الجلسة
| نقطة النهاية | ملاحظات |
|---|---|
| `GET /api/auth/session` | الجلسة الحالية `{user:{email,...}}` — تُستخدم للتحقق من الحساب واختبار التبديل التلقائي |
| `GET /api/auth/linked-accounts` | انظر [§1.2](api-authentication.md) (القائمة الكاملة فقط عندما يكون الحساب الأساسي نشطًا) |
| `GET /rest/user/info`, `/rest/user/settings` | ملف تعريف المستخدم / الإعدادات (لم يتم استكشافها) |

<a id="credit-usage-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### استخدام الرصيد (تم اكتشافه في 2026-07-20)

- **`GET /rest/billing/credits/thread-usage?thread_id=<context_uuid>`** → استخدام الرصيد لكل محادثة (تم اختباره وأعاد 200):
  `{"usage_cents": 27926.36, "meter_usage": [{"meter_type": "asi_token_usage", "cost_cents": ...}]}`
- **ملاحظة**: يتوقع `thread_id` **context_uuid** (psc_uuid); تمرير entryUUID يُرجع 403
  `thread_usage_forbidden` ("المحادثة لا تنتمي إلى المستخدم الحالي" — في الواقع هو شكل معرف خاطئ).
- مصادر context_uuid: `list_collection_threads` (فهرس المساحة REST يغطي بالفعل 27/27)،
  حقل `context_uuid` لإدخال المحادثة (مؤرشف كـ `psc_uuid` في thread.json).
- يمكن الاستعلام فقط عن محادثات الحساب الحالي (عبر الحسابات → 403) — يتطلب كشط الحسابات المتعددة التبديل التلقائي لكل حساب.
- `GET /rest/billing/credits/thread-usages?offset&limit&sessionKind`: إصدار القائمة؛ تم اختباره فارغًا على كلا الحسابين
  (يُشتبه في أنه خاص بفوترة المؤسسة فقط؛ لم يُحدد بعد).
- نقاط نهاية الفوترة الأخرى (`/rest/billing/credits/balance`، إلخ.) في [الملحق §7](api-discovery-roadmap.md); لم يتم استكشافها.

<a id="official-export-backend-of-the-page-export-button-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### التصدير الرسمي (الواجهة الخلفية لزر "تصدير" في الصفحة؛ تم اكتشافه في 2026-07-20)

- **`POST /rest/thread/export`**, النص: `{"thread_uuid": "<uuid>", "format": "<fmt>", "filename": "<name>"}`
- الاستجابة: `{"file_content_64": "<base64>", "filename": "..."}`
- التنسيقات المختبرة: **`md`** (ماركداون رسمي مع رأس شعار `<img>`)، **`pdf`** (ثنائي PDF ~880 كيلوبايت)،
  **`docx`** (PK zip ~350 كيلوبايت) — جميعها HTTP 200. قيم التنسيق الأخرى غير مُختبرة.
- **حدود المحتوى (تم التحقق منها)**: يُرجع ماركداون **المحادثة بأكملها** (ملخص الاستعلام + الإجابة + استشهادات الحواشي السفلية `[^1_N]`)،
  **بدون نص RESEARCH_REPORT** — لا يمكن الحصول على تقرير البحث العميق نفسه إلا عبر عنوان URL الموقع الخاص به (§3.7)؛
  أي أن سلسلة عنوان URL الموقع report.md الحالية **هي مصدر التقرير الرسمي** (نفس مصدر تنزيل لوحة القطع الأثرية في الصفحة)؛ لا حاجة للتبديل إلى نقطة النهاية هذه.
- القيمة: يمكن أن يعمل الماركداون الرسمي على مستوى المحادثة كمصدر للتحقق المتبادل على مستوى المحادثة (الحواشي السفلية للاستشهادات/التنسيق المقدمة رسميًا).

<a id="asset-report-download" data-pplx-source-anchor="true"></a>
### تنزيل الأصول / التقارير
- **عناوين URL الموقعة من CloudFront** في الاستجابة المنظمة (`d2z0o16i8xm8ak.cloudfront.net`): تنزيل مباشر عبر urllib،
  لا حاجة لملفات تعريف الارتباط/المصادقة؛ الملفات متعددة الإصدارات مرقمة بترتيب `created_at`.
- مصدر احتياطي لتقرير البحث: عنوان URL S3 لخطوة RESEARCH_ANSWER (`ppl-ai-file-upload.s3.amazonaws.com`، **تنتهي صلاحيته**)؛
  المصدر الاحتياطي الثاني: استخراج عرض الصفحة (KaTeX `<annotation>`).
- **حذف بعد ~3 أشهر**: تنتهي صلاحية روابط مصدر القطع الأثرية/التقارير بشكل غير قابل للاسترداد — يجب أن تكون الصادرات في الوقت المناسب.

<a id="other-observed-endpoints-page-load-not-explored" data-pplx-source-anchor="true"></a>
### نقاط نهاية أخرى ملاحظة (تحميل الصفحة؛ لم يتم استكشافها)
`/rest/models/config(/v2)`, `/rest/sources`, `/rest/rate-limit/status`, `/rest/assets/pins`,
`/rest/file-repository/list-files`, `/rest/files/list`, `/rest/notifications/in-app/unread-count`,
`/rest/billing/*`, `/rest/sse/recent_thread_updates` (SSE), `/api/version`.

<a id="message-submission-and-telemetry-2026-07-20-webbridge-cdp" data-pplx-source-anchor="true"></a>
### إرسال الرسائل والقياس عن بعد (2026-07-20 WebBridge + CDP)

<a id="submission-endpoint-post-restsseperplexity_ask" data-pplx-source-anchor="true"></a>
#### نقطة نهاية الإرسال: `POST /rest/sse/perplexity_ask`
- نماذج نص الطلب الكامل (أمثلة اصطناعية) تحت `docs/perplexity-api-samples/`:
  - `ask_envelope_deep_research.json` — دورة متابعة للبحث العميق (2026-07-20; 39 معلمة + query_str):
    `model_preference: "pplx_alpha"`, `query_source: "followup"` + سلسلة الاستمرار `last_backend_uuid`
  - `ask_envelope_search.json` — بحث قياسي، محادثة جديدة من الصفحة الرئيسية (2026-07-21; 35 معلمة + query_str):
    `model_preference: "pplx_pro"`, `query_source: "home"` + `frontend_context_uuid`
  - `ask_envelope_model_council.json` — مجلس النماذج، محادثة جديدة من الصفحة الرئيسية (2026-07-21; 36 معلمة + query_str):
    `model_preference: "pplx_agentic_research"` + `compare_model_preferences: ["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`
- الحقول الرئيسية (دورة متابعة للبحث العميق، تم اختبارها):
  - `mode: "copilot"` (بحث عميق); `model_preference: "pplx_alpha"`
  - **سلسلة الاستمرار**: `last_backend_uuid` (معرف uuid الخلفي للدورة السابقة) + `query_source: "followup"`
  - `frontend_uuid` (معرف uuid جديد لهذه الدورة), `read_write_token`, `target_collection_uuid` (المساحة الحاوية),
    `target_thread_access_level: 1`
  - `search_focus: internet`, `sources: ["web"]`, `language: zh-CN`, `timezone: Asia/Shanghai`
  - **`time_from_first_type: 87664`** (مللي ثانية من أول ضغطة مفتاح إلى الإرسال — بيانات سلوكية مرفوعة مع الإرسال)
  - `use_schematized_api: true`, `supported_block_use_cases` (قائمة الحظر الكاملة، مطابقة لـ §3.1 المنظمة),
    `supported_features: ["browser_agent_permission_banner_v1.1"]`, `skip_search_enabled: true`
- الاستجابة عبارة عن دفق SSE (تستهلكه الواجهة الأمامية باستخدام fetch-event-source `getReader()` — وحدة التطبيق تجمد مرجع الجلب عند التهيئة،
  **خطافات fetch/XHR المرفقة بالصفحة غير فعالة**; و **أجسام استجابة الدفق لا يتم الاحتفاظ بها بواسطة المتصفح** (`Network.getResponseBody` يُرجع
  No data found) — الالتقاط ممكن فقط عبر CDP `Network.getRequestPostData` (نص الطلب متاح)).
- الحالة النهائية للدفق هي بالضبط إدخالات/كتل `/rest/thread/<uuid>` (نفس البيانات، يتم تسليمها بشكل تدريجي) —
  لا تحتاج أداة التصدير إلى قراءة الدفق؛ فهي تسحب الحالة النهائية مباشرة.

<a id="telemetry-post-resteventanalytics-batched-high-frequency" data-pplx-source-anchor="true"></a>
#### القياس عن بعد: `POST /rest/event/analytics` (مجمّع، عالي التردد)
الأحداث الملاحظة (مع أساسيات event_data):
| event_name | الحقول الرئيسية | ملاحظات |
|---|---|---|
| `thread viewed` | `authorId`, `authorUsername`, `isThreadCreator`, `contextUUID` | حدث عرض الصفحة — **لا يغير حالة غير المقروء** (تم استبعاده عن طريق الاختبار؛ إيصال القراءة الحقيقي هو `POST /rest/thread/mark_viewed`، انظر §3.1) |
| `thread entry exited` | `entryUUID`, `timeOnEntryMs` (**مدة القراءة بالمللي ثانية لتلك الدورة**), `userId`, `isPro`, `deviceInfo` (التزامن/الشاشة/عمق الألوان) | قياس عن بعد لمدة القراءة (لا يغير حالة غير المقروء، تم استبعاده عن طريق الاختبار) |
| `ask input submit button clicked` | `querySource: followup`, `searchMode: research`, `isFollowUp` | إجراء الإرسال |
| `query first llm token` | `startLLMTokenElapsed` (زمن الوصول للرمز الأول), كامل `queryStr` | قياس عن بعد للأداء |
| `SUCCESSFUL response` | `submissionType: perplexity_ask`, كامل `queryStr` | إيصال النجاح |
| `ask input model selector opened` | `searchMode: "agentic_research"`, `multiple: true`, `selectedModels` | تفاعل محدد نموذج المجلس |
| `ask context pane viewed` | `pane_mode`, `context_uuid` | عرض اللوحة اليمنى |
- حقول الحدث الشائعة: `userId`, `visitor_id`, `timezone`, `language`, `screen`, `device_info` (hardwareConcurrency/الشاشة/عمق الألوان/الهندسة المعمارية), `isBrowserExtension`, `web_platform`.
- **ملاحظة**: حمل أحد الأحداث الملاحظة `userId` ينتمي إلى **الحساب الآخر** (كان uid ينتمي إلى الحساب A بينما كانت الجلسة بالفعل للحساب B) —
  معرف ملف تعريف SDK للقياس عن بعد به تأخير في التخزين المؤقت؛ لا تحكم على الحساب الحالي من خلال userId الخاص بالقياس عن بعد.
- يوجد أيضًا تقارير Datadog RUM (`browser-intake-datadoghq.com/api/v2/rum`) عالية التردد (التمرير/الماوس/الأداء; لم يتم تحليل المحتوى).

<a id="mode-and-model-selection-2026-07-21-tested-on-a-paid-account" data-pplx-source-anchor="true"></a>
#### اختيار الوضع والنموذج (2026-07-21، تم اختباره على حساب مدفوع)
- **`GET /rest/models/config/v2` = جدول النماذج الموثوق**: `models{id→{label,mode,provider}}`,
  `default_models{search:pplx_pro, research:pplx_alpha, agentic_research:pplx_agentic_research,
  study:pplx_study, asi:pplx_asi}`, `agentic_research_compare_models` (افتراضي لمجلس النماذج ثلاثة نماذج).
  `pplx-ask models` يستدعي نقطة النهاية هذه.
  - المراسلات الرسمية (تم اختبارها): **search = `pplx_pro` (اسم واجهة المستخدم "الأفضل"), research = `pplx_alpha`
    (اسم واجهة المستخدم "البحث العميق")**.
  - قائمة النماذج القابلة للتحديد في واجهة المستخدم لوضع البحث (بدون بحث عميق): الأفضل (pplx_pro), Sonar 2,
    GPT-5.6 Terra, GPT-5.6 Sol, Gemini 3.1 Pro, Claude Sonnet 5, Claude Opus 4.8,
    GLM 5.2, Kimi K2.6, Grok 4.5, Nemotron 3 Ultra.
- **حقل `mode` دائمًا `"copilot"` — ليس أداة تمييز للوضع** (نفس الشيء للبحث / البحث العميق / مجلس النماذج).
- التمييز موجود في **`model_preference`**:
  - البحث: `pplx_pro` (أو معرف النموذج الذي اختاره المستخدم، على سبيل المثال `experimental`=Sonar 2, `gpt56_sol`…)
  - البحث العميق: `pplx_alpha` (**لا يوجد محدد نموذج في واجهة المستخدم**, ثابت)
  - **مجلس النماذج**: `pplx_agentic_research` + **`compare_model_preferences: [<2-3 models>]`**
    (الافتراضي الملاحظ `["gpt55_thinking", "claude48opusthinking", "gemini31pro_high"]`;
    واجهة المستخدم هي **اختيار فردي لكل فتحة**, يتم تقليصه إلى نموذجين عند المتابعة).
  - الدراسة خطوة بخطوة: `pplx_study`; الحاسوب: عائلة `pplx_asi*`.
- محدد النموذج في منطقة التأليف ("model ⌄") ومحدد "N models ⌄" في المجلس يتوافقان مع الحقول أعلاه;
  حدث القياس عن بعد `ask input model selector opened` يحمل `searchMode: "agentic_research"`,
  `multiple: true`, `selectedModels` (محادثات البحث العميق السابقة كان لديها `searchMode: "research"`).
- محادثة جديدة: `query_source: "home"`, لا يوجد `last_backend_uuid`, لديه `frontend_context_uuid`;
  متابعة: `query_source: "followup"` + سلسلة `last_backend_uuid`.

<a id="entrysearch_mode-the-authoritative-record-of-conversation-mode-settled-2026-07-22" data-pplx-source-anchor="true"></a>
#### entry.search_mode: السجل الموثوق لوضع المحادثة (تم تسويته في 2026-07-22)
**كل إدخال** من `/rest/thread/<uuid>` يحمل `search_mode`، سجل المنصة الموثوق لوضع المحادثة لتلك الدورة
(إشارة اكتشاف الوضع ذات الأولوية القصوى, `normalize.SEARCH_MODE_MAP`):

| search_mode | المعنى (واجهة المستخدم/النموذج) | وضع الأرشيف |
|---|---|---|
| `SEARCH` | بحث عادي (default_models.search=pplx_pro "الأفضل" ونماذج قابلة للتحديد في واجهة المستخدم) | search |
| `STUDIO` | جلسة مختبر (pplx_beta); تجمعه واجهة المستخدم تحت البحث | search |
| `RESEARCH` | بحث عميق (default_models.research=pplx_alpha; واجهة المستخدم ثابتة، لا يوجد محدد) | deep-research |
| `AGENTIC_RESEARCH` | مجلس النماذج (pplx_agentic_research + compare_model_preferences) | council |
| `STUDY` | دراسة خطوة بخطوة (pplx_study) | study |
| `ASI` | الحاسوب (pplx_asi*) | computer |

- مسح القيمة على مستوى الأرشيف: جميع القيم الست لها مثيلات في الأرشيف الحقيقي؛ SEARCH و RESEARCH هي السائدة،
  STUDIO تليها، ASI / STUDY / AGENTIC_RESEARCH نادرة.
- **pplx_alpha ⟺ إثبات متقاطع لـ RESEARCH**: 100+ إدخال SEARCH من المنصة + محادثات pplx_alpha في الأرشيف هي 100%
  `search_mode=RESEARCH`; 100+ محادثة pplx_pro نقية كلها `search_mode=SEARCH` —
  الإحصاء القديم "pplx_alpha هو نموذج شائع الاستخدام للبحث العادي" كان في الواقع عينات سوء تقدير من المصنف ولا يصح.
- يمكن أن تظهر قيم متعددة داخل محادثة واحدة (تبديل الوضع، على سبيل المثال مزيج SEARCH+RESEARCH ملاحظ): يأخذ الكشف الأعلى حسب الخصوصية
  computer>council>study>deep-research>search.

<a id="model-council-output-structure-and-expansion-behavior" data-pplx-source-anchor="true"></a>
#### هيكل مخرجات مجلس النماذج وسلوك التوسيع
- مخرجات الدورة الواحدة = N كتل خاصة بالنموذج "Council: <model name>" (كل منها يحتوي على استعلامات استرجاع/مصادر/إجابة) + جزء تجميعي:
  **Where Models Agree** (مصفوفة إجماع، لكل نتيجة مقارنة ثلاثة نماذج ✓ + أدلة)،
  **Where Models Disagree** (جدول الخلاف، موقف كل نموذج + أسباب الاختلاف)،
  **Unique Discoveries** (النتائج الفريدة لكل نموذج)، متبوعة بتوصيات الأسئلة ذات الصلة — **يتم تسليمها جميعًا في نفس دفق SSE**.
- سلوك التوسيع (بما في ذلك التوسيع **أثناء التوليد**): الصفوف القابلة للتوسيع تحمل علامة ">" (صفوف الخطوات / صفوف "المصادر" / صفوف المجلس);
  النقر عليها يوسعها — **عرض من جانب العميل فقط، بدون طلبات محتوى**: من بين 1208 طلبًا لهذه الجلسة، كان 921 عبارة عن أصول ثابتة للأيقونة/الخط؛
  التوسيع نفسه يؤدي فقط إلى تحميل الأيقونات و /api/version. التوسيع أثناء البث لا يزعج التسليم المستمر.
- زمن الوصول للرمز الأول الملاحظ ~204 ثانية (ثلاثة نماذج تولد بالتوازي، أطول بشكل ملحوظ من نموذج واحد); عدد المصادر الملاحظ 236.
- أساسيات أتمتة منطقة التأليف (Lexical): يجب حقن النص عبر CDP `Input.insertText` (بعد execCommand/fill،
  تتعطل الحالة الداخلية لـ Lexical ويفشل Enter); يمكن للإرسال استخدام CDP Enter أو النقر على الزر مع aria-label="提交" ("إرسال")
  (وضع المجلس لديه سهم إرسال صريح).

<a id="behavior-when-continuing-a-historical-conversation-tested-2026-07-20" data-pplx-source-anchor="true"></a>
#### السلوك عند متابعة محادثة تاريخية (تم اختباره في 2026-07-20)
1. تحميل صفحة المحادثة → `session`, `assets/pins`, `billing/credits/computer-submit-gate`, `cdn-cgi/trace`.
2. إرسال متابعة → `rate-limit/status` → `sse/perplexity_ask` (مع سلسلة `last_backend_uuid`) → تحليلات عالية التردد.
3. أثناء التوليد → دفق SSE يُعرض بشكل تدريجي؛ بعد الاكتمال، دفعة أخرى من التحليلات (بما في ذلك مدة القراءة `thread entry exited`).
4. دورات متابعة البحث العميق تنتج أيضًا هياكل تقارير (أكملت هذه الدورة 5 خطوات).
