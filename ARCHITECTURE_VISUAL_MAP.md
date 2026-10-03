> Current upload/delivery instructions: [Bot–Website integration](docs/BOT_WEBSITE_INTEGRATION.md). DevUploads/ShrinkMe upload steps below are historical and must not be used for new files. No paid infrastructure is required.

## 🎯 خريطة البوت البصرية الشاملة

هذا الملف يحتوي على خرائط بصرية توضح كيف يعمل البوت من الألف إلى الياء.

---

## الخريطة الرئيسية للبوت

```

╔══════════════════════════════════════════════════════════════════════╗
║                     Waleed Zone Bot - Main Flow                      ║
╚══════════════════════════════════════════════════════════════════════╝


                         🤖 Telegram Bot
                              │
                    ┌─────────┼─────────┐
                    │         │         │
                    ▼         ▼         ▼
            ┌──────────┐ ┌───────┐ ┌─────────┐
            │ Messages │ │Buttons│ │Documents│
            └────┬─────┘ └───┬───┘ └────┬────┘
                 │           │         │
                 └───────────┬┴────────┘
                             │
                 ┌───────────▼──────────┐
                 │  Dispatcher (aiogram)│
                 │   معالج الأحداث     │
                 └───────────┬──────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
    ┌────────┐          ┌─────────┐        ┌───────────┐
    │Handler │          │Middleware│       │States/FSM │
    │معالج  │          │وسطاء    │       │الحالات   │
    └────┬───┘          └────┬────┘        └─────┬─────┘
         │                   │                   │
         │    ┌──────────────┴───────────────┐   │
         │    │ DbSessionMiddleware          │   │
         │    │ AccessMiddleware             │   │
         │    │ ThrottleMiddleware           │   │
         │    └──────────────┬───────────────┘   │
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                   ┌─────────▼──────────┐
                   │   Business Logic   │
                   │   Services Layer   │
                   └─────────┬──────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
  ┌──────────┐      ┌────────────┐      ┌───────────┐
  │  Upload  │      │   Group    │      │Stats &    │
  │ Service  │      │  Service   │      │Broadcast  │
  └────┬─────┘      └─────┬──────┘      └─────┬─────┘
       │                  │                   │
       └──────────────────┼───────────────────┘
                          │
                ┌─────────▼──────────┐
                │  Repositories      │
                │  SQL Operations    │
                └─────────┬──────────┘
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
      ┌────────┐    ┌────────┐    ┌──────────┐
      │ SQLite │    │PostgreSQL    │ Neon.tech│
      │(local) │    │(production)  │(cloud)   │
      └────────┘    └────────┘    └──────────┘


```

---

## دورة الرسالة الكاملة (Message Lifecycle)

