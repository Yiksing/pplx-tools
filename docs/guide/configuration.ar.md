---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/configuration.md"
translation_source_sha256: "39f85a86f94a3b326e9d3b9a74e9452a379a4745667b57c124c9512bfd1d9755"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="configuration" data-pplx-source-anchor="true"></a>
# الإعدادات

pplx-export يحتفظ ببيانات هويتك — سجل الحسابات (أسماء العرض، رسائل البريد الإلكتروني لتسجيل الدخول، معرفات المستخدمين) ومساحة BOT — في ملف TOML على مستوى المستخدم يقع خارج المستودع. تغطي هذه الصفحة مكان وجود هذا الملف، كل حقل يقبله، ما يحدث عندما يكون مفقودًا، وكيف يقود السجل معالجة ملفات تعريف الارتباط متعددة الحسابات.

<a id="why-the-config-lives-outside-the-repo" data-pplx-source-anchor="true"></a>
## لماذا يقع الإعداد خارج المستودع

سجل الحسابات ومساحة BOT هما بيانات شخصية و**لا يتم إيداعهما أبدًا** في المستودع (`pplx_export/config.py:7-12`). يشحن المستودع فقط قالبًا نائبًا، `config.example.toml`؛ تذهب قيمك الحقيقية إلى نسخة خاصة. كل شيء آخر تحتاجه الأداة — نطاق الموقع، عناوين URL لواجهة API، جذر الأرشيف الافتراضي — هو ثابت كود (`pplx_export/config.py:50-58`)، وليس إعداد مستخدم.

