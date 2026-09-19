"""لوحات التحكم لروابط ألعاب SteamRIP.

روابط التحميل نفسها يجب أن تظهر داخل نص الرسالة، وليس كأزرار URL.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_dynamic_servers_keyboard(servers: dict[str, str], app_id: int) -> InlineKeyboardMarkup:
    """أزرار تحكم فقط؛ روابط السيرفرات تُعرض داخل نص الرسالة."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 تحديث الروابط",
                    callback_data=f"rip_refresh:{app_id}",
                ),
                InlineKeyboardButton(
                    text="🔙 رجوع",
                    callback_data=f"app:view:{app_id}",
                ),
            ]
        ]
    )
