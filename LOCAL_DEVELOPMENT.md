> Current upload/delivery instructions: [Bot–Website integration](docs/BOT_WEBSITE_INTEGRATION.md). DevUploads/ShrinkMe upload steps below are historical and must not be used for new files. No paid infrastructure is required.

## 🚀 دليل التشغيل المحلي

الدليل الشامل لتشغيل **Waleed Zone Bot** على جهازك المحلي بخطوات سهلة.

---

## المتطلبات الأساسية 📋

### البرامج المطلوبة

- **Python 3.11+** - [تحميل](https://www.python.org/downloads/)
- **Git** - [تحميل](https://git-scm.com/)
- **PostgreSQL** (اختياري - يمكنك استخدام SQLite)

### التحقق من التثبيت

```bash
# تحقق من إصدارات البرامج
python --version    # يجب أن يكون 3.11 أو أعلى
pip --version
git --version
```

---

## خطوات التثبيت والتشغيل ⚙️

### 1️⃣ استنساخ الريبوزيتوري

```bash
# من Terminal/PowerShell
git clone https://github.com/YOUR_USERNAME/mytelebot.git
cd mytelebot
```

أو إذا كان محلياً:

```bash
cd /path/to/mytelebot
```

### 2️⃣ إنشاء بيئة افتراضية (Virtual Environment)

**على Windows (PowerShell)**:

```powershell
# إنشاء البيئة الافتراضية
python -m venv venv

# تفعيل البيئة
.\venv\Scripts\Activate.ps1

# إذا حصل خطأ بالتوقيع:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\venv\Scripts\Activate.ps1
```

**على Linux/Mac**:

```bash
python3 -m venv venv
source venv/bin/activate
```

✅ يجب أن ترى `(venv)` في بداية السطر بعد التفعيل

### 3️⃣ تثبيت المتطلبات

```bash
# تحديث pip (مهم)
pip install --upgrade pip

# تثبيت كل المكتبات
pip install -r requirements.txt
```

**الحزم المثبتة**:
- `aiogram>=3.7` - مكتبة بناء بوتات تيليجرام
- `sqlalchemy>=2.0` - مكتبة قواعد البيانات
- `httpx>=0.27` - طلبات HTTP غير متزامنة
- `asyncpg` - في معركة PostgreSQL
- `aiohttp>=3.8` - لرفع الصور على ImgBB

### 4️⃣ إعداد ملف `.env`

انسخ ملف القالب وأكمله:

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

**افتح `.env` وعدّل القيم**:

```env
# ✅ المهم جداً
BOT_TOKEN=<BOT_TOKEN_FROM_BOTFATHER>
ADMIN_IDS=7215167792

# ✅ قاعدة البيانات (استخدم SQLite للتطوير المحلي)
DATABASE_URL=sqlite+aiosqlite:///bot.db

# اختياري - للترحيل
IMGBB_API_KEY=<IMGBB_API_KEY_FROM_PROVIDER>

# واختياري - إذا أردت الرفع والتقصير
DEVUPLOAD_API_KEY=xxx
SHRANKME_API_KEY=xxx
```

**أين تجد القيم**:

| المتغير | الحصول عليها من |
|---------|--------|
| `BOT_TOKEN` | [BotFather](https://t.me/botfather) على تيليجرام |
| `ADMIN_IDS` | معرفك على تيليجرام - اكتب `/id` في أي بوت |
| `IMGBB_API_KEY` | [imgbb.com/api](https://imgbb.com/api) |
| `DEVUPLOAD_API_KEY` | [devuploads.com](https://devuploads.com) |
| `SHRANKME_API_KEY` | [shrinkme.io](https://shrinkme.io) |

### 5️⃣ تهيئة قاعدة البيانات

```bash
# البوت ينشئ الجداول تلقائياً عند البدء
# لكن يمكنك اختبار الاتصال:

python -c "
from config import get_settings
from database import init_db
import asyncio

async def test():
    settings = get_settings()
    db = init_db(settings.DATABASE_URL)
    await db.init_models()
    print('✅ قاعدة البيانات جاهزة!')
    await db.close()

asyncio.run(test())
"
```

### 6️⃣ تشغيل البوت 🤖

```bash
# تأكد أن البيئة الافتراضية مفعلة (venv)
python main.py
```

**يجب أن ترى**:

```
✅ Waleed Zone Bot is running...
```

**للتوقف**: اضغط `Ctrl + C`

---

## اختبار البوت ✅

### 1. اختبر على تيليجرام

أرسل `/start` للبوت:
- يجب أن ترى القائمة الرئيسية
- جرّب البحث والتصفح إذا كان لديك تطبيقات

### 2. اختبر كمالك (Admin)

إذا أضفت معرفك في `ADMIN_IDS`:

```bash
# أرسل أي رسالة للبوت
# يجب أن تقدر تشوف قائمة الإدارة
```

### 3. اختبر سكربت الترحيل (اختياري)

```bash
# إذا كان عندك تطبيقات بدون صور
python scripts/migrate_images.py

# يجب أن ترى:
# 📦 وجدنا X تطبيق...
# ✅ تم حفظ...
```

---

## الأوامر المفيدة 🛠️

### تشغيل البوت مع Logging مفصل

```bash
# يعطيك معلومات مفصلة عما يحتري
python main.py --log-level DEBUG

# أو مباشرة (بدون تعديل كود):
python -u main.py 2>&1 | tee bot.log
```

### حذف قاعدة البيانات وإعادة إنشاء جديدة

```bash
# Windows
del bot.db

# Linux/Mac
rm bot.db

# ثم شغّل البوت مرة أخرى
python main.py
```

### فحص ما في قاعدة البيانات (SQLite)

```bash
# افتح قاعدة البيانات
sqlite3 bot.db

# في قاعدة البيانات (sqlite3 prompt):
.tables                           # اعرض الجداول
SELECT * FROM applications;       # اعرض التطبيقات
SELECT * FROM users;             # اعرض المستخدمين
.exit                            # اخرج
```

### تثبيت حزمة واحدة

```bash
pip install package_name
pip install --upgrade package_name
```

### تحديث كل الحزم

```bash
pip install -r requirements.txt --upgrade
```

---

## مشاكل طبيعية وحلولها 🐛

### المشكلة: `ModuleNotFoundError: No module named 'aiogram'`

```
❌ ModuleNotFoundError: No module named 'aiogram'
```

**الحل**:

```bash
# 1. تأكد أن البيئة الافتراضية مفعلة
# (يجب أن ترى (venv) في بداية السطر)

# 2. أعد تثبيت المتطلبات
pip install -r requirements.txt
```

### المشكلة: `BOT_TOKEN غير موجود في ملف .env`

```
❌ BOT_TOKEN غير موجود في ملف .env
```

**الحل**:

```bash
# 1. تأكد من وجود ملف .env
ls .env  # أو dir .env على Windows

# 2. افتح .env وتحقق أن BOT_TOKEN موجود فيه:
cat .env  # أو type .env على Windows

# 3. إذا كان المجلد خطأ، انسخ .env.example:
copy .env.example .env  # Windows
cp .env.example .env    # Linux/Mac
```

### المشكلة: `Timeout waiting for Telegram`

```
❌ Timeout waiting for Telegram API
```

**الحل**:

```bash
# تأكد من اتصالك بالإنترنت

# جرّب الريستارت:
# اضغط Ctrl + C ثم python main.py مرة أخرى

# تحقق من صحة البوت توكن (قد يكون قديم)
# اطلب واحد جديد من BotFather
```

### المشكلة: `Address already in use` أو Port مشغول

```
❌ Address already in use: ('127.0.0.1', 8000)
```

**الحل**: البوت لا يستخدم port محدد عادة، لكن إذا حصل:

```bash
# جد العملية المشغولة وأوقفها
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac:
lsof -i :8000
kill -9 <PID>
```

---

## النمط اليومي للتطوير 📅

```bash
# 1. في الصباح - افتح Terminal بالمجلد
cd /path/to/mytelebot

# 2. فعّل البيئة الافتراضية
.\venv\Scripts\Activate.ps1  # Windows
# أو
source venv/bin/activate      # Linux/Mac

# 3. شغّل البوت
python main.py

# 4. افتح Terminal جديد وعدّل الملفات بـ VS Code

# 5. عندما تعدّل handler أو service:
# - البوت يقبل الأوامر الجديدة بعد restart
# - اضغط Ctrl+C في Terminal
# - شغّل python main.py مرة أخرى

# 6. في النهاية - اضغط Ctrl+C في Terminal واغلقه
```

---

## الملفات المهمة للتطوير 📝

| الملف | الوصف |
|-----|-------|
| `main.py` | نقطة بدء البوت |
| `app/handlers/` | معالجات الأوامر والرسائل |
| `config/settings.py` | الإعدادات العامة |
| `database/models.py` | نماذج قواعد البيانات |
| `.env` | متغيرات البيئة السرية |
| `bot.db` | قاعدة البيانات (محلياً) |

---

✨ **الآن أنت جاهز!** شغّل `python main.py` واستمتع بتطوير البوت!

