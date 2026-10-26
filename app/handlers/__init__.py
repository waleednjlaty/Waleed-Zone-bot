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
    manual_game,
    release_admin,
    remote_import,
    requests,
    search,
    start,
    upload,
)
from integrations.steamrip_metadata import fetch_game_data as fetch_steamrip_metadata

from . import steamrip as steamrip_module

steamrip_module.fetch_game_data = fetch_steamrip_metadata
steamrip_router = steamrip_module.router
logger = logging.getLogger(__name__)


async def _handle_telegram_bad_request(event: ErrorEvent) -> None:
    exc = event.exception
    message = str(exc).lower()
    if isinstance(exc, TelegramBadRequest) and "message is not modified" in message:
        logger.debug("Ignored harmless Telegram 'message is not modified' error")
        return
    raise exc


def register_all_routers(dp: Dispatcher) -> None:
    dp.errors.register(_handle_telegram_bad_request, ExceptionTypeFilter(TelegramBadRequest))
    dp.include_router(start.router)
    dp.include_router(applications.router)
    dp.include_router(manual_game.router)
    dp.include_router(steamrip_router)
    dp.include_router(search.router)
    dp.include_router(requests.router)
    dp.include_router(upload.router)
    dp.include_router(release_admin.router)
    dp.include_router(remote_import.router)
    dp.include_router(admin.router)
    dp.include_router(group.router)
