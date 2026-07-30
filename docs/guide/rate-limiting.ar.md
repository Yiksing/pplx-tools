---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/rate-limiting.md"
translation_source_sha256: "2cb719b72d2ca750e9a7d19731320f9a1b0541e41f3aacca02afe17592a84d3d"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="rate-limiting" data-pplx-source-anchor="true"></a>
# تحديد المعدل

كل رقم في سياسة الإيقاع يخدم هدفًا واحدًا: يجب أن يبدو حركة مرور الأرشفة مثل التصفح العادي. تكلف عملية التصدير ذات الخيط الواحد 1–2 طلب — تقريبًا عرض صفحة واحدة — وتوزع عمليات التشغيل المجمعة تلك الطلبات على فترات زمنية عشوائية بدون تزامن. هذا مطلب صريح لمكافحة المخاطر (`pplx_export/core/throttle.py:1-2`)، وليس مقبض أداء قابل للضبط.

<a id="the-numbers" data-pplx-source-anchor="true"></a>
## الأرقام

| أين | الإيقاع | الكود |
|---|---|---|
| `batch`: بين الخيوط | عشوائي منتظم 10–20 ثانية (`--delay-min` / `--delay-max`) | `pplx_export/cli.py:126-129`, `pplx_export/core/throttle.py:33-36` |
| `sync-deleted --online`: بين المرشحين | عشوائي منتظم 10–20 ثانية | `pplx_export/cli.py:164-167`, `pplx_export/commands/sync_deleted_cmd.py:368-369` |
| `search-mode-backfill`: احتياطي عبر الإنترنت | عشوائي منتظم 10–20 ثانية | `pplx_export/cli.py:144-147` |
| الترقيم داخل خيط / قائمة مساحة | ≥3 ثوانٍ بين الصفحات | `pplx_export/sites/perplexity/rest.py:39,56`, `pplx_export/sites/perplexity/adapter.py:285-309` |
| إعادة تعبئة الكتلة المخططة (computer / deep-research / council / study) | ≥4 ثوانٍ انتظار قبل الجلب الثاني | `pplx_export/sites/perplexity/adapter.py:27-32,88` |
| `spaces --fetch-meta` | 3 ثوانٍ لكل مساحة | `pplx_export/commands/spaces_cmd.py:328` |
| `usage-backfill` | 3 ثوانٍ لكل خيط | `pplx_export/commands/usage_backfill_cmd.py:77` |
| `assets-backfill` مراحل عبر الإنترنت | 3 ثوانٍ لكل خيط | `pplx_export/commands/assets_backfill_cmd.py:215,456` |
| تنزيلات الأصول داخل خيط | 0.5 ثانية | `pplx_export/sites/perplexity/assets.py:28,103` |
| `assets-backfill` مرحلة CDN | 6 تنزيلات متوازية، بدون تأخير | `pplx_export/commands/assets_backfill_cmd.py:460-475` |
| تزامن API | لا شيء — أبدًا | — |

<a id="why-these-numbers" data-pplx-source-anchor="true"></a>
## لماذا هذه الأرقام

