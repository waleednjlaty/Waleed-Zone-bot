"""Owner uploads and attachments: Telegram copy → shared catalog → optional promo."""
from __future__ import annotations
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm.exc import StaleDataError
from app.keyboards.user import cancel_keyboard
from app.services.upload_service import build_upload_service
from app.states import UploadStates
from app.utils.constants import AdminCB, AppCB, MainMenuCB
from app.utils.helpers import build_search_text, format_size, is_admin
from app.utils.text import escape_html
from app.utils.website import website_app_url, website_download_url
from config import get_settings
from database import repositories as repo
from database.models import Application
from integrations.imgbb import ImgBBUploader

logger = logging.getLogger(__name__)
router = Router(name="upload")


class OwnerUploadMiddleware:
    async def __call__(self, handler, event, data):
        if not event.from_user or not is_admin(event.from_user.id):
            if isinstance(event, CallbackQuery):
                await event.answer("⛔ صلاحية غير متاحة.", show_alert=True)
            else:
                await event.answer("⛔ صلاحية غير متاحة.")
            return
        try:
            return await handler(event,data)
        except StaleDataError:
            await data["session"].rollback()
            await data["state"].clear()
            await event.answer("⚠️ تعارض في التعديل. افتح التطبيق مجددًا.")


router.message.middleware(OwnerUploadMiddleware())
router.callback_query.middleware(OwnerUploadMiddleware())


def _only_admin(call):
    return bool(call.from_user and is_admin(call.from_user.id))


@router.callback_query(AppCB.filter(F.action == "upload"))
@router.callback_query(AdminCB.filter(F.action == "add_app"))
async def on_upload_start(call: CallbackQuery, state: FSMContext) -> None:
    if not _only_admin(call):
        await call.answer("⛔", show_alert=True)
        return
    await state.clear()
    await state.set_state(UploadStates.waiting_file)
    await call.answer()
    await call.message.answer("📤 أرسل ملف APK / ZIP / EXE. سيُنسخ داخل Telegram دون تنزيله للسيرفر.",reply_markup=cancel_keyboard())


@router.callback_query(AdminCB.filter(F.action == "attach_file"))
async def on_attach_file(call: CallbackQuery, callback_data: AdminCB, state: FSMContext, session: AsyncSession) -> None:
    if not _only_admin(call):
        await call.answer("⛔", show_alert=True)
        return
    app = await repo.get_application(session, callback_data.app_id)
    if not app:
        await call.answer("التطبيق غير موجود.",show_alert=True)
        return
    await state.clear()
    await state.update_data(attach_app_id=app.id,expected_revision=app.revision)
    await state.set_state(UploadStates.waiting_file)
    await call.answer()
    await call.message.answer(f"📎 أرسل ملف التطبيق {escape_html(app.name)}. لن تتغير حالة النشر.",reply_markup=cancel_keyboard())


@router.message(UploadStates.waiting_file)
async def on_file(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer("⛔ صلاحية غير متاحة.")
        return
    if not message.document:
        await message.answer("أرسل الملف كمستند Telegram.")
        return
    data = await state.get_data()
    try:
        service = await build_upload_service()
        source = await service.copy(message)
    except Exception:
        # Provider errors may contain credential-bearing URLs. Never echo/log them.
        logger.warning("Telegram file copy failed")
        await message.answer("❌ تعذر النسخ. تحقق من إعدادات قناة الملفات العامة وصلاحية البوت وقيود الرسالة.")
        return
    if data.get("attach_app_id"):
        try:
            await repo.bind_telegram_source(session,data["attach_app_id"],source,expected_revision=data["expected_revision"])
            await session.commit()
        except (StaleDataError, ValueError):
            await session.rollback()
            await state.clear()
            await message.answer("⚠️ تغيّر التطبيق أثناء الربط. افتحه مجددًا. النسخة المنسوخة بقيت في قناة الملفات دون ربط.")
            return
        await state.clear()
        await message.answer("✅ تم ربط الملف بالموقع والبوت.")
        return
    await state.update_data(source=source,size=format_size(source.get("size_bytes") or 0))
    await state.set_state(UploadStates.waiting_name)
    await message.answer("✅ تم نسخ الملف. أرسل اسم التطبيق:")


async def _collect(message, state, field, next_state, prompt, max_length):
    if not message.text or not message.text.strip() or len(message.text.strip()) > max_length:
        await message.answer(f"أرسل نصًا بين 1 و{max_length} حرف.")
        return
    value=message.text.strip()
    if any(ord(c)<32 and (field != "description" or c not in "\n\r\t") for c in value):
        await message.answer("النص يحتوي رموزًا غير مسموحة.")
        return
    await state.update_data(**{field:value})
    await state.set_state(next_state)
    await message.answer(prompt,reply_markup=cancel_keyboard())


@router.message(UploadStates.waiting_name)
async def on_name(message: Message,state: FSMContext):
    await _collect(message,state,"name",UploadStates.waiting_description,"أرسل وصف التطبيق:",255)


@router.message(UploadStates.waiting_description)
async def on_description(message: Message,state: FSMContext):
    await _collect(message,state,"description",UploadStates.waiting_version,"أرسل الإصدار:",1000)


@router.message(UploadStates.waiting_version)
async def on_version(message: Message,state: FSMContext):
    await _collect(message,state,"version",UploadStates.waiting_platform,"أرسل النظام (Android / Windows…):",50)


@router.message(UploadStates.waiting_platform)
async def on_platform(message: Message,state: FSMContext):
    await _collect(message,state,"platform",UploadStates.waiting_category,"أرسل التصنيف (تطبيقات / ألعاب موبايل / ألعاب كمبيوتر…):",50)


@router.message(UploadStates.waiting_category)
async def on_category(message: Message,state: FSMContext):
    await _collect(message,state,"category",UploadStates.waiting_icon,"أرسل صورة التطبيق أو /skip لتجاوزها:",100)


@router.message(UploadStates.waiting_icon)
async def on_icon(message: Message,state: FSMContext):
    photo=message.photo[-1].file_id if message.photo else None
    image_url=None
    if photo:
        image_url=await ImgBBUploader(api_key=get_settings().IMGBB_API_KEY or "").upload_telegram_photo(message.bot,photo)
    elif message.text != "/skip":
        await message.answer("أرسل صورة أو /skip.")
        return
    await state.update_data(icon_file_id=photo,image_url=image_url)
    await state.set_state(UploadStates.waiting_publish_choice)
    data=await state.get_data()
    await message.answer(f"📋 {escape_html(data['name'])} · {escape_html(data.get('version') or '')}\nالملف محفوظ في Telegram. اختر حالة التطبيق:",reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 حفظ مسودة",callback_data="upl:save_draft")],
        [InlineKeyboardButton(text="🚀 حفظ ونشر بالقناة",callback_data="upl:save_publish")],
        [InlineKeyboardButton(text="❌ إلغاء",callback_data=MainMenuCB(action="main").pack())]]))


