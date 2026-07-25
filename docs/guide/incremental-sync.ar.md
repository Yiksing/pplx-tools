---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/incremental-sync.md"
translation_source_sha256: "35868edfb3e8e914afd9afa1b00370bffb9f8a50ca374691229f41d51ffa9b64"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="incremental-sync" data-pplx-source-anchor="true"></a>
# المزامنة التزايدية

تم تصميم `pplx-export batch` للعمل بشكل متكرر: كل تشغيل يصدر فقط ما هو جديد أو
مُعدَّل، ويُصلح الفجوات التي تسببها عمليات التشغيل المتقطعة، ولا يعيد لمس
الخيوط التي أنهتها المنصة بالفعل. المصدر الوحيد للحقيقة حول "ما تم تصديره"
هو `index/batch_state.json` (`BatchState`،
`pplx_export/core/state.py:63`)، الذي يتم تحديثه بعد كل خيط — ولا توجد
نسخة ظل منفصلة.

<a id="prerequisites-and-basic-usage" data-pplx-source-anchor="true"></a>
## المتطلبات الأساسية والاستخدام الأساسي

```bash
pplx-export index --account alice   # refresh index/library_alice.json first
pplx-export batch --account alice   # incremental export (early stop, resumable)
```

يرفض `batch` العمل بدون الفهرس
(`pplx_export/commands/batch_cmd.py:79-81`). يقوم `--limit N` و `--mode <mode>`
بتصفية صفوف الفهرس قبل التخطيط؛ يتم تخطي الصفوف التي تفتقد `entryUUID`
مع تحذير بدلاً من تعطل التشغيل (`batch_cmd.py:95-100`).

<a id="how-the-incremental-plan-works" data-pplx-source-anchor="true"></a>
## كيف تعمل الخطة التزايدية

1. **الفرز.** يتم فرز صفوف الفهرس حسب `lastUpdated`، الأحدث أولاً
   (`batch_cmd.py:89`). المحادثات الجديدة تمامًا والمحادثات القديمة المستأنفة (التي
   نقلها `lastUpdated` إلى الأعلى) تقع في القمة — هذا الترتيب هو
   ما يجعل التوقف المبكر آمنًا.
2. **التصنيف.** يقوم `plan_incremental`
   (`pplx_export/hooks/incremental.py:36-87`) — وهي دالة خالصة مشتركة بين
   `batch` و `schedule` — بتعيين إجراء واحد بالضبط لكل صف:

   | الإجراء | الشرط | ما تفعله الدفعة |
   |---|---|---|
   | `new` | uuid لم يُرَ مطلقًا في `batch_state` | تصدير |
   | `updated` | يختلف `lastUpdated` عن القيمة المسجلة، أو `--force` | إعادة تصدير |
   | `done` | الحالة `ok` و `lastUpdated` لم تتغير | تخطي |
   | `expired` | أعادت المنصة `ENTRY_EXPIRED` في محاولة سابقة | تخطي — نهائي، لا يُعاد أبدًا |
   | `deleted` | أكد `sync-deleted` حذفًا عن بُعد | تخطي — نهائي، لا يُعاد أبدًا |

3. **التوقف المبكر.** افتراضيًا (لا `--full` ولا `--force`) يتم اقتطاع أطول
   تشغيل متتالي من الإدخالات النهائية (`done` / `expired` / `deleted`)
   بالكامل ويتم احتسابه كـ `n_stopped` (`incremental.py:83-87`). نظرًا لأن
   القائمة مرتبة من الأحدث إلى الأقدم، فإن كل ما هو أسفل إدخال غير متغير هو بالضرورة
   أقدم وغير متغير أيضًا — الاستمرار في المسح سيضيع الوقت فقط.

   ```mermaid
   flowchart TD
       IDX["library index rows<br/>sorted by lastUpdated, newest first"] --> PLAN["plan_incremental"]
       PLAN --> NEW["new → export"]
       PLAN --> UPD["updated → re-export"]
       PLAN --> DONE["done → skip"]
       PLAN --> TERM["expired / deleted → skip (terminal)"]
       DONE --> STOP["early stop:<br/>trailing terminal run trimmed"]
       TERM --> STOP
   ```

4. **التنفيذ.** يتم وضع علامة على كل خيط تم تصديره فورًا (`mark_ok` /
   `mark_error` / `mark_expired` / `mark_deleted`) ويتم حفظ ملف الحالة
   بعد كل عنصر (`batch_cmd.py:154-201`); كما يحفظ `KeyboardInterrupt`
   قبل النشر (`batch_cmd.py:158-161`). عمليات الكتابة ذرية — ملف مؤقت
   بالإضافة إلى `os.replace` (`state.py:145-152`) — لذا فإن التشغيل المتقطع لا يترك أبدًا
   JSON مقطوعًا.

<a id="gap-healing-after-interrupted-runs" data-pplx-source-anchor="true"></a>
## إصلاح الفجوات بعد عمليات التشغيل المتقطعة

