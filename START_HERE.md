> Current upload/delivery instructions: [Bot–Website integration](docs/BOT_WEBSITE_INTEGRATION.md). DevUploads/ShrinkMe upload steps below are historical and must not be used for new files. No paid infrastructure is required.

## 📚 مرحباً بك في Waleed Zone Bot!

هنا ملخص سريع لكل ما تحتاج معرفته لتشغيل البوت محلياً. 🚀

---

## 🎯 أول شيء: اقرأ هذا!

### أنت تريد:
- ✅ **تشغيل البوت محلياً؟** ← اقرأ `LOCAL_DEVELOPMENT.md`
- 🗺️ **فهم معمارية البوت؟** ← اقرأ `BOT_ARCHITECTURE.md`
- 🧪 **اختبار البوت؟** ← اقرأ `LOCAL_TESTING_CHECKLIST.md`
- 🌐 **نشر على Railway؟** ← اقرأ `RAILWAY_DEPLOYMENT.md`
- 🖼️ **خريطة بصرية للبوت؟** ← اقرأ `ARCHITECTURE_VISUAL_MAP.md`

---

## ⚡ البدء السريع (5 دقائق)

```bash
# 1. انسخ الملف
copy .env.example .env

# 2. أضف بيانات الاتصال (اختياري لـ SQLite)
# افتح .env وأضف:
# BOT_TOKEN=<BOT_TOKEN_FROM_BOTFATHER> BotFather
# ADMIN_IDS=معرفك على تيليجرام

# 3. أنشئ بيئة افتراضية
python -m venv venv

# 4. فعّل البيئة
.\venv\Scripts\Activate.ps1   # Windows
# أو
source venv/bin/activate      # Linux/Mac

# 5. ثبّت المتطلبات
pip install -r requirements.txt

# 6. شغّل البوت!
python main.py
```

✅ يجب أن ترى: `✅ Waleed Zone Bot is running...`

---

## 📋 الملفات المهمة

### للتطوير والاختبار

| الملف | الوصف | الوقت |
|------|-------|------|
| `LOCAL_DEVELOPMENT.md` | دليل كامل للتشغيل المحلي | 15 دقيقة |
| `LOCAL_TESTING_CHECKLIST.md` | قائمة اختبار شاملة | 13 دقيقة |
| `BOT_ARCHITECTURE.md` | شرح معمارية البوت | 10 دقائق |
| `ARCHITECTURE_VISUAL_MAP.md` | خرائط بصرية | 5 دقائق |

### للإنتاج

| الملف | الوصف |
|------|-------|
| `RAILWAY_DEPLOYMENT.md` | نشر على Railway |
| `PRE_DEPLOYMENT_CHECKLIST.md` | قائمة تحقق قبل النشر |
| `CHANGES_SUMMARY.md` | ملخص التغييرات الجديدة |
| `ADVANCED_USAGE.md` | استخدامات متقدمة |

### التكوين

| الملف | الوصف |
|------|-------|
| `.env.example` | قالب متغيرات البيئة |
| `config/settings.py` | خيارات البوت |
| `requirements.txt` | حزم Python المطلوبة |

---

## 🔑 المتطلبات الأساسية

### ملفات البيانات المطلوبة

```env
BOT_TOKEN=<BOT_TOKEN_FROM_BOTFATHER>
ADMIN_IDS=معرفك_على_تيليجرام
IMGBB_API_KEY=<IMGBB_API_KEY_FROM_PROVIDER>
DATABASE_URL=sqlite+aiosqlite:///bot.db (للتطوير المحلي)
```

### الحصول عليها:

