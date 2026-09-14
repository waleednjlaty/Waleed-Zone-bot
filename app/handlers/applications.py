"""معالجات تصفح التطبيقات، أحدث التطبيقات، المفضلة، والتحميل."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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
from app.utils.constants import AppCB, AppsCB, FavsCB, LatestCB, MainMenuCB
from app.utils.helpers import paginate
from app.utils.text import app_card, escape_html
from database import repositories as repo
from integrations.steamrip_extractor import fetch_game_data, extract_bzzhr_direct_link

logger = logging.getLogger(__name__)

router = Router(name="applications")

PER_PAGE = 8


@router.callback_query(AppsCB.filter(F.category == "cats"))
async def on_categories(call: CallbackQuery, session: AsyncSession) -> None:
    cats = await repo.list_categories(session)
    await call.answer()
    await call.message.edit_text(
        "🗂 اختر التصنيف:", reply_markup=categories_keyboard(cats)
    )


@router.callback_query(AppsCB.filter())
async def on_apps_list(
    call: CallbackQuery, callback_data: AppsCB, session: AsyncSession
) -> None:
    await call.answer()
    category = callback_data.category
    if category == "all":
        apps = await repo.list_latest(session, limit=100)
    else:
        apps = await repo.list_by_category(session, category, limit=100)

    page, total_pages = paginate(len(apps), callback_data.page, PER_PAGE)
    chunk = apps[page * PER_PAGE : (page + 1) * PER_PAGE]

    header = "📱 التطبيقات"
    if category != "all":
        header = f"🗂 تصنيف: {escape_html(category)}"
    text = f"{header}\n────────────\n" if chunk else "لا توجد تطبيقات في هذا التصنيف."
    kb = apps_list_keyboard(chunk, category, page, total_pages)
    await call.message.edit_text(text, reply_markup=kb)


@router.callback_query(LatestCB.filter())
async def on_latest(
    call: CallbackQuery, callback_data: LatestCB, session: AsyncSession
) -> None:
    await call.answer()
    apps = await repo.list_latest(session, limit=100)
    page, total_pages = paginate(len(apps), callback_data.page, PER_PAGE)
    chunk = apps[page * PER_PAGE : (page + 1) * PER_PAGE]

    if not chunk:
        text = "🆕 لا توجد تطبيقات بعد."
        kb = back_to_menu_keyboard()
    else:
        text = "🆕 أحدث التطبيقات\n────────────\n"
        kb = latest_keyboard(chunk, page, total_pages)
    await call.message.edit_text(text, reply_markup=kb)


@router.callback_query(FavsCB.filter())
async def on_favorites(
    call: CallbackQuery, callback_data: FavsCB, session: AsyncSession
) -> None:
    await call.answer()
    apps = await repo.list_favorites(session, call.from_user.id, limit=100)
    page, total_pages = paginate(len(apps), callback_data.page, PER_PAGE)
    chunk = apps[page * PER_PAGE : (page + 1) * PER_PAGE]

    if not chunk:
        text = "❤️ لا توجد تطبيقات في المفضلة بعد.\n\n"
        text += "افتح أي تطبيق واضغط على «إضافة للمفضلة»."
        kb = back_to_menu_keyboard()
    else:
        text = "❤️ تطبيقاتي المفضلة\n────────────\n"
        kb = favorites_keyboard(chunk, page, total_pages)
    await call.message.edit_text(text, reply_markup=kb)


@router.callback_query(AppCB.filter(F.action == "open"))
async def on_open_app(
    call: CallbackQuery, callback_data: AppCB, session: AsyncSession
) -> None:
    await call.answer()
    await show_app(call, session, call.bot, callback_data.app_id)


@router.callback_query(AppCB.filter(F.action == "download"))
async def on_download(
    call: CallbackQuery, callback_data: AppCB, session: AsyncSession
) -> None:
    app = await repo.get_active_application(session, callback_data.app_id)
    if app is None:
        await call.answer("❌ التطبيق غير متوفر.", show_alert=True)
        return

    await call.answer("⏳ جاري تجهيز رابط التحميل...")

    url: str | None = None
    status_msg = None

    # رابط مخصص محفوظ من الإدارة له الأولوية.
    if app.shrankme_url:
        url = app.shrankme_url

    # ألعاب SteamRIP: نولّد الرابط المباشر لحظياً عند كل ضغطة.
    elif app.devupload_url and "steamrip.com" in app.devupload_url.lower():
        status_msg = await call.message.answer(
            "🔎 جاري البحث عن سيرفر BZZHR وتجهيز رابط التحميل المباشر..."
        )
        try:
            game_data = await fetch_game_data(app.devupload_url)
            servers = game_data.get("servers", {})

            bzzhr_url = next(
                (
                    server_url
                    for server_name, server_url in servers.items()
                    if (
                        "bzzhr" in server_name.lower()
                        or "buzzheavier" in server_name.lower()
                        or "bzzhr" in server_url.lower()
                        or "buzzheavier" in server_url.lower()
                    )
                ),
                None,
            )

            if not bzzhr_url:
                await status_msg.edit_text(
                    "❌ لم يتم العثور على سيرفر BZZHR / Buzzheavier لهذه اللعبة."
                )
                return

            url = await extract_bzzhr_direct_link(bzzhr_url)

            if not url:
                await status_msg.edit_text(
                    "❌ تم العثور على BZZHR، لكن تعذر توليد رابط التحميل المباشر."
                )
                return

        except Exception:
            logger.exception(
                "SteamRIP direct download failed: %s",
                app.devupload_url,
            )
            await status_msg.edit_text(
                "❌ حدث خطأ أثناء تجهيز رابط التحميل المباشر."
            )
            return

    # التطبيقات العادية تبقى على السلوك السابق.
    else:
        url = app.devupload_url

    if not url:
        if status_msg:
            await status_msg.edit_text("⚠️ لا يوجد رابط تحميل لهذا التطبيق.")
        else:
            await call.message.answer("⚠️ لا يوجد رابط تحميل لهذا التطبيق.")
        return

    await repo.increment_downloads(session, app.id)
    await repo.add_download(session, call.from_user.id, app.id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 رابط التحميل", url=url)],
            [
                InlineKeyboardButton(
                    text="🏠 القائمة",
                    callback_data=MainMenuCB(action="main").pack(),
                )
            ],
        ]
    )
    text = (
        f"⬇️ رابط تحميل {escape_html(app.name)}\n\n"
        "✅ الرابط المباشر جاهز.\n"
        "اضغط على «📥 رابط التحميل» لبدء التنزيل من المتصفح."
    )

    if status_msg:
        await status_msg.edit_text(text, reply_markup=kb)
    else:
        await call.message.answer(text, reply_markup=kb)


@router.callback_query(AppCB.filter(F.action.in_({"fav", "unfav"})))
async def on_toggle_favorite(
    call: CallbackQuery, callback_data: AppCB, session: AsyncSession
) -> None:
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
    is_fav = callback_data.action == "fav"
    kb = app_detail_keyboard(
        app.id,
        is_fav=is_fav,
    )
    try:
        await call.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
