> Current upload/delivery instructions: [Bot–Website integration](docs/BOT_WEBSITE_INTEGRATION.md). DevUploads/ShrinkMe upload steps below are historical and must not be used for new files. No paid infrastructure is required.

## نشر على Railway مع الترحيل التلقائي 🚀

### الخطوات 1️⃣

#### 1. تحضير الريبوزيتوري

```bash
git init
git add .
git commit -m "Initial commit with image migration"
git push origin main
```

#### 2. تسجيل الدخول إلى Railway

```bash
npx railway login
```

#### 3. إنشاء مشروع جديد

```bash
npx railway init
```

اختر:
- **New Project**: نعم
- **Add Database**: PostgreSQL (يفضل)
- **Environment**: production

#### 4. تعيين متغيرات البيئة

```bash
# في لوحة تحكم Railway
railway variables set IMGBB_API_KEY=<IMGBB_API_KEY_FROM_PROVIDER>
railway variables set BOT_TOKEN=<BOT_TOKEN_FROM_BOTFATHER>
```

أو عبر الـ Dashboard:
1. اذهب إلى Settings → Variables
2. أضف:
   - `BOT_TOKEN` = رمز البوت
   - `IMGBB_API_KEY` = مفتاح ImgBB
   - `DATABASE_URL` = (يُعيّن تلقائياً من PostgreSQL)
   - `ADMIN_IDS` = معرفات الأدمن

#### 5. نشر المشروع

```bash
npx railway up
```

أو عبر الـ Dashboard:
1. اضغط Deploy
2. اختر الفرع (main)
3. اجلس وانتظر! 🍿

### كيفية الترحيل 📸

عند كل نشر (deployment):

1. **السكربت يعمل أولاً**:
   ```
   📦 فحص ترحيل الصور...
   📦 وجدنا 12 تطبيق بحاجة لترحيل
   [1/12] جاري رفع صورة...
   ✅ نجح...
   ```

2. **ثم البوت يبدأ**:
   ```
   🤖 تشغيل البوت...
   ✅ Waleed Zone Bot is running...
   ```

### التحقق من حالة النشر 🔍

```bash
# عرض السجلات
npx railway logs

# عرض متغيرات البيئة
npx railway variables

# التحقق من حالة الخدمة
npx railway status
```

### استكشاف الأخطاء 🐛

**المشكلة**: `IMGBB_API_KEY غير موجود`
- **الحل**: تأكد من إضافة المتغير في Dashboard

**المشكلة**: `Failed to connect to Telegram`
- **الحل**: جدّد `BOT_TOKEN` إذا كان قديماً

**المشكلة**: `Database connection failed`
- **الحل**: تحقق من صحة `DATABASE_URL` في المتغيرات

### البنية بعد النشر 📁

```
Railway Container
├── scripts/
│   ├── migrate_images.py  ← يعمل أولاً
│   └── __init__.py
├── entrypoint.sh          ← نقطة البدء
├── main.py                ← البوت الرئيسي
├── requirements.txt       ← المتطلبات
└── ... (سائر الملفات)
```

### الأوامر المفيدة 💡

```bash
# تفعيل السكربت يدوياً (بعد النشر)
railway shell
python scripts/migrate_images.py

# عرض قاعدة البيانات
railway shell
psql $DATABASE_URL

# إعادة نشر
npx railway rebuild
```

### التكلفة والحدود 💰

- Railway توفر **600 ساعة شهرياً** مجاناً
- الترحيل يستغرق **دقائق قليلة فقط**
- PostgreSQL مجاني للأول!

---

**تم!** 🎉 بعد النشر، البوت سيترحل الصور تلقائياً عند كل تحديث!