```
╔════════════════════════════════════════════════════════════════╗
║              كيف تذهب الرسالة من المستخدم للبوت               ║
╚════════════════════════════════════════════════════════════════╝

Step 1: المستخدم يأخذ إجراء
┌────────────────────────────┐
│ 👤 User on Telegram        │
│                            │
│ ✓ أرسل رسالة /start        │
│ ✓ اضغط زر                  │
│ ✓ ارفع ملف                 │
│ ✓ أرسل صورة                │
└────────┬───────────────────┘
         │
         ▼
Step 2: Telegram API تستقبل
┌────────────────────────────┐
│ ☁️ Telegram Servers        │
│ ✓ استقبال الحدث           │
│ ✓ معالجة الخادم           │
│ ✓ إرسال للبوت             │
└────────┬───────────────────┘
         │
         ▼
Step 3: aiogram Dispatcher
┌────────────────────────────┐
│ 🔄 Dispatcher              │
│ ✓ استقبال update          │
│ ✓ تحديد نوع الحدث         │
│ ✓ بحث عن معالج مناسب      │
└────────┬───────────────────┘
         │
         ▼
Step 4: Middleware Chain
┌────────────────────────────┐
│ 🛡️ DbSessionMiddleware     │
│ ✓ توفير جلسة DB           │
└────────┬───────────────────┘
         │
         ▼
┌────────────────────────────┐
│ 🔐 AccessMiddleware        │
│ ✓ التحقق من الصلاحيات    │
│ ✓ معرفة نوع المستخدم     │
└────────┬───────────────────┘
         │
         ▼
┌────────────────────────────┐
│ ⏱️ ThrottleMiddleware      │
│ ✓ منع الإغراق             │
│ ✓ Rate Limiting            │
└────────┬───────────────────┘
         │
Step 5: Handler Function
         ▼
┌────────────────────────────┐
│ ⚙️ Handler (معالج)        │
│ ✓ استقبال الرسالة        │
│ ✓ استخراج البيانات        │
│ ✓ معالجة الطلب            │
│ ✓ استدعاء Services        │
└────────┬───────────────────┘
         │
         ▼
Step 6: Business Logic 
┌────────────────────────────┐
│ 💼 Service Layer           │
│ ✓ معالجة العملية          │
│ ✓ منطق تجاري              │
│ ✓ استدعاء Repositories    │
└────────┬───────────────────┘
         │
         ▼
Step 7: Database Layer
┌────────────────────────────┐
│ 🗄️ Repositories            │
│ ✓ SQL Query                │
│ ✓ INSERT/SELECT/UPDATE     │
│ ✓ إرجاع النتائج           │
└────────┬───────────────────┘
         │
         ▼
Step 8: Build Response
┌────────────────────────────┐
│ 📝 Create Message          │
│ ✓ نص الرد                 │
│ ✓ الأزرار                 │
│ ✓ الصورة                  │
│ ✓ التنسيق (HTML/Markdown) │
└────────┬───────────────────┘
         │
         ▼
Step 9: Send to Telegram
┌────────────────────────────┐
│ ☁️ Telegram API            │
│ ✓ إرسال الرسالة          │
│ ✓ إرسال الأزرار           │
│ ✓ تسجيل في السجل         │
└────────┬───────────────────┘
         │
         ▼
Step 10: User Receives
┌────────────────────────────┐
│ 📱 User Screen             │
│ ✓ رسالة مع أزرار          │
│ ✓ تنسيق جميل              │
│ ✓ جاهز للتفاعل            │
└────────────────────────────┘


⚡ الوقت الكلي: 200-500ms عادي
```

---

## نقطة الدخول (Entry Point)

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│   python main.py  ← تشغيل البوت                            │
│                                                              │
│   ✓ قراءة الإعدادات من .env                              │
│   ✓ إنشاء اتصال قاعدة البيانات                            │
│   ✓ تهيئة جداول البيانات                                  │
│   ✓ إنشاء كائن Bot                                       │
│   ✓ تسجيل جميع المعالجات (الـ Routers)                  │
│   ✓ تعيين الوسطاء (Middlewares)                           │
│   ✓ وضع البوت في polling mode                            │
│   ✓ الاستماع للرسائل                                     │
│                                                              │
│   ✅ Waleed Zone Bot is running...                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## شجرة المعالجات (Handlers Tree)

