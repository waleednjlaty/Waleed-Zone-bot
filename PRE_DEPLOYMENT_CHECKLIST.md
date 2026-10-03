> Current upload/delivery instructions: [Bot–Website integration](docs/BOT_WEBSITE_INTEGRATION.md). DevUploads/ShrinkMe upload steps below are historical and must not be used for new files. No paid infrastructure is required.

## قائمة التحقق قبل النشر ✅

استخدم هذه القائمة قبل نشر البوت على Railway.

### الإعدادات المحلية 🏠

- [ ] تم نسخ `.env.example` إلى `.env`
- [ ] أضفت `BOT_TOKEN` الصحيح
- [ ] أضفت `IMGBB_API_KEY` من [imgbb.com](https://imgbb.com)
- [ ] أضفت `ADMIN_IDS` (معرفات المالكين)
- [ ] اختبرت البوت محلياً: `python main.py`
- [ ] اختبرت السكربت: `python scripts/migrate_images.py`
- [ ] لا توجد أخطاء في السجلات 📜

### ملفات المشروع 📁

- [ ] التأكد من وجود جميع الملفات:
  - `scripts/migrate_images.py` ✓
  - `scripts/__init__.py` ✓
  - `entrypoint.sh` ✓
  - `Dockerfile` (جديد مع entrypoint)
  - `requirements.txt` (يحتوي على aiohttp)
  - `config/settings.py` (يحتوي على IMGBB_API_KEY)
  - `.env.example` ✓

- [ ] تحديث `requirements.txt`:
  ```
  aiohttp>=3.8,<4  # ✓ موجود
  ```

### أوامر Git 🔄

```bash
# 1. إضافة الملفات الجديدة
git add scripts/ entrypoint.sh RAILWAY_DEPLOYMENT.md .env.example

# 2. تحديث الملفات الموجودة
git add Dockerfile requirements.txt config/settings.py

# 3. التأكد من التغييرات
git status
# يجب أن ترى:
# new file: scripts/migrate_images.py
# new file: scripts/__init__.py
# new file: scripts/README.md  
# new file: entrypoint.sh
# new file: RAILWAY_DEPLOYMENT.md
# new file: .env.example
# modified: Dockerfile
# modified: requirements.txt
# modified: config/settings.py

# 4. الحفظ
git commit -m "Add image migration script for deployment"
git push origin main
```

### إعدادات Railway 🚀

قبل النشر:

- [ ] قمت بـ `npx railway login`
- [ ] قمت بـ `npx railway init` واخترت PostgreSQL
- [ ] أضفت المتغيرات في Dashboard:
  - [ ] `BOT_TOKEN`
  - [ ] `IMGBB_API_KEY`
  - [ ] `ADMIN_IDS`
  - [ ] `DATABASE_URL` (يُعيّن من PostgreSQL)
- [ ] تحققت من ملف `railway.toml` في المشروع

### النشر 🎯

```bash
# نشر المشروع
npx railway up

# أو عبر Dashboard:
# 1. اذهب إلى GitHub
# 2. اضغط Deploy
# 3. اختر branch: main
```

### بعد النشر ✨

- [ ] الملاحظة الأولى: يعمل السكربت (تفحص السجلات)
- [ ] وجود رسالة: `📦 وجدنا X تطبيق بحاجة لترحيل`
- [ ] وجود رسالة: `✅ Waleed Zone Bot is running...`
- [ ] اختبار البوت: أرسل `/start` للبوت
- [ ] التحقق من السجلات: `npx railway logs`

### استكشاف الأخطاء 🐛

إذا حدث خطأ:

```bash
# عرض السجلات الكاملة
npx railway logs --follow

# إعادة تشغيل
npx railway redeploy

# التحقق من المتغيرات
npx railway variables
```

---

**نصيحة ذهبية**: احفظ هذه القائمة في bookmark! 🔖

