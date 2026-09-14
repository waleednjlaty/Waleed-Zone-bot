"""خدمة الإحصائيات للوحة الإدارة."""

from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from database import repositories as repo
from database.models import Application
from config import get_settings


async def website_stats() -> dict[str, int] | None:
    settings = get_settings()
    if not settings.WEBSITE_STATS_URL or not settings.WEBSITE_STATS_TOKEN:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                settings.WEBSITE_STATS_URL,
                headers={"Authorization": f"Bearer {settings.WEBSITE_STATS_TOKEN}"},
            )
            response.raise_for_status()
            data = response.json()
            keys = ("visitors", "applications", "published", "downloads", "views")
            return {key: int(data.get(key, 0) or 0) for key in keys}
    except (httpx.HTTPError, ValueError, TypeError):
        return None


async def global_stats(session: AsyncSession) -> str:
    users = await repo.count_users(session)
    new_today = await repo.count_users_today(session)
    apps = await repo.count_applications(session)
    downloads = await repo.count_downloads(session)
    downloads_today = await repo.count_downloads_today(session)
    searches = await repo.count_searches(session)
    searches_today = await repo.count_searches_today(session)
    requests = await repo.count_requests(session)
    pending = await repo.count_pending_requests(session)
    warnings = await repo.count_warnings(session)
    site = await website_stats()

    return (
        "📊 إحصائيات البوت\n"
        "──────────────\n"
        f"👥 المستخدمون: {users}\n"
        f"🆕 مستخدمون جدد اليوم: {new_today}\n"
        f"📱 عدد التطبيقات: {apps}\n"
        f"📥 إجمالي التحميلات: {downloads}\n"
        f"📅 تحميلات اليوم: {downloads_today}\n"
        f"🔎 إجمالي عمليات البحث: {searches}\n"
        f"📅 عمليات بحث اليوم: {searches_today}\n"
        f"📥 طلبات التطبيقات: {requests}\n"
        f"⏳ طلبات معلقة: {pending}\n"
        f"⚠️ تحذيرات المجموعة: {warnings}\n\n"
        "====================\n"
        "🌐 إحصائيات الموقع\n"
        "====================\n"
        f"👀 زوار الموقع: {site['visitors'] if site else 'غير متصل'}\n"
        f"📱 تطبيقات الموقع: {site['applications'] if site else 'غير متصل'}\n"
        f"📢 منشور في الموقع: {site['published'] if site else 'غير متصل'}\n"
        f"📥 تحميلات الموقع: {site['downloads'] if site else 'غير متصل'}\n"
        f"👁 مشاهدات التطبيقات: {site['views'] if site else 'غير متصل'}"
    )


async def app_stats(session: AsyncSession, app: Application) -> str:
    downloads = app.downloads
    views = app.views
    return (
        f"📊 إحصائيات التطبيق\n"
        "──────────────\n"
        f"📱 {app.name}\n"
        f"📥 عدد التحميلات: {downloads}\n"
        f"👀 عدد المشاهدات: {views}"
    )