لا يدفن التوقف المبكر فجوة أبدًا. الخيوط التي فشلت (الحالة `error`) أو لم
يتم الوصول إليها تقع **فوق** اللاحقة النهائية، لذا فإن التشغيل التالي يعيد تخطيطها
كـ `updated` / `new` ويصدرها قبل الوصول إلى نقطة التوقف المبكر
(`incremental.py:12-14`، `batch_cmd.py:206-208`). إلى جانب حفظ الحالة لكل عنصر،
يمكن مقاطعة تشغيل دفعة في أي نقطة وإعادة تشغيله ببساطة.

إذا كان `batch_state.json` نفسه تالفًا، فلن يتم مسحه بصمت: يتم
إعادة تسمية الأصل إلى `batch_state.json.corrupt-<timestamp>` حتى لا تُفقد الحالات النهائية المسجلة
ويتم إعادة محاولتها دون داع (`state.py:68-81`).

<a id="-full-and-force" data-pplx-source-anchor="true"></a>
## `--full` و `--force`

| العلامة | التأثير | الحالات النهائية | متى تستخدم |
|---|---|---|---|
| *(افتراضي)* | توقف مبكر على التشغيل النهائي المتتالي | تم التخطي | كل تشغيل منتظم / مجدول |
| `--full` | مسح كامل، لا توقف مبكر؛ الخيوط غير المتغيرة لا تزال تُتخطى كـ `done` | تم التخطي | شبكة أمان دورية، أو عند الاشتباه بفجوات في الأرشيف |
| `--force` | إعادة تصدير كل شيء، حتى الخيوط غير المتغيرة | لا تزال مستبعدة — لا تُعاد أبدًا | بعد إصلاحات خط الأنابيب التي يجب إعادة جلب البيانات الأولية |

يتم استبعاد الحالات النهائية من `--force` عن قصد: إعادة محاولة خيط منتهي الصلاحية أو
محذوف عن بُعد يهدر فقط الطلبات وميزانية التوقف (`batch_cmd.py:120-127`).

