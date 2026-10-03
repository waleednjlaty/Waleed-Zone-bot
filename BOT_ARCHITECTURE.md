> Current upload/delivery instructions: [Bot–Website integration](docs/BOT_WEBSITE_INTEGRATION.md). DevUploads/ShrinkMe upload steps below are historical and must not be used for new files. No paid infrastructure is required.

## 🗺️ خارطة معمارية البوت

### سير العمل الكامل

```
┌─────────────────────────────────────────────────────────────────┐
│                      المستخدم على تيليجرام                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
         ┌──────────────────────────────┐
         │  Telegram Messages & Events  │
         │  /start, /search, upload ... │
         └────────────┬─────────────────┘
                      │
                      ▼
         ┌──────────────────────────────┐
         │     Dispatcher (aiogram)     │
         │  معالج الرسائل الرئيسي       │
         └────────────┬─────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
    ┌────────┐  ┌────────┐  ┌────────┐
    │Handlers│  │Middlewares│ │States│
    └─┬──────┘  └─┬──────┘  └─┬─────┘
      │           │           │
      ├─────────┬─┴───────┬───┘
      │         │         │
      ▼         ▼         ▼
   ┌─────────────────────────────┐
   │   Business Logic & Services │
   │  - Upload Service           │
   │  - Group Service            │
   │  - Stats Service            │
   └──────────────┬──────────────┘
                  │
                  ▼
      ┌──────────────────────────┐
      │  Database (SQLAlchemy)   │
      │  Users, Apps, Requests.. │
      └──────────────┬───────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    ┌────────┐  ┌────────┐  ┌────────┐
    │ SQLite │ │PostgreSQL│ │ Neon  │
    └────────┘  └────────┘  └────────┘
```

---

## 📦 مكونات البوت التفصيلية

### 1. طبقة المعالجات (Handlers Layer)

```
app/handlers/
│
├── start.py          ← /start - القائمة الرئيسية
├── search.py         ← 🔍 البحث عن التطبيقات
├── upload.py         ← ⬆️ رفع التطبيقات (للمالك)
├── requests.py       ← 📬 طلب تطبيق من المستخدم
├── applications.py   ← 📱 عرض التطبيقات والتفاصيل
├── group.py          ← 👥 معالجات المجموعة
├── admin.py          ← ⚙️ لوحة التحكم
└── common.py         ← 🔗 معالجات مشتركة
```

### 2. طبقة الخدمات (Services Layer)

```
app/services/
│
├── upload_service.py      ← تنسيق عملية الرفع
│   ├── تحديد مصدر الملف
│   ├── رفع لـ DevUploads
│   ├── تقصير مع ShrinkMe
│   └── حفظ في الـ DB
│
├── group_service.py       ← إدارة المجموعة
│   ├── ترحيب بأعضاء جدد
│   ├── إزالة المتطفلين
│   ├── تطبيق القوانين
│   └── تحذيرات وحظر
│
├── broadcast_service.py   ← إرسال إشعارات للمستخدمين
└── stats_service.py       ← إحصائيات الاستخدام
```

### 3. طبقة الوسطاء (Middlewares)

```
app/middlewares/
│
├── DbSessionMiddleware    ← توفير جلسة قاعدة البيانات
├── AccessMiddleware       ← التحقق من الصلاحيات (مالك/مستخدم)
└── ThrottleMiddleware     ← منع الإغراق (Rate Limiting)
```

### 4. طبقة الحالات (States - FSM)

```
app/states/forms.py
│
├── UploadStates           ← حالات عملية الرفع
│   ├── waiting_name
│   ├── waiting_description
│   ├── waiting_category
│   └── waiting_confirmation
│
├── RequestStates          ← حالات طلب تطبيق
│   ├── waiting_request_name
│   └── waiting_request_description
│
└── SearchStates           ← حالات البحث
    └── waiting_search_query
```

### 5. قاعدة البيانات (Database Layer)

```
database/
│
├── models.py              ← نماذج البيانات
│   ├── User              ← المستخدمون
│   ├── Application       ← التطبيقات
│   ├── Favorite          ← المفضلة
│   ├── Request           ← الطلبات
│   ├── Group             ← إعدادات المجموعة
│   └── Stats             ← الإحصائيات
│
├── repository.py          ← عمليات CRUD
│   ├── get_user()
│   ├── create_app()
│   ├── search_apps()
│   └── ...
│
└── database.py            ← إدارة الاتصال
    ├── init_db()
    ├── create_session()
    └── close()
```

---

## 🔄 تدفق رفع التطبيق (Upload Flow)

