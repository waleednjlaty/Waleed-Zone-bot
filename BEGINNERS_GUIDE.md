> Current upload/delivery instructions: [Bot–Website integration](docs/BOT_WEBSITE_INTEGRATION.md). DevUploads/ShrinkMe upload steps below are historical and must not be used for new files. No paid infrastructure is required.

## 🎓 دليل المبتدئين - خطوة بخطوة

دليل شامل وسهل للمبتدئين الذين لم يشغّلوا البوت من قبل.

---

## ✅ قبل البدء - ما الذي تحتاج؟

### البرامج المطلوبة

❌ **لا تفعل هذا قبل قراءة الملف!**

أولاً:
1. ☐ اجعل لديك **Windows 10/11** أو **Linux** أو **Mac**
2. ☐ تأكد أن جهازك متصل بالإنترنت
3. ☐ لديك حساب تيليجرام

ثانياً - ثبّت البرامج:
1. ☐ Python 3.11+ → [python.org](https://www.python.org/downloads/)
2. ☐ Git (اختياري) → [git-scm.com](https://git-scm.com/)
3. ☐ VS Code → [code.visualstudio.com](https://code.visualstudio.com/)

**التحقق**: افتح Terminal واكتب:
```bash
python --version
```
يجب أن يظهر: `Python 3.11.x` أو أعلى

---

## 📋 الخطوة 1: الحصول على البتوكن (10 دقائق)

### اذهب إلى BotFather

```
1. افتح تيليجرام
2. ابحث عن: BotFather
3. اضغط Start
4. أرسل: /newbot
5. اجب على الأسئلة:
   - اسم البوت: Waleed Zone Bot New
   - username: waleed_test_bot (يجب أن ينتهي بـ _bot)
6. انسخ الكود طويل (هو البوت توكن)
```

**مثال التوكن**:
```
<BOT_TOKEN_FROM_BOTFATHER>
```

احفظه بمكان آمن! ☝️

---

## 🎯 الخطوة 2: تحضير المشروع (5 دقائق)

### انقل المشروع لمجلد

```bash
# على Windows (افتح PowerShell):
cd Desktop
mkdir waleed-bot
cd waleed-bot

# انسخ ملفات المشروع هنا (من الـ GitHub أو البريد الإلكتروني)
```

### تحقق أن الملفات موجودة

```bash
# هذه الملفات يجب أن تكون موجودة:
dir  # أو ls على Linux
```

يجب أن تشوف:
- [ ] main.py
- [ ] requirements.txt
- [ ] .env.example
- [ ] app/ (مجلد)
- [ ] database/ (مجلد)
- [ ] config/ (مجلد)

---

## 🔧 الخطوة 3: البيئة الافتراضية (3 دقائق)

البيئة الافتراضية = صندوق منفصل للمكتبات (يحميك من الأخطاء).

### إنشاء البيئة

```powershell
# على Windows:
python -m venv venv

# انتظر قليلاً...
# يجب أن ينتهي بدون أخطاء ✓
```

### تفعيل البيئة

```powershell
# على Windows:
.\venv\Scripts\Activate.ps1

# ستشوف في بداية السطر:
# (venv) C:\Users\...\waleed-bot>
```

**✅ البيئة مفعلة الآن!**

---

## 📦 الخطوة 4: تثبيت المكتبات (5 دقائق)

```bash
# تحديث pip (نظام تثبيت المكتبات)
pip install --upgrade pip

# تثبيت جميع المكتبات المطلوبة
pip install -r requirements.txt

# سيستغرق قليلاً... (5 دقائق تقريباً)
# انتظر حتى ينتهي تماماً
```

ستشوف رسائل زي هيك:
```
Successfully installed aiogram-3.7.0
Successfully installed sqlalchemy-2.0.0
...
```

**✅ المكتبات مثبتة!**

---

## 🔐 الخطوة 5: الإعدادات (2 دقيقة)

### انسخ ملف الإعدادات

**على Windows**:
```bash
copy .env.example .env
```

**على Linux/Mac**:
```bash
cp .env.example .env
```

### عدّل الملف

افتح `.env` بـ Notepad أو VS Code:

```env
BOT_TOKEN=<BOT_TOKEN_FROM_BOTFATHER>

# استبدل PASTE_HERE بالتوكن اللي حصلت عليه من BotFather
# مثال:
BOT_TOKEN=<BOT_TOKEN_FROM_BOTFATHER>

# الباقي لا تعدّله
```

**احفظ الملف!**

---

## 🚀 الخطوة 6: التشغيل! (1 دقيقة)

```bash
# هذا الأمر يشغّل البوت
python main.py

# ستشوف:
# ✅ Waleed Zone Bot is running...
```

### إذا حصل خطأ

```
❌ BOT_TOKEN غير موجود
```

**الحل**: تأكد أنك أضفت التوكن بشكل صحيح في `.env`

```
❌ ModuleNotFoundError: No module named 'aiogram'
```

**الحل**: تأكد من تفعيل البيئة (يجب ترى (venv))

---

## 📱 الاختبار على تيليجرام

### افتح تيليجرام

```
1. ابحث عن معرف البوت الذي أنشأته
   (مثل: @waleed_test_bot)

2. اضغط Start أو /start

3. يجب أن ترى القائمة الرئيسية!
```

### جرّب أنك:
- [ ] اضغط 🔍 بحث
- [ ] اضغط 📱 أحدث
- [ ] اضغط ★ المفضلة
- [ ] اترك رسالة عادية

---

## 🔄 كل مرة تفتح Terminal جديد

```bash
# 1. انتقل للمجلد
cd path/to/waleed-bot

# 2. فعّل البيئة (هام!)
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate     # Linux/Mac

# 3. شغّل البوت
python main.py
```

**نصيحة**: اعمل نفشة Batch File:

**batch_run.bat** (على Windows):
```batch
@echo off
call venv\Scripts\activate.bat
python main.py
pause
```

بعدين انقر عليه = الأوامر كلها تشتغل.

---

## 🎯 أول 10 دقائق = نجاح

```
Goal 1: أشتري Python ✓
Goal 2: انسخ المشروع ✓
Goal 3: أأنشئ البيئة الافتراضية ✓
Goal 4: أثبّت المكتبات ✓
Goal 5: أعدّل .env ✓
Goal 6: صا python main.py ✓
Goal 7: بعت /start على البوت ✓

النتيجة: البوت يعمل! 🎉
```

---

## 📚 الخطوة التالية

بعد التشغيل الناجح:

1. **تعرّف على معمارية البوت**:
   ```
   اقرأ: BOT_ARCHITECTURE.md
   ```

2. **اختبر كل الميزات**:
   ```
   اقرأ: LOCAL_TESTING_CHECKLIST.md
   جرّب كل زر في البوت
   ```

3. **ابدأ التطوير**:
   ```
   اقرأ: LOCAL_DEVELOPMENT.md > ابدأ التعديل على الكود
   ```

---

## 🆘 الأخطاء الشائعة للمبتدئين

### الخطأ 1: Python غير مثبت

```
❌ 'python' is not recognized
```

**التحقق**:
```bash
python --version
```

**الحل**: ثبّت Python من [python.org](https://www.python.org/)

### الخطأ 2: البيئة الافتراضية لم تفعل

```
❌ ModuleNotFoundError
```

**التحقق**: هل ترى `(venv)` في بداية السطر؟

**الحل**:
```bash
.\venv\Scripts\Activate.ps1
```

### الخطأ 3: .env غير موجود

```
❌ EnvFileNotFound
```

**التحقق**: اكتب `dir` وابحث عن .env

**الحل**:
```bash
copy .env.example .env
```

### الخطأ 4: التوكن خطأ

```
❌ Unauthorized
```

**التحقق**: انسخ التوكن من BotFather مرة أخرى

**الحل**: أضفه في .env بشكل صحيح بدون مسافات

---

## 💬 أسئلة شائعة

**س: هل أحتاج إلى قاعدة بيانات منفصلة؟**
ج: لا! البوت ينشئ `bot.db` تلقائياً (SQLite)

**س: هل يمكنني استخدام Python 3.10؟**
ج: الأفضل 3.11+، لكن قد يعمل

**س: كم حجم المشروع؟**
ج: حوالي 100MB مع المكتبات

**س: هل بحتاج إنترنت دائم؟**
ج: نعم، للاتصال بـ Telegram

---

## ✅ ملخص سريع

| الخطوة | الأمر | الوقت |
|-------|-------|------|
| 1. البيئة | `python -m venv venv` | 1 دقيقة |
| 2. التفعيل | `.\venv\Scripts\Activate.ps1` | 10 ثواني |
| 3. المكتبات | `pip install -r requirements.txt` | 5 دقائق |
| 4. الإعدادات | `copy .env.example .env` ثم عدّل | 1 دقيقة |
| 5. الشغّيل | `python main.py` | ∞ (يعمل) |

**الوقت الكلي: 15 دقيقة**

---

## 🎉 تهانينا!

أنت الآن تشغّل **Waleed Zone Bot** محلياً بنجاح! 🚀

الخطوة التالية:
- اقرأ `BOT_ARCHITECTURE.md`
- اختبر الميزات
- ابدأ التطوير

---

**تذكّر**: كل خطأ هو فرصة للتعلم. لا تستسلم! 💪

