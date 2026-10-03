> Current upload/delivery instructions: [Bot–Website integration](docs/BOT_WEBSITE_INTEGRATION.md). DevUploads/ShrinkMe upload steps below are historical and must not be used for new files. No paid infrastructure is required.

## 🚀 خريطة سريعة: من الصفر إلى البوت يعمل

هذا ملف يختصر كل خطوات التشغيل في صفحة واحدة.

---

## ⚡ 3 خطوات فقط (10 دقائق)

### خطوة 1️⃣ : التحضير (2 دقيقة)

```bash
# افتح Terminal/PowerShell
cd path/to/mytelebot

# أنشئ بيئة افتراضية
python -m venv venv

# فعّلها
.\venv\Scripts\Activate.ps1    # Windows
# أو
source venv/bin/activate       # Linux/Mac

# يجب أن تشوف: (venv) في بداية السطر
```

### خطوة 2️⃣ : التثبيت (5 دقائق)

```bash
# تحديث PIP
pip install --upgrade pip

# تثبيت المتطلبات
pip install -r requirements.txt

# الانتظار قليلاً حتى ينتهي...
```

### خطوة 3️⃣ : التشغيل (1 دقيقة)

```bash
# شغّل البوت!
python main.py

# ستشوف:
# ✅ Waleed Zone Bot is running...
```

**خلاص! البوت يعمل الآن!** 🎉

افتح تيليجرام وأرسل `/start` للبوت.

---

## 📝 ملفات التوثيق المهمة

### للبدء:
- **START_HERE.md** ← مرحباً! اقرأني أول شيء
- **BOT_ARCHITECTURE.md** ← فهم معمارية البوت
- **ARCHITECTURE_VISUAL_MAP.md** ← خرائط بصرية

### للتطوير:
- **LOCAL_DEVELOPMENT.md** ← شرح مفصل للتشغيل
- **LOCAL_TESTING_CHECKLIST.md** ← اختبر كل شيء

### للنشر:
- **RAILWAY_DEPLOYMENT.md** ← نشر على Railway
- **PRE_DEPLOYMENT_CHECKLIST.md** ← قبل النشر
- **ADVANCED_USAGE.md** ← استخدامات متقدمة

---

## 🔑 نقاط حساسة

### البيانات المطلوبة

لتشغيل البوت محلياً تحتاج **فقط** إلى:

```env
BOT_TOKEN=من_BotFather
```

الباقي اختياري (اتركه كما هو في .env.example).

### الحصول على BOT_TOKEN

1. افتح تيليجرام
2. ابحث عن `BotFather`
3. أرسل `/newbot`
4. اتبع الخطوات
5. انسخ التوكن إلى `.env`

---

## 🐛 مشاكل التشغيل

| المشكلة | الحل السريع |
|--------|-----------|
| `Python not found` | ثبّت Python 3.11+ من python.org |
| `(venv) لم يظهر` | الأمر = `.\venv\Scripts\Activate.ps1` |
| `ModuleNotFoundError` | أعد تشغيل الأمر: `pip install -r requirements.txt` |
| `BOT_TOKEN غير موجود` | أضفه في `.env` بالكامل |
| `Timeout` | تحقق من الإنترنت |

---

## ✅ كيفية تأكد أن كل شيء يعمل؟

```bash
# 1. البوت يعمل؟
# (يجب أن ترى: ✅ Waleed Zone Bot is running...)

# 2. على تيليجرام:
# أرسل /start للبوت
# يجب أن ترى القائمة الرئيسية

# 3. يعمل تماماً! 🎉
# جاهز للتطوير والاختبار
```

---

## 📚 ماذا تفعل الآن؟

### إذا أردت **تطوير** الكود:
```
اقرأ: LOCAL_DEVELOPMENT.md
حينها: عدّل الملفات وأعد تشغيل python main.py
```

### إذا أردت **اختبار** كل الميزات:
```
اقرأ: LOCAL_TESTING_CHECKLIST.md
جرّب كل زر وميزة
```

### إذا أردت **نشر** على الإنتاج:
```
اقرأ: RAILWAY_DEPLOYMENT.md
ثم: PRE_DEPLOYMENT_CHECKLIST.md
أخيراً: npx railway up
```

---

## 🗂️ ملفات تحتاج أن تعرفها

```
.env               ← ⚠️ لا تنسخه على GitHub (سرار!)
.env.example       ← القالب (انسخه إلى .env)
requirements.txt   ← المكتبات المطلوبة
main.py           ← 🎯 نقطة البدء (كل getattr يرجع هنا)
Dockerfile        ← لـ Docker (للإنتاج)
scripts/          ← سكريبتات مساعدة (ترحيل الصور)
```

---

## 💻 الأوامر المهمة

```bash
# تشغيل البوت
python main.py

# اختبار البوت (بدون تشغيل سجلات)
python main.py --log-level INFO

# ترحيل الصور (اختياري)
python scripts/migrate_images.py

# فحص قاعدة البيانات
sqlite3 bot.db ".tables"

# حذف وإعادة إنشاء DB
rm bot.db
python main.py
```

---

## 🎯 خريطة المسار السريع

```
START_HERE.md
        │
        ├─► تفهم البنية
        │   └─► BOT_ARCHITECTURE.md
        │
        ├─► تشغيل محلياً
        │   └─► LOCAL_DEVELOPMENT.md
        │
        ├─► اختبار الميزات
        │   └─► LOCAL_TESTING_CHECKLIST.md
        │
        └─► نشر على الإنتاج
            └─► RAILWAY_DEPLOYMENT.md
```

---

## 🔗 الملفات الضرورية الآن

```
✅ .env (حالياً يحصل من .env.example)
✅ requirements.txt (حزم Python)
✅ main.py (نقطة البدء)
✅ Dockerfile (بـ entrypoint جديد)
✅ scripts/migrate_images.py (ترحيل الصور)
```

---

## 💚 النصائح الذهبية

1. **شغّل محلياً أولاً** قبل أي نشر
2. **اقرأ السجلات** عند حدوث أخطاء
3. **قم بـ Backup** قبل التعديلات الكبيرة
4. **استخدم Git** لحفظ التغييرات
5. **لا تنسيَ .env** في `.gitignore`

---

## 🎉 جاهز؟

```bash
python main.py
```

**هيا! شغّل البوت وابدأ التطوير!** 🚀

---

**ملحوظة نهائية**: كل الملفات الأخرى تحتوي على معلومات مفصلة جداً.
اقرأها عند الحاجة. الآن ركّز على **python main.py** فقط! ⚡

