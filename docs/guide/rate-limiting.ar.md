---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/rate-limiting.md"
translation_source_sha256: "0f94f3ddbb3a7ac5ea7eef4a48ecd5479e5a834d8fda263c700df5ada0de3350"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="rate-limiting" data-pplx-source-anchor="true"></a>
# تحديد المعدل

كل رقم في سياسة التوقيت يخدم هدفًا واحدًا: يجب أن يبدو حركة الأرشفة مثل التصفح العادي. تكلف عملية التصدير ذات الخيط الواحد 1–2 طلب — تقريبًا عرض صفحة واحدة — وتوزع عمليات التشغيل الدفعية هذه الطلبات على فترات عشوائية دون تزامن. هذا مطلب صريح لمكافحة المخاطر (`pplx_export/core/throttle.py:1-2`)، وليس مقبض أداء قابل للضبط.

<a id="the-numbers" data-pplx-source-anchor="true"></a>
## الأرقام

| أين | التوقيت | الكود |
|---|---|---|
| `batch`: بين الخيوط | عشوائي منتظم 10–20 ثانية (`--delay-min` / `--delay-max`) | `pplx_export/cli.py:126-129`, `pplx_export/core/throttle.py:33-36` |
| `sync-deleted --online`: بين المرشحين | عشوائي منتظم 10–20 ثانية | `pplx_export/cli.py:164-167`, `pplx_export/commands/sync_deleted_cmd.py:368-369` |
| `search-mode-backfill`: الاحتياطي عبر الإنترنت | عشوائي منتظم 10–20 ثانية | `pplx_export/cli.py:144-147` |
| الترقيم داخل خيط / قائمة مساحة | ≥3 ثوانٍ بين الصفحات | `pplx_export/sites/perplexity/rest.py:39,56`, `pplx_export/sites/perplexity/adapter.py:285-309` |
| التعبئة الخلفية للكتل المخططة (computer / deep-research / council / study) | ≥4 ثوانٍ انتظار قبل الجلب الثاني | `pplx_export/sites/perplexity/adapter.py:27-32,88` |
| `spaces --fetch-meta` | 3 ثوانٍ لكل مساحة | `pplx_export/commands/spaces_cmd.py:328` |
| `usage-backfill` | 3 ثوانٍ لكل خيط | `pplx_export/commands/usage_backfill_cmd.py:77` |
| مراحل `assets-backfill` عبر الإنترنت | 3 ثوانٍ لكل خيط | `pplx_export/commands/assets_backfill_cmd.py:215,456` |
| تنزيلات الأصول داخل خيط | 0.5 ثانية | `pplx_export/sites/perplexity/assets.py:28,103` |
| مرحلة CDN `assets-backfill` | 6 تنزيلات متوازية، بدون تأخير | `pplx_export/commands/assets_backfill_cmd.py:460-475` |
| تزامن API | لا شيء — أبدًا | — |

<a id="why-these-numbers" data-pplx-source-anchor="true"></a>
## لماذا هذه الأرقام

- **التصدير الواحد = 1–2 طلب ≈ عرض صفحة واحدة.** يكلف خيط البحث `GET /rest/thread/<uuid>` واحدًا؛ يضيف computer / deep-research / council / study جلب كتل مخططة واحدًا بالضبط (`pplx_export/sites/perplexity/adapter.py:87-89`). هذا تقريبًا ما يفعله المتصفح عند فتح الصفحة مرة واحدة — لا يضيف الأرشيف أي حمل ذي معنى فوق الاستخدام العادي.
- **فاصل عشوائي 10–20 ثانية، بدون تزامن.** إيقاع القراءة البشرية، والتوزيع العشوائي يتجنب التوقيت المثالي الشبيه ببندول الإيقاع. الطلبات التسلسلية تحافظ على المعدل أقل مما ينتجه التصفح العادي بالفعل.
- **≥3 ثوانٍ لقلب الصفحات.** الترقيم داخل خيط طويل يحاكي وقت التمرير والقراءة.
- **≥4 ثوانٍ قبل جلب الكتل.** إعادة الجلب المخطط سيضرب API بالتتابع مع الجلب العادي؛ التوقف يحاكي التأخير قبل تحميل الصفحة الثقيلة حمولتها الكاملة.
- **0.5 ثانية لتنزيلات الأصول.** ملفات ثابتة صغيرة، أرخص بكثير من استدعاءات API — ولكنها لا تزال محددة.
- **مرحلة CDN هي الاسترخاء الوحيد.** تنزيلات URL الموقعة تصل إلى شبكة توصيل المحتوى، وليس API Perplexity، لذا 6 اتصالات متوازية مقبولة هناك فقط.

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
| 429 | تحديد معدل | التراجع وإعادة المحاولة (`cookie_transport.py:86-92`) |
| 500 / 502 / 503 / 504 | خطأ خادم عابر (504 عادةً وميض Cloudflare) | التراجع وإعادة المحاولة مرة واحدة على الأقل قبل الاستسلام (`cookie_transport.py:99-107`) |
| خطأ شبكة | عابر | التراجع وإعادة المحاولة (`cookie_transport.py:117-125`) |
| 401 / 403 | فشل مصادقة | رفع `AuthTransportError` فورًا — بدون تراجع (`cookie_transport.py:82-85`) |
| 400 + `ENTRY_EXPIRED` | مسح المنصة | `EntryExpiredError` — نهائي، لا يعاد أبدًا (`cookie_transport.py:96-98`) |
| 400 + `ENTRY_DELETED` | حذف مستخدم/عن بعد | `EntryDeletedError` — نهائي، لا يعاد أبدًا (`cookie_transport.py:93-95`) |
| 404 / رموز أخرى | خطأ عادي | لا إعادة محاولة على مستوى النقل؛ **أبدًا** لا يُعيّن إلى حالة نهائية (`cookie_transport.py:108-116`) |