- **تصدير واحد = 1–2 طلب ≈ عرض صفحة واحدة.** خيط بحث يكلف `GET /rest/thread/<uuid>` واحدًا؛ computer / deep-research / council / study يضيف جلب كتل مخططة واحدًا بالضبط (`pplx_export/sites/perplexity/adapter.py:87-89`). هذا تقريبًا ما يفعله المتصفح عند فتح الصفحة مرة واحدة — لا يضيف الأرشيف أي حمل ذي معنى فوق الاستخدام العادي.
- **فاصل زمني عشوائي 10–20 ثانية، بدون تزامن.** إيقاع القراءة البشرية، والتوزيع العشوائي يتجنب التوقيت المثالي للميترونوم. الطلبات التسلسلية تحافظ على المعدل أقل مما ينتجه التصفح العادي بالفعل.
- **≥3 ثوانٍ لقلب الصفحات.** الترقيم داخل خيط طويل يحاكي وقت التمرير والقراءة.
- **≥4 ثوانٍ قبل جلب الكتل.** إعادة الجلب المخططة ستضرب API بشكل متتالٍ مع الجلب العادي؛ التوقف يحاكي التأخير قبل تحميل صفحة ثقيلة حمولتها الكاملة.
- **0.5 ثانية لتنزيلات الأصول.** ملفات ثابتة صغيرة، أرخص بكثير من استدعاءات API — ولكن لا يزال يتم إيقاعها.
- **مرحلة CDN هي الاسترخاء الوحيد.** تنزيلات URL الموقعة تصل إلى شبكة توصيل المحتوى، وليس API Perplexity، لذا 6 اتصالات متوازية مقبولة هناك وفقط هناك.

<a id="error-handling-and-backoff" data-pplx-source-anchor="true"></a>
## معالجة الأخطاء والتراجع

يتم كل التصنيف في `CookieTransport._request` (`pplx_export/core/http/cookie_transport.py:63-126`)؛ يحصل كل طلب على ما يصل إلى `max_retries=3` محاولة (`cookie_transport.py:48`).

```mermaid
flowchart TD
    R{response} -->|"2xx"| OK["reset backoff counter"]
    R -->|"429"| BO["backoff + retry (≤3 attempts)"]
    R -->|"5xx / network error"| BO
    R -->|"401 / 403"| AF["raise immediately →<br/>abort after 3 consecutive"]
    R -->|"ENTRY_EXPIRED / ENTRY_DELETED"| TERM["terminal mark<br/>never retried"]
```

| الاستجابة | التصنيف | المعالجة |
|---|---|---|
| 2xx | نجاح | إعادة تعيين عداد التراجع (`cookie_transport.py:77`) — لا تتراكم العدادات عبر الطلبات |
| 429 | تم تحديد المعدل | التراجع وإعادة المحاولة (`cookie_transport.py:86-92`) |
| 500 / 502 / 503 / 504 | خطأ خادم عابر (504 عادةً خلل Cloudflare) | التراجع وإعادة المحاولة مرة واحدة على الأقل قبل الاستسلام (`cookie_transport.py:99-107`) |
| خطأ شبكة | عابر | التراجع وإعادة المحاولة (`cookie_transport.py:117-125`) |
| 401 / 403 | فشل مصادقة | رفع `AuthTransportError` فورًا — بدون تراجع (`cookie_transport.py:82-85`) |
| 400 + `ENTRY_EXPIRED` | مسح المنصة | `EntryExpiredError` — نهائي، لا يعاد أبدًا (`cookie_transport.py:96-98`) |
| 400 + `ENTRY_DELETED` | حذف مستخدم/بعيد | `EntryDeletedError` — نهائي، لا يعاد أبدًا (`cookie_transport.py:93-95`) |
| 404 / رموز أخرى | خطأ عادي | لا إعادة محاولة على مستوى النقل؛ **أبدًا** لا يتم تعيينه إلى حالة نهائية (`cookie_transport.py:108-116`) |

**صيغة التراجع** (`pplx_export/core/throttle.py:38-50`):
`delay_max × 3^N`، حيث `N` هو عدد الإخفاقات المتتالية (الأس مقيد عند 8)، مع تشويش ±20% ضد التزامن، وبحد أقصى 300 ثانية. لا يوجد نوم لا طائل منه بعد المحاولة الفاشلة الأخيرة، و`throttle.reset()` يمسح العداد عند أول نجاح (`throttle.py:52`).

