"""معالجات طلبات التطبيقات: طلب المستخدم وإدارة الطلبات (للمالك)."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.admin import request_manage_keyboard
from app.keyboards.user import back_to_menu_keyboard, cancel_keyboard
from app.states import RequestStates
from app.utils.constants import MainMenuCB, ReqCB
from app.utils.helpers import is_admin
from app.utils.text import app_request_notification, escape_html, request_prompt, request_summary
from config import get_settings
from database import repositories as repo

logger = logging.getLogger(__name__)

router = Router(name="requests")


@router.callback_query(ReqCB.filter(F.action == "start"))
async def on_request_start(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(RequestStates.waiting_app_name)
    await call.message.answer(request_prompt(), reply_markup=cancel_keyboard())


@router.message(RequestStates.waiting_app_name)
async def on_request_message(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    app_name = (message.text or "").strip()
    if not app_name:
        await message.answer("📱 اكتب اسم التطبيق أولًا.")
        return
    if len(app_name) > 80:
        await message.answer("⚠️ اسم التطبيق طويل جدًا. اختصره إلى 80 حرفًا كحد أقصى.")
        return

    req = await repo.create_app_request(
        session,
        user_id=message.from_user.id,
        app_name=app_name,
        username=message.from_user.username,
    )
    await state.clear()

    await message.answer(
        "✅ تم استلام طلبك!\n"
        "سنحاول إضافة التطبيق بأسرع وقت ممكن.",
        reply_markup=back_to_menu_keyboard(),
    )

    # إشعار المالكين
    for admin_id in get_settings().admin_ids:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ تم التنفيذ",
                        callback_data=ReqCB(action="complete", req_id=req.id).pack(),
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="⏳ قيد المعالجة",
                        callback_data=ReqCB(action="process", req_id=req.id).pack(),
                    ),
                    InlineKeyboardButton(
                        text="❌ رفض الطلب",
                        callback_data=ReqCB(action="reject", req_id=req.id).pack(),
                    ),
                ],
            ]
        )
        try:
            await message.bot.send_message(
                admin_id,
                app_request_notification(
                    message.from_user.username,
                    message.from_user.id,
                    app_name,
                    req.id,
                ),
                reply_markup=kb,
            )
        except Exception as exc:
            logger.warning("Cannot notify admin %s: %s", admin_id, exc)


# ------------------------------------------------------------ إدارة المالك
@router.callback_query(ReqCB.filter(F.action == "manage"))
async def on_manage_request(
    call: CallbackQuery, callback_data: ReqCB, session: AsyncSession
) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return
    req = await repo.get_app_request(session, callback_data.req_id)
    if req is None:
        await call.answer("الطلب غير موجود.", show_alert=True)
        return
    await call.answer()
    await call.message.edit_text(
        request_summary(req, callback_data.req_id),
        reply_markup=request_manage_keyboard(req.id),
    )


@router.callback_query(ReqCB.filter(F.action.in_(["complete", "process", "reject"])))
async def on_request_status(
    call: CallbackQuery, callback_data: ReqCB, session: AsyncSession
) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return

    status_map = {
        "complete": "completed",
        "process": "processing",
        "reject": "rejected",
    }
    new_status = status_map[callback_data.action]
    req = await repo.set_request_status(session, callback_data.req_id, new_status)
    if req is None:
        await call.answer("الطلب غير موجود.", show_alert=True)
        return

    status_text = {
        "completed": "✅ تم وضع الطلب كمنفَّذ",
        "processing": "⏳ تم وضع الطلب قيد المعالجة",
        "rejected": "❌ تم رفض الطلب",
    }[new_status]

    await call.answer(status_text)
    await call.message.edit_text(
        f"{request_summary(req, callback_data.req_id)}\n\n{status_text}",
        reply_markup=request_manage_keyboard(req.id),
    )

    # إشعار المستخدم صاحب الطلب
    try:
        await call.bot.send_message(
            req.user_id,
            {
                "completed": "✅ طلبك «{name}» تم تنفيذه! 🎉\nافتح البوت وابحث عن التطبيق.",
                "processing": "⏳ طلبك «{name}» قيد المعالجة حاليًا.",
                "rejected": "❌ نعتذر، لم نتمكن من إضافة «{name}».",
            }[new_status].format(name=req.app_name),
        )
    except Exception as exc:
        logger.warning("Cannot notify requester %s: %s", req.user_id, exc)
