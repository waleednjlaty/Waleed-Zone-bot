"""Owner-authored games: existing external link → shared website catalog."""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.admin import admin_panel_keyboard
from app.utils.catalog import MOBILE_GAME_CATEGORY, PC_GAME_CATEGORY
from app.utils.constants import AdminCB
from app.utils.helpers import build_search_text
from app.utils.owner_guard import owner_gate
from app.utils.text import escape_html
from app.utils.website import website_app_url
from config import get_settings
from database import repositories as repo
from integrations.imgbb import ImgBBUploader
from integrations.public_http import public_url

logger = logging.getLogger(__name__)
router = Router(name="manual_game")


class ManualGameStates(StatesGroup):
    link = State()
    name = State()
    description = State()
    version = State()
    size = State()
    platform = State()
    category = State()
    image = State()
    confirm = State()


def _keyboard(rows=None):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *(rows or []),
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="manual:cancel")],
        ]
    )


def validate_download_link(value: str) -> str:
    """Match the website's legacy delivery URL rules without fetching the file."""
    from app.services.download_service import manual_url
    if urlsplit(value).hostname in {"steamrip.com", "www.steamrip.com"}:
        raise ValueError("USE_STEAMRIP_FLOW")
    return manual_url(value, {h.strip().lower() for h in get_settings().LEGACY_DOWNLOAD_ALLOWED_HOSTS.split(",") if h.strip()})


@router.callback_query(AdminCB.filter(F.action == "add_manual_game"))
async def on_start(call: CallbackQuery, state: FSMContext):
    if not await owner_gate(call):
        return
    await state.clear()
    await state.set_state(ManualGameStates.link)
    await call.answer()
    await call.message.answer(
        "🔗 إضافة لعبة برابط يدوي\n\nأرسل رابط التحميل HTTPS الموجود عندك. "
        "سيُحفظ الرابط دون تنزيل اللعبة أو رفعها من جديد.",
        reply_markup=_keyboard(),
    )


@router.callback_query(F.data == "manual:cancel", StateFilter(ManualGameStates))
@router.message(Command("cancel"), StateFilter(ManualGameStates))
async def on_cancel(event, state: FSMContext):
    if not await owner_gate(event):
        return
    await state.clear()
    message = event.message if isinstance(event, CallbackQuery) else event
    if isinstance(event, CallbackQuery):
        await event.answer()
    await message.answer("تم إلغاء الإضافة.", reply_markup=admin_panel_keyboard())


@router.message(ManualGameStates.link)
async def on_link(message: Message, state: FSMContext):
    if not await owner_gate(message):
        return
    try:
        link = validate_download_link((message.text or "").strip())
    except ValueError:
        await message.answer(
            "❌ أرسل رابط تحميل HTTPS صالحًا من نطاق مسموح بالموقع، بدون بيانات دخول "
            "أو منفذ أو #. لإضافة استضافة جديدة اضبط LEGACY_DOWNLOAD_ALLOWED_HOSTS "
            "بنفس القائمة في البوت والموقع. روابط صفحات SteamRIP لها خيار «إضافة لعبة».",
            reply_markup=_keyboard(),
        )
        return
    await state.update_data(download_link=link)
    await state.set_state(ManualGameStates.name)
    await message.answer("🎮 أرسل اسم اللعبة:", reply_markup=_keyboard())


# One bounded collector for the consecutive metadata steps.
_FIELDS = {
    ManualGameStates.name.state: ("name", 255, ManualGameStates.description, "📝 أرسل الوصف:"),
    ManualGameStates.description.state: (
        "description",
        1000,
        ManualGameStates.version,
        "📦 أرسل الإصدار أو /skip:",
    ),
    ManualGameStates.version.state: (
        "version",
        50,
        ManualGameStates.size,
        "💾 أرسل الحجم مثل 5 GB أو /skip:",
    ),
    ManualGameStates.size.state: (
        "size",
        50,
        ManualGameStates.platform,
        "💻 أرسل النظام مثل Windows أو Android:",
    ),
    ManualGameStates.platform.state: (
        "platform",
        50,
        ManualGameStates.category,
        "🗂 اختر قسم اللعبة:",
    ),
}


@router.message(StateFilter(*_FIELDS))
async def on_metadata(message: Message, state: FSMContext):
    if not await owner_gate(message):
        return
    field, limit, next_state, prompt = _FIELDS[await state.get_state()]
    value = (message.text or "").strip()
    if value == "/skip" and field in {"version", "size"}:
        value = None
    elif (
        not value
        or value.startswith("/")
        or len(value) > limit
        or any(ord(c) < 32 and (field != "description" or c not in "\n\r\t") for c in value)
    ):
        await message.answer(f"أرسل نصًا بين 1 و{limit} حرف.")
        return
    await state.update_data(**{field: value})
    await state.set_state(next_state)
    rows = None
    if field == "platform":
        rows = [
            [
                InlineKeyboardButton(text=PC_GAME_CATEGORY, callback_data="manual:pc"),
                InlineKeyboardButton(text=MOBILE_GAME_CATEGORY, callback_data="manual:mobile"),
            ]
        ]
    await message.answer(prompt, reply_markup=_keyboard(rows))