```
المالك يبدأ برسالة /upload
        │
        ▼
   ┌──────────────────┐
   │ UploadStates.    │
   │ waiting_name     │
   └────────┬─────────┘
            │ (المالك يكتب الاسم)
            ▼
   ┌──────────────────┐
   │ waiting_desc     │ (وصف التطبيق)
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │ waiting_category │ (اختر الفئة)
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │ waiting_platform │ (iOS/Android/Windows)
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │ waiting_file     │ (ارفع الملف)
   └────────┬─────────┘
            │
            ▼
   ┌─────────────────────────┐
   │ upload_service.py       │
   │ ┌─────────────────────┐ │
   │ │ 1. هل من DevUploads?│ │
   │ │    أم رابط مباشر؟   │ │
   │ └──────┬──────────────┘ │
   │        │                │
   │ ┌──────▼──────────────┐ │
   │ │ 2. هل من ShrinkMe?  │ │
   │ │    تقصير الرابط؟   │ │
   │ └──────┬──────────────┘ │
   │        │                │
   │ ┌──────▼──────────────┐ │
   │ │ 3. معاينة التطبيق  │ │
   │ └──────┬──────────────┘ │
   └─────────┼────────────────┘
             │
    ┌────────▼────────┐
    │ المالك يؤكد أم │
    │ يعدّل؟          │
    └────────┬────────┘
             │
    ┌────────▼──────────┐
    │ حفظ في قاعدة      │
    │ البيانات         │
    └────────┬──────────┘
             │
    ┌────────▼──────────┐
    │ إرسال للقناة      │
    │ (اختياري)        │
    └──────────────────┘
             ✅
```

---

## 🔍 تدفق البحث والتصفح

```
المستخدم يختار:
│
├─────────────────────┬──────────────────┬──────────────────┐
│                     │                  │                  │
▼                     ▼                  ▼                  ▼
🔍 بحث          📱 أحدث           🏷️ الفئات         ★ المفضلة
search_query    latest_apps      categories       favorites
│               │                │                │
└─────────────┬─┴────────────────┴────────────────┘
              │
              ▼
   ┌─────────────────────────┐
   │  repositories.py        │
   │  search_apps()          │
   │  get_latest_apps()      │
   │  get_by_category()      │
   │  get_favorites()        │
   └────────────┬────────────┘
                │
                ▼
   ┌─────────────────────────┐
   │  قاعدة البيانات         │
   │  SQLAlchemy Query       │
   └────────────┬────────────┘
                │
                ▼
   ┌─────────────────────────┐
   │  عرض النتائج            │
   │  ✓ اسم التطبيق          │
   │  ✓ صورة صغيرة           │
   │  ✓ عدد المحبين          │
   │  ✓ زر التفاصيل          │
   └────────────┬────────────┘
                │
       ┌────────┴────────┐
       │                 │
       ▼                 ▼
   ❤️ حفظ كمفضل      📄 عرض التفاصيل
   (Favorite)       (Details)
```

---

## 📱 تتراتبية المعالجات (Handlers Hierarchy)

```
Router "start"
├─ /start              → عرض القائمة الرئيسية
├─ callback: main_menu → التعامل مع أزرار القائمة
│
└─ Router "search"
   ├─ message:  search_query → البحث
   ├─ callback: category     → اختيار فئة
   ├─ callback: latest       → أحدث التطبيقات
   │
   └─ Router "upload" (admin)
      ├─ callback: upload_start       → بدء الرفع
      ├─ message:  receive_name       → جمع البيانات
      ├─ message:  receive_desc
      ├─ message:  receive_category
      ├─ document: receive_file       → الملف
      ├─ callback: publish            → نشر
      │
      └─ Router "requests" (user)
         ├─ callback: request_new       → طلب تطبيق
         ├─ message:  receive_request
         │
         └─ Router "group" (members)
            ├─ message: welcome_new_user
            ├─ message: check_flood
            ├─ message: check_spam
            └─ callback: admin_actions  → حظر، كتم، ...
```

---

## 🔐 نظام الصلاحيات

```
┌───────────────────────┐
│ المستخدم يرسل رسالة  │
└───────────┬───────────┘
            │
            ▼
┌──────────────────────────────┐
│ AccessMiddleware.py          │
│ حفص: هل المستخدم مسموح؟      │
└────────┬─────────────────────┘
         │
    ┌────┴─────────────────┐
    │                      │
    ▼                      ▼
🔓 مسموح              ❌ ممنوع
(proceed)              (block)
    │                      │
    ├─ مالك (Admin)        └─ رسالة رفض
    │  └─ كامل الصلاحيات
    │
    ├─ مشرف المجموعة
    │  └─ إدارة المجموعة فقط
    │
    └─ مستخدم عادي
       └─ البحث والتصفح فقط
```