انظر أيضًا [`status`](maintenance-commands.md#status): تقرير بدون شبكة عن
حساب الحالة وخطة التغيير المحسوبة بنفس دلالات `plan_incremental`
(`new`/`updated`/عدد التوقف المبكر).

تعمل مقارنة `lastUpdated` على تطبيع الأصفار الزائدة في
جزء الكسور من الثانية (`.18033Z` يساوي `.180330Z`; `state.py:23-55`)،
لأن المنصة تسقطها أحيانًا — مقارنة سلسلة نصية دقيقة قد تخطئ في تقدير
"تم التغيير" وتسبب تصديرات مكررة.

<a id="terminal-states-expired-and-deleted" data-pplx-source-anchor="true"></a>
## الحالات النهائية: `expired` و `deleted`

| | `expired` | `deleted` |
|---|---|---|
| المعنى | قامت المنصة بتنظيف الخيط (نافذة احتفاظ ~3 أشهر)؛ أعادت محاولة التصدير `ENTRY_EXPIRED` | حذف من المستخدم/عن بُعد، تم تأكيده بواسطة `sync-deleted` |
| تم التسجيل بواسطة | `batch` نفسه (`mark_expired`، `state.py:131-134`) | `pplx-export sync-deleted --online` (`mark_deleted`، `state.py:136-143`) |
| أعيدت المحاولة؟ | أبدًا — ولا حتى مع `--force` | أبدًا — ولا حتى مع `--force` |
| الدليل | استجابة `ENTRY_EXPIRED` | حقل `note`: غياب الفهرس + `GET /rest/thread/<uuid>` → `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 |

<a id="sync-deleted-confirming-remote-deletions" data-pplx-source-anchor="true"></a>
### sync-deleted: تأكيد الحذف عن بُعد

```bash
pplx-export sync-deleted --account alice            # offline dry-run: list candidates only
pplx-export sync-deleted --account alice --online   # confirm each candidate online
```

1. **المرشحون (بدون اتصال، بدون شبكة).** أي خيط بحالة `ok` في
   `batch_state` مفقود من اتحاد `entryUUID` لـ **جميع**
   فهارس حساب `index/library_*.json` هو مرشح مشتبه به للحذف عن بُعد
   (`pplx_export/commands/sync_deleted_cmd.py:148-212`). الاتحاد عبر
   الحسابات مطلوب: خيط مملوك لـ `bob` ولكن تم تصديره بواسطة `alice`
   من خلال مساحة مشتركة لا يظهر أبدًا في فهرس `alice` الخاص —
   فرق حساب واحد سيؤدي إلى نتائج إيجابية خاطئة لتلك المجموعة بأكملها. عندما لا يوجد
   فهرس قابل للاستخدام على الإطلاق، يتم تخطي كل مرشح بأمان مع تسجيل السبب.
2. **تشغيل تجريبي افتراضيًا.** بدون `--online` يسرد الأمر فقط
   المرشحين — لا شبكة، لا تغييرات في الملفات.
3. **تأكيد `--online`.** يتم التحقق من كل مرشح باستخدام
   `GET /rest/thread/<uuid>`، باستخدام حساب `export_via` للمرشح من
   `thread.json` (يتم تبديل ملف تعريف الارتباط تلقائيًا):

   | النتيجة | النتيجة النهائية |
   |---|---|
   | `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 | تم التأكيد: `batch_state` يضع علامة نهائية `deleted` (يسجل `note` السبب)، وكل `thread.json` لذلك الخيط يحصل على طابع زمني `remote_deleted` في مكانه |
   | الخيط لا يزال موجودًا | إيجابي خاطئ: يتم الإبلاغ عنه كما هو (قد لا يكون الفهرس محدثًا بالكامل — أعد تشغيل `index` وتحقق مرة أخرى)، لم يتغير شيء |
   | 5xx / خطأ شبكة | لا تغيير في الحالة؛ يُترك المرشح للجولة التالية |
   | 3 حالات 401/403 متتالية | إحباط سريع الفشل — لا يمكن لملف تعريف ارتباط منتهي الصلاحية إصلاح نفسه، والاستمرار قد يضع علامة خاطئة على الخيوط الحية (`sync_deleted_cmd.py:333-337`) |

   يتم حفظ العلامات المؤكدة لكل عنصر، لذا فإن تشغيل `--online` المتقطع
   لا يفقد شيئًا وإعادة التشغيل متسقة (`sync_deleted_cmd.py:254-256`).

<a id="the-tombstone-principle" data-pplx-source-anchor="true"></a>
## مبدأ شاهد القبر

!!! warning "لا يتم حذف الأرشيفات المحلية أبدًا"
    هذا الأرشيف هو النسخة الاحتياطية الرسمية للمحادثات المصدرة.
    يقوم `sync-deleted` فقط *بتحديد ووضع علامة* (شاهد قبر): فهو **لا يحذف
    أو ينقل أي ملف أرشيف**. يؤكد التغيير شيئين بالضبط — حالة
    `batch_state` ومفتاح علامة واحد في `thread.json`:

    ```json
    "remote_deleted": "2026-07-23T10:20:30Z"
    ```

    الطابع متسق: مفتاح `remote_deleted` الموجود لا يتم
    إعادة كتابته أو استبداله (`sync_deleted_cmd.py:215-244`).

<a id="idempotence-and-offline-re-render" data-pplx-source-anchor="true"></a>
## الاتساق وإعادة العرض دون اتصال

- إعادة تشغيل `batch` مقابل فهرس غير متغير لا يصدر شيئًا: كل صف
  يُصنف كـ `done` ويتوقف التشغيل عند نقطة التوقف المبكر. عمليات كتابة الحالة
  ذرية، والعلامات لكل خيط، وإعادة تأكيد الحذف لا تكرر أبدًا
  طابع `remote_deleted`.
- يحتفظ الأرشيف بحمولات API الأولية (`raw_entries.json` /
  `raw_blocks.json`)، لذا يمكن إعادة إنشاء الملفات المعروضة في أي وقت
  بدون وصول إلى الشبكة:

  ```bash
  pplx-export re-render                 # rebuild conversation.md + turns/ everywhere
  pplx-export re-render --dry-run       # only list the thread directories
  pplx-export re-render --thread-json   # also sync interruptions / answer_variants keys
  ```

  يقوم `re-render` بإعادة تحليل JSON الأولي باستخدام العارض الحالي
  (`pplx_export/commands/rerender_cmd.py:105-190`): يتم إعادة كتابة `conversation.md` و
  `turns/turn_*.md`، وإزالة ملفات الأدوار القديمة المرقمة فوق عدد الأدوار الحالي،
  وترك المصادر والأصول و `report.md` و `thread.json`
  دون تغيير. هكذا يتم نشر إصلاحات العارض على
  الأرشيف بأكمله دون طلب واحد.

<a id="see-also" data-pplx-source-anchor="true"></a>
## انظر أيضًا

- [pplx-export.md](pplx-export.md) — مرجع كامل لأمر `batch` (`--mode`، `--limit`، التأخيرات)
- [maintenance-commands.md](maintenance-commands.md) — `sync-deleted`، `re-render` وأوامر التعبئة الخلفية
- [archive-layout.md](archive-layout.md) — أين توجد `batch_state.json` و `thread.json`
- [rate-limiting.md](rate-limiting.md) — السرعة بين الخيوط، التوقف، الإحباط السريع للمصادقة
- [../architecture/export-pipeline.md](../architecture/export-pipeline.md) — خط أنابيب التصدير الكامل
- [../architecture/offline-operations.md](../architecture/offline-operations.md) — خط أنابيب إعادة البناء دون اتصال بالتفصيل
- [../architecture/rate-limiting-errors.md](../architecture/rate-limiting-errors.md) — تصنيف الأخطاء ومعالجة الحالة النهائية
