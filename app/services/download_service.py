"""One download resolver for normal and historical SteamRIP callbacks.

Release read transactions before public HTTP and re-read publication/revision/source
before using the result. No signed destination is stored in the catalog.
"""
from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urlsplit

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database.models import Application
from database import repositories as repo
from app.utils.website import website_download_url
from app.utils.download_policy import is_blocked_download_provider_host
from integrations.public_http import public_url
from integrations.steamrip_extractor import fetch_game_data, extract_bzzhr_direct_link, _is_bzzhr_url, ProviderResolutionError

logger = logging.getLogger(__name__)

_ACTIVE: set[tuple[int, int]] = set()


def manual_url(value: str, hosts: set[str] | None = None) -> str:
    if len(value) > 2000 or any(c.isspace() for c in value):
        raise ValueError("INVALID_SOURCE")
    # Any HTTPS URL with a public destination is accepted; the allowlist is no longer
    # required for owner-supplied direct download links. Retired ad-link providers stay blocked.
    try:
        host = urlsplit(value).hostname
    except ValueError as exc:
        raise ValueError("INVALID_SOURCE") from exc
    if is_blocked_download_provider_host(host):
        raise ValueError("UNSUPPORTED_PROVIDER")
    if _is_bzzhr_url(value):
        parsed = urlsplit(value)
        if not re.fullmatch(r"/[A-Za-z0-9_-]+/?", parsed.path) or parsed.query:
            raise ValueError("INVALID_SOURCE")
        return value
    public_url(value)
    if urlsplit(value).netloc != urlsplit(value).hostname:
        raise ValueError("INVALID_SOURCE")
    return value


async def resolve_application_download(session: AsyncSession, application_id: int):
    app = await repo.get_active_application(session, application_id)
    if not app:
        raise ValueError("SOURCE_REMOVED")
    source = await repo.get_delivery_source(session, app.id)
    snapshot = (app.revision, app.custom_download_url, app.source_url)
    if source:
        url = website_download_url(app.id)
        if not url:
            raise ValueError("INVALID_SOURCE")
        await session.commit()
        return app, url, "telegram"
    custom, original = app.custom_download_url, app.source_url
    await session.commit()  # No transaction (including middleware reads) across HTTP.
    direct_source = custom if custom and _is_bzzhr_url(custom) else original if not custom and original and _is_bzzhr_url(original) else None
    if direct_source:
        url = await extract_bzzhr_direct_link(direct_source, strict=True)
        if not url:
            raise ValueError("PROVIDER_UNAVAILABLE")
        provider = "bzzhr"
    elif custom:
        url, provider = manual_url(custom), "external"
    elif original and urlsplit(original).hostname in {"steamrip.com", "www.steamrip.com"}:
        public_url(original, {"steamrip.com", "www.steamrip.com"})
        async with asyncio.timeout(30):
            data = await fetch_game_data(original)
            candidates = list(dict.fromkeys(u for u in data.get("servers", {}).values() if _is_bzzhr_url(u)))[:3]
            if not candidates:
                raise ValueError("BZZHR_NOT_FOUND")
            url, failure = None, None
            for bzzhr in candidates:
                try:
                    url = await extract_bzzhr_direct_link(bzzhr, source_page_url=original, strict=True)
                    if url:
                        break
                except ProviderResolutionError as error:
                    failure = error
                    if error.code in {"PROVIDER_CHALLENGE", "PROVIDER_LOGIN_REQUIRED", "PROVIDER_RATE_LIMITED", "PROVIDER_FORBIDDEN"}:
                        raise
            if not url and failure:
                raise failure
        if not url:
            raise ValueError("PROVIDER_UNAVAILABLE")
        provider = "bzzhr"
    else:
        if not original:
            raise ValueError("SOURCE_REMOVED")
        url, provider = manual_url(original), "external"
    current = await session.scalar(select(Application).where(Application.id == application_id)
        .execution_options(populate_existing=True))
    current_source = await repo.get_delivery_source(session, application_id)
    if (not current or not current.active or not current.published or current_source
            or (current.revision, current.custom_download_url, current.source_url) != snapshot):
        await session.rollback()
        raise ValueError("SOURCE_CHANGED")
    await session.commit()
    return current, url, provider


async def send_application_download(call, session: AsyncSession, application_id: int, *, edit=False):
    from app.utils.text import final_download_message
    key = (call.from_user.id, application_id)
    if key in _ACTIVE or len(_ACTIVE) >= 32:
        await call.answer("الطلب قيد المعالجة؛ انتظر قليلًا.")
        return
    _ACTIVE.add(key)
    try:
        await call.answer("⏳ جارٍ تجهيز المصدر...")
        app, url, provider = await resolve_application_download(session, application_id)
        text = final_download_message(app, url)
        # Commit counters before sending to Telegram; never hold a transaction during API I/O.
        if provider != "telegram":
            await repo.increment_downloads(session, app.id)
            await repo.add_download(session, call.from_user.id, app.id)
            await session.commit()
        if edit:
            await call.message.edit_text(text, reply_markup=None)
        else:
            await call.message.answer(text)
    except ProviderResolutionError as error:
        await session.rollback()
        logger.warning("download failed application_id=%s stage=%s host=%s status=%s category=%s",
            application_id, error.stage, error.host, error.status, error.code)
        
        # Cloudflare challenges must be completed by the user in their browser.
        # The website download page does not consume pending-download tokens or send
        # a solved provider URL back to this bot, so do not create an orphaned token
        # or promise an automatic return path that is not implemented.
        if error.code == "PROVIDER_CHALLENGE":
            web_url = website_download_url(application_id)
            if not web_url:
                await call.message.answer(
                    "⚠️ المصدر يتطلب تحققًا بشريًا (Cloudflare)، وتعذر تكوين رابط الموقع. "
                    "أعد المحاولة لاحقًا."
                )
                return

            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🌐 فتح صفحة التحميل بالموقع",
                            url=web_url,
                        )
                    ]
                ]
            )
            msg_text = (
                "⚠️ رفض المصدر معالجة الطلب آليًا وطلب تحققًا بشريًا (Cloudflare).\n\n"
                "افتح صفحة التحميل بالموقع. إذا استمر الرفض، ستجد زرًا لفتح صفحة المصدر "
                "وتنزيل الملف من متصفحك.\n\n"
                "ملاحظة: إكمال التحقق في موقع المصدر لا يعيد رابط الملف إلى البوت تلقائيًا."
            )
            await call.message.answer(msg_text, reply_markup=kb)
            return

        messages = {
            "SOURCE_REMOVED": "ملف المصدر محذوف أو لم يعد متاحًا.",
            "MISSING_HX_REDIRECT": "المصدر لم يُرجع رابط الملف بعد طلب التنزيل.",
            "FINAL_DESTINATION_NOT_FILE": "خادم المصدر أعاد صفحة بدل ملف قابل للتنزيل.",
        }
        await call.message.answer(messages.get(error.code, "تعذر تجهيز مصدر التحميل. أعد المحاولة لاحقًا.") + "\n" + (website_download_url(application_id) or ""))
    except (ValueError, TimeoutError):
        await session.rollback()
        await call.message.answer("تعذر تجهيز الرابط حاليًا. قد يكون المصدر تغيّر؛ افتح صفحة التحميل في Waleed Zone أو أعد المحاولة لاحقًا.\n" + (website_download_url(application_id) or ""))
    except Exception:
        await session.rollback()
        logger.warning("download failed application_id=%s category=unavailable", application_id)
        await call.message.answer("تعذر تجهيز التحميل. أعد المحاولة بعد قليل.")
    finally:
        _ACTIVE.discard(key)