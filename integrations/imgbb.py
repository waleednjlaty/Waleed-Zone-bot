"""رفع صور التطبيقات إلى ImgBB من Telegram أو من رابط ويب خارجي."""

from __future__ import annotations

import io
import logging
import re
from urllib.parse import urlsplit

import aiohttp
from aiogram import Bot

logger = logging.getLogger(__name__)

_IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"
_MAX_IMAGE_BYTES = 32 * 1024 * 1024
_REMOTE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}


def _safe_name(value: str | None) -> str:
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", (value or "cover").strip()).strip("_")
    return name[:80] or "cover"


def is_imgbb_url(url: str | None) -> bool:
    """هل الرابط محفوظ فعلاً على ImgBB وليس رابط المصدر الخارجي؟"""
    if not url:
        return False
    try:
        host = (urlsplit(url).hostname or "").lower()
    except Exception:
        return False
    return host in {"i.ibb.co", "ibb.co"} or host.endswith(".ibb.co")


class ImgBBUploader:
    def __init__(self, api_key: str):
        self.api_key = (api_key or "").strip()

    async def _upload_bytes(
        self,
        payload: bytes,
        *,
        name: str | None = None,
        content_type: str = "image/jpeg",
    ) -> str:
        if not self.api_key:
            logger.error("IMGBB_API_KEY is not configured")
            return ""

        if not payload:
            logger.error("ImgBB image payload is empty")
            return ""

        if len(payload) > _MAX_IMAGE_BYTES:
            logger.error("ImgBB image payload is too large: %d bytes", len(payload))
            return ""

        safe_name = _safe_name(name)
        lower_type = content_type.lower()
        if "png" in lower_type:
            extension = ".png"
        elif "webp" in lower_type:
            extension = ".webp"
        else:
            extension = ".jpg"

        timeout = aiohttp.ClientTimeout(total=45)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                data = aiohttp.FormData()
                data.add_field("key", self.api_key)
                data.add_field("name", safe_name)
                data.add_field(
                    "image",
                    payload,
                    filename=f"{safe_name}{extension}",
                    content_type=content_type,
                )

                async with session.post(_IMGBB_UPLOAD_URL, data=data) as resp:
                    result = await resp.json(content_type=None)
                    if resp.status != 200 or not result.get("success"):
                        logger.error(
                            "ImgBB upload failed HTTP %s: %s",
                            resp.status,
                            result.get("error") or result,
                        )
                        return ""

                    image_url = str(result.get("data", {}).get("url") or "").strip()
                    if not image_url:
                        logger.error("ImgBB returned success without an image URL")
                    return image_url
        except Exception:
            logger.exception("ImgBB upload failed")
            return ""

    async def upload_telegram_photo(
        self,
        bot: Bot,
        file_id: str,
        *,
        name: str | None = None,
    ) -> str:
        """نزّل صورة Telegram ثم ارفعها إلى ImgBB."""
        try:
            tg_file = await bot.get_file(file_id)
            buffer = io.BytesIO()
            await bot.download_file(tg_file.file_path, buffer)
            return await self._upload_bytes(buffer.getvalue(), name=name)
        except Exception:
            logger.exception("Failed to download Telegram image for ImgBB")
            return ""

    async def upload_remote_image(
        self,
        image_url: str,
        *,
        name: str | None = None,
        referer: str | None = None,
    ) -> str:
        """نزّل صورة المصدر بنفس البوت ثم أعد استضافتها على ImgBB.

        هذا يمنع الاعتماد على hotlink من SteamRIP أو أي موقع قد يمنع Telegram
        من جلب الصورة مباشرة لاحقاً.
        """
        if not image_url.startswith(("http://", "https://")):
            logger.warning("Invalid remote image URL: %s", image_url)
            return ""

        headers = dict(_REMOTE_HEADERS)
        if referer:
            headers["Referer"] = referer

        timeout = aiohttp.ClientTimeout(total=45)
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(image_url, allow_redirects=True) as resp:
                    if resp.status != 200:
                        logger.warning(
                            "Remote image returned HTTP %s for %s",
                            resp.status,
                            image_url,
                        )
                        return ""

                    content_type = (resp.headers.get("Content-Type") or "").split(";", 1)[0]
                    if not content_type.startswith("image/"):
                        logger.warning(
                            "Remote URL did not return an image (%s): %s",
                            content_type or "unknown",
                            image_url,
                        )
                        return ""

                    content_length = resp.headers.get("Content-Length")
                    if content_length:
                        try:
                            if int(content_length) > _MAX_IMAGE_BYTES:
                                logger.warning("Remote image is too large: %s", image_url)
                                return ""
                        except ValueError:
                            pass

                    payload = await resp.read()
                    return await self._upload_bytes(
                        payload,
                        name=name,
                        content_type=content_type,
                    )
        except Exception:
            logger.exception("Remote image fetch failed: %s", image_url)
            return ""
