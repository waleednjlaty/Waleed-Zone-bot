"""Telegram-side copy only. No APK download, temporary hosting or external uploader."""

from __future__ import annotations

import asyncio
import re
import unicodedata

from aiogram.enums import ChatType

from app.utils.helpers import is_admin
from config import get_settings


def channel_username(value: str | None) -> str:
    name = (value or "").removeprefix("@").lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]{4,31}", name):
        raise ValueError("INVALID_FILES_CHANNEL")
    return name


def files_channel(settings) -> tuple[int | None, str]:
    explicit = settings.FILES_CHANNEL_ID is not None or bool(settings.FILES_CHANNEL_USERNAME)
    if explicit:
        username = channel_username(settings.FILES_CHANNEL_USERNAME)
        chat_id = settings.FILES_CHANNEL_ID
        if chat_id is not None and (
            not isinstance(chat_id, int) or isinstance(chat_id, bool) or chat_id >= 0
        ):
            raise ValueError("FILES_CHANNEL_NOT_CONFIGURED")
        return chat_id, username
    chat_id = settings.CHANNEL_ID
    username = channel_username(settings.CHANNEL_USERNAME)
    if not isinstance(chat_id, int) or isinstance(chat_id, bool) or chat_id >= 0:
        raise ValueError("FILES_CHANNEL_NOT_CONFIGURED")
    return chat_id, username


def validate_source(source: dict) -> None:
    channel_username(source.get("telegram_channel_username"))
    mid = source.get("telegram_message_id")
    if not isinstance(mid, int) or isinstance(mid, bool) or not 0 < mid <= 2147483647:
        raise ValueError("INVALID_MESSAGE_ID")
    cid = source.get("telegram_chat_id")
    if not isinstance(cid, int) or isinstance(cid, bool) or cid >= 0:
        raise ValueError("INVALID_CHAT_ID")
    fid = source.get("telegram_file_id")
    if fid is not None and (
        not isinstance(fid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,512}", fid)
    ):
        raise ValueError("INVALID_FILE_ID")
    for field in ("filename", "mime_type"):
        value = source.get(field)
        if value is not None and (
            not isinstance(value, str)
            or len(value) > 255
            or any(unicodedata.category(c) in {"Cc", "Cf"} for c in value)
        ):
            raise ValueError("INVALID_FILE_METADATA")
    size = source.get("size_bytes")
    if size is not None and (not isinstance(size, int) or isinstance(size, bool) or size <= 0):
        raise ValueError("INVALID_FILE_SIZE")


class UploadService:
    async def copy(self, message) -> dict:
        if not message.from_user or not is_admin(message.from_user.id):
            raise PermissionError("ADMIN_REQUIRED")
        document = message.document
        if not document:
            raise ValueError("DOCUMENT_REQUIRED")
        settings = get_settings()
        configured_chat_id, username = files_channel(settings)
        if (
            not isinstance(document.file_size, int)
            or isinstance(document.file_size, bool)
            or not 0 < document.file_size <= settings.MAX_UPLOAD_BYTES
        ):
            raise ValueError("FILE_TOO_LARGE")
        if getattr(message, "has_protected_content", False):
            raise ValueError("PROTECTED_SOURCE")
        # Resolve by public username when no numeric ID is configured, then pin the
        # exact resolved ID into metadata. This keeps mobile setup simple while still
        # verifying that the public username maps to the actual destination channel.
        lookup = configured_chat_id if configured_chat_id is not None else f"@{username}"
        chat = await asyncio.wait_for(message.bot.get_chat(lookup), 15)
        if (
            chat.type != ChatType.CHANNEL
            or channel_username(chat.username) != username
            or chat.has_protected_content
        ):
            raise ValueError("FILES_CHANNEL_MISMATCH")
        chat_id = chat.id
        if not isinstance(chat_id, int) or isinstance(chat_id, bool) or chat_id >= 0:
            raise ValueError("FILES_CHANNEL_MISMATCH")
        if configured_chat_id is not None and chat_id != configured_chat_id:
            raise ValueError("FILES_CHANNEL_MISMATCH")
        bot_user = await asyncio.wait_for(message.bot.get_me(), 15)
        member = await asyncio.wait_for(message.bot.get_chat_member(chat_id, bot_user.id), 15)
        if member.status not in {"administrator", "creator"} or (
            member.status == "administrator" and not member.can_post_messages
        ):
            raise ValueError("FILES_CHANNEL_PERMISSION_DENIED")
        source = {
            "telegram_chat_id": chat_id,
            "telegram_message_id": 1,
            "telegram_channel_username": username,
            "telegram_file_id": document.file_id,
            "filename": document.file_name,
            "size_bytes": document.file_size,
            "mime_type": document.mime_type,
        }
        validate_source(source)
        from app.utils.text import append_app_footer, bounded_html

        caption = append_app_footer("📦 " + bounded_html(document.file_name or "ملف التطبيق", 150))
        copied = await asyncio.wait_for(
            message.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                caption=caption,
                parse_mode="HTML",
                disable_notification=True,
            ),
            30,
        )
        source["telegram_message_id"] = copied.message_id
        validate_source(source)
        return source


async def build_upload_service() -> UploadService:
    return UploadService()
