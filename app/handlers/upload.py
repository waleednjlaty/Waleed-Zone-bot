"""معالجات رفع التطبيقات (للمالك فقط) — DevUploads API ثم ShrinkMe API.

التدفق:
    1) استلام الملف من Telegram أو التحميل الريموتلي أو الاختصار المباشر.
    2) الرفع إلى DevUploads (أو تخطيه في وضع Shrink-Only).
    3) تقصير الرابط عبر ShrinkMe.
    4) جمع معلومات التطبيق (اسم/وصف/إصدار/نظام/تصنيف/أيقونة).
    5) معاينة ثم نشر التطبيق في قاعدة البيانات (والقناة إن رغبت).
"""

from __future__ import annotations

import logging
import re
import time
import urllib.parse
from pathlib import Path

import httpx
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    Document,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from integrations.imgbb import ImgBBUploader
from app.keyboards.user import cancel_keyboard
from app.services.upload_service import build_upload_service
from app.states import UploadStates
from app.utils.constants import (
    DEFAULT_CATEGORIES,
    REQUIRED_PLATFORMS,
    AdminCB,
    AppCB,
    MainMenuCB,
)
from app.utils.helpers import (
    build_search_text,
    format_size,
    is_admin,
    sanitize_filename,
)
from app.utils.text import append_app_footer, escape_html
from config import get_settings
from database import repositories as repo
from integrations import (
    DevUploadAuthError,
    DevUploadError,
    build_shrankme_client,
    download_telegram_file,
)

logger = logging.getLogger(__name__)

router = Router(name="upload")

imgbb_client = ImgBBUploader(api_key=get_settings().IMGBB_API_KEY or "")

DIRECT_EXTENSIONS = ('.apk', '.zip', '.rar', '.exe', '.bin', '.7z', '.tar', '.gz', '.ipa', '.pdf', '.iso')


def _only_admin(call: CallbackQuery) -> bool:
    if is_admin(call.from_user.id):
        return True
    return False


def _is_direct_link(url: str) -> bool:
    clean_url = url.split('?')[0].lower()
    return clean_url.endswith(DIRECT_EXTENSIONS)


