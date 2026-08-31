"""لوحات الأزرار التفاعلية لروابط ألعاب SteamRIP."""

from __future__ import annotations
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def build_dynamic_servers_keyboard(servers: dict[str, str], app_id: int) -> InlineKeyboardMarkup:
    """بناء أزرار السيرفرات شبكياً (2x2) مع زر التحديث وزر الرجوع."""
    keyboard: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []

    for server_name, server_url in servers.items():
        current_row.append(
            InlineKeyboardButton(text=server_name, url=server_url)
        )
        if len(current_row) == 2:
            keyboard.append(current_row)
            current_row = []

    if current_row:
        keyboard.append(current_row)

    # صف الأزرار الإضافية للتحكم
    keyboard.append([
        InlineKeyboardButton(text="🔄 تحديث الروابط", callback_data=f"rip_refresh:{app_id}"),
        InlineKeyboardButton(text="🔙 رجوع", callback_data=f"app:view:{app_id}"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)