@router.callback_query(F.data.in_({"manual:pc", "manual:mobile"}), ManualGameStates.category)
async def on_category(call: CallbackQuery, state: FSMContext):
    if not await owner_gate(call):
        return
    category = PC_GAME_CATEGORY if call.data == "manual:pc" else MOBILE_GAME_CATEGORY
    await state.update_data(category=category)
    await state.set_state(ManualGameStates.image)
    await call.answer()
    await call.message.answer("🖼 أرسل صورة أو رابط صورة HTTPS، أو /skip:", reply_markup=_keyboard())


@router.message(ManualGameStates.image)
async def on_image(message: Message, state: FSMContext):
    if not await owner_gate(message):
        return
    image_url = None
    photo = message.photo[-1].file_id if message.photo else None
    try:
        if photo:
            image_url = await ImgBBUploader(
                api_key=get_settings().IMGBB_API_KEY or "",
            ).upload_telegram_photo(message.bot, photo)
            if not image_url:
                raise ValueError("IMAGE_UPLOAD_FAILED")
        elif message.text != "/skip":
            image_url = public_url((message.text or "").strip())
    except Exception:
        logger.warning("Manual game image rejected or upload failed")
        await message.answer("❌ تعذر حفظ الصورة. أرسل صورة أخرى أو رابط صورة HTTPS أو /skip.")
        return
    await state.update_data(image_url=image_url, icon_file_id=photo)
    data = await state.get_data()
    await state.set_state(ManualGameStates.confirm)
    await message.answer(
        "📋 راجع اللعبة قبل الحفظ\n\n"
        + "\n".join(
            f"{label}: {escape_html(data.get(field) or '—')}"
            for field, label in [
                ("name", "🎮 الاسم"),
                ("description", "📝 الوصف"),
                ("version", "📦 الإصدار"),
                ("size", "💾 الحجم"),
                ("platform", "💻 النظام"),
                ("category", "🗂 القسم"),
            ]
        )
        + f"\n🖼 الصورة: {'مضافة' if image_url else 'بدون صورة'}"
        + f"\n🔗 الرابط: {escape_html(data['download_link'])}",
        reply_markup=_keyboard(
            [
                [InlineKeyboardButton(text="🌐 نشر بالموقع فقط", callback_data="manual:site")],
                [
                    InlineKeyboardButton(
                        text="🌐📢 نشر بالموقع والقناة", callback_data="manual:channel"
                    )
                ],
                [InlineKeyboardButton(text="💾 حفظ مسودة", callback_data="manual:draft")],
            ]
        ),
    )


@router.callback_query(
    F.data.in_({"manual:site", "manual:channel", "manual:draft"}),
    ManualGameStates.confirm,
)
async def on_confirm(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    if not await owner_gate(call):
        return
    data = await state.get_data()
    if not all(
        data.get(k) for k in ("name", "description", "platform", "category", "download_link")
    ):
        await call.answer("بيانات اللعبة غير مكتملة.", show_alert=True)
        return
    try:
        link = validate_download_link(data["download_link"])
    except ValueError:
        await call.answer("الرابط لم يعد مسموحًا. أعد الإضافة برابط صالح.", show_alert=True)
        return
    try:
        app = await repo.create_application(
            session,
            **{
                k: data.get(k)
                for k in (
                    "name",
                    "description",
                    "version",
                    "size",
                    "platform",
                    "category",
                    "image_url",
                    "icon_file_id",
                )
            },
            shrankme_url=link,
            search_text=build_search_text(
                data["name"], data["category"], data["platform"], data["description"]
            ),
        )
        app.published = call.data != "manual:draft"
        await session.commit()
    except Exception:
        await session.rollback()
        logger.warning("Manual game save failed")
        await call.answer("تعذر حفظ اللعبة. يمكنك إعادة المحاولة.", show_alert=True)
        return
    await state.clear()
    await call.answer("✅ تم الحفظ")
    status = "حُفظت كمسودة" if not app.published else "نُشرت بالموقع"
    await call.message.answer(
        f"✅ اللعبة #{app.id} {status}.\n{escape_html(website_app_url(app.id) or '')}",
        reply_markup=admin_panel_keyboard(),
    )
    if call.data == "manual:channel":
        from app.handlers.upload import _publish_to_channel

        await _publish_to_channel(call, session, app)