1. **BOT_TOKEN**: [اذهب لـ BotFather](https://t.me/botfather) اضغط `/newbot`
2. **ADMIN_IDS**: أرسل `/id` لأي بوت على تيليجرام
3. **IMGBB_API_KEY**: [اذهب إلى imgbb.com/api](https://imgbb.com/api)
4. **DATABASE_URL**: استخدم SQLite محلياً (افتراضي)

---

## 🗂️ هيكل المشروع بسرعة

```
handlers/     ← معالجات الأوامر والرسائل
services/     ← منطق تجاري معقد
middlewares/  ← فحوصات أمان وتحكم
states/       ← حالات الحوارات (FSM)
database/     ← تعريف الجداول وعمليات CRUD
```

---

## 🚀 خطوات التشغيل (تفصيل)

### المرة الأولى فقط:

```bash
# 1. فتح Terminal/PowerShell بالمجلد
cd path/to/mytelebot

# 2. إنشاء البيئة الافتراضية
python -m venv venv

# 3. تفعيل البيئة (كل مرة تفتح Terminal جديد)
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate     # Linux/Mac

# 4. نسخ الإعدادات
copy .env.example .env       # Windows
cp .env.example .env         # Linux/Mac

# 5. تعديل .env (أضف البيانات المطلوبة)
# افتح .env بـ أي محرر نصوص
# BOT_TOKEN=<BOT_TOKEN_FROM_BOTFATHER> (اسأل BotFather)
# ADMIN_IDS=... (اكتب معرفك)

# 6. تثبيت الحزم (بطيء قليلاً)
pip install --upgrade pip
pip install -r requirements.txt
```

### كل مرة تريد تشغيل البوت:

```bash
# تفعيل البيئة (إذا لم تكن مفعلة)
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate     # Linux/Mac

# شغّل!
python main.py

# ستشوف:
# ✅ Waleed Zone Bot is running...
# 🤖 Ready to receive messages
```

---

## ✅ للتحقق من الاستعداد

```python
# في Terminal جديد (بعد تفعيل venv):

# 1. تحقق من Python
python --version          # يجب أن يكون 3.11+

# 2. تحقق من الحزم
pip list | grep aiogram   # يجب أن تشوفها

# 3. تحقق من .env
cat .env                  # يجب أن يحتوي البيانات

# 4. تحقق من الاتصال
python -c "from config import get_settings; print(get_settings().BOT_TOKEN[:20])"
# يجب أن يطبع أول 20 حرف من التوكن
```

---

## 🐛 مشاكل شائعة وحلها

| المشكلة | الحل |
|--------|-----|
| `ModuleNotFoundError` | فعّل البيئة: `.\venv\Scripts\Activate.ps1` |
| `BOT_TOKEN not found` | أضفه في `.env` |
| `Port already in use` | البوت لا يستخدم port عادي (لا تقلق) |
| Database locked | اوقف البوت واحذف `bot.db` |
| Timeout | تحقق من الإنترنت |

---

## 🎓 الخطوات الموصى بها

### اليوم الأول:
1. ☑️ اقرأ `BOT_ARCHITECTURE.md` (فهم البنية)
2. ☑️ شغّل البوت محلياً `python main.py`
3. ☑️ جرّب `/start` على تيليجرام

### اليوم الثاني:
1. ☑️ اقرأ `LOCAL_TESTING_CHECKLIST.md`
2. ☑️ اختبر كل ميزة
3. ☑️ جرّب إضافة تطبيق (إذا كنت أدمن)

### قبل النشر:
1. ☑️ اقرأ `RAILWAY_DEPLOYMENT.md`
2. ☑️ اقرأ `PRE_DEPLOYMENT_CHECKLIST.md`
3. ☑️ تأكد من كل شيء يعمل محلياً

---

## 🔗 الموارد المفيدة

### التوثيق الرسمي:
- [aiogram docs](https://docs.aiogram.dev/) - مكتبة البوت
- [SQLAlchemy docs](https://docs.sqlalchemy.org/) - قاعدة البيانات
- [Telegram Bot API](https://core.telegram.org/bots/api) - Telegram

### أدوات مساعدة:
- [BotFather](https://t.me/botfather) - إنشاء البوتات
- [API Tester](https://core.telegram.org/bots/api#testing-your-bot) - اختبار API

---

## 🎯 أهداف تطويرية

بعد أن تشغّل البوت:

- [ ] استطعت تشغيل البوت محلياً
- [ ] فهمت معمارية البوت
- [ ] اختبرت كل الميزات
- [ ] أضفت تطبيق جديد (كأدمن)
- [ ] نشرت على Railway بنجاح

## 💡 نصائح من الخبراء

1. **استخدم SQLite محلياً**: أسرع للتطوير
2. **استخدم PostgreSQL للإنتاج**: أقوى وآمن
3. **اختبر دائماً محلياً**: قبل النشر
4. **اجعل السجلات مفصلة**: `python -u main.py 2>&1 | tee bot.log`
5. **احفظ `.env` بشكل آمن**: لا تنشره على GitHub

---

## 📞 تحتاج مساعدة؟

1. **صعوبة تشغيل:** اقرأ `LOCAL_DEVELOPMENT.md`
2. **أخطاء أثناء التشغيل:** اقرأ السجلات بعناية
3. **مشاكل معمارية:** اقرأ `BOT_ARCHITECTURE.md`
4. **أخطاء قاعدة بيانات:** اقرأ `ADVANCED_USAGE.md`

---

## 🎉 وأخيراً

أنت الآن لديك كل ما تحتاج لتطوير وتشغيل البوت!

```
✨ Happy Coding! ✨

🚀 السير: python main.py
📚 التعليم: اقرأ الملفات أعلاه
🧪 الاختبار: تابع LOCAL_TESTING_CHECKLIST.md
🌐 النشر: تابع RAILWAY_DEPLOYMENT.md
```

---

**ملحوظة**: كل ملف من الملفات أعلاه يحتوي على معلومات كاملة ومفصلة. 
اقرأها بهدوء وستصبح خبيراً بالبوت! 🎓

