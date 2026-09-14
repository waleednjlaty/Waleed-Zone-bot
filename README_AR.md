# بوت Waleed Zone

[English](README.md) · [البدء السريع](QUICK_START.md) · [دليل التوثيق](DOCUMENTATION_INDEX.md)

بوت تيليجرام متكامل لإدارة ونشر التطبيقات والألعاب في مجتمع Waleed Zone. يوفر للمستخدمين كتالوجًا قابلًا للبحث، وللمشرف لوحة لإدارة المحتوى ورفعه ونشره، إضافة إلى الطلبات والمفضلة وأدوات حماية المجموعة.

## المزايا

- تصفح التطبيقات والألعاب والبحث عنها وحفظها في المفضلة
- إرسال طلبات التطبيقات وإدارتها
- إضافة المحتوى وتعديله وحذفه ونشره من لوحة المشرف
- تنزيل الملفات من تيليجرام ورفعها إلى خدمة خارجية
- تكاملات اختيارية مع DevUploads وShrinkMe وImgBB
- استخراج روابط الألعاب من SteamRIP
- رسائل ترحيب وحماية من الإغراق وكلمات ممنوعة وتحذير وكتم وحظر
- دعم SQLite محليًا وPostgreSQL عند النشر
- دعم Docker وDocker Compose
- بنية غير متزامنة باستخدام aiogram وSQLAlchemy

## التقنيات

- Python 3.12
- aiogram 3
- SQLAlchemy 2
- SQLite / PostgreSQL
- httpx وaiohttp
- Docker

## التشغيل السريع

### 1. تنزيل المشروع

```bash
git clone https://github.com/waleednjlaty/waleed-zone-bot.git
cd waleed-zone-bot
```

إذا لم تتم إعادة تسمية الريبو بعد، استخدم `MyTelegramBot` بدل `waleed-zone-bot`.

### 2. إنشاء البيئة الافتراضية

على Linux وmacOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

على Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. تثبيت المتطلبات

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. إعداد المتغيرات

على Linux وmacOS:

```bash
cp .env.example .env
```

على Windows:

```powershell
Copy-Item .env.example .env
```

ضع على الأقل القيم التالية داخل `.env`:

```env
BOT_TOKEN=your_bot_token
ADMIN_IDS=123456789
DATABASE_URL=sqlite+aiosqlite:///data/bot.db
```

لا ترفع ملف `.env` الحقيقي أو مفاتيح API إلى GitHub.

### 5. تشغيل البوت

```bash
python main.py
```

افتح البوت في تيليجرام وأرسل `/start`.

## الإعدادات

| المتغير | مطلوب؟ | وظيفته |
|---|---:|---|
| `BOT_TOKEN` | نعم | توكن البوت من [@BotFather](https://t.me/BotFather) |
| `ADMIN_IDS` | مستحسن | معرّفات المشرفين مفصولة بفواصل |
| `DATABASE_URL` | نعم | رابط قاعدة البيانات بصيغة SQLAlchemy |
| `CHANNEL_ID` و`CHANNEL_USERNAME` | للنشر | القناة التي يُنشر إليها المحتوى |
| `GROUP_ID` و`GROUP_USERNAME` | للإشراف | مجموعة المجتمع |
| `DEVUPLOAD_API_KEY` | اختياري | رفع الملفات إلى DevUploads |
| `SHRANKME_API_KEY` | اختياري | اختصار روابط التنزيل |
| `IMGBB_API_KEY` | اختياري | استضافة الصور أو ترحيلها |
| `MAX_UPLOAD_BYTES` | اختياري | الحد الأعلى لحجم الملف |
| `DOWNLOAD_DIR` | اختياري | مسار الملفات المؤقتة |

جميع الخيارات موجودة في [`.env.example`](.env.example).

## التشغيل عبر Docker

```bash
cp .env.example .env
mkdir -p data tmp/uploads logs
docker compose up --build -d
docker compose logs -f
```

لإيقافه:

```bash
docker compose down
```

## الاختبارات وفحص جودة الكود

```bash
pip install pytest pytest-asyncio ruff
pytest
ruff check .
```

## بنية المشروع

```text
.
├── app/
│   ├── handlers/       # الأوامر والرسائل والأزرار
│   ├── keyboards/      # لوحات المفاتيح
│   ├── middlewares/    # قاعدة البيانات والصلاحيات ومنع الإغراق
│   ├── services/       # منطق العمل
│   ├── states/         # حالات FSM
│   └── utils/          # النصوص والثوابت والسجلات والأدوات
├── config/             # إعدادات البيئة
├── database/           # النماذج والجلسات وعمليات البيانات
├── integrations/       # الخدمات الخارجية
├── scripts/            # الصيانة والترحيل
├── tests/              # الاختبارات
├── deploy/             # ملفات النشر
├── main.py             # نقطة التشغيل
└── docker-compose.yml
```

## التوثيق الإضافي

- [ابدأ من هنا](START_HERE.md)
- [دليل المبتدئ](BEGINNERS_GUIDE.md)
- [التطوير المحلي](LOCAL_DEVELOPMENT.md)
- [معمارية البوت](BOT_ARCHITECTURE.md)
- [الخريطة البصرية للمعمارية](ARCHITECTURE_VISUAL_MAP.md)
- [الاستخدام المتقدم](ADVANCED_USAGE.md)
- [قائمة اختبار محلية](LOCAL_TESTING_CHECKLIST.md)
- [النشر على Railway](RAILWAY_DEPLOYMENT.md)
- [قائمة ما قبل النشر](PRE_DEPLOYMENT_CHECKLIST.md)

## الأمان

- احتفظ بالتوكنات والمفاتيح داخل متغيرات البيئة فقط.
- إذا ظهر مفتاح في commit أو سجل أو صورة، ألغِه وأنشئ بديلًا فورًا.
- راجع معرّفات المشرفين وصلاحيات البوت قبل النشر.
- خذ نسخة احتياطية من قاعدة البيانات قبل التحديثات.

## المساهمة

المشكلات وطلبات الدمج مرحب بها. للتغييرات الكبيرة، افتح Issue واشرح السلوك المقترح أولًا.

---

طُوّر ويُصان بواسطة [وليد النجلات](https://github.com/waleednjlaty).
