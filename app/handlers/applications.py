"""معالجات تصفح التطبيقات، أحدث التطبيقات، المفضلة، والتحميل."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.common import show_app
from app.keyboards.user import (
    app_detail_keyboard,
    apps_list_keyboard,
    back_to_menu_keyboard,
    categories_keyboard,
    favorites_keyboard,
    latest_keyboard,
)
from app.utils.catalog import (
    MOBILE_GAME_CATEGORY,
    PC_GAME_CATEGORY,
    app_matches_category,
    visible_categories,
)
from app.utils.constants import AppCB, AppsCB, FavsCB, LatestCB
from app.utils.helpers import paginate
from app.utils.versions import latest_per_family, sort_application_versions
from app.utils.text import escape_html
from database import repositories as repo

logger = logging.getLogger(__name__)
router = Router(name="applications")
PER_PAGE = 8


async def _public_catalog(session: AsyncSession):
    """Load the published catalogue before grouping, so old versions cannot hide other apps."""
    return await repo.list_applications(session, active_only=True, limit=1000)


@router.callback_query(AppsCB.filter(F.category == "cats"))
async def on_categories(call: CallbackQuery, session: AsyncSession) -> None:
    apps = await _public_catalog(session)
    cats = visible_categories(apps)
    await call.answer()
    await call.message.edit_text(
        "🗂 اختر القسم:\n\n"
        "🖥️ ألعاب كمبيوتر: Windows / Linux / macOS\n"
        "📱 ألعاب موبايل: Android / iOS",
        reply_markup=categories_keyboard(cats),
    )


@router.callback_query(AppsCB.filter())
async def on_apps_list(call: CallbackQuery, callback_data: AppsCB, session: AsyncSession) -> None:
    await call.answer()
    category = callback_data.category
    all_apps = await _public_catalog(session)
    if category == "all":
        filtered = all_apps
    elif category in {PC_GAME_CATEGORY, MOBILE_GAME_CATEGORY}:
        filtered = [app for app in all_apps if app_matches_category(app, category)]
    else:
        filtered = [app for app in all_apps if (app.category or "").strip().casefold() == category.strip().casefold()]
    apps = latest_per_family(filtered)

    page, total_pages = paginate(len(apps), callback_data.page, PER_PAGE)
    chunk = apps[page * PER_PAGE : (page + 1) * PER_PAGE]
    if category == PC_GAME_CATEGORY:
        header = "🖥️ ألعاب الكمبيوتر"
    elif category == MOBILE_GAME_CATEGORY:
        header = "📱 ألعاب الموبايل"
    elif category == "all":
        header = "📱 جميع التطبيقات والألعاب"
    else:
        header = f"🗂 تصنيف: {escape_html(category)}"
    text = f"{header}\n────────────\n" if chunk else "لا توجد تطبيقات في هذا القسم."
    await call.message.edit_text(text, reply_markup=apps_list_keyboard(chunk, category, page, total_pages))


@router.callback_query(LatestCB.filter())
async def on_latest(call: CallbackQuery, callback_data: LatestCB, session: AsyncSession) -> None:
    await call.answer()
    apps = latest_per_family(await _public_catalog(session))
    page, total_pages = paginate(len(apps), callback_data.page, PER_PAGE)
    chunk = apps[page * PER_PAGE : (page + 1) * PER_PAGE]
    if not chunk:
        text, kb = "🆕 لا توجد تطبيقات بعد.", back_to_menu_keyboard()
    else:
        text, kb = "🆕 أحدث التطبيقات\n────────────\n", latest_keyboard(chunk, page, total_pages)
    await call.message.edit_text(text, reply_markup=kb)


@router.callback_query(FavsCB.filter())
async def on_favorites(call: CallbackQuery, callback_data: FavsCB, session: AsyncSession) -> None:
    await call.answer()
    apps = latest_per_family(await repo.list_favorites(session, call.from_user.id, limit=100))
    page, total_pages = paginate(len(apps), callback_data.page, PER_PAGE)
    chunk = apps[page * PER_PAGE : (page + 1) * PER_PAGE]
    if not chunk:
        text, kb = "❤️ لا توجد تطبيقات في المفضلة بعد.\n\nافتح أي تطبيق واضغط على «إضافة للمفضلة».", back_to_menu_keyboard()
    else:
        text, kb = "❤️ تطبيقاتي المفضلة\n────────────\n", favorites_keyboard(chunk, page, total_pages)
    await call.message.edit_text(text, reply_markup=kb)


@router.callback_query(AppCB.filter(F.action == "open"))
async def on_open_app(call: CallbackQuery, callback_data: AppCB, session: AsyncSession) -> None:
    await call.answer()
    await show_app(call, session, call.bot, callback_data.app_id)


@router.callback_query(AppCB.filter(F.action == "versions"))
async def on_previous_versions(call: CallbackQuery, callback_data: AppCB, session: AsyncSession) -> None:
    if call.message is None or not hasattr(call.message, "edit_text"):
        await call.answer("تعذر فتح سجل الإصدارات.", show_alert=True)
        return
    releases = sort_application_versions(await repo.list_application_versions(session, callback_data.app_id))
    if len(releases) < 2:
        await call.answer("لا توجد إصدارات سابقة لهذا التطبيق.", show_alert=True)
        return
    rows = []
    for release in releases:
        version = (release.version or "إصدار غير محدد").strip()[:24]
        platform = (release.platform or "").strip()[:12]
        label = f"{'🟢 ' if release.id == callback_data.app_id else '📦 '}{version}"
        if platform:
            label += f" · {platform}"
        rows.append([InlineKeyboardButton(text=label[:60], callback_data=AppCB(action="open", app_id=release.id).pack())])
    rows.append([InlineKeyboardButton(text="⬅️ العودة للتطبيق", callback_data=AppCB(action="open", app_id=callback_data.app_id).pack())])
    await call.answer()
    await call.message.edit_text(
        f"📚 إصدارات {escape_html(releases[0].name or 'التطبيق')}\n"
        "اختر الإصدار المطلوب. الإصدارات الأحدث تظهر أولًا:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(AppCB.filter(F.action == "download"))
async def on_download(call: CallbackQuery, callback_data: AppCB, session: AsyncSession) -> None:
    from app.services.download_service import send_application_download
    await send_application_download(call, session, callback_data.app_id)


@router.callback_query(AppCB.filter(F.action.in_({"fav", "unfav"})))
async def on_toggle_favorite(call: CallbackQuery, callback_data: AppCB, session: AsyncSession) -> None:
    app = await repo.get_active_application(session, callback_data.app_id)
    if app is None:
        await call.answer("❌ التطبيق غير متوفر.", show_alert=True)
        return
    if callback_data.action == "fav":
        await repo.add_favorite(session, call.from_user.id, app.id)
        msg = "❤️ أُضيف إلى المفضلة"
    else:
        await repo.remove_favorite(session, call.from_user.id, app.id)
        msg = "💔 أُزيل من المفضلة"
    await call.answer(msg)
    kb = app_detail_keyboard(app.id, is_fav=callback_data.action == "fav")
    releases = await repo.list_application_versions(session, app.id)
    if len(releases) > 1:
        kb.inline_keyboard.insert(1, [InlineKeyboardButton(text="📚 الإصدارات السابقة", callback_data=AppCB(action="versions", app_id=app.id).pack())])
    try:
        await call.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
