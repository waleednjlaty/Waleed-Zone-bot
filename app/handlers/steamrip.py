"""معالجات التحميل اللحظي والنشر السريع لألعاب SteamRIP."""

from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from integrations.steamrip_extractor import fetch_game_data, extract_bzzhr_direct_link
from app.keyboards.user import cancel_keyboard
from app.utils.helpers import is_admin, escape_html, build_search_text
from app.utils.constants import AdminCB
from database import repositories as repo

logger = logging.getLogger(__name__)

router = Router(name="steamrip")

# حالات مخصصة لملف SteamRIP لعدم التداخل مع معالجات الرفع العادية
class SteamRipStates(StatesGroup):
    waiting_game_url = State()
    waiting_custom_link = State()

@router.callback_query(F.data.startswith("rip_dl:") | F.data.startswith("rip_refresh:"))
async def on_fetch_live_download(call: CallbackQuery, session: AsyncSession) -> None:
    app_id = int(call.data.split(":")[1])
    
    app = await repo.get_application(session, app_id)
    if not app:
        await call.answer("❌ لم يتم العثور على اللعبة.", show_alert=True)
        return

    # إذا قام الإدمن مسبقاً بإضافة رابط مخصص للعبة، نرسله مباشرة
    if app.shrankme_url:
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 بدء التحميل المباشر", url=app.shrankme_url)],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"app:view:{app_id}")]
        ])
        await call.message.edit_text(
            f"🎮 **{escape_html(app.name)}**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"✅ تم تجهيز الرابط المباشر للعبة.",
            reply_markup=markup
        )
        return

    if not app.devupload_url:
        await call.answer("❌ لم يتم العثور على رابط المصدر.", show_alert=True)
        return

    await call.message.edit_text("⏳ جاري البحث عن سيرفر BZZHR وسحب الرابط المباشر...")

    try:
        game_data = await fetch_game_data(app.devupload_url)
        servers = game_data.get("servers", {})
        
        if not servers:
            await call.message.edit_text("⚠️ السيرفرات قيد التحديث في المصدر حالياً، يرجى إعادة المحاولة بعد قليل.")
            return

        bzzhr_url = next((url for name, url in servers.items() if "BZZHR" in name.upper()), None)
        
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
                return
            else:
                await call.message.edit_text(
                    "❌ تعذر استخراج الرابط المباشر من صفحة BZZHR. قد يكون الموقع غير تصميم الصفحة.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔙 رجوع", callback_data=f"app:view:{app_id}")]
                    ])
                )
                return
                
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
    if not is_admin(call.from_user.id):
        await call.answer("⛔ صلاحية غير متاحة. هذا الخيار للإدارة فقط.", show_alert=True)
        return
        
    app_id = int(call.data.split(":")[1])
    await state.update_data(target_app_id=app_id)
    await state.set_state(SteamRipStates.waiting_custom_link)
    
    await call.message.edit_text(
        "🔗 **إضافة رابط تحميل مخصص**\n\n"
        "أرسل الرابط المباشر الذي ترغب بإضافته لهذه اللعبة ليتم حفظه كبديل لسيرفر BZZHR:",
        reply_markup=cancel_keyboard()
    )

@router.message(SteamRipStates.waiting_custom_link)
async def on_custom_link_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return

    new_link = message.text.strip()
    if not new_link.startswith("http"):
        await message.reply("❌ أرسل رابطاً صحيحاً.", reply_markup=cancel_keyboard())
        return

    data = await state.get_data()
    app_id = data.get("target_app_id")

    app = await repo.get_application(session, app_id)
    if not app:
        await message.reply("❌ تعذر العثور على التطبيق في قاعدة البيانات.")
        await state.clear()
        return

    # حفظ الرابط المخصص كحل بديل ودائم للعبة
    app.shrankme_url = new_link
    await session.commit()

    await message.reply(
        f"✅ **تم تحديث اللعبة بنجاح!**\n\n"
        f"تم دمج الرابط المخصص للعبة {escape_html(app.name)} وسيعمل زر التحميل الآن مباشرة."
    )
    await state.clear()

@router.callback_query(AdminCB.filter(F.action == "add_rip_game"))
async def on_add_rip_game_btn(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return
    await call.answer()
    
    await state.set_state(SteamRipStates.waiting_game_url)
    await call.message.edit_text(
        "🎮 **إضافة لعبة من SteamRIP**\n\n"
        "أرسل رابط صفحة اللعبة من موقع SteamRIP الآن:\n"
        "*(سيتم سحب الصور والبيانات ونشرها أوتوماتيكياً)*",
        reply_markup=cancel_keyboard()
    )

@router.message(SteamRipStates.waiting_game_url)
async def on_steamrip_url_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not is_admin(message.from_user.id):
        return

    page_url = message.text.strip()
    if not page_url.startswith("http"):
        await message.reply("❌ أرسل رابطاً صحيحاً يبدأ بـ http أو https", reply_markup=cancel_keyboard())
        return

    status_msg = await message.reply("⏳ جاري سحب بيانات اللعبة وصورتها أوتوماتيكياً...")

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
            search_text=build_search_text(game["title"], "Games", "Windows", game["title"])
        )
        await session.commit()

        await status_msg.edit_text(
            f"✅ **تمت الإضافة بنجاح عبر الأتمتة!**\n\n"
            f"🎮 الاسم: `{game['title']}`\n"
            f"💾 الحجم: `{game['size']}`\n"
            f"🆔 ID التطبيق: `{app.id}`\n\n"
            f"💡 عندما يضغط المستخدمون على زر التحميل، سيقوم البوت بسحب رابط BZZHR المباشر حصرياً."
        )
        await state.clear()

    except Exception as exc:
        logger.error("RIP publish error: %s", exc)
        await status_msg.edit_text(f"❌ فشل جلب بيانات اللعبة:\n`{escape_html(str(exc))}`")
        await state.clear()

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
            search_text=build_search_text(game["title"], "Games", "Windows", game["title"])
        )
        await session.commit()

        await status_msg.edit_text(
            f"✅ **تمت إضافة اللعبة إلى البوت بنجاح!**\n\n"
            f"🎮 الاسم: `{game['title']}`\n"
            f"💾 الحجم: `{game['size']}`\n"
            f"🆔 ID التطبيق: `{app.id}`\n\n"
            f"💡 سيتم جلب رابط التحميل تلقائياً عند طلب المستخدم."
        )
    except Exception as exc:
        logger.error("RIP publish error: %s", exc)
        await status_msg.edit_text(f"❌ فشل جلب بيانات اللعبة:\n`{escape_html(str(exc))}`")