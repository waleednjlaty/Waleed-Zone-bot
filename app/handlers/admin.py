"""لوحة الإدارة الكاملة — للمالك فقط."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.admin import (
    admin_panel_keyboard,
    app_manage_keyboard,
    apps_management_keyboard,
    banned_words_keyboard,
    broadcast_target_keyboard,
    delete_confirm_keyboard,
    group_management_keyboard,
    protection_settings_keyboard,
    publish_select_keyboard,
    requests_keyboard,
    settings_keyboard,
    welcome_settings_keyboard,
)
from app.keyboards.user import back_to_menu_keyboard
from app.services.broadcast_service import broadcast_to_chat, broadcast_to_users
from app.services.stats_service import app_stats, global_stats
from app.states import BroadcastStates, EditAppStates, GroupAdminStates
from app.utils.constants import (
    AdminCB,
    AppCB,
    BannedWordCB,
    MainMenuCB,
    ReqCB,
)
from app.utils.helpers import is_admin, parse_int, paginate
from app.utils.text import app_card, escape_html
from app.utils.website import website_app_url
from config import get_settings
from database import repositories as repo

logger = logging.getLogger(__name__)

router = Router(name="admin")

PER_PAGE = 8
PER_PAGE_REQUESTS = 10

FIELD_LABELS = {
    "name": "📱 الاسم",
    "description": "📝 الوصف",
    "version": "📦 الإصدار",
    "size": "💾 الحجم",
    "platform": "📱 النظام",
    "category": "🗂 التصنيف",
    "developer": "👨‍💻 المطور",
    "image_url": "🖼 رابط الصورة",
}


def _guard(call: CallbackQuery) -> bool:
    if is_admin(call.from_user.id):
        return True
    return False


# ---------------------------------------------------------------- لوحة عامة
@router.callback_query(AdminCB.filter(F.action == "panel"))
async def on_panel(call: CallbackQuery) -> None:
    if not _guard(call):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return
    await call.answer()
    await call.message.edit_text(
        "⚙️ لوحة الإدارة\nاختر ما تريد القيام به:",
        reply_markup=admin_panel_keyboard(),
    )


@router.callback_query(AdminCB.filter(F.action == "stats"))
async def on_stats(call: CallbackQuery, session: AsyncSession) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await call.answer()
    text = await global_stats(session)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 لوحة الإدارة", callback_data=AdminCB(action="panel", page=0).pack())]
        ]
    )
    await call.message.edit_text(text, reply_markup=kb)


# ---------------------------------------------------------------- الطلبات
@router.callback_query(AdminCB.filter(F.action == "requests"))
async def on_requests_list(
    call: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await call.answer()
    requests = await repo.list_requests(session, status=None, limit=100)
    page, total_pages = paginate(len(requests), callback_data.page, PER_PAGE_REQUESTS)
    chunk = requests[page * PER_PAGE_REQUESTS : (page + 1) * PER_PAGE_REQUESTS]
    text = "📥 طلبات التطبيقات\n────────────\n"
    if not chunk:
        text += "لا توجد طلبات بعد."
    await call.message.edit_text(
        text, reply_markup=requests_keyboard(chunk, page, total_pages)
    )


# ---------------------------------------------------------------- إدارة التطبيقات
@router.callback_query(AdminCB.filter(F.action == "apps"))
async def on_apps_management(
    call: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await call.answer()
    apps = await repo.list_applications(session, active_only=False, public_only=False, limit=200)
    page, total_pages = paginate(len(apps), callback_data.page, PER_PAGE)
    chunk = apps[page * PER_PAGE : (page + 1) * PER_PAGE]
    text = "📱 إدارة التطبيقات\n────────────\n"
    if not chunk:
        text += "لا توجد تطبيقات."
    await call.message.edit_text(
        text, reply_markup=apps_management_keyboard(chunk, page, total_pages)
    )


@router.callback_query(AdminCB.filter(F.action == "app_manage"))
async def on_app_manage(
    call: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await call.answer()
    app = await repo.get_application(session, callback_data.app_id)
    if app is None:
        await call.answer("التطبيق غير موجود.", show_alert=True)
        return
    await call.message.edit_text(
        app_card(app),
        reply_markup=app_manage_keyboard(
            app.id,
            app.active,
            callback_data.page,
            website_url=website_app_url(app.id) if app.published else None,
        ),
    )


@router.callback_query(AdminCB.filter(F.action == "app_link"))
async def on_app_link(
    call: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await call.answer()
    app = await repo.get_application(session, callback_data.app_id)
    if app is None:
        await call.answer("التطبيق غير موجود.", show_alert=True)
        return
    from app.utils.website import website_download_url
    text = f"📱 {escape_html(app.name)}\n🌐 {escape_html(website_download_url(app.id) or '')}"
    if app.devupload_url or app.shrankme_url:
        text += "\nمصدر legacy محفوظ لهذا التطبيق."
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=AdminCB(action="app_manage", app_id=app.id, page=callback_data.page).pack())]
        ]
    )
    await call.message.edit_text(text, reply_markup=kb)


@router.callback_query(AdminCB.filter(F.action == "app_stats"))
async def on_app_stats(
    call: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await call.answer()
    app = await repo.get_application(session, callback_data.app_id)
    if app is None:
        await call.answer("التطبيق غير موجود.", show_alert=True)
        return
    text = await app_stats(session, app)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=AdminCB(action="app_manage", app_id=app.id, page=callback_data.page).pack())]
        ]
    )
    await call.message.edit_text(text, reply_markup=kb)


@router.callback_query(AdminCB.filter(F.action == "delete_ask"))
async def on_delete_ask(
    call: CallbackQuery, callback_data: AdminCB
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await call.answer()
    await call.message.edit_text(
        "⚠️ هل أنت متأكد من حذف هذا التطبيق نهائيًا؟",
        reply_markup=delete_confirm_keyboard(callback_data.app_id, callback_data.page),
    )


@router.callback_query(AdminCB.filter(F.action == "delete_yes"))
async def on_delete_yes(
    call: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await repo.archive_application(session, callback_data.app_id)
    await call.answer("🗑 تمت أرشفة التطبيق")
    await on_apps_management(call, callback_data, session)


@router.callback_query(AdminCB.filter(F.action == "toggle"))
async def on_toggle_app(
    call: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await call.answer()
    app = await repo.get_application(session, callback_data.app_id)
    if app is None:
        await call.answer("التطبيق غير موجود.", show_alert=True)
        return
    new_active = not app.active
    await repo.set_application_active(session, app.id, new_active)
    await call.message.edit_text(
        f"{(await repo.get_application(session, app.id)).name} → "
        f"{'✅ مفعّل' if new_active else '🚫 معطّل'}",
        reply_markup=app_manage_keyboard(
            app.id, new_active, callback_data.page
        ),
    )


# ---------------------------------------------------------------- تعديل تطبيق
@router.callback_query(AdminCB.filter(F.action == "edit_app"))
async def on_edit_app(
    call: CallbackQuery, callback_data: AdminCB, state: FSMContext, session: AsyncSession
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await call.answer()
    app = await repo.get_application(session, callback_data.app_id)
    if not app:
        await call.message.answer("التطبيق غير موجود.")
        return
    await state.set_state(EditAppStates.choosing_field)
    await state.update_data(app_id=app.id, page=callback_data.page, expected_revision=app.revision)

    rows: list[list[InlineKeyboardButton]] = []
    for key, label in FIELD_LABELS.items():
        rows.append(
            [InlineKeyboardButton(
                text=label,
                callback_data=f"editfield:{key}",
            )]
        )
    rows.append(
        [InlineKeyboardButton(text="❌ إلغاء", callback_data=AdminCB(action="app_manage", app_id=callback_data.app_id, page=callback_data.page).pack())]
    )
    await call.message.edit_text(
        "✏️ اختر الحقل الذي تريد تعديله:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("editfield:"))
async def on_edit_field(
    call: CallbackQuery, state: FSMContext
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    field = call.data.split(":", 1)[1]
    await state.update_data(field=field)
    await state.set_state(EditAppStates.waiting_value)
    await call.answer()
    await call.message.answer(
        f"أرسل القيمة الجديدة لحقل «{FIELD_LABELS.get(field, field)}»:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ إلغاء", callback_data=MainMenuCB(action="main").pack())]]
        ),
    )


@router.message(EditAppStates.waiting_value)
async def on_edit_value(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("⛔ صلاحية غير متاحة.")
        return
    data = await state.get_data()
    app = await repo.get_application(session, data.get("app_id", 0))
    if app is None:
        await message.answer("التطبيق غير موجود.")
        await state.clear()
        return
    field = data.get("field")
    if field not in FIELD_LABELS or field in {"devupload_url", "shrankme_url"} or not message.text:
        await message.answer("❌ الحقل غير مسموح. اربط ملف Telegram بدل رابط خارجي جديد.")
        return
    if app.revision != data.get("expected_revision"):
        await state.clear()
        await message.answer("⚠️ تعارض في التعديل. افتح التطبيق مجددًا لقراءة النسخة الحالية.")
        return
    value = message.text.strip()
    from unicodedata import category as unicode_category
    limits = {"name":255,"description":1000,"version":50,"size":50,"platform":50,"category":100,"developer":255,"image_url":500}
    if not value or len(value) > limits[field] or any(unicode_category(c) in {"Cc","Cf"} and not (field == "description" and c in "\n\r\t") for c in value):
        await message.answer("❌ قيمة غير صالحة.")
        return
    if field == "image_url":
        from urllib.parse import urlsplit
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.hostname == "api.telegram.org":
            await message.answer("❌ رابط الصورة غير صالح.")
            return
    setattr(app, field, value)
    if field in ("name", "category", "platform", "description"):
        from app.utils.helpers import build_search_text

        app.search_text = build_search_text(
            app.name, app.category, app.platform, app.description
        )
    await repo.update_application(session, app)
    await state.clear()
    await message.answer("✅ تم حفظ التعديل.", reply_markup=back_to_menu_keyboard())


# ---------------------------------------------------------------- النشر بالقناة
@router.callback_query(AdminCB.filter(F.action == "publish_select"))
async def on_publish_select(
    call: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await call.answer()
    apps = await repo.list_applications(session, active_only=True, public_only=False, limit=100)
    page, total_pages = paginate(len(apps), callback_data.page, PER_PAGE)
    chunk = apps[page * PER_PAGE : (page + 1) * PER_PAGE]
    await call.message.edit_text(
        "📢 اختر التطبيق للنشر في القناة:",
        reply_markup=publish_select_keyboard(chunk, page, total_pages),
    )


@router.callback_query(AdminCB.filter(F.action == "publish"))
async def on_publish_app(
    call: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await call.answer()
    app = await repo.get_application(session, callback_data.app_id)
    if app is None:
        await call.answer("التطبيق غير موجود.", show_alert=True)
        return
    from app.handlers.upload import _publish_to_channel

    await _publish_to_channel(call, session, app)


@router.callback_query(AdminCB.filter(F.action == "migrate_images"))
async def on_migrate_images(call: CallbackQuery, session: AsyncSession) -> None:
    """زر مخصص لترحيل صور التطبيقات من Telegram إلى ImgBB."""
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    if not get_settings().IMGBB_API_KEY:
        await call.answer("⚠️ IMGBB_API_KEY غير موجود في .env", show_alert=True)
        return
    await call.answer()
    status = await call.message.edit_text(
        "🖼 جاري ترحيل الصور...\nقد يستغرق ذلك بعض الوقت ⏳"
    )
    try:
        from app.services.image_migration import migrate_app_images

        result = await migrate_app_images(call.bot, session)
    except Exception as exc:
        logger.error("Migrate images failed: %s", exc, exc_info=True)
        await status.edit_text(f"❌ فشل ترحيل الصور:\n{escape_html(str(exc))}")
        return

    if result.total == 0:
        text = "✅ لا توجد صور بحاجة لترحيل — كل التطبيقات لديها روابط صور."
    else:
        text = (
            "🖼 **نتيجة ترحيل الصور:**\n"
            f"📦 المجموع: {result.total}\n"
            f"✅ نجح: {result.migrated}\n"
            f"❌ فشل: {result.failed}"
        )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 لوحة الإدارة", callback_data=AdminCB(action="panel", page=0).pack())]
        ]
    )
    await status.edit_text(text, reply_markup=kb)


# ---------------------------------------------------------------- إدارة الجروب
@router.callback_query(AdminCB.filter(F.action == "group"))
async def on_group_menu(call: CallbackQuery) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await call.answer()
    await call.message.edit_text(
        "👥 إدارة الجروب\nاختر الإعداد الذي تريده:",
        reply_markup=group_management_keyboard(),
    )


@router.callback_query(AdminCB.filter(F.action == "group_help"))
async def on_group_help(call: CallbackQuery) -> None:
    await call.answer()
    text = (
        "🔔 أوامر الإشراف داخل المجموعة (الرد على رسالة العضو):\n\n"
        "🔨 /ban — حظر العضو\n"
        "🔓 /unban — فك الحظر\n"
        "🔇 /mute — كتم العضو\n"
        "🔊 /unmute — فك الكتم\n"
        "⚠️ /warn — تحذير العضو\n"
        "🗑 /del — حذف الرسالة\n"
        "📌 /pin — تثبيت الرسالة\n"
        "📋 /admins — قائمة المشرفين\n"
        "📊 /gstats — إحصائيات المجموعة\n"
        "⚠️ /warns — تحذيرات العضو"
    )
    await call.message.answer(text)


@router.callback_query(AdminCB.filter(F.action == "welcome"))
async def on_welcome_settings(
    call: CallbackQuery, session: AsyncSession
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await call.answer()
    enabled = await repo.get_setting_bool(session, "welcome_enabled", True)
    await call.message.edit_text(
        "👋 إعدادات الترحيب:",
        reply_markup=welcome_settings_keyboard(enabled),
    )


@router.callback_query(AdminCB.filter(F.action.in_(["welcome_on", "welcome_off"])))
async def on_welcome_toggle(
    call: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    enabled = callback_data.action == "welcome_on"
    await repo.set_setting(session, "welcome_enabled", "1" if enabled else "0")
    await call.answer("✅ تم الحفظ")
    await call.message.edit_text(
        "👋 إعدادات الترحيب:",
        reply_markup=welcome_settings_keyboard(enabled),
    )


@router.callback_query(AdminCB.filter(F.action == "welcome_edit"))
async def on_welcome_edit(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(GroupAdminStates.waiting_welcome_message)
    await call.message.answer(
        "✏️ أرسل رسالة الترحيب الجديدة.\n"
        "يمكنك استخدام {username} لاسم العضو و{name} للاسم الكامل.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ إلغاء", callback_data=AdminCB(action="welcome", page=0).pack())]]
        ),
    )


@router.message(GroupAdminStates.waiting_welcome_message)
async def on_welcome_message(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    if not is_admin(message.from_user.id):
        return
    await repo.set_setting(session, "welcome_message", message.text.strip())
    await state.clear()
    await message.answer("✅ تم حفظ رسالة الترحيب.", reply_markup=back_to_menu_keyboard())


@router.callback_query(AdminCB.filter(F.action == "protection"))
async def on_protection(
    call: CallbackQuery, session: AsyncSession
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await call.answer()
    anti_spam = await repo.get_setting_bool(session, "anti_spam_enabled", True)
    warn_limit = parse_int(await repo.get_setting(session, "warn_limit", "3"), 3)
    warn_action = await repo.get_setting(session, "warn_action", "mute") or "mute"
    await call.message.edit_text(
        "🛡 إعدادات الحماية:",
        reply_markup=protection_settings_keyboard(anti_spam, warn_limit, warn_action),
    )


@router.callback_query(AdminCB.filter(F.action.in_(["spam_on", "spam_off"])))
async def on_spam_toggle(
    call: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    enabled = callback_data.action == "spam_on"
    await repo.set_setting(session, "anti_spam_enabled", "1" if enabled else "0")
    await call.answer("✅ تم الحفظ")
    await on_protection(call, session)


@router.callback_query(AdminCB.filter(F.action == "warn_limit_edit"))
async def on_warn_limit_edit(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(GroupAdminStates.waiting_warn_limit)
    await call.message.answer("✏️ أرسل حد التحذيرات (رقم من 1 إلى 10):")


@router.message(GroupAdminStates.waiting_warn_limit)
async def on_warn_limit_value(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    if not is_admin(message.from_user.id):
        return
    value = parse_int(message.text.strip(), 0)
    if not 1 <= value <= 10:
        await message.answer("❌ أرسل رقمًا صحيحًا بين 1 و 10.")
        return
    await repo.set_setting(session, "warn_limit", str(value))
    await state.clear()
    await message.answer("✅ تم حفظ حد التحذيرات.", reply_markup=back_to_menu_keyboard())


@router.callback_query(AdminCB.filter(F.action == "warn_action_toggle"))
async def on_warn_action_toggle(
    call: CallbackQuery, session: AsyncSession
) -> None:
    current = await repo.get_setting(session, "warn_action", "mute") or "mute"
    new_action = "ban" if current == "mute" else "mute"
    await repo.set_setting(session, "warn_action", new_action)
    await call.answer("✅ تم تبديل إجراء التحذيرات")
    await on_protection(call, session)


# ---------------------------------------------------------------- الكلمات المحظورة
@router.callback_query(AdminCB.filter(F.action == "banned_words"))
async def on_banned_words(call: CallbackQuery, session: AsyncSession) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await call.answer()
    words = await repo.list_banned_words(session)
    await call.message.edit_text(
        "🚫 الكلمات المحظورة\nاضغط على أي كلمة لحذفها:",
        reply_markup=banned_words_keyboard(words),
    )


@router.callback_query(AdminCB.filter(F.action == "bw_add"))
async def on_banned_word_add(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(GroupAdminStates.waiting_banned_word)
    await call.message.answer(
        "🚫 أرسل الكلمة التي تريد حظرها في المجموعة:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ إلغاء", callback_data=AdminCB(action="banned_words", page=0).pack())]]
        ),
    )


@router.message(GroupAdminStates.waiting_banned_word)
async def on_banned_word_value(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    if not is_admin(message.from_user.id):
        return
    word = message.text.strip()
    if not word or len(word) > 100:
        await message.answer("❌ كلمة غير صالحة.")
        return
    added = await repo.add_banned_word(session, word)
    await state.clear()
    if added:
        await message.answer(f"✅ تمت إضافة الكلمة المحظورة: {word}")
    else:
        await message.answer("⚠️ الكلمة موجودة مسبقًا.")


@router.callback_query(BannedWordCB.filter(F.action == "del"))
async def on_banned_word_delete(
    call: CallbackQuery, callback_data: BannedWordCB, session: AsyncSession
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    removed = await repo.remove_banned_word(session, callback_data.word)
    await call.answer("🗑 تم الحذف" if removed else "⚠️ الكلمة غير موجودة")
    await on_banned_words(call, session)


# ---------------------------------------------------------------- الإعدادات
@router.callback_query(AdminCB.filter(F.action == "settings"))
async def on_settings(call: CallbackQuery) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await call.answer()
    await call.message.edit_text("⚙️ الإعدادات:", reply_markup=settings_keyboard())


@router.callback_query(AdminCB.filter(F.action == "maintenance"))
async def on_maintenance_toggle(
    call: CallbackQuery, session: AsyncSession
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    current = await repo.get_setting_bool(session, "maintenance_mode", False)
    await repo.set_setting(session, "maintenance_mode", "0" if current else "1")
    await call.answer("✅ تم التبديل")
    await call.message.edit_text(
        "🛠 وضع الصيانة " + ("🟢 معطّل" if current else "🔴 مفعّل"),
        reply_markup=settings_keyboard(),
    )


@router.callback_query(AdminCB.filter(F.action == "force_sub"))
async def on_force_sub_toggle(
    call: CallbackQuery, session: AsyncSession
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    current = await repo.get_setting_bool(session, "force_subscribe", False)
    await repo.set_setting(session, "force_subscribe", "0" if current else "1")
    await call.answer("✅ تم التبديل")
    await call.message.edit_text(
        "📢 الاشتراك الإجباري " + ("🟢 معطّل" if current else "🔴 مفعّل"),
        reply_markup=settings_keyboard(),
    )


@router.callback_query(AdminCB.filter(F.action == "notif_global"))
async def on_notif_global_toggle(
    call: CallbackQuery, session: AsyncSession
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    current = await repo.get_setting_bool(session, "notifications_enabled", True)
    await repo.set_setting(session, "notifications_enabled", "0" if current else "1")
    await call.answer("✅ تم التبديل")
    await call.message.edit_text(
        "🔔 إشعارات التطبيقات الجديدة " + ("🟢 معطّلة" if current else "🔴 مفعّلة"),
        reply_markup=settings_keyboard(),
    )


# ---------------------------------------------------------------- الإعلانات
@router.callback_query(AdminCB.filter(F.action == "broadcast"))
async def on_broadcast(call: CallbackQuery, state: FSMContext) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    await call.answer()
    await state.set_state(BroadcastStates.waiting_text)
    await call.message.answer(
        "📣 أرسل نص الإعلان الذي تريد نشره:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ إلغاء", callback_data=AdminCB(action="panel", page=0).pack())]]
        ),
    )


@router.message(BroadcastStates.waiting_text)
async def on_broadcast_text(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.update_data(broadcast_text=message.text)
    await state.set_state(BroadcastStates.waiting_target)
    await message.answer("إلى أين أرسل الإعلان؟", reply_markup=broadcast_target_keyboard())


@router.callback_query(AdminCB.filter(F.action.in_(["bc_users", "bc_group", "bc_channel"])))
async def on_broadcast_target(
    call: CallbackQuery, callback_data: AdminCB, state: FSMContext, session: AsyncSession
) -> None:
    if not _guard(call):
        await call.answer("⛔", show_alert=True)
        return
    data = await state.get_data()
    text = data.get("broadcast_text")
    if not text:
        await call.answer("لا يوجد نص إعلان.", show_alert=True)
        return
    await state.clear()
    await call.answer("⏳ جاري الإرسال...")

    if callback_data.action == "bc_users":
        user_ids = await repo.list_all_user_ids(session)
        stats = await broadcast_to_users(call.bot, user_ids, text=text)
        report = str(stats)
    elif callback_data.action == "bc_group":
        gid = get_settings().GROUP_ID
        if not gid:
            await call.message.answer("⚠️ لم يتم إعداد GROUP_ID في .env")
            return
        ok = await broadcast_to_chat(call.bot, gid, text=text)
        report = "✅ تم الإرسال للمجموعة." if ok else "❌ فشل الإرسال للمجموعة."
    else:
        cid = get_settings().CHANNEL_ID
        if not cid:
            await call.message.answer("⚠️ لم يتم إعداد CHANNEL_ID في .env")
            return
        ok = await broadcast_to_chat(call.bot, cid, text=text)
        report = "✅ تم الإرسال للقناة." if ok else "❌ فشل الإرسال للقناة."

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 لوحة الإدارة", callback_data=AdminCB(action="panel", page=0).pack())]
        ]
    )
    await call.message.answer(report, reply_markup=kb)