```
Root Dispatcher
│
├─ 🏠 Router: start
│  ├─ Handler: /start command
│  │  └─ عرض القائمة الرئيسية
│  │
│  └─ Callback: main_menu
│     ├─ 🔍 search
│     ├─ 📱 latest
│     ├─ 🏷️ categories
│     ├─ ★ favorites
│     └─ ⚙️ admin (if user is admin)
│
├─ 🔍 Router: search
│  ├─ Handler: search_query (message)
│  │  └─ معالجة البحث
│  │
│  ├─ Callback: select_app
│  │  └─ عرض تفاصيل التطبيق
│  │
│  └─ Callback: app_actions
│     ├─ ⬇️ download
│     ├─ ❤️ favorite
│     └─ 👈 back
│
├─ 📱 Router: applications
│  ├─ Callback: app_details
│  │  └─ عرض كامل التطبيق
│  │
│  ├─ Callback: add_favorite
│  │  └─ إضافة للمفضلة
│  │
│  └─ Callback: download_app
│     └─ تحديث عدد التحميلات
│
├─ ⚙️ Router: admin (requires admin)
│  ├─ Callback: upload_menu
│  │  └─ قائمة الرفع
│  │
│  ├─ Handler: upload_start
│  │  ├─ State: waiting_name
│  │  │  └─ Handler: receive_name
│  │  │
│  │  ├─ State: waiting_description
│  │  │  └─ Handler: receive_description
│  │  │
│  │  ├─ State: waiting_category
│  │  │  └─ Handler: receive_category
│  │  │
│  │  ├─ State: waiting_platform
│  │  │  └─ Handler: receive_platform
│  │  │
│  │  ├─ State: waiting_file
│  │  │  └─ Handler: receive_file
│  │  │
│  │  └─ State: waiting_confirmation
│  │     ├─ Callback: confirm_upload
│  │     ├─ Callback: edit_upload
│  │     └─ Callback: cancel_upload
│  │
│  ├─ Callback: manage_apps
│  │  ├─ Callback: list_apps
│  │  ├─ Callback: edit_app
│  │  └─ Callback: delete_app
│  │
│  ├─ Callback: manage_requests
│  │  └─ عرض الطلبات المعلقة
│  │
│  └─ Callback: statistics
│     └─ عرض الإحصائيات
│
├─ 📬 Router: requests (all users)
│  ├─ Callback: request_menu
│  │  └─ قائمة الطلبات
│  │
│  ├─ Handler: new_request (state: waiting_request_name)
│  │  └─ Handler: request_description (state: waiting_description)
│  │     └─ حفظ الطلب
│  │
│  └─ Callback: my_requests
│     └─ عرض طلبات المستخدم
│
└─ 👥 Router: group (only in groups/channels)
   ├─ ChatMember: welcome_member
   │  └─ ترحيب أعضاء جدد
   │
   ├─ Message: check_spam
   │  └─ فحص الرسائل المريبة
   │
   ├─ Message: check_flood
   │  └─ منع الإغراق
   │
   └─ Callback: admin_actions
      ├─ 🔇 mute_user
      ├─ 🚫 ban_user
      ├─ ⚠️ warn_user
      └─ 🗑️ delete_message
```

---

## تدفق رفع التطبيق (Upload Flow Diagram)

```
                           📤 Upload Flow
                                │
                ┌───────────────┼───────────────┐
                │               │               │
                ▼               ▼               ▼
          ┌─────────┐     ┌──────────┐    ┌──────────┐
          │الملف APK│     │رابط مباشر│    │رابط صفحة │
          └────┬────┘     └────┬─────┘    └────┬─────┘
               │               │               │
               └───────────────┼───────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Upload Service    │
                    │  المرحلة 1: التحقق │
                    │  - حجم الملف       │
                    │  - الصيغة          │
                    │  - الأمان          │
                    └────────┬───────────┘
                             │
                    ┌────────▼──────────┐
                    │ المرحلة 2:        │
                    │ تحميل من Telegram │
                    │ أو تحميل من رابط  │
                    └────────┬──────────┘
                             │
                    ┌────────▼──────────┐
                    │ المرحلة 3:        │
                    │ رفع إلى DevUploads│
                    │ (أو تخطي)         │
                    └────────┬──────────┘
                             │
                ┌────────────▼──────────────┐
                │ هل تقصير مع ShrinkMe؟    │
                └────────┬─────────┬────────┘
                         │         │
                    ┌────▼──┐  ┌───▼────┐
                    │ نعم   │  │ لا     │
                    └────┬──┘  └───┬────┘
                         │         │
                         ├─────────┤
                         │         │
                    ┌────▼─────────▼────┐
                    │ معاينة التطبيق   │
                    │ - الاسم          │
                    │ - الوصف          │
                    │ - الفئة          │
                    │ - الصورة         │
                    │ - الرابط         │
                    └────────┬─────────┘
                             │
                ┌────────────▼────────────┐
                │ الأدمن يؤكد النشر؟     │
                └────────┬─────────┬─────┘
                         │         │
                    ┌────▼──┐  ┌───▼─────┐
                    │ نعم   │  │ لا/عدّل │
                    └────┬──┘  └───┬─────┘
                         │         │
                         │    رجوع للتعديل
                         │         │
                    ┌────▼──┐  ◀──┘
                    │حفظ في │
                    │قاعدة  │
                    │البيانات│
                    └────┬──┘
                         │
                    ┌────▼──────────────┐
                    │ إرسال للقناة؟     │
                    └────┬─────────┬────┘
                         │         │
                    ┌────▼───┐ ┌───▼────┐
                    │ نعم    │ │ لا     │
                    └────┬───┘ └───┬────┘
                         │        │
                    ┌────▼────────▼────┐
                    │ ✅ تم النشر!      │
                    │ إخطار المستخدم   │
                    └───────────────────┘
```

