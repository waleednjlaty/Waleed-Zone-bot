"""لوحات مفاتيح لوحة الإدارة — للمالك فقط."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.utils.constants import AdminCB, AppCB, BannedWordCB, MainMenuCB, ReqCB


def _button(text: str, callback_data: str) -> InlineKeyboardButton:
    """إنشاء زر موحّد لتقليل أخطاء بناء أزرار لوحة الإدارة."""
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [_button("📊 الإحصائيات", AdminCB(action="stats", page=0).pack()),
         _button("⚙️ الإعدادات", AdminCB(action="settings", page=0).pack())],
        [_button("🚀 رفع تطبيق", AppCB(action="upload", app_id=0).pack()),
         _button("🎮 إضافة لعبة", AdminCB(action="add_rip_game", page=0).pack())],
        [_button("📱 إدارة التطبيقات", AdminCB(action="apps", page=0).pack()),
         _button("📥 طلبات التطبيقات", AdminCB(action="requests", page=0).pack())],
        [_button("📢 نشر في القناة", AdminCB(action="publish_select", page=0).pack()),
         _button("🖼 ترحيل الصور", AdminCB(action="migrate_images", page=0).pack())],
        [_button("👥 إدارة المجموعة", AdminCB(action="group", page=0).pack()),
         _button("📣 إرسال إعلان", AdminCB(action="broadcast", page=0).pack())],
        [_button("🏠 القائمة الرئيسية", MainMenuCB(action="main").pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def apps_management_keyboard(apps: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
    kb: list[list[InlineKeyboardButton]] = []
    if not apps:
        kb.append([_button("📭 لا توجد تطبيقات", "noop")])
    for app in apps:
        kb.append(
            [_button(
                text=f"{'🚫 ' if not app.active else ''}📱 {app.name}",
                callback_data=AdminCB(action="app_manage", app_id=app.id, page=page).pack(),
            )]
        )
    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(_button("⬅️ السابق", AdminCB(action="apps", page=page - 1).pack()))
        nav.append(_button(f"📄 {page + 1}/{total_pages}", "noop"))
        if page < total_pages - 1:
            nav.append(_button("التالي ➡️", AdminCB(action="apps", page=page + 1).pack()))
        kb.append(nav)
    kb.append(
        [
            _button("➕ إضافة تطبيق", AdminCB(action="add_app", page=0).pack()),
            _button("🎮 إضافة لعبة", AdminCB(action="add_rip_game", page=0).pack()),
        ]
    )
    kb.append(
        [_button("⚙️ لوحة الإدارة", AdminCB(action="panel", page=0).pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=kb)


def app_manage_keyboard(app_id: int, active: bool, page: int) -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton(text="✏️ تعديل", callback_data=AdminCB(action="edit_app", app_id=app_id, page=page).pack()),
            InlineKeyboardButton(text="🗑 حذف", callback_data=AdminCB(action="delete_ask", app_id=app_id, page=page).pack()),
        ],
        [
            InlineKeyboardButton(text="🔗 رابط التحميل", callback_data=AdminCB(action="app_link", app_id=app_id, page=page).pack()),
            InlineKeyboardButton(text="📊 إحصائيات", callback_data=AdminCB(action="app_stats", app_id=app_id, page=page).pack()),
        ],
        [
            InlineKeyboardButton(text="📢 نشر بالقناة", callback_data=AdminCB(action="publish", app_id=app_id, page=page).pack()),
            InlineKeyboardButton(
                text="🚫 تعطيل" if active else "✅ تفعيل",
                callback_data=AdminCB(action="toggle", app_id=app_id, page=page).pack(),
            ),
        ],
        [InlineKeyboardButton(text="⬅️ رجوع", callback_data=AdminCB(action="apps", page=page).pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def delete_confirm_keyboard(app_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑 نعم، احذف", callback_data=AdminCB(action="delete_yes", app_id=app_id, page=page).pack()),
                InlineKeyboardButton(text="❌ إلغاء", callback_data=AdminCB(action="app_manage", app_id=app_id, page=page).pack()),
            ]
        ]
    )


def requests_keyboard(requests: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
    kb: list[list[InlineKeyboardButton]] = []
    if not requests:
        kb.append([_button("📭 لا توجد طلبات حالياً", "noop")])
    for i, req in enumerate(requests, start=page * 10 + 1):
        kb.append(
            [InlineKeyboardButton(
                text=f"{req.status} #{i} — {req.app_name[:30]}",
                callback_data=ReqCB(action="manage", req_id=req.id).pack(),
            )]
        )
    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=AdminCB(action="requests", page=page - 1).pack()))
        nav.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=AdminCB(action="requests", page=page + 1).pack()))
        kb.append(nav)
    kb.append(
        [InlineKeyboardButton(text="🔙 لوحة الإدارة", callback_data=AdminCB(action="panel", page=0).pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=kb)


def request_manage_keyboard(req_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تم التنفيذ", callback_data=ReqCB(action="complete", req_id=req_id).pack()),
            ],
            [
                InlineKeyboardButton(text="⏳ قيد المعالجة", callback_data=ReqCB(action="process", req_id=req_id).pack()),
                InlineKeyboardButton(text="❌ رفض الطلب", callback_data=ReqCB(action="reject", req_id=req_id).pack()),
            ],
            [InlineKeyboardButton(text="🔙 الطلبات", callback_data=AdminCB(action="requests", page=0).pack())],
        ]
    )


def publish_select_keyboard(apps: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
    kb: list[list[InlineKeyboardButton]] = []
    if not apps:
        kb.append([_button("📭 لا توجد تطبيقات للنشر", "noop")])
    for app in apps:
        kb.append(
            [InlineKeyboardButton(
                text=f"📢 {app.name}",
                callback_data=AdminCB(action="publish", app_id=app.id, page=page).pack(),
            )]
        )
    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=AdminCB(action="publish_select", page=page - 1).pack()))
        nav.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=AdminCB(action="publish_select", page=page + 1).pack()))
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="🔙 لوحة الإدارة", callback_data=AdminCB(action="panel", page=0).pack())])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def group_management_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="👋 إعدادات الترحيب", callback_data=AdminCB(action="welcome", page=0).pack())],
        [InlineKeyboardButton(text="🛡 إعدادات الحماية", callback_data=AdminCB(action="protection", page=0).pack())],
        [InlineKeyboardButton(text="🚫 الكلمات المحظورة", callback_data=AdminCB(action="banned_words", page=0).pack())],
        [InlineKeyboardButton(text="🔔 تنبيه: الأوامر داخل المجموعة", callback_data=AdminCB(action="group_help", page=0).pack())],
        [InlineKeyboardButton(text="🔙 لوحة الإدارة", callback_data=AdminCB(action="panel", page=0).pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def welcome_settings_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    status = "🟢 مفعل" if enabled else "🔴 معطل"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"حالة الترحيب: {status}", callback_data="noop")],
            [InlineKeyboardButton(text="✅ تفعيل" if not enabled else "✅ مفعل", callback_data=AdminCB(action="welcome_on", page=0).pack())],
            [InlineKeyboardButton(text="❌ تعطيل" if enabled else "❌ معطل", callback_data=AdminCB(action="welcome_off", page=0).pack())],
            [InlineKeyboardButton(text="✏️ تعديل الرسالة", callback_data=AdminCB(action="welcome_edit", page=0).pack())],
            [InlineKeyboardButton(text="🔙 إدارة الجروب", callback_data=AdminCB(action="group", page=0).pack())],
        ]
    )


def protection_settings_keyboard(
    anti_spam: bool,
    warn_limit: int,
    warn_action: str,
) -> InlineKeyboardMarkup:
    spam_status = "🟢 مفعل" if anti_spam else "🔴 معطل"
    action_label = "🔇 كتم" if warn_action == "mute" else "🚫 حظر"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🛡 Anti-Spam: {spam_status}", callback_data="noop")],
            [InlineKeyboardButton(text="✅ تفعيل" if not anti_spam else "✅ مفعل", callback_data=AdminCB(action="spam_on", page=0).pack())],
            [InlineKeyboardButton(text="❌ تعطيل" if anti_spam else "❌ معطل", callback_data=AdminCB(action="spam_off", page=0).pack())],
            [InlineKeyboardButton(text=f"⚠️ حد التحذيرات: {warn_limit}", callback_data=AdminCB(action="warn_limit_edit", page=0).pack())],
            [InlineKeyboardButton(text=f"⚡ إجراء التحذيرات: {action_label}", callback_data=AdminCB(action="warn_action_toggle", page=0).pack())],
            [InlineKeyboardButton(text="🔙 إدارة الجروب", callback_data=AdminCB(action="group", page=0).pack())],
        ]
    )


def banned_words_keyboard(words: list[str]) -> InlineKeyboardMarkup:
    kb: list[list[InlineKeyboardButton]] = []
    if not words:
        kb.append([InlineKeyboardButton(text="لا توجد كلمات محظورة", callback_data="noop")])
    for word in words[:20]:
        kb.append(
            [
                InlineKeyboardButton(
                    text=f"🚫 {word}",
                    callback_data=BannedWordCB(action="del", word=word).pack(),
                )
            ]
        )
    kb.append([InlineKeyboardButton(text="➕ إضافة كلمة", callback_data=AdminCB(action="bw_add", page=0).pack())])
    kb.append([InlineKeyboardButton(text="🔙 إدارة الجروب", callback_data=AdminCB(action="group", page=0).pack())],)
    return InlineKeyboardMarkup(inline_keyboard=kb)


def settings_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="🛠 وضع الصيانة", callback_data=AdminCB(action="maintenance", page=0).pack())],
        [InlineKeyboardButton(text="📢 الاشتراك الإجباري", callback_data=AdminCB(action="force_sub", page=0).pack())],
        [InlineKeyboardButton(text="🔔 إشعارات التطبيقات", callback_data=AdminCB(action="notif_global", page=0).pack())],
        [InlineKeyboardButton(text="🔙 لوحة الإدارة", callback_data=AdminCB(action="panel", page=0).pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def broadcast_target_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 مستخدمي البوت", callback_data=AdminCB(action="bc_users", page=0).pack())],
            [InlineKeyboardButton(text="💬 المجموعة", callback_data=AdminCB(action="bc_group", page=0).pack())],
            [InlineKeyboardButton(text="📢 القناة", callback_data=AdminCB(action="bc_channel", page=0).pack())],
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=AdminCB(action="panel", page=0).pack())],
        ]
    )