async def _extract_direct_link_from_page(page_url: str) -> str | None:
    """محاولة استخراج رابط تحميل مباشر من صفحة الويب."""
    try:
        timeout = httpx.Timeout(20.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
            response = await client.get(page_url, headers=headers)
            html = response.text

            links = re.findall(r'href=["\'](https?://[^"\']+)["\']', html)
            for link in links:
                if _is_direct_link(link):
                    return link
            for link in links:
                if any(kw in link.lower() for kw in ["download", "dl", "get", "file", "app"]):
                    if not link.endswith(('.html', '.php', '.aspx')):
                        return link
    except Exception:
        pass
    return None


async def _choice_keyboard(
    choices: list[str], action: str, back_cb: str
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for choice in choices:
        row.append(
            InlineKeyboardButton(
                text=choice,
                callback_data=f"{action}:{choice}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [
            InlineKeyboardButton(
                text="✍️ كتابة خيار مخصص",
                callback_data=AppCB(action="custom", app_id=0).pack(),
            )
        ]
    )
    rows.append([InlineKeyboardButton(text="❌ إلغاء", callback_data=MainMenuCB(action="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(AppCB.filter(F.action == "upload"))
async def on_upload_start(call: CallbackQuery, state: FSMContext) -> None:
    if not _only_admin(call):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return
    await call.answer()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📁 رفع ملف من تيليجرام", callback_data="upl:method_file")],
            [InlineKeyboardButton(text="🌐 تحميل ريموتلي مباشر", callback_data="upl:method_remote")],
            [InlineKeyboardButton(text="🔗 تحميل لعبة وتوليد ريكوست ", callback_data="upl:method_Game")],
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=MainMenuCB(action="main").pack())]
        ]
    )
    await call.message.edit_text(
        "🚀 رفع تطبيق جديد\n\nاختر طريقة الإضافة المناسبة:",
        reply_markup=kb,
    )


@router.callback_query(F.data == "upl:method_file")
async def on_method_file(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(UploadStates.waiting_file)
    await state.update_data(manual=False)
    await call.message.edit_text("📤 أرسل ملف التطبيق الآن (APK / ZIP / EXE...).", reply_markup=cancel_keyboard())


@router.callback_query(F.data == "upl:method_remote")
async def on_method_remote(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(UploadStates.waiting_remote_url)
    await state.update_data(manual=False)
    await call.message.edit_text(
        "🌐 أرسل **الرابط المباشر للملف** (يجب أن ينتهي بامتداد مباشر مثل .apk أو .zip):",
        reply_markup=cancel_keyboard(),
    )


@router.callback_query(F.data == "upl:method_Game")
async def on_method_Game(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(UploadStates.waiting_shrink_only_url)
    await state.update_data(manual=True)
    await call.message.edit_text(
        "🔗 ارسل رابط اللعبة التي تريد رفعها \n\nبعد الاختصار، سيكمل البوت معك خطوات النشر كالعادة.",
        reply_markup=cancel_keyboard(),
    )


@router.callback_query(AdminCB.filter(F.action == "add_app"))
async def on_add_app(call: CallbackQuery, state: FSMContext) -> None:
    if not _only_admin(call):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return
    await call.answer()
    await state.set_state(UploadStates.waiting_name)
    await state.update_data(manual=True)
    await call.message.edit_text("➕ إضافة تطبيق يدويًا\n\n📱 أرسل اسم التطبيق:", reply_markup=cancel_keyboard())


@router.message(UploadStates.waiting_shrink_only_url)
async def on_shrink_only_url(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("⛔ صلاحية غير متاحة.")
        return

    url = message.text.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        await message.answer("❌ أرسل رابطًا صالحًا يبدأ بـ http:// أو https://")
        return

    status_msg = await message.answer("⏳ جاري اختصار الرابط عبر ShrinkMe...")
    try:
        shrankme_client = await build_shrankme_client()
        short_url = await shrankme_client.shorten_url(url)
    except Exception as exc:
        logger.error("ShrinkMe only failed: %s", exc)
        await status_msg.edit_text(f"❌ فشل اختصار الرابط:\n{escape_html(str(exc))}")
        return

    await state.update_data(
        manual=True,
        link=url,
        shrankme_url=short_url,
        devupload_url=None,
        size="—",
        size_bytes=0,
    )
    await status_msg.delete()
    await state.set_state(UploadStates.waiting_name)
    await message.answer("📱 أرسل اسم التطبيق:", reply_markup=cancel_keyboard())


@router.message(UploadStates.waiting_file)
async def on_upload_file(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("⛔ صلاحية غير متاحة.")
        return

    document: Document | None = message.document
    if document is None:
        await message.answer("📤 أرسل ملف التطبيق (وليس نصًا).")
        return

    settings = get_settings()
    if document.file_size and document.file_size > settings.MAX_UPLOAD_BYTES:
        size = format_size(document.file_size)
        await message.answer(
            f"❌ حجم الملف ({size}) أكبر من الحد المسموح ({format_size(settings.MAX_UPLOAD_BYTES)})."
        )
        return

    status_msg = await message.answer("⏳ جاري رفع التطبيق...")
    safe_name = sanitize_filename(document.file_name or "file")
    file_path = settings.DOWNLOAD_DIR / f"{message.from_user.id}_{int(time.time())}_{safe_name}"
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        await download_telegram_file(message.bot, document.file_id, file_path)
    except Exception as exc:
        logger.error("Download from Telegram failed: %s", exc, exc_info=True)
        await status_msg.edit_text("❌ تعذر تنزيل الملف من Telegram.")
        return

    async def progress(text: str) -> None:
        try:
            await status_msg.edit_text(text)
        except Exception:
            pass

    service = await build_upload_service()
    try:
        result = await service.run(file_path, filename=document.file_name, progress_callback=progress)
    except DevUploadAuthError as exc:
        logger.error("Upload failed due to DevUpload auth error: %s", exc)
        await status_msg.edit_text(
            "❌ **فشل المصادقة مع DevUpload**\n\n"
            "يبدو أن مفتاح `DEVUPLOAD_API_KEY` غير صالح أو منتهي الصلاحية. يرجى مراجعة الإعدادات والمحاولة مرة أخرى."
        )
        return
    except DevUploadError as exc:
        logger.error("Upload pipeline failed with DevUploadError: %s", exc)
        await status_msg.edit_text(f"❌ فشل الرفع إلى DevUpload.\n\nخطأ: {escape_html(str(exc))}")
        return
    except Exception as exc:
        logger.error("Upload pipeline failed with an unexpected error: %s", exc, exc_info=True)
        await status_msg.edit_text(f"❌ حدث خطأ غير متوقع أثناء الرفع.\n\nخطأ: {escape_html(str(exc))}")
        return

    await state.update_data(
        manual=False,
        file_path=str(file_path),
        size_bytes=result.size_bytes,
        size=format_size(result.size_bytes),
        devupload_url=result.devupload_url,
        shrankme_url=result.shrankme_url,
        partially=result.partially_successful,
    )

    if result.partially_successful:
        await status_msg.edit_text(
            "⚠️ تم رفع التطبيق إلى Dev Upload لكن فشل إنشاء رابط ShrinkMe.\nسيتم حفظ رابط Dev Upload مؤقتًا."
        )

    await state.set_state(UploadStates.waiting_name)
    await message.answer("📱 أرسل اسم التطبيق:", reply_markup=cancel_keyboard())


@router.message(UploadStates.waiting_remote_url)
async def on_remote_url_received(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("⛔ صلاحية غير متاحة.")
        return

    url = message.text.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        await message.answer("❌ أرسل رابطًا صالحًا يبدأ بـ http:// أو https://")
        return

    if not _is_direct_link(url):
        encoded_url = urllib.parse.quote(url)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 محاولة العثور على رابط التحميل", callback_data=f"upl:find_dl:{encoded_url}")],
                [InlineKeyboardButton(text="❌ إلغاء", callback_data=MainMenuCB(action="main").pack())]
            ]
        )
        await message.answer(
            "⚠️ **هذا الرابط مش ريموتلي!**\nيبدو أن الرابط المرسل يعود لصفحة ويب وليس لرابط تحميل مباشر للملف.",
            reply_markup=kb,
        )
        return

    await _process_remote_download(message, state, url)


@router.callback_query(F.data.startswith("upl:find_dl:"))
async def on_find_download_link(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    encoded_url = call.data.split(":", 2)[2]
    page_url = urllib.parse.unquote(encoded_url)
    status_msg = await call.message.edit_text("🔍 جاري فحص الصفحة ومحاولة العثور على رابط التحميل المباشر...")

    direct_link = await _extract_direct_link_from_page(page_url)
    if not direct_link:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ إلغاء", callback_data=MainMenuCB(action="main").pack())]]
        )
        await status_msg.edit_text(
            "❌ **لم يتم العثور على رابط تحميل مباشر تلقائياً في هذه الصفحة.**\n\n"
            "الرجاء إرسال رابط مباشر صحيح ينتهي بامتداد الملف (مثل .apk أو .zip).",
            reply_markup=kb,
        )
        return

    await status_msg.edit_text(f"✅ تم العثور على رابط مباشر:\n`{direct_link}`\n\n⏳ جاري بدء التحميل والرفع...")
    call.message.text = direct_link
    await _process_remote_download(call.message, state, direct_link)


async def _process_remote_download(message: Message, state: FSMContext, url: str) -> None:
    status_msg = await message.answer("⏳ جاري تحميل الملف من الرابط المباشر...")
    settings = get_settings()
    file_name = url.split("/")[-1].split("?")[0] or "remote_file.apk"
    safe_name = sanitize_filename(file_name)
    file_path = settings.DOWNLOAD_DIR / f"{message.from_user.id}_{int(time.time())}_{safe_name}"

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        timeout = httpx.Timeout(600.0, connect=60.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(file_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
    except Exception as exc:
        logger.error("Remote download failed: %s", exc, exc_info=True)
        await status_msg.edit_text("❌ تعذر تحميل الملف من الرابط المباشر. تأكد أن الرابط يدعم التحميل السريع.")
        return

    async def progress(text: str) -> None:
        try:
            await status_msg.edit_text(text)
        except Exception:
            pass

    service = await build_upload_service()
    try:
        result = await service.run(file_path, filename=file_name, progress_callback=progress)
    except Exception as exc:
        logger.error("Upload pipeline failed for remote file: %s", exc)
        await status_msg.edit_text(f"❌ فشل رفع الملف المرفوع إلى المنصات.\n\nخطأ: {escape_html(str(exc))}")
        return

    await state.update_data(
        manual=False,
        file_path=str(file_path),
        size_bytes=result.size_bytes,
        size=format_size(result.size_bytes),
        devupload_url=result.devupload_url,
        shrankme_url=result.shrankme_url,
        partially=result.partially_successful,
    )

    if result.partially_successful:
        await status_msg.edit_text("⚠️ تم رفع الملف لكن فشل إنشاء رابط الاختصار.\nسيتم حفظ رابط Dev Upload مؤقتًا.")

    await state.set_state(UploadStates.waiting_name)
    await message.answer("📱 أرسل اسم التطبيق:", reply_markup=cancel_keyboard())


async def _ask_icon(message: Message, state: FSMContext) -> None:
    await state.set_state(UploadStates.waiting_icon)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ تخطي (بدون صورة)", callback_data="upl:skipicon")],
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=MainMenuCB(action="main").pack())],
        ]
    )
    await message.answer("🖼 أرسل صورة التطبيق (اختياري)\nأو اضغط «تخطي»:", reply_markup=kb)


async def _ask_publish(message: Message, state: FSMContext) -> None:
    await state.set_state(UploadStates.waiting_publish_choice)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ نعم", callback_data="upl:pub_yes"),
                InlineKeyboardButton(text="❌ لا", callback_data="upl:pub_no"),
            ],
            [InlineKeyboardButton(text="❌ إلغاء", callback_data=MainMenuCB(action="main").pack())],
        ]
    )
    await message.answer("هل تريد نشر التطبيق في القناة؟", reply_markup=kb)


@router.message(UploadStates.waiting_name)
async def on_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await message.answer("📝 أرسل وصف التطبيق:", reply_markup=cancel_keyboard())
    await state.set_state(UploadStates.waiting_description)


@router.message(UploadStates.waiting_description)
async def on_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await message.answer("📦 أرسل الإصدار (مثال: 1.2.0):", reply_markup=cancel_keyboard())
    await state.set_state(UploadStates.waiting_version)


@router.message(UploadStates.waiting_version)
async def on_version(message: Message, state: FSMContext) -> None:
    await state.update_data(version=message.text.strip())
    kb = await _choice_keyboard(REQUIRED_PLATFORMS, "upl:pf", "x")
    await message.answer("📱 اختر النظام أو اكتبه:", reply_markup=kb)
    await state.set_state(UploadStates.waiting_platform)


@router.message(UploadStates.waiting_platform)
async def on_platform(message: Message, state: FSMContext) -> None:
    await state.update_data(platform=message.text.strip())
    kb = await _choice_keyboard(DEFAULT_CATEGORIES, "upl:cat", "x")
    await message.answer("🗂 اختر التصنيف أو اكتبه:", reply_markup=kb)
    await state.set_state(UploadStates.waiting_category)


@router.message(UploadStates.waiting_category)
async def on_category(message: Message, state: FSMContext) -> None:
    await state.update_data(category=message.text.strip())
    data = await state.get_data()
    if data.get("manual") and not data.get("link"):
        await message.answer("🔗 أرسل رابط التحميل النهائي للتطبيق:", reply_markup=cancel_keyboard())
        await state.set_state(UploadStates.waiting_link)
    else:
        await _ask_icon(message, state)


@router.message(UploadStates.waiting_link)
async def on_link(message: Message, state: FSMContext) -> None:
    link = message.text.strip()
    if not link.startswith("http://") and not link.startswith("https://"):
        await message.answer("❌ أرسل رابطًا صالحًا يبدأ بـ http:// أو https://")
        return
    await state.update_data(link=link)
    await _ask_icon(message, state)


@router.message(UploadStates.waiting_icon)
async def on_icon(message: Message, state: FSMContext) -> None:
    if message.photo:
        photo_file_id = message.photo[-1].file_id
        web_image_url = await imgbb_client.upload_telegram_photo(message.bot, photo_file_id)
        await state.update_data(icon_file_id=photo_file_id, image_url=web_image_url)
    else:
        await state.update_data(icon_file_id=None, image_url=None)
    await _ask_publish(message, state)


@router.message(UploadStates.waiting_publish_choice)
async def on_publish_text(message: Message, state: FSMContext) -> None:
    await message.answer("استخدم الأزرار للاختيار.")


async def _choice_value(call: CallbackQuery, state: FSMContext, field: str, value: str) -> None:
    await state.update_data(**{field: value})
    data = await state.get_data()
    if field == "platform":
        kb = await _choice_keyboard(DEFAULT_CATEGORIES, "upl:cat", "x")
        await state.set_state(UploadStates.waiting_category)
        await call.message.edit_text("🗂 اختر التصنيف أو اكتبه:", reply_markup=kb)
    elif field == "category":
        if data.get("manual") and not data.get("link"):
            await state.set_state(UploadStates.waiting_link)
            await call.message.edit_text("🔗 أرسل رابط التحميل النهائي للتطبيق:", reply_markup=cancel_keyboard())
        else:
            await _ask_icon(call.message, state)


@router.callback_query(F.data.startswith("upl:pf:"))
async def on_platform_choice(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 2)[2]
    await call.answer()
    await _choice_value(call, state, "platform", value)


@router.callback_query(F.data.startswith("upl:cat:"))
async def on_category_choice(call: CallbackQuery, state: FSMContext) -> None:
    value = call.data.split(":", 2)[2]
    await call.answer()
    await _choice_value(call, state, "category", value)


@router.callback_query(AppCB.filter(F.action == "custom"))
async def on_custom_choice(call: CallbackQuery, state: FSMContext) -> None:
    current = await state.get_state()
    await call.answer()
    if current == UploadStates.waiting_platform.state:
        await call.message.edit_text("✍️ اكتب اسم النظام (مثال: Android):", reply_markup=cancel_keyboard())
    elif current == UploadStates.waiting_category.state:
        await call.message.edit_text("✍️ اكتب اسم التصنيف:", reply_markup=cancel_keyboard())
    else:
        await call.message.edit_text("✍️ اكتب القيمة:", reply_markup=cancel_keyboard())


@router.callback_query(F.data == "upl:skipicon")
async def on_skip_icon(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.update_data(icon_file_id=None, image_url=None)
    await _ask_publish(call.message, state)


@router.callback_query(F.data.startswith("upl:pub_"))
async def on_publish_choice(call: CallbackQuery, state: FSMContext) -> None:
    choice = "yes" if call.data.endswith("_yes") else "no"
    await call.answer()
    await state.update_data(publish_choice=choice)
    await _show_preview(call.message, state)


async def _show_preview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    link = data.get("shrankme_url") or data.get("link") or data.get("devupload_url") or "—"

    lines = [
        "📋 معاينة التطبيق:",
        "────────────",
        f"📱 الاسم: {escape_html(data.get('name') or '')}",
        f"📦 الإصدار: {escape_html(data.get('version') or '—')}",
        f"💾 الحجم: {escape_html(data.get('size') or '—')}",
        f"📱 النظام: {escape_html(data.get('platform') or '—')}",
        f"🗂 التصنيف: {escape_html(data.get('category') or '—')}",
        f"📝 الوصف: {escape_html(data.get('description') or '—')}",
        f"⬇️ رابط التحميل:\n{escape_html(link)}",
    ]
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 نشر", callback_data=AppCB(action="confirm", app_id=0).pack()),
                InlineKeyboardButton(text="❌ إلغاء", callback_data=MainMenuCB(action="main").pack()),
            ]
        ]
    )
    await state.set_state(UploadStates.waiting_publish_choice)
    try:
        if message.photo:
            await message.edit_caption(caption="\n".join(lines), reply_markup=kb)
            return
    except Exception:
        pass

    try:
        await message.edit_text("\n".join(lines), reply_markup=kb)
    except Exception:
        if data.get("icon_file_id"):
            await message.answer_photo(data["icon_file_id"], caption="\n".join(lines), reply_markup=kb)
        else:
            await message.answer("\n".join(lines), reply_markup=kb)


