---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/archive-layout.md"
translation_source_sha256: "6302a47c60b6c8703d36f420cee6c18017110fcbb6127926eedb5c77e3e1f8e2"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="archive-layout" data-pplx-source-anchor="true"></a>
# تخطيط الأرشيف

كل ما ينزله `pplx-export` يهبط في شجرة إخراج واحدة — `./web_archive/` افتراضيًا
(يمكن التجاوز باستخدام `--out`). هذه الصفحة هي دليل قراءة لتلك الشجرة: ما هو كل دليل وملف،
والمفاتيح التي يحملها `thread.json`، وكيف تحافظ الأداة على دليل واحد لكل محادثة عندما
تستمر المحادثة عبر أيام. كل ذلك من إنشاء الأداة؛ عمق الآلية موجود في
[نموذج البيانات وعقد الدليل](../architecture/data-model.md) و
[خط أنابيب التصدير](../architecture/export-pipeline.md).

<a id="the-output-tree" data-pplx-source-anchor="true"></a>
## شجرة الإخراج

```
web_archive/
├── alice/                                # one folder per account (author display name)
│   ├── search/                           # mode: search | deep-research | computer | council | study
│   │   └── 2026-07-18_quantum-computing-survey_1a2b3c4d/   # one directory per thread
│   │       ├── thread.json               # metadata + optional registries
│   │       ├── conversation.md           # compact read: per-turn Query/Answer
│   │       ├── turns/
│   │       │   ├── turn_0001.md          # full read: complete work-process detail
│   │       │   └── ...
│   │       ├── sources.json              # thread-wide citations (deduped by url)
│   │       ├── sources.md
│   │       ├── report.md                 # deep-research report (only when one exists)
│   │       ├── raw_entries.json          # plain API response, verbatim (always present)
│   │       ├── raw_blocks.json           # schematized API response (absent for search)
│   │       └── assets/
│   │           ├── assets_manifest.json  # versioned manifest
│   │           └── files/                # downloaded asset bodies
│   ├── deep-research/ ...
│   └── computer/ ...
├── index/                                # state files and indexes (see below)
├── relations/                            # edges.jsonl + graph.md (rebuilt by `pplx-export relations`)
├── crosscheck/                           # cross-validation reports (manual/review artifacts)
└── bob/ ...
```

<a id="the-thread-directory" data-pplx-source-anchor="true"></a>
## دليل المحادثة

تحصل كل محادثة على دليل واحد بالضبط، يُحسب بواسطة `thread_dir_for` (`fs_writer.py:58-72`):

```
<account display name>/<mode>/<YYYY-MM-DD>_<title-slug>_<uuid8>/
```

| المكون | المصدر | ملاحظات |
|---|---|---|
| `<account display name>` | مؤلف المحادثة، عبر `author_folder` → `_safe_folder` (`fs_writer.py:40-51`) | فواصل المسارات والأحرف غير القانونية في ويندوز (`:*?"<>\|`) تصبح `_`؛ `.`/`..` مرفوضة (حماية من اجتياز المسار للمساحات المشتركة)؛ كل شيء آخر — بما في ذلك المسافات — يُحتفظ به |
| `<mode>` | `detect_mode` | أحد الأوضاع الخمسة؛ راجع [أوضاع المحادثة](modes.md) |
| `<YYYY-MM-DD>` | `thread.json` `lastUpdated` بادئة التاريخ | تاريخ آخر تحديث للمنصة، **ليس** تاريخ التصدير — يتحرك عند تحديث محادثة مستمرة (انظر الترحيل أدناه) |
| `<title-slug>` | `slugify(title)` (`normalize.py:261-263`) | 40 حرفًا كحد أقصى، الأحرف غير الكلامية → `-`، الفارغ → `untitled` |
| `<uuid8>` | `web_uuid[:8]` | أول 8 أحرف من UUID المحادثة — مرساة هوية الدليل |

<a id="files-in-a-thread-directory" data-pplx-source-anchor="true"></a>
## الملفات في دليل المحادثة

<a id="threadjson-metadata-and-registries" data-pplx-source-anchor="true"></a>
### thread.json — البيانات الوصفية والسجلات

مكتوب بواسطة `write_thread` (`fs_writer.py:224-253`). المفاتيح الموجودة دائمًا:

