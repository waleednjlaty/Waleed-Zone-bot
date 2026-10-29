#!/bin/sh
# نقطة الدخول: الترحيل اختياري ويحتاج تفعيلًا صريحًا، ثم يبدأ البوت.

set -e

echo "🚀 بدء تشغيل Waleed Zone Bot..."

# ترحيل الصور يغيّر سجلات التطبيقات ويتصل بخدمة خارجية؛ لا نشغّله مع كل نشر افتراضيًا.
# لتشغيله عمدًا في عملية صيانة محددة، فعّل RUN_IMAGE_MIGRATION_ON_STARTUP=true.
if [ "${RUN_IMAGE_MIGRATION_ON_STARTUP:-false}" = "true" ]; then
  echo "📦 بدء ترحيل الصور بطلب صريح..."
  if python scripts/migrate_images.py; then
    echo "✅ اكتملت محاولة ترحيل الصور."
  else
    echo "⚠️ تعذّر ترحيل بعض الصور؛ سيستمر تشغيل البوت."
  fi
else
  echo "⏭️ تم تخطي ترحيل الصور التلقائي (غير مفعّل)."
fi

echo "🤖 تشغيل البوت..."
exec python -u main.py