@router.callback_query(AppCB.filter(F.action == "confirm"))
async def on_confirm_app(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _only_admin(call):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return
    data = await state.get_data()

    name = (data.get("name") or "").strip()
    if not name:
        await call.answer("⚠️ التطبيق بدون اسم.", show_alert=True)
        return

    link = data.get("shrankme_url") or data.get("link") or data.get("devupload_url")
    devupload_url = data.get("devupload_url")
    shrankme_url = data.get("shrankme_url") or (link if data.get("manual") else None)

    app = await repo.create_application(
        session,
        name=name,
        description=data.get("description"),
        version=data.get("version"),
        size=data.get("size"),
        category=data.get("category"),
        platform=data.get("platform"),
        icon_file_id=data.get("icon_file_id"),
        image_url=data.get("image_url"),
        devupload_url=devupload_url,
        shrankme_url=shrankme_url,
        search_text=build_search_text(name, data.get("category"), data.get("platform"), data.get("description")),
    )

    await session.commit()
    await call.answer("✅ تم الحفظ والنشر")
    final_url = app.shrankme_url or app.devupload_url or ""

    success_text = (
        "✅ تم رفع التطبيق بنجاح!\n\n"
        f"📱 اسم التطبيق: {escape_html(app.name)}\n"
        f"📦 الإصدار: {escape_html(app.version or '—')}\n"
        f"💾 الحجم: {escape_html(app.size or '—')}\n"
    )
    if app.devupload_url:
        success_text += f"🔗 رابط Dev Upload:\n{escape_html(app.devupload_url)}\n"
    if final_url:
        success_text += f"\n🔗 رابط التحميل الجاهز:\n{escape_html(final_url)}"
    else:
        success_text += "\n⚠️ لا يوجد رابط تحميل متاح."

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 نسخ الرابط", url=final_url)] if final_url else [],
            [InlineKeyboardButton(text="📥 تحميل تطبيق اخر", callback_data=AppCB(action="upload", app_id=0).pack())],
            [InlineKeyboardButton(text="📱 إدارة التطبيقات", callback_data=AdminCB(action="apps", page=0).pack())],
        ]
    )

    await call.message.answer(success_text, reply_markup=kb)

    if data.get("publish_choice") == "yes":
        await _publish_to_channel(call, session, app)

    await _notify_new_app(call, app, session)
    await state.clear()

    file_path = data.get("file_path")
    if file_path:
        try:
            Path(file_path).unlink(missing_ok=True)
        except Exception as exc:
            logger.debug("Cannot remove tmp file %s: %s", file_path, exc)