| المفتاح | المحتوى |
|---|---|
| `web_uuid` | entryUUID على الويب — UUID في رابط المحادثة؛ هوية المحادثة |
| `psc_uuid` | `context_uuid` المنصة (قابل للإلغاء؛ من أول دورة غير فارغة) — المعرف المزدوج المستخدم بواسطة فهارس المساحة |
| `url` | رابط المحادثة الأساسي |
| `title` | عنوان المحادثة |
| `mode` | الوضع المكتشف (`search` / `deep-research` / `computer` / `council` / `study`) |
| `author` | اسم عرض حساب المؤلف |
| `export_via` | اسم مستخدم الحساب الذي أجرى التصدير — مهم للمحادثات في المساحات المشتركة التي تم تصديرها عبر حساب آخر |
| `space` | `{"uuid", "title", "slug"}` أو `null` |
| `lastUpdated` | طابع زمني لآخر تحديث للمنصة (عقد مقارنة آلي للمزامنة المتزايدة) |
| `threadAccess` | علامة الوصول للمنصة |
| `n_turns` | عدد الدورات |
| `n_sources` | عدد الاستشهادات على مستوى المحادثة |
| `metadata` | `thread_metadata` من استجابة API، كما هو |
| `report_info` | `{"title", "file_name", "url"}` أو `null` |
| `exported_at` | وقت التصدير (UTC ISO 8601) |

المفاتيح الاختيارية — غائبة عندما لا يوجد شيء لتسجيله:

