---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/configuration.md"
translation_source_sha256: "0c5f1be9b103913deee332caa4397a3dc356027148beac491834f6791f3b73db"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="configuration" data-pplx-source-anchor="true"></a>
# التكوين

pplx-export يحتفظ ببيانات هويتك — سجل الحسابات (أسماء العرض، رسائل البريد الإلكتروني لتسجيل الدخول، معرفات المستخدمين) ومساحة BOT — في ملف TOML على مستوى المستخدم يقع خارج المستودع. تغطي هذه الصفحة مكان وجود هذا الملف، كل حقل يقبله، ما يحدث عندما يكون مفقودًا، وكيف يدير السجل معالجة ملفات تعريف الارتباط متعددة الحسابات.

<a id="why-the-config-lives-outside-the-repo" data-pplx-source-anchor="true"></a>
## لماذا يقع التكوين خارج المستودع

سجل الحسابات ومساحة BOT هما بيانات شخصية و**لا يتم إيداعهما أبدًا** في المستودع (`pplx_export/config.py:7-12`). يشحن المستودع فقط قالبًا نائبًا، `config.example.toml`؛ قيمك الحقيقية تذهب إلى نسخة خاصة. كل شيء آخر تحتاجه الأداة — نطاق الموقع، عناوين URL لواجهة API، جذر الأرشيف الافتراضي — هو ثابت كود (`pplx_export/config.py:50-58`)، وليس تكوين مستخدم.

