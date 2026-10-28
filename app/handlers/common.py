"""أدوات مشتركة بين المعالجات: عرض صفحة تطبيق وإرسال/تعديل رسائل بأمان."""

from __future__ import annotations

from typing import Union

from aiogram import Bot
from aiogram.types import CallbackQuery, InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.user import app_detail_keyboard
from app.utils.constants import AppCB
from app.utils.helpers import is_admin
from app.utils.text import app_card
from database import repositories as repo

Target = Union[Message, CallbackQuery]


async def answer_target(target: Target, text: str, **kwargs: object) -> None:
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, **kwargs)
        except Exception:
            await target.message.answer(text, **kwargs)
    else:
        await target.answer(text, **kwargs)


async def show_app(target: Target, session: AsyncSession, bot: Bot, app_id: int) -> bool:
    """عرض صفحة إصدار واحدة مع خيار منفصل للإصدارات السابقة."""
    app = await repo.get_active_application(session, app_id)
    if app is None:
        await answer_target(target, "❌ التطبيق غير موجود أو تم تعطيله.")
        return False

    await repo.increment_views(session, app_id)
    user_id = target.from_user.id
    is_fav = await repo.is_favorite(session, user_id, app_id)
    releases = await repo.list_application_versions(session, app_id)
    kb = app_detail_keyboard(
        app_id,
        is_fav=is_fav,
        is_admin_user=is_admin(user_id),
        steamrip_url=app.source_url,
    )
    if len(releases) > 1:
        kb.inline_keyboard.insert(1, [InlineKeyboardButton(
            text="📚 الإصدارات السابقة",
            callback_data=AppCB(action="versions", app_id=app_id).pack(),
        )])
    text = app_card(app)
    if len(releases) > 1:
        text += "\n\n📚 يتوفر لهذا التطبيق " + str(len(releases) - 1) + " إصدار سابق. اضغط «الإصدارات السابقة» لاستعراضها."

    photo = app.image_url or app.icon_file_id
    if isinstance(target, CallbackQuery):
        return await _edit_message(target.message, text=text, keyboard=kb, photo_id=photo)
    if photo:
        try:
            await target.answer_photo(photo, caption=text, reply_markup=kb)
            return True
        except Exception:
            pass
    await target.answer(text, reply_markup=kb)
    return True


async def _edit_message(
    message: Message,
    *,
    text: str,
    keyboard: InlineKeyboardMarkup,
    photo_id: str | None,
) -> bool:
    if photo_id:
        try:
            await message.edit_media(InputMediaPhoto(media=photo_id, caption=text), reply_markup=keyboard)
            return True
        except Exception:
            pass
    try:
        await message.edit_text(text, reply_markup=keyboard)
        return True
    except Exception:
        pass
    if photo_id:
        try:
            await message.answer_photo(photo_id, caption=text, reply_markup=keyboard)
            return True
        except Exception:
            pass
    try:
        await message.answer(text, reply_markup=keyboard)
        return True
    except Exception:
        return False