**صيغة التراجع** (`pplx_export/core/throttle.py:38-50`):
`delay_max × 3^N`، حيث `N` هو عدد الإخفاقات المتتالية (الأس مقيد عند 8)، مع تشويش ±20% ضد التزامن، وبحد أقصى 300 ثانية. لا يوجد نوم غير مجدٍ بعد المحاولة الفاشلة الأخيرة، و`throttle.reset()` يمسح العداد عند أول نجاح (`throttle.py:52`).

لماذا توجد كل قاعدة:

- **تراجع 429** — طلب الخادم صراحةً الإبطاء؛ احترمه بشكل أسي.
- **إعادة محاولة 5xx** — لا يجب أن يفشل وميض بوابة واحد في خيط.
- **401/403 بدون تراجع** — الانتظار لا يمكنه شفاء ملف تعريف ارتباط ميت.
- **`ENTRY_EXPIRED` بدون إعادة محاولة** — مسح المنصة (نافذة ~3 أشهر) دائم؛ إعادة المحاولة تحرق فقط الطلبات وميزانية التراجع.
- **404 ليس نهائيًا أبدًا** — خيط تم إنشاؤه بواسطة `pplx-ask` يمكن أن يعطي 404 بشكل عابر بعد الإنشاء مباشرة (تأخير الانتشار)؛ علامة نهائية ستدفن خيطًا حيًا غير مرئي لفترة وجيزة فقط.

<a id="auth-fail-fast" data-pplx-source-anchor="true"></a>
## فشل المصادقة السريع

تحسب طبقة الدفعة إخفاقات المصادقة المتتالية (`_AUTH_FAIL_FAST = 3`, `pplx_export/commands/batch_cmd.py:43`). أي استجابة وصلت إلى الخادم — بما في ذلك `ENTRY_DELETED` / `ENTRY_EXPIRED` — تثبت أن ملف تعريف الارتباط يعمل وتعيد تعيين العداد (`batch_cmd.py:170-182`). ثلاث مرات 401/403 متتالية ويحفظ التشغيل ملف حالته، ثم يلغي (`batch_cmd.py:190-194`): الاستمرار بملف تعريف ارتباط ميت سيجعل مئات الخيوط تفشل كل منها مرة واحدة — ساعات مهدرة. `sync-deleted` يطبق نفس الانضباط (`pplx_export/commands/sync_deleted_cmd.py:111,333-337`). الحل هو تحديث ملف تعريف الارتباط وإعادة التشغيل؛ كل ما تم تصديره بالفعل يتم تخطيه.

`batch` وطبقة النقل تشتركان في مثيل `Throttle` واحد (`pplx_export/cli.py:280-282`, `batch_cmd.py:101-105`)، لذا لا ينقسم عد التراجع أبدًا بين الطبقات — والمثيل المشترك يبقى على قيد الحياة عند تبديل الحسابات تلقائيًا.

<a id="scheduling-periodic-sync" data-pplx-source-anchor="true"></a>
## جدولة المزامنة الدورية

`pplx-export schedule` يحسب الخطة التزايدية الحالية (عدد الجديد/المحدث) ويكتب مقتطف cron إلى `<out>/index/cron_snippet.txt` (`pplx_export/commands/misc_cmd.py:86-96`, `pplx_export/hooks/scheduler.py:48-77`):

```bash
pplx-export schedule --account alice
```

```cron
17 3 * * * cd '<out-parent>' && '/abs/path/to/pplx-export' batch --account 'alice' --out '<out>'
```

- عمليات التشغيل الدورية **تزايدية فقط** (توقف مبكر) — لا إعادة جلب كاملة (`scheduler.py:4-9`).
- يستخدم المقتطف مسارات مطلقة مقتبسة لأن دليل عمل cron و`PATH` غير متوقعين (`scheduler.py:63-75`).
- قم بتثبيته باستخدام `crontab -e` واضبط الوقت حسب الرغبة؛ وزع حسابات متعددة على فتحات مختلفة.
- شبكة أمان اختيارية: أضف مسحًا يدويًا أسبوعيًا أو شهريًا باستخدام `pplx-export batch --account alice --full` (انظر [incremental-sync.md](incremental-sync.md)).

<a id="see-also" data-pplx-source-anchor="true"></a>
## انظر أيضًا

- [incremental-sync.md](incremental-sync.md) — ما يصدره كل تشغيل مجدول بالضبط
- [pplx-export.md](pplx-export.md) — `--delay-min` / `--delay-max` وخيارات الأوامر الأخرى
- [troubleshooting.md](troubleshooting.md) — ما يجب فعله بعد إلغاء فشل المصادقة السريع
- [../architecture/rate-limiting-errors.md](../architecture/rate-limiting-errors.md) — التصنيف الكامل للأخطاء
- [../reference/api/api-responses-errors.md](../reference/api/api-responses-errors.md) — دلالات الأخطاء من جانب المنصة (`ENTRY_EXPIRED`, `ENTRY_DELETED`, Cloudflare)
- [../reference/api/api-authentication.md](../reference/api/api-authentication.md) — ملفات تعريف الارتباط وتبديل الحسابات المتعددة
