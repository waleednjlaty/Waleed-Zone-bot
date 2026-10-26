"""Admin entry point for the guided add-update workflow."""

from __future__ import annotations

from math import ceil

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.constants import AdminCB
from app.utils.helpers import is_admin
from app.utils.owner_guard import owner_gate
from app.utils.versions import latest_per_family, sort_application_versions
from database import repositories as repo

router = Router(name="release_admin")
PAGE_SIZE = 8


@router.callback_query(AdminCB.filter(F.action == "add_update"))
async def on_add_update(call: CallbackQuery, callback_data: AdminCB, session: AsyncSession) -> None:
    if not await owner_gate(call):
        return
    if not call.from_user or not is_admin(call.from_user.id):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return

    apps = await repo.list_applications(session, active_only=True, public_only=False, limit=1000)
    apps = sort_application_versions(latest_per_family(apps))
    total_pages = max(1, ceil(len(apps) / PAGE_SIZE))
    page = max(0, min(callback_data.page, total_pages - 1))
    visible = apps[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    rows = []
    for app in visible:
        name = str(app.name or "تطبيق")[:24]
        version = str(app.version or "إصدار غير محدد")[:14]
        platform = str(app.platform or "نظام غير محدد")[:10]
        rows.append([InlineKeyboardButton(
            text=f"{name} · {version} · {platform}",
            callback_data=AdminCB(action="new_release", app_id=app.id, page=page).pack(),
        )])
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️ السابق", callback_data=AdminCB(action="add_update", page=page - 1).pack()))
        nav.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="التالي ➡️", callback_data=AdminCB(action="add_update", page=page + 1).pack()))
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="⬅️ لوحة الإدارة", callback_data=AdminCB(action="panel", page=0).pack())])
    await call.answer()
    await call.message.edit_text(
        "🆕 إضافة تحديث لتطبيق موجود\n\n"
        "اختر التطبيق الذي تريد تحديثه. سيطلب منك البوت رفع الملف ثم إدخال رقم الإصدار، "
        "وسيبقى الملف القديم ورابطه محفوظين. لا تختَر تطبيقًا مختلفًا لمجرد تشابه الاسم.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
