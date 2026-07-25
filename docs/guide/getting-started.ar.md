---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/getting-started.md"
translation_source_sha256: "d98ba1f32b1e75bff7b3d51ef17e833417ecaf283996152cfa3342455b6eca7a"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="getting-started" data-pplx-source-anchor="true"></a>
# البدء

من استنساخ جديد إلى أول أرشيف محلي: تثبيت الأمرين، إنشاء الإعدادات على مستوى المستخدم، اختيار قناة ملفات تعريف الارتباط، وتنفيذ أول تصدير.

<a id="requirements" data-pplx-source-anchor="true"></a>
## المتطلبات

- **Python ≥ 3.11**
- **[uv](https://docs.astral.sh/uv/)** — يُستخدم لتثبيت الأدوات وتشغيل مجموعة الاختبارات
- **متصفح سطح مكتب مسجل الدخول إلى Perplexity** — تعيد الأدوات استخدام ملفات تعريف الارتباط الخاصة بجلسة المتصفح؛ لا يتم تخزين أي رمز مميز في الإعدادات

يستخدم فك تشفير ملفات تعريف الارتباط `browser_cookie3`. يغطي الاكتشاف التلقائي Edge وChrome وFirefox وSafari؛ تعمل Brave وChromium وOpera وVivaldi عبر `--cookies-from`.

<a id="install" data-pplx-source-anchor="true"></a>
## التثبيت

لا حاجة للاستنساخ — قم بالتثبيت مباشرة من رابط git:

```bash
uv tool install git+https://github.com/Yiksing/pplx-tools.git
# PyPI-mirror alternative (e.g. mainland China):
# uv tool install --index-url https://mirrors.aliyun.com/pypi/simple git+https://github.com/Yiksing/pplx-tools.git
```

من استنساخ محلي (جذر المستودع):

```bash
uv tool install .            # or development mode: uv tool install --editable .
```

يؤدي هذا إلى تثبيت أمرين: `pplx-export` (الأرشفة) و`pplx-ask` (الاستعلامات التفاعلية). تحقق:

```bash
pplx-export --version
pplx-export --help           # overview with examples; each subcommand has its own --help
pplx-ask --help
```

يقوم `uvx --from . pplx-export` بتشغيل أمر لمرة واحدة دون تثبيت.

<a id="create-the-user-level-config" data-pplx-source-anchor="true"></a>
## إنشاء الإعدادات على مستوى المستخدم

سجل الحساب (الاسم المعروض / البريد الإلكتروني / معرف المستخدم) ومساحة BOT هي بيانات شخصية و**لا يتم إيداعها في المستودع**؛ فهي موجودة في ملف TOML خارجي. النموذج: `config.example.toml` في جذر المستودع.

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml   # personal data — keep it owner-only
# edit and fill in your real account values
```

1. إنشاء دليل الإعدادات.
2. نسخ النموذج إلى المسار الافتراضي.
3. `chmod 600` — يحتوي الملف على بيانات شخصية؛ اجعله مملوكًا للمالك فقط.
4. ملء `[accounts.<name>]` — المفتاح هو اسم مستخدم الحساب (كما يظهر في روابط المواضيع / المكتبة)؛ قم بتعيين `display_name` و`email` و`user_id` واختر `default_account`.
5. ملء `[bot_space]` — حيث يتم جمع المواضيع التي أنشأها `pplx-ask` بعد الانتهاء (يمكن إنشاء مساحة حقيقية باستخدام `pplx-ask space-create`).

**البديل التلقائي:** يقوم `pplx-export init` باشتقاق هذا الملف لك — فهو يعدد ملفات تعريف الارتباط الخاصة بجلسة كل حساب في متصفحك، ويستكشف `/api/auth/session` للبريد الإلكتروني / الاسم المعروض لكل رمز مميز، ويضبط `default_account` على الحساب النشط حاليًا، ويطابق مساحة BOT حسب العنوان، ويكتب TOML بشكل ذري بأذونات 0600 (لا يتم استبدال ملف موجود إلا باستخدام `--force`).

```bash
pplx-export init                     # discover accounts, write the default config path
pplx-export init --create-bot-space [TITLE]  # create the BOT space when no title matches (custom title optional)
pplx-export init --bot-title TITLE   # match/create a different space title (default BOT)
pplx-export init --config /path/to/config.toml   # write to a custom path
```

العلامات: `--force` يستبدل الإعدادات الموجودة؛ `--create-bot-space [TITLE]` ينشئ المساحة عبر API عندما لا يتطابق أي عنوان (عملية كتابة على الحساب؛ عنوان TITLE صريح يوجه كلاً من المطابقة والإنشاء)؛ `--bot-title TITLE` يُستخدم لكل من المطابقة والإنشاء. لاحظ أنه بالنسبة لـ `init` — على عكس كل أمر آخر — فإن `--config` هو مسار **الكتابة**، وليس مسار التحميل. التفاصيل الكاملة: [pplx-export → init](pplx-export.md#init).

مرجع الحقول الكامل موجود في [الإعدادات](configuration.md).

**أولوية التحميل** (الأعلى أولاً):

| # | المصدر |
|---|--------|
| 1 | `--config PATH` |
| 2 | متغير البيئة `PPLX_EXPORT_CONFIG` |
| 3 | `~/.config/pplx-export/config.toml` (الافتراضي) |

!!! ملاحظة "عندما تكون الإعدادات مفقودة"
    تعمل الأوامر بدون `--account` في وضع منخفض — يتم تخطي التحقق من ملكية البريد الإلكتروني مع تحذير (الأوامر غير المتصلة غير متأثرة)؛ يؤدي `--account` صريح إلى ظهور خطأ يشير إلى `config.example.toml`. عند حذف `--account`، يتم استخدام `default_account` من الإعدادات.

<a id="choose-a-cookie-channel" data-pplx-source-anchor="true"></a>
## اختيار قناة ملفات تعريف الارتباط

تأتي بيانات الاعتماد من ملفات تعريف ارتباط جلسة Perplexity المسجل دخوله في متصفحك المحلي، والتي تُقرأ عبر `browser_cookie3` — بما في ذلك تعداد الرموز المميزة متعددة الحسابات والتبديل التلقائي. أربع قنوات:

| القناة | الكيفية | ملاحظات |
|---------|-----|-------|
| الاكتشاف التلقائي (الافتراضي) | لا علامة | ذاكرة تخزين مؤقت جديدة لمدة 12 ساعة أولاً، ثم مخازن المتصفح بالترتيب edge→chrome→firefox→safari |
| متصفح مسمى | `--cookies-from <browser>` | edge / chrome / firefox / safari / brave … |
| ملف تعريف ارتباط | `--cookies /path/to/cookies.txt` | ملف تعريف ارتباط Netscape أو JSON مُصدَّر |
| WebBridge | `--transport webbridge` | جلب سياق الصفحة — القناة الاحتياطية، تُستخدم فقط عند الطلب الصريح |

على Linux، يتم أيضًا اكتشاف تثبيتات المتصفح snap و flatpak تلقائيًا — يتم تغطية مسارات ملفات التعريف الخاصة بها بواسطة السجل المدمج. مصفوفة Linux الكاملة (keyring، بيئات سطح المكتب، حزم التوزيعات):
[استكشاف الأخطاء وإصلاحها → فك تشفير ملفات تعريف الارتباط على Linux](troubleshooting.md#linux-cookie-decryption).

```bash
pplx-export export <thread_url>                                 # default: auto-detect browser store
pplx-export export <thread_url> --cookies-from edge             # import from a specific browser
pplx-export export <thread_url> --cookies /path/to/cookies.txt  # use a cookie file
pplx-export export <thread_url> --transport webbridge           # WebBridge page context (explicit fallback)
```

بعد الحصول على ملفات تعريف الارتباط، تستدعي الأداة `/api/auth/session` وتطبع البريد الإلكتروني للحساب الحالي حتى تتمكن من تأكيد استخدام الحساب الصحيح — انتبه إذا كان `--account` لا يتفق مع حساب ملف تعريف الارتباط. يتم تغطية تصميم النقل / بيانات الاعتماد في [الاستعلام والحسابات](../architecture/ask-and-accounts.md).

<a id="first-run" data-pplx-source-anchor="true"></a>
## التشغيل الأول

```bash
pplx-export index --account alice     # fetch the library index
pplx-export export <thread_url>       # export a single thread
pplx-export batch --account alice     # batch (incremental early-stop by default; --full for a full sweep)
pplx-export re-render --dry-run       # offline re-render, zero network
```

1. **`index`** يجلب فهرس مكتبة الحساب — نقطة الدخول التي يبني عليها `batch` والأوامر الأخرى على مستوى الحساب.
2. **`export`** يؤرشف موضوعًا واحدًا من البداية إلى النهاية: يحتفظ باستجابات API الأولية (`raw_*.json`) إلى جانب Markdown بحيث يمكن إعادة تشغيل العرض في وضع عدم الاتصال.
3. **`batch`** يمسح المكتبة بأكملها. يتوقف مبكرًا بمجرد أن يكون كل ما تبقى مؤرشفًا بالفعل (إيقاف مبكر تدريجي)، ويكتب نقاط تفتيش قابلة للاستئناف، ويقبل `--full` لمسح كامل. التفاصيل: [المزامنة التدريجية](incremental-sync.md).
4. **`re-render --dry-run`** يثبت مسار عدم الاتصال: يعيد إنشاء `conversation.md` + `turns/` من الملفات الأولية المحلية بدون شبكة. احذف `--dry-run` لكتابة النتائج. انظر [العمليات غير المتصلة](../architecture/offline-operations.md).

بمجرد أن يعمل ذلك، يقوم `pplx-ask ask "<prompt>"` بتشغيل استعلام متدفق ويؤرشف الموضوع الناتج تلقائيًا — انظر [pplx-ask](pplx-ask.md).

<a id="where-archives-land" data-pplx-source-anchor="true"></a>
## أين تهبط الأرشيفات

تتم كتابة الأرشيفات إلى `./web_archive/` افتراضيًا (تجاوز باستخدام `--out`): دليل واحد لكل موضوع.

| المسار | المحتوى |
|------|---------|
| `conversation.md`, `turns/` | المحادثة المعروضة |
| `thread.json` | بيانات وصفية للموضوع + سجل المقاطعات |
| `sources.md` / `sources.json` | الاستشهادات |
| `report.md` | تقرير البحث العميق / المجلس / الدراسة |
| `assets/` | الأصول التي تم تنزيلها (وضع الكمبيوتر) |
| `raw_*.json` | استجابات API الأولية المحتفظ بها — يمكن إعادة عرض الأرشيفات الناجحة دون اتصال دون إعادة الجلب |

عقد الدليل الكامل: [تخطيط الأرشيف](archive-layout.md).

<a id="next-steps" data-pplx-source-anchor="true"></a>
## الخطوات التالية

- حدث خطأ ما؟ → [استكشاف الأخطاء وإصلاحها](troubleshooting.md)
- مرجع أمر بأمر → [pplx-export](pplx-export.md) · [pplx-ask](pplx-ask.md) · [أوامر الصيانة](maintenance-commands.md)
- أوضاع المحادثة الخمسة → [الأوضاع](modes.md)
