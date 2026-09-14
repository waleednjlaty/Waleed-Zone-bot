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

from .steamrip import router as steamrip_router

logger = logging.getLogger(__name__)


async def _handle_telegram_bad_request(event: ErrorEvent) -> bool:
    """تجاهل فقط خطأ Telegram الحميد عند محاولة إرسال نفس التعديل مرتين."""
    exc = event.exception
    message = str(exc).lower()

    if isinstance(exc, TelegramBadRequest) and "message is not modified" in message:
        logger.debug("Ignored harmless Telegram 'message is not modified' error")
        return True

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
