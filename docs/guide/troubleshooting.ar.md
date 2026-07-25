---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/troubleshooting.md"
translation_source_sha256: "99dee1bd48f525fcf72fcfd09992043114e918fd4ce2870f0586fc2937c70d62"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="troubleshooting" data-pplx-source-anchor="true"></a>
# استكشاف الأخطاء وإصلاحها

تنسيق الأسئلة الشائعة: كل إدخال هو **مشكلة → سبب → حل**. للحصول على مرجع كامل لدلالات الأخطاء (رموز الحالة، الحالات النهائية، سياسة إعادة المحاولة)، راجع [الاستجابات والأخطاء](../reference/api/api-responses-errors.md) و[تحديد المعدل والأخطاء](../architecture/rate-limiting-errors.md).

<a id="bare-requests-to-the-api-get-a-cloudflare-403" data-pplx-source-anchor="true"></a>
## الطلبات المباشرة لواجهة API تحصل على Cloudflare 403

**المشكلة**: نص برمجي يدوي `curl` / سكريبت ضد نقاط نهاية REST الخاصة بـ `www.perplexity.ai` يُرجع 403 مع صفحة تحدي Cloudflare — حتى مع نسخ ملفات تعريف الارتباط من المتصفح — بينما تعمل نفس نقاط النهاية من خلال الأداة.

**السبب**: Cloudflare موجود أمام الموقع، و `cf_clearance` / `__cf_bm` مرتبطان ببصمة TLS الخاصة بالمتصفح. بصمة العميل المباشر لا تتطابق، لذلك يتم تشغيل التحدي. تمر الأداة لأنها تستخدم Python `urllib` مع ملفات تعريف الارتباط المستوردة من المتصفح و `User-Agent` لسطح مكتب Chrome (`pplx_export/core/http/cookie_transport.py:29`). يمكن لـ Cloudflare أيضًا إرجاع 403 تحت التحكم في المعدل — في هذه الحالة، يحمل الاستجابة نفس شكل التحدي.

**الحل**:

- لا تتجاوز نقل الأداة؛ قم بتشغيل طلبك من خلال `pplx-export` / `pplx-ask` بدلاً من النصوص البرمجية المخصصة.
- داخل الأداة، يتم تصنيف استجابة 200 مع نص غير JSON (النص البيني لـ Cloudflare) كخطأ في النقل، وليس بيانات (`pplx_export/core/http/cookie_transport.py:133`).
- إذا بدأت 403 في الظهور داخل الأداة، أبطئ (راجع [تحديد المعدل](rate-limiting.md)) وقم بتحديث ملفات تعريف الارتباط؛ التحدي المستمر يعني إعادة تسجيل الدخول في المتصفح.
- انتبه إلى وجهي 403: تحدي التحكم في المخاطر من Cloudflare (يختفي بمجرد أن تبطئ) مقابل 403 على مستوى API (ملف تعريف ارتباط منتهي الصلاحية — يتم رفعه فورًا دون تراجع؛ راجع القسم التالي). صفحة التصميم ترسم الأخير ([rate-limiting-errors.md](../architecture/rate-limiting-errors.md)).

خلفية: [مصادقة API](../reference/api/api-authentication.md).

<a id="401-errors-expired-cookies" data-pplx-source-anchor="true"></a>
## أخطاء 401 / ملفات تعريف الارتباط منتهية الصلاحية

**المشكلة**: تفشل الأوامر مع خطأ مصادقة — `AuthTransportError: 鉴权失败 401` من `pplx-export`، أو `pplx-ask ask` يخرج مع تلميح HTTP 401/403 لتحديث ملف تعريف الارتباط.

**السبب**: انتهت صلاحية جلسة ملف تعريف الارتباط أو تم إبطالها. يتم التعامل مع `401`/`403` كفشل في المصادقة ويتم رفعها فورًا — لا تراجع، لأن التراجع لا يمكنه إصلاح جلسة ميتة ذاتيًا (`pplx_export/core/http/cookie_transport.py:82`; `pplx_export/core/errors.py:68`). بالإضافة إلى ذلك، يفشل `batch` بسرعة بعد 3 حالات فشل متتالية في المصادقة حتى لا يحرق ملف تعريف الارتباط الميت قائمة الانتظار.

