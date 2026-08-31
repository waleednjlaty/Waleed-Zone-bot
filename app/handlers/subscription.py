from aiogram.types import CallbackQuery , Message
from aiogram import Bot
from typing import Union
from config import settings
from app.middlewares import is_subscribed


async def require_subscription(event:Union[Message,CallbackQuery],bot:Bot) ->bool:
   
    user_id =event.from_user.id
    if await is_subscribed(bot,user_id,settings.CHANNEL_USERNAME):
        return True
        text =   "الرجاء الاشتراك بلقناة قبل استخدام البوت 🔔"
        if isinstance(event,CallbackQuery):
            await event.answer(text,show_alert=True)
        else:
            await event.answer(text)
        return False