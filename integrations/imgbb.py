"""رفع صور التطبيقات إلى ImgBB من Telegram أو من رابط ويب خارجي."""

from __future__ import annotations

import io
import logging
import os
import re
from typing import Any
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
_IMGBB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
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


def _extract_imgbb_error(result: Any) -> tuple[int | None, str]:
    """استخرج code/message من صيغ أخطاء ImgBB المختلفة."""
    if not isinstance(result, dict):
        return None, str(result or "Unknown ImgBB error")

    error = result.get("error")
    if isinstance(error, dict):
        raw_code = error.get("code")
        message = str(error.get("message") or result.get("status_txt") or "ImgBB upload failed")
    else:
        raw_code = result.get("code")
        message = str(result.get("message") or result.get("status_txt") or error or "ImgBB upload failed")

    try:
        code = int(raw_code) if raw_code is not None else None
    except (TypeError, ValueError):
        code = None

    return code, message


def _configured_proxy() -> str | None:
    """Proxy اختياري إذا كانت شبكة الاستضافة محجوبة من ImgBB."""
    value = (os.getenv("IMGBB_PROXY_URL") or "").strip()
    return value or None


class ImgBBUploader:
    def __init__(self, api_key: str):
        self.api_key = (api_key or "").strip()
        self.last_error_code: int | None = None
        self.last_error_message: str = ""

    def _reset_error(self) -> None:
        self.last_error_code = None
        self.last_error_message = ""

    def _remember_error(self, code: int | None, message: str) -> None:
        self.last_error_code = code
        self.last_error_message = message

    async def _upload_form(
        self,
        *,
        image: bytes | str,
        name: str | None = None,
        content_type: str = "image/jpeg",
    ) -> str:
        """نفّذ طلب ImgBB بالطريقة الموثقة رسمياً.

        المفتاح يرسل في query string، بينما ``image`` و``name`` يرسلان كـ
        multipart/form-data. ImgBB يقبل image كبايتات أو URL مباشر.
        """
        if not self.api_key:
            self._remember_error(None, "IMGBB_API_KEY is not configured")
            logger.error(self.last_error_message)
            return ""

        safe_name = _safe_name(name)
        params = {"key": self.api_key}
        proxy = _configured_proxy()
        timeout = aiohttp.ClientTimeout(total=60)

        data = aiohttp.FormData()
        data.add_field("name", safe_name)

        if isinstance(image, bytes):
            lower_type = content_type.lower()
            if "png" in lower_type:
                extension = ".png"
            elif "webp" in lower_type:
                extension = ".webp"
            elif "gif" in lower_type:
                extension = ".gif"
            else:
                extension = ".jpg"

            data.add_field(
                "image",
                image,
                filename=f"{safe_name}{extension}",
                content_type=content_type,
            )
        else:
            data.add_field("image", image)

        try:
            async with aiohttp.ClientSession(
                timeout=timeout,
                headers=_IMGBB_HEADERS,
            ) as session:
                async with session.post(
                    _IMGBB_UPLOAD_URL,
                    params=params,
                    data=data,
                    proxy=proxy,
                    allow_redirects=True,
                ) as resp:
                    try:
                        result = await resp.json(content_type=None)
                    except Exception:
                        body = (await resp.text())[:500]
                        self._remember_error(resp.status, body or "Invalid ImgBB response")
                        logger.error(
                            "ImgBB returned non-JSON HTTP %s: %s",
                            resp.status,
                            body,
                        )
                        return ""

                    if resp.status != 200 or not result.get("success"):
                        code, message = _extract_imgbb_error(result)
                        self._remember_error(code, message)

                        if code == 103:
                            logger.error(
                                "ImgBB rejected this server/network (code 103): %s. "
                                "This is a provider-side forbidden response, not proof of an invalid API key. "
                                "If it persists on Railway, use an allowed egress/IP or set IMGBB_PROXY_URL.",
                                message,
                            )
                        else:
                            logger.error(
                                "ImgBB upload failed HTTP %s (code=%s): %s",
                                resp.status,
                                code,
                                message,
                            )
                        return ""

                    image_url = str(result.get("data", {}).get("url") or "").strip()
                    if not image_url:
                        self._remember_error(None, "ImgBB returned success without an image URL")
                        logger.error(self.last_error_message)
                        return ""

                    self._reset_error()
                    return image_url
        except Exception as exc:
            self._remember_error(None, str(exc))
            logger.exception("ImgBB upload request failed")
            return ""

    async def _upload_bytes(
        self,
        payload: bytes,
        *,
        name: str | None = None,
        content_type: str = "image/jpeg",
    ) -> str:
        if not payload:
            self._remember_error(None, "ImgBB image payload is empty")
            logger.error(self.last_error_message)
            return ""

        if len(payload) > _MAX_IMAGE_BYTES:
            self._remember_error(None, f"ImgBB image payload is too large: {len(payload)} bytes")
            logger.error(self.last_error_message)
            return ""

        return await self._upload_form(
            image=payload,
            name=name,
            content_type=content_type,
        )

    async def upload_telegram_photo(
        self,
        bot: Bot,
        file_id: str,
        *,
        name: str | None = None,
    ) -> str:
        """نزّل صورة Telegram ثم ارفعها إلى ImgBB."""
        self._reset_error()
        try:
            tg_file = await bot.get_file(file_id)
            buffer = io.BytesIO()
            await bot.download_file(tg_file.file_path, buffer)
            return await self._upload_bytes(buffer.getvalue(), name=name)
        except Exception as exc:
            self._remember_error(None, str(exc))
            logger.exception("Failed to download Telegram image for ImgBB")
            return ""

    async def upload_remote_image(
        self,
        image_url: str,
        *,
        name: str | None = None,
        referer: str | None = None,
    ) -> str:
        """ارفع صورة ويب إلى ImgBB مع fallback للتنزيل المحلي.

        ImgBB يدعم URL مباشر كقيمة ``image``. نجربه أولاً؛ إذا رفض جلب المصدر
        لسبب عادي ننزّل الصورة باستخدام Referer ثم نرفع البايتات. إذا أعاد ImgBB
        code 103 فلا نكرر نفس الطلب لأن المشكلة حظر من المزود/مخرج الشبكة.
        """
        self._reset_error()

        if not image_url.startswith(("http://", "https://")):
            self._remember_error(None, f"Invalid remote image URL: {image_url}")
            logger.warning(self.last_error_message)
            return ""

        # أسرع مسار: ImgBB نفسه يجلب رابط الصورة.
        hosted_url = await self._upload_form(image=image_url, name=name)
        if hosted_url:
            return hosted_url

        # code 103 يعني ImgBB رفض الاتصال نفسه؛ إعادة الرفع من نفس IP لن تفيد.
        if self.last_error_code == 103:
            return ""

        headers = dict(_REMOTE_HEADERS)
        if referer:
            headers["Referer"] = referer

        timeout = aiohttp.ClientTimeout(total=45)
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(image_url, allow_redirects=True) as resp:
                    if resp.status != 200:
                        self._remember_error(resp.status, f"Remote image returned HTTP {resp.status}")
                        logger.warning(
                            "Remote image returned HTTP %s for %s",
                            resp.status,
                            image_url,
                        )
                        return ""

                    content_type = (resp.headers.get("Content-Type") or "").split(";", 1)[0]
                    if not content_type.startswith("image/"):
                        self._remember_error(
                            None,
                            f"Remote URL did not return an image ({content_type or 'unknown'})",
                        )
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
                                self._remember_error(None, "Remote image is too large")
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
        except Exception as exc:
            self._remember_error(None, str(exc))
            logger.exception("Remote image fetch failed: %s", image_url)
            return ""
