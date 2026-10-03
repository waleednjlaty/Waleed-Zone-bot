> Current upload/delivery instructions: [Bot–Website integration](docs/BOT_WEBSITE_INTEGRATION.md). DevUploads/ShrinkMe upload steps below are historical and must not be used for new files. No paid infrastructure is required.

## الاستخدام المتقدم والاستكشاف 🔧

### تشغيل السكربت يدوياً 🏃

#### 1. على الجهاز المحلي

```bash
# تثبيت المتطلبات
pip install -r requirements.txt

# تشغيل السكربت
python scripts/migrate_images.py
```

#### 2. داخل Docker Container

```bash
# بناء الـ image
docker build -t waleed-bot .

# تشغيل مع ترحيل الصور
docker run --env-file .env waleed-bot

# أو لتشغيل السكربت فقط
docker run --env-file .env waleed-bot python scripts/migrate_images.py
```

### المراقبة والسجلات 📊

#### عرض سجلات التطبيق

```bash
# للتطوير المحلي
python scripts/migrate_images.py 2>&1 | tee migration.log

# على Railway
npx railway logs --follow
```

#### فحص قاعدة البيانات

```bash
# للـ SQLite
sqlite3 bot.db "SELECT id, name, image_url FROM applications WHERE image_url IS NOT NULL LIMIT 10;"

# للـ PostgreSQL
psql $DATABASE_URL -c "SELECT id, name, image_url FROM applications WHERE image_url IS NOT NULL LIMIT 10;"
```

### الأداء والتحسينات ⚡

#### تحديد عدد الصور للمعالجة

إذا أردت معالجة عدد محدود:

**عدّل `scripts/migrate_images.py`**:

```python
# ابحث عن هذا السطر:
query = select(Application).where(...)

# أضف LIMIT:
query = select(Application).where(...).limit(10)  # ترحيل أول 10 فقط
```

#### معالجة الأخطاء والإعادة

السكربت يتخطى الأخطاء تلقائياً:

```python
try:
    image_url = await imgbb_uploader.upload_telegram_photo(bot, app.icon_file_id)
except Exception as e:
    logger.error(f"خطأ: {e}")
    continue  # ننتقل للصورة التالية
```

### الجدولة الدورية ⏱️

إذا أردت تشغيل الترحيل كل فترة:

#### استخدام Cron (على Linux/Railway)

أنشئ ملف `scripts/scheduler.py`:

```python
import asyncio
from aioschedule import every, run_pending
from migrate_images import migrate_images

async def scheduler():
    """تشغيل الترحيل كل ساعة"""
    every().hour.do(asyncio.create_task, migrate_images())
    
    while True:
        await run_pending()
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(scheduler())
```

#### استخدام APScheduler

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(migrate_images, 'interval', hours=1)
scheduler.start()
```

### الإحصائيات 📈

#### إضافة عداد للصور المترحلة

عدّل `scripts/migrate_images.py`:

```python
# أضف هذا في النهاية:
stats = {
    "total": len(apps),
    "migrated": migrated_count,
    "failed": len(apps) - migrated_count,
    "percentage": (migrated_count / len(apps) * 100) if apps else 0
}

logger.info(f"""
📊 الإحصائيات:
   الإجمالي: {stats['total']}
   مترحل: {stats['migrated']}
   فشل: {stats['failed']}
   النسبة: {stats['percentage']:.1f}%
""")
```

### الاختبار الشامل 🧪

#### سيناريو الاختبار 1: صور موجودة

```bash
# 1. تحقق أن لديك تطبيقات مع icon_file_id
python -c "
from database.database import init_db
from database.models import Application
from sqlalchemy import select
import asyncio

async def check():
    db = init_db('sqlite+aiosqlite:///bot.db')
    async with db.session() as session:
        result = await session.execute(
            select(Application).where(Application.icon_file_id.isnot(None))
        )
        apps = result.scalars().all()
        print(f'تطبيقات مع صور: {len(apps)}')

asyncio.run(check())
"

# 2. شغّل السكربت
python scripts/migrate_images.py

# 3. تحقق من النتائج
python -c "
from database.database import init_db
from database.models import Application
from sqlalchemy import select
import asyncio

async def check():
    db = init_db('sqlite+aiosqlite:///bot.db')
    async with db.session() as session:
        result = await session.execute(
            select(Application).where(Application.image_url.isnot(None))
        )
        apps = result.scalars().all()
        for app in apps:
            print(f'{app.name}: {app.image_url}')

asyncio.run(check())
"
```

### الإصلاح والنظافة 🧹

#### حذف الصور المعطوبة

```python
# اجعل هذا في سكربت منفصل إذا أردت:
query = select(Application).where(
    Application.image_url.isnot(None) & (Application.image_url.like(''))
)
# ثم احذفها من قاعدة البيانات
```

#### التراجع عن الترحيل

```sql
-- حذف روابط ImgBB واحتفظ بـ file_id
UPDATE applications 
SET image_url = NULL 
WHERE image_url LIKE 'https://i.ibb.co%';
```

### تصحيح الأخطاء الشائعة 🐛

#### الخطأ: `FileNotFoundError`

```
❌ Error: /app/scripts/migrate_images.py: No such file or directory
```

**الحل**: تأكد من أن السكربت موجود بالمسار الصحيح

```bash
# تحقق من الملف
ls -la scripts/migrate_images.py

# تأكد من الإذن
chmod +x scripts/migrate_images.py
```

#### الخطأ: `ImgBB API Error`

```
❌ Error migrating FILE_ID: Invalid API key
```

**الحل**: تحقق من المفتاح في `.env`

```bash
echo $IMGBB_API_KEY
# يجب أن يظهر المفتاح
```

#### الخطأ: `Database connection failed`

```
❌ Error: could not connect to server
```

**الحل**: تأكد من `DATABASE_URL`

```bash
# على Railway
npx railway variables | grep DATABASE_URL

# محلياً
grep DATABASE_URL .env
```

---

**وقت المساعدة**: إذا واجهت مشاكل، اطبع السجلات كاملة! 📋