| المفتاح | يُضاف عندما | المحتوى |
|---|---|---|
| `interruptions` | أي سير عمل غير مكتمل (`fs_writer.py:242-244`) | قائمة `{location, kind, headline, status}`؛ راجع [أوضاع المحادثة — المقاطعات](modes.md#interruptions-non-completed-workflows) |
| `answer_variants` | يتم اكتشاف متغير إعادة كتابة الإجابة (`fs_writer.py:247-252`) | `side_by_side_metadata` ضيقة تحدد الحقول؛ راجع [أوضاع المحادثة — متغيرات إعادة كتابة الإجابة](modes.md#answer-rewrite-variants-answer_variants) |
| `remote_deleted` | `pplx-export sync-deleted --online` يؤكد الحذف عن بُعد | طابع زمني للشاهد القبري، مكتوب في مكانه، غير قابل للتغيير (لا يتم استبدال القيمة الموجودة أبدًا؛ `sync_deleted_cmd.py:215-244`) — يتم الاحتفاظ بالأرشيف المحلي نفسه |

<a id="conversationmd-the-compact-read" data-pplx-source-anchor="true"></a>
### conversation.md — القراءة المدمجة

`render_conversation` (`render.py:641`): رأس العنوان (الوضع / المؤلف / عدد الدورات / عدد الاستشهادات)،
ثم لكل دورة زوج `### Query` + `### Answer` مع الإجابات كاملة، وعند الوجود —
ملحق المهمة الخلفية على مستوى المحادثة في النهاية. هذا هو الملف الذي يجب فتحه أولاً؛ عمليات العمل لكل دورة
موجودة في `turns/`.

<a id="turnsturn_nnnnmd-the-full-read" data-pplx-source-anchor="true"></a>
### turns/turn_NNNN.md — القراءة الكاملة

`render_turn` (`render.py:596`): ملف واحد لكل دورة (`turn_0001.md` …)، كل منها يحتوي على عملية العمل
الكاملة — الخطوات، استدعاءات الأدوات، تشغيلات الوكيل الفرعي، الجداول، الاستشهادات لكل دورة. عندما يتقلص
عدد دورات المحادثة، يتم حذف ملفات `turn_*.md` القديمة ذات الأرقام العالية ولكن الملفات غير المتأثرة تحتفظ
بوقت تعديلها (`fs_writer.py:287-301`).

### sources.json / sources.md

الاستشهادات على مستوى المحادثة، مكررة حسب الرابط (`fs_writer.py:270-278`). `sources.json` هو
`{"count", "sources": [{"name", "url", "snippet", "timestamp"}]}`؛ `sources.md` هو نفس القائمة
كقائمة روابط Markdown مرقمة.

### report.md

منتج تقرير البحث العميق، يُكتب فقط عندما تحمل المحادثة واحدًا
(`fs_writer.py:308-316`): عنوان التقرير، اسم ملف المنتج الأصلي، ثم نص التقرير الكامل
بتنسيق Markdown.

<a id="raw_entriesjson-raw_blocksjson-raw-fidelity" data-pplx-source-anchor="true"></a>
### raw_entries.json / raw_blocks.json — الدقة الخام

استجابات API، محفوظة كما هي **قبل** أي تحليل (`fs_writer.py:257-266`):

- `raw_entries.json` — الاستجابة البسيطة: `{"thread_metadata", "entries", "background_entries"}`.
  موجودة دائمًا.
- `raw_blocks.json` — الاستجابة المخطط لها، نفس الشكل. غائبة لمحادثات `search`
  (لا جلب للكتل)؛ يتم جلبها للأوضاع الأربعة الأخرى، وأيضًا كحل احتياطي عندما تكون كل
  إشارات اكتشاف الوضع مفقودة.

هذان الملفان هما مرساة دقة الأرشيف: يمكن إعادة بناء التحليل والعرض والسجلات
كلها منها دون اتصال، بدون أي شبكة. راجع
[العمليات دون اتصال](../architecture/offline-operations.md).

<a id="assets-products-and-their-manifest" data-pplx-source-anchor="true"></a>
### assets/ — المنتجات وبيانها

يتم جلب المنتجات القابلة للتنزيل (ملفات وضع الكمبيوتر، وأي أصول أخرى يسردها API)
من روابط CloudFront الموقعة إلى `assets/files/`؛ يتم تحديد الامتداد وقت التنزيل
من مسار الرابط، أو بايتات السحر للمحتوى، أو نوع الأصل. `assets/assets_manifest.json`
(`fs_writer.py:320-330`) يسجل كل إصدار:

```json
{"count": 2, "files": [{"filename": "analysis.xlsx", "n_versions": 2,
  "versions": [{"uuid": "…", "asset_type": "XLSX_FILE", "version": "v1",
                "created_at": "…", "downloaded_to": "…"}]}]}
```

`count` هو دائمًا **العدد الإجمالي للإصدارات** (Σ `len(versions)`)، وليس عدد مجموعات
الملفات — استخدم `len(files)` لذلك.

<a id="the-index-layer" data-pplx-source-anchor="true"></a>
## طبقة index/

`web_archive/index/` تحتوي على حالة وفهارس تديرها الأداة — لا تقم بتحريرها يدويًا:

| الملف | مكتوب بواسطة | الدلالة |
|---|---|---|
| `library_<account>.json` | `pplx-export index` (`index_cmd.py:17-43`) | فهرس كامل لمحادثات الحساب (GraphQL)؛ إدخال للفهارس الدفعية / المجدولة / المساحة |
| `batch_state.json` | `BatchState` (`state.py`) | نقطة تفتيش قابلة للاستئناف: uuid → حالة (ok/error/expired/deleted) + lastUpdated؛ كتابات ذرية؛ الملفات التالفة تُنسخ احتياطيًا تلقائيًا كـ `.corrupt-<ts>` |
| `.cookies.json` | ذاكرة تخزين مؤقت للكوكيز (`common.py:111`, `common.py:150`) | ذاكرة تخزين مؤقت للكوكيز بحداثة 12 ساعة مع المصدر والبريد الإلكتروني للحساب؛ تُكتب `0o600` ثم تُستبدل ذريًا (بيانات اعتماد الجلسة، قابلة للقراءة من قبل المالك فقط) |
| `space_<slug>.json` | `pplx-export space-index` (`spaces_cmd.py:106-167`) | قائمة محادثات لكل مساحة، بما في ذلك تعيين المعرف المزدوج `context_uuid` |
| `space_meta.json` | `pplx-export spaces --fetch-meta` (`spaces_cmd.py:299-330`) | ذاكرة تخزين مؤقت لمالك/عضو المساحة تُستخدم في عمليات إعادة البناء |
| `credit_usage_<account>.json` | `pplx-export usage-backfill` (`usage_backfill_cmd.py:17`) | استخدام الائتمان لكل محادثة (غير قابل للتغيير، قابل للاستئناف، يُفرغ كل 25 إدخالًا) |
| `cron_snippet.txt` | `pplx-export schedule` (`scheduler.py:48-78`) | مقتطف استدعاء cron (مسارات مطلقة) |
| `answer_variants_log.jsonl` | `variant_log.append_registry` (`variant_log.py:76`) | سجل مركزي لمتغيرات إعادة كتابة الإجابة، مكرر حسب (محادثة، إدخال)، غير قابل للتغيير |
| `logs/` | `--log-file` (`common.py:218-229`) | سجلات DEBUG كاملة |

<a id="the-spaces-layer" data-pplx-source-anchor="true"></a>
## طبقة spaces/

`pplx-export spaces` تجمع `index/library_*.json` في فهرس مساحة (`spaces_cmd.py:259-389`):
واحد `<slug>.md` لكل مساحة (الحسابات المشاركة، رأس المالك/العضو، جدول المحادثات،
روابط خلفية لموقع التصدير) بالإضافة إلى سجل `spaces.json`.

!!! ملاحظة "موقع الإخراج"
    `spaces/` يُكتب نسبة إلى دليل العمل الحالي (`spaces_cmd.py:332`) — إنه
    **لا** يتبع `--out`. لا تقم بتحريره يدويًا: إعادة البناء التالية تستبدله.

<a id="cross-day-continuation-directory-migration-by-uuid-identity" data-pplx-source-anchor="true"></a>
## الاستمرار عبر الأيام: ترحيل الدليل بواسطة هوية UUID

اسم الدليل يضم تاريخ `lastUpdated`، لذلك عندما تواصل محادثة في يوم لاحق
يعطي الحساب الساذج دليلًا *جديدًا*. يمنع الكاتب التكرارات بواسطة هوية UUID
(`thread_dir_for`, `fs_writer.py:58-72`):

1. **البحث**: `find_thread_dirs` (`fs_writer.py:74-105`) يبحث في الأرشيف بأكمله عن
   أدلة تنتهي بـ `_<uuid8>` — عبر الحسابات والأوضاع. يُقبل المرشح فقط
   إذا كان `thread.json` موجودًا، ويُحلل، و `web_uuid` يطابق تمامًا؛ الأدلة المفقودة أو التالفة أو
   غير المتطابقة لا تُلمس أبدًا (من الأفضل تخطي الترحيل بدلاً من الدمج الخاطئ).
2. **الدمج**: `_merge_into` (`fs_writer.py:107-178`) يدمج الدليل القديم في الجديد —
   اتحاد الملفات (لا شيء فريد في الدليل القديم يُفقد)؛ نفس الاسم + نفس المحتوى → تخطي؛
   تعارضات نفس الاسم **تحتفظ دائمًا بالجانب الهدف** (الأحدث دلاليًا)، مع تسجيل كل تعارض.
   يتم التحقق من كل ملف منسوخ باستخدام sha256 قبل حذف الدليل القديم؛ أي فشل
   يترك الدليل القديم سليمًا وإعادة المحاولة غير قابلة للتغيير.
3. **تنظيف التكرارات التاريخية**: `consolidate_uuid` (`fs_writer.py:180-209`) يدمج
   أدلة التاريخ المكررة لـ UUID واحد عبر الأرشيف، مع الاحتفاظ بالدليل الذي يحتوي على أقصى
   `lastUpdated` — شبكة الأمان للتكرارات التي خلفتها الإصدارات الأقدم.

نفس الصرامة في UUID تحمي الروابط الخلفية لفهرس المساحة: الأدلة المرشحة التي تحتوي على
`thread.json` مفقود/تالف/غير متطابق لا تُربط أبدًا.

<a id="hand-editable-vs-tool-managed" data-pplx-source-anchor="true"></a>
## قابل للتحرير يدويًا مقابل مُدار بالأداة

- **مُدار بالأداة (لا تقم بتحريره يدويًا)**: كل شيء داخل أدلة المحادثات، بالإضافة إلى `index/`،
  `spaces/`، و `relations/`. إذا كان المحتوى خاطئًا، أصلح الأداة وأعد التوليد — إصلاحات
  العرض تمر عبر `pplx-export re-render`، إصلاحات البيانات عبر أمر التعبئة الخلفي المطابق
  (راجع [أوامر الصيانة](maintenance-commands.md)) — لذلك يبقى كل أثر قابلًا لإعادة الإنتاج من
  البيانات الخام.
- **قابل للتحرير يدويًا**: التوثيق وتقارير مراجعة `web_archive/crosscheck/`.
  استثناء واحد على مستوى المستخدم: يمكن تسجيل إجابة بديلة تم إنقاذها يدويًا كـ
  `rewritten_answer_variant.md` داخل دليل المحادثة — راجع
  [أوضاع المحادثة — متغيرات إعادة كتابة الإجابة](modes.md#answer-rewrite-variants-answer_variants).

<a id="see-also" data-pplx-source-anchor="true"></a>
## انظر أيضًا

- [أوضاع المحادثة](modes.md) — الأوضاع الخمسة وما ينتجه كل منها
- [المزامنة المتزايدة](incremental-sync.md) — كيف يقود `lastUpdated` عمليات إعادة التصدير
- [أوامر الصيانة](maintenance-commands.md) — إعادة العرض، التعبئة الخلفية، المزامنة المحذوفة
- [نموذج البيانات وعقد الدليل](../architecture/data-model.md) — فئات البيانات الأساسية
- [خط أنابيب التصدير](../architecture/export-pipeline.md) — كيف تُكتب هذه الملفات
- [العمليات دون اتصال](../architecture/offline-operations.md) — إعادة بناء كل شيء من `raw_*.json`