async def _publish_to_channel(call: CallbackQuery, session: AsyncSession, app) -> None:
    settings = get_settings()
    if not settings.CHANNEL_ID:
        await call.message.answer("⚠️ لم يتم إعداد القناة (CHANNEL_ID) في .env — تم الحفظ دون نشر.")
        return
    try:
        me = await call.bot.me()
        bot_username = me.username or ""
    except Exception:
        bot_username = ""

    deep_link = f"https://t.me/{bot_username}?start=app_{app.id}" if bot_username else ""

    text = (
        "━━━━━━━━━━━━━━\n"
        f"📱 {escape_html(app.name)}\n"
        f"📦 الإصدار: {escape_html(app.version or '—')}\n"
        f"💾 الحجم: {escape_html(app.size or '—')}\n"
        f"📱 النظام: {escape_html(app.platform or '—')}\n"
        "━━━━━━━━━━━━━━\n\n"
        f"📝 {escape_html(app.description or '')}\n\n"
        "⬇️ اضغط الزر لتحميل التطبيق"
    )
    text = append_app_footer(text)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 تحميل الآن", url=deep_link or (app.shrankme_url or ""))]
        ]
    )
    try:
        if app.icon_file_id:
            await call.bot.send_photo(settings.CHANNEL_ID, app.icon_file_id, caption=text, reply_markup=kb)
        else:
            await call.bot.send_message(settings.CHANNEL_ID, text, reply_markup=kb)
        app.published = True
        await session.flush()
        await call.message.answer("📢 تم نشر التطبيق في القناة بنجاح.")
    except Exception as exc:
        logger.warning("Channel publish failed: %s", exc)
        await call.message.answer("❌ فشل النشر في القناة. تأكد أن البوت أدمن في القناة.")


async def _notify_new_app(call: CallbackQuery, app, session: AsyncSession) -> None:
    try:
        global_enabled = await repo.get_setting_bool(session, "notifications_enabled", True)
        if not global_enabled:
            return
        users = await repo.list_notification_users(session)
    except Exception as exc:
        logger.warning("Cannot load notification users: %s", exc)
        return

    text = (
        f"🆕 تطبيق جديد!\n\n"
        f"📱 {escape_html(app.name)}\n"
        f"📦 {escape_html(app.version or '')}\n"
        f"{escape_html(app.category or '')}"
    )
    text = append_app_footer(text)

    bot_username = await _bot_username(call)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📥 فتح التطبيق",
                    url=f"https://t.me/{bot_username}?start=app_{app.id}",
                )
            ]
        ]
    )
    sent = 0
    for user in users[:200]:
        try:
            await call.bot.send_message(user.telegram_id, text, reply_markup=kb)
            sent += 1
        except Exception:
            pass
    if sent:
        await call.message.answer(f"🔔 تم إرسال إشعار لـ {sent} مستخدم.")


async def _bot_username(call: CallbackQuery) -> str:
    try:
        me = await call.bot.me()
        return me.username or ""
    except Exception:
        return ""