@router.callback_query(F.data.in_({"upl:save_draft","upl:save_publish"}), UploadStates.waiting_publish_choice)
async def on_confirm_app(call: CallbackQuery,state: FSMContext,session: AsyncSession):
    if not _only_admin(call):
        await call.answer("⛔",show_alert=True)
        return
    data=await state.get_data()
    if not data.get("name") or not data.get("source"):
        await call.answer("بيانات المسودة غير مكتملة.",show_alert=True)
        return
    app=await repo.create_application(session,name=data['name'],description=data.get('description'),version=data.get('version'),
        size=data.get('size'),category=data.get('category'),platform=data.get('platform'),icon_file_id=data.get('icon_file_id'),
        image_url=data.get('image_url'),search_text=build_search_text(data['name'],data.get('category'),data.get('platform'),data.get('description')))
    await repo.bind_telegram_source(session,app.id,data['source'])
    await session.commit()  # Both rows saved atomically before any optional promo.
    await state.clear()
    await call.answer("✅ تم حفظ المسودة")
    await call.message.answer(f"✅ حُفظ التطبيق #{app.id}.\n🌐 {escape_html(website_download_url(app.id) or '')}")
    if call.data == "upl:save_publish":
        await _publish_to_channel(call,session,app)


def channel_promo(app):
    download_url=website_download_url(app.id)
    if not download_url:
        raise ValueError("WEBSITE_URL_NOT_CONFIGURED")
    # Caption limit is 1024; Telegram text and captions are escaped before display.
    text=(f"📱 {escape_html(app.name[:150])}\n📦 {escape_html(app.version or '—')}\n💾 {escape_html(app.size or '—')}\n\n"
        f"📝 {escape_html((app.description or '')[:450])}")
    rows=[[InlineKeyboardButton(text="🌐 تحميل من Waleed Zone",url=download_url)]]
    details=website_app_url(app.id)
    if details:
        rows.append([InlineKeyboardButton(text="🌐 تفاصيل التطبيق",url=details)])
    return text,InlineKeyboardMarkup(inline_keyboard=rows)


async def _publish_to_channel(call: CallbackQuery,session: AsyncSession,app) -> None:
    if not _only_admin(call):
        await call.answer("⛔",show_alert=True)
        return
    settings=get_settings()
    if not settings.CHANNEL_ID:
        await call.message.answer("⚠️ CHANNEL_ID غير مضبوط. بقي التطبيق مسودة.")
        return
    app=await session.scalar(select(Application).where(Application.id==app.id).with_for_update().execution_options(populate_existing=True))
    if not app or not app.active:
        await call.message.answer("⚠️ التطبيق معطل. أعد تفعيله قبل النشر.")
        return
    try:
        text,kb=channel_promo(app)
        photo=app.image_url or app.icon_file_id
        if photo:
            await call.bot.send_photo(settings.CHANNEL_ID,photo=photo,caption=text,reply_markup=kb)
        else:
            await call.bot.send_message(settings.CHANNEL_ID,text,reply_markup=kb)
    except Exception:
        logger.warning("Channel promo publish failed")
        await call.message.answer("❌ تعذر نشر الإعلان. تحقق من إعدادات القناة والصورة.")
        return
    app.published=True
    await session.flush()
    await call.message.answer("📢 تم النشر. زر التحميل يفتح Waleed Zone.")
