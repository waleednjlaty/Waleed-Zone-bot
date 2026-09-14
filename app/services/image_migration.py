"""خدمة ترحيل صور التطبيقات إلى ImgBB وربطها بسجل التطبيق.

تُستخدم من:
    - سكربت CLI:  python scripts/migrate_images.py
    - التشغيل التلقائي داخل Docker قبل بدء البوت.

الخدمة تدعم الآن:
    - صور Telegram المخزنة في ``icon_file_id``.
    - روابط الصور الخارجية القديمة.
    - صور SteamRIP التي تحتاج إعادة جلب ثم إعادة استضافة على ImgBB.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database.models import Application
from integrations.imgbb import ImgBBUploader, is_imgbb_url
from integrations.steamrip_extractor import fetch_game_data

logger = logging.getLogger(__name__)


@dataclass
class MigrationResult:
    total: int = 0
    migrated: int = 0
    failed: int = 0


def _is_http_url(value: str | None) -> bool:
    return bool(value and value.startswith(("http://", "https://")))


def _is_steamrip_app(app: Application) -> bool:
    return bool(app.devupload_url and "steamrip.com" in app.devupload_url.lower())


def _needs_migration(app: Application) -> bool:
    # صورة ImgBB موجودة فعلاً: لا نرفعها من جديد في كل Startup.
    if is_imgbb_url(app.image_url):
        return False

    # Telegram file_id أو رابط خارجي أو لعبة SteamRIP يمكن إعادة جلب غلافها.
    return bool(app.icon_file_id or _is_http_url(app.image_url) or _is_steamrip_app(app))


async def _source_image_for_app(app: Application) -> str | None:
    """اختر رابط الصورة الخارجي، مع تحديثه من SteamRIP إن أمكن."""
    source_url = app.image_url if _is_http_url(app.image_url) else None

    if _is_steamrip_app(app):
        try:
            game_data = await fetch_game_data(app.devupload_url or "")
            fresh_url = game_data.get("image_url")
            if _is_http_url(fresh_url):
                source_url = fresh_url
        except Exception:
            # لا نهدم الترحيل كله إذا كانت صفحة SteamRIP غير متاحة مؤقتاً؛
            # سنجرب الرابط القديم إن كان موجوداً.
            logger.warning(
                "تعذر تحديث صورة SteamRIP للتطبيق ID=%s (%s)",
                app.id,
                app.name,
                exc_info=True,
            )

    return source_url


async def migrate_app_images(
    bot: Bot,
    session: AsyncSession,
    uploader: ImgBBUploader | None = None,
) -> MigrationResult:
    """رحّل الصور غير الموجودة على ImgBB ثم احفظ الرابط في Application.image_url.

    اسم الصورة المرسل إلى ImgBB يحتوي رقم التطبيق ``game_<id>``، بينما الربط
    الحقيقي والدائم يتم بحفظ الرابط الناتج في صف التطبيق نفسه بواسطة ``id``.
    """
    settings = get_settings()
    if uploader is None:
        if not settings.IMGBB_API_KEY:
            raise RuntimeError("IMGBB_API_KEY غير موجود في ملف .env")
        uploader = ImgBBUploader(api_key=settings.IMGBB_API_KEY)

    result = await session.execute(select(Application).order_by(Application.id))
    apps = [app for app in result.scalars().all() if _needs_migration(app)]

    summary = MigrationResult(total=len(apps))
    if not apps:
        return summary

    logger.info("📦 وجدنا %d تطبيق بحاجة لترحيل الصور إلى ImgBB", len(apps))

    for idx, app in enumerate(apps, 1):
        image_name = f"game_{app.id}"
        hosted_url = ""

        logger.info(
            "[%d/%d] ترحيل صورة التطبيق ID=%s: %s",
            idx,
            len(apps),
            app.id,
            app.name,
        )

        # أفضل مصدر للصورة اليدوية هو Telegram نفسه.
        if app.icon_file_id:
            hosted_url = await uploader.upload_telegram_photo(
                bot,
                app.icon_file_id,
                name=image_name,
            )

        # إذا لم تنجح صورة Telegram أو لم تكن موجودة، نجرب رابط المصدر.
        if not hosted_url:
            source_url = await _source_image_for_app(app)
            if source_url:
                hosted_url = await uploader.upload_remote_image(
                    source_url,
                    name=image_name,
                    referer=app.devupload_url if _is_steamrip_app(app) else None,
                )

        if hosted_url:
            app.image_url = hosted_url
            summary.migrated += 1
            logger.info(
                "✅ تم ربط صورة ImgBB بالتطبيق ID=%s",
                app.id,
            )
        else:
            summary.failed += 1
            logger.warning(
                "⚠️ فشل ترحيل صورة التطبيق ID=%s (%s)",
                app.id,
                app.name,
            )

    await session.commit()
    logger.info(
        "💾 انتهى ترحيل الصور: نجح=%d فشل=%d",
        summary.migrated,
        summary.failed,
    )
    return summary
