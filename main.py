"""نقطة تشغيل البوت (Waleed Zone Bot).

    python main.py
"""

from __future__ import annotations

import asyncio
import logging
import os  # 👈 تمت إضافة هذا السطر هنا

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.types import BotCommand  # تم نقله للأعلى لترتيب الاستدعاءات بشكل نظيف

from app.handlers import register_all_routers
from app.middlewares import (
    AccessMiddleware,
    DbSessionMiddleware,
    ThrottleMiddleware,
)
from app.utils.logging_config import setup_logging
from config import get_settings
from database import init_db

logger = logging.getLogger("main")


async def set_default_commands(bot):
    commands = [
        BotCommand(command="start", description="تشغيل البوت وبدء الاستخدام"),
        # يمكنك إضافة أي أوامر أخرى هنا مستقبلاً
    ]
    await bot.set_my_commands(commands)


async def main() -> None:
    setup_logging()
    settings = get_settings()

    # 👈 محاولة إنشاء المجلدات، وتخطي الخطأ إذا كان السيرفر مجانياً (Trial) ومحمياً
    try:
        os.makedirs("data", exist_ok=True)
        os.makedirs("tmp", exist_ok=True)
    except PermissionError:
        logger.warning("⚠️ البوت يعمل في بيئة محمية (Trial). سيتم تجاهل إنشاء المجلدات.")

    if not settings.BOT_TOKEN:
        raise SystemExit("❌ BOT_TOKEN غير موجود في ملف .env")

    db = init_db(settings.DATABASE_URL)
    await db.init_models()

    bot = Bot(
        settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await set_default_commands(bot)
    dp = Dispatcher(storage=MemoryStorage(), events_isolation=SimpleEventIsolation())

    # ترتيب الوسطاء: الخارجي أولًا (قاعدة البيانات ثم الوصول ثم الفيض)
    dp.message.middleware(DbSessionMiddleware())
    dp.message.middleware(AccessMiddleware())
    dp.message.middleware(ThrottleMiddleware())

    dp.callback_query.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(AccessMiddleware())
    dp.callback_query.middleware(ThrottleMiddleware())

    dp.chat_member.middleware(DbSessionMiddleware())

    register_all_routers(dp)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Waleed Zone Bot is running...")
        await dp.start_polling(bot)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
