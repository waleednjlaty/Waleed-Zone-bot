"""تجميع معالجات البوت وتزويد الدالة register_all_routers()."""

from __future__ import annotations

from aiogram import Dispatcher

from app.handlers.steamrip import router as steamrip_router

from app.handlers import (
    admin,
    applications,
    group,
    requests,
    search,
    start,
    upload,
)

# داخل دالة register_all_routers(dp):


def register_all_routers(dp: Dispatcher) -> None:
    dp.include_router(start.router)
    dp.include_router(applications.router)
    dp.include_router(steamrip_router)
    dp.include_router(search.router)
    dp.include_router(requests.router)
    dp.include_router(upload.router)
    dp.include_router(admin.router)
    dp.include_router(group.router)
