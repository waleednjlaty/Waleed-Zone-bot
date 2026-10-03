# DEPRECATED: offline legacy reference only; never imported by runtime upload flow.
"""تكامل رسمي مع DevUploads (devuploads.com) باستخدام وثائقهم الرسمية.

التدفق الموثق (من https://devuploads.com/api و script الرفع الرسمي upload.sh):
    1) GET  {base}/api/upload/server?key=KEY
         -> {"status":200, "sess_id":"...", "result":"https://s01.devuploads.com/upload/01"}
    2) POST {result}  (multipart/form-data)
         - sess_id  : القيمة المرجعة من الخطوة 1
         - utype    : "reg"
         - file     : الملف
         -> {"status":200, "file_code":"..."} (أو على شكل قائمة عناصر)
    3) رابط الملف: {base}/{file_code}
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from config import get_settings

logger = logging.getLogger(__name__)


class DevUploadError(Exception):
    """خطأ عام في تكامل DevUploads."""


class DevUploadAuthError(DevUploadError):
    """مفتاح API غير صالح أو غير مفوَّض."""


class DevUploadFileError(DevUploadError):
    """فشل رفع الملف نفسه."""


class DevUploadsClient:
    """عميل غير متزامن لرفع الملفات إلى DevUploads عبر API الرسمي."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://devuploads.com",
        timeout: float = 300.0,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    async def _request(
        self, client: httpx.AsyncClient, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        """تنفيذ طلب مع إعادة محاولة مرنة عند أخطاء الشبكة/الخادم."""
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                wait = min(2 ** attempt, 15)
                logger.warning(
                    "DevUploads network error (%s) on %s, retry %s/%s",
                    exc,
                    url,
                    attempt,
                    self.max_retries,
                )
                await asyncio.sleep(wait)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (401, 403):
                    raise DevUploadAuthError(
                        f"DevUploads API key is invalid or unauthorized (HTTP {exc.response.status_code})"
                    ) from exc
                raise DevUploadError(
                    f"DevUploads HTTP {exc.response.status_code} on {url}"
                ) from exc
        raise DevUploadError(f"DevUploads unreachable after {self.max_retries} tries") from last_error

    @staticmethod
    def _parse_json(response: httpx.Response) -> Any:
        """تحويل نص الاستجابة إلى JSON بمرونة (حتى لو كان HTML/نص عادي)."""
        try:
            return response.json()
        except ValueError:
            try:
                return json.loads(response.text)
            except ValueError:
                return {"raw_text": response.text[:2000]}

    def _validate_json(self, payload: Any, *, expected_field: str) -> str:
        """استخراج حقل نصي من JSON صالح (سواء كان Dict أو List)، أو رفع خطأ واضح."""
        if isinstance(payload, list):
            if not payload:
                raise DevUploadError(f"DevUploads returned empty list: {payload!r}")
            payload = payload[0]

        if not isinstance(payload, dict):
            raise DevUploadError(f"DevUploads returned non-JSON object: {payload!r}")

        status = payload.get("status")
        if status not in (200, None) and payload.get("file_status") != "OK":
            msg = payload.get("msg") or payload.get("error") or payload
            if str(status) == "401":
                raise DevUploadAuthError(f"Invalid DevUploads API key: {msg}")
            raise DevUploadError(f"DevUploads error: {msg}")

        value = payload.get(expected_field)
        if not value:
            result = payload.get("result")
            if isinstance(result, dict):
                value = result.get(expected_field)
            elif isinstance(result, list) and result and isinstance(result[0], dict):
                value = result[0].get(expected_field)
        if not value:
            raise DevUploadError(
                f"DevUploads response missing '{expected_field}': {payload!r}"
            )
        return str(value)

    async def get_upload_server(self) -> tuple[str, str]:
        """إرجاع (upload_url, sess_id)."""
        url = f"{self.base_url}/api/upload/server?key={self.api_key}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await self._request(client, "GET", url)
            payload = self._parse_json(response)

        if isinstance(payload, list) and payload:
            payload = payload[0]
        if not isinstance(payload, dict):
            raise DevUploadError(
                f"DevUploads invalid server response: {payload!r}"
            )

        upload_url = self._validate_json(payload, expected_field="result")
        sess_id = payload.get("sess_id")
        if not sess_id:
            raise DevUploadError(
                f"DevUploads response missing 'sess_id': {payload!r}"
            )
        return upload_url, str(sess_id)

    async def upload_file(self, file_path: Path, filename: str | None = None) -> str:
        """رفع ملف وتكوين رابط DevUploads (https://devuploads.com/{file_code})."""
        path = Path(file_path)
        if not path.is_file():
            raise DevUploadFileError(f"File not found: {path}")
        if path.stat().st_size == 0:
            raise DevUploadFileError(f"File is empty: {path}")

        upload_url, sess_id = await self.get_upload_server()
        if not upload_url.startswith("http"):
            raise DevUploadError(f"Invalid upload server URL: {upload_url!r}")

        name = filename or path.name
        with path.open("rb") as fh:
            files = {
                "sess_id": (None, sess_id),
                "utype": (None, "reg"),
                "file": (name, fh),
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    response = await client.post(upload_url, files=files)
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    raise DevUploadFileError(
                        f"Upload failed (network): {exc}"
                    ) from exc

        if response.status_code >= 400:
            raise DevUploadFileError(
                f"Upload failed with HTTP {response.status_code}"
            )

        try:
            payload = self._parse_json(response)
        except Exception as exc:
            raise DevUploadFileError(
                f"Upload response is not JSON (may be HTML error page): "
                f"{response.text[:200]!r}"
            ) from exc

        file_code = self._validate_json(payload, expected_field="file_code")
        return f"{self.base_url}/{file_code}"

    async def file_info(self, file_code: str) -> dict[str, Any] | None:
        """استرجاع معلومات ملف (اختياري — للتحقق بعد الرفع)."""
        url = (
            f"{self.base_url}/api/file/info"
            f"?key={self.api_key}&file_code={file_code}"
        )
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await self._request(client, "GET", url)
            payload = self._parse_json(response)

        if isinstance(payload, list) and payload:
            payload = payload[0]

        if not isinstance(payload, dict) or (payload.get("status") not in (200, None) and payload.get("file_status") != "OK"):
            return None

        result = payload.get("result")
        if isinstance(result, list) and result:
            return result[0] if isinstance(result[0], dict) else payload
        return result if isinstance(result, dict) else payload


async def build_devupload_client() -> DevUploadsClient:
    settings = get_settings()
    if not settings.DEVUPLOAD_API_KEY:
        raise DevUploadAuthError(
            "DEVUPLOAD_API_KEY is not configured in .env"
        )
    return DevUploadsClient(
        api_key=settings.DEVUPLOAD_API_KEY,
        base_url=settings.DEVUPLOAD_BASE_URL,
        timeout=settings.DEVUPLOAD_TIMEOUT,
        max_retries=settings.HTTP_MAX_RETRIES,
    )