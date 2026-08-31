from aiogram.types import CallbackQuery
from aiogram import Bot

from app.config import get_settings
from app.services.subscription import is_subscribed


async def require_subscription(call: CallbackQuery,bot:Bot) ->bool:
    settings =get_settings()
    if await is_subscribed(bot,call.from_user.id,settings.CHANNEL_USERNAME):
        return True
        await call.answer(
            "الرجاء الاشتراك بلقناة قبل استخدام البوت 🔔",
            show_alert=True
        )
        return False