---

## شجرة قاعدة البيانات

```
                    📦 Database Schema
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
      ┌─────────┐      ┌──────────┐     ┌────────────┐
      │  Users  │      │Applications   │ Favorites   │
      ├─────────┤      ├──────────┤    ├────────────┤
      │ id      │◄────┤ id       │      │ id         │
      │ tg_id   │      │ name     │      │ user_id    │
      │ username│      │ desc     │      │ app_id     │
      │ first..│       │ version  │      │ created_at │
      │ active  │       │ category │      └────────────┘
      └─────────┘      │ platform │
                       │ icon...  │
                       │ image_url│
                       │ devurl   │
                       │ shrinkurl│
                       │ active   │
                       └┬────────┬┘
                        │        │
              ┌─────────▼──┐  ┌──▼──────────┐
              │  Requests  │  │ Group Rules │
              ├────────────┤  ├─────────────┤
              │ id         │  │ id          │
              │ user_id    │  │ group_id    │
              │ app_name   │  │ welcome_msg │
              │ description│  │ rules       │
              │ status     │  │ banned_ids  │
              │ replied_at │  └─────────────┘
              └────────────┘
```

---

## خريطة الملفات المهمة

```
mytelebot/
│
├── 📄 main.py ← 🎯 نقطة البدء
│
├── config/
│   └── settings.py ← إعدادات البوت (من .env)
│
├── database/
│   ├── models.py ← 🗄️ تعريف الجداول
│   ├── database.py ← اتصال DB
│   └── repositories.py ← عمليات DB
│
├── app/
│   ├── handlers/ ← ⚙️ معالجات الأوامر
│   │   ├── start.py
│   │   ├── upload.py
│   │   ├── search.py
│   │   ├── requests.py
│   │   └── group.py
│   │
│   ├── services/ ← 💼 المنطق التجاري
│   │   ├── upload_service.py
│   │   ├── group_service.py
│   │   └── stats_service.py
│   │
│   ├── middlewares/ ← 🛡️ الوسطاء
│   │   ├── db.py
│   │   ├── access.py
│   │   └── throttle.py
│   │
│   ├── states/ ← 📍 حالات FSM
│   │   └── forms.py
│   │
│   ├── keyboards/ ← ⌨️ الأزرار
│   │   ├── user.py
│   │   └── admin.py
│   │
│   └── utils/
│       ├── constants.py
│       ├── helpers.py
│       ├── text.py
│       └── logging_config.py
│
├── integrations/ ← 🔌 خدمات خارجية
│   ├── telegram.py
│   ├── imgbb.py
│   ├── devupload.py
│   └── shrankme.py
│
├── scripts/
│   └── migrate_images.py ← ترحيل الصور
│
├── .env ← 🔐 الأسرار (لا تنشره!)
├── .env.example ← 📋 قالب الإعدادات
├── requirements.txt ← 📦 المتطلبات
├── Dockerfile ← 🐳 بناء الـ container
├── docker-compose.yml ← تشغيل الخدمات
│
└── 📚 Documentation
    ├── LOCAL_DEVELOPMENT.md ← 👈 اقرأ هذا!
    ├── BOT_ARCHITECTURE.md
    ├── LOCAL_TESTING_CHECKLIST.md
    └── ...
```

---

## ملخص معمارية البوت بعبارة قصيرة

```
┌─────────────────────────────────────────────────────────┐
│                  Waleed Zone Bot Architecture           │
└─────────────────────────────────────────────────────────┘

User on Telegram
        │
        ▼
   Dispatcher (aiogram)
        │
        ├─► Middlewares (Auth, DB, Rate Limit)
        │
        ├─► Handlers (معالجات الأوامر)
        │
        ├─► Services (منطق الأعمال)
        │
        ├─► Repositories (عمليات قاعدة البيانات)
        │
        ▼
   Database (SQLite/PostgreSQL)
        │
        └─► Telegram Cloud / External APIs


✨ Result: Response back to User
```

---

✅ **فهمت المعمارية؟** جرّب تشغيل البوت الآن! 🚀

