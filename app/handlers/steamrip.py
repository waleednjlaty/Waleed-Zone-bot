"""معالجات SteamRIP: إضافة ألعاب الكمبيوتر وتوليد روابط BZZHR المباشرة لحظياً."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.user import cancel_keyboard
from app.utils.catalog import PC_GAME_CATEGORY
from app.utils.constants import (
    AdminCB,
    DEFAULT_CATEGORIES,
    MainMenuCB,
    REQUIRED_PLATFORMS,
)
from app.utils.helpers import build_search_text, escape_html, is_admin
from app.utils.text import append_app_footer
from config import get_settings
from database import repositories as repo
from integrations.imgbb import ImgBBUploader
from integrations.steamrip_extractor import extract_bzzhr_direct_link, fetch_game_data

logger = logging.getLogger(__name__)

router = Router(name="steamrip")
imgbb_client = ImgBBUploader(api_key=get_settings().IMGBB_API_KEY or "")


class SteamRipStates(StatesGroup):
    waiting_game_url = State()
    waiting_custom_link = State()

    waiting_metadata_choice = State()
    waiting_name = State()
    waiting_description = State()
    waiting_version = State()
    waiting_platform = State()
    waiting_category = State()
    waiting_image_choice = State()
    waiting_manual_image = State()
    waiting_publish_choice = State()
    waiting_confirm = State()


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ إلغاء",
                    callback_data=MainMenuCB(action="main").pack(),
                )
            ]
        ]
    )


def _metadata_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ إدخال البيانات يدويًا",
                    callback_data="rip:meta_manual",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚡ استخدام بيانات SteamRIP",
                    callback_data="rip:meta_auto",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ إلغاء",
                    callback_data=MainMenuCB(action="main").pack(),
                )
            ],
        ]
    )


def _choice_keyboard(
    values: list[str] | tuple[str, ...],
    prefix: str,
    custom_callback: str,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    for value in values:
        row.append(
            InlineKeyboardButton(
                text=value,
                callback_data=f"{prefix}:{value}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                text="✍️ كتابة خيار مخصص",
                callback_data=custom_callback,
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="❌ إلغاء",
                callback_data=MainMenuCB(action="main").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _prepare_rip_flow(
    message: Message,
    state: FSMContext,
    page_url: str,
    status_msg: Message,
) -> None:
    """فحص رابط SteamRIP ثم بدء معالج إضافة اللعبة التفاعلي."""
    try:
        game = await fetch_game_data(page_url)
    except Exception as exc:
        logger.exception("RIP source fetch failed: %s", page_url)
        await status_msg.edit_text(
            f"❌ فشل جلب بيانات اللعبة من SteamRIP:\n{escape_html(str(exc))}"
        )
        await state.clear()
        return

    await state.clear()
    await state.update_data(
        steamrip_source=True,
        source_page_url=game.get("page_url") or page_url,
        source_image_url=game.get("image_url"),
        scraped_title=game.get("title") or "Game Title",
        size=game.get("size") or "—",
        size_bytes=0,
        image_mode="none",
        image_url=None,
        icon_file_id=None,
        publish_choice="no",
    )
    await state.set_state(SteamRipStates.waiting_metadata_choice)

    image_status = "✅ تم العثور عليها" if game.get("image_url") else "⚠️ لم تُكتشف"
    await status_msg.edit_text(
        "✅ تم التعرف على لعبة SteamRIP.\n\n"
        f"🎮 العنوان المكتشف: {escape_html(game.get('title') or '—')}\n"
        f"💾 الحجم المكتشف: {escape_html(game.get('size') or '—')}\n"
        f"🖼 الصورة: {image_status}\n\n"
        "هل تريد إدخال بيانات التطبيق يدويًا خطوة بخطوة مثل «إضافة تطبيق»، "
        "أم استخدام بيانات SteamRIP تلقائيًا؟",
        reply_markup=_metadata_choice_keyboard(),
    )


async def _ask_category(message: Message, state: FSMContext) -> None:
    await state.set_state(SteamRipStates.waiting_category)
    await message.answer(
        "🗂 اختر التصنيف أو اكتبه:",
        reply_markup=_choice_keyboard(
            DEFAULT_CATEGORIES,
            "rip:cat",
            "rip:custom_category",
        ),
    )


async def _ask_image_source(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(SteamRipStates.waiting_image_choice)

    rows: list[list[InlineKeyboardButton]] = []
    if data.get("source_image_url"):
        rows.append(
            [
                InlineKeyboardButton(
                    text="🌐 اسحب الصورة من SteamRIP وارفعها إلى ImgBB",
                    callback_data="rip:img_site",
                )
            ]
        )

    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="🖼 أضيف الصورة يدويًا",
                    callback_data="rip:img_manual",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⏭️ بدون صورة",
                    callback_data="rip:img_none",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ إلغاء",
                    callback_data=MainMenuCB(action="main").pack(),
                )
            ],
        ]
    )

    await message.answer(
        "🖼 كيف تريد إضافة صورة اللعبة؟\n\n"
        "عند اختيار صورة SteamRIP سيتم تنزيلها ثم إعادة رفعها إلى ImgBB "
        "وربط رابط ImgBB بسجل اللعبة بعد إنشاء ID.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


async def _ask_publish(message: Message, state: FSMContext) -> None:
    await state.set_state(SteamRipStates.waiting_publish_choice)
    await message.answer(
        "📢 هل تريد نشر التطبيق في القناة بعد حفظه؟",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ نعم", callback_data="rip:pub_yes"),
                    InlineKeyboardButton(text="❌ لا", callback_data="rip:pub_no"),
                ],
                [
                    InlineKeyboardButton(
                        text="إلغاء العملية",
                        callback_data=MainMenuCB(action="main").pack(),
                    )
                ],
            ]
        ),
    )


async def _show_preview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(SteamRipStates.waiting_confirm)

    image_mode = data.get("image_mode") or "none"
    image_label = {
        "site": "SteamRIP → ImgBB عند الحفظ",
        "telegram": "Telegram → ImgBB عند الحفظ",
        "none": "بدون صورة",
    }.get(image_mode, "بدون صورة")

    text = (
        "📋 معاينة لعبة SteamRIP\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🎮 الاسم: {escape_html(data.get('name') or '—')}\n"
        f"📝 الوصف: {escape_html(data.get('description') or '—')}\n"
        f"📦 الإصدار: {escape_html(data.get('version') or '—')}\n"
        f"💾 الحجم: {escape_html(data.get('size') or '—')}\n"
        f"💻 النظام: {escape_html(data.get('platform') or '—')}\n"
        f"🗂 التصنيف: {escape_html(data.get('category') or '—')}\n"
        f"🖼 الصورة: {escape_html(image_label)}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🔗 مصدر التحميل: SteamRIP\n"
        "⚡ الرابط المباشر سيُولد من BZZHR عند ضغط المستخدم على «تحميل التطبيق»."
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ حفظ التطبيق", callback_data="rip:confirm")],
            [
                InlineKeyboardButton(
                    text="❌ إلغاء",
                    callback_data=MainMenuCB(action="main").pack(),
                )
            ],
        ]
    )

    photo = data.get("icon_file_id")
    if not photo and image_mode == "site":
        photo = data.get("source_image_url")
    if not photo:
        photo = data.get("image_url")

    if photo:
        try:
            await message.answer_photo(photo=photo, caption=text, reply_markup=kb)
            return
        except Exception:
            logger.debug("Could not render RIP preview image", exc_info=True)

    await message.answer(text, reply_markup=kb)


async def _publish_to_channel(call: CallbackQuery, app) -> None:
    settings = get_settings()
    if not settings.CHANNEL_ID:
        await call.message.answer(
            "⚠️ لم يتم إعداد CHANNEL_ID؛ تم حفظ التطبيق بدون نشر في القناة."
        )
        return

    try:
        me = await call.bot.me()
        bot_username = me.username or ""
    except Exception:
        bot_username = ""

    deep_link = f"https://t.me/{bot_username}?start=app_{app.id}" if bot_username else ""
    text = (
        "━━━━━━━━━━━━━━\n"
        f"🎮 {escape_html(app.name)}\n"
        f"📦 الإصدار: {escape_html(app.version or '—')}\n"
        f"💾 الحجم: {escape_html(app.size or '—')}\n"
        f"💻 النظام: {escape_html(app.platform or '—')}\n"
        "━━━━━━━━━━━━━━\n\n"
        f"📝 {escape_html(app.description or '')}\n\n"
        "⬇️ اضغط الزر لتحميل اللعبة"
    )
    text = append_app_footer(text)

    kb = (
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🚀 تحميل الآن", url=deep_link)]
            ]
        )
        if deep_link
        else None
    )

    photo = app.image_url or app.icon_file_id

    try:
        if photo:
            await call.bot.send_photo(
                settings.CHANNEL_ID,
                photo=photo,
                caption=text,
                reply_markup=kb,
            )
        else:
            await call.bot.send_message(settings.CHANNEL_ID, text, reply_markup=kb)
        await call.message.answer("📢 تم نشر اللعبة في القناة بنجاح.")
    except Exception:
        logger.exception("SteamRIP channel publish failed")
        await call.message.answer("❌ تم حفظ اللعبة، لكن فشل النشر في القناة.")


@router.callback_query(F.data.startswith("rip_dl:") | F.data.startswith("rip_refresh:"))
async def on_fetch_live_download(call: CallbackQuery, session: AsyncSession) -> None:
    app_id = int(call.data.split(":")[1])
    app = await repo.get_application(session, app_id)
    if not app:
        await call.answer("❌ لم يتم العثور على اللعبة.", show_alert=True)
        return

    if app.shrankme_url:
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📥 بدء التحميل المباشر", url=app.shrankme_url)],
                [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"app:view:{app_id}")],
            ]
        )
        await call.message.edit_text(
            f"🎮 {escape_html(app.name)}\n━━━━━━━━━━━━━━━━━━━\n✅ تم تجهيز الرابط المباشر للعبة.",
            reply_markup=markup,
        )
        return

    if not app.devupload_url:
        await call.answer("❌ لم يتم العثور على رابط المصدر.", show_alert=True)
        return

    await call.message.edit_text("⏳ جاري البحث عن سيرفر BZZHR وسحب الرابط المباشر...")

    try:
        game_data = await fetch_game_data(app.devupload_url)
        servers = game_data.get("servers", {})
        if not servers:
            await call.message.edit_text("⚠️ السيرفرات قيد التحديث في المصدر حالياً، يرجى إعادة المحاولة بعد قليل.")
            return

        bzzhr_url = next(
            (
                url
                for name, url in servers.items()
                if (
                    "bzzhr" in name.lower()
                    or "buzzheavier" in name.lower()
                    or "bzzhr" in url.lower()
                    or "buzzheavier" in url.lower()
                )
            ),
            None,
        )

        if bzzhr_url:
            direct_link = await extract_bzzhr_direct_link(
                bzzhr_url,
                source_page_url=app.devupload_url,
            )
            if direct_link:
                markup = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="📥 بدء التحميل المباشر", url=direct_link)],
                        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"app:view:{app_id}")],
                    ]
                )
                await call.message.edit_text(
                    f"🎮 {escape_html(app.name)}\n"
                    f"💾 الحجم: {escape_html(app.size or game_data.get('size') or '—')}\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "✅ تم العثور على الرابط المباشر من BZZHR بنجاح.",
                    reply_markup=markup,
                )
                return

            await call.message.edit_text(
                "❌ تعذر استخراج الرابط المباشر من صفحة BZZHR.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="🔙 رجوع", callback_data=f"app:view:{app_id}")]]
                ),
            )
            return

        await call.message.edit_text(f"⚠️ سيرفر BZZHR غير متوفر للعبة {escape_html(app.name)}.")
    except Exception as exc:
        logger.exception("Live scrape failed")
        await call.message.edit_text(f"❌ تعذر جلب الروابط:\n{escape_html(str(exc))}")


@router.callback_query(F.data.startswith("add_custom_link:"))
async def on_add_custom_link(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("⛔ صلاحية غير متاحة. هذا الخيار للإدارة فقط.", show_alert=True)
        return

    app_id = int(call.data.split(":")[1])
    await state.update_data(target_app_id=app_id)
    await state.set_state(SteamRipStates.waiting_custom_link)
    await call.message.edit_text(
        "🔗 إضافة رابط تحميل مخصص\n\nأرسل الرابط المباشر الذي ترغب بإضافته لهذه اللعبة:",
        reply_markup=cancel_keyboard(),
    )


@router.message(SteamRipStates.waiting_custom_link)
async def on_custom_link_received(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    if not is_admin(message.from_user.id):
        return

    new_link = (message.text or "").strip()
    if not new_link.startswith(("http://", "https://")):
        await message.reply("❌ أرسل رابطاً صحيحاً.", reply_markup=cancel_keyboard())
        return

    data = await state.get_data()
    app_id = data.get("target_app_id")
    app = await repo.get_application(session, app_id)
    if not app:
        await message.reply("❌ تعذر العثور على التطبيق في قاعدة البيانات.")
        await state.clear()
        return

    app.shrankme_url = new_link
    await session.commit()
    await message.reply(f"✅ تم تحديث اللعبة {escape_html(app.name)} بالرابط المخصص.")
    await state.clear()


@router.callback_query(AdminCB.filter(F.action == "add_rip_game"))
async def on_add_rip_game_btn(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return

    await call.answer()
    await state.clear()
    await state.set_state(SteamRipStates.waiting_game_url)
    await call.message.edit_text(
        "🎮 إضافة لعبة كمبيوتر من SteamRIP\n\nأرسل رابط صفحة اللعبة من موقع SteamRIP الآن:",
        reply_markup=cancel_keyboard(),
    )


@router.message(SteamRipStates.waiting_game_url)
async def on_steamrip_url_received(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    page_url = (message.text or "").strip()
    if not page_url.startswith(("http://", "https://")):
        await message.reply("❌ أرسل رابطاً صحيحاً يبدأ بـ http أو https", reply_markup=cancel_keyboard())
        return

    status_msg = await message.reply("⏳ جاري فحص SteamRIP وسحب بيانات اللعبة...")
    await _prepare_rip_flow(message, state, page_url, status_msg)


@router.message(Command("rip"))
async def on_quick_publish_rip(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return

    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or not args[1].startswith(("http://", "https://")):
        await message.reply("⚠️ طريقة الاستخدام:\n/rip https://steamrip.com/game-name-free-download/")
        return

    page_url = args[1].strip()
    status_msg = await message.reply("⏳ جاري فحص SteamRIP وسحب بيانات اللعبة...")
    await _prepare_rip_flow(message, state, page_url, status_msg)


@router.callback_query(F.data == "rip:meta_manual")
async def on_rip_manual_metadata(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return

    data = await state.get_data()
    if not data.get("source_page_url"):
        await call.answer("⚠️ انتهت جلسة الإضافة. أرسل /rip من جديد.", show_alert=True)
        return

    await call.answer()
    await state.set_state(SteamRipStates.waiting_name)
    await call.message.edit_text(
        "✍️ إضافة اللعبة يدويًا خطوة بخطوة\n\n1️⃣ أرسل اسم التطبيق:",
        reply_markup=_cancel_keyboard(),
    )


@router.callback_query(F.data == "rip:meta_auto")
async def on_rip_auto_metadata(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return

    data = await state.get_data()
    title = data.get("scraped_title") or "Game Title"
    await state.update_data(
        name=title,
        description=f"تحميل لعبة {title} كاملة ومجانية من سيرفرات سريعة.",
        version="Latest",
        platform="Windows",
        category=PC_GAME_CATEGORY,
    )
    await call.answer()
    await call.message.edit_text("⚡ تم اعتماد بيانات SteamRIP تلقائيًا كلعبة كمبيوتر.")
    await _ask_image_source(call.message, state)


@router.message(SteamRipStates.waiting_name)
async def on_rip_name(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not value:
        await message.answer("❌ أرسل اسمًا صالحًا.")
        return

    await state.update_data(name=value)
    await state.set_state(SteamRipStates.waiting_description)
    await message.answer("2️⃣ 📝 أرسل وصف التطبيق:", reply_markup=_cancel_keyboard())


@router.message(SteamRipStates.waiting_description)
async def on_rip_description(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not value:
        await message.answer("❌ أرسل وصفًا صالحًا.")
        return

    await state.update_data(description=value)
    await state.set_state(SteamRipStates.waiting_version)
    await message.answer("3️⃣ 📦 أرسل الإصدار (مثال: 1.0 أو Latest):", reply_markup=_cancel_keyboard())


@router.message(SteamRipStates.waiting_version)
async def on_rip_version(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not value:
        await message.answer("❌ أرسل إصدارًا صالحًا.")
        return

    await state.update_data(version=value)
    await state.set_state(SteamRipStates.waiting_platform)
    await message.answer(
        "4️⃣ 💻 اختر النظام أو اكتبه:",
        reply_markup=_choice_keyboard(REQUIRED_PLATFORMS, "rip:pf", "rip:custom_platform"),
    )


@router.message(SteamRipStates.waiting_platform)
async def on_rip_platform_text(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not value:
        await message.answer("❌ أرسل اسم نظام صالحًا.")
        return
    await state.update_data(platform=value)
    await _ask_category(message, state)


@router.callback_query(F.data.startswith("rip:pf:"))
async def on_rip_platform_choice(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 2)[2]
    await call.answer()
    await state.update_data(platform=value)
    await _ask_category(call.message, state)


@router.callback_query(F.data == "rip:custom_platform")
async def on_rip_custom_platform(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(SteamRipStates.waiting_platform)
    await call.message.edit_text("✍️ اكتب اسم النظام:", reply_markup=_cancel_keyboard())


@router.message(SteamRipStates.waiting_category)
async def on_rip_category_text(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not value:
        await message.answer("❌ أرسل اسم تصنيف صالحًا.")
        return
    await state.update_data(category=value)
    await _ask_image_source(message, state)


@router.callback_query(F.data.startswith("rip:cat:"))
async def on_rip_category_choice(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 2)[2]
    await call.answer()
    await state.update_data(category=value)
    await _ask_image_source(call.message, state)


@router.callback_query(F.data == "rip:custom_category")
async def on_rip_custom_category(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(SteamRipStates.waiting_category)
    await call.message.edit_text("✍️ اكتب اسم التصنيف:", reply_markup=_cancel_keyboard())


@router.callback_query(F.data == "rip:img_site")
async def on_rip_image_site(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("source_image_url"):
        await call.answer("⚠️ لم يتم العثور على صورة في SteamRIP.", show_alert=True)
        return

    await state.update_data(image_mode="site", image_url=None, icon_file_id=None)
    await call.answer("✅ سيتم ترحيل صورة SteamRIP إلى ImgBB عند الحفظ")
    await _ask_publish(call.message, state)


@router.callback_query(F.data == "rip:img_manual")
async def on_rip_image_manual(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(SteamRipStates.waiting_manual_image)
    await call.message.edit_text(
        "🖼 أرسل صورة اللعبة الآن:\n\nسيتم رفعها إلى ImgBB وربطها بـ ID اللعبة عند الحفظ.",
        reply_markup=_cancel_keyboard(),
    )


@router.callback_query(F.data == "rip:img_none")
async def on_rip_image_none(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.update_data(image_mode="none", image_url=None, icon_file_id=None)
    await _ask_publish(call.message, state)


@router.message(SteamRipStates.waiting_manual_image)
async def on_rip_manual_image(message: Message, state: FSMContext) -> None:
    if not message.photo:
        await message.answer("❌ أرسل صورة، وليس نصًا أو ملفًا آخر.")
        return

    photo_file_id = message.photo[-1].file_id
    await state.update_data(image_mode="telegram", icon_file_id=photo_file_id, image_url=None)
    await _ask_publish(message, state)


@router.callback_query(F.data.in_({"rip:pub_yes", "rip:pub_no"}))
async def on_rip_publish_choice(call: CallbackQuery, state: FSMContext) -> None:
    choice = "yes" if call.data.endswith("_yes") else "no"
    await call.answer()
    await state.update_data(publish_choice=choice)
    await _show_preview(call.message, state)


@router.message(SteamRipStates.waiting_publish_choice)
async def on_rip_publish_text(message: Message) -> None:
    await message.answer("استخدم أزرار نعم أو لا.")


@router.callback_query(F.data == "rip:confirm")
async def on_rip_confirm(
    call: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return

    data = await state.get_data()
    name = (data.get("name") or "").strip()
    source_page_url = data.get("source_page_url")
    image_mode = data.get("image_mode") or "none"

    if not name or not source_page_url:
        await call.answer("⚠️ بيانات الإضافة ناقصة. أرسل /rip من جديد.", show_alert=True)
        return

    await call.answer("⏳ جاري حفظ اللعبة وترحيل الصورة...")

    try:
        app = await repo.create_application(
            session,
            name=name,
            description=data.get("description"),
            version=data.get("version"),
            size=data.get("size"),
            category=data.get("category"),
            platform=data.get("platform"),
            icon_file_id=data.get("icon_file_id"),
            image_url=None,
            devupload_url=source_page_url,
            shrankme_url=None,
            search_text=build_search_text(name, data.get("category"), data.get("platform"), data.get("description")),
        )

        hosted_image_url = ""
        image_name = f"game_{app.id}"

        if image_mode == "site":
            source_image_url = data.get("source_image_url")
            if not source_image_url:
                raise RuntimeError("لم يعد رابط صورة SteamRIP متوفراً.")
            hosted_image_url = await imgbb_client.upload_remote_image(
                source_image_url,
                name=image_name,
                referer=source_page_url,
            )
        elif image_mode == "telegram":
            icon_file_id = data.get("icon_file_id")
            if not icon_file_id:
                raise RuntimeError("صورة Telegram غير موجودة في جلسة الإضافة.")
            hosted_image_url = await imgbb_client.upload_telegram_photo(call.bot, icon_file_id, name=image_name)

        if image_mode in {"site", "telegram"}:
            if not hosted_image_url:
                raise RuntimeError(
                    "فشل ترحيل صورة اللعبة إلى ImgBB. تأكد من IMGBB_API_KEY وأن صورة المصدر متاحة ثم أعد المحاولة."
                )
            app.image_url = hosted_image_url
            await repo.update_application(session, app)

        await session.commit()
    except Exception as exc:
        logger.exception("RIP app creation/image migration failed")
        await session.rollback()
        await call.message.answer(
            "❌ فشل حفظ اللعبة بصورة صحيحة. لم يتم حفظ سجل ناقص.\n\n"
            f"السبب: {escape_html(str(exc))}"
        )
        return

    image_result = "✅ ImgBB" if app.image_url else "بدون صورة"
    await call.message.answer(
        "✅ تمت إضافة اللعبة بنجاح!\n\n"
        f"🎮 الاسم: {escape_html(app.name)}\n"
        f"💾 الحجم: {escape_html(app.size or '—')}\n"
        f"🗂 القسم: {escape_html(app.category or '—')}\n"
        f"🖼 الصورة: {image_result}\n"
        f"🆔 ID التطبيق: {app.id}\n\n"
        "⚡ عند ضغط المستخدم على «تحميل التطبيق» سيولد البوت رابط BZZHR مباشرًا لحظيًا."
    )

    if data.get("publish_choice") == "yes":
        await _publish_to_channel(call, app)

    await state.clear()