يحمل TOML بيانات الهوية فقط. اختيار مصدر ملفات تعريف الارتباط والنقل هما علامات CLI لكل استدعاء، وليسا حقول إعداد — انظر [علامات CLI، وليس حقول إعداد](#cli-flags-not-config-fields) أدناه.

<a id="location-and-load-priority" data-pplx-source-anchor="true"></a>
## الموقع وأولوية التحميل

`configure()` (`pplx_export/config.py:113`) يحل مسار الإعداد بهذه الأولوية (`pplx_export/config.py:95-110`):

| الأولوية | المصدر | يُعتبر صريحًا |
|---|---|---|
| 1 | علامة CLI `--config PATH` | نعم |
| 2 | متغير البيئة `PPLX_EXPORT_CONFIG` | نعم |
| 3 | `~/.config/pplx-export/config.toml` (المسار الافتراضي) | لا |

"صريح" مهم لسلوك الخطأ عندما يكون الملف مفقودًا — انظر [الوضع المتدهور](#missing-config-degraded-mode). يعيد كلا إدخالي CLI تحميل الإعداد في الوضع الصارم بعد تحليل الوسائط (`pplx_export/cli.py:223`، `pplx_export/ask_cli.py:278`)؛ تحميل وقت الاستيراد (`pplx_export/config.py:174-179`) متسامح مع الأخطاء، لذا فإن استيراد الحزمة لا يفشل أبدًا بسبب ملف مفقود.

<a id="creating-your-config" data-pplx-source-anchor="true"></a>
## إنشاء الإعداد الخاص بك

!!! tip "بديل تلقائي"
    يمكن لـ `pplx-export init` إنشاء هذا الملف تلقائيًا — يكتشف الحسابات المسجلة الدخول من ملفات تعريف الارتباط في متصفحك ويكتب TOML بأذونات 0600. انظر [pplx-export → init](pplx-export.md#init).

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml
```

ثم قم بتحرير النسخة. يستخدم القالب عناصر نائبة خالصة — انسخ الهيكل، واستبدل كل قيمة:

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

نمط العنصر النائب: `alice`/`bob` هما أسماء مستخدمين للحسابات وهمية، تستخدم رسائل البريد الإلكتروني `example.com`، وتستخدم UUIDs نموذج الأصفار الكاملة `00000000-0000-4000-8000-…`. في ملفك الحقيقي، **يجب أن يكون مفتاح الجدول هو اسم مستخدم الحساب الفعلي** كما يظهر في عناوين URL للخيوط ومكتبتك.

!!! warning "احتفظ به خاصًا"
    يحتوي الإعداد الحقيقي على بيانات شخصية (رسائل بريد إلكتروني، معرفات مستخدمين). الإذن الموصى به هو `0o600`؛ لا تقم بإيداعه أبدًا في أي مستودع git (`config.example.toml:4-6`).

<a id="field-reference" data-pplx-source-anchor="true"></a>
## مرجع الحقول

<a id="top-level" data-pplx-source-anchor="true"></a>
### المستوى الأعلى

| الحقل | النوع | المعنى |
|---|---|---|
| `default_account` | string | مفتاح جدول `[accounts.<name>]` واحد، يُستخدم عندما لا يتم تقديم `--account` (`pplx_export/commands/common.py:84-85`). فارغ/مفقود = وضع متدهور. |

### `[accounts.<name>]`

جدول واحد لكل حساب؛ `<name>` هو اسم مستخدم الحساب. يتم تحميل السجل في ثلاثة قواميس مفتاحية باسم المستخدم: `ACCOUNT_DISPLAY_NAMES`، `ACCOUNT_EMAIL`، `ACCOUNT_UID` (`pplx_export/config.py:65-75`).

| الحقل | النوع | مطلوب | المعنى |
|---|---|---|---|
| `display_name` | string | لا | اسم العرض الكامل، يُستخدم لتسمية دليل الأرشيف (`web_archive/<display name>/…`)؛ يتراجع إلى اسم المستخدم عند الحذف. انظر [تخطيط الأرشيف](archive-layout.md). |
| `email` | string | موصى به | البريد الإلكتروني لتسجيل الدخول. يتحقق النقل من ملكية ملف تعريف الارتباط ضده، مما يمنع "تصدير للحساب B يحمل جلسة الحساب A" (`pplx_export/config.py:69-72`). عند عدم التطابق، تقوم الأداة بتعداد رموز جلسة كل حساب في المتصفح وتتحول تلقائيًا — انظر [نموذج ملفات تعريف الارتباط متعددة الحسابات](#multi-account-cookie-model). |
| `user_id` | string | لقياس عن بعد `pplx-ask` | معرف الحساب، مطلوب لقياس عن بعد عرض الخيط (`pplx_export/config.py:73-75`). اقرأه من `GET /api/auth/linked-accounts`، الذي يعيد `user_id` / `email` / `display_name` لكل حساب مسجل دخول — انظر [مصادقة API](../reference/api/api-authentication.md). |

### `[bot_space]`

مساحة BOT هي نقطة تجميع للخيوط التي تم إنشاؤها بواسطة `pplx-ask` بعد اكتمالها (`pplx_export/config.py:76-79`). أنشئ المساحة نفسها باستخدام `pplx-ask space-create` (انظر [pplx-ask](pplx-ask.md))، ثم سجلها هنا.

| الحقل | النوع | المعنى |
|---|---|---|
| `uuid` | string | UUID المساحة. ينقل `pplx-ask` الخيوط المنتهية إلى هنا (`pplx_export/ask_cli.py:156-158`)؛ عندما يكون فارغًا، يتم تخطي خطوة النقل. |
| `slug` | string | جزء عنوان URL الخاص بالمساحة. يتم تحميله في `BOT_SPACE_SLUG` (`pplx_export/config.py:79`)؛ لا يقرأه CLI وقت التشغيل — تستهلكه أداة صيانة الاختبارات، وتبني منه زوج استبدال الهوية (`tests/scrub_fixtures.py:446-447`). |

<a id="cli-flags-not-config-fields" data-pplx-source-anchor="true"></a>
### علامات CLI، وليس حقول إعداد

لا يحتوي TOML على أي إعدادات نقل أو ملفات تعريف ارتباط. يتم اختيارها لكل استدعاء:

| الشأن | أين يتم تعيينه |
|---|---|
| مسار ملف الإعداد | `--config PATH`، أو `PPLX_EXPORT_CONFIG` |
| مصدر ملف تعريف الارتباط | `--cookies-from BROWSER` / `--cookies FILE` |
| النقل | `--transport cookie\|webbridge` (`pplx-export` فقط؛ الافتراضي `cookie`) |

انظر [pplx-export](pplx-export.md) للحصول على مرجع العلامات الكامل.

<a id="missing-config-degraded-mode" data-pplx-source-anchor="true"></a>
## الإعداد المفقود: الوضع المتدهور

عندما لا يتم تحميل شيء، تبقى السجلات على مستوى الوحدة فارغة ويكون `LOADED_CONFIG_PATH` هو `None` (`pplx_export/config.py:83-85`). السلوك حسب السيناريو (`resolve_cli_account`، `pplx_export/commands/common.py:51-90`):

| السيناريو | السلوك |
|---|---|
| لا يوجد إعداد في المسار الافتراضي، `--account` غير معطى | وضع متدهور: يتم تسجيل تحذير وتشغيل الأوامر بحساب نائب (`username='default'`)؛ يتم تخطي فحص ملكية البريد الإلكتروني. الأوامر اليومية غير المتصلة بالإنترنت غير متأثرة (`pplx_export/commands/common.py:86-90`). |
| لا يوجد إعداد، `--account` صريح | `SystemExit` يسمي ترتيب البحث ويشير إلى `config.example.toml` (`pplx_export/commands/common.py:67-74`). |
| تم تحميل الإعداد، `--account` غير مسجل | `SystemExit` يسمي الملف المحمل، ويطلب منك إضافة `[accounts.<name>]` (`pplx_export/commands/common.py:77-82`). |
| المسار الصريح (`--config` / متغير البيئة) غير موجود | `ConfigError` في الوضع الصارم (`pplx_export/config.py:140-146`). |
| الملف موجود لكنه يفشل في التحليل | دائمًا `ConfigError` — يجب ألا يتدهور إعداد تالف بصمت (`pplx_export/config.py:147-150`). |
| `--account` محذوف، تم تحميل الإعداد | يتم استخدام `default_account` (`pplx_export/commands/common.py:84-85`). |

ما تغطيه "الأوامر غير المتصلة بالإنترنت" وكيف تتفاعل عمليات التشغيل المتدهورة مع الأرشيف مفصل في [العمليات غير المتصلة بالإنترنت](../architecture/offline-operations.md).

<a id="multi-account-cookie-model" data-pplx-source-anchor="true"></a>
## نموذج ملفات تعريف الارتباط متعددة الحسابات

مع تسجيل عدة حسابات دخول في نفس المتصفح، يحمل المخزن ملف تعريف ارتباط جلسة واحد **لكل حساب**، ويخبر حقل `email` في الإعداد الأداة بأي منها تحتاج:

- لكل حساب مسجل دخول ملف تعريف ارتباط `__Secure-pplx.session.<uid>` (`ACCOUNT_SESSION_PREFIX`، `pplx_export/core/cookies/loaders.py:171`)؛ اللاحقة `<uid>` هي `user_id` للحساب.
- الحساب **النشط** هو أي رمز موجود حاليًا في `__Secure-next-auth.session-token` (`ACTIVE_SESSION_COOKIE`، `pplx_export/core/cookies/loaders.py:172`). تبديل الحسابات = كتابة قيمة ملف تعريف ارتباط كل حساب مستهدف في ذلك ملف تعريف الارتباط — لا حاجة لواجهة مستخدم المتصفح (`pplx_export/core/cookies/loaders.py:180-187`).
- عند بدء التشغيل، يتحقق النقل من `GET https://www.perplexity.ai/api/auth/session` ويقارن البريد الإلكتروني المعاد بـ `accounts.<name>.email` (`pplx_export/commands/common.py:126-130`).
- عند عدم التطابق، يقوم `_try_switch_account` (`pplx_export/commands/common.py:190-215`) بتعداد كل رمز حساب في المتصفح عبر `list_account_tokens` (`pplx_export/core/cookies/loaders.py:175-206`، مع تفضيل الإدخالات على النطاق الفرعي `www.`)، ويجرب كل واحد في `__Secure-next-auth.session-token`، ويعيد بناء النقل عند أول تطابق.
- إذا لم يتطابق أي رمز، يخرج الأمر مسميًا كلا البريدين الإلكترونيين ويطلب منك تسجيل دخول الحساب المستهدف في المتصفح أولاً (`pplx_export/commands/common.py:142-145`) — انظر [استكشاف الأخطاء وإصلاحها](troubleshooting.md).
- حساب بدون `email` مسجل يتم متابعته دون فحص، مع تحذير يطلب منك تأكيد تسجيل دخول المتصفح بنفسك (`pplx_export/commands/common.py:146-149`).

للحصول على تدفق التبديل الكامل ودلالات نقطة نهاية الجلسة، انظر [Ask والحسابات](../architecture/ask-and-accounts.md) و[مصادقة API](../reference/api/api-authentication.md).

<a id="cookie-cache" data-pplx-source-anchor="true"></a>
## ذاكرة التخزين المؤقت لملفات تعريف الارتباط

بعد التحقق الناجح، يتم تخزين ملفات تعريف الارتباط المحلولة مؤقتًا بحيث تتخطى عمليات التشغيل اللاحقة المتصفح:

| الخاصية | القيمة |
|---|---|
| المسار | `<archive root>/index/.cookies.json` — يتبع `--out` (`pplx_export/commands/common.py:111`) |
| النضارة | 12 ساعة (`CACHE_MAX_AGE_S = 12 * 3600`، `pplx_export/core/cookies/cache.py:22`)؛ يتم التعامل مع ذاكرة التخزين المؤقتة القديمة أو التالفة كغير موجودة |
| المحتويات | `fetched_at`، `source`، `account_email`، `cookies` (`pplx_export/core/cookies/cache.py:62-66`) |
| الكتابة | ذرية: يتم إنشاء ملف مؤقت بالوضع `0o600`، ثم `os.replace` (`pplx_export/core/cookies/cache.py:49-67`) |
| Git | مغطى بـ `.gitignore` (`**/index/.cookies.json`) |

ترتيب حل ملفات تعريف الارتباط (`cookies.resolve`، `pplx_export/core/cookies/loaders.py:270-302`): `--cookies-from` صريح → ملف `--cookies` صريح → ذاكرة تخزين مؤقتة جديدة → اكتشاف تلقائي للمتصفحات (edge → chrome → firefox → safari). يتم تحديث ذاكرة التخزين المؤقت بعد كل تحقق ناجح من الحساب (`pplx_export/commands/common.py:150`).

<a id="protecting-your-files" data-pplx-source-anchor="true"></a>
## حماية ملفاتك

- `chmod 600` ملف `config.toml` الخاص بك — يحتوي على بيانات شخصية (رسائل بريد إلكتروني، معرفات مستخدمين).
- يتم بالفعل كتابة ذاكرة التخزين المؤقتة لملفات تعريف الارتباط بالوضع `0o600` بواسطة الأداة؛ ملفات تعريف ارتباط الجلسة هي بيانات اعتماد مكافئة لتسجيل الدخول.
- إذا قمت بإنشاء ملف تعريف ارتباط يدويًا لـ `--cookies`، فطبق `chmod 600` عليه أيضًا.

<a id="when-authentication-fails" data-pplx-source-anchor="true"></a>
## عندما تفشل المصادقة

ملفات تعريف الارتباط منتهية الصلاحية، حساب لا يمكن للتبديل التلقائي العثور عليه، أخطاء أذونات سلسلة مفاتيح المتصفح، وغيرها من إخفاقات المصادقة مغطاة في [استكشاف الأخطاء وإصلاحها](troubleshooting.md).
