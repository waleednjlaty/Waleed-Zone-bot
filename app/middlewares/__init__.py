"""Middlewares: جلسة قاعدة البيانات، فحص الوصول، ومكافحة الفيض الخفيفة."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, TelegramObject, User
from aiogram.enums import ChatType
from app.utils.helpers import is_admin
from sqlalchemy.orm.exc import StaleDataError
from config import get_settings
from database import get_db
from database.repositories import get_setting_bool

HandlerType = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class DbSessionMiddleware:
    """حقن جلسة قاعدة البيانات في كل حدث (message/callback).

    يُنفَّذ ``commit`` تلقائيًا بعد نجاح المعالج حتى لا تضيع أي كتابة في
    قاعدة البيانات (كانت كل الجلسات تُغلق دون commit فتُتراجع التغييرات).
    """

    async def __call__(self, handler: HandlerType, event: TelegramObject, data: dict[str, Any]) -> Any:
        db = get_db()
        async with db.session() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
            except StaleDataError:
                await session.rollback()
                state = data.get("state")
                if state:
                    await state.clear()
                await event.answer("⚠️ تغيّر التطبيق أثناء التعديل. افتحه مجددًا واقرأ النسخة الحالية.")
                return
            except asyncio.CancelledError:
                await session.rollback()
                raise
            except Exception:
                await session.rollback()
                raise
            await session.commit()
            return result


async def is_subscribed(bot: Bot, user_id: int, channel_username: str | None) -> bool:
    if not channel_username:
        return True
    try:
        member = await bot.get_chat_member(f"@{channel_username}", user_id)
        return member.status in {"member", "administrator", "creator"}
    except Exception:
        # البوت ليس أدمن في القناة، أو خطأ — لا نعطل المستخدمين
        return True


class AccessMiddleware:
    """فحص وضع الصيانة والاشتراك الإجباري للمحادثات الخاصة.

    - وضع الصيانة: يحجب غير المالكين.
    - الاشتراك الإجباري: يمنع غير المشتركين في القناة.
    جميع الفحوصات تتجاهل المالك (Admin).
    """

    async def __call__(self, handler: HandlerType, event: TelegramObject, data: dict[str, Any]) -> Any:
        session = data.get("session")
        user: User | None = data.get("event_from_user")
        bot: Bot = data.get("bot")
        if session is None or user is None or bot is None:
            return await handler(event, data)

        chat: Chat | None = getattr(event, "chat", None)
        if chat is None:
            if isinstance(event, CallbackQuery) and event.message:
                chat = event.message.chat
        if chat is None or chat.type != ChatType.PRIVATE:
            return await handler(event, data)

        if is_admin(user.id):
            return await handler(event, data)

        # --- وضع الصيانة ---
        maintenance = await get_setting_bool(session, "maintenance_mode", False)
        if maintenance:
            text = "🛠 البوت تحت الصيانة حاليًا.\n\nجرّب لاحقًا وشكرًا لتفهمك."
            if isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            else:
                await event.answer(text)
            return None

        # --- الاشتراك الإجباري ---
        settings = get_settings()
        force_sub = await get_setting_bool(session, "force_subscribe", False)
        if force_sub and settings.CHANNEL_USERNAME:
            subscribed = await is_subscribed(bot, user.id, settings.CHANNEL_USERNAME)
            if not subscribed:
                text = (
                    "⚠️ اشترك في قناتنا أولًا لتتمكن من استخدام البوت.\n\n"
                    f"📢 القناة: @{settings.CHANNEL_USERNAME}"
                )
                if isinstance(event, CallbackQuery):
                    await event.answer("⚠️ اشترك في القناة أولًا", show_alert=True)
                else:
                    from app.keyboards.user import force_subscribe_keyboard

                    await event.answer(text, reply_markup=force_subscribe_keyboard())
                return None

        return await handler(event, data)


class ThrottleMiddleware:
    """منع الفيض الخفيف: يمنع تكرار الأحداث السريع جدًا من نفس المستخدم.

    صُمم بحيث لا يحذف رسائل المستخدمين العادية ولا يكون عدوانيًا.
    """

    def __init__(self, min_interval: float = 0.4) -> None:
        self._last: dict[int, float] = defaultdict(float)
        self._min_interval = min_interval

    async def __call__(self, handler: HandlerType, event: TelegramObject, data: dict[str, Any]) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None:
            return await handler(event, data)
        if is_admin(user.id):
            return await handler(event, data)

        now = time.monotonic()
        if now - self._last[user.id] < self._min_interval:
            return None
        self._last[user.id] = now
        return await handler(event, data)