**الحل**:

1. أعد تسجيل الدخول (أو أعد فتح الموقع) في المتصفح حتى يتم تجديد ملفات تعريف ارتباط الجلسة.
2. قم بتحديث ذاكرة التخزين المؤقت لملفات تعريف الارتباط الخاصة بالأداة. يتم إعادة استخدام ذاكرة التخزين المؤقت في `<out>/index/.cookies.json` خلال نافذة نضارة مدتها 12 ساعة (`pplx_export/core/cookies/cache.py:22`)، لذلك بعد إعادة تسجيل الدخول إما:
   - قم بتشغيل مرة واحدة مع `--cookies-from <browser>` لفرض استيراد متصفح جديد، أو
   - احذف `<out>/index/.cookies.json` واترك التشغيل التالي يعيد الاستيراد تلقائيًا.
3. كل تشغيل يتم التحقق منه بنجاح يعيد حفظ ذاكرة التخزين المؤقت (`pplx_export/commands/common.py:150`)، لذلك تبقى عمليات التشغيل اليومية جديدة من تلقاء نفسها.

تفاصيل الإعداد: [بدء الاستخدام](getting-started.md) · [التكوين](configuration.md).

<a id="linux-cookie-decryption" data-pplx-source-anchor="true"></a>
## فك تشفير ملفات تعريف الارتباط في Linux

**المشكلة**: على Linux، لا يستطيع الكشف التلقائي (أو `--cookies-from chrome` وشركاه) قراءة مخزن ملفات تعريف الارتباط الخاص بالمتصفح حتى إذا كان المتصفح مسجلاً للدخول.

**الآلية**: تقوم متصفحات عائلة Chromium على Linux بتشفير قاعدة بيانات ملفات تعريف الارتباط بمفتاح محفوظ في سلسلة مفاتيح نظام التشغيل، ويتم قراءته في وقت التشغيل عبر واجهة برمجة تطبيقات Secret Service D-Bus. يتحدث `browser_cookie3` مع D-Bus عبر `jeepney` بلغة Python النقية — المثبتة بالفعل مع الأداة على Linux، لا حاجة لإعداد أي شيء إضافي — ويعود إلى كلمة مرور `peanuts` القديمة عندما لا تستجيب سلسلة المفاتيح، والتي تقوم فقط بفك تشفير ملفات تعريف الارتباط التي كتبها Chrome أيضًا بدون سلسلة مفاتيح. لا يحتاج Firefox إلى أي من هذا: `cookies.sqlite` الخاص به غير مشفر.

**المصفوفة**:

| الطبقة | الحالة | ما يحدث |
|---|---|---|
| المتصفح | Firefox | بدون احتكاك — `cookies.sqlite` غير مشفر |
| المتصفح | Chromium + سلسلة مفاتيح قابلة للوصول | يعمل — يتم جلب المفتاح عبر Secret Service |
| المتصفح | Chromium + بدون سلسلة مفاتيح | مسار `peanuts` — يعمل فقط إذا كتب Chrome أيضًا بدون سلسلة مفاتيح |
| طريقة التثبيت | حزمة أصلية | يتم الكشف تلقائيًا (المسارات المضمنة في browser_cookie3) |
| طريقة التثبيت | snap / flatpak | يتم الكشف تلقائيًا — يغطي سجل الملفات الشخصية المضمنة الملفات الشخصية تحت `~/snap/<name>/...` أو `~/.var/app/<app-id>/...` (`pplx_export/core/cookies/profiles.py:37-67`) |
| بيئة سطح المكتب | GNOME | يعمل عادةً خارج الصندوق (gnome-keyring) |
| بيئة سطح المكتب | KDE | قم بتمكين **استخدام KWallet لواجهة Secret Service** في إعدادات KWallet |
| بيئة سطح المكتب | بدون رأس / بسيط | لا توجد حافلة جلسة D-Bus → مسار `peanuts` |
| عائلة التوزيعة | Debian / Ubuntu | قم بتثبيت `libsecret-1-0` + `gnome-keyring` |
| عائلة التوزيعة | Fedora / RHEL | قم بتثبيت `libsecret` + `gnome-keyring`؛ غالبًا ما تفتقر التثبيتات البسيطة / الخادم إلى سلسلة مفاتيح تمامًا — الفشل الأكثر شيوعًا |
| عائلة التوزيعة | Arch | نفس الآلية، تختلف أسماء الحزم فقط |

