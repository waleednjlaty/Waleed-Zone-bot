"""معالجات التحميل اللحظي والنشر السريع لألعاب SteamRIP."""

from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

# لاحظ هنا أضفنا استدعاء الدالة الجديدة التي صنعناها في الخطوة 2
from integrations.steamrip_extractor import fetch_game_data, extract_bzzhr_direct_link
from app.keyboards.user import cancel_keyboard
from app.utils.helpers import is_admin, escape_html, build_search_text
from app.utils.constants import AdminCB
from database import repositories as repo

logger = logging.getLogger(__name__)

router = Router(name="steamrip")


@router.callback_query(F.data.startswith("rip_dl:") | F.data.startswith("rip_refresh:"))
async def on_fetch_live_download(call: CallbackQuery, session: AsyncSession) -> None:
    app_id = int(call.data.split(":")[1])
    
    app = await repo.get_application(session, app_id)
    if not app or not app.devupload_url:
        await call.answer("❌ لم يتم العثور على رابط المصدر.", show_alert=True)
        return

    # رسالة الانتظار أثناء عملية الدخول والاختراق للصفحات
    await call.message.edit_text("⏳ جاري البحث عن سيرفر BZZHR وسحب الرابط المباشر...")

    try:
        game_data = await fetch_game_data(app.devupload_url)
        servers = game_data.get("servers", {})
        
        if not servers:
            await call.message.edit_text("⚠️ السيرفرات قيد التحديث في المصدر حالياً، يرجى إعادة المحاولة بعد قليل.")
            return

        # 1. البحث عن سيرفر BZZHR من القائمة
        bzzhr_url = None
        for server_name, server_url in servers.items():
            if "BZZHR" in server_name.upper():
                bzzhr_url = server_url
                break
        
        # 2. في حال العثور على BZZHR: ندخل ونسحب الرابط
        if bzzhr_url:
            direct_link = await extract_bzzhr_direct_link(bzzhr_url)
            
            if direct_link:
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📥 بدء التحميل المباشر", url=direct_link)],
                    [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"app:view:{app_id}")]
                ])
                await call.message.edit_text(
                    f"🎮 **{escape_html(app.name)}**\n"
                    f"💾 **الحجم:** {escape_html(app.size or game_data.get('size') or '—')}\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"✅ تم العثور على الرابط المباشر من سيرفر **BZZHR** بنجاح.",
                    reply_markup=markup
                )
            else:
                await call.message.edit_text(
                    "❌ تعذر استخراج الرابط المباشر من صفحة BZZHR. قد يكون الموقع غير تصميم الصفحة.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"app:view:{app_id}")]
                    ])
                )
                
        # 3. في حال لم يتم العثور على BZZHR إطلاقاً
        else:
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 بحث في منصة أخرى", switch_inline_query_current_chat=f"{app.name}")],
                [InlineKeyboardButton(text="➕ إضافة رابط تحميل (للإدمن)", callback_data=f"add_custom_link:{app_id}")],
                [InlineKeyboardButton(text="🔙 رجوع للملف", callback_data=f"app:view:{app_id}")]
            ])
            await call.message.edit_text(
                f"⚠️ **سيرفر BZZHR غير متوفر لهذه اللعبة.**\n\n"
                f"لم يتم العثور على السيرفر المطلوب للعبة **{escape_html(app.name)}**.\n"
                f"يرجى تحديد إجراء بديل:",
                reply_markup=markup
            )

    except Exception as exc:
        logger.error("Live scrape failed: %s", exc)
        await call.message.edit_text(f"❌ تعذر جلب الروابط:\n`{escape_html(str(exc))}`")


@router.callback_query(F.data.startswith("add_custom_link:"))
async def on_add_custom_link(call: CallbackQuery, state: FSMContext) -> None:
    """معالجة زر 'إضافة رابط تحميل' للإدمن في حال لم يجد BZZHR"""
    if not is_admin(call.from_user.id):
        await call.answer("⛔ صلاحية غير متاحة. هذا الخيار للإدارة فقط.", show_alert=True)
        return
        
    app_id = int(call.data.split(":")[1])
    await state.update_data(target_app_id=app_id)
    
    from app.states import UploadStates
    await state.set_state(UploadStates.waiting_remote_url)
    
    await call.message.edit_text(
        "🔗 **إضافة رابط تحميل مخصص**\n\n"
        "أرسل الرابط المباشر الذي ترغب بإضافته لهذه اللعبة الآن:",
        reply_markup=cancel_keyboard()
    )


@router.callback_query(AdminCB.filter(F.action == "add_rip_game"))
async def on_add_rip_game_btn(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return
    await call.answer()
    from app.states import UploadStates
    await state.set_state(UploadStates.waiting_remote_url)
    await call.message.edit_text(
        "🎮 **إضافة لعبة من SteamRIP**\n\n"
        "أرسل رابط صفحة اللعبة من موقع SteamRIP الآن:\n"
        "*(مثال: `https://steamrip.com/game-name-free-download/`)*",
        reply_markup=cancel_keyboard()
    )


@router.message(Command("rip"))
async def on_quick_publish_rip(message: Message, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].startswith("http"):
        await message.reply("⚠️ **طريقة الاستخدام:**\n`/rip https://steamrip.com/game-name-free-download/`")
        return

    page_url = args[1].strip()
    status_msg = await message.reply("⏳ جاري سحب بيانات اللعبة وصورتها من SteamRIP...")

    try:
        game = await fetch_game_data(page_url)
        
        app = await repo.create_application(
            session,
            name=game["title"],
            description=f"تحميل لعبة {game['title']} كاملة ومجانية من سيرفرات سريعة.",
            version="Latest",
            size=game["size"],
            category="Games",
            platform="Windows",
            image_url=game["image_url"],
            devupload_url=page_url,
            # تم إزالة published=True و active=True من هنا لتطابق قاعدة بياناتك
            search_text=build_search_text(game["title"], "Games", "Windows", game["title"])
        )
        await session.commit()

        await status_msg.edit_text(
            f"✅ **تمت إضافة اللعبة إلى البوت بنجاح!**\n\n"
            f"🎮 الاسم: `{game['title']}`\n"
            f"💾 الحجم: `{game['size']}`\n"
            f"🆔 ID التطبيق: `{app.id}`\n\n"
            f"💡 عندما يضغط المستخدمون على زر التحميل، سيقوم البوت بسحب رابط BZZHR المباشر حصرياً."
        )

    except Exception as exc:
        logger.error("RIP publish error: %s", exc)
        await status_msg.edit_text(f"❌ فشل جلب بيانات اللعبة:\n`{escape_html(str(exc))}`")