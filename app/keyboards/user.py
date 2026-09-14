"""لوحات مفاتيح المستخدم العادي — تصميم بسيط مناسب للموبايل."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.utils.constants import (
    AppCB,
    AppsCB,
    FavsCB,
    LatestCB,
    MainMenuCB,
    NotifCB,
    ReqCB,
    SearchCB,
)
from app.utils.helpers import paginate
from config import get_settings

PER_PAGE = 8


def main_menu_keyboard(*, is_admin_user: bool = False) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📱 التطبيقات", callback_data=AppsCB(category="cats", page=0).pack()),
        
            InlineKeyboardButton(text="🔎 بحث عن تطبيق", callback_data=SearchCB(action="start").pack()),
        ],
        [InlineKeyboardButton(text="🆕 أحدث التطبيقات", callback_data=LatestCB(page=0).pack())],
       # [InlineKeyboardButton(text="❤️ تطبيقاتي المفضلة", callback_data=FavsCB(page=0).pack())],
        [InlineKeyboardButton(text="📥 طلب تطبيق", callback_data=ReqCB(action="start", req_id=0).pack())],
        [
            InlineKeyboardButton(text="📢 القناة", callback_data=MainMenuCB(action="channel").pack()),
            InlineKeyboardButton(text="💬 المجموعة", callback_data=MainMenuCB(action="group").pack()),
        ],
        [InlineKeyboardButton(text="ℹ️ التعليمات", callback_data=MainMenuCB(action="help").pack())],
    ]
    if is_admin_user:
        kb += [
            [InlineKeyboardButton(text="🚀 رفع تطبيق", callback_data=AppCB(action="upload", app_id=0).pack())],
            [InlineKeyboardButton(text="⚙️ لوحة الإدارة", callback_data=MainMenuCB(action="admin").pack())],
        ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def categories_keyboard(categories: list[str], *, current: str = "all") -> InlineKeyboardMarkup:
    kb: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(
            text="🗂 جميع التصنيفات" if current != "all" else "🗂 جميع التصنيفات ✅",
            callback_data=AppsCB(category="all", page=0).pack(),
        )]
    ]
    row: list[InlineKeyboardButton] = []
    for i, cat in enumerate(categories):
        label = cat
        if current.lower() == cat.lower():
            label = f"{cat} ✅"
        btn = InlineKeyboardButton(text=label, callback_data=AppsCB(category=cat, page=0).pack())
        row.append(btn)
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(text="🏠 القائمة الرئيسية", callback_data=MainMenuCB(action="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def apps_list_keyboard(
    apps: list, category: str, page: int, total_pages: int
) -> InlineKeyboardMarkup:
    kb: list[list[InlineKeyboardButton]] = []
    for app in apps:
        kb.append(
            [InlineKeyboardButton(
                text=f"📱 {app.name}",
                callback_data=AppCB(action="open", app_id=app.id).pack(),
            )]
        )
    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️ السابق", callback_data=AppsCB(category=category, page=page - 1).pack()))
        nav.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="➡️ التالي", callback_data=AppsCB(category=category, page=page + 1).pack()))
        kb.append(nav)
    kb.append(
        [
            InlineKeyboardButton(text="🗂 التصنيفات", callback_data=AppsCB(category="cats", page=0).pack()),
            InlineKeyboardButton(text="🏠 القائمة", callback_data=MainMenuCB(action="main").pack()),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=kb)


def latest_keyboard(apps: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
    kb: list[list[InlineKeyboardButton]] = []
    for app in apps:
        kb.append(
            [InlineKeyboardButton(
                text=f"🆕 {app.name}",
                callback_data=AppCB(action="open", app_id=app.id).pack(),
            )]
        )
    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️ السابق", callback_data=LatestCB(page=page - 1).pack()))
        nav.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="➡️ التالي", callback_data=LatestCB(page=page + 1).pack()))
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="🏠 القائمة الرئيسية", callback_data=MainMenuCB(action="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def favorites_keyboard(apps: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
    kb: list[list[InlineKeyboardButton]] = []
    for app in apps:
        kb.append(
            [InlineKeyboardButton(
                text=f"❤️ {app.name}",
                callback_data=AppCB(action="open", app_id=app.id).pack(),
            )]
        )
    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️ السابق", callback_data=FavsCB(page=page - 1).pack()))
        nav.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="➡️ التالي", callback_data=FavsCB(page=page + 1).pack()))
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="🏠 القائمة الرئيسية", callback_data=MainMenuCB(action="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def app_detail_keyboard(
    app_id: int,
    *,
    is_fav: bool = False,
    is_admin_user: bool = False,
) -> InlineKeyboardMarkup:
    kb: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(
            text="⬇️ تحميل التطبيق",
            callback_data=AppCB(action="download", app_id=app_id).pack(),
        )],
    ]
    kb.append(
        [
            InlineKeyboardButton(
                text="💔 إزالة من المفضلة" if is_fav else "❤️ إضافة للمفضلة",
                callback_data=AppCB(action="unfav" if is_fav else "fav", app_id=app_id).pack(),
            ),
            InlineKeyboardButton(
                text="🔔 إشعارات",
                callback_data=NotifCB(enabled=1).pack(),
            ),
        ]
    )
    if is_admin_user:
        kb.append(
            [InlineKeyboardButton(
                text="⚙️ إدارة التطبيق",
                callback_data=AppCB(action="manage", app_id=app_id).pack(),
            )]
        )
    kb.append(
        [
            InlineKeyboardButton(text="🆕 أحدث", callback_data=LatestCB(page=0).pack()),
            InlineKeyboardButton(text="🏠 القائمة", callback_data=MainMenuCB(action="main").pack()),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=kb)


def confirm_download_keyboard(app_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬇️ تحميل التطبيق",
                    url=None,
                    callback_data=AppCB(action="download", app_id=app_id).pack(),
                )
            ]
        ]
    )
    return kb


def notifications_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    on = "🔔 تفعيل ✅" if enabled else "🔔 تفعيل"
    off = "🔕 إيقاف" if enabled else "🔕 إيقاف ✅"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=on, callback_data=NotifCB(enabled=1).pack()),
                InlineKeyboardButton(text=off, callback_data=NotifCB(enabled=0).pack()),
            ],
            [InlineKeyboardButton(text="🏠 القائمة", callback_data=MainMenuCB(action="main").pack())],
        ]
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=MainMenuCB(action="main").pack())]
        ]
    )


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 القائمة الرئيسية", callback_data=MainMenuCB(action="main").pack())]
        ]
    )


def force_subscribe_keyboard() -> InlineKeyboardMarkup:
    settings = get_settings()
    kb: list[list[InlineKeyboardButton]] = []
    if settings.CHANNEL_USERNAME:
        kb.append(
            [InlineKeyboardButton(text="📢 الاشتراك بالقناة", url=f"https://t.me/{settings.CHANNEL_USERNAME}")]
        )
    kb.append(
        [InlineKeyboardButton(text="✅ تحقق", callback_data=MainMenuCB(action="check_sub").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=kb)


def channel_group_links_keyboard() -> InlineKeyboardMarkup:
    settings = get_settings()
    kb: list[list[InlineKeyboardButton]] = []
    if settings.CHANNEL_USERNAME:
        kb.append([InlineKeyboardButton(text="📢 القناة", url=f"https://t.me/{settings.CHANNEL_USERNAME}")])
    if settings.GROUP_USERNAME:
        kb.append([InlineKeyboardButton(text="💬 المجموعة", url=f"https://t.me/{settings.GROUP_USERNAME}")])
    kb.append([InlineKeyboardButton(text="🏠 القائمة", callback_data=MainMenuCB(action="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=kb)