لا تحتاج تثبيتات الحماية إلى علامات إضافية: يتم فحص المسار الأصلي أولاً، ثم قواعد بيانات ملفات تعريف الارتباط snap/flatpak الخاصة بالسجل عبر `cookie_file=` صريح (`pplx_export/core/cookies/loaders.py:89-101`).

**السيناريو → القناة الموصى بها**:

| السيناريو | القناة الموصى بها |
|---|---|
| Firefox مثبت | `--cookies-from firefox` — بدون احتكاك |
| سطح مكتب GNOME / KDE | الكشف التلقائي يعمل فقط |
| متصفح snap / flatpak | الكشف التلقائي — يغطيه السجل؛ وإلا `--cookies FILE` تم تصديره عبر إضافة متصفح |
| خادم بدون رأس | `--cookies FILE` — الحل الاحتياطي الشامل؛ `--transport webbridge` كملاذ أخير |

<a id="an-export-ran-under-the-wrong-account-multi-account" data-pplx-source-anchor="true"></a>
## تم تشغيل تصدير تحت حساب خاطئ (حسابات متعددة)

**المشكلة**: تم جلب سلاسل المحادثات المؤرشفة بجلسة الحساب الخاطئ — على سبيل المثال، سحب تشغيل `--account alice` بيانات كـ `bob`، أو يظهر الأرشيف سلاسل محادثات لا تنتمي إلى الحساب المقصود.

**السبب**: مع تسجيل العديد من الحسابات في نفس المتصفح، قد ينتمي رمز الجلسة النشط (`__Secure-next-auth.session-token`) إلى حساب مختلف عن الذي استهدفته. إذا لم يتم تسجيل `email` للحساب المستهدف في تكوين مستوى المستخدم، لا يمكن للأداة اكتشاف ذلك وتسجل تحذيرًا فقط.

**كيف تمنع الأداة ذلك** (`pplx_export/commands/common.py:93`): عند بدء التشغيل، يستدعي النقل `GET /api/auth/session` ويقارن البريد الإلكتروني المباشر مع المسجل. عند عدم التطابق، يقوم تلقائيًا بتعداد ملفات تعريف ارتباط الجلسة لكل حساب في المتصفح (`__Secure-pplx.session.<user_id>`)، ويستبدل كل منها في الرمز النشط، ويختبر الجلسة حتى يتطابق البريد الإلكتروني الهدف (`pplx_export/commands/common.py:190`; `pplx_export/core/cookies/loaders.py:108`). إذا لم يتطابق أي رمز، يتم إحباط الأمر مع خطأ واضح — لا يستمر بصمت كحساب خاطئ.

**الحل**:

- سجل `email` لكل حساب تحت `[accounts.<name>]` (راجع [التكوين](configuration.md)) ومرر `--account` بشكل صريح.
- تحقق من سطر سجل بدء التشغيل `[auth] cookie 来源 …，当前账户: …` — يسمي البريد الإلكتروني للجلسة المباشرة قبل جلب أي شيء.
- لتدقيق أرشيف موجود، يحمل `thread.json` لكل سلسلة محادثات حقل `export_via` يسجل أي حساب قام بالتصدير (`pplx_export/sites/perplexity/fs_writer.py:229`). يستخدم `pplx-export sync-deleted` نفس الحقل لاختيار الحساب للتحقق عبر الإنترنت.

عمق الآلية: [مصادقة API](../reference/api/api-authentication.md) · [الأسئلة والحسابات](../architecture/ask-and-accounts.md).

<a id="config-file-not-found-degraded-mode" data-pplx-source-anchor="true"></a>
## "لم يتم العثور على ملف التكوين" — الوضع المنخفض

**المشكلة**: يقول تحذير بدء التشغيل أنه لم يتم العثور على ملف تكوين على مستوى المستخدم ويتم تشغيل الأمر في الوضع المنخفض؛ أو يفشل `--account alice` صريح مع خطأ يشير إلى `config.example.toml`.

