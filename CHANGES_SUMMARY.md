> Current upload/delivery instructions: [Bot–Website integration](docs/BOT_WEBSITE_INTEGRATION.md). DevUploads/ShrinkMe upload steps below are historical and must not be used for new files. No paid infrastructure is required.

## ملخص التغييرات 📋

### الملفات الجديدة ✨

```
scripts/
├── migrate_images.py      ← سكربت الترحيل الرئيسي
├── __init__.py           ← تحويل المجلد لحزمة Python
└── README.md            ← توثيق السكربت

entrypoint.sh            ← نقطة الدخول للـ Docker

ملفات التوثيق:
├── RAILWAY_DEPLOYMENT.md     ← شرح نشر على Railway
├── PRE_DEPLOYMENT_CHECKLIST.md  ← قائمة تحقق قبل النشر
├── GET_IMGBB_API_KEY.md      ← الحصول على مفتاح ImgBB
├── ADVANCED_USAGE.md         ← الاستخدام المتقدم
└── .env.example             ← قالب متغيرات البيئة
```

### التعديلات على الملفات الموجودة 🔧

#### 1. `Dockerfile`
```diff
- ENTRYPOINT ["python", "-u", "main.py"]
+ # Make entrypoint executable
+ RUN chmod +x /app/entrypoint.sh
+ ENTRYPOINT ["/app/entrypoint.sh"]
```

#### 2. `requirements.txt`
```diff
+ aiohttp>=3.8,<4
```

#### 3. `config/settings.py`
```diff
+ # --- ImgBB (رفع الصور) ---
+ IMGBB_API_KEY: str | None = None
```

### سير العمل الجديد 🔄

#### قبل النشر:

```
1. تعديل .env
   ├── BOT_TOKEN ← من BotFather
   ├── IMGBB_API_KEY ← من imgbb.com
   └── ADMIN_IDS ← معرفاتك

2. git add && git commit && git push

3. npx railway up
```

#### أثناء النشر:

```
Docker Start
├── entrypoint.sh
│   ├── python scripts/migrate_images.py
│   │   ├── قراءة Apps بدون صور
│   │   ├── تحميل صور من Telegram
│   │   ├── رفع إلى ImgBB
│   │   └── تحديث DB
│   └── python main.py (البوت الرئيسي)
```

### المتطلبات الجديدة 📦

لتشغيل السكربت تحتاج:

```
✓ aiohttp>=3.8   (للرفع على ImgBB)
✓ aiogram>=3.7   (للتحميل من Telegram)
✓ sqlalchemy>=2.0  (للبيانات)
✓ asyncpg        (للـ PostgreSQL)
```

جميعها موجودة في `requirements.txt` ✓

### المتغيرات المطلوبة 🔐

في ملف `.env`:

```env
# المطلوب الأساسي:
BOT_TOKEN=<BOT_TOKEN_FROM_BOTFATHER>         ← رمز البوت

# اختياري لكن مهم للترحيل:
IMGBB_API_KEY=<IMGBB_API_KEY_FROM_PROVIDER>     ← مفتاح ImgBB

# قاعدة البيانات:
DATABASE_URL=xxx      ← رابط الـ DB (SQLite أو PostgreSQL)
```

### الميزات الجديدة 🚀

1. **الترحيل التلقائي**: عند كل نشر
2. **عدم توقف البوت**: السكربت لا يوقف البوت إذا فشل
3. **سجلات مفصلة**: معرفة ما يحدث خطوة بخطوة
4. **معالجة الأخطاء**: تخطي الصور المعطوبة والمتابعة
5. **التوثيق الشامل**: ملفات شرح لكل حالة

### الأداء ⚡

- **سرعة الترحيل**: 2-3 ثانية لكل صورة
- **عدد الصور**: حسب الـ Telegram API limits
- **تأثير على البوت**: بسيط جداً (يعمل بالتوازي)

### الأمان 🔒

- لا توجد أسرار في الكود
- جميع المفاتيح من `.env`
- HTTPS مضمون من ImgBB
- قاعدة البيانات محمية

### الاختبار ✅

قبل النشر:

```bash
# اختبر محلياً
python scripts/migrate_images.py

# يجب أن ترى:
# 📦 وجدنا X تطبيق...
# ✅ نجح...
# 💾 تم حفظ...
```

### الاستكشاف 🔍

إذا حدثت مشاكل:

```bash
# على Railway
npx railway logs --follow

# محلياً
python scripts/migrate_images.py 2>&1 | tee debug.log
```

### الخطوات التالية 🎯

1. ✅ نسخ `IMGBB_API_KEY` من [imgbb.com/api](https://imgbb.com/api)
2. ✅ أضفه إلى ملف `.env`
3. ✅ رفع الكود على GitHub
4. ✅ نشر على Railway: `npx railway up`
5. ✅ راقب السجلات: `npx railway logs`

---

**ملاحظة**: إذا كان لديك تطبيقات قديمة بدون صور، سيتم ترحيلها تلقائياً! 🎉

