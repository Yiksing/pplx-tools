---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-authentication.md"
translation_source_sha256: "dc9067f0d08c997245ee548a335fc762ad0cbe986661ba0ad7f976150131dd72"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="authentication-model" data-pplx-source-anchor="true"></a>
# نموذج المصادقة

> تقدم هذه الصفحة منطقة مرجع واجهة برمجة التطبيقات — السجل الميداني لمشروع pplx_export لواجهة برمجة التطبيقات الخاصة لـ Perplexity.
> الجمهور: المشرفون ومستخدمو هذا المشروع. تم التحقق من جميع نقاط النهاية عبر التقاط شبكة WebBridge + طلبات مباشرة موثقة بملفات تعريف الارتباط (يوليو 2026).
> **يجب مزامنة أي تغيير أو إضافة إلى معرفة واجهة برمجة التطبيقات في هذه الصفحات** (متطلب مستخدم صريح).
> آخر تحديث: 2026-07-23
>
> تنقسم المنطقة المرجعية إلى: **1. نموذج المصادقة** (هذه الصفحة) · [2. GraphQL (الاستعلامات المستمرة / APQ)](api-graphql.md) · [3. نقاط نهاية REST (مجمعة حسب الغرض)](api-rest-endpoints.md) · [4–5. هيكل الاستجابة ودلالات الأخطاء](api-responses-errors.md) · [6–8. عناصر TBD، اكتشاف نقاط النهاية وخريطة الطريق](api-discovery-roadmap.md) — لتصميم النظام المحيط، راجع [خريطة قراءة البنية](../../architecture/index.md).

---

<a id="authentication-model_1" data-pplx-source-anchor="true"></a>
## نموذج المصادقة

<a id="cookie-session" data-pplx-source-anchor="true"></a>
### جلسة ملفات تعريف الارتباط
- تحتاج جميع طلبات واجهة برمجة التطبيقات فقط إلى ملف تعريف ارتباط جلسة المتصفح (لا حاجة لرمز CSRF؛ تم التحقق من عمل كل من GET و POST عبر الطلبات المباشرة).
- ملف تعريف الارتباط الرئيسي: `__Secure-next-auth.session-token` (رمز جلسة **الحساب النشط حاليًا**).
- Cloudflare موجود في المقدمة: `cf_clearance`/`__cf_bm` مرتبطان ببصمة TLS للمتصفح — **تحصل طلبات curl العارية على 403**؛
  تمر الأداة مع Python urllib + ملفات تعريف الارتباط المستوردة من المتصفح (UA متنكر كـ Chrome سطح المكتب).

<a id="multi-account-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### حسابات متعددة (اكتُشفت في 2026-07-20)
- عندما يتم تسجيل دخول حسابات متعددة إلى نفس المتصفح، يحمل كل حساب ملف تعريف الارتباط `__Secure-pplx.session.<user_id>` الخاص به
  (النطاق www.perplexity.ai؛ القيمة تتقدم مع الاستجابات).
- قيمة `__Secure-next-auth.session-token` = قيمة ملف تعريف الارتباط الخاص بالحساب النشط.
- **تبديل الحسابات على الويب** = الانتقال إلى `https://www.perplexity.ai/?pplx_account=<user_id>`؛ يعيد الخادم كتابة الرمز النشط.
- **التبديل التلقائي من جانب الأداة** (مُطبق في pplx_export): تعداد ملفات تعريف الارتباط `__Secure-pplx.session.*` للمتصفح،
  استبدال `__Secure-next-auth.session-token` بكل منها بدوره، وفحص `/api/auth/session` حتى يتطابق البريد الإلكتروني الهدف.
- يُرجع `GET /api/auth/linked-accounts` `accounts: [{user_id, email, display_name, subscription_tier, is_primary}]`،
  لكن **يُرجع قائمة الحسابات الكاملة فقط عندما يكون الحساب الأساسي نشطًا** (فقط الحساب الحالي عندما يكون غير الأساسي نشطًا) — لذلك لا تعتمد الأداة عليه.
- أمثلة الحسابات المسجلة (جدول الحسابات الحقيقي موجود في `config.toml` على مستوى المستخدم؛ العناصر النائبة موضحة هنا):
  A `alice` / alice@example.com / uid `00000000-0000-4000-8000-0000000000aa` (Max)؛
  B `bob` / bob@example.com / uid `00000000-0000-4000-8000-0000000000bb` (Pro، أساسي).
