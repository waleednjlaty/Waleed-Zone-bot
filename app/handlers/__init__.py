"""تجميع معالجات البوت وتزويد الدالة register_all_routers()."""

from __future__ import annotations

import logging

from aiogram import Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.exception import ExceptionTypeFilter
from aiogram.types import ErrorEvent

from app.handlers import (
    admin,
    applications,
    group,
    requests,
    search,
    start,
    upload,
)
from integrations.steamrip_metadata import fetch_game_data as fetch_steamrip_metadata

from . import steamrip as steamrip_module

# اجعل تدفق /rip يستخدم طبقة metadata المحسنة. الدوال داخل steamrip.py تقرأ
# fetch_game_data من globals وقت التنفيذ، لذلك الاستبدال هنا يطبّق على كل ألعاب
# SteamRIP الجديدة بدون تكرار منطق الاستخراج داخل الـhandler.
steamrip_module.fetch_game_data = fetch_steamrip_metadata
steamrip_router = steamrip_module.router

logger = logging.getLogger(__name__)


async def _handle_telegram_bad_request(event: ErrorEvent) -> None:
    """تجاهل فقط خطأ Telegram الحميد عند محاولة إرسال نفس التعديل مرتين."""
    exc = event.exception
    message = str(exc).lower()

    if isinstance(exc, TelegramBadRequest) and "message is not modified" in message:
        logger.debug("Ignored harmless Telegram 'message is not modified' error")
        return

    raise exc


def register_all_routers(dp: Dispatcher) -> None:
    # يمنع ضغط نفس زر اللوحة مرتين من تلويث السجل بخطأ غير مؤثر.
    dp.errors.register(
        _handle_telegram_bad_request,
        ExceptionTypeFilter(TelegramBadRequest),
    )

    dp.include_router(start.router)
    dp.include_router(applications.router)
    dp.include_router(steamrip_router)
    dp.include_router(search.router)
    dp.include_router(requests.router)
    dp.include_router(upload.router)
    dp.include_router(admin.router)
    dp.include_router(group.router)