---

## 🗄️ نموذج قاعدة البيانات

```
┌──────────────────┐
│      users       │
├──────────────────┤
│ id: int (PK)     │
│ telegram_id: int │
│ username: str    │
│ is_active: bool  │
│ created_at: date │
└──────────────────┘
       │
       ├─── relation ──────────────┐
       │                           │
       ▼                           ▼
┌──────────────────┐      ┌──────────────────┐
│    favorites     │      │     requests     │
├──────────────────┤      ├──────────────────┤
│ id: int (PK)     │      │ id: int (PK)     │
│ user_id: int (FK)│      │ user_id: int (FK)│
│ app_id: int (FK) │      │ app_name: str    │
│ created_at: date │      │ description: str │
└──────────────────┘      │ status: enum     │
                          │ replied_at: date │
                          └──────────────────┘
       ▲
       │
┌──────┴──┐                ┌──────────────────┐
│          │                │  applications    │
└──────────┘                ├──────────────────┤
│      (relation)           │ id: int (PK)     │
│                           │ name: str        │
                            │ description: str │
                            │ version: str     │
                            │ category: str    │
                            │ platform: enum   │
                            │ icon_file_id: str│
                            │ image_url: url   │
                            │ devupload_url    │
                            │ shrankme_url     │
                            │ downloads: int   │
                            │ views: int       │
                            │ active: bool     │
                            │ published: bool  │
                            │ created_at: date │
                            └──────────────────┘
                                    │
                                    │
                            ┌───────┴────────┐
                            │                │
                      ┌──────▼──────┐  ┌─────▼──────┐
                      │   Stats     │  │   Group    │
                      ├─────────────┤  ├────────────┤
                      │ app_id: FK  │  │ id: int    │
                      │ views: int  │  │ rules: str │
                      │ downloads   │  │ welcome    │
                      │ rating: avg │  │ config     │
                      └─────────────┘  └────────────┘
```

---

## 🔌 التكاملات الخارجية

```
┌─────────────────────────────────────┐
│      Waleed Zone Bot                │
└────────────┬────────────────────────┘
             │
    ┌────────┼────────┬────────┬─────────┐
    │        │        │        │         │
    ▼        ▼        ▼        ▼         ▼
  ┌──┐   ┌──┐    ┌──┐    ┌──┐      ┌──┐
  │📱│   │☁️│    │🔗│    │🖼️│      │💾│
  └──┘   └──┘    └──┘    └──┘      └──┘
  Telegram DevUploads ShrinkMe ImgBB PostgreSQL
    API     (hosting) (shortner) (images) (Cloud)

Telegram API:
- تحميل الملفات من المستخدمين
- إرسال الرسائل والأزرار
- إدارة الأعضاء

DevUploads:
- رفع ملفات التطبيقات الكبيرة
- الحصول على روابط دائمة

ShrinkMe.io:
- تقصير الروابط الطويلة
- تتبع الضغطات (اختياري)

ImgBB:
- رفع الصور (أيقونات التطبيقات)
- استضافة الصور مجاناً

PostgreSQL:
- قاعدة بيانات قوية للإنتاج
- تخزين آمن للبيانات
```

---

## 🚀 دورة حياة الرسالة (Message Lifecycle)

```
1. Telegram User
   ├─ أرسل /start أو اضغط زر

2. Telegram Bot API
   ├─ استقبل الحدث
   ├─ أرسل للـ Bot

3. Dispatcher (aiogram)
   ├─ معالج الأحداث الرئيسي
   └─ وجد المعالج المناسب

4. Middlewares (بالترتيب)
   ├─ DbSessionMiddleware    ← توفير جلسة DB
   ├─ AccessMiddleware       ← التحقق من الصلاحيات
   └─ ThrottleMiddleware     ← منع الإغراق

5. Handler Function
   ├─ استقبال الرسالة
   ├─ معالجة الطلب
   ├─ استدعاء Services إن لزم
   └─ استدعاء Repositories للـ DB

6. Database Query
   ├─ SELECT/INSERT/UPDATE
   └─ إرجاع النتيجة

7. Response Building
   ├─ تصميم الرد
   ├─ إضافة الأزرار والتنسيق
   └─ إرسال الرد

8. Telegram API
   ├─ إرسال الرسالة للمستخدم
   └─ تسجيل الحدث

9. User Screen
   └─ ✅ المستخدم يرى الرد
```

---

✨ **تمت!** أنت الآن تفهم معمارية البوت بشكل كامل! 🎉

