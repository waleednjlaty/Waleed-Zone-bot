"""أدوات مشتركة بين المعالجات: عرض صفحة تطبيق و إرسال/تعديل رسائل بأمان."""

from __future__ import annotations

from typing import Union

from aiogram import Bot
from aiogram.types import CallbackQuery, InputMediaPhoto, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.user import app_detail_keyboard
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


async def show_app(
    target: Target,
    session: AsyncSession,
    bot: Bot,
    app_id: int,
) -> bool:
    """عرض صفحة تطبيق (صورة إن وُجدت + زر تحميل + مفضلة + إشعارات)."""
    app = await repo.get_active_application(session, app_id)
    if app is None:
        await answer_target(target, "❌ التطبيق غير موجود أو تم تعطيله.")
        return False

    await repo.increment_views(session, app_id)

    user_id = target.from_user.id
    is_fav = await repo.is_favorite(session, user_id, app_id)
    kb = app_detail_keyboard(
        app_id,
        is_fav=is_fav,
        is_admin_user=is_admin(user_id),
    )
    text = app_card(app)
    photo = app.icon_file_id or app.image_url

    if isinstance(target, CallbackQuery):
        return await _edit_message(
            target.message,
            text=text,
            keyboard=kb,
            photo_id=photo,
        )

    if photo:
        await target.answer_photo(photo, caption=text, reply_markup=kb)
    else:
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
            await message.edit_media(
                InputMediaPhoto(media=photo_id, caption=text),
                reply_markup=keyboard,
            )
            return True
        except Exception:
            pass
    try:
        await message.edit_text(text, reply_markup=keyboard)
        return True
    except Exception:
        try:
            if photo_id:
                await message.answer_photo(photo_id, caption=text, reply_markup=keyboard)
            else:
                await message.answer(text, reply_markup=keyboard)
            return True
        except Exception:
            return False