**نبضات القلب (مرئية في مستوى الإفصاح الافتراضي).** لم يعد التراجع ينتظر بصمت: يطبع سطرًا مقدمًا ثم عدًا تنازليًا كل `Throttle.heartbeat_interval` (افتراضي 10 ثوانٍ)، وينام في أجزاء مجموعها يساوي نفس الإجمالي — لذا يبقى الإيقاع وميزانية مكافحة المخاطر دون تغيير، فقط أصبح مرئيًا (`pplx_export/core/throttle.py`, `Throttle._sleep_with_heartbeat`). نفس الفكرة تغطي فترتي انتظار طويلتين أخريين: كل طلب قيد التنفيذ يصدر علامة "لا يزال ينتظر الرد" أثناء تعطله قبل الاستجابة (`CookieTransport._open_read`)، و`pplx-ask` تيارات SSE تصدر علامة "لا يزال ينتظر تيار الاستجابة" أثناء صمت تشغيل deep-research / council (`ask_api.post_stream`). لا يتطلب أي من هذا `-v`.

لماذا توجد كل قاعدة:

- **تراجع 429** — طلب الخادم صراحةً الإبطاء؛ احترمه بشكل أسي.
- **إعادة محاولة 5xx** — يجب ألا يفشل خيط بسبب خلل بوابة واحد.
- **401/403 بدون تراجع** — الانتظار لا يمكنه إصلاح ملف تعريف ارتباط ميت.
- **`ENTRY_EXPIRED` بدون إعادة محاولة** — مسح المنصة (~نافذة 3 أشهر) دائم؛ إعادة المحاولة تحرق الطلبات وميزانية التراجع فقط.
- **404 ليس نهائيًا أبدًا** — خيط تم إنشاؤه بواسطة `pplx-ask` يمكن أن يعطي 404 بشكل عابر بعد الإنشاء مباشرة (تأخير الانتشار)؛ علامة نهائية ستدفن خيطًا حيًا غير مرئي لفترة وجيزة فقط.

<a id="runtime-budget-for-callers" data-pplx-source-anchor="true"></a>
## ميزانية وقت التشغيل للمتصلين

انضباط التراجع أعلاه يستبدل وقت الحائط بسلامة الحساب، ويجب على المتصلين تخصيص ميزانية لذلك الوقت: طلب واحد يقوم بما يصل إلى 3 محاولات مع نوم تراجع بينها — حتى 300 ثانية لكل منها (`pplx_export/core/throttle.py:38-50`) — لذا بينما تتقلب الشبكة، يمكن لطلب واحد أن يشغل بشكل مشروع حوالي 10 دقائق. `index` / `batch` يبدأان أيضًا بفحص جلسة يتبع نفس القواعد (`pplx_export/commands/common.py`, `make_transport`)؛ مرر `--skip-auth-check` لتخطي هذا الفحص والبدء فورًا (انظر [التكوين](configuration.md)). الصمت الطويل يعني أن انتظارًا قيد التقدم، ليس تعليقًا — وهذا الانتظار أصبح الآن ظاهرًا بواسطة نبضات INFO في مستوى الإفصاح الافتراضي (العد التنازلي للتراجع، الطلب قيد التنفيذ، وتيار SSE).

ثلاث قواعد للوكلاء، وظائف cron، وأغلفة CI:

1. **حساب واحد لكل استدعاء.** قم بتشغيل الحسابات بشكل تسلسلي كعمليات منفصلة؛ لا تربطها أبدًا بـ `&&` داخل مهمة خارجية تفرض مهلة زمنية صارمة — سلسلة التراجع للحساب الأول تستهلك الميزانية بأكملها والحساب المرتبط لا يعمل أبدًا.
2. **ميزانية ≥ 15 دقيقة، أو افصل.** أعط الأغلفة مهلة زمنية سخية، أو قم بتشغيلها في الخلفية وراقب نبضات القلب (الآن في مستوى الإفصاح الافتراضي؛ `-v` / `--log-file` يضيفان التتبع الكامل) لتمييز انتظارات التراجع عن التعليقات الحقيقية.
3. **المقاطعة آمنة دائمًا.** الحالة تُكتب بشكل ذري؛ إعادة التشغيل غير مؤثرة وتصلح أي فجوة تركتها المقاطعة (دلالات الإيقاف المبكر والاستئناف: [المزامنة المتزايدة](incremental-sync.md)).

