# DEPRECATED: offline legacy reference only; never imported by runtime upload flow.
"""تكامل رسمي مع ShrinkMe.io باستخدام نمط الـ API الموثق.

النمط الموثق والمستخدم حاليًا:
    GET https://shrinkme.io/st?api=API_KEY&url=<URL>
    GET https://shrinkme.io/api?api=API_KEY&url=<URL>   (نقطة قديمة)

الاستجابة JSON وتحتوي الحقل: "shortenedUrl"
رابط المختصر الناتج يكون بصيغة: https://shrinkme.io/xxxxx

ملاحظة حول التحقق:
    الموقع كان في وضع صيانة وقت كتابة الكود، لذا لا يمكن ضمان تنسيق
    الاستجابة المباشر بنسبة 100% الآن. العميل أدناه:
      - يجرّب نقطة /st المفعّلة ثم /api القديمة كاحتياط.
      - يقبل JSON يحوي "shortenedUrl" أو نص رابط مباشر.
      - لا يعتبر العملية ناجحة إلا إذا حصل على رابط shrinkme.io صالح.

انظر README.md لمزيد من التفاصيل.
"""

from __future__ import annotations

import asyncio
import logging
import re
import urllib.parse

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

# قبول أي نطاق يبدأ بـ shrinkme بغض النظر عن الامتداد (io, click, site, etc.)
_SHRANKME_RE = re.compile(r"^https?://(?:www\.)?shrinkme\.(?:io|click|net|org)/\S+", re.IGNORECASE)

class ShrankMeError(Exception):
    """خطأ عام في تكامل ShrinkMe."""


class ShrankMeAuthError(ShrankMeError):
    """مفتاح API غير صالح."""


class ShrankMeClient:
    """عميل غير متزامن لتقصير الروابط عبر ShrinkMe.io API."""

    def __init__(
        self,
        api_key: str,
        api_url: str = "https://shrinkme.io/st",
        legacy_api_url: str = "https://shrinkme.io/api",
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key
        self.api_url = api_url
        self.legacy_api_url = legacy_api_url
        self.timeout = timeout
        self.max_retries = max_retries

    async def _call(self, endpoint: str, url: str) -> httpx.Response:
        query = urllib.parse.urlencode({"api": self.api_key, "url": url})
        target = f"{endpoint}?{query}"
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout, follow_redirects=False
                ) as client:
                    response = await client.get(target)
                if response.status_code in (429, 500, 502, 503, 504):
                    last_error = ShrankMeError(
                        f"ShrinkMe returned HTTP {response.status_code}"
                    )
                    await asyncio.sleep(min(2 ** attempt, 15))
                    continue
                return response
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                logger.warning(
                    "ShrinkMe network error: %s (attempt %s/%s)",
                    exc,
                    attempt,
                    self.max_retries,
                )
                await asyncio.sleep(min(2 ** attempt, 15))
        raise ShrankMeError(
            f"ShrinkMe unreachable after {self.max_retries} tries"
        ) from last_error

    @staticmethod
    def _extract_short_url(text: str) -> str | None:
        """استخراج رابط short من JSON أو نص خام بطريقة مرنة."""
        if not text:
            return None
        text = text.strip()
        # 1) استجابة JSON بها shortenedUrl
        try:
            import json

            payload = json.loads(text)
            # بعض الـ APIs ترجع قائمة كائنات
            if isinstance(payload, list):
                if not payload:
                    return None
                payload = payload[0]
            if isinstance(payload, dict):
                for key in ("shortenedUrl", "short_url", "url", "link", "short", "result"):
                    value = payload.get(key)
                    if isinstance(value, str) and _SHRANKME_RE.match(value):
                        return value
                # حقل "result" قد يكون كائنًا يحتوي الرابط
                if isinstance(payload.get("result"), dict):
                    inner = payload["result"]
                    for key in ("url", "short_url", "link", "short"):
                        value = inner.get(key)
                        if isinstance(value, str) and _SHRANKME_RE.match(value):
                            return value
                # "result" قد يكون قائمة كائنات
                if isinstance(payload.get("result"), list):
                    for inner in payload["result"]:
                        if isinstance(inner, dict):
                            for key in ("url", "short_url", "link", "short"):
                                value = inner.get(key)
                                if isinstance(value, str) and _SHRANKME_RE.match(value):
                                    return value
        except ValueError:
            pass
        # 2) نص رابط مباشر
        if _SHRANKME_RE.match(text):
            return text
        return None

    async def shorten_url(self, url: str) -> str:
        """تقصير رابط وإرجاع رابط shrinkme.io.

        لا تُعتبر العملية ناجحة إلا عند استخراج رابط shrinkme.io صالح.
        """
        if not url.startswith(("http://", "https://")):
            raise ShrankMeError(f"Invalid URL to shorten: {url!r}")

        last_error: ShrankMeError | None = None
        for endpoint in (self.api_url, self.legacy_api_url):
            try:
                response = await self._call(endpoint, url)
            except ShrankMeError as exc:
                last_error = exc
                continue

            if response.status_code in (401, 403):
                raise ShrankMeAuthError(
                    f"ShrinkMe rejected the API key (HTTP {response.status_code})"
                )

            short_url = self._extract_short_url(response.text)
            if short_url:
                return short_url
            last_error = ShrankMeError(
                f"ShrinkMe returned no valid link (endpoint {endpoint}, "
                f"HTTP {response.status_code}): {response.text[:200]!r}"
            )

        raise ShrankMeError(str(last_error) or "ShrinkMe failed to shorten URL")


async def build_shrankme_client() -> ShrankMeClient:
    settings = get_settings()
    if not settings.SHRANKME_API_KEY:
        raise ShrankMeAuthError("SHRANKME_API_KEY is not configured in .env")
    return ShrankMeClient(
        api_key=settings.SHRANKME_API_KEY,
        api_url=settings.SHRANKME_API_URL,
        legacy_api_url=settings.SHRANKME_LEGACY_API_URL,
        timeout=settings.SHRANKME_TIMEOUT,
        max_retries=settings.HTTP_MAX_RETRIES,
    )