**السبب**: لا يوجد ملف تكوين في أي من مواقع البحث الثلاثة — `--config PATH`، متغير البيئة `PPLX_EXPORT_CONFIG`، أو المسار الافتراضي `~/.config/pplx-export/config.toml` (`pplx_export/config.py:113`). حالتان مرتبطتان لكن متميزتان: **مسار تكوين محدد بشكل صريح** غير موجود يثير `ConfigError`؛ التكوين التالف (غير قابل للتحليل) يثير دائمًا `ConfigError` — التكوين المكسور لا ينخفض ​​بصمت أبدًا.

**تأثيرات الوضع المنخفض**:

- سجل الحساب فارغ، لذلك يتم تخطي التحقق من ملكية ملف تعريف الارتباط مع تحذير ويتم تشغيل الأوامر كحساب نائب `default` (`pplx_export/commands/common.py:51`). `--account` صريح يخطئ بدلاً من ذلك.
- يتخطى `pplx-ask ask` النقل التلقائي إلى مساحة BOT (يبقى `moved_to_bot` `false` في JSON النتيجة) ويحمل القياس عن بُعد معرف مستخدم فارغ؛ وإلا فإن السؤال والأرشفة يعملان.
- تهبط الأرشيفات تحت مجلد الحساب الاحتياطي المشتق من اسم المستخدم.

**الحل**: انسخ `config.example.toml` إلى `~/.config/pplx-export/config.toml`، املأ `[accounts.<name>]` (`display_name` / `email` / `user_id`)، `[bot_space]`، و `default_account` — راجع [التكوين](configuration.md).

<a id="entry_expired-vs-entry_deleted" data-pplx-source-anchor="true"></a>
## ENTRY_EXPIRED مقابل ENTRY_DELETED

**المشكلة**: الإبلاغ عن تصدير أو إعادة مزامنة سلسلة محادثات `ENTRY_EXPIRED` أو `ENTRY_DELETED`، ولا يمكن جلب سلسلة المحادثات مرة أخرى أبدًا.

**السبب**: يصل كلاهما كـ HTTP 400 من `GET /rest/thread/<uuid>` مع رموز خطأ مختلفة، وكلاهما نهائي — سلسلة المحادثات لم تعد موجودة على المنصة:

| الرمز | المعنى | تعيين الأداة | الحالة النهائية |
|---|---|---|---|
| `ENTRY_EXPIRED` | قامت المنصة بتنظيف سلسلة المحادثات (احتفاظ ~3 أشهر) | `EntryExpiredError` (`pplx_export/core/errors.py:24`) | `expired` |
| `ENTRY_DELETED` | تم حذف سلسلة المحادثات بنشاط بواسطة المستخدم / الجانب البعيد (التأثير النهائي لـ `DELETE /rest/thread/delete_thread_by_entry_uuid`) | `EntryDeletedError`، فئة فرعية من `EntryExpiredError` (`pplx_export/core/errors.py:30`) | `deleted` |

**ما يعنيه ذلك لأرشيفك**:

- لا يتم إعادة محاولة أي من الحالتين أبدًا — ليس عن طريق المزامنة المتزايدة، ولا مع `--force`. العلامة النهائية موجودة في `<out>/index/batch_state.json`.
- **لا يتم حذف أرشيفك المحلي أو نقله أبدًا** بواسطة الأداة — نسخة المستودع هي النسخة الاحتياطية. يسجل أمر التصدير الحالة النهائية ويخرج بأمان (`pplx_export/commands/export_cmd.py:51`).
- نظرًا لأن علاقة الفئة الفرعية متعمدة، فإن مسارات التعليمات البرمجية التي تعرف فقط `EntryExpiredError` لا تزال تعامل `ENTRY_DELETED` كنهائي؛ المسارات الواعية (دفعة / تصدير / مزامنة محذوفة / ملء خلفي لوضع البحث) تصنفها بدقة كـ `deleted`.
- الخلاصة العملية: قم بالتصدير في الوقت المناسب. بعد التنظيف لمدة ~3 أشهر، تنتهي صلاحية روابط مصدر القطعة / التقرير أيضًا بشكل لا رجعة فيه.

