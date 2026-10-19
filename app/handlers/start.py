"""معالجات /start والقائمة الرئيسية وروابط القناة/المجموعة/المساعدة."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart, Command  # تمت إضافة Command هنا
from aiogram.types import CallbackQuery, Message, FSInputFile  # تمت إضافة FSInputFile هنا
from sqlalchemy.ext.asyncio import AsyncSession
from app.handlers.subscription import require_subscription
from app.handlers.common import show_app
from app.keyboards.admin import admin_panel_keyboard
from app.keyboards.user import (
    back_to_menu_keyboard,
    channel_group_links_keyboard,
    force_subscribe_keyboard,
    main_menu_keyboard,
    notifications_keyboard,
)
from app.middlewares import is_subscribed
from app.utils.constants import MainMenuCB, NotifCB
from app.utils.helpers import is_admin
from config import get_settings
from database import repositories as repo

logger = logging.getLogger(__name__)

router = Router(name="start")

WELCOME_TEXT = (
    "👋 أهلاً بك في Waleed Zone!\n\n"
    "🔥 البوت الرسمي لقناة @Waleed_Zone\n\n"
    "من هنا يمكنك تصفّح التطبيقات والألعاب وتحميلها بسهولة.\n"
    "وإذا احتجت إلى مساعدة، اضغط على زر «التعليمات».\n\n"
    "❤️ شكرًا لاستخدامك البوت، ونتمنى لك تجربة ممتعة!"
)

HELP_TEXT = (
    "ℹ️ تعليمات استخدام البوت\n\n"
    "يمكنك من خلال القائمة الرئيسية:\n"
    "📱 تصفّح التطبيقات حسب التصنيف.\n"
    "🔎 البحث عن أي تطبيق بالاسم.\n"
    "📥 إرسال طلب لإضافة تطبيق جديد.\n"
    "📢 الوصول إلى القناة الرسمية.\n"
    "💬 الانضمام إلى مجموعة المجتمع.\n\n"
    "🔔 الإشعارات\n"
    "افتح أي تطبيق، ثم اضغط على زر الإشعارات "
    "لتفعيل أو إيقاف التنبيهات الخاصة بالتطبيقات الجديدة.\n\n"
    "⬅️ اضغط على «العودة» للرجوع إلى القائمة الرئيسية."
)

@router.message(CommandStart(), F.chat.type == "private")
async def on_start(message: Message, session: AsyncSession, bot: Bot) -> None:
    if not await require_subscription(message, bot):
        return
    """بداية البوت — يدعم deep link: t.me/BOT?start=app_123 أو dl_TOKEN"""
    user = message.from_user
    if user is None:
        return

    await repo.get_or_create_user(
        session,
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    args = (message.text or "").split(maxsplit=1)
    deep = args[1] if len(args) > 1 else ""

    # معالجة العودة من التحقق عبر الويب (Deep Link للتحميل)
    if deep.startswith("dl_"):
        token = deep.replace("dl_", "", 1)
        pending_record = await repo.get_pending_download_by_token(session, token)

        if not pending_record:
            await message.answer("❌ رابط الطلب غير صالح أو منتهي الصلاحية.")
            return

        if pending_record.status == "resolved" and pending_record.download_url:
            # جلب تفاصيل اللعبة لعرض رسالة التحميل بشكل منظم
            app = await repo.get_application(session, pending_record.app_id)
            app_name = app.name if app else "اللعبة المطلوبة"
            
            await message.answer(
                f"✅ **تم تجاوز التحقق بنجاح وتجهيز الرابط للعبة:** `{app_name}`\n\n"
                f"🔗 **رابط التحميل المباشر:**\n{pending_record.download_url}",
                parse_mode="Markdown",
            )
        elif pending_record.status == "pending":
            web_url = f"https://waleed-zone.up.railway.app/download/{pending_record.app_id}?token={token}"
            await message.answer(
                "⚠️ **لم يتم تأكيد اجتياز التحقق في المتصفح بعد.**\n\n"
                "يرجى فتح الرابط التالي في المتصفح لإتمام التحقق ثم الضغط على زر العودة هنا مرة أخرى:\n"
                f"{web_url}"
            )
        else:
            await message.answer("❌ تعذر العثور على الرابط المطلوب. حاول إعادة المحاولة من القائمة.")
        return

    if deep.startswith("app_"):
        try:
            app_id = int(deep.split("_", 1)[1])
        except ValueError:
            app_id = 0
        if app_id:
            await show_app(message, session, message.bot, app_id)
            return

    await message.answer(
        WELCOME_TEXT,
        reply_markup=main_menu_keyboard(is_admin_user=is_admin(user.id)),
    )

@router.callback_query(MainMenuCB.filter(F.action == "main"))
async def on_main_menu(call: CallbackQuery, bot: Bot) -> None:
    if not await require_subscription(call, bot):
        return

    await call.answer()
    await call.message.answer(
        WELCOME_TEXT,
        reply_markup=main_menu_keyboard(is_admin_user=is_admin(call.from_user.id)),
    )


@router.callback_query(MainMenuCB.filter(F.action == "channel"))
async def on_channel(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.answer(
        "📢 قناتنا الرسمية:\nتابعنا ليصلك كل جديد.",
        reply_markup=channel_group_links_keyboard(),
    )


@router.callback_query(MainMenuCB.filter(F.action == "group"))
async def on_group(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.answer(
        "💬 مجموعتنا الرسمية:\nانضم للمناقشات وطلبات التطبيقات.",
        reply_markup=channel_group_links_keyboard(),
    )


@router.callback_query(MainMenuCB.filter(F.action == "help"))
async def on_help(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.answer(HELP_TEXT, reply_markup=back_to_menu_keyboard())


@router.callback_query(MainMenuCB.filter(F.action == "admin"))
async def on_admin_panel(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return
    await call.answer()
    await call.message.answer(
        "⚙️ لوحة الإدارة\nاختر ما تريد القيام به:",
        reply_markup=admin_panel_keyboard(),
    )


@router.callback_query(MainMenuCB.filter(F.action == "check_sub"))
async def on_check_subscription(
    call: CallbackQuery, bot: Bot
) -> None:
    settings = get_settings()
    subscribed = await is_subscribed(bot, call.from_user.id, settings.CHANNEL_USERNAME)
    if subscribed:
        await call.answer("✅ تم التحقق! أهلاً بك.")
        await call.message.answer(
            WELCOME_TEXT,
            reply_markup=main_menu_keyboard(is_admin_user=is_admin(call.from_user.id)),
        )
    else:
        await call.answer("⚠️ لم تشترك بعد.", show_alert=True)


@router.callback_query(NotifCB.filter())
async def on_notifications(
    call: CallbackQuery, callback_data: NotifCB, session: AsyncSession
) -> None:
    """تفعيل/إيقاف إشعارات التطبيقات الجديدة للمستخدم."""
    enabled = callback_data.enabled == 1
    await repo.set_user_notifications(session, call.from_user.id, enabled)
    status = "🔔 تم تفعيل الإشعارات" if enabled else "🔕 تم إيقاف الإشعارات"
    await call.answer(status)
    await call.message.edit_text(
        f"{status}\nسنخبرك عند إضافة تطبيقات جديدة.",
        reply_markup=notifications_keyboard(enabled),
    )


@router.callback_query(F.data == "noop")
async def on_noop(call: CallbackQuery) -> None:
    await call.answer()
