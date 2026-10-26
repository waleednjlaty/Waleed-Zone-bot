"""Secure owner-only direct-URL import into the Telegram files channel.

This intentionally refuses redirects, non-HTTPS URLs, unapproved hosts, private
network destinations, HTML/challenge pages, and files larger than Telegram's
hosted Bot API upload limit. It does not bypass provider authentication or anti-bot
challenges.
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
import re
import socket
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

import aiofiles
import httpx
from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.upload_service import files_channel
from app.states import RemoteImportStates
from app.utils.constants import AdminCB
from app.utils.helpers import is_admin
from app.utils.owner_guard import owner_gate
from app.utils.text import append_app_footer, bounded_html, escape_html
from config import get_settings

logger = logging.getLogger(__name__)
router = Router(name="remote_import")
MAX_REMOTE_BYTES = 45 * 1024 * 1024
CHUNK_SIZE = 64 * 1024
ALLOWED_EXTENSIONS = {".apk", ".xapk", ".apks", ".aab", ".zip", ".exe", ".msi", ".dmg", ".ipa", ".7z", ".rar", ".tar", ".gz"}


def _allowed_hosts() -> set[str]:
    settings = get_settings()
    configured = getattr(settings, "REMOTE_UPLOAD_ALLOWED_HOSTS", "") or settings.LEGACY_DOWNLOAD_ALLOWED_HOSTS
    return {item.strip().lower().rstrip(".") for item in configured.split(",") if item.strip()}


def _parse_url(raw: str) -> tuple[str, str]:
    parsed = urlsplit(raw.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "https" or not host or parsed.username or parsed.password
        or parsed.port not in (None, 443) or parsed.fragment or parsed.query
    ):
        raise ValueError("INVALID_URL")
    if host not in _allowed_hosts():
        raise ValueError("HOST_NOT_ALLOWED")
    filename = unquote(PurePosixPath(parsed.path).name or "")
    filename = re.sub(r"[^\w.() -]", "_", filename, flags=re.UNICODE).strip(" .")[:180]
    if not filename or Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("UNSUPPORTED_FILE_TYPE")
    return raw.strip(), filename


async def _assert_public_host(host: str) -> None:
    try:
        results = await asyncio.wait_for(
            asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM),
            timeout=8,
        )
    except Exception as exc:
        raise ValueError("DNS_LOOKUP_FAILED") from exc
    addresses = {item[4][0] for item in results}
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("NON_PUBLIC_DESTINATION")


async def _download(url: str, path: Path) -> tuple[int, str]:
    parsed = urlsplit(url)
    await _assert_public_host(parsed.hostname or "")
    timeout = httpx.Timeout(connect=12.0, read=60.0, write=30.0, pool=12.0)
    written = 0
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        async with client.stream("GET", url, headers={"User-Agent": "WaleedZone-RemoteImport/1.0"}) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                raise ValueError("REDIRECT_NOT_ALLOWED")
            if response.status_code != 200:
                raise ValueError("UPSTREAM_NOT_READY")
            length = response.headers.get("content-length")
            if length and (not length.isdigit() or int(length) > MAX_REMOTE_BYTES):
                raise ValueError("FILE_TOO_LARGE")
            content_type = response.headers.get("content-type", "").lower()
            if any(marker in content_type for marker in ("text/html", "application/json", "text/plain")):
                raise ValueError("NOT_A_DIRECT_FILE")
            async with aiofiles.open(path, "wb") as output:
                async for chunk in response.aiter_bytes(CHUNK_SIZE):
                    written += len(chunk)
                    if written > MAX_REMOTE_BYTES:
                        raise ValueError("FILE_TOO_LARGE")
                    await output.write(chunk)
    if written <= 0:
        raise ValueError("EMPTY_FILE")
    async with aiofiles.open(path, "rb") as source:
        prefix = (await source.read(512)).lstrip().lower()
    if prefix.startswith((b"<!doctype html", b"<html", b"<head", b"<body")):
        raise ValueError("HTML_CHALLENGE_PAGE")
    return written, content_type


@router.callback_query(AdminCB.filter(F.action == "remote_import"))
async def on_remote_import_start(call: CallbackQuery, state) -> None:
    if not await owner_gate(call):
        return
    if not call.from_user or not is_admin(call.from_user.id):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return
    hosts = "، ".join(sorted(_allowed_hosts()))
    await state.clear()
    await state.set_state(RemoteImportStates.waiting_url)
    await call.answer()
    await call.message.answer(
        "⬇️ أرسل رابط HTTPS مباشرًا لملف تطبيق أو لعبة.\n"
        f"المضيفون المسموحون: {escape_html(hosts or 'لم يتم ضبطهم')}\n"
        "الحد الأقصى 45 MB. لا تُقبل التحويلات أو صفحات تسجيل الدخول/التحدي. "
        "لن يُحفظ الملف على استضافة دائمة؛ سيُرفع إلى قناة ملفات Telegram.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ إلغاء", callback_data=AdminCB(action="panel", page=0).pack())
        ]]),
    )


@router.message(RemoteImportStates.waiting_url)
async def on_remote_import_url(message: Message, state, session: AsyncSession) -> None:
    if not await owner_gate(message):
        return
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer("⛔ صلاحية غير متاحة.")
        return
    raw = (message.text or "").strip()
    try:
        url, filename = _parse_url(raw)
    except ValueError as exc:
        reason = str(exc)
        messages = {
            "INVALID_URL": "الرابط غير صالح. استخدم HTTPS على المنفذ 443 دون query أو بيانات دخول.",
            "HOST_NOT_ALLOWED": "المضيف غير موجود في قائمة السماح. أضفه إلى REMOTE_UPLOAD_ALLOWED_HOSTS في إعدادات Railway بعد التأكد من موثوقيته.",
            "UNSUPPORTED_FILE_TYPE": "امتداد الملف غير مدعوم. استخدم APK / XAPK / APKS / ZIP / EXE / MSI / DMG / IPA / 7Z / RAR / TAR / GZ.",
        }
        await message.answer("❌ " + messages.get(reason, "الرابط غير صالح."))
        return

    settings = get_settings()
    try:
        chat_id, username = files_channel(settings)
    except ValueError:
        await message.answer("❌ إعداد قناة الملفات غير مكتمل. تحقق من FILES_CHANNEL_ID وFILES_CHANNEL_USERNAME.")
        return

    status = await message.answer("⏳ جاري التحقق من الرابط وتنزيل الملف مؤقتًا...")
    temp_path: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="wz-remote-") as directory:
            temp_path = Path(directory) / filename
            size, _ = await asyncio.wait_for(_download(url, temp_path), timeout=180)
            lookup = chat_id if chat_id is not None else f"@{username}"
            chat = await asyncio.wait_for(message.bot.get_chat(lookup), 15)
            if getattr(chat, "type", None) != "channel" or (chat.username or "").lower() != username.lower() or getattr(chat, "has_protected_content", False):
                raise ValueError("FILES_CHANNEL_MISMATCH")
            bot_user = await asyncio.wait_for(message.bot.get_me(), 15)
            member = await asyncio.wait_for(message.bot.get_chat_member(chat.id, bot_user.id), 15)
            if member.status not in {"administrator", "creator"} or (member.status == "administrator" and not member.can_post_messages):
                raise ValueError("FILES_CHANNEL_PERMISSION_DENIED")
            caption = append_app_footer("📦 " + bounded_html(filename, 150))
            sent = await asyncio.wait_for(message.bot.send_document(
                chat_id=chat.id,
                document=FSInputFile(temp_path, filename=filename),
                caption=caption,
                parse_mode="HTML",
                disable_notification=True,
            ), timeout=90)
            link = f"https://t.me/{username}/{sent.message_id}"
            await state.clear()
            await status.edit_text(
                "✅ تم تنزيل الملف ورفعه إلى قناة الملفات في Telegram.\n"
                f"📄 {escape_html(filename)}\n"
                f"💾 {size / (1024 * 1024):.2f} MB\n"
                f"🔗 {escape_html(link)}\n\n"
                "لم يُحفظ الملف على قرص دائم في Railway."
            )
    except asyncio.TimeoutError:
        await status.edit_text("❌ انتهت مهلة التنزيل أو الرفع. جرّب رابطًا مباشرًا أصغر.")
    except ValueError as exc:
        reasons = {
            "DNS_LOOKUP_FAILED": "تعذر التحقق من عنوان المصدر.",
            "NON_PUBLIC_DESTINATION": "رُفض المصدر لأنه لا يحل إلى عنوان عام.",
            "REDIRECT_NOT_ALLOWED": "المصدر يحوّل إلى رابط آخر؛ التحويلات غير مسموحة لحماية الاستضافة.",
            "UPSTREAM_NOT_READY": "المصدر لم يعطِ ملفًا مباشرًا بنجاح. قد يتطلب تسجيل دخول أو يعرض تحدي حماية.",
            "FILE_TOO_LARGE": "حجم الملف يتجاوز الحد المسموح وهو 45 MB.",
            "NOT_A_DIRECT_FILE": "المصدر أعاد صفحة أو نصًا بدل ملف مباشر.",
            "EMPTY_FILE": "الملف فارغ.",
            "HTML_CHALLENGE_PAGE": "المصدر أعاد صفحة HTML أو تحدي حماية بدل الملف.",
            "FILES_CHANNEL_MISMATCH": "قناة الملفات لا تطابق إعدادات البوت.",
            "FILES_CHANNEL_PERMISSION_DENIED": "البوت يحتاج صلاحية نشر في قناة الملفات.",
        }
        await status.edit_text("❌ " + reasons.get(str(exc), "تعذر استيراد الملف."))
    except Exception:
        logger.warning("Remote import failed; URL and response body intentionally omitted")
        await status.edit_text("❌ فشل استيراد الملف. تحقق من الرابط وقناة الملفات ثم حاول مجددًا.")
