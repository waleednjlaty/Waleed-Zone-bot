"""خدمة الإحصائيات للوحة الإدارة."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from database import repositories as repo
from database.models import Application


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
        f"⚠️ تحذيرات المجموعة: {warnings}"
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
