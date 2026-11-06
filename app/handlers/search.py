"""معالجات البحث عن التطبيقات — يدعم العربية والإنجليزية والبحث الجزئي."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.states import SearchStates
from app.utils.constants import AppCB, MainMenuCB, SearchCB
from app.utils.helpers import normalize_text
from app.utils.text import escape_html, search_prompt
from database import repositories as repo

logger = logging.getLogger(__name__)

router = Router(name="search")


@router.callback_query(SearchCB.filter(F.action == "start"))
async def on_search_start(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(SearchStates.waiting_query)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=MainMenuCB(action="main").pack())]
        ]
    )
    await call.message.answer(search_prompt(), reply_markup=kb)


@router.message(SearchStates.waiting_query)
async def on_search_query(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    query = (message.text or "").strip()
    if not query:
        await message.answer(
            "🔎 أرسل اسم التطبيق أو اللعبة كنص، وليس صورة أو ملفًا.\n"
            "مثال: CapCut أو فوتوشوب."
        )
        return
    if len(query) > 80:
        await message.answer("⚠️ عبارة البحث طويلة. اختصرها إلى 80 حرفًا كحد أقصى.")
        return

    normalized = normalize_text(query)
    apps = await repo.search_applications(session, normalized, limit=10)

    await repo.log_search(session, message.from_user.id, query[:200], len(apps))
    await state.clear()

    if not apps:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✏️ تعديل عبارة البحث", callback_data=SearchCB(action="start").pack())],
                [InlineKeyboardButton(text="🏠 القائمة", callback_data=MainMenuCB(action="main").pack())],
            ]
        )
        await message.answer(
            f"❌ لم أجد تطبيقًا باسم «{escape_html(query)}».\n"
            "جرّب تهجئة مختلفة للاسم، أو اكتبه بالعربية أو الإنجليزية، أو استخدم جزءًا من الاسم.\n"
            "يمكنك تعديل عبارة البحث مباشرة من الزر أدناه.",
            reply_markup=kb,
        )
        return

    lines = [
        f"🔎 نتائج البحث عن «{escape_html(query)}»:",
        f"📦 نعرض {len(apps)} نتيجة كحد أقصى من أفضل النتائج المطابقة.",
        "💡 لم تجد ما تبحث عنه؟ يمكنك تعديل عبارة البحث.",
        "",
    ]
    kb_rows: list[list[InlineKeyboardButton]] = []
    for i, app in enumerate(apps, start=1):
        lines.append(f"{i}. {escape_html(app.name)}")
        kb_rows.append(
            [InlineKeyboardButton(
                text=f"{i}. {str(app.name or 'تطبيق')[:55]}",
                callback_data=AppCB(action="open", app_id=app.id).pack(),
            )]
        )
    kb_rows.append(
        [
            InlineKeyboardButton(text="✏️ تعديل البحث", callback_data=SearchCB(action="start").pack()),
            InlineKeyboardButton(text="🏠 القائمة", callback_data=MainMenuCB(action="main").pack()),
        ]
    )
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await message.answer("\n".join(lines), reply_markup=kb)