يحمل TOML بيانات الهوية فقط. اختيار مصدر ملفات تعريف الارتباط والنقل هما علامات CLI لكل استدعاء، وليسا حقول تكوين — انظر [علامات CLI، وليست حقول تكوين](#cli-flags-not-config-fields) أدناه.

<a id="location-and-load-priority" data-pplx-source-anchor="true"></a>
## الموقع وأولوية التحميل

`configure()` (`pplx_export/config.py:113`) يحل مسار التكوين بهذه الأولوية (`pplx_export/config.py:95-110`):

| الأولوية | المصدر | يُعتبر صريحًا |
|---|---|---|
| 1 | علامة CLI `--config PATH` | نعم |
| 2 | متغير البيئة `PPLX_EXPORT_CONFIG` | نعم |
| 3 | `~/.config/pplx-export/config.toml` (المسار الافتراضي) | لا |

"صريح" مهم لسلوك الخطأ عندما يكون الملف مفقودًا — انظر [الوضع المنخفض](#missing-config-degraded-mode). كلا الإدخالين من CLI يعيدان تحميل التكوين في الوضع الصارم بعد تحليل الوسائط (`pplx_export/cli.py:223`، `pplx_export/ask_cli.py:278`)؛ تحميل وقت الاستيراد (`pplx_export/config.py:174-179`) متسامح مع الأخطاء، لذا فإن استيراد الحزمة لا يفشل أبدًا بسبب ملف مفقود.

<a id="creating-your-config" data-pplx-source-anchor="true"></a>
## إنشاء التكوين الخاص بك

!!! تلميح "بديل تلقائي"
    يمكن لـ `pplx-export init` إنشاء هذا الملف تلقائيًا — يكتشف الحسابات المسجلة الدخول من ملفات تعريف الارتباط في متصفحك ويكتب TOML بأذونات 0600. انظر [pplx-export → init](pplx-export.md#init).

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml
```

ثم حرر النسخة. يستخدم القالب عناصر نائبة بحتة — انسخ الهيكل، واستبدل كل قيمة:

```toml
# Default account used when --account is not given (a key of [accounts.<name>] below)
default_account = "alice"

# Account registry: key = account username (the username in thread URLs / library)
[accounts.alice]
# Full display name: used for archive directory naming (web_archive/<display name>/…)
display_name = "Alice Example"
# Login email: verifies cookie ownership
email = "alice@example.com"
# Account uid (required for thread-viewed telemetry)
user_id = "00000000-0000-4000-8000-0000000000aa"

[accounts.bob]
display_name = "Bob Example"
email = "bob@example.com"
user_id = "00000000-0000-4000-8000-0000000000bb"

# BOT space: where threads created by pplx-ask are collected after completion
[bot_space]
uuid = "00000000-0000-4000-8000-0000000000b0"
slug = "bot-EXAMPLE"
```

نمط العنصر النائب: `alice`/`bob` هما أسماء مستخدمين للحسابات وهمية، تستخدم رسائل البريد الإلكتروني `example.com`، وتستخدم UUIDs نموذج الأصفار الكاملة `00000000-0000-4000-8000-…`. في ملفك الحقيقي، **يجب أن يكون مفتاح الجدول هو اسم المستخدم الفعلي للحساب** كما يظهر في عناوين URL للموضوعات ومكتبتك.

!!! تحذير "احتفظ به خاصًا"
    يحتوي التكوين الحقيقي على بيانات شخصية (رسائل بريد إلكتروني، معرفات مستخدمين). الإذن الموصى به هو `0o600`؛ لا تقم أبدًا بإيداعه في أي مستودع git (`config.example.toml:4-6`).

<a id="field-reference" data-pplx-source-anchor="true"></a>
## مرجع الحقول

<a id="top-level" data-pplx-source-anchor="true"></a>
### المستوى الأعلى

| الحقل | النوع | المعنى |
|---|---|---|
| `default_account` | سلسلة نصية | مفتاح جدول `[accounts.<name>]` واحد، يُستخدم عندما لا يتم تقديم `--account` (`pplx_export/commands/common.py:84-85`). فارغ/مفقود = الوضع المنخفض. |
| `archive_root` | سلسلة نصية | اختياري. جذر إخراج الأرشيف المستخدم كاحتياطي لـ `--out`، بحيث يمكن للأوامر اليومية حذف `--out`. الأولوية: `--out` > `archive_root` > `./web_archive` (`pplx_export/config.py`، محمل في `ARCHIVE_ROOT`؛ تم حله في `cli.py` / `ask_cli.py`). يتم توسيع `~`. |
| `[models]` (جدول) | جدول | **مدار تلقائيًا، غير مكتوب يدويًا.** كتالوج نماذج قابل للتحديث مكتوب بواسطة `pplx-ask models --refresh` ومُبذر بواسطة `pplx-export init`؛ يتجاوز الخط الأساسي المثبت في `pplx_export/sites/perplexity/platform.py`. المفاتيح: `last_refreshed` (UTC)، `source_version`، `auto_refresh` (منطقي)، `mode_defaults`، `council_defaults`، `search_models`، و `[models.catalog]` كامل (`id → {label, provider, mode}`). تقرأه الطلبات (مع خط الأساس `platform.py` كاحتياطي)؛ مدة صلاحية TTL لمدة 7 أيام تطبع تذكيرًا بالتحديث، أو يتم التحديث تلقائيًا عندما `auto_refresh = true`. الكتابة ذهابًا وإيابًا تحافظ على جداولك الأخرى وتعليقاتك (عبر تبعية وقت التشغيل `tomlkit`) وتبقى `0600`. |

### `[accounts.<name>]`

جدول واحد لكل حساب؛ `<name>` هو اسم المستخدم للحساب. يتم تحميل السجل في ثلاثة قواميس مفهرسة باسم المستخدم: `ACCOUNT_DISPLAY_NAMES`، `ACCOUNT_EMAIL`، `ACCOUNT_UID` (`pplx_export/config.py:65-75`).

| الحقل | النوع | مطلوب | المعنى |
|---|---|---|---|
| `display_name` | سلسلة نصية | لا | اسم العرض الكامل، يُستخدم لتسمية دليل الأرشيف (`web_archive/<display name>/…`)؛ يتراجع إلى اسم المستخدم عند الحذف. انظر [تخطيط الأرشيف](archive-layout.md). |
| `email` | سلسلة نصية | موصى به | البريد الإلكتروني لتسجيل الدخول. يتحقق النقل من ملكية ملف تعريف الارتباط ضده، مما يمنع "تصدير للحساب B يحمل جلسة الحساب A" (`pplx_export/config.py:69-72`). عند عدم التطابق، تقوم الأداة بتعداد رموز الجلسة لكل حساب في المتصفح وتتحول تلقائيًا — انظر [نموذج ملفات تعريف الارتباط متعددة الحسابات](#multi-account-cookie-model). |
| `user_id` | سلسلة نصية | لقياس عن بعد `pplx-ask` | معرف الحساب uid، مطلوب لقياس عن بعد لعرض الموضوع (`pplx_export/config.py:73-75`). اقرأه من `GET /api/auth/linked-accounts`، الذي يعيد `user_id` / `email` / `display_name` لكل حساب مسجل دخول — انظر [مصادقة API](../reference/api/api-authentication.md). |

### `[bot_space]`

مساحة BOT هي نقطة التجميع للموضوعات التي تم إنشاؤها بواسطة `pplx-ask` بعد اكتمالها (`pplx_export/config.py:76-79`). أنشئ المساحة نفسها باستخدام `pplx-ask space-create` (انظر [pplx-ask](pplx-ask.md))، ثم سجلها هنا.

| الحقل | النوع | المعنى |
|---|---|---|
| `uuid` | سلسلة نصية | UUID المساحة. ينقل `pplx-ask` الموضوعات المكتملة إلى هنا (`pplx_export/ask_cli.py:156-158`)؛ عندما يكون فارغًا، يتم تخطي خطوة النقل. |
| `slug` | سلسلة نصية | جزء slug من عنوان URL للمساحة. يتم تحميله في `BOT_SPACE_SLUG` (`pplx_export/config.py:79`)؛ لا يقرأه CLI وقت التشغيل — تستهلكه أداة صيانة النماذج الاختبارية، وتبني منه زوج استبدال الهوية (`tests/scrub_fixtures.py:446-447`). |

<a id="cli-flags-not-config-fields" data-pplx-source-anchor="true"></a>
### علامات CLI، وليست حقول تكوين

لا يحتوي TOML على أي إعدادات نقل أو ملفات تعريف ارتباط. يتم اختيارها لكل استدعاء:

| الشأن | أين يتم تعيينه |
|---|---|
| مسار ملف التكوين | `--config PATH`، أو `PPLX_EXPORT_CONFIG` |
| مصدر ملفات تعريف الارتباط | `--cookies-from BROWSER` / `--cookies FILE` |
| النقل | `--transport cookie\|webbridge` (`pplx-export` فقط؛ الافتراضي `cookie`) |
| تخطي فحص الحساب عند بدء التشغيل | `--skip-auth-check` (كلا الإدخالين) — انظر [نموذج ملفات تعريف الارتباط متعددة الحسابات](#multi-account-cookie-model) |

انظر [pplx-export](pplx-export.md) للحصول على مرجع العلامات الكامل.

<a id="missing-config-degraded-mode" data-pplx-source-anchor="true"></a>
## التكوين المفقود: الوضع المنخفض

عندما لا يتم تحميل شيء، تبقى سجلات مستوى الوحدة فارغة ويكون `LOADED_CONFIG_PATH` هو `None` (`pplx_export/config.py:83-85`). السلوك حسب السيناريو (`resolve_cli_account`، `pplx_export/commands/common.py:51-90`):

| السيناريو | السلوك |
|---|---|
| لا يوجد تكوين في المسار الافتراضي، `--account` غير معطى | الوضع المنخفض: يتم تسجيل تحذير وتعمل الأوامر مع حساب نائب (`username='default'`)؛ يتم تخطي فحص ملكية البريد الإلكتروني. الأوامر اليومية غير المتصلة بالإنترنت غير متأثرة (`pplx_export/commands/common.py:86-90`). |
| لا يوجد تكوين، `--account` صريح | `SystemExit` يسمي ترتيب البحث ويشير إلى `config.example.toml` (`pplx_export/commands/common.py:67-74`). |
| تم تحميل التكوين، `--account` غير مسجل | `SystemExit` يسمي الملف المحمل، ويطلب منك إضافة `[accounts.<name>]` (`pplx_export/commands/common.py:77-82`). |
| المسار الصريح (`--config` / متغير البيئة) غير موجود | `ConfigError` في الوضع الصارم (`pplx_export/config.py:140-146`). |
| الملف موجود لكن فشل تحليله | دائمًا `ConfigError` — يجب ألا يتدهور تكوين تالف بصمت (`pplx_export/config.py:147-150`). |
| `--account` محذوف، تم تحميل التكوين | يتم استخدام `default_account` (`pplx_export/commands/common.py:84-85`). |

ما تغطيه "الأوامر غير المتصلة بالإنترنت" وكيف تتفاعل عمليات التشغيل المنخفضة مع الأرشيف مفصل في [العمليات غير المتصلة بالإنترنت](../architecture/offline-operations.md).

<a id="multi-account-cookie-model" data-pplx-source-anchor="true"></a>
## نموذج ملفات تعريف الارتباط متعددة الحسابات

مع تسجيل عدة حسابات دخول في نفس المتصفح، يحمل المخزن ملف تعريف ارتباط جلسة **واحد لكل حساب**، ويخبر حقل `email` في التكوين الأداة بأي منها تحتاج:

- كل حساب مسجل دخول لديه ملف تعريف ارتباط `__Secure-pplx.session.<uid>` (`ACCOUNT_SESSION_PREFIX`، `pplx_export/core/cookies/loaders.py:171`)؛ اللاحقة `<uid>` هي `user_id` للحساب.
- الحساب **النشط** هو أي رمز موجود حاليًا في `__Secure-next-auth.session-token` (`ACTIVE_SESSION_COOKIE`، `pplx_export/core/cookies/loaders.py:172`). تبديل الحسابات = كتابة قيمة ملف تعريف الارتباط لكل حساب للحساب الهدف في ذلك الملف — لا حاجة لواجهة مستخدم المتصفح (`pplx_export/core/cookies/loaders.py:180-187`).
- عند بدء التشغيل، يتحقق النقل من `GET https://www.perplexity.ai/api/auth/session` ويقارن البريد الإلكتروني المعاد بـ `accounts.<name>.email` (`pplx_export/commands/common.py:126-130`).
- عند عدم التطابق، يقوم `_try_switch_account` (`pplx_export/commands/common.py:190-215`) بتعداد كل رمز حساب في المتصفح عبر `list_account_tokens` (`pplx_export/core/cookies/loaders.py:175-206`، مفضلاً الإدخالات على النطاق الفرعي `www.`)، ويجرب كل واحد في `__Secure-next-auth.session-token`، ويعيد بناء النقل عند أول تطابق.
- إذا لم يتطابق أي رمز، يخرج الأمر مسميًا كلا البريدين الإلكترونيين ويطلب منك تسجيل دخول الحساب الهدف في المتصفح أولاً (`pplx_export/commands/common.py:142-145`) — انظر [استكشاف الأخطاء وإصلاحها](troubleshooting.md).
- حساب بدون `email` مسجل يتم متابعته دون فحص، مع تحذير يطلب منك تأكيد تسجيل دخول المتصفح بنفسك (`pplx_export/commands/common.py:146-149`).

للحصول على تدفق التبديل الكامل ودلالات نقطة نهاية الجلسة، انظر [الأسئلة والحسابات](../architecture/ask-and-accounts.md) و[مصادقة API](../reference/api/api-authentication.md).

**تخطي الفحص (`--skip-auth-check`).** يستبدل فحص جلسة بدء التشغيل أعلاه
بضع ثوانٍ — أحيانًا دقائق على شبكة ضعيفة — بحارس ملكية "الحساب B
المستخدم كحساب A". عندما تعلم أن المتصفح قد سجل دخول إلى
الحساب الصحيح، يتخطى `--skip-auth-check` (مشترك بواسطة `pplx-export` و `pplx-ask`)
ذلك الفحص تمامًا ويذهب مباشرة إلى العمل (`pplx_export/commands/common.py`،
`make_transport`):

- لا يوجد `GET /api/auth/session` عند بدء التشغيل، لذا لم يعد الشبكة غير المستقرة تنتج
  انتظارًا طويلًا صامتًا (يتم الآن نبض القلب) قبل أول طلب حقيقي.
- تثق الأداة في أي حساب مسجل دخول حاليًا؛ لا يتم تشغيل فحص ملكية
  البريد الإلكتروني المسبق والتبديل التلقائي متعدد الحسابات أعلاه.
- **شبكة أمان مؤجلة**: في `batch`، بمجرد تراكم أخطاء التصدير العامة
  (ثلاثة إخفاقات)، يتم تشغيل فحص حساب لمرة واحدة ويحذرك بما وجده —
  ملف تعريف الارتباط منتهي الصلاحية، الحساب لا يتطابق مع الهدف، أو الحساب
  سليم (لذا الأخطاء هي شبكة / حد معدل، وليست مصادقة)
  (`pplx_export/commands/common.py`، `report_account_status`؛
  `pplx_export/commands/batch_cmd.py`).
- **المقايضة**: يكتشف الفحص المؤجل ملف تعريف ارتباط منتهي الصلاحية، لكنه لا يستطيع
  اكتشاف حساب *خاطئ ولكنه صالح* يصدر بدون خطأ — مع
  `--skip-auth-check` تتحمل المسؤولية بأن الحساب المسجل دخول هو
  الحساب المقصود.

استخدمه لعمليات تشغيل سريعة غير مراقبة على تسجيل دخول معروف الجودة؛ احذفه عندما تعتمد
على حارس الملكية المسبق أو التبديل التلقائي للحساب.

<a id="cookie-cache" data-pplx-source-anchor="true"></a>
## ذاكرة التخزين المؤقت لملفات تعريف الارتباط

بعد التحقق الناجح، يتم تخزين ملفات تعريف الارتباط التي تم حلها مؤقتًا بحيث تتخطى عمليات التشغيل اللاحقة المتصفح:

| الخاصية | القيمة |
|---|---|
| المسار | `<archive root>/index/.cookies.json` — يتبع `--out` (`pplx_export/commands/common.py:111`) |
| النضارة | 12 ساعة (`CACHE_MAX_AGE_S = 12 * 3600`، `pplx_export/core/cookies/cache.py:22`)؛ يتم التعامل مع ذاكرة تخزين مؤقت قديمة أو تالفة على أنها غير موجودة |
| المحتويات | `fetched_at`، `source`، `account_email`، `cookies` (`pplx_export/core/cookies/cache.py:62-66`) |
| الكتابة | ذرية: يتم إنشاء ملف مؤقت بالوضع `0o600`، ثم `os.replace` (`pplx_export/core/cookies/cache.py:49-67`) |
| Git | مغطى بـ `.gitignore` (`**/index/.cookies.json`) |

ترتيب حل ملفات تعريف الارتباط (`cookies.resolve`، `pplx_export/core/cookies/loaders.py:270-302`): `--cookies-from` صريح → ملف `--cookies` صريح → ذاكرة تخزين مؤقت جديدة → اكتشاف تلقائي للمتصفحات (edge → chrome → firefox → safari). يتم تحديث ذاكرة التخزين المؤقت بعد كل تحقق ناجح من الحساب (`pplx_export/commands/common.py:150`).

<a id="protecting-your-files" data-pplx-source-anchor="true"></a>
## حماية ملفاتك

- `chmod 600` ملف `config.toml` الخاص بك — يحتوي على بيانات شخصية (رسائل بريد إلكتروني، معرفات مستخدمين).
- يتم بالفعل كتابة ذاكرة التخزين المؤقت لملفات تعريف الارتباط بالوضع `0o600` بواسطة الأداة؛ ملفات تعريف ارتباط الجلسة هي بيانات اعتماد مكافئة لتسجيل الدخول.
- إذا قمت بإنشاء ملف ملفات تعريف ارتباط يدويًا لـ `--cookies`، فطبق `chmod 600` عليه أيضًا.

<a id="when-authentication-fails" data-pplx-source-anchor="true"></a>
## عندما تفشل المصادقة

ملفات تعريف ارتباط منتهية الصلاحية، حساب لا يمكن للتبديل التلقائي العثور عليه، أخطاء أذونات سلسلة مفاتيح المتصفح، وغيرها من إخفاقات المصادقة مغطاة في [استكشاف الأخطاء وإصلاحها](troubleshooting.md).