<a id="auth-fail-fast" data-pplx-source-anchor="true"></a>
## فشل المصادقة السريع

طبقة الدفعة تحسب إخفاقات المصادقة المتتالية (`_AUTH_FAIL_FAST = 3`, `pplx_export/commands/batch_cmd.py:43`). أي استجابة وصلت إلى الخادم — بما في ذلك `ENTRY_DELETED` / `ENTRY_EXPIRED` — تثبت أن ملف تعريف الارتباط يعمل وتعيد تعيين العداد (`batch_cmd.py:170-182`). ثلاث 401/403 متتالية ويحفظ التشغيل ملف الحالة الخاص به، ثم يلغي (`batch_cmd.py:190-194`): الاستمرار بملف تعريف ارتباط ميت سيجعل مئات الخيوط تفشل كل منها مرة واحدة — ساعات مهدرة. `sync-deleted` يطبق نفس الانضباط (`pplx_export/commands/sync_deleted_cmd.py:111,333-337`). الحل هو تحديث ملف تعريف الارتباط وإعادة التشغيل؛ كل ما تم تصديره بالفعل يتم تخطيه.

`batch` والنقل يشتركان في مثيل `Throttle` واحد (`pplx_export/cli.py:280-282`, `batch_cmd.py:101-105`)، لذا لا ينقسم عد التراجع أبدًا بين الطبقات — والمثيل المشترك يبقى على قيد الحياة عند التبديل التلقائي للحساب.

<a id="scheduling-periodic-sync" data-pplx-source-anchor="true"></a>
## جدولة المزامنة الدورية

`pplx-export schedule` يحسب الخطة المتزايدة الحالية (عدد الجديد/المحدث) ويكتب مقتطف cron إلى `<out>/index/cron_snippet.txt` (`pplx_export/commands/misc_cmd.py:86-96`, `pplx_export/hooks/scheduler.py:48-77`):

```bash
pplx-export schedule --account alice
```

```cron
17 3 * * * cd '<out-parent>' && '/abs/path/to/pplx-export' batch --account 'alice' --out '<out>'
```

- التشغيلات الدورية هي **متزايدة فقط** (إيقاف مبكر) — لا إعادة جلب كاملة (`scheduler.py:4-9`).
- يستخدم المقتطف مسارات مطلقة ومقتبسة لأن دليل عمل cron و`PATH` غير متوقعين (`scheduler.py:63-75`).
- قم بتثبيته باستخدام `crontab -e` واضبط الوقت حسب الرغبة؛ قم بتوزيع حسابات متعددة على فتحات مختلفة.
- شبكة أمان اختيارية: أضف مسحًا يدويًا أسبوعيًا أو شهريًا باستخدام `pplx-export batch --account alice --full` (انظر [incremental-sync.md](incremental-sync.md)).

<a id="see-also" data-pplx-source-anchor="true"></a>
## انظر أيضًا

- [incremental-sync.md](incremental-sync.md) — ما يصدره كل تشغيل مجدول فعليًا
- [pplx-export.md](pplx-export.md) — `--delay-min` / `--delay-max` وخيارات الأوامر الأخرى
- [troubleshooting.md](troubleshooting.md) — ما يجب فعله بعد إلغاء فشل المصادقة السريع
- [../architecture/rate-limiting-errors.md](../architecture/rate-limiting-errors.md) — تصنيف الأخطاء الكامل
- [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md) — دلالات الأخطاء من جانب المنصة (`ENTRY_EXPIRED`, `ENTRY_DELETED`, Cloudflare)
- [../reference/api/api-authentication.md](../reference/api/api-authentication.md) — ملفات تعريف الارتباط والتبديل بين حسابات متعددة