ذات صلة: [المزامنة المتزايدة](incremental-sync.md) · [الاستجابات والأخطاء](../reference/api/api-responses-errors.md).

<a id="assets-that-cannot-be-downloaded-toolu_-handles" data-pplx-source-anchor="true"></a>
## الأصول التي لا يمكن تنزيلها (معالجات `toolu_`)

**المشكلة**: بعض الإدخالات في `assets/assets_manifest.json` تحتوي على إصدارات تم وضع علامة عليها `"no_download_channel": true`، ولا يوجد ملف مقابل تحت `assets/files/`.

**السبب**: معالجات مساحة العمل السحابية المسبوقة بـ `toolu_` (DOC_FILE / CODE_FILE / UNKNOWN بدون نموذج URL) ليس لديها قناة تنزيل API: يُرجع `GET /rest/assets/<asset_uuid>/data` 404 `ASSET_NOT_FOUND` لها، ويرفض `file-repository/download` معالجات `file:repo/...` (400). هذه **حدود معروفة لاكتمال الأرشيف**، وليس خطأ في التصدير. يميز `pplx-export assets-backfill` هذه الإصدارات `no_download_channel` ويتخطاها (`pplx_export/commands/assets_backfill_cmd.py:356`).

**الحل**:

- لا شيء لتنزيله اليوم — العلم هو السجل المتعمد للحدود.
- غالبًا ما يبقى المحتوى مضمنًا: يتم حفظ نص استخراج صفحة الوكيل الفرعي وحمولات الخطوة في JSON الخام لسلسلة المحادثات (`raw_entries.json` / `raw_blocks.json`) وفي `turns/` المقدم — تحقق هناك أولاً.
- يتم تتبع `file-repository/list-files` كمسار إنقاذ محتمل في المستقبل؛ راجع [خريطة طريق اكتشاف API](../reference/api/api-discovery-roadmap.md).

تخطيط البيان: [تخطيط الأرشيف](archive-layout.md).

<a id="where-are-the-logs" data-pplx-source-anchor="true"></a>
## أين توجد السجلات؟

**وحدة التحكم**: تقدم مستوى INFO افتراضيًا؛ `-v` / `--verbose` يتحول إلى DEBUG (تتبع الطلب، القرارات الداخلية)؛ يتم عرض التحذيرات والأخطاء دائمًا.

**ملف**: مرر `--log-file` لالتقاط تدفق DEBUG الكامل (`pplx_export/core/logging.py:45`):

- `--log-file` بدون قيمة يهبط في `<out>/index/logs/<cmd>-<timestamp>.log` (`pplx_export/commands/common.py:218`) — على سبيل المثال `pplx-ask-ask-20260723-120000.log`.
- `--log-file PATH` يكتب إلى المسار المحدد.

**ملفات الحالة الأخرى المفيدة للتشخيص** (تحت `<out>/index/`):

| الملف | المحتوى |
|---|---|
| `.cookies.json` | ذاكرة تخزين مؤقت لملفات تعريف الارتباط (نضارة 12 ساعة؛ مكتوبة بشكل ذري مع 0o600 — إنها بيانات اعتماد مكافئة لتسجيل الدخول، حافظ عليها خاصة) |
| `batch_state.json` | حالة تصدير لكل سلسلة محادثات، بما في ذلك علامات `expired` / `deleted` النهائية |
| `answer_variants_log.jsonl` | سجل متغير إعادة كتابة الإجابة |
| `library_*.json` | لقطات فهرس المكتبة لكل حساب |

<a id="see-also" data-pplx-source-anchor="true"></a>
## انظر أيضًا

- [بدء الاستخدام](getting-started.md) — الإعداد الأولي واستيراد ملفات تعريف الارتباط
- [التكوين](configuration.md) — الحسابات، مساحة BOT، الوضع المنخفض
- [pplx-ask](pplx-ask.md) — واجهة سطر الأوامر للاستعلام التفاعلي
- [pplx-export](pplx-export.md) — واجهة سطر الأوامر للأرشفة
- [تحديد المعدل](rate-limiting.md) — سياسة السرعة والتراجع
